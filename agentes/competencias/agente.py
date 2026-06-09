"""
Agente de Competências
Transforma a matriz cargo×competência do cliente no catálogo de Competências e
Fatores (modelo fator-espelho) para o template da plataforma.

Domínio: primeiro do grupo `competencias` (o formulário referencia os códigos
gerados aqui). A lógica de leitura da matriz é pura, em
`ferramentas/transformacao/competencias_matriz.py`.
"""
import csv
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.transformacao import competencias_matriz as cm

STAGING_DIR = "staging/08_competencias"


def executar(pasta_cliente: str) -> dict:
    resultado = {"status": "ok", "agente": "competencias", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"
    staging = base / STAGING_DIR
    staging.mkdir(parents=True, exist_ok=True)

    conf = _conf_competencias(config)
    if conf is None:
        resultado["status"] = "erro"
        resultado["erros"].append(
            "mapeamento.json sem entrada 'competencias'. Execute o mapeamento primeiro."
        )
        return resultado

    arquivo = conf.get("arquivo_sugerido")
    if not arquivo:
        resultado["status"] = "erro"
        resultado["erros"].append("Arquivo de competências não identificado no mapeamento.")
        return resultado

    caminho = base / arquivo
    if not caminho.exists():
        resultado["status"] = "erro"
        resultado["erros"].append(f"Arquivo não encontrado: {arquivo}")
        return resultado

    extr = cm.extrair(str(caminho), conf.get("aba_sugerida"))
    resultado["avisos"].extend(extr["avisos"])

    df = pd.DataFrame(extr["catalogo"], columns=cm.COLUNAS_CATALOGO)
    caminho_out = staging / "competencias_transformadas.csv"
    df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8-sig")

    # Dicionário de códigos — espelha o padrão dos demais agentes (config/).
    caminho_dic = config / "dicionario_competencias.csv"
    with open(caminho_dic, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["nome", "codigo_competencia", "codigo_fator"])
        w.writeheader()
        w.writerows(extr["dicionario"])

    resultado["dados"]["linhas_transformadas"] = len(df)
    resultado["dados"]["arquivos_gerados"] = [str(caminho_out), str(caminho_dic)]
    return resultado


def _conf_competencias(config: Path) -> dict:
    caminho = config / "mapeamento.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f).get("competencias")
