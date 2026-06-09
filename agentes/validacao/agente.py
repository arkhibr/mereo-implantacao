"""
Agente de Validação
Valida todos os arquivos de staging contra os templates e gera o output final.
"""
import json
import shutil
import pandas as pd
from pathlib import Path
from datetime import date
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ferramentas.exportacao import validar_schema, validar_referencias
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

    # Copiar para output se aprovado
    if status_geral == "aprovado":
        data_hoje = date.today().isoformat()
        output = base / "output" / data_hoje
        output.mkdir(parents=True, exist_ok=True)
        # BOM UTF-8: o Excel só abre os CSVs corretamente com BOM —
        # sem ele os acentos viram mojibake (CÃ³digo, Ãrea etc).
        BOM = b"\xef\xbb\xbf"
        for staging_rel, (nome_template, _) in STAGING_PARA_TEMPLATE.items():
            src = base / staging_rel
            if src.exists():
                dados = src.read_bytes()
                if not dados.startswith(BOM):
                    dados = BOM + dados
                (output / nome_template).write_bytes(dados)
        resultado["dados"]["output_gerado"] = str(output)
        resultado["avisos"].append(f"Arquivos copiados para output/{data_hoje}/")
    else:
        resultado["status"] = "erro"
        nomes = [r["entidade"] for r in bloqueados]
        resultado["erros"].append(f"{len(bloqueados)} entidade(s) bloqueada(s): {nomes}. Corrigir antes de gerar output.")

    return resultado


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
