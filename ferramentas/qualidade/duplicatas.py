"""
Skill: Detecção de duplicatas
Identifica registros duplicados em uma ou mais colunas-chave.
"""
import pandas as pd


def detectar(df: pd.DataFrame, colunas_chave: list) -> dict:
    """Identifica registros duplicados dado uma ou mais colunas-chave."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    if isinstance(colunas_chave, str):
        colunas_chave = [colunas_chave]

    ausentes = [c for c in colunas_chave if c not in df.columns]
    if ausentes:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Colunas não encontradas: {ausentes}")
        return resultado

    mascara = df.duplicated(subset=colunas_chave, keep=False)
    duplicados = df[mascara].copy()
    duplicados["_linha"] = duplicados.index + 2

    grupos = (
        duplicados.groupby(colunas_chave)["_linha"]
        .apply(list)
        .reset_index()
        .rename(columns={"_linha": "linhas"})
        .to_dict(orient="records")
    )

    resultado["dados"]["colunas_chave"] = colunas_chave
    resultado["dados"]["total_registros_afetados"] = int(mascara.sum())
    resultado["dados"]["total_grupos"] = len(grupos)
    resultado["dados"]["grupos"] = grupos

    if grupos:
        resultado["status"] = "aviso"
        resultado["avisos"].append(
            f"{mascara.sum()} registros duplicados em {len(grupos)} grupo(s)."
        )

    return resultado
