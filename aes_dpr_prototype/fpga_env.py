"""Ambiente MASPY simplificado para o sistema AES com reconfiguração parcial."""

from threading import Lock

from maspy import Any, Environment, Percept


class FPGAEnvironment(Environment):
    """Mantém perceptos dos setores, da potência, da ICAP e do orçamento."""

    def __init__(self, env_name="FPGA", budget=10):
        super().__init__(env_name)
        self.reconfiguration_budget = budget
        self.icap_busy = False
        self.icap_lock = Lock()
        self.catalog = {
            # (módulo, ganho de segurança, custo de reconfiguração, custo de operação)
            "setor_0": [
                ("sbox_bram", 0.85, 2, 0.10),
                ("sbox_logic", 0.70, 1, 0.08),
            ],
            "setor_1": [
                ("round_masked", 0.90, 3, 0.12),
                ("round_compact", 0.65, 1, 0.10),
            ],
        }

        # Perceptos criados um a um por compatibilidade com a versão MASPY
        # instalada neste projeto.
        initial_percepts = [
            Percept("modulo", ("setor_0", "sbox_bram")),
            Percept("modulo", ("setor_1", "round_masked")),
            Percept("estado_atual", ("setor_0", "sbox_bram")),
            Percept("estado_atual", ("setor_1", "round_masked")),
            # Leituras de exemplo, em watts. O limiar do Trigger também é
            # ilustrativo e deve ser calibrado com os dados reais do projeto.
            Percept("potencia", ("setor_0", 0.62)),
            Percept("potencia", ("setor_1", 0.71)),
            Percept("estado_icap", "livre"),
        ]
        for percept in initial_percepts:
            self.create(percept)

    def reconfigure(self, agent_name, sector, module, cost):
        """Simula uma troca pela ICAP e atualiza os perceptos do ambiente."""
        with self.icap_lock:
            if self.icap_busy:
                self.print(f"ICAP ocupada; troca de {sector} foi recusada.")
                return False
            if cost > self.reconfiguration_budget:
                self.print(
                    f"Orçamento insuficiente para a troca de {sector}: "
                    f"custo={cost}, restante={self.reconfiguration_budget}."
                )
                return False

            current = self.get(Percept("modulo", (sector, Any)))
            if current is None:
                self.print(f"Setor desconhecido: {sector}.")
                return False

            self.icap_busy = True
            self._set_percept("estado_icap", "ocupada")
            self.print(
                f"{agent_name} iniciou reconfiguração de {sector} para {module}."
            )

            self._set_percept("modulo", (sector, module))
            self._set_percept("estado_atual", (sector, module))
            self.reconfiguration_budget -= cost

            self.icap_busy = False
            self._set_percept("estado_icap", "livre")
            self.print(
                f"Reconfiguração concluída; orçamento restante="
                f"{self.reconfiguration_budget}."
            )
            self._notify_change()
            return True

    def _set_percept(self, name, values):
        if name in {"modulo", "estado_atual"}:
            query = Percept(name, (values[0], Any))
        else:
            query = Percept(name, Any)
        current = self.get(query)
        normalized_values = values if isinstance(values, tuple) else (values,)
        if current is None:
            self.create(Percept(name, normalized_values))
        else:
            # Substituir o percept gera uma mudança inequívoca para os agentes
            # que comparam os perceptos atuais com suas crenças anteriores.
            self.delete(current)
            self.create(Percept(name, normalized_values))
