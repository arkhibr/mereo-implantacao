"""
Agente LLM de exemplo — demonstração da espinha dorsal.

Este agente NÃO faz parte do pipeline real. Existe para validar a infra
do núcleo (runner, tools, HITL, sessões) com um caso mínimo antes de
migrar os agentes de diagnóstico/mapeamento/validação para o paradigma
LLM.

A tarefa é trivial: listar os arquivos brutos do cliente e descrever
brevemente o que parece haver em cada um. Caso encontre algo ambíguo
ou inesperado, deve perguntar ao consultor via `perguntar_humano`.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from nucleo.hitl import construir_tool_hitl
from nucleo.registro_tools import RegistroTools, Tool
from nucleo.runner import executar_agente


PROMPT_BASE = (Path(__file__).parent.parent.parent / "prompts/sistema/base_agente.md").read_text(encoding="utf-8")

PROMPT_TAREFA = (
    "Liste os arquivos em raw/, descreva cada um em uma linha e sintetize "
    "o que parece disponível para iniciar a implantação. "
    "Se identificar AMBIGUIDADE relevante entre arquivos sobrepostos (por exemplo, "
    "dois arquivos que cobrem a mesma entidade ou cujo papel não fica claro pelo nome), "
    "você DEVE invocar a tool `perguntar_humano` ANTES de gerar a resposta final. "
    "Não conclua sem decidir, nem deixe perguntas no texto final."
)


def _listar_raw(pasta_cliente: str) -> dict:
    """Lista arquivos da pasta raw/ do cliente, com tamanho em KB."""
    raw = Path(pasta_cliente) / "raw"
    if not raw.exists():
        return {"status": "erro", "erros": [f"Pasta não encontrada: {raw}"]}
    arquivos = []
    for f in sorted(raw.rglob("*")):
        if f.is_file():
            arquivos.append({
                "nome": str(f.relative_to(raw)),
                "extensao": f.suffix.lower(),
                "tamanho_kb": round(f.stat().st_size / 1024, 1),
            })
    return {"status": "ok", "dados": {"total": len(arquivos), "arquivos": arquivos}}


def construir_registro(pasta_cliente: str) -> RegistroTools:
    registro = RegistroTools()
    registro.registrar(Tool(
        nome="listar_arquivos_raw",
        descricao=(
            "Lista os arquivos em raw/ do cliente com nome relativo, extensão e "
            "tamanho em KB. Use no início para entender o que foi disponibilizado."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=lambda: _listar_raw(pasta_cliente),
        paralela=True,
    ))
    registro.registrar(construir_tool_hitl())
    return registro


def executar(pasta_cliente: str):
    """Dispara a sessão LLM. Retorna ResultadoExecucao."""
    registro = construir_registro(pasta_cliente)
    return executar_agente(
        cliente_path=Path(pasta_cliente),
        agente="exemplo_llm",
        prompt_sistema=PROMPT_BASE,
        tarefa=PROMPT_TAREFA,
        registro=registro,
    )
