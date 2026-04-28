"""
Skill: Conversão de datas
Converte seriais Excel e strings de data para o formato desejado.
"""
import pandas as pd
from datetime import datetime, timedelta


_EPOCH_EXCEL = datetime(1899, 12, 30)


def converter(df: pd.DataFrame, coluna: str, formato_saida: str = "%d/%m/%Y") -> dict:
    """
    Converte uma coluna de datas (serial Excel ou texto) para o formato especificado.
    Suporta: serial numérico Excel, strings ISO, strings BR (DD/MM/AAAA) e datetime.
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    if coluna not in df.columns:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Coluna '{coluna}' não encontrada.")
        return resultado

    df_out = df.copy()
    falhas = []

    def _converter_valor(val):
        if pd.isna(val):
            return val
        try:
            if isinstance(val, (int, float)):
                return (_EPOCH_EXCEL + timedelta(days=int(val))).strftime(formato_saida)
            if isinstance(val, datetime):
                return val.strftime(formato_saida)
            dt = pd.to_datetime(str(val), dayfirst=True, infer_datetime_format=True)
            return dt.strftime(formato_saida)
        except Exception:
            falhas.append(str(val))
            return val

    df_out[coluna] = df_out[coluna].apply(_converter_valor)

    resultado["dados"]["dataframe"] = df_out
    resultado["dados"]["formato_saida"] = formato_saida
    resultado["dados"]["falhas"] = list(set(falhas))

    if falhas:
        resultado["status"] = "aviso"
        resultado["avisos"].append(
            f"{len(set(falhas))} valor(es) não convertido(s) em '{coluna}'."
        )

    return resultado


def serial_para_data(serial: int) -> str:
    """Converte um único serial Excel para string de data (DD/MM/AAAA)."""
    return (_EPOCH_EXCEL + timedelta(days=int(serial))).strftime("%d/%m/%Y")
