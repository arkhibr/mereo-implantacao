"""
Agente de Formulários (Gestão de Formulários / Função)
Gera, a partir da mesma matriz cargo×competência, um formulário de avaliação por
cargo: cada linha associa competência+fator (por código) ao peso, replicado nos
avaliadores em uso (Gestor→LIDER, Autoavaliação→AUTO).

Domínio: roda depois de `competencias` (referencia os mesmos códigos). Re-extrai
da fonte em vez de ler o staging do catálogo — a extração é determinística, então
os códigos CPT##/FT## saem idênticos aos do agente de competências.
"""
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.transformacao import competencias_matriz as cm

STAGING_DIR = "staging/09_formularios"


def executar(pasta_cliente: str) -> dict:
    resultado = {"status": "ok", "agente": "formularios", "dados": {}, "erros": [], "avisos": []}

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
    caminho = base / arquivo if arquivo else None
    if not caminho or not caminho.exists():
        resultado["status"] = "erro"
        resultado["erros"].append(f"Arquivo de competências não encontrado: {arquivo}")
        return resultado

    extr = cm.extrair(str(caminho), conf.get("aba_sugerida"))
    # Avisos de soma de peso ≠ 1 são relevantes aqui (é o peso que entra no formulário).
    resultado["avisos"].extend(a for a in extr["avisos"] if "Soma de pesos" in a)

    df = pd.DataFrame(extr["formularios"], columns=cm.COLUNAS_FORMULARIO)
    caminho_out = staging / "formularios_transformados.csv"
    df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8-sig")

    resultado["dados"]["linhas_transformadas"] = len(df)
    resultado["dados"]["arquivos_gerados"] = [str(caminho_out)]
    return resultado


def _conf_competencias(config: Path) -> dict:
    caminho = config / "mapeamento.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f).get("competencias")
