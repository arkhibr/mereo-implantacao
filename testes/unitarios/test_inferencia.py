"""
Testes da heurística determinista de inferência de indicadores.
Execute com: .venv/bin/python -m pytest testes/unitarios/test_inferencia.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from ferramentas.inferencia.indicadores import (
    PLACEHOLDER,
    extrair_candidatos,
    inferir_polaridade,
    inferir_unidade,
    montar_linha,
    normalizar_descricao,
)


# ── normalizar_descricao ──────────────────────────────────────────────────────

def test_normalizar_remove_sufixo_temporal_simples():
    assert normalizar_descricao("Vendas (2024)") == "Vendas"

def test_normalizar_remove_sufixo_temporal_composto():
    assert normalizar_descricao("Vendas Remanescentes (Entregas 2024+)") == "Vendas Remanescentes"

def test_normalizar_remove_sufixo_traco_ano():
    assert normalizar_descricao("Lucro Operacional - 2025") == "Lucro Operacional"

def test_normalizar_preserva_descricao_sem_ano():
    assert normalizar_descricao("Receita Total") == "Receita Total"

def test_normalizar_colapsa_espacos():
    assert normalizar_descricao("  Vendas    Totais  ") == "Vendas Totais"

def test_normalizar_lida_com_none():
    assert normalizar_descricao(None) == ""


# ── inferir_polaridade ────────────────────────────────────────────────────────

def test_polaridade_menor_em_despesa():
    pol, conf = inferir_polaridade("Despesas Operacionais")
    assert pol == "Menor é Melhor"
    assert conf == "media"

def test_polaridade_menor_em_atraso():
    pol, _ = inferir_polaridade("Atraso médio de entrega")
    assert pol == "Menor é Melhor"

def test_polaridade_maior_em_vendas():
    pol, conf = inferir_polaridade("Vendas Remanescentes")
    assert pol == "Maior é Melhor"
    assert conf == "media"

def test_polaridade_maior_em_receita():
    pol, _ = inferir_polaridade("Receita Bruta")
    assert pol == "Maior é Melhor"

def test_polaridade_default_baixa_quando_sem_sinal():
    pol, conf = inferir_polaridade("Indicador Estranho XYZ")
    assert pol == "Maior é Melhor"
    assert conf == "baixa"

def test_polaridade_default_para_descricao_vazia():
    pol, conf = inferir_polaridade("")
    assert pol == "Maior é Melhor"
    assert conf == "baixa"


# ── extrair_candidatos ────────────────────────────────────────────────────────

def test_extrair_agrupa_por_codigo():
    metas = [
        {"cod": "M001", "desc": "Vendas Totais"},
        {"cod": "M001", "desc": "Vendas Totais"},
        {"cod": "M002", "desc": "Despesas"},
    ]
    cands = extrair_candidatos(metas, "cod", "desc")
    codigos = sorted(c.codigo for c in cands)
    assert codigos == ["M001", "M002"]

def test_extrair_descricao_canonica_normaliza_sufixo_temporal():
    metas = [
        {"cod": "M001", "desc": "Vendas Remanescentes (Entregas 2024+)"},
    ]
    cands = extrair_candidatos(metas, "cod", "desc")
    assert cands[0].descricao_canonica == "Vendas Remanescentes"

def test_extrair_pula_metas_sem_codigo():
    metas = [
        {"cod": None, "desc": "x"},
        {"cod": "", "desc": "y"},
        {"cod": "M001", "desc": "Vendas"},
    ]
    cands = extrair_candidatos(metas, "cod", "desc")
    assert len(cands) == 1 and cands[0].codigo == "M001"

def test_extrair_preserva_variantes_observadas():
    metas = [
        {"cod": "M001", "desc": "Vendas (2024)"},
        {"cod": "M001", "desc": "Vendas Remanescentes (2024)"},
        {"cod": "M001", "desc": "Vendas (2024)"},
    ]
    cands = extrair_candidatos(metas, "cod", "desc")
    assert len(cands[0].descricoes_observadas) == 2  # set de variantes

def test_extrair_descricao_canonica_pega_a_mais_frequente():
    metas = [
        {"cod": "M001", "desc": "Receita A"},
        {"cod": "M001", "desc": "Receita A"},
        {"cod": "M001", "desc": "Receita B"},
    ]
    cands = extrair_candidatos(metas, "cod", "desc")
    assert cands[0].descricao_canonica == "Receita A"

def test_extrair_linhas_origem_acumula_indices():
    metas = [
        {"cod": "M001", "desc": "x"},
        {"cod": "M002", "desc": "y"},
        {"cod": "M001", "desc": "x"},
    ]
    cands = extrair_candidatos(metas, "cod", "desc")
    m001 = next(c for c in cands if c.codigo == "M001")
    assert m001.linhas_origem == [1, 3]


# ── montar_linha ──────────────────────────────────────────────────────────────

def test_montar_linha_preenche_14_campos_template_e_4_auxiliares():
    cands = extrair_candidatos(
        [{"cod": "M001", "desc": "Vendas Totais"}],
        "cod", "desc",
    )
    linha = montar_linha(cands[0], "raw/x.xlsx", "Metas")
    # Identitários
    assert linha["Código do Indicador *"] == "M001"
    assert linha["Descrição do Indicador *"] == "Vendas Totais"
    # Default
    assert linha["Ativo *"] == "Sim"
    # Polaridade da heurística (Vendas → Maior)
    assert linha["Polaridade *"] == "Maior é Melhor"
    # Placeholders intactos
    assert linha["Código da Unidade de Medida *"] == PLACEHOLDER
    assert linha["Código da Faixa de Farol *"] == PLACEHOLDER
    assert linha["Código de Frequência de Acompanhamento *"] == PLACEHOLDER
    # Auxiliares
    assert linha["_origem"] == "inferido"
    assert linha["_derivado_de"].startswith("raw/x.xlsx:Metas:")
    assert "_confianca" in linha and linha["_confianca"] in ("alta", "media", "baixa", "nenhuma")

def test_montar_linha_confianca_media_quando_descricoes_variantes():
    metas = [
        {"cod": "M001", "desc": "Vendas Remanescentes (2024)"},
        {"cod": "M001", "desc": "Vendas Remanescentes Diferente"},
    ]
    cands = extrair_candidatos(metas, "cod", "desc")
    linha = montar_linha(cands[0], "raw/x.xlsx", "Metas")
    # Identidade rebaixada por variantes (media), polaridade media → agregado media.
    assert linha["_confianca"] == "media"
    assert "variações de descrição" in linha["_observacao"]

def test_montar_linha_confianca_baixa_para_indicador_sem_palavra_chave():
    metas = [{"cod": "M001", "desc": "Indicador XYZ"}]
    cands = extrair_candidatos(metas, "cod", "desc")
    linha = montar_linha(cands[0], "raw/x.xlsx", "Metas")
    # Identidade alta, polaridade baixa → agregado baixa.
    assert linha["_confianca"] == "baixa"

def test_montar_linha_derivado_de_trunca_lista_longa():
    metas = [{"cod": "M001", "desc": "Vendas"} for _ in range(10)]
    cands = extrair_candidatos(metas, "cod", "desc")
    linha = montar_linha(cands[0], "raw/x.xlsx", "Metas")
    assert "10 no total" in linha["_derivado_de"]


# ── inferência de unidade de medida ──────────────────────────────────────────

class TestInferirUnidade:

    def test_percentual(self):
        assert inferir_unidade("Reduzir inadimplência para 2%") == "UM001"
        assert inferir_unidade("Atingir 95 percentual de SLA") == "UM001"

    def test_reais_simples(self):
        assert inferir_unidade("Faturar R$ 500") == "UM002"

    def test_reais_mil(self):
        assert inferir_unidade("Receita de R$ 300 mil") == "UM003"

    def test_reais_milhoes(self):
        assert inferir_unidade("Faturar R$ 120 milhões") == "UM004"

    def test_percentual_vence_reais(self):
        assert inferir_unidade("Atingir 90% da meta de R$ 1 milhão") == "UM001"

    def test_dias_horas(self):
        assert inferir_unidade("Reduzir prazo médio para 5 dias") == "UM005"
        assert inferir_unidade("Atendimento em até 2 horas") == "UM006"

    def test_score(self):
        assert inferir_unidade("Elevar score de crédito") == "UM012"

    def test_sem_sinal_devolve_none(self):
        assert inferir_unidade("Entregar 45 projetos") is None
        assert inferir_unidade("") is None
        assert inferir_unidade(None) is None
