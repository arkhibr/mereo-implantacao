"""
Agente de Diagnóstico
Analisa todos os arquivos em raw/ e produz config/diagnostico.json
e config/diagnostico_resumo.md.
"""
import json
from pathlib import Path
import pandas as pd
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.ingestao import perfilamento, encoding
from ferramentas.qualidade import erros_planilha, duplicatas, pii

EXTENSOES_SUPORTADAS = {".xlsx", ".xls", ".csv"}


def executar(pasta_cliente: str) -> dict:
    resultado = {"status": "ok", "agente": "diagnostico", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    raw = base / "raw"
    config = base / "config"

    if not raw.exists():
        resultado["status"] = "erro"
        resultado["erros"].append(f"Pasta raw/ não encontrada em: {pasta_cliente}")
        return resultado

    config.mkdir(parents=True, exist_ok=True)

    arquivos = [
        f for f in raw.rglob("*")
        if f.is_file() and f.suffix.lower() in EXTENSOES_SUPORTADAS
    ]

    if not arquivos:
        resultado["status"] = "erro"
        resultado["erros"].append("Nenhum arquivo suportado encontrado em raw/")
        return resultado

    relatorio = []

    for arquivo in sorted(arquivos):
        entrada = {
            "arquivo": str(arquivo.relative_to(base)),
            "caminho_absoluto": str(arquivo),
            "perfil": {},
            "encoding": {},
            "qualidade_por_aba": [],
            "erros_leitura": [],
        }

        res_perfil = perfilamento.perfil(str(arquivo))

        if res_perfil["status"] == "erro":
            entrada["erros_leitura"] = res_perfil["erros"]
            relatorio.append(entrada)
            resultado["avisos"].append(f"Não foi possível ler: {arquivo.name}")
            continue

        entrada["perfil"] = res_perfil["dados"]

        if arquivo.suffix.lower() == ".csv":
            res_enc = encoding.detectar(str(arquivo))
            entrada["encoding"] = res_enc["dados"]
            if res_enc["avisos"]:
                resultado["avisos"].extend(res_enc["avisos"])

        for aba_info in res_perfil["dados"].get("abas", []):
            aba_diag = {"aba": aba_info["nome"], "linhas": aba_info["linhas"]}
            try:
                df = _ler_aba(arquivo, aba_info["nome"])
                aba_diag["erros_formula"] = _erros_formula(df)
                aba_diag["linhas_vazias"] = _linhas_vazias(df)
                aba_diag["pii"] = pii.detectar(df)["dados"]["colunas_suspeitas"]
                aba_diag["duplicatas_primeira_coluna"] = _duplicatas_primeira_col(df)
            except Exception as e:
                aba_diag["erro"] = str(e)

            entrada["qualidade_por_aba"].append(aba_diag)

        relatorio.append(entrada)

    resultado["dados"]["total_arquivos"] = len(arquivos)
    resultado["dados"]["relatorio"] = relatorio

    caminho_json = config / "diagnostico.json"
    with open(caminho_json, "w", encoding="utf-8") as f:
        json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)

    caminho_md = config / "diagnostico_resumo.md"
    _salvar_resumo_md(relatorio, caminho_md)

    resultado["dados"]["arquivos_gerados"] = [str(caminho_json), str(caminho_md)]

    tem_erro = any(e["erros_leitura"] for e in relatorio)
    if tem_erro:
        resultado["status"] = "aviso"

    return resultado


# ── helpers privados ──────────────────────────────────────────────────────────

def _ler_aba(arquivo: Path, nome_aba: str) -> pd.DataFrame:
    if arquivo.suffix.lower() == ".csv":
        return pd.read_csv(str(arquivo), sep=None, engine="python", encoding_errors="replace")
    return pd.read_excel(str(arquivo), sheet_name=nome_aba, engine="openpyxl")


def _erros_formula(df: pd.DataFrame) -> list:
    res = erros_planilha.diagnosticar(df)
    return [a for a in res["dados"]["achados"] if a["tipo"] == "erro_formula"]


def _linhas_vazias(df: pd.DataFrame) -> int:
    return int(df.isna().all(axis=1).sum())


def _duplicatas_primeira_col(df: pd.DataFrame) -> dict:
    if df.empty or len(df.columns) == 0:
        return {}
    col = df.columns[0]
    res = duplicatas.detectar(df, [col])
    return {"coluna": str(col), "total_duplicados": res["dados"].get("total_registros_afetados", 0)}


def _salvar_resumo_md(relatorio: list, caminho: Path):
    linhas = ["# Diagnóstico — Resumo\n"]
    for entrada in relatorio:
        linhas.append(f"## {entrada['arquivo']}\n")
        perfil = entrada.get("perfil", {})
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

        if entrada.get("erros_leitura"):
            linhas.append(f"- ❌ Erro de leitura: {entrada['erros_leitura']}\n")

        linhas.append("")

    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
