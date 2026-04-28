"""
Skill: Normalização de domínio
Padroniza valores de uma coluna para um conjunto canônico de valores.
"""
import pandas as pd


def normalizar(df: pd.DataFrame, coluna: str, equivalencias: dict, padrao: str = None) -> dict:
    """
    Substitui variações de valores pelo valor canônico.

    equivalencias: {"valor_canonico": ["variacao1", "variacao2", ...], ...}
    padrao: valor a usar quando nenhuma equivalência for encontrada (None = manter original)
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    if coluna not in df.columns:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Coluna '{coluna}' não encontrada.")
        return resultado

    mapa_invertido = {}
    for canonico, variacoes in equivalencias.items():
        for v in variacoes:
            mapa_invertido[str(v).strip().upper()] = canonico
        mapa_invertido[str(canonico).strip().upper()] = canonico

    df_out = df.copy()
    nao_reconhecidos = []

    def _mapear(val):
        if pd.isna(val):
            return val
        chave = str(val).strip().upper()
        if chave in mapa_invertido:
            return mapa_invertido[chave]
        nao_reconhecidos.append(str(val))
        return padrao if padrao is not None else val

    df_out[coluna] = df_out[coluna].apply(_mapear)

    resultado["dados"]["dataframe"] = df_out
    resultado["dados"]["nao_reconhecidos"] = list(set(nao_reconhecidos))

    if nao_reconhecidos:
        resultado["status"] = "aviso"
        resultado["avisos"].append(
            f"{len(set(nao_reconhecidos))} valor(es) não reconhecido(s) em '{coluna}'."
        )

    return resultado
