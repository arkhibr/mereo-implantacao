"""
Agente de Validação — versão LLM.

Lê o SOP-prompt em `sops/agentes/sop_validacao.md`, expõe ferramentas
determinísticas para validar schema, unicidade e integridade referencial,
e produz `relatorios/relatorio_validacao.md` mais (quando aprovado) os
arquivos finais em `output/<data>/`.

A política dos três estados (aprovado, aprovado_com_ressalvas, bloqueado)
é decisão do agente — as tools só fornecem fatos. A cópia para output é
uma tool separada que só deve ser chamada quando o agente decide commitar.
"""
import json
import shutil
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentes.validacao.agente import (
    STAGING_PARA_TEMPLATE,
    REFERENCIAS,
    CHAVES_UNICAS,
    _validar_periodicidade,
)
from ferramentas.exportacao import validar_schema, validar_referencias, validar_codigos, exportar_output
from ferramentas.transformacao.dominios_plataforma import REGRAS_CODIGOS
from ferramentas.qualidade import duplicatas
from nucleo.hitl import construir_tool_hitl
from nucleo.registro_tools import RegistroTools, Tool
from nucleo.runner import executar_agente


BASE_PROJETO = Path(__file__).parent.parent.parent
TEMPLATES_DIR = BASE_PROJETO / "templates"

STATUS_VALIDOS = {"aprovado", "aprovado_com_ressalvas", "bloqueado"}

PROMPT_SISTEMA = (
    (BASE_PROJETO / "prompts/sistema/base_agente.md").read_text(encoding="utf-8")
    + "\n\n---\n\n"
    + (BASE_PROJETO / "sops/agentes/sop_validacao.md").read_text(encoding="utf-8")
)

PROMPT_TAREFA = (
    "Valide os arquivos em staging/ e decida se podem virar output/. "
    "Siga o procedimento descrito no SOP. Ao final, garanta que "
    "relatorios/relatorio_validacao.md foi gerado e — se o status permitir "
    "e o consultor autorizar quando exigido — que output/<data>/ foi populado."
)


def construir_registro(pasta_cliente: str, sessao=None) -> RegistroTools:
    base = Path(pasta_cliente)
    relatorios = base / "relatorios"
    relatorios.mkdir(exist_ok=True)

    # Cache de DataFrames lidos para evitar relê-los entre tools.
    cache_df: dict[str, pd.DataFrame] = {}

    def _carregar(entidade: str) -> pd.DataFrame | None:
        if entidade in cache_df:
            return cache_df[entidade]
        for staging_rel, (_nome_template, chave) in STAGING_PARA_TEMPLATE.items():
            if chave != entidade:
                continue
            caminho = base / staging_rel
            if not caminho.exists():
                return None
            df = pd.read_csv(str(caminho), sep=";", encoding="utf-8-sig", dtype=str)
            cache_df[entidade] = df
            return df
        return None

    # ── Tools ────────────────────────────────────────────────────────────────

    def t_listar() -> dict:
        presentes = []
        ausentes = []
        for staging_rel, (nome_template, chave) in STAGING_PARA_TEMPLATE.items():
            caminho = base / staging_rel
            if caminho.exists():
                df = _carregar(chave)
                presentes.append({
                    "entidade": chave,
                    "arquivo_staging": staging_rel,
                    "arquivo_template": nome_template,
                    "linhas": int(len(df)) if df is not None else 0,
                })
            else:
                ausentes.append({"entidade": chave, "arquivo_staging": staging_rel})
        return {
            "status": "ok",
            "dados": {"presentes": presentes, "ausentes": ausentes},
        }

    def t_validar_schema(entidade: str) -> dict:
        df = _carregar(entidade)
        if df is None:
            return {"status": "erro", "erros": [f"Staging de '{entidade}' não encontrado."]}

        nome_template = next(
            (n for _, (n, c) in STAGING_PARA_TEMPLATE.items() if c == entidade), None
        )
        if not nome_template:
            return {"status": "erro", "erros": [f"Entidade desconhecida: {entidade}"]}

        achados = []
        from nucleo import templates as _tpl
        caminho_tmpl = _tpl.localizar(TEMPLATES_DIR, nome_template)
        if caminho_tmpl:
            schema = validar_schema.schema_do_template(str(caminho_tmpl))
            res_schema = validar_schema.validar(df, schema)
            achados.extend(res_schema["dados"]["achados"])

        regras = REGRAS_CODIGOS.get(entidade)
        if regras:
            res_cod = validar_codigos.validar(df, regras)
            achados.extend(res_cod["dados"]["achados"])

        chave = CHAVES_UNICAS.get(entidade)
        if chave and chave in df.columns:
            res_dup = duplicatas.detectar(df, [chave])
            total = res_dup["dados"]["total_registros_afetados"]
            if total:
                achados.append({
                    "severidade": "critico",
                    "tipo": "duplicata",
                    "coluna": chave,
                    "detalhe": f"{total} registros duplicados em {res_dup['dados']['total_grupos']} grupo(s)",
                    "grupos": res_dup["dados"]["grupos"][:10],
                })

        sev_set = {a["severidade"] for a in achados}
        status_ent = "ok"
        if "critico" in sev_set or "alto" in sev_set:
            status_ent = "bloqueado"
        elif sev_set:
            status_ent = "aviso"

        return {
            "status": "ok",
            "dados": {
                "entidade": entidade,
                "linhas": int(len(df)),
                "status_entidade": status_ent,
                "total_achados": len(achados),
                "achados": achados,
            },
        }

    def t_validar_referencias() -> dict:
        tabelas = {}
        for staging_rel, (_nome_template, chave) in STAGING_PARA_TEMPLATE.items():
            df = _carregar(chave)
            if df is not None:
                tabelas[chave] = df

        refs_aplicaveis = [
            r for r in REFERENCIAS
            if r["tabela_origem"] in tabelas and r["tabela_destino"] in tabelas
        ]
        if not refs_aplicaveis:
            return {
                "status": "ok",
                "dados": {
                    "tabelas_consideradas": list(tabelas.keys()),
                    "referencias_verificadas": 0,
                    "achados": [],
                },
            }

        res = validar_referencias.validar(tabelas, refs_aplicaveis)
        achados = res["dados"]["achados"] + _validar_periodicidade(base, tabelas)
        return {
            "status": "ok",
            "dados": {
                "tabelas_consideradas": list(tabelas.keys()),
                "referencias_verificadas": res["dados"]["total_referencias_verificadas"],
                "total_achados": len(achados),
                "achados": achados,
            },
        }

    def t_amostras_invalidas(entidade: str, coluna: str, valores: list = None, n: int = 5) -> dict:
        df = _carregar(entidade)
        if df is None:
            return {"status": "erro", "erros": [f"Staging de '{entidade}' não encontrado."]}
        if coluna not in df.columns:
            return {"status": "erro", "erros": [f"Coluna '{coluna}' não existe em {entidade}."]}

        n = max(1, min(int(n or 5), 50))
        if valores:
            mascara = df[coluna].astype(str).str.strip().isin([str(v).strip() for v in valores])
            sub = df[mascara].head(n)
        else:
            mascara = df[coluna].isna() | (df[coluna].astype(str).str.strip() == "")
            sub = df[mascara].head(n)

        linhas = json.loads(sub.to_json(orient="records", force_ascii=False, default_handler=str))
        return {
            "status": "ok",
            "dados": {
                "entidade": entidade,
                "coluna": coluna,
                "linhas": linhas,
                "total_linhas_afetadas_no_staging": int(mascara.sum()),
            },
        }

    def t_gravar_relatorio(
        status_geral: str,
        resumo: list,
        narrativa: str,
        achados: list = None,
    ) -> dict:
        if status_geral not in STATUS_VALIDOS:
            return {
                "status": "erro",
                "erros": [f"status_geral inválido: '{status_geral}'. Use {sorted(STATUS_VALIDOS)}."],
            }
        if achados is None:
            achados = []
        if not isinstance(resumo, list) or not isinstance(achados, list):
            return {"status": "erro", "erros": ["resumo e achados devem ser listas."]}
        if not isinstance(narrativa, str) or not narrativa.strip():
            return {"status": "erro", "erros": ["narrativa deve ser uma string não-vazia."]}

        caminho = relatorios / "relatorio_validacao.md"
        caminho.write_text(
            _renderizar_relatorio(status_geral, resumo, achados, narrativa),
            encoding="utf-8",
        )

        return {
            "status": "ok",
            "dados": {
                "arquivo": str(caminho.relative_to(base)),
                "status_geral": status_geral,
                "total_entidades": len(resumo),
                "total_achados": len(achados),
            },
        }

    def t_copiar_output(data: str = None) -> dict:
        arquivos = {rel: nome for rel, (nome, _chave) in STAGING_PARA_TEMPLATE.items()}
        res_exp = exportar_output.exportar(base, arquivos, data=data)

        return {
            "status": "ok",
            "dados": {
                "diretorio_output": str(Path(res_exp["dados"]["diretorio_output"]).relative_to(base)),
                "arquivos_copiados": res_exp["dados"]["arquivos_gerados"],
                "ausentes": res_exp["dados"]["ausentes"],
                "data": res_exp["dados"]["data"],
            },
        }

    # ── Registro ─────────────────────────────────────────────────────────────

    registro = RegistroTools()
    registro.registrar(Tool(
        nome="listar_staging",
        descricao=(
            "Lista as entidades presentes em staging/ (com contagem de linhas) e as ausentes. "
            "Use no início para saber o que vai validar."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=t_listar,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="validar_schema_entidade",
        descricao=(
            "Valida uma entidade contra o template correspondente: colunas presentes/ordem, "
            "obrigatórios vazios, tipos básicos, e duplicatas na chave única (areas, colaboradores, "
            "indicadores). Devolve achados com severidade (critico/alto/medio/baixo)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "entidade": {
                    "type": "string",
                    "description": "Nome canônico: areas, colaboradores, indicadores, metas_individuais, metas_compartilhadas, metas_projeto, curva_alcance.",
                },
            },
            "required": ["entidade"],
        },
        funcao=t_validar_schema,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="validar_referencias",
        descricao=(
            "Verifica integridade referencial entre as entidades presentes (colaboradores→areas, "
            "metas→areas, metas→colaboradores, metas→indicadores). Devolve achados com tabela_origem, "
            "coluna_fk, total_invalidas e exemplos de valores inválidos. Chame UMA vez após ter "
            "validado os schemas."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=t_validar_referencias,
    ))
    registro.registrar(Tool(
        nome="obter_amostras_invalidas",
        descricao=(
            "Retorna até N linhas reais do staging onde uma coluna apresenta valor problemático. "
            "Se 'valores' for fornecido, filtra linhas onde a coluna assume um desses valores "
            "(útil para investigar FKs órfãs específicas). Sem 'valores', retorna linhas onde a "
            "coluna está vazia. Use para investigar causa-raiz."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "entidade": {"type": "string"},
                "coluna": {"type": "string"},
                "valores": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Valores específicos a procurar nessa coluna. Default: linhas vazias.",
                },
                "n": {"type": "integer", "minimum": 1, "maximum": 50, "description": "Default 5."},
            },
            "required": ["entidade", "coluna"],
        },
        funcao=t_amostras_invalidas,
    ))
    registro.registrar(Tool(
        nome="gravar_relatorio",
        descricao=(
            "Escreve relatorios/relatorio_validacao.md. Recebe status_geral (aprovado | "
            "aprovado_com_ressalvas | bloqueado), resumo por entidade, lista completa de achados "
            "e uma narrativa em markdown PT-BR com sua análise (causas-raiz, severidade contextual, "
            "recomendações)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "status_geral": {
                    "type": "string",
                    "enum": ["aprovado", "aprovado_com_ressalvas", "bloqueado"],
                },
                "resumo": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "entidade": {"type": "string"},
                            "linhas": {"type": "integer"},
                            "achados": {"type": "integer"},
                            "status": {"type": "string"},
                        },
                        "required": ["entidade", "linhas", "achados", "status"],
                    },
                },
                "achados": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Lista completa de achados (preserve os campos originais das tools). Omita ou passe lista vazia quando não houver achados.",
                },
                "narrativa": {
                    "type": "string",
                    "description": "Análise em markdown PT-BR. Pode usar headers, listas, código.",
                },
            },
            "required": ["status_geral", "resumo", "narrativa"],
        },
        funcao=t_gravar_relatorio,
    ))
    registro.registrar(Tool(
        nome="copiar_para_output",
        descricao=(
            "Exporta os arquivos de staging/ como planilhas .xlsx em output/<data>/, nomeadas "
            "pelo template (formato que a plataforma importa). Chame APENAS quando o status for "
            "'aprovado' (direto) ou 'aprovado_com_ressalvas' "
            "(após autorização via perguntar_humano). Nunca chame em estado 'bloqueado'."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "data": {
                    "type": "string",
                    "description": "Data do output no formato YYYY-MM-DD. Default: hoje.",
                },
            },
        },
        funcao=t_copiar_output,
    ))
    registro.registrar(construir_tool_hitl())
    return registro


def executar(pasta_cliente: str):
    registro = construir_registro(pasta_cliente)
    return executar_agente(
        cliente_path=Path(pasta_cliente),
        agente="validacao_llm",
        prompt_sistema=PROMPT_SISTEMA,
        tarefa=PROMPT_TAREFA,
        registro=registro,
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def _renderizar_relatorio(status_geral: str, resumo: list, achados: list, narrativa: str) -> str:
    icone = {"aprovado": "✅", "aprovado_com_ressalvas": "⚠️", "bloqueado": "❌"}.get(status_geral, "?")
    linhas = [
        "# Relatório de Validação",
        "",
        f"**Status geral: {icone} {status_geral.upper()}**",
        "",
        "## Análise",
        "",
        narrativa.strip(),
        "",
        "## Resumo por entidade",
        "",
        "| Entidade | Linhas | Achados | Status |",
        "|---|---|---|---|",
    ]
    for r in resumo:
        st = r.get("status", "")
        ic = {"ok": "✅", "aviso": "⚠️", "bloqueado": "❌", "ausente": "—"}.get(st, "?")
        linhas.append(f"| {r.get('entidade','')} | {r.get('linhas',0)} | {r.get('achados',0)} | {ic} {st} |")

    if achados:
        linhas.extend(["", "## Achados detalhados", "",
                       "| Entidade | Severidade | Tipo | Coluna | Detalhe |",
                       "|---|---|---|---|---|"])
        for a in achados:
            entidade = a.get("entidade") or a.get("tabela_origem") or ""
            coluna = a.get("coluna") or a.get("coluna_fk") or ""
            detalhe = a.get("detalhe", "")
            if not detalhe and a.get("tipo") == "referencia_invalida":
                exemplos = a.get("valores_invalidos", [])[:3]
                detalhe = f"{a.get('total_invalidas','?')} ref. inválidas → {a.get('tabela_destino','')}.{a.get('coluna_pk','')} | ex: {exemplos}"
            linhas.append(
                f"| {entidade} | {a.get('severidade','')} | {a.get('tipo','')} | {coluna} | {detalhe} |"
            )

    return "\n".join(linhas) + "\n"
