"""Ponto de entrada do esqueleto MASPY AES-DPR."""

from maspy import Admin, Channel

from agents import ChoiceAgent, SectorAgent, TriggerAgent
from fpga_env import FPGAEnvironment


if __name__ == "__main__":
    Admin(listener_log=True)
    Channel().show_exec = True

    fpga = FPGAEnvironment()
    trigger = TriggerAgent()
    choice = ChoiceAgent(
        sectors=fpga.catalog.keys(),
        budget=fpga.reconfiguration_budget,
    )
    sectors = [
        SectorAgent(name="agente_setor_0", sector="setor_0", catalog=fpga.catalog["setor_0"]),
        SectorAgent(name="agente_setor_1", sector="setor_1", catalog=fpga.catalog["setor_1"]),
    ]

    for agent in [trigger, choice, *sectors]:
        agent.connect_to(fpga)
        agent.connect_to("default")
        agent.perceive("FPGA")

    # Os ciclos dos agentes processam a meta do Trigger e as crenças percebidas.
    Admin().start_system()
