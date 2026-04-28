"""
Skill: Validação de árvore hierárquica
Detecta ciclos, nós órfãos e raízes em estruturas pai-filho.
"""
import pandas as pd


def validar(df: pd.DataFrame, col_codigo: str, col_pai: str) -> dict:
    """
    Valida uma estrutura hierárquica pai-filho.

    Detecta:
    - Ciclos diretos e indiretos
    - Nós órfãos (pai referenciado não existe)
    - Múltiplas raízes (quando apenas uma é esperada)
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    for col in [col_codigo, col_pai]:
        if col not in df.columns:
            resultado["status"] = "erro"
            resultado["erros"].append(f"Coluna '{col}' não encontrada.")
            return resultado

    codigos = set(df[col_codigo].dropna().astype(str).str.strip())
    mapa_pai = {}
    for _, row in df.iterrows():
        cod = str(row[col_codigo]).strip() if pd.notna(row[col_codigo]) else None
        pai = str(row[col_pai]).strip() if pd.notna(row[col_pai]) else None
        if cod:
            mapa_pai[cod] = pai

    orfaos = [
        cod for cod, pai in mapa_pai.items()
        if pai and pai not in codigos
    ]

    raizes = [cod for cod, pai in mapa_pai.items() if not pai]

    ciclos = _detectar_ciclos(mapa_pai)

    resultado["dados"]["total_nos"] = len(codigos)
    resultado["dados"]["raizes"] = raizes
    resultado["dados"]["total_raizes"] = len(raizes)
    resultado["dados"]["orfaos"] = orfaos
    resultado["dados"]["total_orfaos"] = len(orfaos)
    resultado["dados"]["ciclos"] = ciclos
    resultado["dados"]["total_ciclos"] = len(ciclos)

    if ciclos:
        resultado["status"] = "erro"
        resultado["erros"].append(f"{len(ciclos)} ciclo(s) detectado(s) na hierarquia.")
    if orfaos:
        resultado["status"] = "erro" if resultado["status"] == "erro" else "aviso"
        resultado["avisos"].append(f"{len(orfaos)} nó(s) órfão(s): pai inexistente.")
    if len(raizes) > 1:
        resultado["avisos"].append(f"{len(raizes)} raízes encontradas. Esperado: 1.")

    return resultado


def _detectar_ciclos(mapa_pai: dict) -> list:
    ciclos = []
    visitados_global = set()

    for inicio in mapa_pai:
        if inicio in visitados_global:
            continue
        caminho = []
        visitados = set()
        atual = inicio

        while atual and atual not in visitados_global:
            if atual in visitados:
                idx = caminho.index(atual)
                ciclo = caminho[idx:]
                if frozenset(ciclo) not in {frozenset(c) for c in ciclos}:
                    ciclos.append(ciclo)
                break
            visitados.add(atual)
            caminho.append(atual)
            atual = mapa_pai.get(atual)

        visitados_global.update(visitados)

    return ciclos
