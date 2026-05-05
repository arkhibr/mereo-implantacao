"""
Testes do módulo visual: detecção de cor, helpers semânticos, cabeçalho.
Execute com: .venv/bin/python -m pytest testes/unitarios/test_visual.py -v
"""
import io
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from nucleo import visual
from nucleo.visual import (
    cabecalho,
    colorir,
    error,
    fraco,
    info,
    pausa,
    success,
    titulo,
    usar_cor,
    warning,
    BOLD,
    CIANO,
    RESET,
    VERDE,
    VERMELHO,
)


# Helper: força usar_cor() a retornar o valor desejado durante o teste.
@pytest.fixture
def forcar_cor(monkeypatch):
    def _forcar(valor: bool):
        monkeypatch.setattr(visual, "usar_cor", lambda: valor)
    return _forcar


# ── usar_cor ──────────────────────────────────────────────────────────────────

def test_usar_cor_falso_quando_no_color_definida(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.delenv("TERM", raising=False)
    # Mesmo com isatty=True, NO_COLOR vence.
    fake_stdout = io.StringIO()
    fake_stdout.isatty = lambda: True
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    assert usar_cor() is False

def test_usar_cor_falso_em_terminal_dumb(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    fake_stdout = io.StringIO()
    fake_stdout.isatty = lambda: True
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    assert usar_cor() is False

def test_usar_cor_falso_quando_stdout_nao_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    fake_stdout = io.StringIO()
    fake_stdout.isatty = lambda: False
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    assert usar_cor() is False

def test_usar_cor_verdadeiro_em_tty_normal(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    fake_stdout = io.StringIO()
    fake_stdout.isatty = lambda: True
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    assert usar_cor() is True


# ── colorir ───────────────────────────────────────────────────────────────────

def test_colorir_envolve_com_codigos_quando_cor_ativa(forcar_cor):
    forcar_cor(True)
    assert colorir("oi", VERDE) == VERDE + "oi" + RESET

def test_colorir_combina_multiplos_codigos(forcar_cor):
    forcar_cor(True)
    assert colorir("x", BOLD, CIANO) == BOLD + CIANO + "x" + RESET

def test_colorir_sem_cor_devolve_texto_puro(forcar_cor):
    forcar_cor(False)
    assert colorir("oi", VERDE) == "oi"

def test_colorir_sem_codigos_nao_envolve():
    assert colorir("oi") == "oi"


# ── helpers semânticos ────────────────────────────────────────────────────────

def test_success_tem_simbolo_check(forcar_cor):
    forcar_cor(False)
    assert success("ok") == "✓ ok"

def test_warning_tem_simbolo_aviso(forcar_cor):
    forcar_cor(False)
    assert warning("aviso") == "⚠ aviso"

def test_error_tem_simbolo_x(forcar_cor):
    forcar_cor(False)
    assert error("erro") == "✗ erro"

def test_info_tem_simbolo_seta(forcar_cor):
    forcar_cor(False)
    assert info("info") == "► info"

def test_pausa_tem_simbolo_pause(forcar_cor):
    forcar_cor(False)
    assert pausa("pausada") == "⏸ pausada"

def test_helpers_aplicam_cor_quando_ativa(forcar_cor):
    forcar_cor(True)
    assert success("ok") == VERDE + "✓ ok" + RESET
    assert error("erro") == VERMELHO + "✗ erro" + RESET

def test_titulo_aplica_bold_e_branco(forcar_cor):
    forcar_cor(True)
    saida = titulo("TITULO")
    assert saida.startswith(BOLD)
    assert "TITULO" in saida
    assert saida.endswith(RESET)

def test_fraco_sem_cor_e_idempotente(forcar_cor):
    forcar_cor(False)
    assert fraco("texto") == "texto"


# ── cabecalho ─────────────────────────────────────────────────────────────────

def test_cabecalho_devolve_string_vazia_sem_campos():
    assert cabecalho(largura=60) == ""

def test_cabecalho_envolve_com_box_drawing(forcar_cor):
    forcar_cor(False)
    saida = cabecalho(largura=60, Cliente="demo", Agente="x")
    linhas = saida.split("\n")
    assert linhas[0].startswith("╔") and linhas[0].endswith("╗")
    assert linhas[-1].startswith("╚") and linhas[-1].endswith("╝")
    assert all(l.startswith("║") and l.endswith("║") for l in linhas[1:-1])

def test_cabecalho_largura_consistente_em_todas_as_linhas(forcar_cor):
    forcar_cor(False)
    saida = cabecalho(largura=60, Cliente="demo", Agente="inferir (LLM)", Iniciado="2026-05-05 19:34:17")
    linhas = saida.split("\n")
    larguras = {len(l) for l in linhas}
    assert larguras == {60}, f"larguras inconsistentes: {larguras}"

def test_cabecalho_inclui_rotulo_e_valor(forcar_cor):
    forcar_cor(False)
    saida = cabecalho(largura=60, Cliente="demo", Agente="x")
    assert "Cliente" in saida
    assert "demo" in saida
    assert "Agente" in saida

def test_cabecalho_trunca_valor_que_estoura(forcar_cor):
    forcar_cor(False)
    valor_longo = "x" * 200
    saida = cabecalho(largura=60, Campo=valor_longo)
    linhas = saida.split("\n")
    # Largura ainda consistente (60) e há reticência no truncamento.
    assert all(len(l) == 60 for l in linhas)
    assert "…" in saida


# ── banner ────────────────────────────────────────────────────────────────────

def test_banner_inclui_texto_implantacao_e_versao(forcar_cor):
    forcar_cor(False)
    saida = visual.banner(versao="1.2.3")
    assert "Implantação RHTec/Mereo" in saida
    assert "v1.2.3" in saida

def test_banner_sem_versao_omite_v(forcar_cor):
    forcar_cor(False)
    saida = visual.banner()
    assert "Implantação RHTec/Mereo" in saida
    assert " · v" not in saida


# ── largura_terminal ──────────────────────────────────────────────────────────

def _fake_terminal(cols: int):
    """Devolve uma função que imita shutil.get_terminal_size — usa os.terminal_size,
    que é named tuple e funciona tanto pro nosso código quanto pro pytest.terminal."""
    def _faux(*args, **kwargs):
        return os.terminal_size((cols, 24))
    return _faux

def test_largura_terminal_respeita_minimo(monkeypatch):
    monkeypatch.setattr(visual.shutil, "get_terminal_size", _fake_terminal(30))
    assert visual.largura_terminal(minimo=50, maximo=90) == 50

def test_largura_terminal_respeita_maximo(monkeypatch):
    monkeypatch.setattr(visual.shutil, "get_terminal_size", _fake_terminal(200))
    assert visual.largura_terminal(minimo=50, maximo=90) == 90

def test_largura_terminal_dentro_do_intervalo(monkeypatch):
    monkeypatch.setattr(visual.shutil, "get_terminal_size", _fake_terminal(70))
    assert visual.largura_terminal(minimo=50, maximo=90) == 70
