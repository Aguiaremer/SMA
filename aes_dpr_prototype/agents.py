"""Agentes MASPY do protótipo AES-DPR, organizados conforme o diagrama."""

from time import monotonic

from maspy import Agent, Any, Belief, Goal, gain, pl, tell


class TriggerAgent(Agent):
    """Mantém exposição por setor e envia um sinal quando cruza o limiar."""

    def __init__(self, name="trigger", threshold=0.70):
        super().__init__(name, max_intentions=1)
        self.threshold = threshold
        self.exposure = {}
        self.past_module = {}
        self.add(Goal("avaliar_risco"))

    @pl(gain, Goal("avaliar_risco"))
    def evaluate_risk(self, src):
        # Uma avaliação por execução. Novas leituras do simulador poderão
        # gerar novas avaliações quando a integração contínua for adicionada.
        self.perceive("FPGA")
        readings = self.get(
            Belief("potencia", (Any, Any), "FPGA"), all=True
        ) or []
        current_states = self.get(
            Belief("estado_atual", (Any, Any), "FPGA"), all=True
        ) or []

        for state in current_states:
            sector, module = state.values
            previous_module = self.past_module.get(sector)
            if previous_module is not None and previous_module != module:
                self.exposure[sector] = 0.0
            self.past_module[sector] = module
            self.exposure.setdefault(sector, 0.0)

        candidates = []
        for reading in readings:
            sector, power_w = reading.values
            self.exposure[sector] = self.exposure.get(sector, 0.0) + power_w
            urgency = self.exposure[sector] / self.threshold
            if urgency >= 1.0:
                candidates.append((sector, min(urgency, 1.0)))

        if candidates:
            sector, urgency = max(candidates, key=lambda item: item[1])
            self.send("escolha", tell, Belief("sinal", (sector, urgency)))
            self.print(f"Sinal enviado: setor={sector}, urgência={urgency:.2f}")
        else:
            self.print("Nenhum setor cruzou o limiar de exposição nesta leitura.")

    @pl(gain, Belief("estado_atual", (Any, Any), "FPGA"))
    def observe_module_change(self, src, state):
        sector, module = state
        previous_module = self.past_module.get(sector)
        if previous_module is not None and previous_module != module:
            self.exposure[sector] = 0.0
            self.print(f"Exposição de {sector} reiniciada após troca de módulo.")
        self.past_module[sector] = module


class ChoiceAgent(Agent):
    """Guarda propostas e executa a melhor quando recebe um sinal."""

    def __init__(self, name="escolha", sectors=None, budget=10):
        super().__init__(name, max_intentions=1)
        self.expected_sectors = set(sectors or [])
        self.budget = budget
        self.proposals = {}
        self.pending_signal = None
        self.reconfiguration_running = False

    @pl(gain, Belief("proposta", (Any, Any, Any, Any, Any)))
    def save_proposal(self, src, proposal):
        sector, active_module, new_module, utility, cost = proposal
        self.proposals[sector] = {
            "active_module": active_module,
            "new_module": new_module,
            "utility": utility,
            "cost": cost,
            "received_at": monotonic(),
        }
        self.print(
            f"Proposta recebida: {sector} {active_module} -> {new_module}; "
            f"U={utility:.3f}, custo={cost}"
        )
        self._try_pending_reconfiguration()

    @pl(gain, Belief("sinal", (Any, Any)))
    def receive_signal(self, src, signal):
        self.pending_signal = signal
        sector, urgency = signal
        self.print(f"Sinal recebido: setor={sector}, urgência={urgency:.2f}")
        self._try_pending_reconfiguration()

    def _try_pending_reconfiguration(self):
        if self.pending_signal is None or self.reconfiguration_running:
            return

        # Aguarda as propostas iniciais de todos os setores. Assim, a ordem
        # de chegada das mensagens não faz a Escolha tomar uma decisão cedo.
        if self.expected_sectors and not self.expected_sectors.issubset(self.proposals):
            waiting = self.expected_sectors.difference(self.proposals)
            self.print(f"Aguardando propostas dos setores: {sorted(waiting)}")
            return

        urgent_sector, urgency = self.pending_signal
        eligible = [
            (sector, proposal)
            for sector, proposal in self.proposals.items()
            if proposal["cost"] <= self.budget
        ]
        if not eligible:
            self.print(f"Sem propostas dentro do orçamento restante ({self.budget}).")
            self.pending_signal = None
            return

        def score(item):
            sector, proposal = item
            age = monotonic() - proposal["received_at"]
            urgency_bonus = urgency if sector == urgent_sector else 0.0
            return proposal["utility"] + urgency_bonus + 0.01 * age

        sector, proposal = max(eligible, key=score)
        self.reconfiguration_running = True
        self.print(
            f"Selecionada troca {sector} -> {proposal['new_module']} "
            f"(urgência={urgency:.2f}, orçamento={self.budget})."
        )
        completed = self.reconfigure(
            sector, proposal["new_module"], proposal["cost"]
        )
        if completed:
            self.budget -= proposal["cost"]
            self.proposals.pop(sector, None)
            self.pending_signal = None
            self.print(f"Troca concluída. Orçamento restante: {self.budget}.")
        else:
            self.print("Troca não concluída; o sinal permanece pendente.")
        self.reconfiguration_running = False


class SectorAgent(Agent):
    """Calcula e mantém a proposta de melhor módulo para um setor."""

    W_SECURITY = 1.0
    W_RECONFIGURATION = 0.10
    W_OPERATION = 0.05
    RECENT_USE_PENALTY = 0.15

    def __init__(self, name, sector, catalog):
        super().__init__(name, max_intentions=1)
        self.sector = sector
        # Cada entrada: (nome, ganho de segurança, custo de reconfiguração,
        # custo de operação). Valores fictícios para demonstrar o fluxo.
        self.catalog = catalog
        self.turn = 0
        self.last_used = {module[0]: -100 for module in catalog}
        self.active_module = None
        self.last_proposed_state = None
        self.add(Goal("preparar_proposta"))

    @pl(gain, Goal("preparar_proposta"))
    def prepare_initial_proposal(self, src):
        self.perceive("FPGA")
        self._propose_for_current_module()

    @pl(gain, Belief("modulo", (Any, Any), "FPGA"))
    def module_changed(self, src, module_state):
        sector, active_module = module_state
        if sector == self.sector:
            self._propose(active_module)

    def _propose_for_current_module(self):
        current = self.get(
            Belief("modulo", (self.sector, Any), "FPGA")
        )
        if current:
            self._propose(current.values[1])
        else:
            self.print(f"Não encontrei o módulo ativo de {self.sector}.")

    def _propose(self, active_module):
        if self.last_proposed_state == active_module:
            return

        if self.active_module is not None and self.active_module != active_module:
            self.turn += 1
            self.last_used[self.active_module] = self.turn
        self.active_module = active_module
        self.last_used[active_module] = self.turn

        candidates = [entry for entry in self.catalog if entry[0] != active_module]
        if not candidates:
            self.print(f"Catálogo de {self.sector} não tem módulo alternativo.")
            return

        scored = []
        for module, security_gain, reconfiguration_cost, operation_cost in candidates:
            recently_used = self.turn - self.last_used.get(module, -100) <= 1
            recent_penalty = self.RECENT_USE_PENALTY if recently_used else 0.0
            utility = (
                self.W_SECURITY * security_gain
                - self.W_RECONFIGURATION * reconfiguration_cost
                - self.W_OPERATION * operation_cost
                - recent_penalty
            )
            scored.append((utility, module, reconfiguration_cost))

        utility, new_module, cost = max(scored, key=lambda item: item[0])
        self.last_proposed_state = active_module
        self.send(
            "escolha",
            tell,
            Belief(
                "proposta",
                (self.sector, active_module, new_module, utility, cost),
            ),
        )
        self.print(
            f"Proposta enviada: {self.sector} {active_module} -> {new_module}; "
            f"U={utility:.3f}, custo={cost}"
        )
