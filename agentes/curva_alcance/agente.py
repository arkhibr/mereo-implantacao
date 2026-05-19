"""
Agente de Curva de Alcance
Transforma as faixas de atingimento das metas para o template da plataforma.
"""
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.codificacao import aplicar_dicionario

TODOS_CAMPOS = [
    "Código da Meta*", " Tipo de Valor*",
    "Percentual/Valor 1º Nota", " Percentual/Valor 2º Nota", " Percentual/Valor Nota n",
]
STAGING_DIR = "staging/07_curva_alcance"


def executar(pasta_cliente: str) -> dict:
    resultado = {"status": "ok", "agente": "curva_alcance", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"
    staging = base / STAGING_DIR
    staging.mkdir(parents=True, exist_ok=True)

    mapeamento = _carregar_mapeamento(config)
    if mapeamento is None:
        resultado["status"] = "erro"
        resultado["erros"].append("mapeamento.json não encontrado.")
        return resultado

    conf = mapeamento.get("curva_alcance", {})
    arquivo = conf.get("arquivo_sugerido")
    if not arquivo:
        resultado["avisos"].append("Dados de curva_alcance não mapeados — ignorado.")
        return resultado

    df_raw = _ler_dados(base / arquivo, conf.get("aba_sugerida"), conf.get("header_linha", 0))
    if df_raw is None:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Não foi possível ler: {arquivo}")
        return resultado

    df = _aplicar_mapeamento(df_raw, conf.get("campos", []))

    # Recodificar código da meta usando dicionários consolidados
    dic_metas = _consolidar_dicionario_metas(config)
    if dic_metas and "Código da Meta*" in df.columns:
        res = aplicar_dicionario.aplicar(df, dic_metas, ["Código da Meta*"], ausentes="manter")
        df = res["dados"]["dataframe"]

    # Garantir colunas na ordem do template
    for col in TODOS_CAMPOS:
        if col not in df.columns:
            df[col] = ""
    df = df[TODOS_CAMPOS]

    # Remover linhas sem código de meta
    df = df[df["Código da Meta*"].notna() & (df["Código da Meta*"].astype(str).str.strip() != "")]

    caminho_out = staging / "curva_alcance_transformada.csv"
    df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8-sig")

    resultado["dados"]["linhas_transformadas"] = len(df)
    resultado["dados"]["arquivos_gerados"] = [str(caminho_out)]
    return resultado


def _consolidar_dicionario_metas(config: Path) -> dict:
    consolidado = {}
    for tipo in ["individual", "compartilhada", "projeto"]:
        caminho = config / f"dicionario_metas_{tipo}.csv"
        if caminho.exists():
            import csv
            with open(caminho, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    consolidado[row["id_origem"]] = row["id_destino"]
    return consolidado


def _carregar_mapeamento(config: Path) -> dict:
    caminho = config / "mapeamento.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _ler_dados(caminho: Path, aba: str, header_linha: int = 0) -> pd.DataFrame:
    try:
        if not caminho.exists():
            return None
        if caminho.suffix.lower() == ".csv":
            return pd.read_csv(str(caminho), sep=None, engine="python", encoding_errors="replace")
        return pd.read_excel(str(caminho), sheet_name=aba, header=header_linha, engine="openpyxl")
    except Exception:
        return None


def _aplicar_mapeamento(df: pd.DataFrame, campos: list) -> pd.DataFrame:
    renomear = {}
    for c in campos:
        cliente = c.get("campo_cliente")
        if not cliente:
            continue
        # Suporta chaves numéricas (colunas Excel com números como header)
        for col in df.columns:
            if str(col) == str(cliente) or col == cliente:
                renomear[col] = c["campo_template"]
                break
    return df.rename(columns=renomear)
