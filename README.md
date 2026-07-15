# Pipeline de Implantação RHTec/Mereo

Pipeline em Python que transforma os dados brutos enviados por clientes corporativos nos arquivos finais para importação na plataforma RHTec/Mereo. Combina agentes determinísticos (transformações) com agentes LLM (decisões semânticas e diagnóstico), e tem um modelo de **human-in-the-loop assíncrono** para os pontos onde a decisão precisa do consultor.

> **Para quem é:** equipe de implantação Mereo. Não é necessário saber programar para operar — é necessário ter familiaridade com terminal e com a estrutura dos templates da plataforma.

---

## O que o pipeline faz

![Fluxo do pipeline](docs/arquitetura/00_fluxo_pipeline.svg)

> Fonte: [`docs/arquitetura/00_fluxo_pipeline.puml`](docs/arquitetura/00_fluxo_pipeline.puml). Para regenerar: `cd docs/arquitetura && make`.

Cada etapa pode ser rodada isoladamente. O agente **orquestrador** (LLM) inspeciona o estado e decide a próxima ação razoável.

---

## Pré-requisitos

- **Python 3.10+** (`python3 --version` no Linux/macOS, `python --version` no Windows)
- **git** (para clonar)
- **Chave de API de um provider LLM compatível com OpenAI**. Default: [Abacus RouteLLM](https://routellm.abacus.ai). Outros providers (OpenAI direto, Together, Groq, vLLM local) funcionam ajustando a `base_url`.
- Sistema operacional: **Linux, macOS ou Windows**. No Windows funciona em cmd.exe e PowerShell nativos (não precisa de WSL).

---

## Atualização

Se o pipeline já está instalado e houve uma atualização, basta puxar as mudanças — não é necessário rodar o instalador novamente:

```bash
cd mereo-implantacao
git pull
```

Confira a versão instalada rodando `./implantacao` (aparece ao lado do nome) ou:

```bash
git pull && ./implantacao grupos
```

> [!NOTE]
> **v0.3.0 — padrões da plataforma + output em Excel.** Nenhuma dependência
> nova — o `git pull` acima já habilita tudo. O que muda:
>
> - **Output final em `.xlsx`** (formato que a plataforma importa), em vez de CSV.
> - **Códigos saem como estão na base do cliente** — sem os prefixos `AREA_`/`METI_`/`IND_`.
> - **Campos codificados traduzidos e validados**: polaridade, agregação, definição
>   do valor, frequência e unidades de medida usam as tabelas oficiais da
>   plataforma; texto onde se espera código é bloqueado antes do output.
> - **Indicadores gerados junto com as metas** quando o cliente não tem fonte
>   própria; periodicidade (mensal × anual) detectada pela estrutura dos valores.
> - De-para manuais opcionais em `config/` (pilares, grupos de permissão,
>   indicadores, áreas, metas) — ver `sops/03_transformacao/sop_transformacao.md`.

> [!IMPORTANT]
> **Se você já processou algum cliente em versão anterior**, remova os dicionários
> gerados automaticamente antes de reprocessar — a partir da v0.3.0 eles são
> interpretados como de-para manual e reintroduziriam os prefixos antigos:
>
> ```bash
> rm clientes/<cliente>/config/dicionario_{areas,metas_*,indicadores}.csv
> ```

> [!NOTE]
> **v0.2.0 — módulo de Competências.** Esta atualização adiciona o módulo de
> competências (catálogo + formulários de avaliação), listado em
> `./implantacao grupos`. Nenhuma dependência nova é necessária — o `git pull`
> acima já habilita a feature.

---

## Instalação

### Modo recomendado: instalador automático

**Linux / macOS** (Bash):

```bash
curl -fsSL https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.sh | bash
```

**Windows** (PowerShell — máquina pessoal):

```powershell
iwr -useb https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.ps1 | iex
```

**Windows** (PowerShell — ambiente corporativo, com bypass de execution policy):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.ps1 | iex"
```

O instalador:
1. Configura TLS 1.2 e detecta proxy do Windows (usa o do sistema se não houver `HTTPS_PROXY`)
2. Confere que existe Python 3.10+ e git — oferece instalação automática via `winget` quando ausente
3. Clona o repo em `./mereo-implantacao/` (ou baixa o ZIP se git falhar / não estiver disponível)
4. Cria `.venv` e instala dependências
5. Pergunta a chave do provider LLM e escreve no `.env`
6. Roda um smoke test que importa as dependências do venv (detecta falha real, não só CLI vazio)

> Os scripts estão versionados no repo: [`install.sh`](install.sh) e [`install.ps1`](install.ps1) — você pode inspecionar antes de rodar.

Se houver um erro de rede/SSL/proxy durante a instalação, veja a seção [Ambiente corporativo](#instalação-em-ambiente-corporativo) abaixo.

#### Após instalar — valide a conectividade LLM

O smoke test do instalador confirma que as dependências Python estão instaladas, mas **não** confirma que sua rede alcança o gateway do provider LLM nem que a chave responde. Antes de tentar com dados reais, rode o agente de smoke test (faz uma chamada mínima ao gateway):

```bash
# Linux/macOS
./implantacao novo teste
./implantacao demo teste

# Windows
.\implantacao.bat novo teste
.\implantacao.bat demo teste
```

Se ambos rodarem com status `concluida`, sua instalação está pronta. Pode apagar o cliente de teste depois:

```bash
rm -rf clientes/teste              # Linux/macOS
Remove-Item -Recurse -Force clientes\teste   # Windows
```

Se o `demo` falhar com erro de rede ou autenticação, antes de tentar dados reais resolva: confirme `MEREO_LLM_API_KEY` no `.env`, confirme que a rede corporativa não está bloqueando `routellm.abacus.ai` (ou o gateway que você configurou em `MEREO_LLM_BASE_URL`), e veja [Ambiente corporativo](#instalação-em-ambiente-corporativo) para proxy/SSL.

### Modo manual

#### Linux / macOS

```bash
git clone https://github.com/arkhibr/mereo-implantacao.git
cd mereo-implantacao

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# edite .env e preencha MEREO_LLM_API_KEY com sua chave do provider
```

Comandos rodam com `./implantacao <comando> <cliente>`.

#### Windows (PowerShell ou cmd.exe)

```powershell
git clone https://github.com/arkhibr/mereo-implantacao.git
cd mereo-implantacao

python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

copy .env.example .env
notepad .env
# preencha MEREO_LLM_API_KEY com sua chave do provider
```

Comandos rodam com `implantacao.bat <comando> <cliente>` (no PowerShell, use `.\implantacao.bat`).

> O `.env` é lido pelo próprio Python — funciona igual em Linux, macOS e Windows. Variáveis já definidas no ambiente têm prioridade sobre o `.env`.

### Instalação em ambiente corporativo

Em máquinas corporativas (Windows) é comum encontrar bloqueios. Os pontos abaixo cobrem os cenários mais frequentes — o `install.ps1` já trata vários deles automaticamente, mas vale conhecer.

#### 1. Execution Policy do PowerShell

Em máquina nova com policy `Restricted` ou `AllSigned`, `iwr | iex` não roda. Use o one-liner com bypass de escopo (não muda a policy global, só da sessão):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -Command "iwr -useb https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.ps1 | iex"
```

Se a empresa bloqueia até o `-ExecutionPolicy Bypass` por GPO, baixe o script primeiro e rode local:

```powershell
iwr -useb https://raw.githubusercontent.com/arkhibr/mereo-implantacao/main/install.ps1 -OutFile install.ps1
Unblock-File .\install.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
```

#### 2. Proxy corporativo

O instalador detecta automaticamente o proxy do Windows (Internet Options) e exporta para `HTTPS_PROXY`/`HTTP_PROXY` na sessão. Se o proxy exige usuário/senha, defina antes de rodar:

```powershell
$env:HTTPS_PROXY = "http://USUARIO:SENHA@proxy.empresa.local:8080"
$env:HTTP_PROXY  = $env:HTTPS_PROXY
```

Caracteres especiais na senha (`@`, `:`, `#`, `/`) precisam ser URL-encoded (ex.: `@` → `%40`).

#### 3. Inspeção SSL (TLS interception)

Sintoma: `pip` ou `git` falham com `SSL: CERTIFICATE_VERIFY_FAILED` ou `unable to get local issuer certificate`. Significa que o proxy reescreve o tráfego HTTPS com um certificado próprio, que o Python/git não conhece.

Peça ao TI o certificado raiz do proxy (formato PEM) e troque os comandos abaixo, **substituindo `<CAMINHO\REAL\AQUI>` pelo caminho de verdade do .pem na sua máquina** (não copie o exemplo literal — ele é placeholder):

```powershell
# Para pip — substitua <CAMINHO\REAL\AQUI> pelo caminho do seu .pem
setx PIP_CERT "<CAMINHO\REAL\AQUI>\proxy-root.pem"

# Para o requests do Python (alguns componentes usam esta var)
setx REQUESTS_CA_BUNDLE "<CAMINHO\REAL\AQUI>\proxy-root.pem"

# Para git
git config --global http.sslCAInfo "<CAMINHO\REAL\AQUI>\proxy-root.pem"
```

Reabra o terminal depois do `setx`. **Não use `--trusted-host` como solução permanente** — desabilita verificação SSL e expõe a outros riscos.

> [!WARNING]
> Se você seguiu este passo e digitou um caminho falso (ex.: `C:\caminho\proxy-root.pem`), o `pip` vai quebrar em **toda** instalação futura (mesmo sem proxy). Para desfazer, em qualquer sessão PowerShell:
>
> ```powershell
> [Environment]::SetEnvironmentVariable("PIP_CERT", $null, "User")
> [Environment]::SetEnvironmentVariable("REQUESTS_CA_BUNDLE", $null, "User")
> git config --global --unset http.sslCAInfo
> ```
>
> Reabra o terminal depois. O instalador atual também detecta esse caso automaticamente e remove a variável da sessão antes de chamar pip — mas a versão **persistente** segue gravada até você desfazer manualmente.

#### 4. SmartScreen / Windows Defender

Scripts baixados da internet podem ser bloqueados pelo Mark-of-the-Web. Se aparecer aviso ao executar `install.ps1` salvo localmente:

```powershell
Unblock-File .\install.ps1
```

#### 5. Sem `git` na máquina

O instalador detecta e oferece instalação via `winget install --id Git.Git`. Se `winget` também estiver bloqueado, ele cai automaticamente para baixar o repositório como ZIP.

#### 6. Sem Python na máquina

Mesmo comportamento: oferece `winget install --id Python.Python.3.12`. Se nada funcionar, instale manualmente da [página oficial](https://www.python.org/downloads/windows/) marcando **Add python.exe to PATH** e reabra o terminal.

#### 7. Modo totalmente offline (air-gapped)

Em uma máquina com acesso, baixe:

```bash
curl -L -o mereo.zip https://github.com/arkhibr/mereo-implantacao/archive/refs/heads/main.zip
```

Transfira o ZIP para a máquina-alvo, descompacte, renomeie a pasta para `mereo-implantacao` e rode o `install.ps1` de dentro dela. As dependências Python (`pip install -r requirements.txt`) ainda precisam de acesso ao PyPI — para verdadeiro air-gap, é preciso pré-baixar os wheels com `pip download -r requirements.txt -d wheels/` e instalar com `pip install --no-index --find-links wheels/ -r requirements.txt`.

### Variáveis de ambiente

| Variável | Default | Função |
|---|---|---|
| `MEREO_LLM_API_KEY` | *(obrigatória)* | Chave do provider LLM |
| `MEREO_LLM_BASE_URL` | `https://routellm.abacus.ai/v1` | Endpoint do provider |
| `MEREO_LLM_MODEL` | `gpt-5` | Modelo a usar |
| `MEREO_MAX_TOKENS` | `16000` | Limite por resposta |
| `MEREO_MAX_ITERACOES` | `50` | Limite de turnos por sessão |

O `.env` é carregado automaticamente pelo `cli.py` (em qualquer SO).

---

```
 ██████╗ ███████╗███╗   ███╗ ██████╗
 ██╔══██╗██╔════╝████╗ ████║██╔═══██╗
 ██║  ██║█████╗  ██╔████╔██║██║   ██║
 ██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║
 ██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝
 ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝
 🎬  apresentação ao vivo do pipeline
```

## 🎬 Demo — apresentação ao vivo

> [!NOTE]
> Use esta seção quando quiser **mostrar o pipeline rodando** com pausas explicativas, em treinamento ou apresentação. **Não é o fluxo de uso real com um cliente** — para isso veja a próxima seção.

Para executar a demo:

```bash
./demo.sh demo
```

O script roda os 3 comandos (`pilotar` → `validar` → `responder`) com narração e pausa entre cada um. Pressione **Enter** para avançar, **Ctrl+C** para abortar. Funciona em qualquer cliente que tenha `mapeamento.json` travado e `raw/` populado:

```bash
./demo.sh acme              # cliente acme
./demo.sh acme --no-reset   # não limpa staging/output antes (útil pra rerun)
```

---

```
 ██╗   ██╗███████╗ ██████╗     ██████╗ ███████╗ █████╗ ██╗
 ██║   ██║██╔════╝██╔═══██╗    ██╔══██╗██╔════╝██╔══██╗██║
 ██║   ██║███████╗██║   ██║    ██████╔╝█████╗  ███████║██║
 ██║   ██║╚════██║██║   ██║    ██╔══██╗██╔══╝  ██╔══██║██║
 ╚██████╔╝███████║╚██████╔╝    ██║  ██║███████╗██║  ██║███████╗
  ╚═════╝ ╚══════╝ ╚═════╝     ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝
 🚀  implantação completa de um cliente real
```

## 🚀 Uso real — implantação de um cliente

> [!IMPORTANT]
> **Esta é a seção principal do README.** Cobre o fluxo de ponta a ponta para um cliente real, do recebimento dos arquivos brutos até o output pronto pra importar na plataforma RHTec/Mereo.

### Forma dos comandos

> [!IMPORTANT]
> **Todos os comandos rodam de dentro da pasta `mereo-implantacao/`** (a pasta criada pelo instalador). Antes de qualquer comando, faça `cd` pra ela:
>
> ```bash
> cd mereo-implantacao    # Linux/macOS
> cd mereo-implantacao    # Windows (cmd e PowerShell)
> ```
>
> Os caminhos `./implantacao` e `.\implantacao.bat` são **relativos à pasta atual** — fora dela não funcionam.

Todos os comandos seguem `<wrapper> <comando> <cliente>`:
- **Linux/macOS:** `./implantacao <comando> <cliente>`
- **Windows:** `implantacao.bat <comando> <cliente>` (ou `.\implantacao.bat` no PowerShell)

Os exemplos abaixo usam a forma Linux. No Windows, troque `./implantacao` por `implantacao.bat`. Use o wrapper sem argumentos para ver a ajuda — `./implantacao ajuda <comando>` (ou `<comando> --help`) detalha qualquer comando.

> [!TIP]
> Existem duas rotas equivalentes: a **determinista** (`analisar` + `transformar` — mais rápida, sem custo de LLM) e a **assistida por agentes** (`diagnosticar`, `mapear`, `validar`, `pilotar` — com análise narrativa e perguntas ao consultor). O passo a passo abaixo mostra a rota assistida; para a determinista, troque os passos 2–3 por `./implantacao analisar acme`.

### 1. Criar a estrutura para um cliente novo

```bash
./implantacao novo acme
```

Cria `clientes/acme/` com as subpastas (`raw/`, `config/`, `staging/`, `output/`, `relatorios/`). Coloque os arquivos enviados pelo cliente dentro de `clientes/acme/raw/`.

### 2. Diagnóstico

```bash
./implantacao diagnosticar acme
```

Agente LLM percorre `raw/`, perfilha cada Excel/CSV (abas, colunas, tipos, % de nulos, amostras), detecta erros de fórmula, duplicatas, PII, e produz:

- `clientes/acme/config/diagnostico.json` — dados estruturados
- `clientes/acme/config/diagnostico_resumo.md` — resumo legível

### 3. Mapeamento

```bash
./implantacao mapear acme
```

Agente LLM lê o diagnóstico e os templates da plataforma, decide qual arquivo/aba do cliente corresponde a cada entidade (`areas`, `colaboradores`, `indicadores`, `metas_individuais`, `metas_compartilhadas`, `metas_projeto`, `curva_alcance`) e mapeia campo a campo. Pode pausar para perguntar quando a fonte é ambígua (ver [Fluxo HITL](#fluxo-human-in-the-loop)).

Produz `clientes/acme/config/mapeamento.json`.

**Importante:** o mapeamento é uma sugestão — abra o JSON, revise, ajuste. Quando estiver satisfeito, adicione `"travado": true` no início do arquivo. Sem isso, etapas seguintes não podem confiar no mapeamento.

### 4. Transformações + validação

Modo determinístico clássico (todas as transformações de uma vez):

```bash
./implantacao transformar acme
```

Modo dirigido por LLM (decide o que falta, age e/ou recomenda próximos passos):

```bash
./implantacao pilotar acme
```

O `pilotar` é o orquestrador LLM. Ele inspeciona o estado em disco, executa as transformações pendentes e — se ainda faltar diagnóstico, mapeamento ou validação — recomenda os comandos correspondentes.

#### Se a validação bloquear: o ciclo de correção com de-para

A validação impede que saia qualquer coisa que a plataforma rejeitaria — o caso mais comum é **texto onde a plataforma espera código** (ex.: "Metas Setoriais" no campo do pilar estratégico, "Administrador Global" no grupo de permissões). O ciclo de correção:

```bash
# 1. veja o que bloqueou
cat clientes/acme/relatorios/relatorio_validacao.md

# 2. crie o de-para do tipo apontado (nome e cabeçalho corretos, sem decorar nada)
./implantacao depara acme pilares

# 3. preencha o CSV (uma linha por tradução), ex.:
#    id_origem;id_destino
#    Metas Setoriais;DZ001

# 4. rode de novo
./implantacao transformar acme
```

`./implantacao depara acme` (sem tipo) lista todos os de-para suportados e o status de cada um. Repita o ciclo até o status `aprovado`.

### 5. Validação final

```bash
./implantacao validar acme
```

Agente LLM valida cada arquivo de staging contra o template (schema, campos obrigatórios, tipos, duplicatas em chave única) e a integridade referencial entre as tabelas. Decide entre três estados:

- **`aprovado`** — copia para `output/<data>/` direto.
- **`aprovado_com_ressalvas`** — copia após confirmação humana via HITL.
- **`bloqueado`** — não copia; relatório explica os achados críticos. Se o motivo for texto em campo de código, use o [ciclo de correção com de-para](#se-a-validação-bloquear-o-ciclo-de-correção-com-de-para).

Produz `clientes/acme/relatorios/relatorio_validacao.md` (com seção narrativa) e, quando aprovado, `clientes/acme/output/<data>/Import_*.xlsx` — planilhas Excel no formato que a plataforma importa.

### 6. Importar na plataforma Mereo

Os arquivos em `output/<data>/` seguem o nome dos templates da plataforma e podem ser importados diretamente. **Respeite a ordem de dependência** — cada import referencia códigos do anterior:

1. **Áreas** → 2. **Colaboradores** (referenciam áreas) → 3. **Indicadores** → 4. **Metas** (referenciam áreas, colaboradores e indicadores) → 5. **Curva de Alcance e Valores** (referenciam metas).

É a mesma ordem que `./implantacao grupos` mostra: o núcleo primeiro, depois os módulos que dependem dele.

---

## Fluxo Human-in-the-loop

Os agentes LLM podem fazer perguntas ao consultor quando precisam de uma decisão de domínio. **A pausa é assíncrona** — o estado é gravado em disco e a sessão pode ser retomada de outro terminal, em outro horário.

### Quando você vê uma pausa

```
⏸ Status: PAUSADA_HITL
  Sessão: clientes/acme/sessoes/20260428_142037_a3f1c2

  ❓ Pergunta: Existem duas abas plausíveis para colaboradores. Qual usar?

     Opções:
       - Usar Plan1 (Evolução Midia) com login=CPF
       - Usar Colaboradores (IA Coleta) com login textual

  ► Para responder:  ./implantacao responder acme 20260428_142037_a3f1c2
```

A sessão fica esperando. Você pode fechar o terminal, voltar amanhã, e rodar:

```bash
./implantacao responder acme 20260428_142037_a3f1c2
```

O comando mostra a pergunta de novo, lê sua resposta do stdin (termine com Enter duplo) e o agente continua de onde parou.

### O que é gravado

Cada sessão fica em `clientes/<cliente>/sessoes/<id>/`:

```
metadata.json    — agente, status (ativa/pausada_hitl/concluida/erro), timestamps
prompt.md        — system prompt + tarefa inicial
transcript.jsonl — uma linha por mensagem da conversa
estado.json      — só existe quando pausada (informação para retomar)
```

Os transcripts servem como auditoria — você pode revisar exatamente o que o agente fez e perguntou.

---

## Estrutura de pastas de um cliente

```
clientes/acme/
├── raw/             ← arquivos brutos do cliente (somente leitura)
├── config/          ← artefatos de planejamento
│   ├── diagnostico.json
│   ├── diagnostico_resumo.md
│   ├── mapeamento.json
│   ├── dicionario_areas.csv      (de-para manual, opcional)
│   └── dicionario_metas_*.csv
├── staging/         ← intermediários de cada transformação
│   ├── 01_areas/
│   ├── 02_colaboradores/
│   ├── 03_indicadores/
│   ├── 04_metas_individuais/
│   ├── 05_metas_compartilhadas/
│   ├── 06_metas_projeto/
│   └── 07_curva_alcance/
├── output/          ← planilhas .xlsx prontas pra importação
│   └── 2026-07-15/
│       ├── Import_Áreas (Estrutura Hierárquica).xlsx
│       ├── Import_Colaboradores.xlsx
│       └── ...
├── relatorios/      ← relatorio_validacao.md, log_pipeline.json
└── sessoes/         ← histórico de sessões dos agentes LLM
```

---

## Comandos: referência rápida

| Comando | O que faz | Determinístico ou LLM |
|---|---|---|
| `novo <cliente>` | Cria estrutura de pastas a partir de `_modelo/` | det |
| `diagnosticar <cliente>` | Agente LLM de diagnóstico | LLM |
| `mapear <cliente>` | Agente LLM de mapeamento | LLM |
| `analisar <cliente>` | Diagnóstico + mapeamento (versão determinística clássica) | det |
| `transformar <cliente>` | Roda todas as transformações + validação | det |
| `validar <cliente>` | Agente LLM de validação final | LLM |
| `pilotar <cliente>` | Orquestrador LLM (decide o próximo passo) | LLM |
| `rodar <cliente>` | Pipeline completo determinístico | det |
| `depara <cliente> [tipo]` | Lista ou cria de-para manuais (texto → código da plataforma) | det |
| `grupos` | Lista os módulos de carga e suas dependências | det |
| `grupo <grupo> <cliente>` | Roda um módulo específico (nucleo, indicadores, metas, competencias) | det |
| `inferir <cliente>` | Agente LLM de inferência (fabrica entidades que o cliente não enviou) | LLM |
| `responder <cliente> <sessao_id>` | Retoma agente pausado em HITL | — |
| `demo <cliente>` | Smoke test do agente exemplo | LLM |
| `ajuda [comando]` | Visão geral, ou detalhes de um comando (`<comando> --help` funciona igual) | det |

---

## Troubleshooting

**`MEREO_LLM_API_KEY não definida`**
O `.env` não foi criado ou está vazio. Confirme com `cat .env` e edite a variável.

**`config/diagnostico.json não encontrado`**
Você está tentando mapear/transformar antes de diagnosticar. Rode `./implantacao diagnosticar <cliente>` primeiro.

**`mapeamento.json está travado — não foi sobrescrito`**
Comportamento esperado quando você rerodar `mapear` ou `analisar` em cima de um mapeamento revisado. Se quiser regenerar, remova o flag `"travado": true` do JSON manualmente.

**`Pipeline interrompido em 'X' (agente bloqueador)`**
O agente determinístico de áreas/diagnostico/mapeamento falhou. Veja a mensagem de erro acima para a causa. Áreas é dependência das demais, então não dá pra continuar sem.

**Validação bloqueada por "texto em campo de código" / "código fora do domínio"**
A base do cliente trouxe descrição onde a plataforma espera código (pilar, grupo de permissões, agregação…). Abra `clientes/<cliente>/relatorios/relatorio_validacao.md` para ver os valores, crie o de-para com `./implantacao depara <cliente> <tipo>` e rode `transformar` de novo.

**Sessão LLM travou ou não retorna**
Verifique `clientes/<cliente>/sessoes/<id>/metadata.json` — se status for `ativa`, o processo provavelmente foi interrompido. Sessões `pausada_hitl` esperam `responder`. Sessões `erro` podem ser inspecionadas no `transcript.jsonl`.

**Arquivos com encoding estranho na saída**
Os templates da plataforma usam `latin-1`. Os CSVs intermediários de `staging/` são gerados em UTF-8 com BOM; o output final é `.xlsx`, sem questão de encoding.

---

## Documentação adicional

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — arquitetura interna, núcleo LLM, modelo HITL, como adicionar novos agentes. *(documento em construção, primeira versão)*
- [`sops/`](sops/) — procedimentos operacionais para humanos (coleta, diagnóstico, importação) e SOPs-prompt dos agentes LLM (`sops/agentes/`).
- [`docs/`](docs/) — material histórico do design original (pré-migração LLM).
- [`templates/`](templates/) — templates oficiais da plataforma RHTec/Mereo.
