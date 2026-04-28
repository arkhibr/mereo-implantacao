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

- **Python 3.10+** (`python3 --version`)
- **git** (para clonar)
- **Chave de API de um provider LLM compatível com OpenAI**. Default: [Abacus RouteLLM](https://routellm.abacus.ai). Outros providers (OpenAI direto, Together, Groq, vLLM local) funcionam ajustando a `base_url`.
- Sistema operacional: Linux ou macOS recomendados. Windows funciona via WSL.

---

## Instalação

```bash
git clone https://github.com/arkhibr/mereo-implantacao.git
cd mereo-implantacao

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env
# edite .env e preencha MEREO_LLM_API_KEY com sua chave do provider
```

> Um instalador automatizado está em desenvolvimento — vai cuidar do venv, das dependências e da configuração interativa do `.env`.

### Variáveis de ambiente

| Variável | Default | Função |
|---|---|---|
| `MEREO_LLM_API_KEY` | *(obrigatória)* | Chave do provider LLM |
| `MEREO_LLM_BASE_URL` | `https://routellm.abacus.ai/v1` | Endpoint do provider |
| `MEREO_LLM_MODEL` | `gpt-5` | Modelo a usar |
| `MEREO_MAX_TOKENS` | `16000` | Limite por resposta |
| `MEREO_MAX_ITERACOES` | `50` | Limite de turnos por sessão |

O wrapper `./implantacao` carrega o `.env` automaticamente.

---

## Uso — passo a passo

Todos os comandos são chamados via `./implantacao <comando> <cliente>`. Use `./implantacao` sem argumentos para ver a ajuda.

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

### 5. Validação final

```bash
./implantacao validar acme
```

Agente LLM valida cada arquivo de staging contra o template (schema, campos obrigatórios, tipos, duplicatas em chave única) e a integridade referencial entre as tabelas. Decide entre três estados:

- **`aprovado`** — copia para `output/<data>/` direto.
- **`aprovado_com_ressalvas`** — copia após confirmação humana via HITL.
- **`bloqueado`** — não copia; relatório explica os achados críticos.

Produz `clientes/acme/relatorios/relatorio_validacao.md` (com seção narrativa) e, quando aprovado, `clientes/acme/output/<data>/Import_*.csv`.

### 6. Importar na plataforma Mereo

Os arquivos em `output/<data>/` seguem o nome dos templates da plataforma e podem ser importados diretamente.

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
│   ├── dicionario_areas.csv      (gerado nas transformações)
│   └── dicionario_metas_*.csv
├── staging/         ← intermediários de cada transformação
│   ├── 01_areas/
│   ├── 02_colaboradores/
│   ├── 03_indicadores/
│   ├── 04_metas_individuais/
│   ├── 05_metas_compartilhadas/
│   ├── 06_metas_projeto/
│   └── 07_curva_alcance/
├── output/          ← arquivos prontos pra importação
│   └── 2026-04-28/
│       ├── Import_Áreas (Estrutura Hierárquica).csv
│       ├── Import_Colaboradores.csv
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
| `responder <cliente> <sessao_id>` | Retoma agente pausado em HITL | — |
| `demo <cliente>` | Smoke test do agente exemplo | LLM |

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

**Sessão LLM travou ou não retorna**
Verifique `clientes/<cliente>/sessoes/<id>/metadata.json` — se status for `ativa`, o processo provavelmente foi interrompido. Sessões `pausada_hitl` esperam `responder`. Sessões `erro` podem ser inspecionadas no `transcript.jsonl`.

**Arquivos com encoding estranho na saída**
Os templates da plataforma usam `latin-1`. Os CSVs de output são gerados em UTF-8 com BOM por padrão — o Excel abre corretamente.

---

## Documentação adicional

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — arquitetura interna, núcleo LLM, modelo HITL, como adicionar novos agentes. *(documento em construção, primeira versão)*
- [`sops/`](sops/) — procedimentos operacionais para humanos (coleta, diagnóstico, importação) e SOPs-prompt dos agentes LLM (`sops/agentes/`).
- [`docs/`](docs/) — material histórico do design original (pré-migração LLM).
- [`templates/`](templates/) — templates oficiais da plataforma RHTec/Mereo.
