"""
Skill: Quebra e junção de campos
Separa um campo em múltiplos ou concatena múltiplos campos em um.
"""
import pandas as pd


def quebrar(df: pd.DataFrame, coluna: str, separador: str,
            nomes_saida: list, remover_original: bool = True) -> dict:
    """
    Divide coluna em múltiplas colunas pelo separador.
    nomes_saida define o nome de cada parte resultante.
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    if coluna not in df.columns:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Coluna '{coluna}' não encontrada.")
        return resultado

    df_out = df.copy()
    partes = df_out[coluna].astype(str).str.split(separador, expand=True)

    for i, nome in enumerate(nomes_saida):
        df_out[nome] = partes[i].str.strip() if i < partes.shape[1] else None

    if len(nomes_saida) < partes.shape[1]:
        resultado["avisos"].append(
            f"Coluna '{coluna}' gerou {partes.shape[1]} partes mas apenas "
            f"{len(nomes_saida)} nomes foram fornecidos. Partes excedentes ignoradas."
        )

    if remover_original:
        df_out = df_out.drop(columns=[coluna])

    resultado["dados"]["dataframe"] = df_out
    resultado["dados"]["colunas_criadas"] = nomes_saida

    return resultado


def juntar(df: pd.DataFrame, colunas: list, nome_saida: str,
           separador: str = " ", remover_originais: bool = False) -> dict:
    """
    Concatena múltiplas colunas em uma única coluna.
    Valores nulos são ignorados na concatenação.
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    ausentes = [c for c in colunas if c not in df.columns]
    if ausentes:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Colunas não encontradas: {ausentes}")
        return resultado

    df_out = df.copy()

    def _juntar_linha(row):
        partes = [str(row[c]).strip() for c in colunas if pd.notna(row[c]) and str(row[c]).strip()]
        return separador.join(partes)

    df_out[nome_saida] = df_out.apply(_juntar_linha, axis=1)

    if remover_originais:
        df_out = df_out.drop(columns=colunas)

    resultado["dados"]["dataframe"] = df_out
    resultado["dados"]["coluna_criada"] = nome_saida

    return resultado
