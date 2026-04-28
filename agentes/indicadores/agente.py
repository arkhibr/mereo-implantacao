"""
Agente de Indicadores (KPI)
Transforma definições de KPIs para o template da plataforma.
"""
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.codificacao import construir_dicionario, aplicar_dicionario
from ferramentas.transformacao import normalizar_dominio
from ferramentas.qualidade import erros_planilha

TODOS_CAMPOS = [
    "Código do Indicador *", "Descrição do Indicador *", "Código da Unidade de Medida *",
    "Código da Faixa de Farol *", "Código de Frequência de Acompanhamento *", "Polaridade *",
    "Memória de Cálculo", "Ativo *", "Personalizar parâmetros de alerta via e-mail para este indicador",
    "Frequência de recorrência de e-mail", "Envio de e-mail de data limite a partir do dia",
    "Envio de e-mail de alerta a partir do dia", "Dias de atraso para notificação dos Stakeholders",
    "Stakeholders a serem notificados",
]
CAMPOS_OBRIGATORIOS = [
    "Código do Indicador *", "Descrição do Indicador *", "Código da Unidade de Medida *",
    "Código da Faixa de Farol *", "Código de Frequência de Acompanhamento *", "Polaridade *", "Ativo *",
]
EQUIVALENCIAS_POLARIDADE = {
    "1": ["1", "maior melhor", "maior_melhor", "crescente", "positivo", "asc"],
    "2": ["2", "menor melhor", "menor_melhor", "decrescente", "negativo", "desc"],
    "3": ["3", "nominal", "exato", "igual"],
}
PREFIXO_INDICADOR = "IND_"
STAGING_DIR = "staging/03_indicadores"


def executar(pasta_cliente: str, unidade_padrao: str = "1",
             faixa_padrao: str = "FXF01", frequencia_padrao: str = "1") -> dict:
    resultado = {"status": "ok", "agente": "indicadores", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"
    staging = base / STAGING_DIR
    staging.mkdir(parents=True, exist_ok=True)

    mapeamento = _carregar_mapeamento(config)
    if mapeamento is None:
        resultado["status"] = "erro"
        resultado["erros"].append("mapeamento.json não encontrado.")
        return resultado

    conf = mapeamento.get("indicadores", {})
    arquivo = conf.get("arquivo_sugerido")
    if not arquivo:
        resultado["avisos"].append("Dados de indicadores não mapeados — ignorado.")
        return resultado
    df_raw = _ler_dados(base / arquivo, conf.get("aba_sugerida"), conf.get("header_linha", 0))
    if df_raw is None:
        resultado["status"] = "erro"
        resultado["erros"].append("Dados de indicadores não encontrados.")
        return resultado

    res_qual = erros_planilha.diagnosticar(df_raw)
    if res_qual["dados"]["achados"]:
        resultado["avisos"].append(f"{len(res_qual['dados']['achados'])} problema(s) nos dados brutos.")

    df = _aplicar_mapeamento(df_raw, conf.get("campos", []))

    # Recodificar indicadores
    if "Código do Indicador *" in df.columns:
        ids = df["Código do Indicador *"].dropna().astype(str).unique().tolist()
        res_dic = construir_dicionario.construir(ids, PREFIXO_INDICADOR)
        dic = {e["id_origem"]: e["id_destino"] for e in res_dic["dados"]["dicionario"]}
        res_aplic = aplicar_dicionario.aplicar(df, dic, ["Código do Indicador *"])
        df = res_aplic["dados"]["dataframe"]
        construir_dicionario.salvar(res_dic["dados"]["dicionario"], str(config / "dicionario_indicadores.csv"))

    # Normalizar polaridade
    if "Polaridade *" in df.columns:
        res = normalizar_dominio.normalizar(df, "Polaridade *", EQUIVALENCIAS_POLARIDADE, padrao="1")
        df = res["dados"]["dataframe"]
        if res["avisos"]:
            resultado["avisos"].extend(res["avisos"])

    # Defaults para campos obrigatórios
    defaults = {
        "Código da Unidade de Medida *": unidade_padrao,
        "Código da Faixa de Farol *": faixa_padrao,
        "Código de Frequência de Acompanhamento *": frequencia_padrao,
        "Ativo *": "1",
    }
    for campo, valor in defaults.items():
        if campo not in df.columns or df[campo].isna().all():
            df[campo] = valor
            resultado["avisos"].append(f"'{campo}' preenchido com padrão: {valor}")

    for col in TODOS_CAMPOS:
        if col not in df.columns:
            df[col] = ""
    df = df[TODOS_CAMPOS]

    caminho_out = staging / "indicadores_transformados.csv"
    df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8")

    resultado["dados"]["linhas_transformadas"] = len(df)
    resultado["dados"]["arquivos_gerados"] = [str(caminho_out)]
    return resultado


def _carregar_mapeamento(config: Path) -> dict:
    caminho = config / "mapeamento.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _ler_dados(caminho: Path, aba: str, header_linha: int = 0) -> pd.DataFrame:
    try:
        if not caminho.exists():
            return None
        if caminho.suffix.lower() == ".csv":
            return pd.read_csv(str(caminho), sep=None, engine="python", encoding_errors="replace")
        return pd.read_excel(str(caminho), sheet_name=aba, header=header_linha, engine="openpyxl")
    except Exception:
        return None


def _aplicar_mapeamento(df: pd.DataFrame, campos: list) -> pd.DataFrame:
    renomear = {
        c["campo_cliente"]: c["campo_template"]
        for c in campos
        if c.get("campo_cliente") and c["campo_cliente"] in df.columns
    }
    return df.rename(columns=renomear)
