"""
Skill: Validação de integridade referencial entre tabelas
Verifica que toda chave estrangeira aponta para um registro existente.
"""
import pandas as pd


def validar(tabelas: dict, referencias: list) -> dict:
    """
    Verifica integridade referencial entre múltiplas tabelas.

    tabelas: {"nome_tabela": DataFrame, ...}

    referencias: lista de dicts definindo cada relação FK → PK:
        [
            {
                "tabela_origem": "colaboradores",
                "coluna_fk": "Código da Área*",
                "tabela_destino": "areas",
                "coluna_pk": "Código da Área*",
                "obrigatorio": True,
            },
            ...
        ]
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}
    achados = []

    for ref in referencias:
        t_orig = ref["tabela_origem"]
        col_fk = ref["coluna_fk"]
        t_dest = ref["tabela_destino"]
        col_pk = ref["coluna_pk"]
        obrigatorio = ref.get("obrigatorio", True)

        if t_orig not in tabelas:
            resultado["erros"].append(f"Tabela origem '{t_orig}' não fornecida.")
            continue
        if t_dest not in tabelas:
            resultado["erros"].append(f"Tabela destino '{t_dest}' não fornecida.")
            continue

        df_orig = tabelas[t_orig]
        df_dest = tabelas[t_dest]

        if col_fk not in df_orig.columns:
            resultado["avisos"].append(f"'{t_orig}.{col_fk}' não encontrada — referência ignorada.")
            continue
        if col_pk not in df_dest.columns:
            resultado["avisos"].append(f"'{t_dest}.{col_pk}' não encontrada — referência ignorada.")
            continue

        chaves_destino = set(df_dest[col_pk].dropna().astype(str).str.strip())

        fks = df_orig[col_fk].dropna().astype(str).str.strip()

        if not obrigatorio:
            fks = fks[fks != ""]

        invalidas = fks[~fks.isin(chaves_destino)]

        if len(invalidas):
            linhas = [int(i) + 2 for i in invalidas.index.tolist()]
            valores_unicos = invalidas.unique().tolist()
            achados.append({
                "severidade": "critico",
                "tipo": "referencia_invalida",
                "tabela_origem": t_orig,
                "coluna_fk": col_fk,
                "tabela_destino": t_dest,
                "coluna_pk": col_pk,
                "total_invalidas": len(invalidas),
                "valores_invalidos": valores_unicos[:10],
                "linhas": linhas[:20],
            })

    resultado["dados"]["total_referencias_verificadas"] = len(referencias)
    resultado["dados"]["total_achados"] = len(achados)
    resultado["dados"]["achados"] = achados

    if achados:
        resultado["status"] = "erro"
        resultado["erros"].append(
            f"{len(achados)} relação(ões) com referências inválidas."
        )

    return resultado
