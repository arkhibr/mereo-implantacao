"""
Núcleo de execução de agentes LLM.

Este módulo concentra a infraestrutura usada pelos agentes baseados em LLM:
cliente Anthropic, registro de tools, runner com loop manual, mecanismo
de human-in-the-loop e persistência de sessões.

Os agentes deterministas (areas, colaboradores, metas, etc.) continuam
usando seu próprio módulo `agentes/<nome>/agente.py` — este núcleo serve
aos agentes que dependem de julgamento (diagnostico, mapeamento,
validacao, orquestrador) e os aciona via tool calls.
"""

__version__ = "0.1.0"
