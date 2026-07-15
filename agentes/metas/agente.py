"""
Agente de Metas
Transforma metas (Individual, Compartilhada, Projeto) para os templates da plataforma.
É o agente mais complexo: classifica o tipo de cada meta antes de transformar.
"""
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.codificacao import aplicar_dicionario
from ferramentas.transformacao import normalizar_dominio, agregar_pipe
from ferramentas.transformacao.dominios_plataforma import (
    EQUIVALENCIAS_AGREGACAO, EQUIVALENCIAS_DEFINICAO_VALOR,
)
from ferramentas.qualidade import erros_planilha

CAMPOS_INDIVIDUAL = [
    "Código da Meta *", "Código da Área *", "Login do Responsável pela Meta *",
    "Login do Data-Provider *", "Código do Indicador *", "Código do Pilar Estratégico *",
    "Código da Curva de Notas", "Códigos da Metas Superiores", "Objetivo da Meta *",
    "Peso da Meta *", "Tipo de Agregação *", "Tipo de Definição do Valor *",
    "Fonte de Dados", "Memória de Cálculo", "Rótulos", " Meta Qualificadora", "Meta Auditável",
]
CAMPOS_COMPARTILHADA = [
    "Código da Meta *", "Código da Área *", "Login do Responsável pela Meta *",
    "Código da meta a ser compartilhada *", " Códigos das Metas Superiores",
    "Peso da Meta *", " Rótulos", " Meta Qualificadora",
]
CAMPOS_PROJETO = [
    "Código da Meta *", "Código da Área *", "Login do Responsável pela Meta *",
    "Código do Indicador *", "Código do Pilar Estratégico *", "Código da Curva de Notas",
    "Códigos das Metas Superiores", "Objetivo da Meta *", "Peso da Meta *",
    "Fonte de Dados", "Memória de Cálculo", "Rótulos", "Meta Auditável",
]
STAGING_DIRS = {
    "individual":    "staging/04_metas_individuais",
    "compartilhada": "staging/05_metas_compartilhadas",
    "projeto":       "staging/06_metas_projeto",
}
TIPO_CHAVE = {
    "metas_individuais":    "individual",
    "metas_compartilhadas": "compartilhada",
    "metas_projeto":        "projeto",
}


def executar(pasta_cliente: str) -> dict:
    resultado = {"status": "ok", "agente": "metas", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"

    mapeamento = _carregar_mapeamento(config)
    if mapeamento is None:
        resultado["status"] = "erro"
        resultado["erros"].append("mapeamento.json não encontrado.")
        return resultado

    dic_areas = _carregar_dic(config / "dicionario_areas.csv")
    dic_colab = _carregar_dic(config / "dicionario_colaboradores.csv")
    dic_ind = _carregar_dic(config / "dicionario_indicadores.csv")

    contagens = {}
    arquivos_gerados = []

    for tipo in ["metas_individuais", "metas_compartilhadas", "metas_projeto"]:
        chave = TIPO_CHAVE[tipo]
        conf = mapeamento.get(tipo, {})
        arquivo = conf.get("arquivo_sugerido")
        if not arquivo:
            resultado["avisos"].append(f"Dados de '{tipo}' não mapeados — ignorado.")
            continue
        df_raw = _ler_dados(base / arquivo, conf.get("aba_sugerida"), conf.get("header_linha", 0))

        if df_raw is None:
            resultado["avisos"].append(f"Dados de '{tipo}' não encontrados — ignorado.")
            continue

        res_qual = erros_planilha.diagnosticar(df_raw)
        if res_qual["dados"]["achados"]:
            resultado["avisos"].append(f"{tipo}: {len(res_qual['dados']['achados'])} problema(s) nos dados brutos.")

        df = _aplicar_mapeamento(df_raw, conf.get("campos", []))
        avisos_transf = []
        df = _classificar_e_transformar(df, chave, dic_areas, dic_colab, dic_ind, config,
                                        avisos=avisos_transf)
        resultado["avisos"].extend(f"{tipo}: {av}" for av in avisos_transf)

        staging = base / STAGING_DIRS[chave]
        staging.mkdir(parents=True, exist_ok=True)
        campos = {"individual": CAMPOS_INDIVIDUAL, "compartilhada": CAMPOS_COMPARTILHADA,
                  "projeto": CAMPOS_PROJETO}[chave]

        for col in campos:
            if col not in df.columns:
                df[col] = ""
        df = df[campos]

        caminho_out = staging / f"metas_{chave}_transformadas.csv"
        df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8-sig")
        contagens[tipo] = len(df)
        arquivos_gerados.append(str(caminho_out))

    resultado["dados"]["contagens"] = contagens
    resultado["dados"]["arquivos_gerados"] = arquivos_gerados
    return resultado


def _classificar_e_transformar(df: pd.DataFrame, tipo: str, dic_areas: dict,
                                dic_colab: dict, dic_ind: dict, config: Path,
                                avisos: list = None) -> pd.DataFrame:
    if avisos is None:
        avisos = []

    # Derivar Código do Indicador * do Código da Meta * se não mapeado na fonte
    if "Código da Meta *" in df.columns:
        if "Código do Indicador *" not in df.columns or df["Código do Indicador *"].isna().all():
            df["Código do Indicador *"] = df["Código da Meta *"].copy()
            if not dic_ind:
                avisos.append(
                    "'Código do Indicador *' derivado do código da meta SEM dicionário de "
                    "indicadores (config/dicionario_indicadores.csv) — os valores podem não "
                    "corresponder aos códigos da plataforma (limite Texto(10)); a validação "
                    "vai bloquear códigos suspeitos."
                )

    # Códigos de meta do cliente passam adiante como estão — a plataforma não usa prefixo.
    # De-para manual opcional em config/dicionario_metas_<tipo>.csv (curva de alcance e
    # valores consolidam os mesmos arquivos para manter a referência consistente).
    dic_meta = _carregar_dic(config / f"dicionario_metas_{tipo}.csv")
    if dic_meta and "Código da Meta *" in df.columns:
        colunas_meta = [c for c in ["Código da Meta *", "Código da meta a ser compartilhada *",
                                     "Códigos da Metas Superiores"] if c in df.columns]
        res = aplicar_dicionario.aplicar(df, dic_meta, colunas_meta, ausentes="manter")
        df = res["dados"]["dataframe"]
        avisos.append(f"De-para manual de metas aplicado (config/dicionario_metas_{tipo}.csv).")

    if dic_areas and "Código da Área *" in df.columns:
        res = aplicar_dicionario.aplicar(df, dic_areas, ["Código da Área *"], ausentes="manter")
        df = res["dados"]["dataframe"]

    if dic_ind and "Código do Indicador *" in df.columns:
        res = aplicar_dicionario.aplicar(df, dic_ind, ["Código do Indicador *"], ausentes="manter")
        df = res["dados"]["dataframe"]

    # Converter email → login nas colunas de responsável (padrão: user@dominio → user)
    for col_login in ["Login do Responsável pela Meta *", "Login do Data-Provider *"]:
        if col_login in df.columns:
            df[col_login] = df[col_login].apply(
                lambda x: x.split("@")[0].lower() if pd.notna(x) and "@" in str(x) else x
            )

    # Extrair primeiro valor numérico do peso (pode ser "40 / 10 / 10 / ...")
    if "Peso da Meta *" in df.columns:
        def _extrair_primeiro_peso(val):
            if pd.isna(val):
                return None
            s = str(val).split("/")[0].strip()
            try:
                return float(s)
            except ValueError:
                return None
        df["Peso da Meta *"] = df["Peso da Meta *"].apply(_extrair_primeiro_peso)

    # Normalizar domínios da plataforma (texto → código oficial)
    for coluna, equivalencias in [
        ("Tipo de Agregação *", EQUIVALENCIAS_AGREGACAO),
        ("Tipo de Definição do Valor *", EQUIVALENCIAS_DEFINICAO_VALOR),
    ]:
        if coluna in df.columns:
            res = normalizar_dominio.normalizar(df, coluna, equivalencias, padrao=None)
            df = res["dados"]["dataframe"]
            if res["dados"]["nao_reconhecidos"]:
                avisos.append(
                    f"'{coluna}': valor(es) não reconhecido(s) no domínio da plataforma: "
                    f"{res['dados']['nao_reconhecidos'][:5]}"
                )

    # Preencher "Tipo de Definição do Valor *" com default se ausente
    # (1 = Definido pelo Usuário, código oficial da plataforma)
    if "Tipo de Definição do Valor *" not in df.columns or df["Tipo de Definição do Valor *"].isna().all():
        df["Tipo de Definição do Valor *"] = "1"
        avisos.append("'Tipo de Definição do Valor *' preenchido com padrão: 1 (Definido pelo Usuário).")

    return df


def _carregar_mapeamento(config: Path) -> dict:
    caminho = config / "mapeamento.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _carregar_dic(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    import csv
    with open(caminho, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        return {row["id_origem"]: row["id_destino"] for row in reader}


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
