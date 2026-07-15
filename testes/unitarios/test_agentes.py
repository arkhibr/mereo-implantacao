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
        assert r["Tipo de Definição do Valor *"].iloc[0] == "1"

    def test_tipo_definicao_texto_normalizado_para_codigo(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01", "M02"],
            "Tipo de Definição do Valor *": ["Manual", "Fórmula"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Tipo de Definição do Valor *"].tolist() == ["1", "2"]


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
            "Tipo de Agregação *":             ["3"],
            "Tipo de Definição do Valor *":    ["1"],
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


# ── códigos sem prefixo (o cliente manda o código, a plataforma não usa prefixo) ─

class TestCodigosSemPrefixo:

    def _rodar_areas(self, cliente_dir, df_raw):
        from agentes.areas import agente as ag_areas
        df_raw.to_csv(cliente_dir / "areas.csv", sep=";", index=False, encoding="utf-8")
        m = {"areas": {"campos": [], "arquivo_sugerido": "areas.csv", "aba_sugerida": None}}
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")
        res = ag_areas.executar(str(cliente_dir))
        df = pd.read_csv(cliente_dir / "staging/01_areas/areas_transformadas.csv",
                         sep=";", encoding="utf-8-sig", dtype=str)
        return df, res

    def test_area_sem_prefixo(self, cliente_dir):
        df, res = self._rodar_areas(cliente_dir, pd.DataFrame({
            "Código da Área*": ["1.1", "1.1.1"],
            "Descrição da Área*": ["Operações", "Logística"],
            "Código da Área Superior": [None, "1.1"],
        }))
        assert df["Código da Área*"].tolist() == ["1.1", "1.1.1"]
        assert df["Código da Área Superior"].iloc[1] == "1.1"
        # dicionário não é mais gerado
        assert not (cliente_dir / "config" / "dicionario_areas.csv").exists()

    def test_area_de_para_manual_aplicado(self, cliente_dir):
        (cliente_dir / "config" / "dicionario_areas.csv").write_text(
            "id_origem;id_destino\nDiretoria Comercial;1.2\n", encoding="utf-8")
        df, res = self._rodar_areas(cliente_dir, pd.DataFrame({
            "Código da Área*": ["Diretoria Comercial"],
            "Descrição da Área*": ["Comercial"],
        }))
        assert df["Código da Área*"].iloc[0] == "1.2"
        assert any("De-para manual" in av for av in res["avisos"])

    def test_meta_sem_prefixo(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["FIN01"]})
        r = ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)
        assert r["Código da Meta *"].iloc[0] == "FIN01"
        assert not (tmp_path / "dicionario_metas_individual.csv").exists()

    def test_meta_de_para_manual_aplicado(self, tmp_path):
        (tmp_path / "dicionario_metas_individual.csv").write_text(
            "id_origem;id_destino\nFIN01;MT_0001\n", encoding="utf-8")
        df = pd.DataFrame({"Código da Meta *": ["FIN01"]})
        r = ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)
        assert r["Código da Meta *"].iloc[0] == "MT_0001"

    def test_indicador_sem_prefixo(self, cliente_dir):
        from agentes.indicadores import agente as ag_ind
        pd.DataFrame({
            "Código do Indicador *": ["SLA01"],
            "Descrição do Indicador *": ["SLA"],
        }).to_csv(cliente_dir / "ind.csv", sep=";", index=False, encoding="utf-8")
        m = {"indicadores": {"campos": [], "arquivo_sugerido": "ind.csv", "aba_sugerida": None}}
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")
        res = ag_ind.executar(str(cliente_dir))
        assert res["status"] == "ok"
        df = pd.read_csv(cliente_dir / "staging/03_indicadores/indicadores_transformados.csv",
                         sep=";", encoding="utf-8-sig", dtype=str)
        assert df["Código do Indicador *"].iloc[0] == "SLA01"
        assert not (cliente_dir / "config" / "dicionario_indicadores.csv").exists()


# ── metas: pilar estratégico ─────────────────────────────────────────────────

class TestMetasPilar:

    def test_pilar_default_dz001_quando_ausente(self, tmp_path):
        avisos = []
        df = pd.DataFrame({"Código da Meta *": ["M01"]})
        r = ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path,
                                                avisos=avisos)
        assert r["Código do Pilar Estratégico *"].iloc[0] == "DZ001"
        assert any("DZ001" in av for av in avisos)

    def test_pilar_de_para_manual_aplicado(self, tmp_path):
        (tmp_path / "dicionario_pilares.csv").write_text(
            "id_origem;id_destino\nMetas Setoriais;DZ001\n", encoding="utf-8")
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Código do Pilar Estratégico *": ["Metas Setoriais"],
        })
        r = ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)
        assert r["Código do Pilar Estratégico *"].iloc[0] == "DZ001"

    def test_pilar_texto_sem_de_para_mantido(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Código do Pilar Estratégico *": ["Metas Setoriais"],
        })
        r = ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path)
        # mantém o texto — a validação de códigos bloqueia antes do output
        assert r["Código do Pilar Estratégico *"].iloc[0] == "Metas Setoriais"

    def test_pilar_nao_criado_em_compartilhada(self, tmp_path):
        df = pd.DataFrame({"Código da Meta *": ["M01"]})
        r = ag_metas._classificar_e_transformar(df, "compartilhada", {}, {}, {}, tmp_path)
        assert "Código do Pilar Estratégico *" not in r.columns


# ── colaboradores: grupo de permissões ───────────────────────────────────────

class TestColaboradoresGrupoPermissao:

    def _rodar(self, cliente_dir, df_raw):
        from agentes.colaboradores import agente as ag_colab
        df_raw.to_csv(cliente_dir / "colab.csv", sep=";", index=False, encoding="utf-8")
        m = {"colaboradores": {"campos": [], "arquivo_sugerido": "colab.csv", "aba_sugerida": None}}
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")
        res = ag_colab.executar(str(cliente_dir))
        df = pd.read_csv(cliente_dir / "staging/02_colaboradores/colaboradores_transformados.csv",
                         sep=";", encoding="utf-8-sig", dtype=str)
        return df, res

    def test_default_grp_4_quando_ausente(self, cliente_dir):
        df, res = self._rodar(cliente_dir, pd.DataFrame({
            "Login*": ["joao"], "Nome completo*": ["João"], "E-mail*": ["joao@x.com"],
        }))
        assert df["Código do Grupo de Permissões*"].iloc[0] == "GRP_4"

    def test_de_para_manual_aplicado(self, cliente_dir):
        (cliente_dir / "config" / "dicionario_grupos_permissao.csv").write_text(
            "id_origem;id_destino\nAdministrador Global;GRP_4\n", encoding="utf-8")
        df, res = self._rodar(cliente_dir, pd.DataFrame({
            "Login*": ["joao"], "Nome completo*": ["João"], "E-mail*": ["joao@x.com"],
            "Código do Grupo de Permissões*": ["Administrador Global"],
        }))
        assert df["Código do Grupo de Permissões*"].iloc[0] == "GRP_4"
        assert any("grupos de permissão" in av for av in res["avisos"])


# ── metas: geração de indicadores derivados ──────────────────────────────────

class TestMetasIndicadoresDerivadosStaging:

    def _rodar(self, cliente_dir, mapeamento_extra=None):
        df = pd.DataFrame({
            "Código da Meta *": ["FIN01", "FIN02"],
            "Objetivo da Meta *": ["Aumentar vendas em 10%", "Reduzir custo operacional"],
        })
        df.to_csv(cliente_dir / "metas.csv", sep=";", index=False, encoding="utf-8")
        m = {
            "indicadores": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
            "metas_individuais": {"campos": [], "arquivo_sugerido": "metas.csv", "aba_sugerida": None},
            "metas_compartilhadas": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
            "metas_projeto": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
        }
        if mapeamento_extra:
            m.update(mapeamento_extra)
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")
        return ag_metas.executar(str(cliente_dir))

    def test_staging_indicadores_gerado_1_para_1(self, cliente_dir):
        res = self._rodar(cliente_dir)
        caminho = cliente_dir / "staging/03_indicadores/indicadores_transformados.csv"
        assert caminho.exists()
        df = pd.read_csv(caminho, sep=";", encoding="utf-8-sig", dtype=str)
        assert df["Código do Indicador *"].tolist() == ["FIN01", "FIN02"]
        assert df["Descrição do Indicador *"].iloc[0] == "Aumentar vendas em 10%"
        # heurística de polaridade: vendas → maior melhor (1); custo → menor melhor (2)
        assert df["Polaridade *"].tolist() == ["1", "2"]
        assert df["Ativo *"].iloc[0] == "1"
        assert res["dados"]["contagens"]["indicadores_derivados"] == 2

    def test_nao_gera_quando_indicadores_mapeado(self, cliente_dir):
        res = self._rodar(cliente_dir, {"indicadores": {
            "campos": [], "arquivo_sugerido": "indicadores.csv", "aba_sugerida": None}})
        assert not (cliente_dir / "staging/03_indicadores/indicadores_transformados.csv").exists()


# ── áreas: login do responsável ──────────────────────────────────────────────

class TestAreasLoginResponsavel:

    def _rodar(self, cliente_dir, valores):
        from agentes.areas import agente as ag_areas
        df = pd.DataFrame({
            "Código da Área*": [f"A{i}" for i in range(len(valores))],
            "Descrição da Área*": ["X"] * len(valores),
            "Login Responsável da Área": valores,
        })
        df.to_csv(cliente_dir / "areas.csv", sep=";", index=False, encoding="utf-8")
        m = {"areas": {"campos": [], "arquivo_sugerido": "areas.csv", "aba_sugerida": None}}
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")
        res = ag_areas.executar(str(cliente_dir))
        out = pd.read_csv(cliente_dir / "staging/01_areas/areas_transformadas.csv",
                          sep=";", encoding="utf-8-sig", dtype=str, keep_default_na=False)
        return out["Login Responsável da Área"], res

    def test_email_vira_login(self, cliente_dir):
        logins, _ = self._rodar(cliente_dir, ["Maria.Santos@empresa.com.br"])
        assert logins.iloc[0] == "maria.santos"

    def test_nome_nao_vaza_fica_vazio_com_aviso(self, cliente_dir):
        logins, res = self._rodar(cliente_dir, ["Maria Silva Santos"])
        assert pd.isna(logins.iloc[0]) or str(logins.iloc[0]).strip() == ""
        assert any("sem login derivável" in av for av in res["avisos"])

    def test_null_literal_preservado(self, cliente_dir):
        # "null"/"NULL" viram NaN na leitura (na_values do pandas); só variantes
        # mistas como "Null" chegam ao agente — e devem sair como o literal NULL.
        logins, _ = self._rodar(cliente_dir, ["Null"])
        assert logins.iloc[0] == "NULL"

    def test_login_simples_normalizado(self, cliente_dir):
        logins, _ = self._rodar(cliente_dir, ["JSILVA"])
        assert logins.iloc[0] == "jsilva"

    def test_vazio_permanece_vazio(self, cliente_dir):
        logins, res = self._rodar(cliente_dir, [None])
        assert pd.isna(logins.iloc[0]) or str(logins.iloc[0]).strip() == ""
        assert not any("sem login derivável" in av for av in res["avisos"])
