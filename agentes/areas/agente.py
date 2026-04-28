"""
Agente de Áreas
Transforma dados de estrutura organizacional para o template da plataforma.
"""
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.codificacao import construir_dicionario, aplicar_dicionario
from ferramentas.hierarquia import validar_hierarquia, reconstruir_hierarquia
from ferramentas.qualidade import erros_planilha

CAMPOS_OBRIGATORIOS = ["Código da Área*", "Descrição da Área*", "Código da Filial*"]
TODOS_CAMPOS = ["Código da Área*", "Descrição da Área*", "Código da Filial*",
                "Código da Área Superior", "Status da Área"]
PREFIXO_AREA = "AREA_"
PREFIXO_FILIAL = "FIL_"
STAGING_DIR = "staging/01_areas"


def executar(pasta_cliente: str, codigo_filial_padrao: str = "1") -> dict:
    resultado = {"status": "ok", "agente": "areas", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"
    staging = base / STAGING_DIR
    staging.mkdir(parents=True, exist_ok=True)

    mapeamento = _carregar_mapeamento(config)
    if mapeamento is None:
        resultado["status"] = "erro"
        resultado["erros"].append("mapeamento.json não encontrado. Execute o Agente de Mapeamento primeiro.")
        return resultado

    conf_areas = mapeamento.get("areas", {})
    arquivo = conf_areas.get("arquivo_sugerido")
    aba = conf_areas.get("aba_sugerida")

    if not arquivo:
        resultado["status"] = "erro"
        resultado["erros"].append("Arquivo de áreas não identificado no mapeamento.")
        return resultado

    df_raw = _ler_dados(base / arquivo, aba, conf_areas.get("header_linha", 0))
    if df_raw is None:
        resultado["status"] = "erro"
        resultado["erros"].append(f"Não foi possível ler: {arquivo} / {aba}")
        return resultado

    # Diagnóstico de qualidade antes de transformar
    res_qual = erros_planilha.diagnosticar(df_raw)
    if res_qual["dados"]["achados"]:
        resultado["avisos"].append(
            f"{len(res_qual['dados']['achados'])} problema(s) de qualidade encontrado(s) nos dados brutos."
        )

    df = _aplicar_mapeamento(df_raw, conf_areas["campos"])

    # Preencher coluna de filial se ausente
    if "Código da Filial*" not in df.columns or df["Código da Filial*"].isna().all():
        df["Código da Filial*"] = codigo_filial_padrao
        resultado["avisos"].append(f"Código da Filial preenchido com valor padrão: {codigo_filial_padrao}")

    # Recodificar área
    ids_area = df["Código da Área*"].dropna().astype(str).unique().tolist()
    res_dic = construir_dicionario.construir(ids_area, PREFIXO_AREA)
    dic_areas = {e["id_origem"]: e["id_destino"] for e in res_dic["dados"]["dicionario"]}

    res_aplic = aplicar_dicionario.aplicar(df, dic_areas, ["Código da Área*", "Código da Área Superior"])
    df = res_aplic["dados"]["dataframe"]

    # Validar hierarquia
    if "Código da Área Superior" in df.columns:
        res_hier = validar_hierarquia.validar(df, "Código da Área*", "Código da Área Superior")
        resultado["dados"]["hierarquia"] = {
            "ciclos": res_hier["dados"]["total_ciclos"],
            "orfaos": res_hier["dados"]["total_orfaos"],
            "raizes": res_hier["dados"]["total_raizes"],
        }
        if res_hier["status"] == "erro":
            resultado["status"] = "aviso"
            resultado["avisos"].extend(res_hier["erros"])

    # Garantir colunas na ordem do template
    for col in TODOS_CAMPOS:
        if col not in df.columns:
            df[col] = ""
    df = df[TODOS_CAMPOS]

    # Persistir dicionário e staging
    caminho_dic = config / "dicionario_areas.csv"
    construir_dicionario.salvar(res_dic["dados"]["dicionario"], str(caminho_dic))

    caminho_out = staging / "areas_transformadas.csv"
    df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8")

    resultado["dados"]["linhas_transformadas"] = len(df)
    resultado["dados"]["arquivos_gerados"] = [str(caminho_out), str(caminho_dic)]
    return resultado


# ── helpers privados ──────────────────────────────────────────────────────────

def _carregar_mapeamento(config: Path) -> dict:
    caminho = config / "mapeamento.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _ler_dados(caminho: Path, aba: str, header_linha: int = 0) -> pd.DataFrame:
    try:
        if caminho.suffix.lower() == ".csv":
            return pd.read_csv(str(caminho), sep=None, engine="python", encoding_errors="replace")
        return pd.read_excel(str(caminho), sheet_name=aba, header=header_linha, engine="openpyxl")
    except Exception:
        return None


def _aplicar_mapeamento(df: pd.DataFrame, campos: list) -> pd.DataFrame:
    """Renomeia colunas do cliente para os nomes do template conforme o mapeamento."""
    renomear = {
        c["campo_cliente"]: c["campo_template"]
        for c in campos
        if c.get("campo_cliente") and c["campo_cliente"] in df.columns
    }
    return df.rename(columns=renomear)
