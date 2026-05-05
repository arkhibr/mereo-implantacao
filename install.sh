#!/usr/bin/env bash
# Instalador do Pipeline de Implantação RHTec/Mereo (Linux/macOS).
#
# One-liner (a partir de qualquer diretório):
#   curl -fsSL https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.sh | bash
#
# O que faz:
#   1. Confere que existe Python 3.10+ e git
#   2. Clona o repo em ./mereo-implantacao/ (ou git pull se já existe)
#   3. Cria .venv e instala requirements
#   4. Pergunta a MEREO_LLM_API_KEY e escreve em .env
#   5. Roda um smoke test
#   6. Imprime os próximos passos
#
# Variáveis de ambiente reconhecidas:
#   DIR_INSTALACAO  — pasta-alvo (default: mereo-implantacao)
#   MEREO_LLM_API_KEY — pula o prompt interativo se já estiver definida
set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

abort() { printf "${RED}✗ %s${NC}\n" "$1" >&2; exit 1; }
ok()    { printf "${GREEN}✓ %s${NC}\n" "$1"; }
info()  { printf "${BLUE}→ %s${NC}\n" "$1"; }
warn()  { printf "${YELLOW}⚠ %s${NC}\n" "$1"; }
titulo(){ printf "\n${BOLD}%s${NC}\n" "$1"; }

REPO_URL="https://github.com/arkhibr/mereo-implantacao.git"
DIR_INSTALACAO="${DIR_INSTALACAO:-mereo-implantacao}"

# Lê uma linha do tty real, mesmo quando o script vem via curl | bash.
ler_do_tty() {
    if [ -t 0 ]; then
        read -r REPLY
    elif [ -r /dev/tty ]; then
        read -r REPLY < /dev/tty
    else
        REPLY=""
    fi
    printf "%s" "$REPLY"
}

cat <<'BANNER'
===============================================
  Pipeline de Implantação RHTec/Mereo
  Instalador
===============================================
BANNER

# 1) Pré-requisitos --------------------------------------------------------
titulo "1/5  Verificando pré-requisitos"

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        if "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' 2>/dev/null; then
            PYTHON="$cmd"
            ver=$("$cmd" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}")')
            ok "Python $ver  ($(command -v "$cmd"))"
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    abort "Python 3.10+ não encontrado.

  Instale a partir de:
    Linux:   sudo apt install python3 python3-venv  (Debian/Ubuntu)
             sudo dnf install python3              (Fedora/RHEL)
    macOS:   https://www.python.org/downloads/macos/
             ou:  brew install python@3.12

  Depois rode este instalador novamente."
fi

if ! command -v git >/dev/null 2>&1; then
    abort "git não encontrado.

  Instale a partir de:
    Linux:   sudo apt install git    ou    sudo dnf install git
    macOS:   xcode-select --install   ou   brew install git

  Depois rode este instalador novamente."
fi
ok "git  ($(command -v git))"

# 2) Clonar / atualizar ----------------------------------------------------
titulo "2/5  Obtendo o código"

if [ -d "$DIR_INSTALACAO/.git" ]; then
    info "Já existe um clone em ./$DIR_INSTALACAO — atualizando"
    cd "$DIR_INSTALACAO"
    if git pull --ff-only --quiet; then
        ok "Atualizado para a última versão"
    else
        warn "git pull falhou; prosseguindo com a versão local"
    fi
elif [ -e "$DIR_INSTALACAO" ]; then
    abort "./$DIR_INSTALACAO existe mas não é um clone do repositório.
  Remova-o ou rode o instalador em outro diretório."
else
    info "Clonando $REPO_URL em ./$DIR_INSTALACAO"
    git clone --quiet "$REPO_URL" "$DIR_INSTALACAO"
    cd "$DIR_INSTALACAO"
    ok "Clone concluído"
fi

# 3) venv + dependências ---------------------------------------------------
titulo "3/5  Ambiente virtual e dependências"

if [ ! -d ".venv" ]; then
    info "Criando .venv"
    "$PYTHON" -m venv .venv
fi

info "Instalando dependências (pode levar 1-2 min)"
.venv/bin/pip install --quiet --disable-pip-version-check --upgrade pip
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
ok "Dependências prontas"

# 4) .env ------------------------------------------------------------------
titulo "4/5  Configuração da chave do provider LLM"

if [ -f .env ] && grep -q '^MEREO_LLM_API_KEY=..' .env 2>/dev/null; then
    ok ".env já existe e tem MEREO_LLM_API_KEY preenchida — preservando"
else
    [ -f .env ] || cp .env.example .env

    if [ -n "$MEREO_LLM_API_KEY" ]; then
        info "Usando MEREO_LLM_API_KEY do ambiente"
        chave="$MEREO_LLM_API_KEY"
    else
        echo
        echo "Cole sua chave do provider LLM (ex: Abacus RouteLLM)."
        echo "Pode deixar em branco e editar .env manualmente depois."
        printf "Chave: "
        chave="$(ler_do_tty)"
        echo
    fi

    if [ -z "$chave" ]; then
        warn "Chave vazia — edite ./$DIR_INSTALACAO/.env antes de rodar agentes LLM"
    else
        # Substituição segura (sem expansão pela shell): chave entra via env var.
        CHAVE="$chave" "$PYTHON" - <<'PY'
import os, re
arq = '.env'
texto = open(arq, encoding='utf-8').read()
nova = f"MEREO_LLM_API_KEY={os.environ['CHAVE']}"
if re.search(r'(?m)^MEREO_LLM_API_KEY=', texto):
    texto = re.sub(r'(?m)^MEREO_LLM_API_KEY=.*$', nova, texto)
else:
    texto = (texto.rstrip() + "\n" + nova + "\n") if texto else (nova + "\n")
open(arq, 'w', encoding='utf-8').write(texto)
PY
        chmod 600 .env 2>/dev/null || true
        ok ".env configurado (permissão 600)"
    fi
fi

# 5) Smoke test ------------------------------------------------------------
titulo "5/5  Smoke test"

if ./implantacao >/dev/null 2>&1; then
    ok "CLI responde"
else
    warn "CLI retornou erro — verifique manualmente:  cd $DIR_INSTALACAO && ./implantacao"
fi

# Próximos passos ----------------------------------------------------------
echo
echo "==============================================="
printf "${GREEN}✓ Instalação concluída${NC}\n"
echo "==============================================="
echo
printf "${BOLD}Próximos passos:${NC}\n\n"
echo  "  1. Entre no diretório do projeto:"
printf "     ${BLUE}cd %s${NC}\n\n" "$DIR_INSTALACAO"
echo  "  2. RECOMENDADO: valide conectividade com o provider LLM antes de usar"
echo  "     dados reais. Roda uma chamada mínima ao gateway e confirma que"
echo  "     rede/proxy/chave estão OK:"
printf "     ${BLUE}./implantacao novo teste${NC}\n"
printf "     ${BLUE}./implantacao demo teste${NC}\n"
echo  "     (se OK, pode remover:  rm -rf clientes/teste )"
echo
echo  "  3. Crie a estrutura para o cliente real:"
printf "     ${BLUE}./implantacao novo NOME_DO_CLIENTE${NC}\n\n"
echo  "  4. Coloque os arquivos do cliente (Excel/CSV) em:"
printf "     ${BLUE}clientes/NOME_DO_CLIENTE/raw/${NC}\n\n"
echo  "  5. Rode o orquestrador (decide o próximo passo):"
printf "     ${BLUE}./implantacao pilotar NOME_DO_CLIENTE${NC}\n\n"
echo  "  Documentação: README.md  e  ARCHITECTURE.md"
echo
