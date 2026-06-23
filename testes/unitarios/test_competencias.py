"""
Testes do módulo de competências (ferramenta de matriz + agentes + validação).
Execute com: python -m pytest testes/unitarios/test_competencias.py -v
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ferramentas.transformacao import competencias_matriz as cm
from agentes.competencias import agente as ag_competencias
from agentes.formularios import agente as ag_formularios
from agentes.validacao import agente as ag_validacao

AMOSTRAS = Path(__file__).parent.parent / "amostras" / "competencias"
AGRO = str(AMOSTRAS / "matriz_cargo-x-competencia_belmont-agro.xlsx")
CORP = str(AMOSTRAS / "matriz_cargo-x-competencia_belmont-corporativo.xlsx")


# ── ferramenta pura ────────────────────────────────────────────────────────────

class TestExtracaoMatriz:

    def test_colunas_batem_com_templates(self):
        r = cm.extrair(AGRO)
        assert list(r["catalogo"][0].keys()) == cm.COLUNAS_CATALOGO
        assert list(r["formularios"][0].keys()) == cm.COLUNAS_FORMULARIO

    def test_fator_espelho_1_para_1(self):
        """Cada competência gera exatamente um fator (espelho de códigos 1:1)."""
        r = cm.extrair(AGRO)
        for linha in r["catalogo"]:
            assert linha["Código da Competência"].startswith("CPT")
            assert linha["Código do Fator de Avaliação"].startswith("FT")
            # mesmo índice no par CPT##/FT## (espelho)
            assert linha["Código da Competência"][3:] == linha["Código do Fator de Avaliação"][2:]
        # 1 linha por competência → códigos de competência únicos
        cpts = [l["Código da Competência"] for l in r["catalogo"]]
        assert len(cpts) == len(set(cpts))

    def test_posicionamento_do_conteudo_no_catalogo(self):
        """Feedback Mereo (2026-06-23): C vazia; F = definição da competência;
        G = comportamentos observáveis (≥1 nível concatenado)."""
        r = cm.extrair(CORP)
        comp = next(l for l in r["catalogo"] if l["Nome da competência"] == "Comprometimento")
        assert comp["Descrição da Competencia"] == ""
        assert comp["Nome do Fator de Avaliação"].startswith("Capacidade de cumprir")
        g = comp["Descrição do Fator de Avaliação"]
        assert g.strip() != ""
        # os 4 níveis da escala vêm empilhados numa célula
        assert len(g.split(cm.SEP_COMPORTAMENTOS)) == 4

    def test_peso_convertido_e_replicado_nos_avaliadores(self):
        r = cm.extrair(AGRO)
        # Comprometimento no Operacional: 0.2 → 20, em AUTO e LIDER; resto vazio.
        linha = next(l for l in r["formularios"]
                     if l["Descrição"] == "Operacional" and l["Código do Fator de Avaliação"] == "FT01")
        assert linha["AUTO"] == 20 and linha["LIDER"] == 20
        # avaliadores não usados vão 0 (obrigatório p/ importar), não vazio
        assert linha["PAR"] == 0 and linha["COMITÊ"] == 0 and linha["FORNECEDOR"] == 0

    def test_integridade_referencial_interna(self):
        """Todo fator citado nos formulários existe no catálogo."""
        r = cm.extrair(CORP)
        fatores_cat = {l["Código do Fator de Avaliação"] for l in r["catalogo"]}
        comps_cat = {l["Código da Competência"] for l in r["catalogo"]}
        for l in r["formularios"]:
            assert l["Código do Fator de Avaliação"] in fatores_cat
            assert l["Código da Competência"] in comps_cat

    def test_descricao_capturada_mesmo_com_aba_de_nome_divergente(self):
        """'Negociação' vive na aba 'Comprador e Controlador Manut.' (nome ≠ cargo
        'Comprador e Controlador de Manutenção'); definição e comportamentos ainda
        são capturados."""
        r = cm.extrair(CORP)
        neg = next(l for l in r["catalogo"] if l["Nome da competência"] == "Negociação")
        assert neg["Nome do Fator de Avaliação"].strip() != ""        # definição
        assert neg["Descrição do Fator de Avaliação"].strip() != ""   # comportamentos
        assert r["avisos"] == []  # sem competência órfã de definição/comportamentos

    def test_soma_de_pesos_por_cargo(self):
        r = cm.extrair(AGRO)
        for cargo, soma in r["somas"].items():
            assert abs(soma - 1.0) < 0.001, f"{cargo} soma {soma}"


# ── agentes (staging) ───────────────────────────────────────────────────────────

@pytest.fixture
def cliente(tmp_path):
    (tmp_path / "raw").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "relatorios").mkdir()
    import shutil
    shutil.copy(CORP, tmp_path / "raw" / "competencias.xlsx")
    (tmp_path / "config" / "mapeamento.json").write_text(
        json.dumps({"competencias": {"arquivo_sugerido": "raw/competencias.xlsx",
                                      "aba_sugerida": "Corporativo"}}),
        encoding="utf-8")
    return tmp_path


class TestAgentes:

    def test_competencias_gera_staging_e_dicionario(self, cliente):
        res = ag_competencias.executar(str(cliente))
        assert res["status"] == "ok"
        staging = cliente / "staging/08_competencias/competencias_transformadas.csv"
        dic = cliente / "config/dicionario_competencias.csv"
        assert staging.exists() and dic.exists()
        df = pd.read_csv(staging, sep=";", encoding="utf-8-sig")
        assert list(df.columns) == cm.COLUNAS_CATALOGO
        assert len(df) == res["dados"]["linhas_transformadas"]

    def test_formularios_gera_staging(self, cliente):
        res = ag_formularios.executar(str(cliente))
        assert res["status"] == "ok"
        staging = cliente / "staging/09_formularios/formularios_transformados.csv"
        assert staging.exists()
        df = pd.read_csv(staging, sep=";", encoding="utf-8-sig")
        assert list(df.columns) == cm.COLUNAS_FORMULARIO

    def test_erro_sem_entrada_no_mapeamento(self, tmp_path):
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "mapeamento.json").write_text("{}", encoding="utf-8")
        res = ag_competencias.executar(str(tmp_path))
        assert res["status"] == "erro"


# ── validação ────────────────────────────────────────────────────────────────────

class TestValidacao:

    def test_aprova_com_fk_integra(self, cliente):
        ag_competencias.executar(str(cliente))
        ag_formularios.executar(str(cliente))
        res = ag_validacao.executar(str(cliente))
        assert res["dados"]["status_geral"] == "aprovado"
        ents = {r["entidade"]: r for r in res["dados"]["resumo"]}
        assert ents["competencias"]["status"] == "ok"
        assert ents["formularios"]["status"] == "ok"

    def test_detecta_fk_orfa(self, cliente):
        """Formulário apontando para fator inexistente deve bloquear."""
        ag_competencias.executar(str(cliente))
        ag_formularios.executar(str(cliente))
        staging = cliente / "staging/09_formularios/formularios_transformados.csv"
        df = pd.read_csv(staging, sep=";", encoding="utf-8-sig", dtype=str)
        df.loc[0, "Código do Fator de Avaliação"] = "FT_INEXISTENTE"
        df.to_csv(staging, sep=";", index=False, encoding="utf-8-sig")
        res = ag_validacao.executar(str(cliente))
        assert res["dados"]["status_geral"] == "bloqueado"
