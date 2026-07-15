"""
Testes de sanidade para todas as 15 skills.
Execute com: .venv/bin/python -m pytest testes/unitarios/test_skills.py -v
"""
import sys
import os
import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ferramentas.ingestao import perfilamento, encoding
from ferramentas.qualidade import erros_planilha, duplicatas, pii
from ferramentas.codificacao import construir_dicionario, aplicar_dicionario
from ferramentas.transformacao import normalizar_dominio, converter_datas, agregar_pipe, quebrar_juntar
from ferramentas.hierarquia import validar_hierarquia, reconstruir_hierarquia
from ferramentas.exportacao import validar_schema, validar_referencias


# ── helpers ──────────────────────────────────────────────────────────────────

def df_areas():
    return pd.DataFrame({
        "codigo": ["A001", "A002", "A003"],
        "descricao": ["Diretoria", "Comercial", "TI"],
        "codigo_pai": [None, "A001", "A001"],
    })

def df_colaboradores():
    return pd.DataFrame({
        "Login*": ["joao.silva", "maria.lima", "pedro.souza"],
        "Nome completo*": ["João Silva", "Maria Lima", "Pedro Souza"],
        "E-mail*": ["joao@empresa.com", "maria@empresa.com", "ERRO"],
        "Código da Área*": ["A001", "A002", "A999"],  # A999 não existe
        "Ativo*": ["1", "1", "0"],
    })


# ── Wave 1: ingestao ─────────────────────────────────────────────────────────

def test_perfilamento_dataframe():
    df = df_areas()
    df.to_csv("/tmp/test_areas.csv", sep=";", index=False)
    res = perfilamento.perfil("/tmp/test_areas.csv")
    assert res["status"] == "ok"
    assert res["dados"]["total_abas"] == 1
    assert res["dados"]["abas"][0]["linhas"] == 3

def test_perfilamento_arquivo_inexistente():
    res = perfilamento.perfil("/tmp/nao_existe.csv")
    assert res["status"] == "erro"
    assert "não encontrado" in res["erros"][0]

def test_encoding_detectar(tmp_path):
    arq = tmp_path / "teste.txt"
    arq.write_bytes("Ação de coração".encode("windows-1252"))
    res = encoding.detectar(str(arq))
    assert res["status"] == "ok"
    assert res["dados"]["encoding_detectado"] is not None


# ── Wave 2: qualidade ─────────────────────────────────────────────────────────

def test_erros_planilha_detecta_na():
    df = pd.DataFrame({"col": ["#N/A", "ok", "#REF!"]})
    res = erros_planilha.diagnosticar(df)
    assert any(a["tipo"] == "erro_formula" for a in res["dados"]["achados"])

def test_erros_planilha_obrigatorio_vazio():
    df = pd.DataFrame({"Login*": ["joao", None, ""]})
    res = erros_planilha.diagnosticar(df, obrigatorios=["Login*"])
    assert any(a["tipo"] == "obrigatorio_vazio" for a in res["dados"]["achados"])

def test_duplicatas_detecta():
    df = pd.DataFrame({"id": ["A", "B", "A", "C"]})
    res = duplicatas.detectar(df, "id")
    assert res["status"] == "aviso"
    assert res["dados"]["total_registros_afetados"] == 2

def test_pii_detecta_cpf():
    df = pd.DataFrame({"documento": ["123.456.789-00", "987.654.321-11"]})
    res = pii.detectar(df)
    assert res["dados"]["total"] >= 1

def test_pii_detecta_nome_coluna():
    df = pd.DataFrame({"cpf_colaborador": ["abc", "def"]})
    res = pii.detectar(df)
    assert res["dados"]["total"] >= 1


# ── Wave 3: codificacao ───────────────────────────────────────────────────────

def test_construir_dicionario():
    res = construir_dicionario.construir(["001", "002", "003"], prefixo="AREA_")
    assert res["dados"]["total_entradas"] == 3
    assert res["dados"]["dicionario"][0]["id_destino"] == "AREA_001"

def test_aplicar_dicionario():
    df = pd.DataFrame({"area": ["001", "002", "999"]})
    mapa = {"001": "AREA_001", "002": "AREA_002"}
    res = aplicar_dicionario.aplicar(df, mapa, colunas=["area"], ausentes="manter")
    assert res["dados"]["dataframe"]["area"][0] == "AREA_001"
    assert res["dados"]["dataframe"]["area"][2] == "999"


# ── Wave 4: transformacao ─────────────────────────────────────────────────────

def test_normalizar_dominio():
    df = pd.DataFrame({"ativo": ["Sim", "S", "1", "Não", "N", "0"]})
    eq = {"1": ["Sim", "S", "sim", "s"], "0": ["Não", "N", "não", "n"]}
    res = normalizar_dominio.normalizar(df, "ativo", eq)
    assert list(res["dados"]["dataframe"]["ativo"]) == ["1", "1", "1", "0", "0", "0"]

def test_converter_datas_serial():
    df = pd.DataFrame({"data": [44197]})  # 2021-01-01
    res = converter_datas.converter(df, "data", "%d/%m/%Y")
    assert res["dados"]["dataframe"]["data"][0] == "01/01/2021"

def test_agregar_pipe():
    df = pd.DataFrame({
        "meta": ["M001", "M001", "M002"],
        "superior": ["S001", "S002", "S003"],
    })
    res = agregar_pipe.agregar(df, "meta", "superior")
    resultado = res["dados"]["dataframe"].set_index("meta")["superior"].to_dict()
    assert resultado["M001"] == "S001|S002"

def test_quebrar_campos():
    df = pd.DataFrame({"nome_area": ["João / TI", "Maria / RH"]})
    res = quebrar_juntar.quebrar(df, "nome_area", "/", ["nome", "area"])
    assert res["dados"]["dataframe"]["nome"][0] == "João"
    assert res["dados"]["dataframe"]["area"][0] == "TI"

def test_juntar_campos():
    df = pd.DataFrame({"nome": ["João"], "sobrenome": ["Silva"]})
    res = quebrar_juntar.juntar(df, ["nome", "sobrenome"], "nome_completo", " ")
    assert res["dados"]["dataframe"]["nome_completo"][0] == "João Silva"


# ── Wave 5: hierarquia ────────────────────────────────────────────────────────

def test_validar_hierarquia_ok():
    df = df_areas()
    res = validar_hierarquia.validar(df, "codigo", "codigo_pai")
    assert res["status"] == "ok"
    assert res["dados"]["total_ciclos"] == 0
    assert res["dados"]["total_orfaos"] == 0

def test_validar_hierarquia_ciclo():
    df = pd.DataFrame({
        "codigo": ["A", "B"],
        "codigo_pai": ["B", "A"],
    })
    res = validar_hierarquia.validar(df, "codigo", "codigo_pai")
    assert res["dados"]["total_ciclos"] > 0

def test_validar_hierarquia_orfao():
    df = pd.DataFrame({
        "codigo": ["A001", "A002"],
        "codigo_pai": [None, "A999"],
    })
    res = validar_hierarquia.validar(df, "codigo", "codigo_pai")
    assert res["dados"]["total_orfaos"] == 1

def test_reconstruir_hierarquia():
    df = pd.DataFrame({
        "dir": ["Comercial", "Comercial", "TI"],
        "ger": ["Vendas", "Marketing", "Infra"],
    })
    res = reconstruir_hierarquia.reconstruir(df, ["dir", "ger"])
    df_res = res["dados"]["dataframe"]
    assert len(df_res) == 5
    assert set(df_res["nivel"].tolist()) == {1, 2}


# ── Wave 6: exportacao ────────────────────────────────────────────────────────

def test_validar_schema_ok():
    df = pd.DataFrame({"Login*": ["joao"], "Nome completo*": ["João"]})
    schema = {"colunas": [
        {"nome": "Login*", "obrigatorio": True, "tipo": "texto"},
        {"nome": "Nome completo*", "obrigatorio": True, "tipo": "texto"},
    ]}
    res = validar_schema.validar(df, schema)
    assert res["status"] == "ok"

def test_validar_schema_obrigatorio_vazio():
    df = pd.DataFrame({"Login*": [None], "Nome completo*": ["João"]})
    schema = {"colunas": [
        {"nome": "Login*", "obrigatorio": True, "tipo": "texto"},
        {"nome": "Nome completo*", "obrigatorio": True, "tipo": "texto"},
    ]}
    res = validar_schema.validar(df, schema)
    assert res["status"] == "erro"

def test_validar_referencias_ok():
    areas = pd.DataFrame({"Código da Área*": ["A001", "A002"]})
    colab = pd.DataFrame({"Código da Área*": ["A001", "A002"]})
    refs = [{"tabela_origem": "colaboradores", "coluna_fk": "Código da Área*",
              "tabela_destino": "areas", "coluna_pk": "Código da Área*", "obrigatorio": True}]
    res = validar_referencias.validar({"areas": areas, "colaboradores": colab}, refs)
    assert res["status"] == "ok"

def test_validar_referencias_invalida():
    areas = pd.DataFrame({"Código da Área*": ["A001"]})
    colab = pd.DataFrame({"Código da Área*": ["A001", "A999"]})
    refs = [{"tabela_origem": "colaboradores", "coluna_fk": "Código da Área*",
              "tabela_destino": "areas", "coluna_pk": "Código da Área*", "obrigatorio": True}]
    res = validar_referencias.validar({"areas": areas, "colaboradores": colab}, refs)
    assert res["status"] == "erro"
    assert res["dados"]["achados"][0]["valores_invalidos"] == ["A999"]


# ── exportar_output ──────────────────────────────────────────────────────────

def test_exportar_output_gera_xlsx_com_nome_do_template(tmp_path):
    from ferramentas.exportacao import exportar_output

    staging = tmp_path / "staging" / "01_areas"
    staging.mkdir(parents=True)
    df = pd.DataFrame({"Código da Área*": ["A001"], "Status da Área": ["1"]})
    df.to_csv(staging / "areas_transformadas.csv", sep=";", index=False, encoding="utf-8-sig")

    res = exportar_output.exportar(tmp_path, {
        "staging/01_areas/areas_transformadas.csv": "Import_Áreas (Estrutura Hierárquica).csv",
    }, data="2026-07-15")

    destino = tmp_path / "output" / "2026-07-15" / "Import_Áreas (Estrutura Hierárquica).xlsx"
    assert destino.exists()
    assert res["dados"]["arquivos_gerados"] == ["Import_Áreas (Estrutura Hierárquica).xlsx"]

    lido = pd.read_excel(destino, sheet_name="Plan1", dtype=str)
    assert list(lido.columns) == ["Código da Área*", "Status da Área"]
    # códigos preservados como texto ("1" não vira 1.0)
    assert lido["Status da Área"].iloc[0] == "1"


def test_exportar_output_reporta_staging_ausente(tmp_path):
    from ferramentas.exportacao import exportar_output

    res = exportar_output.exportar(tmp_path, {
        "staging/01_areas/areas_transformadas.csv": "Import_Áreas (Estrutura Hierárquica).csv",
    })
    assert res["dados"]["arquivos_gerados"] == []
    assert res["dados"]["ausentes"] == ["Import_Áreas (Estrutura Hierárquica).csv"]
