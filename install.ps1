# Instalador do Pipeline de Implantacao RHTec/Mereo (Windows).
#
# One-liner (PowerShell, com bypass de execution policy):
#   powershell -NoProfile -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.ps1 | iex"
#
# Alternativa (salvar e rodar local, util quando ha SmartScreen ativo):
#   iwr -useb https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.ps1 -OutFile install.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
#
# O que faz:
#   1. Configura TLS 1.2 e detecta proxy do sistema (usa o do Windows se nao houver env)
#   2. Confere que existe Python 3.10+ e git (oferece winget quando ausente)
#   3. Clona o repo em .\mereo-implantacao\ (ou baixa ZIP se git falhar)
#   4. Cria .venv e instala requirements
#   5. Pergunta a MEREO_LLM_API_KEY e escreve em .env
#   6. Roda um smoke test real (importa as dependencias do venv)
#   7. Imprime os proximos passos
#
# Variaveis de ambiente reconhecidas:
#   DIR_INSTALACAO     - pasta-alvo (default: mereo-implantacao)
#   MEREO_LLM_API_KEY  - pula o prompt interativo se ja estiver definida
#   HTTP_PROXY/HTTPS_PROXY - usados se ja definidos; senao detecta do Windows

$ErrorActionPreference = "Stop"

# UTF-8 no console para imprimir acentuados.
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# Salva o pwd inicial para que qualquer caminho de erro retorne pra ele,
# evitando deixar o usuario "preso" em diretorios aninhados quando o script
# rodar via 'iwr | iex' e abortar antes do Pop-Location final.
$Script:PwdInicial = (Get-Location).Path

function Write-OK    { param($m) Write-Host "[OK] $m"   -ForegroundColor Green }
function Write-Info  { param($m) Write-Host "[..] $m"   -ForegroundColor Cyan }
function Write-Warn2 { param($m) Write-Host "[!!] $m"   -ForegroundColor Yellow }
function Write-Err {
    param($m)
    Write-Host "[XX] $m" -ForegroundColor Red
    # Volta pro diretorio inicial para que erros nao deixem o usuario
    # com pwd dentro do clone. Tolerante a falhas (path pode ter sumido).
    try { Set-Location $Script:PwdInicial -ErrorAction Stop } catch {}
    exit 1
}
function Write-Tit   { param($m) Write-Host "`n$m"      -ForegroundColor White -BackgroundColor DarkBlue }

# Le uma linha do tty atual (funciona via "iwr | iex" tambem, pois o stdin do
# host PowerShell continua disponivel; em hosts nao-interativos cai no default).
function Read-Linha {
    param([string]$Pergunta, [string]$Default = "")
    try {
        return Read-Host $Pergunta
    } catch {
        if ($Default) { return $Default }
        return ""
    }
}

$RepoUrl  = "https://github.com/arkhibr/mereo-implantacao.git"
$ZipUrl   = "https://github.com/arkhibr/mereo-implantacao/archive/refs/heads/main.zip"
$DirInstalacao = if ($env:DIR_INSTALACAO) { $env:DIR_INSTALACAO } else { "mereo-implantacao" }

Write-Host "==============================================="
Write-Host "  Pipeline de Implantacao RHTec/Mereo"
Write-Host "  Instalador (Windows)"
Write-Host "==============================================="

# 0) TLS + Proxy ----------------------------------------------------------
Write-Tit "0/6  Rede (TLS e proxy)"

# Forca TLS 1.2 (PS 5.1 padrao Windows 10/11 ainda pode tentar TLS 1.0/1.1).
try {
    [Net.ServicePointManager]::SecurityProtocol = `
        [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    Write-OK "TLS 1.2 habilitado"
} catch {
    Write-Warn2 "Nao consegui forcar TLS 1.2 (PowerShell antigo); seguindo mesmo assim"
}

# Se nao houver proxy nas env vars, tenta detectar do Windows (Internet Options).
function Detectar-ProxySistema {
    try {
        $proxy = [System.Net.WebRequest]::GetSystemWebProxy()
        $alvo  = [Uri]"https://github.com"
        $uri   = $proxy.GetProxy($alvo)
        if ($uri -and $uri.AbsoluteUri -ne $alvo.AbsoluteUri) {
            return $uri.AbsoluteUri.TrimEnd('/')
        }
    } catch {}
    return $null
}

if ($env:HTTPS_PROXY -or $env:HTTP_PROXY) {
    $px = if ($env:HTTPS_PROXY) { $env:HTTPS_PROXY } else { $env:HTTP_PROXY }
    Write-OK "Proxy ja definido no ambiente: $px"
} else {
    $sysProxy = Detectar-ProxySistema
    if ($sysProxy) {
        $env:HTTPS_PROXY = $sysProxy
        $env:HTTP_PROXY  = $sysProxy
        Write-OK "Proxy do Windows detectado: $sysProxy (exportado para esta sessao)"
        Write-Info "Se o proxy exigir usuario/senha, defina HTTPS_PROXY=http://USR:PWD@host:porta antes de reexecutar"
    } else {
        Write-Info "Sem proxy detectado (acesso direto)"
    }
}

# Faz iwr/Invoke-WebRequest usar credenciais default do Windows no proxy (NTLM).
try {
    [System.Net.WebRequest]::DefaultWebProxy = [System.Net.WebRequest]::GetSystemWebProxy()
    [System.Net.WebRequest]::DefaultWebProxy.Credentials = [System.Net.CredentialCache]::DefaultNetworkCredentials
} catch {}

# Verifica se PIP_CERT / REQUESTS_CA_BUNDLE foram setadas mas apontam para um
# arquivo que nao existe. Sintoma classico: usuario seguiu a doc e copiou o
# placeholder 'C:\caminho\proxy-root.pem' literalmente. Sem tratamento, o pip
# falha logo na fase 3 com mensagem confusa.
foreach ($var in @("PIP_CERT", "REQUESTS_CA_BUNDLE")) {
    $valor = [Environment]::GetEnvironmentVariable($var, "Process")
    if (-not $valor) { $valor = [Environment]::GetEnvironmentVariable($var, "User") }
    if ($valor -and -not (Test-Path $valor)) {
        Write-Warn2 "$var aponta para um caminho que nao existe: $valor"
        Write-Info "Removendo $var desta sessao para o pip funcionar."
        Remove-Item "Env:$var" -ErrorAction SilentlyContinue
        $persistente = [Environment]::GetEnvironmentVariable($var, "User")
        if ($persistente) {
            Write-Warn2 "Atencao: $var tambem esta gravada no perfil do usuario."
            Write-Info "Para remover permanentemente (em outra sessao): [Environment]::SetEnvironmentVariable('$var', `$null, 'User')"
        }
    }
}

# 1) Pre-requisitos --------------------------------------------------------
Write-Tit "1/6  Verificando pre-requisitos"

function Encontrar-Python {
    foreach ($cmd in @("python", "py", "python3")) {
        $existe = Get-Command $cmd -ErrorAction SilentlyContinue
        if (-not $existe) { continue }
        try {
            & $cmd -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" 2>$null
            if ($LASTEXITCODE -eq 0) {
                $ver = & $cmd -c "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')"
                return [pscustomobject]@{ Cmd = $cmd; Ver = $ver }
            }
        } catch {}
    }
    return $null
}

function Atualizar-PathDaSessao {
    $u = [Environment]::GetEnvironmentVariable("Path", "User")
    $m = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:Path = ($m, $u, $env:Path) -join ';'
}

$python = Encontrar-Python
if (-not $python) {
    Write-Warn2 "Python 3.10+ nao encontrado"

    $temWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
    if ($temWinget) {
        Write-Host
        Write-Host "Posso instalar o Python 3.12 automaticamente via winget."
        $resp = Read-Linha "Instalar agora? [S/n]" "S"
        if ($resp -notmatch '^[nN]') {
            Write-Info "Rodando: winget install --id Python.Python.3.12 -e --silent --accept-source-agreements --accept-package-agreements"
            & winget install --id Python.Python.3.12 -e --silent --accept-source-agreements --accept-package-agreements
            if ($LASTEXITCODE -ne 0) {
                Write-Warn2 "winget retornou erro; pode ser politica corporativa bloqueando o repositorio"
            }
            Atualizar-PathDaSessao
            $python = Encontrar-Python
        }
    }

    if (-not $python) {
        Write-Err @"
Python 3.10+ nao encontrado e instalacao automatica indisponivel.

  Instale manualmente:
    https://www.python.org/downloads/windows/

  IMPORTANTE: marque 'Add python.exe to PATH' durante a instalacao.
  Apos instalar, FECHE este terminal, abra um novo e rode o instalador novamente.

  Se o download estiver bloqueado por proxy/firewall, pode usar a Microsoft
  Store: procure 'Python 3.12' e instale por la.
"@
    }
}
Write-OK "Python $($python.Ver)  ($($python.Cmd))"
$python = $python.Cmd

# git e desejavel mas nao obrigatorio (cai pra ZIP se faltar).
$temGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
if (-not $temGit) {
    Write-Warn2 "git nao encontrado"

    $temWinget = [bool](Get-Command winget -ErrorAction SilentlyContinue)
    if ($temWinget) {
        Write-Host
        $resp = Read-Linha "Instalar git via winget? [S/n]" "S"
        if ($resp -notmatch '^[nN]') {
            Write-Info "Rodando: winget install --id Git.Git -e --silent --accept-source-agreements --accept-package-agreements"
            & winget install --id Git.Git -e --silent --accept-source-agreements --accept-package-agreements
            Atualizar-PathDaSessao
            $temGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
        }
    }

    if (-not $temGit) {
        Write-Warn2 "Seguindo sem git -- vou baixar o repo como ZIP (atualizacoes futuras precisarao de git ou re-execucao)"
    }
}
if ($temGit) { Write-OK "git encontrado" }

# 2) Obter o codigo --------------------------------------------------------
Write-Tit "2/6  Obtendo o codigo"

function Baixar-Zip {
    param([string]$Destino)

    $tmpZip = Join-Path $env:TEMP ("mereo-impl-" + [guid]::NewGuid().ToString("N") + ".zip")
    $tmpDir = Join-Path $env:TEMP ("mereo-impl-" + [guid]::NewGuid().ToString("N"))

    Write-Info "Baixando ZIP: $ZipUrl"
    try {
        Invoke-WebRequest -Uri $ZipUrl -OutFile $tmpZip -UseBasicParsing
    } catch {
        Write-Err @"
Falha ao baixar o ZIP do GitHub.
  Mensagem: $($_.Exception.Message)

  Provaveis causas em ambiente corporativo:
    - Proxy bloqueando github.com / raw.githubusercontent.com
    - SSL inspection (a cadeia de cert do proxy nao e confiavel pelo Windows)
    - SmartScreen bloqueando o download

  Alternativa manual:
    1) Em uma maquina com acesso, baixe:  $ZipUrl
    2) Copie o arquivo para esta maquina e descompacte
    3) Renomeie a pasta para '$Destino' e rode este instalador de dentro dela
"@
    }

    Write-Info "Descompactando"
    Expand-Archive -Path $tmpZip -DestinationPath $tmpDir -Force

    # O zip do GitHub gera <repo>-main\ ; renomeia pro destino final.
    $extraido = Get-ChildItem $tmpDir | Select-Object -First 1
    Move-Item -Path $extraido.FullName -Destination $Destino
    Remove-Item -Recurse -Force $tmpDir, $tmpZip -ErrorAction SilentlyContinue
}

if (Test-Path "$DirInstalacao\.git") {
    Write-Info "Ja existe um clone em .\$DirInstalacao -- atualizando"
    Push-Location $DirInstalacao
    try {
        if ($temGit) {
            git pull --ff-only --quiet
            if ($LASTEXITCODE -eq 0) {
                Write-OK "Atualizado para a ultima versao"
            } else {
                Write-Warn2 "git pull falhou; prosseguindo com a versao local"
            }
        }
    } catch {
        Write-Warn2 "git pull falhou ($($_.Exception.Message)); prosseguindo com a versao local"
    }
}
elseif (Test-Path $DirInstalacao) {
    if (Test-Path "$DirInstalacao\cli.py") {
        Write-Info "Pasta .\$DirInstalacao ja existe e parece ser o projeto -- usando"
        Push-Location $DirInstalacao
    } else {
        Write-Err ".\$DirInstalacao existe mas nao parece ser um clone do repositorio. Remova-o ou rode em outro diretorio."
    }
}
else {
    $cloneOk = $false
    if ($temGit) {
        Write-Info "Clonando $RepoUrl em .\$DirInstalacao"
        $cloneOut = & git clone --quiet $RepoUrl $DirInstalacao 2>&1
        if ($LASTEXITCODE -eq 0) {
            $cloneOk = $true
            Write-OK "Clone concluido"
        } else {
            $msg = ($cloneOut -join "`n")
            Write-Warn2 "git clone falhou:"
            Write-Host $msg -ForegroundColor DarkGray
            if ($msg -match "SSL|certificate") {
                Write-Warn2 "Sintoma de SSL inspection do proxy corporativo. Vou tentar via ZIP."
            } elseif ($msg -match "proxy|Could not resolve|timed out") {
                Write-Warn2 "Sintoma de proxy/conectividade. Vou tentar via ZIP."
            }
        }
    }

    if (-not $cloneOk) {
        Baixar-Zip -Destino $DirInstalacao
        Write-OK "Codigo extraido em .\$DirInstalacao"
    }

    Push-Location $DirInstalacao
}

# 3) venv + dependencias ---------------------------------------------------
Write-Tit "3/6  Ambiente virtual e dependencias"

if (-not (Test-Path ".venv")) {
    Write-Info "Criando .venv"
    & $python -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Err @"
Falha ao criar .venv.
  Causas comuns:
    - Pacote 'venv' nao incluso (Python da Microsoft Store as vezes vem sem)
    - Permissao negada na pasta atual

  Solucao: reinstale o Python a partir de python.org marcando 'Add to PATH'.
"@
    }
}

$pipExe    = ".\.venv\Scripts\pip.exe"
$pythonVenv = ".\.venv\Scripts\python.exe"

Write-Info "Atualizando pip"
$pipOut = & $pipExe install --disable-pip-version-check --upgrade pip 2>&1
if ($LASTEXITCODE -ne 0) {
    $msg = ($pipOut -join "`n")
    Write-Warn2 "Falha ao atualizar pip; tentando seguir com a versao atual"
    Write-Host $msg -ForegroundColor DarkGray
}

Write-Info "Instalando dependencias (pode levar 1-2 min)"
$pipOut = & $pipExe install --disable-pip-version-check -r requirements.txt 2>&1
if ($LASTEXITCODE -ne 0) {
    $msg = ($pipOut -join "`n")
    Write-Host $msg -ForegroundColor DarkGray

    if ($msg -match "SSL.*VERIFY_FAILED|certificate verify failed|SSLError") {
        Write-Err @"
pip falhou por SSL (provavelmente inspecao SSL do proxy corporativo).

  Solucoes (peca ao TI o cert raiz do proxy, em formato PEM):
    1) Apontar pip para o cert:
         setx PIP_CERT "C:\caminho\proxy-root.pem"
       e reabra o terminal
    2) Adicionar o cert ao Trust Store do Windows
    3) Em ULTIMO caso (apenas se autorizado pelo TI):
         $env:PIP_INDEX_URL = 'https://pypi.org/simple'
         & $pipExe install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
"@
    }
    elseif ($msg -match "ProxyError|Cannot connect to proxy|getaddrinfo failed|Could not resolve") {
        Write-Err @"
pip falhou por proxy/rede.

  Confirme que o proxy corporativo esta certo:
    `$env:HTTPS_PROXY = 'http://USR:PWD@proxy.empresa.local:8080'
    `$env:HTTP_PROXY  = '`$env:HTTPS_PROXY'
  Depois rode novamente o instalador.
"@
    }
    else {
        Write-Err "Falha ao instalar dependencias. Veja a saida acima."
    }
}
Write-OK "Dependencias prontas"

# 4) .env ------------------------------------------------------------------
Write-Tit "4/6  Configuracao da chave do provider LLM"

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
        $chave = Read-Linha "Chave" ""
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
Write-Tit "5/6  Smoke test (importando dependencias do venv)"

$smokeOut = & $pythonVenv -c "import pandas, openpyxl, openai, chardet; print('imports OK')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-OK "Imports OK ($($smokeOut -join ' '))"
} else {
    $msg = ($smokeOut -join "`n")
    Write-Warn2 "Imports falharam:"
    Write-Host $msg -ForegroundColor DarkGray
    Write-Warn2 "Verifique manualmente:  cd $DirInstalacao; .\.venv\Scripts\python.exe -c `"import pandas, openpyxl, openai, chardet`""
}

# 6) Resumo ----------------------------------------------------------------
Write-Tit "6/6  Resumo"
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
Write-Host "  2. RECOMENDADO: valide conectividade com o provider LLM antes de"
Write-Host "     usar dados reais. Roda uma chamada minima ao gateway e confirma"
Write-Host "     que rede/proxy/chave estao OK:"
Write-Host "     .\implantacao.bat novo teste" -ForegroundColor Cyan
Write-Host "     .\implantacao.bat demo teste" -ForegroundColor Cyan
Write-Host "     (se OK, pode remover:  Remove-Item -Recurse -Force clientes\teste )"
Write-Host
Write-Host "  3. Crie a estrutura para o cliente real:"
Write-Host "     .\implantacao.bat novo NOME_DO_CLIENTE" -ForegroundColor Cyan
Write-Host
Write-Host "  4. Coloque os arquivos do cliente (Excel/CSV) em:"
Write-Host "     clientes\NOME_DO_CLIENTE\raw\" -ForegroundColor Cyan
Write-Host
Write-Host "  5. Rode o orquestrador (decide o proximo passo):"
Write-Host "     .\implantacao.bat pilotar NOME_DO_CLIENTE" -ForegroundColor Cyan
Write-Host
Write-Host "  Documentacao: README.md  e  ARCHITECTURE.md"
Write-Host

Pop-Location
