"""
Testes para a camada de agentes.
Execute com: python -m pytest testes/unitarios/test_agentes.py -v
"""
import json
import sys
import os
import pytest
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from agentes.metas        import agente as ag_metas
from agentes.mapeamento   import agente as ag_mapeamento
from agentes.curva_alcance import agente as ag_curva_alcance


# ── fixtures compartilhadas ───────────────────────────────────────────────────

@pytest.fixture
def cliente_dir(tmp_path):
    """Estrutura mínima de um cliente."""
    (tmp_path / "config").mkdir()
    (tmp_path / "relatorios").mkdir()
    return tmp_path


@pytest.fixture
def mapeamento_vazio(cliente_dir):
    """mapeamento.json sem travado, sem dados mapeados."""
    m = {
        "areas": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "colaboradores": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "indicadores": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "metas_individuais": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "metas_compartilhadas": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "metas_projeto": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "curva_alcance": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "valores_previstos": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        "valores_realizados": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
    }
    (cliente_dir / "config" / "mapeamento.json").write_text(
        json.dumps(m), encoding="utf-8"
    )
    return m


# ── metas: email → login ──────────────────────────────────────────────────────

class TestMetasEmailLogin:

    def _transformar(self, df, tmp_path):
        return ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)

    def test_email_minusculo_extraido(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Login do Responsável pela Meta *": ["fsilva@mereo.com.br"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Login do Responsável pela Meta *"].iloc[0] == "fsilva"

    def test_email_maiusculo_normalizado(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Login do Responsável pela Meta *": ["TBARRETO@mereo.COM.BR"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Login do Responsável pela Meta *"].iloc[0] == "tbarreto"

    def test_login_sem_arroba_preservado(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Login do Responsável pela Meta *": ["fsilva"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Login do Responsável pela Meta *"].iloc[0] == "fsilva"

    def test_data_provider_tambem_convertido(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Login do Data-Provider *": ["nfinotti@mereo.com.br"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Login do Data-Provider *"].iloc[0] == "nfinotti"

    def test_nulo_preservado(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Login do Responsável pela Meta *": [None],
        })
        r = self._transformar(df, tmp_path)
        assert pd.isna(r["Login do Responsável pela Meta *"].iloc[0])


# ── metas: peso slash-separado ────────────────────────────────────────────────

class TestMetasPeso:

    def _transformar(self, df, tmp_path):
        return ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)

    def test_peso_numerico_simples(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["M01"], "Peso da Meta *": ["20.0"]})
        r = self._transformar(df, tmp_path)
        assert r["Peso da Meta *"].iloc[0] == 20.0

    def test_peso_inteiro(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["M01"], "Peso da Meta *": ["35"]})
        r = self._transformar(df, tmp_path)
        assert r["Peso da Meta *"].iloc[0] == 35.0

    def test_peso_slash_extrai_primeiro(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["M01"], "Peso da Meta *": ["40 / 10 / 10 / 10"]})
        r = self._transformar(df, tmp_path)
        assert r["Peso da Meta *"].iloc[0] == 40.0

    def test_peso_nulo_permanece_nulo(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["M01"], "Peso da Meta *": [None]})
        r = self._transformar(df, tmp_path)
        assert pd.isna(r["Peso da Meta *"].iloc[0])


# ── metas: derivação do indicador ────────────────────────────────────────────

class TestMetasIndicadorDerivado:

    def _transformar(self, df, tmp_path):
        return ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)

    def test_indicador_derivado_quando_ausente(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["FIN01", "FIN02"]})
        r = self._transformar(df, tmp_path)
        assert "Código do Indicador *" in r.columns
        assert r["Código do Indicador *"].iloc[0] == "FIN01"
        assert r["Código do Indicador *"].iloc[1] == "FIN02"

    def test_indicador_derivado_quando_todos_nulos(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["FIN01"],
            "Código do Indicador *": [None],
        })
        r = self._transformar(df, tmp_path)
        assert r["Código do Indicador *"].iloc[0] == "FIN01"

    def test_indicador_existente_nao_sobrescrito(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["FIN01"],
            "Código do Indicador *": ["IND_PROPRIO"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Código do Indicador *"].iloc[0] == "IND_PROPRIO"


# ── metas: default tipo de definição ─────────────────────────────────────────

class TestMetasTipoDefinicao:

    def _transformar(self, df, tmp_path):
        return ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)

    def test_tipo_definicao_preenchido_quando_ausente(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["M01"]})
        r = self._transformar(df, tmp_path)
        assert r["Tipo de Definição do Valor *"].iloc[0] == "Manual"

    def test_tipo_definicao_existente_preservado(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Tipo de Definição do Valor *": ["Fórmula"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Tipo de Definição do Valor *"].iloc[0] == "Fórmula"


# ── mapeamento: flag travado ──────────────────────────────────────────────────

class TestMapeamentoTravado:

    def _diagnostico_vazio(self, config_dir):
        (config_dir / "diagnostico.json").write_text("[]", encoding="utf-8")

    def test_travado_preserva_arquivo(self, cliente_dir):
        config = cliente_dir / "config"
        self._diagnostico_vazio(config)
        original = {"travado": True, "areas": {"campos": [], "arquivo_sugerido": "ORIGINAL", "aba_sugerida": None}}
        (config / "mapeamento.json").write_text(json.dumps(original), encoding="utf-8")

        resultado = ag_mapeamento.executar(str(cliente_dir))

        assert resultado["status"] == "aviso"
        assert any("travado" in av for av in resultado["avisos"])
        conteudo = json.loads((config / "mapeamento.json").read_text(encoding="utf-8"))
        assert conteudo["areas"]["arquivo_sugerido"] == "ORIGINAL"

    def test_sem_travado_sobrescreve(self, cliente_dir):
        config = cliente_dir / "config"
        self._diagnostico_vazio(config)
        antigo = {"areas": {"campos": [], "arquivo_sugerido": "ANTIGO", "aba_sugerida": None}}
        (config / "mapeamento.json").write_text(json.dumps(antigo), encoding="utf-8")

        ag_mapeamento.executar(str(cliente_dir))

        conteudo = json.loads((config / "mapeamento.json").read_text(encoding="utf-8"))
        assert conteudo.get("areas", {}).get("arquivo_sugerido") != "ANTIGO"

    def test_travado_false_sobrescreve(self, cliente_dir):
        config = cliente_dir / "config"
        self._diagnostico_vazio(config)
        antigo = {"travado": False, "areas": {"campos": [], "arquivo_sugerido": "ANTIGO", "aba_sugerida": None}}
        (config / "mapeamento.json").write_text(json.dumps(antigo), encoding="utf-8")

        resultado = ag_mapeamento.executar(str(cliente_dir))

        assert resultado["status"] in ("ok", "aviso")
        conteudo = json.loads((config / "mapeamento.json").read_text(encoding="utf-8"))
        assert conteudo.get("areas", {}).get("arquivo_sugerido") != "ANTIGO"


# ── curva_alcance: null handling ──────────────────────────────────────────────

class TestCurvaAlcanceNullArquivo:

    def test_null_arquivo_retorna_aviso(self, cliente_dir, mapeamento_vazio):
        resultado = ag_curva_alcance.executar(str(cliente_dir))
        assert resultado["status"] == "ok"
        assert any("não mapeados" in av for av in resultado["avisos"])

    def test_arquivo_inexistente_retorna_erro(self, cliente_dir):
        m = {"curva_alcance": {"campos": [], "arquivo_sugerido": "raw/nao_existe.xlsx", "aba_sugerida": "CURVA"}}
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")

        resultado = ag_curva_alcance.executar(str(cliente_dir))
        assert resultado["status"] == "erro"

    def test_sem_mapeamento_retorna_erro(self, cliente_dir):
        resultado = ag_curva_alcance.executar(str(cliente_dir))
        assert resultado["status"] == "erro"


# ── validacao: referencial bloqueia ──────────────────────────────────────────

class TestValidacaoReferencial:

    def _setup_staging(self, tmp_path, areas_df, colab_df, metas_df):
        for subdir, nome, df in [
            ("01_areas", "areas_transformadas.csv", areas_df),
            ("02_colaboradores", "colaboradores_transformados.csv", colab_df),
            ("04_metas_individuais", "metas_individual_transformadas.csv", metas_df),
        ]:
            d = tmp_path / "staging" / subdir
            d.mkdir(parents=True)
            df.to_csv(d / nome, sep=";", index=False, encoding="utf-8")
        (tmp_path / "relatorios").mkdir(exist_ok=True)
        (tmp_path / "config").mkdir(exist_ok=True)

    def _areas(self):
        return pd.DataFrame({"Código da Área*": ["AREA_01", "AREA_02"]})

    def _colab(self):
        return pd.DataFrame({
            "Login*": ["joao", "maria"],
            "Código da Área*": ["AREA_01", "AREA_02"],
        })

    def _metas_validas(self):
        return pd.DataFrame({
            "Código da Meta *":                ["METI_01"],
            "Código da Área *":                ["AREA_01"],
            "Login do Responsável pela Meta *": ["joao"],
            "Objetivo da Meta *":              ["Crescer"],
            "Peso da Meta *":                  ["20"],
            "Tipo de Agregação *":             ["Media"],
            "Tipo de Definição do Valor *":    ["Manual"],
        })

    def test_area_invalida_bloqueia_referencial(self, tmp_path):
        from agentes.validacao import agente as ag_validacao

        metas = self._metas_validas()
        metas["Código da Área *"] = ["AREA_INEXISTENTE"]
        self._setup_staging(tmp_path, self._areas(), self._colab(), metas)

        resultado = ag_validacao.executar(str(tmp_path), pasta_templates=str(tmp_path / "_sem_templates"))
        resumo = resultado["dados"]["resumo"]
        ref = next((r for r in resumo if r["entidade"] == "referencial"), None)
        assert ref is not None, "entrada 'referencial' deve aparecer no resumo"
        assert ref["status"] == "bloqueado"

    def test_login_invalido_bloqueia_referencial(self, tmp_path):
        from agentes.validacao import agente as ag_validacao

        metas = self._metas_validas()
        metas["Login do Responsável pela Meta *"] = ["LOGIN_INEXISTENTE"]
        self._setup_staging(tmp_path, self._areas(), self._colab(), metas)

        resultado = ag_validacao.executar(str(tmp_path), pasta_templates=str(tmp_path / "_sem_templates"))
        resumo = resultado["dados"]["resumo"]
        ref = next((r for r in resumo if r["entidade"] == "referencial"), None)
        assert ref is not None
        assert ref["status"] == "bloqueado"

    def test_referencias_validas_nao_bloqueiam(self, tmp_path):
        from agentes.validacao import agente as ag_validacao

        self._setup_staging(tmp_path, self._areas(), self._colab(), self._metas_validas())

        resultado = ag_validacao.executar(str(tmp_path), pasta_templates=str(tmp_path / "_sem_templates"))
        resumo = resultado["dados"]["resumo"]
        bloqueados = [r["entidade"] for r in resumo if r["status"] == "bloqueado"]
        assert "referencial" not in bloqueados
