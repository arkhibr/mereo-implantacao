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
from ferramentas.inferencia.indicadores import inferir_polaridade, inferir_unidade
from ferramentas.transformacao import normalizar_dominio, agregar_pipe
from ferramentas.transformacao import periodicidade
from ferramentas.transformacao.dominios_plataforma import (
    EQUIVALENCIAS_AGREGACAO, EQUIVALENCIAS_DEFINICAO_VALOR,
)
from ferramentas.qualidade import erros_planilha
from agentes.indicadores.agente import TODOS_CAMPOS as CAMPOS_INDICADORES

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
    pares_indicadores = []

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
        derivou_indicador = chave in ("individual", "projeto") and (
            "Código do Indicador *" not in df.columns or df["Código do Indicador *"].isna().all()
        )
        avisos_transf = []
        df = _classificar_e_transformar(df, chave, dic_areas, dic_colab, dic_ind, config,
                                        avisos=avisos_transf)
        resultado["avisos"].extend(f"{tipo}: {av}" for av in avisos_transf)

        if derivou_indicador:
            pares_indicadores.extend(
                zip(df["Código do Indicador *"].tolist(),
                    df.get("Objetivo da Meta *", pd.Series([""] * len(df))).tolist())
            )

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

    # Sem cadastro prévio de indicadores na plataforma (decisão de 2026-07-15): quando o
    # indicador é derivado das metas e o cliente não tem fonte própria, o arquivo de
    # importação de indicadores sai daqui, 1:1, para a FK metas→indicadores fechar.
    if pares_indicadores and not mapeamento.get("indicadores", {}).get("arquivo_sugerido"):
        frequencias = _detectar_frequencias_valores(base, mapeamento, resultado["avisos"])
        df_ind = _gerar_indicadores_derivados(pares_indicadores, frequencias)
        staging_ind = base / "staging/03_indicadores"
        staging_ind.mkdir(parents=True, exist_ok=True)
        caminho_ind = staging_ind / "indicadores_transformados.csv"
        df_ind.to_csv(str(caminho_ind), sep=";", index=False, encoding="utf-8-sig")
        contagens["indicadores_derivados"] = len(df_ind)
        arquivos_gerados.append(str(caminho_ind))
        resultado["avisos"].append(
            f"Indicadores gerados 1:1 a partir das metas ({len(df_ind)}): unidade/faixa/"
            "frequência preenchidas com padrão e polaridade por heurística — revisar antes da importação."
        )

    resultado["dados"]["contagens"] = contagens
    resultado["dados"]["arquivos_gerados"] = arquivos_gerados
    return resultado


def _detectar_frequencias_valores(base: Path, mapeamento: dict, avisos: list) -> dict:
    """
    Frequência por meta a partir da estrutura dos valores na fonte
    (1 valor no ano = anual, 2+ = mensal). Previstos primeiro; realizados como
    fallback (realizados de ano parcial subestimam a contagem).
    """
    for chave in ["valores_previstos", "valores_realizados"]:
        conf = mapeamento.get(chave, {})
        arquivo = conf.get("arquivo_sugerido")
        if not arquivo:
            continue
        df = _ler_dados(base / arquivo, conf.get("aba_sugerida"), conf.get("header_linha", 0))
        if df is None:
            continue
        col_meta = next(
            (c for c in df.columns if "meta" in str(c).lower() or "cod" in str(c).lower()),
            df.columns[0] if len(df.columns) else None,
        )
        res = periodicidade.detectar_frequencias(df, col_meta)
        frequencias = res["dados"]["frequencias"]
        if frequencias:
            anuais = sum(1 for f in frequencias.values() if f == periodicidade.FREQUENCIA_ANUAL)
            avisos.append(
                f"Periodicidade detectada pelos valores de '{chave}': "
                f"{len(frequencias) - anuais} mensal(is), {anuais} anual(is)."
            )
            return frequencias
    return {}


def _gerar_indicadores_derivados(pares: list, frequencias: dict = None) -> pd.DataFrame:
    """Monta o staging de indicadores (1 por código) a partir de (código, objetivo) das metas."""
    frequencias = frequencias or {}
    vistos = {}
    for codigo, objetivo in pares:
        if pd.isna(codigo) or str(codigo).strip() == "":
            continue
        codigo = str(codigo).strip()
        if codigo not in vistos:
            descricao = str(objetivo).strip() if pd.notna(objetivo) and str(objetivo).strip() else codigo
            vistos[codigo] = descricao

    linhas = []
    for codigo, descricao in vistos.items():
        polaridade_texto, _confianca = inferir_polaridade(descricao)
        linha = {c: "" for c in CAMPOS_INDICADORES}
        linha.update({
            "Código do Indicador *": codigo,
            "Descrição do Indicador *": descricao,
            # Unidade inferida do texto; sem sinal, UM007 (Número) como neutro
            "Código da Unidade de Medida *": inferir_unidade(descricao) or "UM007",
            "Código da Faixa de Farol *": "FXF01",
            # Frequência detectada pela estrutura dos valores; sem sinal, mensal
            "Código de Frequência de Acompanhamento *": frequencias.get(codigo, "1"),
            "Polaridade *": "2" if polaridade_texto == "Menor é Melhor" else "1",
            "Ativo *": "1",
        })
        linhas.append(linha)
    return pd.DataFrame(linhas, columns=CAMPOS_INDICADORES)


def _classificar_e_transformar(df: pd.DataFrame, tipo: str, dic_areas: dict,
                                dic_colab: dict, dic_ind: dict, config: Path,
                                avisos: list = None) -> pd.DataFrame:
    if avisos is None:
        avisos = []

    # Derivar Código do Indicador * do Código da Meta * se não mapeado na fonte
    if "Código da Meta *" in df.columns:
        if "Código do Indicador *" not in df.columns or df["Código do Indicador *"].isna().all():
            df["Código do Indicador *"] = df["Código da Meta *"].copy()
            avisos.append(
                "'Código do Indicador *' derivado 1:1 do código da meta "
                "(sem fonte de indicadores na base do cliente)."
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

    # Pilar estratégico: de-para manual opcional + código padrão de cadastro da plataforma
    if tipo in ("individual", "projeto"):
        col_pilar = "Código do Pilar Estratégico *"
        dic_pilares = _carregar_dic(config / "dicionario_pilares.csv")
        if dic_pilares and col_pilar in df.columns:
            res = aplicar_dicionario.aplicar(df, dic_pilares, [col_pilar], ausentes="manter")
            df = res["dados"]["dataframe"]
            avisos.append("De-para manual de pilares aplicado (config/dicionario_pilares.csv).")
        if col_pilar not in df.columns or df[col_pilar].isna().all():
            df[col_pilar] = "DZ001"
            avisos.append(f"'{col_pilar}' preenchido com padrão: DZ001 (código padrão de cadastro).")

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
