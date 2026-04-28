# Instalador do Pipeline de Implantacao RHTec/Mereo (Windows).
#
# One-liner (PowerShell):
#   iwr -useb https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.ps1 | iex
#
# O que faz:
#   1. Confere que existe Python 3.10+ e git
#   2. Clona o repo em .\mereo-implantacao\ (ou git pull se ja existe)
#   3. Cria .venv e instala requirements
#   4. Pergunta a MEREO_LLM_API_KEY e escreve em .env
#   5. Roda um smoke test
#   6. Imprime os proximos passos
#
# Variaveis de ambiente reconhecidas:
#   DIR_INSTALACAO     - pasta-alvo (default: mereo-implantacao)
#   MEREO_LLM_API_KEY  - pula o prompt interativo se ja estiver definida

$ErrorActionPreference = "Stop"

# UTF-8 no console para imprimir os icones e textos acentuados.
try {
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
} catch {}

function Write-OK    { param($m) Write-Host "[OK] $m"   -ForegroundColor Green }
function Write-Info  { param($m) Write-Host "[..] $m"   -ForegroundColor Cyan }
function Write-Warn2 { param($m) Write-Host "[!!] $m"   -ForegroundColor Yellow }
function Write-Err   { param($m) Write-Host "[XX] $m"   -ForegroundColor Red; exit 1 }
function Write-Tit   { param($m) Write-Host "`n$m"      -ForegroundColor White -BackgroundColor DarkBlue }

$RepoUrl = "https://github.com/arkhibr/mereo-implantacao.git"
$DirInstalacao = if ($env:DIR_INSTALACAO) { $env:DIR_INSTALACAO } else { "mereo-implantacao" }

Write-Host "==============================================="
Write-Host "  Pipeline de Implantacao RHTec/Mereo"
Write-Host "  Instalador (Windows)"
Write-Host "==============================================="

# 1) Pre-requisitos --------------------------------------------------------
Write-Tit "1/5  Verificando pre-requisitos"

$python = $null
foreach ($cmd in @("python", "py", "python3")) {
    $existe = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $existe) { continue }

    $out = & $cmd -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"
        $python = $cmd
        Write-OK "Python $ver  ($cmd)"
        break
    }
}

if (-not $python) {
    Write-Err @"
Python 3.10+ nao encontrado.

  Instale a partir de:
    https://www.python.org/downloads/windows/

  IMPORTANTE: marque 'Add python.exe to PATH' na instalacao.
  Depois rode este instalador novamente.
"@
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Err @"
git nao encontrado.

  Instale a partir de:
    https://git-scm.com/download/win

  Depois rode este instalador novamente.
"@
}
Write-OK "git encontrado"

# 2) Clonar / atualizar ----------------------------------------------------
Write-Tit "2/5  Obtendo o codigo"

if (Test-Path "$DirInstalacao\.git") {
    Write-Info "Ja existe um clone em .\$DirInstalacao -- atualizando"
    Push-Location $DirInstalacao
    try {
        git pull --ff-only --quiet
        Write-OK "Atualizado para a ultima versao"
    } catch {
        Write-Warn2 "git pull falhou; prosseguindo com a versao local"
    }
}
elseif (Test-Path $DirInstalacao) {
    Write-Err ".\$DirInstalacao existe mas nao e um clone do repositorio. Remova-o ou rode em outro diretorio."
}
else {
    Write-Info "Clonando $RepoUrl em .\$DirInstalacao"
    git clone --quiet $RepoUrl $DirInstalacao
    if ($LASTEXITCODE -ne 0) { Write-Err "Falha ao clonar." }
    Push-Location $DirInstalacao
    Write-OK "Clone concluido"
}

# 3) venv + dependencias ---------------------------------------------------
Write-Tit "3/5  Ambiente virtual e dependencias"

if (-not (Test-Path ".venv")) {
    Write-Info "Criando .venv"
    & $python -m venv .venv
}

$pipExe = ".\.venv\Scripts\pip.exe"
Write-Info "Instalando dependencias (pode levar 1-2 min)"
& $pipExe install --quiet --disable-pip-version-check --upgrade pip
& $pipExe install --quiet --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Write-Err "Falha ao instalar dependencias." }
Write-OK "Dependencias prontas"

# 4) .env ------------------------------------------------------------------
Write-Tit "4/5  Configuracao da chave do provider LLM"

$envOk = $false
if (Test-Path ".env") {
    $linha = Select-String -Path .env -Pattern "^MEREO_LLM_API_KEY=.." -Quiet
    if ($linha) { $envOk = $true }
}

if ($envOk) {
    Write-OK ".env ja existe e tem MEREO_LLM_API_KEY preenchida -- preservando"
}
else {
    if (-not (Test-Path ".env")) { Copy-Item .env.example .env }

    if ($env:MEREO_LLM_API_KEY) {
        Write-Info "Usando MEREO_LLM_API_KEY do ambiente"
        $chave = $env:MEREO_LLM_API_KEY
    }
    else {
        Write-Host
        Write-Host "Cole sua chave do provider LLM (ex: Abacus RouteLLM)."
        Write-Host "Pode deixar em branco e editar .env manualmente depois."
        $chave = Read-Host "Chave"
    }

    if ([string]::IsNullOrWhiteSpace($chave)) {
        Write-Warn2 "Chave vazia -- edite .\$DirInstalacao\.env antes de rodar agentes LLM"
    }
    else {
        $env:CHAVE = $chave
        # Here-string single-quoted (@'...'@) NAO interpola variaveis PowerShell.
        $script = @'
import os, re
arq = ".env"
texto = open(arq, encoding="utf-8").read()
nova = "MEREO_LLM_API_KEY=" + os.environ["CHAVE"]
if re.search(r"(?m)^MEREO_LLM_API_KEY=", texto):
    texto = re.sub(r"(?m)^MEREO_LLM_API_KEY=.*$", nova, texto)
else:
    texto = (texto.rstrip() + "\n" + nova + "\n") if texto else (nova + "\n")
open(arq, "w", encoding="utf-8").write(texto)
'@
        & $python -c $script
        Remove-Item env:CHAVE
        Write-OK ".env configurado"
    }
}

# 5) Smoke test ------------------------------------------------------------
Write-Tit "5/5  Smoke test"

$null = & ".\implantacao.bat" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "CLI responde"
} else {
    Write-Warn2 "CLI retornou erro -- verifique manualmente: cd $DirInstalacao; .\implantacao.bat"
}

# Proximos passos ----------------------------------------------------------
Write-Host
Write-Host "==============================================="
Write-Host "  Instalacao concluida" -ForegroundColor Green
Write-Host "==============================================="
Write-Host
Write-Host "Proximos passos:"
Write-Host
Write-Host "  1. Entre no diretorio do projeto:"
Write-Host "     cd $DirInstalacao" -ForegroundColor Cyan
Write-Host
Write-Host "  2. Crie a estrutura para um cliente novo:"
Write-Host "     .\implantacao.bat novo NOME_DO_CLIENTE" -ForegroundColor Cyan
Write-Host
Write-Host "  3. Coloque os arquivos do cliente (Excel/CSV) em:"
Write-Host "     clientes\NOME_DO_CLIENTE\raw\" -ForegroundColor Cyan
Write-Host
Write-Host "  4. Rode o orquestrador (decide o proximo passo):"
Write-Host "     .\implantacao.bat pilotar NOME_DO_CLIENTE" -ForegroundColor Cyan
Write-Host
Write-Host "  Documentacao: README.md  e  ARCHITECTURE.md"
Write-Host

Pop-Location
