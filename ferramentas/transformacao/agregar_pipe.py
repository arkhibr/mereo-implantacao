"""
Skill: Agregação de linhas em campo pipe-separado
Consolida múltiplas linhas do mesmo registro em um campo único separado por pipe.
"""
import pandas as pd


def agregar(df: pd.DataFrame, coluna_chave: str, coluna_valor: str,
            separador: str = "|", ordenar: bool = True) -> dict:
    """
    Agrupa o DataFrame por coluna_chave e concatena os valores de coluna_valor
    em um campo separado por pipe.

    Retorna um DataFrame com uma linha por chave.
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    for col in [coluna_chave, coluna_valor]:
        if col not in df.columns:
            resultado["status"] = "erro"
            resultado["erros"].append(f"Coluna '{col}' não encontrada.")
            return resultado

    df_valido = df[[coluna_chave, coluna_valor]].dropna(subset=[coluna_chave])

    def _juntar(series):
        valores = series.dropna().astype(str).str.strip()
        valores = valores[valores != ""]
        if ordenar:
            valores = sorted(valores.tolist())
        return separador.join(valores)

    agregado = (
        df_valido.groupby(coluna_chave)[coluna_valor]
        .apply(_juntar)
        .reset_index()
    )

    linhas_antes = len(df)
    linhas_depois = len(agregado)

    resultado["dados"]["dataframe"] = agregado
    resultado["dados"]["linhas_antes"] = linhas_antes
    resultado["dados"]["linhas_depois"] = linhas_depois
    resultado["dados"]["reducao"] = linhas_antes - linhas_depois

    return resultado


def agregar_multiplas(df: pd.DataFrame, coluna_chave: str, colunas_valor: list,
                      separador: str = "|") -> dict:
    """Agrega múltiplas colunas de valor para a mesma chave."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    ausentes = [c for c in [coluna_chave] + colunas_valor if c not in df.columns]
    if ausentes:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Colunas não encontradas: {ausentes}")
        return resultado

    agg_dict = {col: lambda s, sep=separador: sep.join(
        s.dropna().astype(str).str.strip().replace("", pd.NA).dropna().tolist()
    ) for col in colunas_valor}

    agregado = df.groupby(coluna_chave).agg(agg_dict).reset_index()
    resultado["dados"]["dataframe"] = agregado
    resultado["dados"]["linhas"] = len(agregado)

    return resultado
