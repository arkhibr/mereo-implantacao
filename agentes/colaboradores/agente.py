"""
Agente de Colaboradores
Transforma o cadastro de pessoas para o template da plataforma.
"""
import json
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.codificacao import construir_dicionario, aplicar_dicionario
from ferramentas.transformacao import normalizar_dominio, quebrar_juntar
from ferramentas.qualidade import erros_planilha

TODOS_CAMPOS = [
    "Login*", "Nome completo*", "E-mail*", "Código do Grupo de Permissões*",
    "Código da Área*", "Código das Áreas sob sua Responsabilidade",
    "Idioma de interação com o usuário*", "Workflow de Ações*", "Ativo*",
    "Autenticação do Windows", "Tratativa de metas na movimentação",
    "Mover Responsável Área", "Tratativa das responsabilidades na inativação",
    "Localidade", "Matrícula",
]
CAMPOS_OBRIGATORIOS = [
    "Login*", "Nome completo*", "E-mail*", "Código do Grupo de Permissões*",
    "Código da Área*", "Idioma de interação com o usuário*", "Workflow de Ações*", "Ativo*",
]
EQUIVALENCIAS_ATIVO = {
    "1": ["1", "sim", "s", "ativo", "true", "yes", "y", "a"],
    "0": ["0", "nao", "não", "n", "inativo", "false", "no", "i"],
}
STAGING_DIR = "staging/02_colaboradores"


def executar(pasta_cliente: str, grupo_permissoes_padrao: str = "GRP_PADRAO",
             idioma_padrao: str = "1", workflow_padrao: str = "0") -> dict:
    resultado = {"status": "ok", "agente": "colaboradores", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"
    staging = base / STAGING_DIR
    staging.mkdir(parents=True, exist_ok=True)

    mapeamento = _carregar_mapeamento(config)
    if mapeamento is None:
        resultado["status"] = "erro"
        resultado["erros"].append("mapeamento.json não encontrado.")
        return resultado

    conf = mapeamento.get("colaboradores", {})
    arquivo = conf.get("arquivo_sugerido")
    if not arquivo:
        resultado["status"] = "erro"
        resultado["erros"].append("Dados de colaboradores não mapeados.")
        return resultado
    df_raw = _ler_dados(base / arquivo, conf.get("aba_sugerida"), conf.get("header_linha", 0))
    if df_raw is None:
        resultado["status"] = "erro"
        resultado["erros"].append("Dados de colaboradores não encontrados.")
        return resultado

    res_qual = erros_planilha.diagnosticar(df_raw)
    criticos = [a for a in res_qual["dados"]["achados"] if a["severidade"] == "critico"]
    if criticos:
        resultado["avisos"].append(f"{len(criticos)} problema(s) crítico(s) nos dados brutos.")

    df = _aplicar_mapeamento(df_raw, conf.get("campos", []))

    # Carregar dicionário de áreas gerado pelo Agente de Áreas
    dic_areas = _carregar_dicionario(config / "dicionario_areas.csv")
    if dic_areas and "Código da Área*" in df.columns:
        res = aplicar_dicionario.aplicar(df, dic_areas, ["Código da Área*", "Código das Áreas sob sua Responsabilidade"], ausentes="manter")
        df = res["dados"]["dataframe"]
        if res["avisos"]:
            resultado["avisos"].extend(res["avisos"])

    # Gerar login se ausente
    if "Login*" not in df.columns or df["Login*"].isna().all():
        if "Nome completo*" in df.columns:
            df["Login*"] = df["Nome completo*"].apply(_gerar_login)
            resultado["avisos"].append("Login gerado automaticamente a partir do nome.")

    # Normalizar login: lowercase + strip (garante consistência com outros agentes)
    if "Login*" in df.columns:
        df["Login*"] = df["Login*"].apply(
            lambda x: str(x).strip().lower() if pd.notna(x) else x
        )

    # Normalizar campo Ativo
    if "Ativo*" in df.columns:
        res = normalizar_dominio.normalizar(df, "Ativo*", EQUIVALENCIAS_ATIVO, padrao="1")
        df = res["dados"]["dataframe"]

    # Preencher campos obrigatórios com defaults quando ausentes
    defaults = {
        "Código do Grupo de Permissões*": grupo_permissoes_padrao,
        "Idioma de interação com o usuário*": idioma_padrao,
        "Workflow de Ações*": workflow_padrao,
        "Ativo*": "1",
    }
    for campo, valor in defaults.items():
        if campo not in df.columns:
            df[campo] = valor
            resultado["avisos"].append(f"'{campo}' preenchido com padrão: {valor}")
        elif df[campo].isna().any():
            n = int(df[campo].isna().sum())
            df[campo] = df[campo].fillna(valor)
            resultado["avisos"].append(f"'{campo}': {n} linha(s) preenchida(s) com padrão: {valor}")

    # Campos booleanos opcionais
    for campo in ["Autenticação do Windows", "Tratativa de metas na movimentação",
                  "Mover Responsável Área", "Tratativa das responsabilidades na inativação"]:
        if campo not in df.columns:
            df[campo] = "0"

    for col in TODOS_CAMPOS:
        if col not in df.columns:
            df[col] = ""
    df = df[TODOS_CAMPOS]

    caminho_out = staging / "colaboradores_transformados.csv"
    df.to_csv(str(caminho_out), sep=";", index=False, encoding="utf-8-sig")

    resultado["dados"]["linhas_transformadas"] = len(df)
    resultado["dados"]["arquivos_gerados"] = [str(caminho_out)]
    return resultado


def _gerar_login(nome_completo: str) -> str:
    if not nome_completo or pd.isna(nome_completo):
        return ""
    partes = str(nome_completo).strip().lower().split()
    partes = [p for p in partes if len(p) > 1]
    if len(partes) >= 2:
        return f"{partes[0]}.{partes[-1]}"
    return partes[0] if partes else ""


def _carregar_mapeamento(config: Path) -> dict:
    caminho = config / "mapeamento.json"
    if not caminho.exists():
        return None
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def _carregar_dicionario(caminho: Path) -> dict:
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
