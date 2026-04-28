"""
Skill: Reconstrução de hierarquia a partir de dados planos
Converte colunas de nível (nivel1/nivel2/nivel3) em registros pai-filho normalizados.
"""
import pandas as pd


def reconstruir(df: pd.DataFrame, colunas_nivel: list,
                prefixo_codigo: str = "N") -> dict:
    """
    Converte colunas de nível hierárquico em uma tabela pai-filho normalizada.

    colunas_nivel: lista ordenada do nível mais alto para o mais baixo
                   ex: ["diretoria", "gerencia", "area"]

    Retorna DataFrame com: codigo, descricao, codigo_pai, nivel
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    ausentes = [c for c in colunas_nivel if c not in df.columns]
    if ausentes:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Colunas não encontradas: {ausentes}")
        return resultado

    nos = {}

    for _, row in df.iterrows():
        pai_codigo = None
        for nivel_idx, col in enumerate(colunas_nivel):
            val = row[col]
            if pd.isna(val) or str(val).strip() == "":
                break
            descricao = str(val).strip()
            chave = (nivel_idx, descricao)

            if chave not in nos:
                codigo = f"{prefixo_codigo}{len(nos) + 1:04d}"
                nos[chave] = {
                    "codigo": codigo,
                    "descricao": descricao,
                    "codigo_pai": pai_codigo,
                    "nivel": nivel_idx + 1,
                }
            pai_codigo = nos[chave]["codigo"]

    df_saida = pd.DataFrame(list(nos.values()))

    resultado["dados"]["dataframe"] = df_saida
    resultado["dados"]["total_nos"] = len(df_saida)
    resultado["dados"]["niveis"] = len(colunas_nivel)

    return resultado
