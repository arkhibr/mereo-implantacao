"""
Agente de Mapeamento — versão LLM.

Lê o SOP-prompt em `sops/agentes/sop_mapeamento.md` como instrução, expõe
ferramentas determinísticas para inspeção e sugestão de correspondência,
e produz `config/mapeamento.json` no mesmo formato esperado pelas etapas
seguintes (transformação).
"""
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentes.mapeamento.agente import (
    SINONIMOS,
    TRANSFORMACOES_PADRAO,
    _encontrar_melhor_correspondencia,
)
from nucleo.hitl import construir_tool_hitl
from nucleo.registro_tools import RegistroTools, Tool
from nucleo.runner import executar_agente


BASE_PROJETO = Path(__file__).parent.parent.parent
TEMPLATES_DIR = BASE_PROJETO / "templates"

# Mapa nome do arquivo CSV → chave canônica usada no mapeamento.json.
TEMPLATES_ENTIDADES = {
    "Import_Áreas (Estrutura Hierárquica).csv": "areas",
    "Import_Colaboradores.csv": "colaboradores",
    "Import_Indicadores (KPI).csv": "indicadores",
    "Import_Metas Individuais.csv": "metas_individuais",
    "Import_Metas Compartilhadas.csv": "metas_compartilhadas",
    "Import_Metas Projeto.csv": "metas_projeto",
    "Import_Curva de Alcance.csv": "curva_alcance",
}

PROMPT_SISTEMA = (
    (BASE_PROJETO / "prompts/sistema/base_agente.md").read_text(encoding="utf-8")
    + "\n\n---\n\n"
    + (BASE_PROJETO / "sops/agentes/sop_mapeamento.md").read_text(encoding="utf-8")
)

PROMPT_TAREFA = (
    "Construa o mapeamento campo a campo entre os dados do cliente e os "
    "templates da plataforma. Siga o procedimento descrito no SOP. Ao final, "
    "garanta que config/mapeamento.json foi gerado, ou que o motivo de não "
    "ter sido gerado está claro na sua resposta final (ex: arquivo travado)."
)


def construir_registro(pasta_cliente: str, sessao=None) -> RegistroTools:
    base = Path(pasta_cliente)
    config = base / "config"
    config.mkdir(parents=True, exist_ok=True)

    def _resolver(arquivo_rel: str) -> Path:
        f = (base / arquivo_rel).resolve()
        if not str(f).startswith(str(base.resolve())):
            raise ValueError("Caminho fora do diretório do cliente.")
        return f

    # ── Tools ────────────────────────────────────────────────────────────────

    def t_diagnostico() -> dict:
        caminho = config / "diagnostico.json"
        if not caminho.exists():
            return {
                "status": "erro",
                "erros": [
                    "config/diagnostico.json não encontrado. Rode o agente de "
                    "diagnóstico primeiro (./implantacao diagnosticar <cliente>)."
                ],
            }
        diagnostico = json.loads(caminho.read_text(encoding="utf-8"))
        resumo = {}
        for entrada in diagnostico:
            arq = entrada.get("arquivo")
            if not arq:
                continue
            resumo[arq] = {}
            perfil = entrada.get("perfil") or {}
            for aba in perfil.get("abas", []) or []:
                if not isinstance(aba, dict):
                    continue
                nome = aba.get("nome")
                if not nome:
                    continue
                colunas = [c.get("nome") for c in (aba.get("colunas") or []) if isinstance(c, dict)]
                resumo[arq][nome] = {
                    "total_linhas": aba.get("total_linhas"),
                    "colunas": colunas,
                }
        return {"status": "ok", "dados": resumo}

    def t_entidades() -> dict:
        entidades = {}
        for nome_arquivo, chave in TEMPLATES_ENTIDADES.items():
            caminho = TEMPLATES_DIR / nome_arquivo
            if not caminho.exists():
                continue
            df = pd.read_csv(str(caminho), sep=";", nrows=0, encoding="latin-1")
            campos = []
            for col in df.columns:
                campos.append({
                    "campo": col,
                    "obrigatorio": col.endswith("*"),
                    "transformacao_sugerida": TRANSFORMACOES_PADRAO.get(col, "direto"),
                })
            entidades[chave] = {"arquivo_template": nome_arquivo, "campos": campos}
        return {"status": "ok", "dados": entidades}

    def t_amostras(arquivo_relativo: str, aba: str, n: int = 5) -> dict:
        try:
            f = _resolver(arquivo_relativo)
        except ValueError as e:
            return {"status": "erro", "erros": [str(e)]}
        if not f.exists():
            return {"status": "erro", "erros": [f"Arquivo não encontrado: {arquivo_relativo}"]}

        n = max(1, min(int(n or 5), 20))
        try:
            if f.suffix.lower() == ".csv":
                df = pd.read_csv(str(f), sep=None, engine="python", encoding_errors="replace", nrows=n)
            else:
                df = pd.read_excel(str(f), sheet_name=aba, engine="openpyxl", nrows=n)
        except Exception as e:
            return {"status": "erro", "erros": [f"Falha ao ler aba '{aba}': {e}"]}

        amostras = json.loads(df.head(n).to_json(orient="records", force_ascii=False, default_handler=str))
        return {
            "status": "ok",
            "dados": {
                "colunas": [str(c) for c in df.columns],
                "linhas": amostras,
                "total_lidas": len(amostras),
            },
        }

    def t_sugerir(campo_template: str, colunas: list) -> dict:
        if not isinstance(colunas, list):
            return {"status": "erro", "erros": ["colunas deve ser uma lista de strings"]}
        melhor = _encontrar_melhor_correspondencia(campo_template, colunas)
        sinonimos = SINONIMOS.get(campo_template, [])
        if melhor is None:
            return {
                "status": "ok",
                "dados": {
                    "campo_template": campo_template,
                    "candidata": None,
                    "score": 0,
                    "confianca": "nenhuma",
                    "sinonimos_conhecidos": sinonimos,
                },
            }
        return {
            "status": "ok",
            "dados": {
                "campo_template": campo_template,
                "candidata": melhor["campo"],
                "score": melhor["score"],
                "confianca": melhor["confianca"],
                "sinonimos_conhecidos": sinonimos,
            },
        }

    def t_gravar(mapeamento: dict) -> dict:
        if not isinstance(mapeamento, dict) or not mapeamento:
            return {"status": "erro", "erros": ["mapeamento deve ser um objeto não-vazio"]}

        caminho = config / "mapeamento.json"
        if caminho.exists():
            try:
                existente = json.loads(caminho.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existente = {}
            if isinstance(existente, dict) and existente.get("travado"):
                return {
                    "status": "aviso",
                    "avisos": [
                        "mapeamento.json está travado ('travado': true) — não foi sobrescrito. "
                        "Remova o flag manualmente para regenerar."
                    ],
                    "dados": {"arquivo": str(caminho.relative_to(base)), "travado": True},
                }

        caminho.write_text(
            json.dumps(mapeamento, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        total = len(mapeamento)
        com_fonte = sum(1 for v in mapeamento.values() if isinstance(v, dict) and v.get("arquivo_sugerido"))
        obrig_sem_fonte = []
        for entidade, bloco in mapeamento.items():
            if not isinstance(bloco, dict):
                continue
            for campo in bloco.get("campos", []) or []:
                if campo.get("obrigatorio") and not campo.get("campo_cliente"):
                    obrig_sem_fonte.append(f"{entidade}.{campo.get('campo_template')}")

        return {
            "status": "ok",
            "dados": {
                "arquivo": str(caminho.relative_to(base)),
                "total_entidades": total,
                "entidades_com_fonte": com_fonte,
                "obrigatorios_sem_correspondencia": obrig_sem_fonte,
            },
        }

    # ── Registro ─────────────────────────────────────────────────────────────

    registro = RegistroTools()
    registro.registrar(Tool(
        nome="obter_diagnostico_resumido",
        descricao=(
            "Devolve a estrutura do cliente lida de config/diagnostico.json, no formato "
            "{arquivo: {aba: {total_linhas, colunas}}}. Use no início para saber quais "
            "arquivos e abas existem."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=t_diagnostico,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="listar_entidades_template",
        descricao=(
            "Lista as 7 entidades canônicas e os campos exatos de cada template. Para cada campo "
            "retorna nome (com asterisco/espaços originais), obrigatoriedade e transformação sugerida."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=t_entidades,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="obter_amostras_aba",
        descricao=(
            "Lê as primeiras N linhas reais de uma aba específica para inspeção. Use quando o "
            "nome da coluna não basta para decidir o mapeamento, ou quando precisa confirmar "
            "se o cabeçalho está na linha 1 ou 2 (header_linha)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "arquivo_relativo": {
                    "type": "string",
                    "description": "Caminho relativo a clientes/<cliente>/, ex: raw/simples/dados.xlsx",
                },
                "aba": {
                    "type": "string",
                    "description": "Nome da aba como aparece no diagnóstico. Para CSV, qualquer string serve.",
                },
                "n": {
                    "type": "integer",
                    "description": "Quantidade de linhas a retornar (1–20). Default 5.",
                    "minimum": 1,
                    "maximum": 20,
                },
            },
            "required": ["arquivo_relativo", "aba"],
        },
        funcao=t_amostras,
    ))
    registro.registrar(Tool(
        nome="sugerir_correspondencia",
        descricao=(
            "Aplica a heurística determinista (sinônimos + similaridade de string) para sugerir "
            "a melhor coluna do cliente para um campo do template. Devolve a candidata, score e "
            "nível de confiança. Use como segunda opinião — você decide se aceita ou rejeita."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "campo_template": {
                    "type": "string",
                    "description": "Nome exato do campo do template, com asterisco e espaços.",
                },
                "colunas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de nomes de coluna disponíveis na aba do cliente.",
                },
            },
            "required": ["campo_template", "colunas"],
        },
        funcao=t_sugerir,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="gravar_mapeamento",
        descricao=(
            "Escreve config/mapeamento.json com o mapeamento completo. Respeita 'travado: true' "
            "(não sobrescreve nesse caso). Devolve resumo com total de entidades, quantas têm "
            "fonte e a lista de campos obrigatórios sem correspondência. Chame UMA vez no final."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "mapeamento": {
                    "type": "object",
                    "description": (
                        "Objeto com uma chave por entidade. Cada valor tem arquivo_sugerido, "
                        "aba_sugerida, header_linha (int) e campos (lista). Cada campo tem "
                        "campo_template, obrigatorio, campo_cliente, confianca, transformacao, observacao."
                    ),
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "arquivo_sugerido": {"type": ["string", "null"]},
                            "aba_sugerida": {"type": ["string", "null"]},
                            "header_linha": {"type": "integer"},
                            "campos": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "campo_template": {"type": "string"},
                                        "obrigatorio": {"type": "boolean"},
                                        "campo_cliente": {"type": ["string", "null"]},
                                        "confianca": {
                                            "type": "string",
                                            "enum": ["alta", "media", "baixa", "nenhuma"],
                                        },
                                        "transformacao": {"type": "string"},
                                        "observacao": {"type": "string"},
                                    },
                                    "required": [
                                        "campo_template", "obrigatorio", "campo_cliente",
                                        "confianca", "transformacao",
                                    ],
                                },
                            },
                        },
                        "required": ["arquivo_sugerido", "aba_sugerida", "header_linha", "campos"],
                    },
                },
            },
            "required": ["mapeamento"],
        },
        funcao=t_gravar,
    ))
    registro.registrar(construir_tool_hitl())
    return registro


def executar(pasta_cliente: str):
    registro = construir_registro(pasta_cliente)
    return executar_agente(
        cliente_path=Path(pasta_cliente),
        agente="mapeamento_llm",
        prompt_sistema=PROMPT_SISTEMA,
        tarefa=PROMPT_TAREFA,
        registro=registro,
    )
