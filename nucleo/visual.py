"""
Helpers visuais para o CLI: cores ANSI semânticas, cabeçalho de execução
estilizado, banner de welcome.

Fontes de inspiração: Claude Code, Gemini CLI, Codex CLI.

Princípios:
- Cor só quando faz sentido: stdout é TTY, NO_COLOR não está setado,
  TERM != "dumb". Em pipes/redirect/CI, retorna texto puro.
- Em Windows, ativamos VT processing via colorama no import, para que
  códigos ANSI funcionem em cmd.exe legado.
- Símbolos ASCII-friendly (✓ ✗ ⚠ ⏸ ►) — funcionam em terminais modernos
  inclusive Windows Terminal, e degradam aceitáveis em fontes mais limitadas.
"""
import os
import shutil
import sys
from datetime import datetime

# Ativa VT no Windows quando disponível. just_fix_windows_console é a forma
# moderna do colorama (≥0.4.6) — não envolve stdout, só liga o flag VT.
if sys.platform == "win32":
    try:
        import colorama
        colorama.just_fix_windows_console()
    except Exception:
        pass


# ── Códigos ANSI ─────────────────────────────────────────────────────────────

RESET = "\x1b[0m"
BOLD = "\x1b[1m"
DIM = "\x1b[2m"

VERMELHO = "\x1b[31m"
VERDE = "\x1b[32m"
AMARELO = "\x1b[33m"
AZUL = "\x1b[34m"
MAGENTA = "\x1b[35m"
CIANO = "\x1b[36m"
BRANCO = "\x1b[37m"
CINZA = "\x1b[90m"


def usar_cor() -> bool:
    """Detecta em runtime se faz sentido emitir códigos ANSI."""
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    try:
        return sys.stdout.isatty()
    except (AttributeError, ValueError):
        return False


def colorir(texto: str, *codigos: str) -> str:
    """Envolve `texto` com os códigos ANSI passados, se cor estiver habilitada."""
    if not usar_cor() or not codigos:
        return texto
    return "".join(codigos) + texto + RESET


# ── Marcações semânticas ─────────────────────────────────────────────────────

def success(msg: str) -> str:
    return colorir(f"✓ {msg}", VERDE)

def warning(msg: str) -> str:
    return colorir(f"⚠ {msg}", AMARELO)

def error(msg: str) -> str:
    return colorir(f"✗ {msg}", VERMELHO)

def info(msg: str) -> str:
    return colorir(f"► {msg}", CIANO)

def pausa(msg: str) -> str:
    return colorir(f"⏸ {msg}", MAGENTA)

def titulo(texto: str) -> str:
    return colorir(texto, BOLD, BRANCO)

def comando(texto: str) -> str:
    return colorir(texto, CIANO)

def caminho(texto: str) -> str:
    return colorir(texto, CIANO)

def fraco(texto: str) -> str:
    return colorir(texto, DIM)


# ── Cabeçalho de execução ────────────────────────────────────────────────────

def cabecalho(largura: int = 60, **campos: str) -> str:
    """
    Renderiza um cabeçalho com box-drawing chars e campos rotulados.

    Exemplo:
      cabecalho(Cliente="demo", Agente="inferir (LLM)", Iniciado="2026-05-05 19:34:17")

    Produz:
      ╔══════════════════════════════════════════════════════════╗
      ║  Cliente    demo                                         ║
      ║  Agente     inferir (LLM)                                ║
      ║  Iniciado   2026-05-05 19:34:17                          ║
      ╚══════════════════════════════════════════════════════════╝
    """
    if not campos:
        return ""

    rotulo_w = max(len(k) for k in campos.keys())
    # Conteúdo total = "║" + "  " + miolo + "  " + "║" = 6 + miolo
    inner_w = largura - 6

    linha_topo = "╔" + ("═" * (largura - 2)) + "╗"
    linha_base = "╚" + ("═" * (largura - 2)) + "╝"

    linhas = [colorir(linha_topo, CIANO)]

    for rotulo, valor in campos.items():
        rotulo_fmt = rotulo.ljust(rotulo_w)
        # Largura visível ocupada pelo rótulo + separador + valor.
        ocupado = rotulo_w + 3 + len(str(valor))
        if ocupado > inner_w:
            # Trunca o valor pra não estourar a borda.
            corte = inner_w - rotulo_w - 3 - 1
            valor = str(valor)[:corte] + "…"
            ocupado = rotulo_w + 3 + len(valor)
        padding = " " * (inner_w - ocupado)

        linha = (
            colorir("║", CIANO)
            + "  "
            + colorir(rotulo_fmt, BOLD, BRANCO)
            + "   "
            + str(valor)
            + padding
            + "  "
            + colorir("║", CIANO)
        )
        linhas.append(linha)

    linhas.append(colorir(linha_base, CIANO))
    return "\n".join(linhas)


# ── Banner de welcome ────────────────────────────────────────────────────────

# Figlet "ANSI Shadow" — 88 chars de largura, 6 linhas.
_BANNER_IMPLANTACAO = """\
██╗███╗   ███╗██████╗ ██╗      █████╗ ███╗   ██╗████████╗ █████╗  ██████╗ █████╗  ██████╗
██║████╗ ████║██╔══██╗██║     ██╔══██╗████╗  ██║╚══██╔══╝██╔══██╗██╔════╝██╔══██╗██╔═══██╗
██║██╔████╔██║██████╔╝██║     ███████║██╔██╗ ██║   ██║   ███████║██║     ███████║██║   ██║
██║██║╚██╔╝██║██╔═══╝ ██║     ██╔══██║██║╚██╗██║   ██║   ██╔══██║██║     ██╔══██║██║   ██║
██║██║ ╚═╝ ██║██║     ███████╗██║  ██║██║ ╚████║   ██║   ██║  ██║╚██████╗██║  ██║╚██████╔╝
╚═╝╚═╝     ╚═╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝ ╚═════╝"""


def banner(versao: str = None, tagline: str = None) -> str:
    """Banner de welcome com 'IMPLANTACAO' em figlet, subtítulo opcional."""
    linhas = [colorir(_BANNER_IMPLANTACAO, CIANO, BOLD)]
    sub = "  Implantação RHTec/Mereo"
    if versao:
        sub += f" · v{versao}"
    linhas.append(colorir(sub, CINZA))
    if tagline:
        linhas.append("")
        linhas.append(tagline)
    return "\n".join(linhas)


# ── Timestamp helper para cabeçalhos ────────────────────────────────────────

def agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ── Largura responsiva ──────────────────────────────────────────────────────

def largura_terminal(default: int = 70, minimo: int = 50, maximo: int = 90) -> int:
    """Largura adequada do terminal, com clamp em [minimo, maximo]."""
    try:
        cols = shutil.get_terminal_size((default, 20)).columns
    except Exception:
        cols = default
    return max(minimo, min(maximo, cols))
