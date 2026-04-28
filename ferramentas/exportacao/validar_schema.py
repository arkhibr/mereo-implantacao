"""
Skill: Validação de schema contra template
Verifica conformidade de um DataFrame com o schema esperado do template.
"""
import re
import pandas as pd


def validar(df: pd.DataFrame, schema: dict) -> dict:
    """
    Valida um DataFrame contra um schema declarado.

    schema: {
        "colunas": [
            {"nome": "Login*", "obrigatorio": True, "tipo": "texto"},
            ...
        ]
    }
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}
    achados = []

    colunas_schema = [c["nome"] for c in schema.get("colunas", [])]
    colunas_df = list(df.columns)

    ausentes = [c for c in colunas_schema if c not in colunas_df]
    excedentes = [c for c in colunas_df if c not in colunas_schema]
    fora_de_ordem = colunas_schema != [c for c in colunas_schema if c in colunas_df]

    if ausentes:
        for col in ausentes:
            achados.append({"severidade": "critico", "tipo": "coluna_ausente", "coluna": col, "detalhe": ""})
    if excedentes:
        for col in excedentes:
            achados.append({"severidade": "medio", "tipo": "coluna_excedente", "coluna": col, "detalhe": ""})
    if fora_de_ordem:
        achados.append({"severidade": "baixo", "tipo": "ordem_incorreta", "coluna": None,
                        "detalhe": f"Esperado: {colunas_schema}"})

    for spec in schema.get("colunas", []):
        nome = spec["nome"]
        if nome not in df.columns:
            continue

        if spec.get("obrigatorio"):
            mascara = df[nome].isna() | (df[nome].astype(str).str.strip() == "")
            qtd = int(mascara.sum())
            if qtd:
                achados.append({
                    "severidade": "critico",
                    "tipo": "obrigatorio_vazio",
                    "coluna": nome,
                    "detalhe": f"{qtd} linha(s) vazia(s)",
                })

        tipo_esp = spec.get("tipo")
        if tipo_esp == "inteiro":
            invalidos = df[nome].dropna()[~df[nome].dropna().astype(str).str.match(r"^\d+$")]
            if len(invalidos):
                achados.append({
                    "severidade": "alto",
                    "tipo": "tipo_invalido",
                    "coluna": nome,
                    "detalhe": f"{len(invalidos)} valor(es) não inteiro(s). Ex: {invalidos.head(3).tolist()}",
                })
        elif tipo_esp == "booleano":
            invalidos = df[nome].dropna()[~df[nome].dropna().astype(str).isin(["0", "1"])]
            if len(invalidos):
                achados.append({
                    "severidade": "alto",
                    "tipo": "tipo_invalido",
                    "coluna": nome,
                    "detalhe": f"Esperado 0 ou 1. Encontrado: {invalidos.unique().tolist()[:5]}",
                })
        elif tipo_esp == "email":
            pat = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
            invalidos = df[nome].dropna()[~df[nome].dropna().astype(str).str.match(pat)]
            if len(invalidos):
                achados.append({
                    "severidade": "alto",
                    "tipo": "formato_invalido",
                    "coluna": nome,
                    "detalhe": f"{len(invalidos)} e-mail(s) inválido(s). Ex: {invalidos.head(3).tolist()}",
                })

    resultado["dados"]["total_achados"] = len(achados)
    resultado["dados"]["achados"] = achados

    severidades = {a["severidade"] for a in achados}
    if "critico" in severidades or "alto" in severidades:
        resultado["status"] = "erro"
    elif severidades:
        resultado["status"] = "aviso"

    return resultado


def schema_do_template(caminho_csv: str) -> dict:
    """Infere o schema a partir de um arquivo de template CSV."""
    df = pd.read_csv(caminho_csv, sep=";", nrows=1, encoding="latin-1")
    colunas = []
    for col in df.columns:
        colunas.append({
            "nome": col,
            "obrigatorio": col.strip().endswith("*"),
            "tipo": "texto",
        })
    return {"colunas": colunas}
