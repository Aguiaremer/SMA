# Protótipo inicial: SMA para AES-DPR

Este protótipo representa uma rodada do fluxo proposto no diagrama Prometheus. O ambiente e os parâmetros ainda são simulados: não há conexão com Vivado, execução de CPA, bitstreams parciais ou ICAP real.

## Arquivos

- `main.py`: cria o ambiente, o Trigger, a Escolha e um agente por setor.
- `fpga_env.py`: mantém módulos ativos, estado atual, leituras de potência, ICAP e orçamento; a troca é simulada.
- `agents.py`: contém a lógica dos agentes e as mensagens entre eles.

## Fluxo representado

1. Cada agente de setor consulta o módulo ativo e seu catálogo, calcula uma utilidade e envia sua melhor proposta.
2. O Trigger lê os perceptos de potência e estado atual, atualiza sua exposição por setor e envia um sinal quando cruza o limiar ilustrativo.
3. A Escolha mantém as propostas recebidas. Se o sinal chegar antes das propostas, guarda o sinal até que todos os setores tenham enviado uma proposta.
4. A Escolha seleciona uma proposta compatível com o orçamento e pede ao ambiente a reconfiguração.
5. O ambiente atualiza o módulo e `estado_atual`, debita o custo e libera a ICAP. A percepção da mudança permite que o setor prepare uma nova proposta e o Trigger reinicie sua exposição.

## Parâmetros provisórios

Os catálogos, leituras de potência, limiar do Trigger, pesos da utilidade e orçamento são valores de demonstração. Precisam ser substituídos ou calibrados quando o grupo definir os dados do Vivado e a política final. A exposição acumula os valores simulados de potência como aproximação didática; não representa diretamente uma contagem CPA real.
