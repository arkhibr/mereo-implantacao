"""
Skill: Construção de dicionário de recodificação
Gera mapa de tradução entre IDs de origem e IDs de destino.
"""
import csv
from pathlib import Path


def construir(ids_origem: list, prefixo: str, mapa_customizado: dict = None) -> dict:
    """
    Gera IDs de destino para uma lista de IDs de origem.
    mapa_customizado sobrescreve a geração automática para IDs específicos.
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    mapa_customizado = mapa_customizado or {}
    dicionario = []
    vistos = set()

    for id_orig in ids_origem:
        chave = str(id_orig).strip()
        if chave in vistos:
            continue
        vistos.add(chave)

        if chave in mapa_customizado:
            id_dest = str(mapa_customizado[chave]).strip()
        else:
            id_dest = f"{prefixo}{chave}"

        dicionario.append({"id_origem": chave, "id_destino": id_dest})

    resultado["dados"]["prefixo"] = prefixo
    resultado["dados"]["total_entradas"] = len(dicionario)
    resultado["dados"]["dicionario"] = dicionario

    return resultado


def salvar(dicionario: list, caminho: str) -> dict:
    """Persiste o dicionário em CSV para reutilização."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    try:
        Path(caminho).parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["id_origem", "id_destino"], delimiter=";")
            writer.writeheader()
            writer.writerows(dicionario)
        resultado["dados"]["arquivo"] = caminho
        resultado["dados"]["total_entradas"] = len(dicionario)
    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))

    return resultado


def carregar(caminho: str) -> dict:
    """Carrega dicionário de um CSV e retorna como dict {id_origem: id_destino}."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    try:
        with open(caminho, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=";")
            mapa = {row["id_origem"]: row["id_destino"] for row in reader}
        resultado["dados"]["mapa"] = mapa
        resultado["dados"]["total_entradas"] = len(mapa)
    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))

    return resultado
