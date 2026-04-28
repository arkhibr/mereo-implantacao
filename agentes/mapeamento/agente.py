"""
Agente de Mapeamento
Constrói a ponte semântica entre o esquema do cliente e os templates da plataforma.
Produz config/mapeamento.json com mapeamento campo a campo por entidade.
"""
import json
from pathlib import Path
from difflib import SequenceMatcher
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

# Dicionário de sinônimos semânticos por campo do template.
# As chaves devem ser EXATAMENTE iguais aos nomes de coluna dos templates CSV
# (incluindo espaços antes de * em metas e indicadores).
SINONIMOS = {
    # ── Áreas (sem espaço antes de *) ────────────────────────────────────────
    "Código da Área*":             ["cod_area", "area_cod", "codigo_area", "id_area", "area_id",
                                    "cod_setor", "setor_cod", "cód. da área", "cod. da area"],
    "Descrição da Área*":          ["nome_area", "desc_area", "descricao_area", "area", "setor",
                                    "departamento", "descrição da área", "descricao da area"],
    "Código da Área Superior":     ["area_pai", "cod_pai", "superior", "area_superior",
                                    "hierarquia_pai", "cód. da área sup.", "cod. da area sup."],
    # ── Colaboradores (sem espaço antes de *) ────────────────────────────────
    "Login*":                      ["login", "usuario", "user", "cod_usuario", "cod_colaborador",
                                    "matricula", "login_ad", "login com usuário e senha"],
    "Nome completo*":              ["nome", "nome_completo", "colaborador", "funcionario",
                                    "empregado", "nome completo do colaborador"],
    "E-mail*":                     ["email", "e_mail", "email_corporativo", "email_trabalho",
                                    "mail", "e-mail"],
    "Código do Grupo de Permissões*": ["grupo_permissoes", "permissao", "perfil",
                                       "permissão de acesso", "grupo de acesso"],
    "Código da Filial*":           ["filial", "cod_filial", "empresa", "unidade"],
    # ── Indicadores (COM espaço antes de *) ──────────────────────────────────
    "Código do Indicador *":       ["cod_indicador", "indicador_cod", "id_kpi", "kpi_id",
                                    "cod_kpi", "indicador", "código do indicador"],
    "Descrição do Indicador *":    ["nome_indicador", "kpi", "nome_kpi", "descricao_kpi",
                                    "descrição do indicador", "nome do indicador"],
    "Polaridade *":                ["polaridade", "sentido", "direcao", "tipo_meta",
                                    "melhor para cima", "melhor para baixo"],
    "Ativo *":                     ["ativo", "status", "situacao", "ativo sim nao"],
    # ── Metas (COM espaço antes de *) ────────────────────────────────────────
    "Código da Meta *":            ["cod_meta", "meta_cod", "id_meta", "meta_id",
                                    "cód. da meta", "código da meta"],
    "Código da Área *":            ["cod_area_meta", "area_meta", "área da meta",
                                    "area da meta", "cód. da área da meta"],
    "Login do Responsável pela Meta *": ["responsavel", "login_responsavel", "gestor",
                                          "owner", "login do responsável",
                                          "login do responsável pela meta"],
    "Login do Data-Provider *":    ["data_provider", "dataprovider", "provedor",
                                    "login dataprovider", "data provider"],
    "Objetivo da Meta *":          ["objetivo", "descricao_meta", "nome_meta", "meta",
                                    "descrição da meta", "descrição da meta*"],
    "Peso da Meta *":              ["peso", "weight", "ponderacao", "percentual_peso",
                                    "peso (%)*", "peso (%)"],
    "Tipo de Agregação *":         ["tipo_acumulacao", "acumulacao", "tipo de acumulação",
                                    "tipo de acumulação*"],
    "Código do Pilar Estratégico *": ["pilar", "pilar_estrategico", "pilar estratégico",
                                      "pilar estratégico*"],
}

TRANSFORMACOES_PADRAO = {
    # Áreas
    "Código da Área*":             "recodificacao",
    "Código da Área Superior":     "recodificacao",
    # Colaboradores
    "Login*":                      "recodificacao",
    "Ativo*":                      "normalizar_dominio",
    # Indicadores
    "Código do Indicador *":       "recodificacao",
    "Polaridade *":                "normalizar_dominio",
    "Ativo *":                     "normalizar_dominio",
    # Metas
    "Código da Meta *":            "recodificacao",
    "Código da Área *":            "recodificacao",
    # Curva (sem espaço — template é diferente)
    "Código da Meta*":             "recodificacao",
}


def executar(pasta_cliente: str, pasta_templates: str = None) -> dict:
    resultado = {"status": "ok", "agente": "mapeamento", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    config = base / "config"
    templates_path = Path(pasta_templates) if pasta_templates else TEMPLATES_DIR

    caminho_diag = config / "diagnostico.json"
    if not caminho_diag.exists():
        resultado["status"] = "erro"
        resultado["erros"].append("diagnostico.json não encontrado. Execute o Agente de Diagnóstico primeiro.")
        return resultado

    with open(caminho_diag, encoding="utf-8") as f:
        diagnostico = json.load(f)

    colunas_cliente = _extrair_colunas(diagnostico)
    templates = _carregar_templates(templates_path)

    mapeamento = {}
    duvidas = []

    for entidade, campos_template in templates.items():
        mapeamento[entidade] = {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None}
        arquivo_sugerido, aba_sugerida = _sugerir_fonte(entidade, colunas_cliente)
        mapeamento[entidade]["arquivo_sugerido"] = arquivo_sugerido
        mapeamento[entidade]["aba_sugerida"] = aba_sugerida

        colunas_disponiveis = colunas_cliente.get(arquivo_sugerido, {}).get(aba_sugerida, []) if arquivo_sugerido else []

        for campo_tmpl in campos_template:
            obrigatorio = campo_tmpl.endswith("*")
            melhor = _encontrar_melhor_correspondencia(campo_tmpl, colunas_disponiveis)
            transformacao = TRANSFORMACOES_PADRAO.get(campo_tmpl, "direto")

            entrada = {
                "campo_template": campo_tmpl,
                "obrigatorio": obrigatorio,
                "campo_cliente": melhor["campo"] if melhor else None,
                "confianca": melhor["confianca"] if melhor else "nenhuma",
                "transformacao": transformacao,
                "observacao": "",
            }

            if obrigatorio and not melhor:
                duvidas.append({
                    "entidade": entidade,
                    "campo_template": campo_tmpl,
                    "problema": "campo obrigatório sem correspondência identificada",
                })

            if melhor and melhor["score"] < 0.5:
                entrada["observacao"] = "⚠️ baixa confiança — revisar manualmente"

            mapeamento[entidade]["campos"].append(entrada)

    resultado["dados"]["mapeamento"] = mapeamento
    resultado["dados"]["duvidas"] = duvidas
    resultado["dados"]["total_duvidas"] = len(duvidas)

    caminho_map = config / "mapeamento.json"
    if caminho_map.exists():
        with open(caminho_map, encoding="utf-8") as f:
            existente = json.load(f)
        if existente.get("travado"):
            resultado["status"] = "aviso"
            resultado["avisos"].append(
                "mapeamento.json está travado ('travado': true) — não foi sobrescrito. "
                "Remova o flag para regenerar automaticamente."
            )
            resultado["dados"]["arquivo_gerado"] = str(caminho_map)
            return resultado

    with open(caminho_map, "w", encoding="utf-8") as f:
        json.dump(mapeamento, f, ensure_ascii=False, indent=2)

    if duvidas:
        resultado["status"] = "aviso"
        resultado["avisos"].append(
            f"{len(duvidas)} campo(s) obrigatório(s) sem correspondência. Revisar mapeamento.json."
        )

    resultado["dados"]["arquivo_gerado"] = str(caminho_map)
    return resultado


# ── helpers privados ──────────────────────────────────────────────────────────

def _extrair_colunas(diagnostico: list) -> dict:
    """Extrai {arquivo: {aba: [colunas]}} do diagnóstico."""
    estrutura = {}
    for entrada in diagnostico:
        arq = entrada.get("arquivo", "")
        estrutura[arq] = {}
        for aba in entrada.get("perfil", {}).get("abas", []):
            cols = [c["nome"] for c in aba.get("colunas", [])]
            estrutura[arq][aba["nome"]] = cols
    return estrutura


def _carregar_templates(pasta: Path) -> dict:
    """Carrega os nomes de colunas de cada template CSV."""
    templates = {}
    mapa_nomes = {
        "Import_Áreas (Estrutura Hierárquica).csv": "areas",
        "Import_Colaboradores.csv": "colaboradores",
        "Import_Indicadores (KPI).csv": "indicadores",
        "Import_Metas Individuais.csv": "metas_individuais",
        "Import_Metas Compartilhadas.csv": "metas_compartilhadas",
        "Import_Metas Projeto.csv": "metas_projeto",
        "Import_Curva de Alcance.csv": "curva_alcance",
    }
    for nome_arquivo, chave in mapa_nomes.items():
        caminho = pasta / nome_arquivo
        if caminho.exists():
            import pandas as pd
            df = pd.read_csv(str(caminho), sep=";", nrows=0, encoding="latin-1")
            templates[chave] = list(df.columns)
    return templates


def _sugerir_fonte(entidade: str, colunas_cliente: dict) -> tuple:
    """Heurística simples: tenta encontrar o arquivo/aba mais provável para a entidade."""
    palavras_chave = {
        "areas":               ["hierarquia", "area", "setor", "estrutura"],
        "colaboradores":       ["colaborador", "empregado", "funcionario", "pessoa", "usuario"],
        "indicadores":         ["indicador", "kpi", "metrica"],
        "metas_individuais":   ["meta", "individual", "objetivo"],
        "metas_compartilhadas":["compartilhada", "composta", "holding"],
        "metas_projeto":       ["projeto", "entregavel"],
        "curva_alcance":       ["curva", "alcance", "nota", "faixa"],
    }
    palavras = palavras_chave.get(entidade, [entidade])

    melhor_arquivo = None
    melhor_aba = None
    melhor_score = 0

    for arquivo, abas in colunas_cliente.items():
        nome_arquivo = arquivo.lower()
        for aba, _ in abas.items():
            nome_aba = aba.lower()
            score = sum(1 for p in palavras if p in nome_arquivo or p in nome_aba)
            if score > melhor_score:
                melhor_score = score
                melhor_arquivo = arquivo
                melhor_aba = aba

    return melhor_arquivo, melhor_aba


def _encontrar_melhor_correspondencia(campo_template: str, colunas_disponiveis: list) -> dict:
    """Encontra a melhor correspondência por similaridade e sinônimos."""
    if not colunas_disponiveis:
        return None

    nome_limpo = campo_template.rstrip("*").strip().lower()
    sinonimos = [s.lower() for s in SINONIMOS.get(campo_template, [])]

    melhor = None
    melhor_score = 0

    for col in colunas_disponiveis:
        col_lower = str(col).lower()

        # Correspondência exata por sinônimo
        if col_lower in sinonimos:
            return {"campo": col, "score": 1.0, "confianca": "alta"}

        # Similaridade de string
        score = SequenceMatcher(None, nome_limpo, col_lower).ratio()

        # Boost se a coluna contém palavras do campo template
        palavras_tmpl = set(nome_limpo.split())
        palavras_col = set(col_lower.split("_"))
        overlap = len(palavras_tmpl & palavras_col) / max(len(palavras_tmpl), 1)
        score = max(score, overlap * 0.8)

        if score > melhor_score:
            melhor_score = score
            confianca = "alta" if score >= 0.8 else "media" if score >= 0.5 else "baixa"
            melhor = {"campo": col, "score": round(score, 3), "confianca": confianca}

    return melhor if melhor_score > 0.3 else None
