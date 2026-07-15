"""
Testes da detecção de periodicidade e do fluxo frequência/valores/validação.
Critério (aprovado 15/07/2026): 1 valor no ano = anual (8), 2+ = mensal (1).
Execute com: python -m pytest testes/unitarios/test_periodicidade.py -v
"""
import json
import sys
import os
import pytest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ferramentas.transformacao import periodicidade
from agentes.metas import agente as ag_metas
from agentes.valores import agente as ag_valores


@pytest.fixture
def cliente_dir(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "relatorios").mkdir()
    return tmp_path


# ── ferramenta: detecção de colunas de período e frequência ──────────────────

class TestFerramentaPeriodicidade:

    def test_interpretar_rotulos(self):
        assert periodicidade.interpretar_periodo("01/2026") == (1, 2026)
        assert periodicidade.interpretar_periodo("2026-03") == (3, 2026)
        assert periodicidade.interpretar_periodo("Jan") == (1, None)
        assert periodicidade.interpretar_periodo("dezembro/2025") == (12, 2025)
        assert periodicidade.interpretar_periodo(pd.Timestamp("2026-02-01")) == (2, 2026)
        assert periodicidade.interpretar_periodo("Peso da Meta *") is None

    def test_coluna_isolada_nao_conta_como_periodo(self):
        df = pd.DataFrame({"Código": ["M1"], "Mai": [10]})
        assert periodicidade.colunas_periodo(df) == {}

    def test_frequencia_mensal_e_anual(self):
        df = pd.DataFrame({
            "Código da Meta": ["FIN01", "ISO01"],
            "01/2026": [10, None],
            "02/2026": [12, None],
            "12/2026": [15, 100],
        })
        res = periodicidade.detectar_frequencias(df, "Código da Meta")
        assert res["dados"]["frequencias"] == {"FIN01": "1", "ISO01": "8"}

    def test_sem_colunas_periodo_devolve_vazio_com_aviso(self):
        df = pd.DataFrame({"Código da Meta": ["M1"], "Valor": [10]})
        res = periodicidade.detectar_frequencias(df, "Código da Meta")
        assert res["dados"]["frequencias"] == {}
        assert res["avisos"]


# ── metas: frequência detectada entra no indicador derivado ──────────────────

class TestMetasFrequenciaDetectada:

    def test_indicador_derivado_recebe_frequencia_dos_valores(self, cliente_dir):
        pd.DataFrame({
            "Código da Meta *": ["FIN01", "ISO01"],
            "Objetivo da Meta *": ["Faturar", "Certificar ISO"],
        }).to_csv(cliente_dir / "metas.csv", sep=";", index=False, encoding="utf-8")
        pd.DataFrame({
            "Código da Meta": ["FIN01", "ISO01"],
            "01/2026": [10, None],
            "02/2026": [12, None],
            "12/2026": [15, 1],
        }).to_csv(cliente_dir / "valores.csv", sep=";", index=False, encoding="utf-8")
        m = {
            "indicadores": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
            "metas_individuais": {"campos": [], "arquivo_sugerido": "metas.csv", "aba_sugerida": None},
            "metas_compartilhadas": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
            "metas_projeto": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None},
            "valores_previstos": {"campos": [], "arquivo_sugerido": "valores.csv", "aba_sugerida": None},
        }
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")

        res = ag_metas.executar(str(cliente_dir))
        df = pd.read_csv(cliente_dir / "staging/03_indicadores/indicadores_transformados.csv",
                         sep=";", encoding="utf-8-sig", dtype=str)
        freq = dict(zip(df["Código do Indicador *"], df["Código de Frequência de Acompanhamento *"]))
        assert freq == {"FIN01": "1", "ISO01": "8"}
        assert any("Periodicidade detectada" in av for av in res["avisos"])


# ── valores: layout do template ──────────────────────────────────────────────

class TestValoresLayout:

    def _rodar(self, cliente_dir, df_raw):
        df_raw.to_csv(cliente_dir / "valores.csv", sep=";", index=False, encoding="utf-8")
        m = {"valores_previstos": {"campos": [], "arquivo_sugerido": "valores.csv", "aba_sugerida": None},
             "valores_realizados": {"campos": [], "arquivo_sugerido": None, "aba_sugerida": None}}
        (cliente_dir / "config" / "mapeamento.json").write_text(json.dumps(m), encoding="utf-8")
        res = ag_valores.executar(str(cliente_dir))
        out = pd.read_csv(cliente_dir / "staging/08_valores_previstos/valores_previstos_transformados.csv",
                          sep=";", encoding="utf-8-sig", dtype=str)
        return out, res

    def test_colunas_ordenadas_no_formato_template(self, cliente_dir):
        out, _ = self._rodar(cliente_dir, pd.DataFrame({
            "Meta": ["FIN01"],
            "Fev/2026": [12],
            "01/2026": [10],
        }))
        assert list(out.columns) == ["Código da Meta", "Tipo de Valor", "01/2026", "02/2026"]
        assert out["Código da Meta"].iloc[0] == "FIN01"

    def test_mes_sem_ano_herda_ano_das_demais(self, cliente_dir):
        out, _ = self._rodar(cliente_dir, pd.DataFrame({
            "Meta": ["FIN01"],
            "Jan": [10],
            "02/2026": [12],
        }))
        assert "01/2026" in out.columns

    def test_fonte_sem_periodo_mantida_com_aviso(self, cliente_dir):
        out, res = self._rodar(cliente_dir, pd.DataFrame({
            "Meta": ["FIN01"],
            "Valor": [10],
        }))
        assert any("Nenhuma coluna de período" in av for av in res["avisos"])


# ── validação: consistência valores × frequência ─────────────────────────────

class TestValidacaoPeriodicidade:

    def _setup(self, tmp_path, freq_iso, valores_iso):
        from agentes.validacao import agente as ag_validacao
        stg = tmp_path / "staging"
        (stg / "03_indicadores").mkdir(parents=True)
        (stg / "04_metas_individuais").mkdir(parents=True)
        (stg / "08_valores_previstos").mkdir(parents=True)
        (tmp_path / "relatorios").mkdir(exist_ok=True)

        pd.DataFrame({
            "Código do Indicador *": ["ISO01"],
            "Código de Frequência de Acompanhamento *": [freq_iso],
        }).to_csv(stg / "03_indicadores/indicadores_transformados.csv",
                  sep=";", index=False, encoding="utf-8")
        pd.DataFrame({
            "Código da Meta *": ["ISO01"],
            "Código da Área *": ["1.1"],
            "Login do Responsável pela Meta *": ["joao"],
            "Código do Indicador *": ["ISO01"],
            "Código do Pilar Estratégico *": ["DZ001"],
            "Objetivo da Meta *": ["Certificar"],
            "Peso da Meta *": ["20"],
            "Tipo de Agregação *": ["1"],
            "Tipo de Definição do Valor *": ["1"],
        }).to_csv(stg / "04_metas_individuais/metas_individual_transformadas.csv",
                  sep=";", index=False, encoding="utf-8")
        pd.DataFrame({
            "Código da Meta": ["ISO01"],
            "Tipo de Valor": [""],
            "01/2026": [valores_iso[0]],
            "02/2026": [valores_iso[1]],
        }).to_csv(stg / "08_valores_previstos/valores_previstos_transformados.csv",
                  sep=";", index=False, encoding="utf-8")
        return ag_validacao.executar(str(tmp_path), pasta_templates=str(tmp_path / "_sem"))

    def test_indicador_anual_com_varios_valores_bloqueia(self, tmp_path):
        res = self._setup(tmp_path, "8", [10, 20])
        assert any(a["tipo"] == "periodicidade_inconsistente" for a in res["dados"]["achados"])
        per = next(r for r in res["dados"]["resumo"] if r["entidade"] == "periodicidade")
        assert per["status"] == "bloqueado"

    def test_indicador_anual_com_um_valor_passa(self, tmp_path):
        res = self._setup(tmp_path, "8", [10, None])
        assert not any(a.get("entidade") == "periodicidade" for a in res["dados"]["achados"])

    def test_mensal_com_um_valor_avisa_sem_bloquear(self, tmp_path):
        res = self._setup(tmp_path, "1", [10, None])
        per = next((r for r in res["dados"]["resumo"] if r["entidade"] == "periodicidade"), None)
        assert per is not None and per["status"] == "aviso"
