"""
Skill: Aplicação de dicionário de recodificação
Substitui IDs de origem por IDs de destino em um DataFrame.
"""
import pandas as pd


def aplicar(df: pd.DataFrame, mapa: dict, colunas: list, ausentes: str = "manter") -> dict:
    """
    Aplica o dicionário de recodificação nas colunas indicadas.

    ausentes: o que fazer com valores sem mapeamento
        "manter"  — mantém o valor original
        "vazio"   — substitui por vazio
        "erro"    — registra como erro e não altera
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    if isinstance(colunas, str):
        colunas = [colunas]

    df_out = df.copy()
    nao_mapeados = {}

    for col in colunas:
        if col not in df_out.columns:
            resultado["avisos"].append(f"Coluna '{col}' não encontrada — ignorada.")
            continue

        sem_mapa = []
        def _traduzir(val):
            chave = str(val).strip() if pd.notna(val) else ""
            if chave in mapa:
                return mapa[chave]
            sem_mapa.append(chave)
            if ausentes == "vazio":
                return ""
            return val

        df_out[col] = df_out[col].apply(_traduzir)

        if sem_mapa:
            nao_mapeados[col] = list(set(sem_mapa))
            resultado["avisos"].append(
                f"'{col}': {len(set(sem_mapa))} valor(es) sem mapeamento → ação: '{ausentes}'."
            )

    resultado["dados"]["dataframe"] = df_out
    resultado["dados"]["nao_mapeados"] = nao_mapeados

    if nao_mapeados and ausentes == "erro":
        resultado["status"] = "erro"
        resultado["erros"].append("Valores sem mapeamento encontrados. Completar o dicionário.")

    return resultado
