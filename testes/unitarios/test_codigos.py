"""
Testes dos domínios oficiais da plataforma e da validação de campos codificados.
Fonte dos padrões: feedback/mereo/padroes_2026-07-15.xlsx.
Execute com: python -m pytest testes/unitarios/test_codigos.py -v
"""
import json
import sys
import os
import pytest
import pandas as pd
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ferramentas.exportacao import validar_codigos
from ferramentas.transformacao import dominios_plataforma as dom
from agentes.metas import agente as ag_metas


# ── ferramenta: validar_codigos ───────────────────────────────────────────────

class TestValidarCodigos:

    def test_dominio_invalido_e_critico(self):
        df = pd.DataFrame({"Polaridade *": ["1", "3", "nominal"]})
        res = validar_codigos.validar(df, {"Polaridade *": {"tipo": "dominio", "valores": {"1", "2"}}})
        achados = res["dados"]["achados"]
        assert len(achados) == 1
        assert achados[0]["severidade"] == "critico"
        assert achados[0]["tipo"] == "dominio_invalido"

    def test_dominio_valido_sem_achados(self):
        df = pd.DataFrame({"Polaridade *": ["1", "2"]})
        res = validar_codigos.validar(df, {"Polaridade *": {"tipo": "dominio", "valores": {"1", "2"}}})
        assert res["dados"]["achados"] == []

    def test_codigo_excede_limite_e_critico(self):
        df = pd.DataFrame({"Código do Indicador *": ["IND_Faturamento_Liquido"]})
        res = validar_codigos.validar(df, {"Código do Indicador *": {"tipo": "codigo", "max": 10}})
        tipos = {a["tipo"]: a for a in res["dados"]["achados"]}
        assert tipos["codigo_excede_limite"]["severidade"] == "critico"

    def test_texto_em_campo_codigo_estrito_bloqueia(self):
        df = pd.DataFrame({"Código do Pilar Estratégico *": ["Metas Setoriais"]})
        res = validar_codigos.validar(
            df, {"Código do Pilar Estratégico *": {"tipo": "codigo", "max": 10, "estrito": True}})
        tipos = {a["tipo"]: a for a in res["dados"]["achados"]}
        assert tipos["texto_em_campo_codigo"]["severidade"] == "critico"

    def test_texto_em_campo_codigo_nao_estrito_avisa(self):
        df = pd.DataFrame({"Código da Área *": ["Area Comercial"]})
        res = validar_codigos.validar(
            df, {"Código da Área *": {"tipo": "codigo", "max": 50}})
        tipos = {a["tipo"]: a for a in res["dados"]["achados"]}
        assert tipos["texto_em_campo_codigo"]["severidade"] == "medio"

    def test_acento_detectado_como_texto(self):
        df = pd.DataFrame({"Código do Pilar Estratégico *": ["Inovação"]})
        res = validar_codigos.validar(
            df, {"Código do Pilar Estratégico *": {"tipo": "codigo", "max": 10, "estrito": True}})
        assert any(a["tipo"] == "texto_em_campo_codigo" for a in res["dados"]["achados"])

    def test_fora_da_lista_padrao_avisa_sem_bloquear(self):
        df = pd.DataFrame({"Código da Unidade de Medida *": ["1"]})
        res = validar_codigos.validar(
            df, {"Código da Unidade de Medida *":
                 {"tipo": "codigo", "max": 10, "estrito": True,
                  "conhecidos": set(dom.EQUIVALENCIAS_UNIDADE_MEDIDA)}})
        achados = res["dados"]["achados"]
        assert len(achados) == 1
        assert achados[0]["tipo"] == "codigo_fora_da_lista_padrao"
        assert achados[0]["severidade"] == "medio"
        assert res["status"] == "aviso"

    def test_vazios_ignorados(self):
        df = pd.DataFrame({"Código do Pilar Estratégico *": ["", None]})
        res = validar_codigos.validar(
            df, {"Código do Pilar Estratégico *": {"tipo": "codigo", "max": 10, "estrito": True}})
        assert res["dados"]["achados"] == []

    def test_coluna_ausente_ignorada(self):
        df = pd.DataFrame({"Outra": ["x"]})
        res = validar_codigos.validar(df, {"Polaridade *": {"tipo": "dominio", "valores": {"1"}}})
        assert res["dados"]["achados"] == []

    def test_codigo_valido_da_plataforma_passa_limpo(self):
        df = pd.DataFrame({
            "Código do Indicador *": ["IND_1234"],
            "Código do Pilar Estratégico *": ["DIR_1234"],
        })
        res = validar_codigos.validar(df, dom.REGRAS_CODIGOS["metas_individuais"])
        assert res["dados"]["achados"] == []


# ── agente de metas: normalização de domínios ────────────────────────────────

class TestMetasDominios:

    def _transformar(self, df, tmp_path, avisos=None):
        return ag_metas._classificar_e_transformar(df, "individual", {}, {}, {}, tmp_path,
                                                   avisos=avisos)

    def test_agregacao_texto_vira_codigo(self, tmp_path):
        df = pd.DataFrame({
            "Código da Meta *": ["M01", "M02", "M03", "M04"],
            "Tipo de Agregação *": ["Soma", "Média Simples", "Definido pelo usuário", "2"],
        })
        r = self._transformar(df, tmp_path)
        assert r["Tipo de Agregação *"].tolist() == ["2", "3", "4", "2"]

    def test_agregacao_nao_reconhecida_mantida_com_aviso(self, tmp_path):
        avisos = []
        df = pd.DataFrame({
            "Código da Meta *": ["M01"],
            "Tipo de Agregação *": ["Ponderada"],
        })
        r = self._transformar(df, tmp_path, avisos=avisos)
        assert r["Tipo de Agregação *"].iloc[0] == "Ponderada"
        assert any("Tipo de Agregação" in av for av in avisos)

    def test_indicador_derivado_sem_dicionario_gera_aviso(self, tmp_path):
        avisos = []
        df = pd.DataFrame({"Código da Meta *": ["Faturamento Líquido Mensal"]})
        self._transformar(df, tmp_path, avisos=avisos)
        assert any("dicionário de indicadores" in av for av in avisos)


# ── agente de indicadores: normalização de domínios ──────────────────────────

class TestIndicadoresDominios:

    def _executar(self, tmp_path, df_raw):
        from agentes.indicadores import agente as ag_ind
        (tmp_path / "config").mkdir(exist_ok=True)
        arquivo = tmp_path / "indicadores.csv"
        df_raw.to_csv(arquivo, sep=";", index=False, encoding="utf-8")
        mapeamento = {"indicadores": {
            "arquivo_sugerido": "indicadores.csv", "aba_sugerida": None,
            "campos": [],
        }}
        (tmp_path / "config" / "mapeamento.json").write_text(
            json.dumps(mapeamento), encoding="utf-8")
        res = ag_ind.executar(str(tmp_path))
        assert res["status"] == "ok"
        return pd.read_csv(tmp_path / "staging/03_indicadores/indicadores_transformados.csv",
                           sep=";", encoding="utf-8-sig", dtype=str), res

    def test_polaridade_nominal_cai_no_padrao_com_aviso(self, tmp_path):
        df, res = self._executar(tmp_path, pd.DataFrame({
            "Código do Indicador *": ["I1", "I2", "I3"],
            "Descrição do Indicador *": ["a", "b", "c"],
            "Polaridade *": ["Maior é Melhor", "Para Baixo", "nominal"],
        }))
        assert df["Polaridade *"].tolist() == ["1", "2", "1"]
        assert any("Polaridade" in av for av in res["avisos"])

    def test_frequencia_e_unidade_normalizadas(self, tmp_path):
        df, _ = self._executar(tmp_path, pd.DataFrame({
            "Código do Indicador *": ["I1", "I2"],
            "Descrição do Indicador *": ["a", "b"],
            "Código de Frequência de Acompanhamento *": ["Mensal", "Anual"],
            "Código da Unidade de Medida *": ["Percentual", "R$"],
        }))
        assert df["Código de Frequência de Acompanhamento *"].tolist() == ["1", "8"]
        assert df["Código da Unidade de Medida *"].tolist() == ["UM001", "UM002"]

    def test_unidade_nao_reconhecida_mantida_com_aviso(self, tmp_path):
        df, res = self._executar(tmp_path, pd.DataFrame({
            "Código do Indicador *": ["I1"],
            "Descrição do Indicador *": ["a"],
            "Código da Unidade de Medida *": ["Furlongs"],
        }))
        assert df["Código da Unidade de Medida *"].iloc[0] == "Furlongs"
        assert any("Unidade de Medida" in av for av in res["avisos"])


# ── validação: campos codificados bloqueiam antes do output ──────────────────

class TestValidacaoCodigos:

    def _setup_staging(self, tmp_path, metas_df):
        d = tmp_path / "staging" / "04_metas_individuais"
        d.mkdir(parents=True)
        metas_df.to_csv(d / "metas_individual_transformadas.csv",
                        sep=";", index=False, encoding="utf-8")
        (tmp_path / "relatorios").mkdir(exist_ok=True)

    def _meta_base(self, **kw):
        base = {
            "Código da Meta *": ["METI_01"],
            "Código da Área *": ["AREA_01"],
            "Login do Responsável pela Meta *": ["joao"],
            "Código do Indicador *": ["IND_1234"],
            "Código do Pilar Estratégico *": ["DIR_1234"],
            "Objetivo da Meta *": ["Crescer"],
            "Peso da Meta *": ["20"],
            "Tipo de Agregação *": ["3"],
            "Tipo de Definição do Valor *": ["1"],
        }
        base.update(kw)
        return pd.DataFrame(base)

    def _validar(self, tmp_path, metas_df):
        from agentes.validacao import agente as ag_validacao
        self._setup_staging(tmp_path, metas_df)
        return ag_validacao.executar(str(tmp_path),
                                     pasta_templates=str(tmp_path / "_sem_templates"))

    def test_pilar_com_texto_bloqueia(self, tmp_path):
        res = self._validar(tmp_path, self._meta_base(**{
            "Código do Pilar Estratégico *": ["Metas Setoriais"]}))
        assert res["dados"]["status_geral"] == "bloqueado"
        assert any(a["tipo"] == "texto_em_campo_codigo" for a in res["dados"]["achados"])

    def test_agregacao_texto_bloqueia(self, tmp_path):
        res = self._validar(tmp_path, self._meta_base(**{
            "Tipo de Agregação *": ["Definido pelo usuário"]}))
        assert res["dados"]["status_geral"] == "bloqueado"
        assert any(a["tipo"] == "dominio_invalido" for a in res["dados"]["achados"])

    def test_indicador_longo_bloqueia(self, tmp_path):
        res = self._validar(tmp_path, self._meta_base(**{
            "Código do Indicador *": ["IND_Faturamento_Liquido_Mensal"]}))
        assert res["dados"]["status_geral"] == "bloqueado"
        assert any(a["tipo"] == "codigo_excede_limite" for a in res["dados"]["achados"])

    def test_codigos_validos_aprovam_e_geram_xlsx(self, tmp_path):
        res = self._validar(tmp_path, self._meta_base())
        assert res["dados"]["status_geral"] == "aprovado"
        output = Path(res["dados"]["output_gerado"])
        assert (output / "Import_Metas Individuais.xlsx").exists()
