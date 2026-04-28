#!/usr/bin/env bash
# Demo dirigida do pipeline para apresentação ao vivo.
#
# Uso:   ./demo.sh [cliente]      (default: demo)
#        ./demo.sh demo --no-reset    não limpa staging/output antes
#
# Cada passo pausa esperando Enter — o apresentador controla o ritmo.
# Pressione Ctrl+C para abortar a qualquer momento.
set -e

CLIENTE="${1:-demo}"
NO_RESET=0
[ "${2:-}" = "--no-reset" ] && NO_RESET=1

# ── cores ──────────────────────────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD=$'\033[1m'; DIM=$'\033[2m'
    CYAN=$'\033[0;36m'; YELLOW=$'\033[0;33m'; GREEN=$'\033[0;32m'; MAGENTA=$'\033[0;35m'
    RESET=$'\033[0m'
else
    BOLD=''; DIM=''; CYAN=''; YELLOW=''; GREEN=''; MAGENTA=''; RESET=''
fi

narra()  { printf "${CYAN}  ▸ %s${RESET}\n" "$1"; }
titulo() { printf "\n${YELLOW}${BOLD}━━━ %s ━━━${RESET}\n\n" "$1"; }
ok()     { printf "${GREEN}  ✓ %s${RESET}\n" "$1"; }
cmd()    { printf "${MAGENTA}  $ %s${RESET}\n" "$1"; }
pausa() {
    printf "\n${DIM}  [Enter para continuar — Ctrl+C aborta]${RESET} "
    read -r _ </dev/tty
    echo
}

CLIENTE_DIR="clientes/$CLIENTE"
if [ ! -d "$CLIENTE_DIR" ]; then
    printf "Cliente '%s' não encontrado em %s\n" "$CLIENTE" "$CLIENTE_DIR" >&2
    exit 1
fi
if [ ! -f "$CLIENTE_DIR/config/mapeamento.json" ]; then
    printf "Cliente '%s' sem config/mapeamento.json — esta demo assume mapeamento travado\n" "$CLIENTE" >&2
    exit 1
fi

# ── 0. Cabeçalho ───────────────────────────────────────────────────────────
clear || true
cat <<EOF
${BOLD}═══════════════════════════════════════════════════════════════
  Pipeline de Implantação RHTec/Mereo — Demo dirigida
  Cliente: ${CYAN}$CLIENTE${RESET}${BOLD}
═══════════════════════════════════════════════════════════════${RESET}

  Esta demo executa o pipeline completo no cliente '$CLIENTE',
  partindo de mapeamento travado e raw/ alimentado.

  Você verá 3 comandos em sequência:
    1. ${BOLD}./implantacao pilotar${RESET}    (orquestrador LLM decide o próximo passo)
    2. ${BOLD}./implantacao validar${RESET}    (validação que o orquestrador delegou)
    3. ${BOLD}./implantacao responder${RESET}  (retoma o orquestrador com o resultado)

  Cada passo pausa esperando Enter.
EOF
pausa

# ── 1. Estado inicial ──────────────────────────────────────────────────────
titulo "Estado inicial do cliente"

if [ "$NO_RESET" -eq 0 ]; then
    narra "Limpando execuções anteriores (preservando raw/ e config/)"
    rm -rf "$CLIENTE_DIR/staging" "$CLIENTE_DIR/output" \
           "$CLIENTE_DIR/relatorios" "$CLIENTE_DIR/sessoes"
fi

narra "Conteúdo de clientes/$CLIENTE/:"
ls "$CLIENTE_DIR" | sed 's/^/    /'
echo
narra "raw/ — dados brutos do cliente (Excel/CSV):"
find "$CLIENTE_DIR/raw" -type f | sed "s|$CLIENTE_DIR/raw|    raw|"
echo
narra "config/ — mapeamento travado e dicionários revisados:"
ls "$CLIENTE_DIR/config" | sed 's/^/    /'
echo
narra "Mapeamento travado:"
head -3 "$CLIENTE_DIR/config/mapeamento.json" | sed 's/^/    /'
pausa

# ── 2. Pilotar ─────────────────────────────────────────────────────────────
titulo "1/3 — Orquestrador (pilotar)"
narra "O orquestrador inspeciona o estado, executa as transformações"
narra "deterministas que pode (areas, colaboradores, metas, …) e delega"
narra "validação/diagnóstico via HITL quando precisa de outro agente LLM."
echo
cmd "./implantacao pilotar $CLIENTE"
pausa

LOG_PILOTAR="$(mktemp)"
./implantacao pilotar "$CLIENTE" 2>&1 | tee "$LOG_PILOTAR"
SESSAO_ID=$(grep -oE "responder $CLIENTE [0-9_a-zA-Z]+" "$LOG_PILOTAR" | head -1 | awk '{print $3}')
rm -f "$LOG_PILOTAR"

if [ -z "$SESSAO_ID" ]; then
    printf "\n${YELLOW}Não foi possível extrair o ID da sessão. Aborte e investigue.${RESET}\n" >&2
    exit 1
fi
echo
ok "Orquestrador pausou pedindo o agente 'validar' (HITL)"
ok "Sessão para retomar: $SESSAO_ID"
narra "Os 3 staging foram gerados em paralelo:"
find "$CLIENTE_DIR/staging" -name "*.csv" 2>/dev/null | sed "s|$CLIENTE_DIR/|    |"
pausa

# ── 3. Validar ─────────────────────────────────────────────────────────────
titulo "2/3 — Validação"
narra "Outro agente LLM valida schema, campos obrigatórios e integridade"
narra "referencial. Decide entre aprovado / aprovado_com_ressalvas / bloqueado."
narra "Quando aprovado, copia para output/<data>/ com BOM UTF-8 (Excel-friendly)."
echo
cmd "./implantacao validar $CLIENTE"
pausa

./implantacao validar "$CLIENTE"
echo
ok "Validação concluída"
narra "Relatório com seção narrativa em:"
echo "    $CLIENTE_DIR/relatorios/relatorio_validacao.md"
narra "Output gerado:"
ls "$CLIENTE_DIR/output/"*/ 2>/dev/null | sed "s|^|    |"
pausa

# ── 4. Responder ───────────────────────────────────────────────────────────
titulo "3/3 — Retomar orquestrador"
narra "Devolvemos o resultado da validação ao orquestrador. Ele consolida tudo,"
narra "grava o log_pipeline.json e devolve o sumário final."
echo
cmd "./implantacao responder $CLIENTE $SESSAO_ID"
pausa

printf 'feito — validar concluiu com status aprovado, output gerado\n\n' \
    | ./implantacao responder "$CLIENTE" "$SESSAO_ID"

# ── 5. Resultado final ─────────────────────────────────────────────────────
titulo "Resultado final"

narra "Arquivos prontos para importação na plataforma:"
ls -1 "$CLIENTE_DIR/output/"*/ 2>/dev/null | sed 's|^|    |'
echo
narra "Verificação de BOM UTF-8 (Excel abre os acentos corretamente):"
for f in "$CLIENTE_DIR/output/"*/*.csv; do
    [ -f "$f" ] || continue
    if head -c 3 "$f" | xxd -p | grep -q "^efbbbf"; then
        ok "$(basename "$f")"
    else
        printf "    ${YELLOW}⚠ sem BOM:${RESET} %s\n" "$(basename "$f")"
    fi
done
echo
narra "Relatórios:"
ls "$CLIENTE_DIR/relatorios/" | sed 's/^/    /'
echo
narra "Sessão completa para auditoria (prompt, transcript, estado):"
echo "    $CLIENTE_DIR/sessoes/$SESSAO_ID/"

cat <<EOF

${GREEN}${BOLD}═══════════════════════════════════════════════════════════════
  Demo concluída
═══════════════════════════════════════════════════════════════${RESET}

Próximo passo (em produção): subir os arquivos de output/<data>/ na
plataforma RHTec/Mereo.

EOF
