"""
Skill: Diagnóstico de erros de planilha
Detecta erros de fórmula Excel, campos obrigatórios vazios e linhas vazias.
"""
import pandas as pd

ERROS_EXCEL = {
    "#N/A", "#REF!", "#VALOR!", "#DIV/0!", "#NOME?", "#NULO!", "#NÚM!",
    "#NULL!", "#VALUE!", "#NAME?", "#NUM!", "#N/D",
}


def diagnosticar(df: pd.DataFrame, obrigatorios: list = None) -> dict:
    """Detecta erros de fórmula, campos obrigatórios vazios e linhas totalmente vazias."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}
    achados = []

    for col in df.columns:
        mascara = df[col].astype(str).str.strip().str.upper().isin(ERROS_EXCEL)
        linhas = [int(i) + 2 for i in df.index[mascara].tolist()]
        if linhas:
            achados.append({
                "tipo": "erro_formula",
                "severidade": "alto",
                "coluna": str(col),
                "linhas": linhas,
                "quantidade": len(linhas),
            })

    linhas_vazias = [int(i) + 2 for i in df.index[df.isna().all(axis=1)].tolist()]
    if linhas_vazias:
        achados.append({
            "tipo": "linhas_vazias",
            "severidade": "medio",
            "coluna": None,
            "linhas": linhas_vazias,
            "quantidade": len(linhas_vazias),
        })

    for campo in (obrigatorios or []):
        if campo not in df.columns:
            achados.append({
                "tipo": "coluna_ausente",
                "severidade": "critico",
                "coluna": campo,
                "linhas": [],
                "quantidade": len(df),
            })
            continue
        mascara = df[campo].isna() | (df[campo].astype(str).str.strip() == "")
        linhas = [int(i) + 2 for i in df.index[mascara].tolist()]
        if linhas:
            achados.append({
                "tipo": "obrigatorio_vazio",
                "severidade": "critico",
                "coluna": campo,
                "linhas": linhas,
                "quantidade": len(linhas),
            })

    resultado["dados"]["total_achados"] = len(achados)
    resultado["dados"]["achados"] = achados

    severidades = {a["severidade"] for a in achados}
    if "critico" in severidades:
        resultado["status"] = "erro"
    elif severidades:
        resultado["status"] = "aviso"

    return resultado
