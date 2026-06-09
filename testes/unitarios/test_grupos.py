"""
Testes do registro de grupos de carga (nucleo/grupos.py).
Execute com: python -m pytest testes/unitarios/test_grupos.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from nucleo import grupos


# ── Estrutura real ─────────────────────────────────────────────────────────────

def test_nucleo_e_o_seminal():
    assert grupos.GRUPO_SEMINAL == "nucleo"
    assert grupos.GRUPOS["nucleo"]["seminal"] is True


def test_nucleo_nao_depende_de_nada():
    assert grupos.GRUPOS["nucleo"]["depende_de"] == []


def test_predicados_dependem_do_nucleo():
    for g, info in grupos.GRUPOS.items():
        if g == grupos.GRUPO_SEMINAL:
            continue
        assert "nucleo" in info["depende_de"], f"{g} deveria depender do núcleo"


def test_ordem_topologica_poe_nucleo_primeiro():
    ordem = grupos.ordem_topologica()
    assert ordem[0] == "nucleo"
    assert set(ordem) == set(grupos.GRUPOS)


def test_etapas_em_ordem_comeca_pelo_nucleo():
    etapas = grupos.etapas_em_ordem()
    assert etapas[:2] == ["areas", "colaboradores"]
    # Todas as 6 transformações estão presentes, sem repetição.
    assert sorted(etapas) == sorted(
        ["areas", "colaboradores", "indicadores", "metas", "curva_alcance", "valores"]
    )
    assert len(etapas) == len(set(etapas))


def test_metas_agrega_curva_e_valores():
    assert grupos.etapas_do_grupo("metas") == ["metas", "curva_alcance", "valores"]


def test_grupo_de_etapa():
    assert grupos.grupo_de_etapa("areas") == "nucleo"
    assert grupos.grupo_de_etapa("colaboradores") == "nucleo"
    assert grupos.grupo_de_etapa("indicadores") == "indicadores"
    assert grupos.grupo_de_etapa("curva_alcance") == "metas"
    assert grupos.grupo_de_etapa("inexistente") is None


def test_dependencias_de():
    assert grupos.dependencias_de("nucleo") == []
    assert grupos.dependencias_de("metas") == ["nucleo"]
    assert grupos.dependencias_de("indicadores") == ["nucleo"]


# ── Validação ──────────────────────────────────────────────────────────────────

def test_validar_aceita_o_registro_real():
    grupos._validar(grupos.GRUPOS)  # não levanta


def test_validar_rejeita_dependencia_inexistente():
    ruim = {
        "nucleo": {"seminal": True, "depende_de": [], "etapas": ["a"]},
        "x": {"seminal": False, "depende_de": ["fantasma"], "etapas": ["b"]},
    }
    with pytest.raises(ValueError):
        grupos._validar(ruim)


def test_validar_rejeita_ciclo():
    ruim = {
        "nucleo": {"seminal": True, "depende_de": [], "etapas": ["a"]},
        "x": {"seminal": False, "depende_de": ["y"], "etapas": ["b"]},
        "y": {"seminal": False, "depende_de": ["x"], "etapas": ["c"]},
    }
    with pytest.raises(ValueError):
        grupos._validar(ruim)


def test_validar_exige_um_unico_seminal():
    dois = {
        "a": {"seminal": True, "depende_de": [], "etapas": ["x"]},
        "b": {"seminal": True, "depende_de": [], "etapas": ["y"]},
    }
    with pytest.raises(ValueError):
        grupos._validar(dois)

    nenhum = {"a": {"seminal": False, "depende_de": [], "etapas": ["x"]}}
    with pytest.raises(ValueError):
        grupos._validar(nenhum)


def test_validar_rejeita_etapa_repetida_entre_grupos():
    ruim = {
        "nucleo": {"seminal": True, "depende_de": [], "etapas": ["a"]},
        "x": {"seminal": False, "depende_de": ["nucleo"], "etapas": ["a"]},
    }
    with pytest.raises(ValueError):
        grupos._validar(ruim)


# ── Extensibilidade ──────────────────────────────────────────────────────────

def test_grupo_novo_se_encaixa_sem_tocar_nos_existentes():
    """Acrescentar um grupo predicado é só uma entrada apontando para o núcleo."""
    estendido = dict(grupos.GRUPOS)
    estendido["competencias"] = {
        "titulo": "Competências",
        "descricao": "teste",
        "seminal": False,
        "depende_de": ["nucleo"],
        "etapas": ["competencias"],
    }
    grupos._validar(estendido)  # registro estendido continua válido
    ordem = grupos.ordem_topologica(estendido)
    assert ordem[0] == "nucleo"
    assert "competencias" in ordem
    assert ordem.index("competencias") > ordem.index("nucleo")
    assert grupos.dependencias_de("competencias", estendido) == ["nucleo"]
