"""
Agente de Validação
Valida todos os arquivos de staging contra os templates e gera o output final.
"""
import json
import shutil
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.exportacao import validar_schema, validar_referencias, validar_codigos, exportar_output
from ferramentas.transformacao.dominios_plataforma import REGRAS_CODIGOS
from ferramentas.qualidade import duplicatas
from nucleo import templates as _tpl

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

STAGING_PARA_TEMPLATE = {
    "staging/01_areas/areas_transformadas.csv":
        ("Import_Áreas (Estrutura Hierárquica).csv", "areas"),
    "staging/02_colaboradores/colaboradores_transformados.csv":
        ("Import_Colaboradores.csv", "colaboradores"),
    "staging/03_indicadores/indicadores_transformados.csv":
        ("Import_Indicadores (KPI).csv", "indicadores"),
    "staging/04_metas_individuais/metas_individual_transformadas.csv":
        ("Import_Metas Individuais.csv", "metas_individuais"),
    "staging/05_metas_compartilhadas/metas_compartilhada_transformadas.csv":
        ("Import_Metas Compartilhadas.csv", "metas_compartilhadas"),
    "staging/06_metas_projeto/metas_projeto_transformadas.csv":
        ("Import_Metas Projeto.csv", "metas_projeto"),
    "staging/07_curva_alcance/curva_alcance_transformada.csv":
        ("Import_Curva de Alcance.csv", "curva_alcance"),
    "staging/08_competencias/competencias_transformadas.csv":
        ("Import_Competências (Catálogo).csv", "competencias"),
    "staging/09_formularios/formularios_transformados.csv":
        ("Import_Formulários de Avaliação.csv", "formularios"),
}

REFERENCIAS = [
    {"tabela_origem": "colaboradores", "coluna_fk": "Código da Área*",
     "tabela_destino": "areas",       "coluna_pk": "Código da Área*", "obrigatorio": True},
    {"tabela_origem": "metas_individuais", "coluna_fk": "Código da Área *",
     "tabela_destino": "areas",            "coluna_pk": "Código da Área*", "obrigatorio": True},
    {"tabela_origem": "metas_individuais", "coluna_fk": "Login do Responsável pela Meta *",
     "tabela_destino": "colaboradores",    "coluna_pk": "Login*", "obrigatorio": True},
    {"tabela_origem": "metas_individuais", "coluna_fk": "Código do Indicador *",
     "tabela_destino": "indicadores",      "coluna_pk": "Código do Indicador *", "obrigatorio": True},
    {"tabela_origem": "formularios", "coluna_fk": "Código da Competência",
     "tabela_destino": "competencias", "coluna_pk": "Código da Competência", "obrigatorio": True},
    {"tabela_origem": "formularios", "coluna_fk": "Código do Fator de Avaliação",
     "tabela_destino": "competencias", "coluna_pk": "Código do Fator de Avaliação", "obrigatorio": True},
]

CHAVES_UNICAS = {
    "areas":         "Código da Área*",
    "colaboradores": "Login*",
    "indicadores":   "Código do Indicador *",
    # No modelo fator-espelho cada competência tem um único fator → código único.
    "competencias":  "Código do Fator de Avaliação",
}


def executar(pasta_cliente: str, pasta_templates: str = None) -> dict:
    resultado = {"status": "ok", "agente": "validacao", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    templates_path = Path(pasta_templates) if pasta_templates else TEMPLATES_DIR
    relatorios = base / "relatorios"
    relatorios.mkdir(exist_ok=True)

    tabelas = {}
    resumo = []
    todos_achados = []

    for staging_rel, (nome_template, chave_tabela) in STAGING_PARA_TEMPLATE.items():
        caminho_staging = base / staging_rel
        if not caminho_staging.exists():
            resumo.append({"entidade": chave_tabela, "status": "ausente", "linhas": 0, "achados": 0})
            continue

        df = pd.read_csv(str(caminho_staging), sep=";", encoding="utf-8-sig", dtype=str)
        tabelas[chave_tabela] = df

        achados_entidade = []

        # Validação de schema
        caminho_tmpl = _tpl.localizar(templates_path, nome_template)
        if caminho_tmpl:
            schema = validar_schema.schema_do_template(str(caminho_tmpl))
            res_schema = validar_schema.validar(df, schema)
            achados_entidade.extend(res_schema["dados"]["achados"])

        # Validação de campos codificados (domínios e limites da plataforma)
        regras = REGRAS_CODIGOS.get(chave_tabela)
        if regras:
            res_cod = validar_codigos.validar(df, regras)
            achados_entidade.extend(res_cod["dados"]["achados"])

        # Validação de unicidade
        chave = CHAVES_UNICAS.get(chave_tabela)
        if chave and chave in df.columns:
            res_dup = duplicatas.detectar(df, [chave])
            if res_dup["dados"]["total_registros_afetados"] > 0:
                achados_entidade.append({
                    "severidade": "critico",
                    "tipo": "duplicata",
                    "coluna": chave,
                    "detalhe": f"{res_dup['dados']['total_registros_afetados']} registros duplicados",
                })

        status_ent = "ok"
        sev = {a["severidade"] for a in achados_entidade}
        if "critico" in sev or "alto" in sev:
            status_ent = "bloqueado"
        elif sev:
            status_ent = "aviso"

        resumo.append({
            "entidade": chave_tabela,
            "status": status_ent,
            "linhas": len(df),
            "achados": len(achados_entidade),
        })
        todos_achados.extend([{**a, "entidade": chave_tabela} for a in achados_entidade])

    # Validação referencial entre tabelas
    if len(tabelas) > 1:
        refs_aplicaveis = [
            r for r in REFERENCIAS
            if r["tabela_origem"] in tabelas and r["tabela_destino"] in tabelas
        ]
        if refs_aplicaveis:
            res_ref = validar_referencias.validar(tabelas, refs_aplicaveis)
            achados_ref = []
            for a in res_ref["dados"]["achados"]:
                coluna = f"{a.get('tabela_origem','')}.{a.get('coluna_fk','')}"
                exemplos = a.get("valores_invalidos", [])[:3]
                detalhe = f"{a.get('total_invalidas','')} ref. inválidas → {a.get('tabela_destino','')}.{a.get('coluna_pk','')} | ex: {exemplos}"
                achados_ref.append({**a, "entidade": "referencial", "coluna": coluna, "detalhe": detalhe})
            todos_achados.extend(achados_ref)

            sev_ref = {a["severidade"] for a in res_ref["dados"]["achados"]}
            if "critico" in sev_ref or "alto" in sev_ref:
                resumo.append({"entidade": "referencial", "status": "bloqueado",
                                "linhas": 0, "achados": len(achados_ref)})
            elif sev_ref:
                resumo.append({"entidade": "referencial", "status": "aviso",
                                "linhas": 0, "achados": len(achados_ref)})

    # Consistência de periodicidade: valores × frequência do indicador da meta
    achados_per = _validar_periodicidade(base, tabelas)
    if achados_per:
        todos_achados.extend(achados_per)
        sev_per = {a["severidade"] for a in achados_per}
        status_per = "bloqueado" if ("critico" in sev_per or "alto" in sev_per) else "aviso"
        resumo.append({"entidade": "periodicidade", "status": status_per,
                       "linhas": 0, "achados": len(achados_per)})

    # Decidir status geral
    bloqueados = [r for r in resumo if r["status"] == "bloqueado"]
    status_geral = "bloqueado" if bloqueados else "aprovado"

    resultado["dados"]["status_geral"] = status_geral
    resultado["dados"]["resumo"] = resumo
    resultado["dados"]["total_achados"] = len(todos_achados)
    resultado["dados"]["achados"] = todos_achados

    # Persistir relatório
    caminho_rel = relatorios / "relatorio_validacao.md"
    _salvar_relatorio_md(resumo, todos_achados, status_geral, caminho_rel)
    resultado["dados"]["relatorio"] = str(caminho_rel)

    # Exportar para output se aprovado (a plataforma importa .xlsx, não CSV)
    if status_geral == "aprovado":
        arquivos = {rel: nome for rel, (nome, _) in STAGING_PARA_TEMPLATE.items()}
        res_exp = exportar_output.exportar(base, arquivos)
        resultado["dados"]["output_gerado"] = res_exp["dados"]["diretorio_output"]
        resultado["avisos"].append(
            f"{len(res_exp['dados']['arquivos_gerados'])} planilha(s) .xlsx geradas em "
            f"output/{res_exp['dados']['data']}/"
        )
    else:
        resultado["status"] = "erro"
        nomes = [r["entidade"] for r in bloqueados]
        resultado["erros"].append(
            f"{len(bloqueados)} entidade(s) bloqueada(s): {nomes}. Corrigir antes de gerar output."
        )
        resultado["erros"].append(
            f"Detalhes dos achados: relatorios/relatorio_validacao.md — se o problema for "
            f"texto no lugar de código, crie um de-para: ./implantacao depara {base.name}"
        )

    return resultado


VALORES_STAGING = {
    "valores_previstos": "staging/08_valores_previstos/valores_previstos_transformados.csv",
    "valores_realizados": "staging/09_valores_realizados/valores_realizados_transformados.csv",
}


def _validar_periodicidade(base: Path, tabelas: dict) -> list:
    """
    Meta com indicador anual (frequência 8) deve ter no máximo 1 valor no ano;
    mais de um bloqueia. Mensal com 1 valor vira aviso (pode ser ano parcial).
    """
    from ferramentas.transformacao import periodicidade

    achados = []
    inds = tabelas.get("indicadores")
    if inds is None or "Código de Frequência de Acompanhamento *" not in inds.columns:
        return achados

    freq_por_ind = dict(zip(inds["Código do Indicador *"].astype(str),
                            inds["Código de Frequência de Acompanhamento *"].astype(str)))
    ind_por_meta = {}
    for chave in ["metas_individuais", "metas_projeto"]:
        metas = tabelas.get(chave)
        if metas is not None and "Código do Indicador *" in metas.columns:
            ind_por_meta.update(zip(metas["Código da Meta *"].astype(str),
                                    metas["Código do Indicador *"].astype(str)))
    if not ind_por_meta:
        return achados

    for tipo, rel in VALORES_STAGING.items():
        caminho = base / rel
        if not caminho.exists():
            continue
        df = pd.read_csv(str(caminho), sep=";", encoding="utf-8-sig", dtype=str)
        periodos = periodicidade.colunas_periodo(df)
        if not periodos or "Código da Meta" not in df.columns:
            continue

        anuais_estouradas, mensais_com_um = [], []
        for _, linha in df.iterrows():
            meta = str(linha["Código da Meta"]).strip()
            freq = freq_por_ind.get(ind_por_meta.get(meta, ""), None)
            if freq is None:
                continue
            preenchidos = sum(
                1 for c in periodos
                if pd.notna(linha[c]) and str(linha[c]).strip() != ""
            )
            if freq == periodicidade.FREQUENCIA_ANUAL and preenchidos > 1:
                anuais_estouradas.append(meta)
            elif freq == periodicidade.FREQUENCIA_MENSAL and preenchidos == 1:
                mensais_com_um.append(meta)

        if anuais_estouradas:
            achados.append({
                "entidade": "periodicidade", "severidade": "alto",
                "tipo": "periodicidade_inconsistente", "coluna": tipo,
                "detalhe": f"{len(anuais_estouradas)} meta(s) com indicador ANUAL e mais de "
                           f"um valor no ano. Ex: {anuais_estouradas[:3]}",
            })
        if mensais_com_um:
            achados.append({
                "entidade": "periodicidade", "severidade": "medio",
                "tipo": "periodicidade_suspeita", "coluna": tipo,
                "detalhe": f"{len(mensais_com_um)} meta(s) com indicador MENSAL e um único "
                           f"valor no ano (ano parcial?). Ex: {mensais_com_um[:3]}",
            })
    return achados


def _salvar_relatorio_md(resumo: list, achados: list, status_geral: str, caminho: Path):
    icone = "✅" if status_geral == "aprovado" else "❌"
    linhas = [f"# Relatório de Validação\n\n**Status geral: {icone} {status_geral.upper()}**\n\n## Resumo por entidade\n"]
    linhas.append("| Entidade | Linhas | Achados | Status |")
    linhas.append("|---|---|---|---|")
    for r in resumo:
        ic = "✅" if r["status"] == "ok" else ("⚠️" if r["status"] == "aviso" else ("—" if r["status"] == "ausente" else "❌"))
        linhas.append(f"| {r['entidade']} | {r['linhas']} | {r['achados']} | {ic} {r['status']} |")

    if achados:
        linhas.append("\n## Achados\n")
        linhas.append("| Entidade | Severidade | Tipo | Coluna | Detalhe |")
        linhas.append("|---|---|---|---|---|")
        for a in achados:
            linhas.append(f"| {a.get('entidade','')} | {a.get('severidade','')} | {a.get('tipo','')} | {a.get('coluna','')} | {a.get('detalhe','')} |")

    with open(caminho, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
