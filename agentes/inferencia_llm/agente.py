"""
Agente de Inferência — versão LLM.

Lê o SOP-prompt em `sops/agentes/sop_inferencia.md` como instrução. No MVP,
fabrica registros de Indicadores (KPI) a partir das Metas Individuais quando
o cliente não enviou o template de indicadores explicitamente.

Saída:
  - clientes/<cliente>/inferencia/Indicadores_inferidos.csv
  - clientes/<cliente>/relatorios/relatorio_inferencia.md

Não escreve em raw/ — princípio da imutabilidade da pasta de origem.
Não altera mapeamento.json automaticamente — o consultor revisa o CSV e
aponta a fonte manualmente quando aprovar.
"""
import csv
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.inferencia.indicadores import (
    CandidatoIndicador,
    COLUNAS_AUXILIARES,
    COLUNAS_TEMPLATE,
    PLACEHOLDER,
    extrair_candidatos,
    inferir_polaridade,
    montar_linha,
    normalizar_descricao,
)
from nucleo.hitl import construir_tool_hitl
from nucleo.registro_tools import RegistroTools, Tool
from nucleo.runner import executar_agente


BASE_PROJETO = Path(__file__).parent.parent.parent

PROMPT_SISTEMA = (
    (BASE_PROJETO / "prompts/sistema/base_agente.md").read_text(encoding="utf-8")
    + "\n\n---\n\n"
    + (BASE_PROJETO / "sops/agentes/sop_inferencia.md").read_text(encoding="utf-8")
)

PROMPT_TAREFA = (
    "Inferir o catálogo de indicadores (KPIs) deste cliente a partir das metas "
    "individuais que ele enviou. Siga o procedimento descrito no SOP. Ao final, "
    "garanta que inferencia/Indicadores_inferidos.csv e "
    "relatorios/relatorio_inferencia.md foram gerados, ou que o motivo de não "
    "ter sido gerado está claro na sua resposta final."
)


def construir_registro(pasta_cliente: str, sessao=None) -> RegistroTools:
    base = Path(pasta_cliente)
    config = base / "config"
    inferencia = base / "inferencia"
    relatorios = base / "relatorios"
    inferencia.mkdir(parents=True, exist_ok=True)
    relatorios.mkdir(parents=True, exist_ok=True)

    # Buffer mantido entre chamadas para que o agente não precise reentregar
    # estruturas grandes no transcript. As tools de extração populam, a tool de
    # gravação consome.
    buffer: dict = {"fonte_metas": None, "candidatos": []}

    def _resolver(arquivo_rel: str) -> Path:
        f = (base / arquivo_rel).resolve()
        if not str(f).startswith(str(base.resolve())):
            raise ValueError("Caminho fora do diretório do cliente.")
        return f

    def _ler_metas(fonte: dict) -> pd.DataFrame:
        caminho = _resolver(fonte["arquivo"])
        if not caminho.exists():
            raise FileNotFoundError(f"Arquivo de metas não encontrado: {fonte['arquivo']}")
        if caminho.suffix.lower() == ".csv":
            return pd.read_csv(
                str(caminho), sep=None, engine="python", encoding_errors="replace",
                header=fonte.get("header_linha", 0),
            )
        return pd.read_excel(
            str(caminho), sheet_name=fonte["aba"],
            header=fonte.get("header_linha", 0), engine="openpyxl",
        )

    # ── Tools ────────────────────────────────────────────────────────────────

    def t_obter_fonte() -> dict:
        caminho = config / "mapeamento.json"
        if not caminho.exists():
            return {
                "status": "erro",
                "erros": [
                    "config/mapeamento.json não encontrado. Rode mapeamento primeiro "
                    "(./implantacao mapear <cliente>) ou crie o mapeamento manual."
                ],
            }
        try:
            mapeamento = json.loads(caminho.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            return {"status": "erro", "erros": [f"mapeamento.json inválido: {e}"]}

        bloco = mapeamento.get("metas_individuais")
        if not isinstance(bloco, dict) or not bloco.get("arquivo_sugerido"):
            return {
                "status": "erro",
                "erros": [
                    "metas_individuais sem fonte definida no mapeamento. "
                    "O agente de inferência precisa de pelo menos a fonte das metas "
                    "individuais para extrair indicadores."
                ],
            }

        # Localiza o nome de coluna do cliente para Código da Meta e Objetivo da Meta.
        campos_por_template = {
            c.get("campo_template"): c.get("campo_cliente")
            for c in (bloco.get("campos") or [])
            if isinstance(c, dict)
        }
        campo_codigo = campos_por_template.get("Código da Meta *")
        campo_descricao = (
            campos_por_template.get("Objetivo da Meta *")
            or campos_por_template.get("Descrição da Meta *")
            or campos_por_template.get("Nome da Meta *")
        )

        if not campo_codigo:
            return {
                "status": "erro",
                "erros": [
                    "metas_individuais não tem 'Código da Meta *' mapeado. "
                    "Sem o código da meta, não é possível agrupar indicadores."
                ],
            }

        fonte = {
            "arquivo": bloco["arquivo_sugerido"],
            "aba": bloco.get("aba_sugerida"),
            "header_linha": int(bloco.get("header_linha") or 0),
            "campo_codigo": campo_codigo,
            "campo_descricao": campo_descricao,
        }
        buffer["fonte_metas"] = fonte
        return {"status": "ok", "dados": fonte}

    def t_amostras_metas(n: int = 5) -> dict:
        if not buffer["fonte_metas"]:
            return {"status": "erro", "erros": ["Chame obter_fonte_metas antes."]}
        n = max(1, min(int(n or 5), 20))
        try:
            df = _ler_metas(buffer["fonte_metas"]).head(n)
        except Exception as e:
            return {"status": "erro", "erros": [f"Falha ao ler metas: {e}"]}

        amostras = json.loads(df.to_json(orient="records", force_ascii=False, default_handler=str))
        return {
            "status": "ok",
            "dados": {
                "colunas": [str(c) for c in df.columns],
                "linhas": amostras,
                "total_lidas": len(amostras),
            },
        }

    def t_extrair_candidatos() -> dict:
        if not buffer["fonte_metas"]:
            return {"status": "erro", "erros": ["Chame obter_fonte_metas antes."]}
        fonte = buffer["fonte_metas"]
        try:
            df = _ler_metas(fonte)
        except Exception as e:
            return {"status": "erro", "erros": [f"Falha ao ler metas: {e}"]}

        if not fonte["campo_descricao"]:
            return {
                "status": "erro",
                "erros": [
                    "metas_individuais não tem campo de descrição/nome mapeado "
                    "('Objetivo da Meta *' ou 'Nome da Meta *'). "
                    "Sem descrição, não dá pra inferir indicador legível."
                ],
            }

        if fonte["campo_codigo"] not in df.columns:
            return {
                "status": "erro",
                "erros": [
                    f"Coluna '{fonte['campo_codigo']}' (Código da Meta) não existe "
                    f"no arquivo. Colunas disponíveis: {list(df.columns)[:10]}"
                ],
            }

        registros = df.to_dict(orient="records")
        candidatos = extrair_candidatos(
            registros,
            campo_codigo=fonte["campo_codigo"],
            campo_descricao=fonte["campo_descricao"],
        )
        buffer["candidatos"] = candidatos

        # Resumo enxuto pro modelo (não devolve linhas completas — só o suficiente
        # pra ele revisar dedup e ajustar antes de gravar).
        resumo = []
        for c in candidatos:
            polaridade, conf_pol = inferir_polaridade(c.descricao_canonica)
            resumo.append({
                "codigo": c.codigo,
                "descricao_canonica": c.descricao_canonica,
                "polaridade_inferida": polaridade,
                "confianca_polaridade": conf_pol,
                "descricoes_observadas": c.descricoes_observadas,
                "ocorrencias": len(c.linhas_origem),
            })

        return {
            "status": "ok",
            "dados": {
                "total_candidatos": len(candidatos),
                "total_metas_lidas": len(registros),
                "candidatos": resumo,
            },
        }

    def t_gravar(indicadores: list) -> dict:
        if not buffer["fonte_metas"]:
            return {"status": "erro", "erros": ["Chame obter_fonte_metas antes."]}
        if not isinstance(indicadores, list) or not indicadores:
            return {"status": "erro", "erros": ["indicadores deve ser uma lista não-vazia"]}

        fonte = buffer["fonte_metas"]
        # Indexa candidatos extraídos pelo código pra recuperar audit (linhas_origem,
        # descricoes_observadas) caso o agente não tenha repassado.
        cand_por_codigo = {c.codigo: c for c in buffer["candidatos"]}

        linhas_csv = []
        for item in indicadores:
            if not isinstance(item, dict):
                return {"status": "erro", "erros": [f"item inválido (não-dict): {item!r}"]}
            codigo = str(item.get("codigo", "")).strip()
            descricao = str(item.get("descricao_canonica", "")).strip()
            if not codigo or not descricao:
                return {
                    "status": "erro",
                    "erros": [f"item sem 'codigo' ou 'descricao_canonica': {item!r}"],
                }

            ref = cand_por_codigo.get(codigo)
            descricoes_observadas = item.get("descricoes_observadas") or (
                ref.descricoes_observadas if ref else [descricao]
            )
            linhas_origem = item.get("linhas_origem") or (
                ref.linhas_origem if ref else []
            )

            candidato = CandidatoIndicador(
                codigo=codigo,
                descricao_canonica=descricao,
                descricoes_observadas=list(descricoes_observadas),
                linhas_origem=list(linhas_origem),
            )
            linha = montar_linha(
                candidato,
                fonte_arquivo=fonte["arquivo"],
                fonte_aba=fonte.get("aba") or "(csv)",
            )

            polaridade_override = item.get("polaridade_override")
            if polaridade_override:
                if polaridade_override not in ("Maior é Melhor", "Menor é Melhor"):
                    return {
                        "status": "erro",
                        "erros": [
                            f"polaridade_override inválida: {polaridade_override!r}. "
                            "Use 'Maior é Melhor' ou 'Menor é Melhor'."
                        ],
                    }
                linha["Polaridade *"] = polaridade_override
                obs = linha["_observacao"]
                ajuste = "polaridade ajustada pelo agente"
                linha["_observacao"] = f"{obs} | {ajuste}" if obs else ajuste

            obs_extra = (item.get("observacao") or "").strip()
            if obs_extra:
                linha["_observacao"] = (
                    f"{linha['_observacao']} | {obs_extra}" if linha["_observacao"] else obs_extra
                )

            linhas_csv.append(linha)

        # Grava CSV (UTF-8 com BOM, separador ';').
        cabecalho = COLUNAS_TEMPLATE + COLUNAS_AUXILIARES
        caminho_csv = inferencia / "Indicadores_inferidos.csv"
        with caminho_csv.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=cabecalho, delimiter=";")
            writer.writeheader()
            for linha in linhas_csv:
                writer.writerow({k: linha.get(k, "") for k in cabecalho})

        # Grava relatório markdown.
        caminho_md = relatorios / "relatorio_inferencia.md"
        caminho_md.write_text(_montar_relatorio(linhas_csv, fonte), encoding="utf-8")

        # Resumo pro agente.
        campos_pendentes = []
        for col in COLUNAS_TEMPLATE:
            if any(linha.get(col) == PLACEHOLDER for linha in linhas_csv):
                campos_pendentes.append(col)

        return {
            "status": "ok",
            "dados": {
                "arquivo_csv": str(caminho_csv.relative_to(base)),
                "arquivo_relatorio": str(caminho_md.relative_to(base)),
                "total_inferidos": len(linhas_csv),
                "campos_pendentes_definir": campos_pendentes,
                "distribuicao_confianca": _contar_confianca(linhas_csv),
            },
        }

    # ── Registro ─────────────────────────────────────────────────────────────

    registro = RegistroTools()
    registro.registrar(Tool(
        nome="obter_fonte_metas",
        descricao=(
            "Lê config/mapeamento.json e devolve a fonte das metas individuais "
            "(arquivo, aba, header_linha, campo_codigo, campo_descricao). Falha com "
            "mensagem orientada se o mapeamento não existir ou se metas_individuais "
            "não tiver fonte. Chame UMA vez no início."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=t_obter_fonte,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="obter_amostras_metas",
        descricao=(
            "Lê as primeiras N linhas das metas individuais (já com header_linha "
            "aplicado) para você inspecionar antes de extrair candidatos. Útil pra "
            "confirmar nome/conteúdo das colunas de código e descrição."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "n": {"type": "integer", "minimum": 1, "maximum": 20, "description": "Default 5."},
            },
        },
        funcao=t_amostras_metas,
    ))
    registro.registrar(Tool(
        nome="extrair_candidatos_indicadores",
        descricao=(
            "Aplica heurística determinista: agrupa metas por Código da Meta, normaliza "
            "descrições (remove sufixos temporais comuns), e devolve lista de candidatos "
            "a indicador com polaridade inferida. Você revisa, decide se quer agrupar "
            "ainda mais, ajustar descrição, e passa o resultado pra gravar_indicadores_inferidos."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=t_extrair_candidatos,
    ))
    registro.registrar(Tool(
        nome="gravar_indicadores_inferidos",
        descricao=(
            "Grava inferencia/Indicadores_inferidos.csv (formato do template + colunas "
            "auxiliares _origem, _confianca, _derivado_de, _observacao) e "
            "relatorios/relatorio_inferencia.md. Códigos de tabelas auxiliares "
            "(Unidade, Faixa de Farol, Frequência) saem como '<DEFINIR>' — não invente. "
            "Chame UMA vez no final."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "indicadores": {
                    "type": "array",
                    "description": "Lista final de indicadores a gravar.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "codigo": {"type": "string"},
                            "descricao_canonica": {"type": "string"},
                            "descricoes_observadas": {"type": "array", "items": {"type": "string"}},
                            "linhas_origem": {"type": "array", "items": {"type": "integer"}},
                            "polaridade_override": {
                                "type": "string",
                                "enum": ["Maior é Melhor", "Menor é Melhor"],
                                "description": (
                                    "Use APENAS quando a heurística errar e você tem evidência "
                                    "(ex: 'Inadimplência' não bate em palavra-chave mas é Menor)."
                                ),
                            },
                            "observacao": {"type": "string"},
                        },
                        "required": ["codigo", "descricao_canonica"],
                    },
                },
            },
            "required": ["indicadores"],
        },
        funcao=t_gravar,
    ))
    registro.registrar(construir_tool_hitl())
    return registro


def executar(pasta_cliente: str):
    registro = construir_registro(pasta_cliente)
    return executar_agente(
        cliente_path=Path(pasta_cliente),
        agente="inferencia_llm",
        prompt_sistema=PROMPT_SISTEMA,
        tarefa=PROMPT_TAREFA,
        registro=registro,
    )


# ── helpers ─────────────────────────────────────────────────────────────────

def _contar_confianca(linhas: list) -> dict:
    cont = {"alta": 0, "media": 0, "baixa": 0, "nenhuma": 0}
    for linha in linhas:
        c = linha.get("_confianca", "nenhuma")
        if c in cont:
            cont[c] += 1
    return cont


def _montar_relatorio(linhas: list, fonte: dict) -> str:
    distribuicao = _contar_confianca(linhas)
    campos_pendentes = sorted({
        col for linha in linhas for col in COLUNAS_TEMPLATE
        if linha.get(col) == PLACEHOLDER
    })

    md = ["# Relatório de Inferência — Indicadores\n"]
    md.append("## Origem\n")
    md.append(f"- Arquivo: `{fonte['arquivo']}`")
    md.append(f"- Aba: `{fonte.get('aba') or '(csv)'}`")
    md.append(f"- Linha de cabeçalho: {fonte.get('header_linha', 0)}")
    md.append(f"- Campo de código da meta: `{fonte['campo_codigo']}`")
    md.append(f"- Campo de descrição da meta: `{fonte.get('campo_descricao')}`\n")

    md.append("## Resultado\n")
    md.append(f"- Total de indicadores inferidos: **{len(linhas)}**")
    md.append("- Distribuição de confiança agregada:")
    for nivel in ("alta", "media", "baixa", "nenhuma"):
        md.append(f"  - {nivel}: {distribuicao[nivel]}")
    md.append("")

    if campos_pendentes:
        md.append("## ⚠️ Campos `<DEFINIR>` que o consultor precisa preencher\n")
        md.append(
            "Estes campos não são inferidos por princípio (dependem do cadastro da "
            "plataforma do cliente). Abra o CSV em `inferencia/Indicadores_inferidos.csv` "
            "e substitua `<DEFINIR>` pelos códigos válidos antes de aprovar:\n"
        )
        for col in campos_pendentes:
            md.append(f"- `{col}`")
        md.append("")

    md.append("## Indicadores inferidos\n")
    md.append("| Código | Descrição | Polaridade | Confiança | Observação |")
    md.append("|---|---|---|---|---|")
    for linha in linhas:
        # Escapa pipes nas células pra não quebrar a tabela markdown.
        descricao = str(linha["Descrição do Indicador *"]).replace("|", r"\|")
        observacao = str(linha["_observacao"] or "—").replace("|", r"\|")
        md.append(
            f"| `{linha['Código do Indicador *']}` "
            f"| {descricao} "
            f"| {linha['Polaridade *']} "
            f"| {linha['_confianca']} "
            f"| {observacao} |"
        )
    md.append("")

    md.append("## Próximo passo\n")
    md.append(
        "1. Revise `inferencia/Indicadores_inferidos.csv` — confira descrições, "
        "polaridade, agrupamentos.\n"
        "2. Substitua os `<DEFINIR>` pelos códigos cadastrados na plataforma do cliente.\n"
        "3. Edite `config/mapeamento.json` apontando "
        "`indicadores.arquivo_sugerido` para `inferencia/Indicadores_inferidos.csv` "
        "(e mapeie campo a campo: o nome do campo no cliente = o nome do campo no template).\n"
        "4. Rode `./implantacao transformar <cliente>` — a transformação determinista "
        "consome o CSV inferido como qualquer outra fonte.\n"
    )

    return "\n".join(md)
