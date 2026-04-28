"""
Agente de Diagnóstico — versão LLM.

Lê o SOP-prompt em `sops/agentes/sop_diagnostico.md` como instrução, expõe
as ferramentas de ingestão e qualidade como tools e produz os mesmos
artefatos do agente determinista (`config/diagnostico.json` e
`config/diagnostico_resumo.md`).

Usa um buffer local capturado por closure: cada chamada de `perfilar_*`
ou `analisar_qualidade_aba` acumula resultados, e `consolidar_diagnostico`
grava os dois arquivos finais a partir do buffer. Isso evita que o LLM
precise reentregar dados via conversa.
"""
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.ingestao import perfilamento, encoding
from ferramentas.qualidade import erros_planilha, duplicatas, pii
from nucleo.hitl import construir_tool_hitl
from nucleo.registro_tools import RegistroTools, Tool
from nucleo.runner import executar_agente


EXTENSOES_SUPORTADAS = {".xlsx", ".xls", ".csv"}

PROMPT_SISTEMA = (
    (Path(__file__).parent.parent.parent / "prompts/sistema/base_agente.md").read_text(encoding="utf-8")
    + "\n\n---\n\n"
    + (Path(__file__).parent.parent.parent / "sops/agentes/sop_diagnostico.md").read_text(encoding="utf-8")
)

PROMPT_TAREFA = (
    "Execute o diagnóstico completo dos arquivos em raw/ deste cliente. "
    "Siga o procedimento descrito no SOP. Ao final, garanta que "
    "config/diagnostico.json e config/diagnostico_resumo.md foram gerados."
)


def construir_registro(pasta_cliente: str) -> RegistroTools:
    base = Path(pasta_cliente)
    raw = base / "raw"
    config = base / "config"
    config.mkdir(parents=True, exist_ok=True)

    # Buffer indexado por arquivo relativo a `base`.
    buffer: dict[str, dict] = {}

    def _entrada(arquivo_rel: str) -> dict:
        if arquivo_rel not in buffer:
            buffer[arquivo_rel] = {
                "arquivo": arquivo_rel,
                "caminho_absoluto": str(base / arquivo_rel),
                "perfil": {},
                "encoding": {},
                "qualidade_por_aba": [],
                "erros_leitura": [],
            }
        return buffer[arquivo_rel]

    def _resolver(arquivo_rel: str) -> Path:
        f = (base / arquivo_rel).resolve()
        if not str(f).startswith(str(base.resolve())):
            raise ValueError("Caminho fora do diretório do cliente.")
        return f

    # ── Tools ────────────────────────────────────────────────────────────────

    def t_listar() -> dict:
        if not raw.exists():
            return {"status": "erro", "erros": [f"Pasta raw/ não encontrada em: {pasta_cliente}"]}
        arquivos = []
        for f in sorted(raw.rglob("*")):
            if f.is_file() and f.suffix.lower() in EXTENSOES_SUPORTADAS:
                arquivos.append({
                    "arquivo": str(f.relative_to(base)),
                    "extensao": f.suffix.lower(),
                    "tamanho_kb": round(f.stat().st_size / 1024, 1),
                })
        return {"status": "ok", "dados": {"total": len(arquivos), "arquivos": arquivos}}

    def t_perfilar(arquivo_relativo: str) -> dict:
        try:
            f = _resolver(arquivo_relativo)
        except ValueError as e:
            return {"status": "erro", "erros": [str(e)]}
        if not f.exists():
            return {"status": "erro", "erros": [f"Arquivo não encontrado: {arquivo_relativo}"]}

        res = perfilamento.perfil(str(f))
        entrada = _entrada(arquivo_relativo)
        if res["status"] == "ok":
            entrada["perfil"] = res["dados"]
        else:
            entrada["erros_leitura"] = res.get("erros", [])
        return res

    def t_encoding(arquivo_relativo: str) -> dict:
        try:
            f = _resolver(arquivo_relativo)
        except ValueError as e:
            return {"status": "erro", "erros": [str(e)]}
        if f.suffix.lower() != ".csv":
            return {"status": "aviso", "avisos": ["detectar_encoding só se aplica a .csv"]}
        res = encoding.detectar(str(f))
        entrada = _entrada(arquivo_relativo)
        if res["status"] == "ok":
            entrada["encoding"] = res["dados"]
        return res

    def t_qualidade(arquivo_relativo: str, aba: str) -> dict:
        try:
            f = _resolver(arquivo_relativo)
        except ValueError as e:
            return {"status": "erro", "erros": [str(e)]}
        try:
            df = _ler_aba(f, aba)
        except Exception as e:
            return {"status": "erro", "erros": [f"Falha ao ler aba '{aba}': {e}"]}

        achados_planilha = erros_planilha.diagnosticar(df)["dados"]["achados"]
        erros_formula = [a for a in achados_planilha if a["tipo"] == "erro_formula"]
        linhas_vazias = int(df.isna().all(axis=1).sum())
        pii_cols = pii.detectar(df)["dados"]["colunas_suspeitas"]

        dup = {}
        if not df.empty and len(df.columns) > 0:
            col = str(df.columns[0])
            res_d = duplicatas.detectar(df, [df.columns[0]])
            dup = {"coluna": col, "total_duplicados": res_d["dados"].get("total_registros_afetados", 0)}

        diag = {
            "aba": aba,
            "linhas": len(df),
            "erros_formula": erros_formula,
            "linhas_vazias": linhas_vazias,
            "pii": pii_cols,
            "duplicatas_primeira_coluna": dup,
        }

        entrada = _entrada(arquivo_relativo)
        # Substitui se já existir entrada para essa aba.
        entrada["qualidade_por_aba"] = [
            q for q in entrada["qualidade_por_aba"] if q.get("aba") != aba
        ]
        entrada["qualidade_por_aba"].append(diag)

        return {"status": "ok", "dados": diag}

    def t_consolidar() -> dict:
        if not buffer:
            return {"status": "erro", "erros": ["Buffer vazio: chame perfilar_arquivo antes."]}

        relatorio = list(buffer.values())
        caminho_json = config / "diagnostico.json"
        caminho_json.write_text(
            json.dumps(relatorio, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        caminho_md = config / "diagnostico_resumo.md"
        caminho_md.write_text(_montar_resumo(relatorio), encoding="utf-8")

        return {
            "status": "ok",
            "dados": {
                "total_arquivos": len(relatorio),
                "arquivos_gerados": [
                    str(caminho_json.relative_to(base)),
                    str(caminho_md.relative_to(base)),
                ],
            },
        }

    # ── Registro ─────────────────────────────────────────────────────────────

    registro = RegistroTools()
    registro.registrar(Tool(
        nome="listar_arquivos_raw",
        descricao="Lista os arquivos suportados (.xlsx, .xls, .csv) em raw/ com extensão e tamanho. Use no início para descobrir o que diagnosticar.",
        input_schema={"type": "object", "properties": {}},
        funcao=t_listar,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="perfilar_arquivo",
        descricao="Perfilamento estrutural de um arquivo: abas, linhas, colunas, tipos inferidos, % de nulos, amostras. Resultado é acumulado no buffer interno do agente.",
        input_schema={
            "type": "object",
            "properties": {
                "arquivo_relativo": {
                    "type": "string",
                    "description": "Caminho relativo a clientes/<cliente>/, ex: raw/simples/dados.xlsx",
                },
            },
            "required": ["arquivo_relativo"],
        },
        funcao=t_perfilar,
    ))
    registro.registrar(Tool(
        nome="detectar_encoding",
        descricao="Detecta o encoding de um arquivo CSV (UTF-8, latin-1 etc.). Só faz sentido para .csv. Resultado acumulado no buffer.",
        input_schema={
            "type": "object",
            "properties": {
                "arquivo_relativo": {
                    "type": "string",
                    "description": "Caminho relativo do CSV.",
                },
            },
            "required": ["arquivo_relativo"],
        },
        funcao=t_encoding,
    ))
    registro.registrar(Tool(
        nome="analisar_qualidade_aba",
        descricao="Para uma aba específica, analisa erros de fórmula Excel, linhas vazias, duplicatas na primeira coluna e PII potencial. Resultado acumulado no buffer.",
        input_schema={
            "type": "object",
            "properties": {
                "arquivo_relativo": {"type": "string"},
                "aba": {
                    "type": "string",
                    "description": "Nome da aba como retornado por perfilar_arquivo. Para CSV, use o próprio nome do arquivo.",
                },
            },
            "required": ["arquivo_relativo", "aba"],
        },
        funcao=t_qualidade,
    ))
    registro.registrar(Tool(
        nome="consolidar_diagnostico",
        descricao="Grava config/diagnostico.json e config/diagnostico_resumo.md a partir de tudo que foi coletado no buffer. Chame APENAS no final, após perfilar e analisar todos os arquivos.",
        input_schema={"type": "object", "properties": {}},
        funcao=t_consolidar,
    ))
    registro.registrar(construir_tool_hitl())
    return registro


def executar(pasta_cliente: str):
    registro = construir_registro(pasta_cliente)
    return executar_agente(
        cliente_path=Path(pasta_cliente),
        agente="diagnostico_llm",
        prompt_sistema=PROMPT_SISTEMA,
        tarefa=PROMPT_TAREFA,
        registro=registro,
    )


# ── helpers ─────────────────────────────────────────────────────────────────

def _ler_aba(arquivo: Path, nome_aba: str) -> pd.DataFrame:
    if arquivo.suffix.lower() == ".csv":
        return pd.read_csv(str(arquivo), sep=None, engine="python", encoding_errors="replace")
    return pd.read_excel(str(arquivo), sheet_name=nome_aba, engine="openpyxl")


def _montar_resumo(relatorio: list) -> str:
    linhas = ["# Diagnóstico — Resumo\n"]
    for entrada in relatorio:
        linhas.append(f"## {entrada['arquivo']}\n")
        perfil = entrada.get("perfil", {})
        if perfil:
            linhas.append(f"- **Formato:** {perfil.get('formato', '?')}  ")
            linhas.append(f"- **Tamanho:** {perfil.get('tamanho_bytes', 0):,} bytes  ")
            linhas.append(f"- **Abas:** {perfil.get('total_abas', 1)}\n")

        for aba in entrada.get("qualidade_por_aba", []):
            linhas.append(f"### Aba: {aba['aba']} ({aba.get('linhas', '?')} linhas)\n")
            erros = aba.get("erros_formula", [])
            if erros:
                total = sum(e["quantidade"] for e in erros)
                linhas.append(f"- ⚠️ Erros de fórmula: **{total}** ocorrências\n")
            if aba.get("linhas_vazias", 0):
                linhas.append(f"- ⚠️ Linhas completamente vazias: **{aba['linhas_vazias']}**\n")
            pii_cols = aba.get("pii", [])
            if pii_cols:
                nomes = [c["coluna"] for c in pii_cols]
                linhas.append(f"- 🔒 PII potencial: `{'`, `'.join(nomes)}`\n")
            dup = aba.get("duplicatas_primeira_coluna") or {}
            if dup.get("total_duplicados", 0):
                linhas.append(f"- ⚠️ Duplicatas na coluna `{dup['coluna']}`: **{dup['total_duplicados']}** registros\n")

        if entrada.get("erros_leitura"):
            linhas.append(f"- ❌ Erro de leitura: {entrada['erros_leitura']}\n")

        linhas.append("")

    return "\n".join(linhas)
