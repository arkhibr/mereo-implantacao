# Plano de Construção das Skills

**Total:** 15 skills | **Ondas:** 6 | **Critério de priorização:** skills que desbloqueiam mais etapas do pipeline vêm primeiro

---

## Mapa de dependências

```
Wave 1 - Fundação
  └── Wave 2 - Diagnóstico
        └── Wave 3 - Recodificação
              └── Wave 4 - Transformações Atômicas
                    └── Wave 5 - Hierarquia
                          └── Wave 6 - Validação
```

Nenhuma wave pode ser executada sem as anteriores estarem prontas.

---

## Wave 1 — Fundação
> Sem essas duas, nenhum outro skill funciona. Todo pipeline começa com leitura de arquivo.

| # | Skill | Pasta | O que faz | Desbloqueia |
|---|---|---|---|---|
| 1 | **Perfilamento de arquivo tabular** | `skills/ingestao/` | Recebe qualquer Excel/CSV e retorna: abas, colunas, tipos inferidos, contagem de nulos, valores únicos, amostra de 5 linhas | Todas as waves |
| 2 | **Detecção e normalização de encoding** | `skills/ingestao/` | Detecta o encoding de um arquivo texto e converte para UTF-8 | Todas as waves |

---

## Wave 2 — Diagnóstico
> Habilita o SOP 02 a ser executado (parcialmente) por um agente. Também alimenta o relatório de validação do SOP 04.

| # | Skill | Pasta | O que faz | Desbloqueia |
|---|---|---|---|---|
| 3 | **Diagnóstico de erros de planilha** | `skills/qualidade/` | Detecta `#N/A`, `#REF!`, `#VALOR!`, células vazias em colunas obrigatórias, linhas totalmente vazias | SOP 02 (passo 4), SOP 04 |
| 4 | **Detecção de duplicatas** | `skills/qualidade/` | Dado um arquivo e uma coluna-chave, identifica registros duplicados e retorna lista com as ocorrências | SOP 02 (passo 4), SOP 04 |
| 5 | **Detecção de PII** | `skills/qualidade/` | Analisa nomes de colunas e amostras de valores para sinalizar campos que provavelmente contêm CPF, e-mail, nome completo, data de nascimento | SOP 02 (passo 4) |

---

## Wave 3 — Recodificação
> Artefato central do SOP 03. Construído antes das transformações atômicas porque muitas delas dependem de ter os IDs já traduzidos.

| # | Skill | Pasta | O que faz | Desbloqueia |
|---|---|---|---|---|
| 6 | **Construção de dicionário de recodificação** | `skills/codificacao/` | Dado um conjunto de IDs de origem e um prefixo, gera os IDs de destino e salva o mapa de tradução em CSV | SOP 03 (passo 2) |
| 7 | **Aplicação de dicionário de recodificação** | `skills/codificacao/` | Dado o dicionário e um arquivo, substitui todos os IDs de origem pelos de destino — inclusive em campos de referência cruzada | SOP 03 (passo 3) |

---

## Wave 4 — Transformações Atômicas
> Operações individuais de transformação. Cada uma é independente das outras nesta wave. São os "verbos" do pipeline.

| # | Skill | Pasta | O que faz | Desbloqueia |
|---|---|---|---|---|
| 8 | **Normalização de domínio** | `skills/transformacao/` | Recebe uma coluna e uma tabela de equivalências (`"Sim"/"S"/"1" → 1`) e normaliza todos os valores para o canônico | SOP 03 (passo 3) |
| 9 | **Conversão de data serial Excel** | `skills/transformacao/` | Converte números seriais do Excel (`44197`) para datas legíveis no formato configurável (`DD/MM/AAAA`, `AAAA-MM-DD`, etc.) | SOP 03 (passo 3) |
| 10 | **Agregação de linhas em campo pipe-separado** | `skills/transformacao/` | Agrupa múltiplas linhas do mesmo registro em um único campo `val1\|val2\|val3`, dado uma chave de agrupamento e a coluna a agregar | SOP 03 (passo 3) |
| 11 | **Quebra e junção de campos** | `skills/transformacao/` | Separa um campo em múltiplos dado um delimitador, ou concatena múltiplos campos em um, com separador configurável | SOP 03 (passo 3) |

---

## Wave 5 — Hierarquia
> Mais especializada, mas universal: qualquer estrutura pai-filho (organograma, categorias, plano de contas) passa por aqui.

| # | Skill | Pasta | O que faz | Desbloqueia |
|---|---|---|---|---|
| 12 | **Validação de árvore hierárquica** | `skills/hierarquia/` | Dado um dataset com `código` e `código_pai`, detecta: ciclos diretos e indiretos, nós órfãos (pai inexistente), múltiplas raízes quando só deveria ter uma | SOP 03 (passo 4), SOP 04 |
| 13 | **Reconstrução de hierarquia a partir de dados planos** | `skills/hierarquia/` | Converte colunas de nível (`nivel1 / nivel2 / nivel3`) em registros pai-filho normalizados | SOP 03 (passo 3) |

---

## Wave 6 — Validação
> Portão final antes da importação. Estas skills tornam o SOP 04 automatizável.

| # | Skill | Pasta | O que faz | Desbloqueia |
|---|---|---|---|---|
| 14 | **Validação de schema contra template** | `skills/exportacao/` | Dado um arquivo de output e um template de referência, verifica: colunas presentes e na ordem correta, campos obrigatórios preenchidos, tipos e formatos corretos | SOP 04 |
| 15 | **Validação de integridade referencial entre tabelas** | `skills/exportacao/` | Dados N arquivos com mapeamento de chaves estrangeiras, verifica que toda referência aponta para um registro existente | SOP 04 |

---

## Visão consolidada

| Wave | Skills | SOP que habilita | Esforço estimado |
|---|---|---|---|
| 1 — Fundação | 2 | Todos | P |
| 2 — Diagnóstico | 3 | SOP 02, SOP 04 | M |
| 3 — Recodificação | 2 | SOP 03 | M |
| 4 — Transformações Atômicas | 4 | SOP 03 | M |
| 5 — Hierarquia | 2 | SOP 03, SOP 04 | G |
| 6 — Validação | 2 | SOP 04 | M |
| **Total** | **15** | | |

---

## Contrato de uma skill

Toda skill construída deve respeitar este contrato para garantir universalidade:

1. **Entrada declarada** — aceita tipos primitivos (path, string, dict, dataframe); nunca assume estrutura de negócio
2. **Saída padronizada** — retorna sempre um objeto estruturado com `status`, `dados` e `erros`
3. **Sem efeitos colaterais** — não escreve em disco a menos que explicitamente solicitado
4. **Configurável, não hardcoded** — qualquer regra específica (prefixo, delimitador, formato de data) vem como parâmetro
5. **Testável isoladamente** — cada skill tem seus próprios casos de teste em `testes/unitarios/`
