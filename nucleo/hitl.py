"""
Mecanismo de human-in-the-loop.

Quando o agente LLM precisa de uma decisão humana, ele invoca a tool
`perguntar_humano`. A função registrada para essa tool levanta a exceção
`HITLPausaSolicitada`, que o runner captura para gravar o estado da
sessão e devolver controle ao CLI. O consultor responde via
`./implantacao responder <cliente> <sessao_id>` e o runner retoma a partir
do estado salvo, injetando a resposta como `tool_result`.
"""
from dataclasses import dataclass

from .registro_tools import SinalControle, Tool


NOME_TOOL = "perguntar_humano"


@dataclass
class HITLPausaSolicitada(SinalControle):
    """Levantada pelo agente para pausar a execução até resposta humana."""
    pergunta: str = ""
    contexto: str = ""
    opcoes: list[str] | None = None
    tool_use_id: str | None = None  # preenchido pelo runner ao capturar

    def __str__(self) -> str:
        return f"HITL: {self.pergunta}"


def _tool_perguntar_humano(pergunta: str, contexto: str = "", opcoes: list[str] | None = None) -> str:
    raise HITLPausaSolicitada(pergunta=pergunta, contexto=contexto, opcoes=opcoes)


def construir_tool_hitl() -> Tool:
    """Devolve a Tool padrão de HITL para registrar no agente."""
    return Tool(
        nome=NOME_TOOL,
        descricao=(
            "Faça uma pergunta ao consultor humano e pause a execução até a resposta. "
            "Use quando precisar de uma decisão de domínio, validação de mapeamento "
            "ambíguo ou autorização para uma ação irreversível. NÃO use para erros "
            "técnicos comuns — esses devem ser resolvidos pelo próprio agente. "
            "A execução é interrompida e retomada depois pelo CLI."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pergunta": {
                    "type": "string",
                    "description": "Pergunta clara e objetiva, em PT-BR.",
                },
                "contexto": {
                    "type": "string",
                    "description": "Informações relevantes para a decisão (trechos de dados, alternativas consideradas, riscos).",
                },
                "opcoes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista opcional de respostas sugeridas. Use quando a resposta cabe num conjunto fechado.",
                },
            },
            "required": ["pergunta"],
        },
        funcao=_tool_perguntar_humano,
    )
