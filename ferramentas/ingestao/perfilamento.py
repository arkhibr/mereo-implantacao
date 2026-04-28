"""
Skill: Perfilamento de arquivo tabular
Retorna perfil estrutural de qualquer Excel ou CSV.
"""
from pathlib import Path
import pandas as pd


def perfil(caminho: str, abas: list = None) -> dict:
    """Retorna perfil estrutural de um arquivo tabular (Excel ou CSV)."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    try:
        path = Path(caminho)
        if not path.exists():
            resultado["status"] = "erro"
            resultado["erros"].append(f"Arquivo não encontrado: {caminho}")
            return resultado

        fmt = path.suffix.lower().lstrip(".")
        resultado["dados"]["arquivo"] = path.name
        resultado["dados"]["formato"] = fmt
        resultado["dados"]["tamanho_bytes"] = path.stat().st_size
        resultado["dados"]["abas"] = []

        if fmt in ("xlsx", "xls", "xlsm"):
            xf = pd.ExcelFile(caminho, engine="openpyxl")
            nomes = abas if abas else xf.sheet_names
            resultado["dados"]["total_abas"] = len(xf.sheet_names)
            for nome in nomes:
                try:
                    df = pd.read_excel(caminho, sheet_name=nome, header=0, engine="openpyxl")
                    resultado["dados"]["abas"].append(_perfil_df(df, nome))
                except Exception as e:
                    resultado["avisos"].append(f"Aba '{nome}' não pôde ser lida: {e}")

        elif fmt == "csv":
            df = pd.read_csv(caminho, sep=None, engine="python", encoding_errors="replace")
            resultado["dados"]["total_abas"] = 1
            resultado["dados"]["abas"].append(_perfil_df(df, path.name))

        else:
            resultado["status"] = "erro"
            resultado["erros"].append(f"Formato não suportado: {fmt}")

    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))

    return resultado


def _perfil_df(df: pd.DataFrame, nome: str) -> dict:
    total = len(df)
    colunas = []

    for col in df.columns:
        s = df[col]
        nulos = int(s.isna().sum())
        colunas.append({
            "nome": str(col),
            "tipo_inferido": _inferir_tipo(s),
            "nulos": nulos,
            "percentual_nulos": round(nulos / total * 100, 1) if total > 0 else 0.0,
            "unicos": int(s.nunique(dropna=True)),
            "amostra": s.dropna().head(5).astype(str).tolist(),
        })

    return {"nome": nome, "linhas": total, "total_colunas": len(df.columns), "colunas": colunas}


def _inferir_tipo(s: pd.Series) -> str:
    amostra = s.dropna()
    if len(amostra) == 0:
        return "vazio"
    if pd.api.types.is_bool_dtype(s):
        return "booleano"
    if pd.api.types.is_integer_dtype(s):
        return "inteiro"
    if pd.api.types.is_float_dtype(s):
        return "decimal"
    if pd.api.types.is_datetime64_any_dtype(s):
        return "data"
    try:
        pd.to_numeric(amostra)
        return "numerico"
    except (ValueError, TypeError):
        pass
    try:
        pd.to_datetime(amostra, infer_datetime_format=True)
        return "data_texto"
    except (ValueError, TypeError):
        pass
    return "texto"
