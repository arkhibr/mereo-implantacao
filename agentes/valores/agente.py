"""
Agente de Valores
Transforma valores previstos e realizados das metas para os templates da plataforma.
"""
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.codificacao import aplicar_dicionario
from ferramentas.transformacao import converter_datas

STAGING_DIRS = {
    "previstos":  "staging/08_valores_previstos",
    "realizados": "staging/09_valores_realizados",
}


def executar(pasta_cliente: str) -> dict:
    resultado = {"status": "ok", "agente": "valores", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"

    mapeamento = _carregar_mapeamento(config)
    if mapeamento is None:
        resultado["status"] = "erro"
        resultado["erros"].append("mapeamento.json não encontrado.")
        return resultado

    dic_metas = _consolidar_dicionario_metas(config)
    arquivos_gerados = []
    contagens = {}

    for tipo, chave_mapa in [("previstos", "valores_previstos"), ("realizados", "valores_realizados")]:
        conf = mapeamento.get(chave_mapa, {})
        arquivo = conf.get("arquivo_sugerido")
        aba = conf.get("aba_sugerida")

        if not arquivo:
            resultado["avisos"].append(f"Dados de '{tipo}' não mapeados — ignorado.")
            continue

        df_raw = _ler_dados(base / arquivo, aba, conf.get("header_linha", 0))
        if df_raw is None:
            resultado["avisos"].append(f"Não foi possível ler dados de '{tipo}'.")
            continue

        df = _aplicar_mapeamento(df_raw, conf.get("campos", []))

        # Aplicar dicionário de metas na coluna de código de meta
        col_meta = _encontrar_coluna_meta(df)
        if col_meta and dic_metas:
            res = aplicar_dicionario.aplicar(df, dic_metas, [col_meta], ausentes="manter")
            df = res["dados"]["dataframe"]

        # Converter colunas de data (seriais Excel)
        for col in df.columns:
            amostra = df[col].dropna().head(5)
            if _parece_serial_excel(amostra):
                res = converter_datas.converter(df, col, "%d/%m/%Y")
                df = res["dados"]["dataframe"]
                if res["avisos"]:
                    resultado["avisos"].extend(res["avisos"])

        staging = base / STAGING_DIRS[tipo]
        staging.mkdir(parents=True, exist_ok=True)
        caminho_out = staging / f"valores_{tipo}_transformados.csv"
        df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8-sig")

        contagens[tipo] = len(df)
        arquivos_gerados.append(str(caminho_out))

    resultado["dados"]["contagens"] = contagens
    resultado["dados"]["arquivos_gerados"] = arquivos_gerados
    return resultado


def _parece_serial_excel(serie: pd.Series) -> bool:
    try:
        numericos = pd.to_numeric(serie, errors="coerce").dropna()
        return len(numericos) > 0 and numericos.between(30000, 50000).all()
    except Exception:
        return False


def _encontrar_coluna_meta(df: pd.DataFrame) -> str:
    for col in df.columns:
        if "meta" in str(col).lower() or "cod" in str(col).lower():
            return col
    return df.columns[0] if len(df.columns) > 0 else None


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
    renomear = {
        c["campo_cliente"]: c["campo_template"]
        for c in campos
        if c.get("campo_cliente") and c["campo_cliente"] in df.columns
    }
    return df.rename(columns=renomear)
