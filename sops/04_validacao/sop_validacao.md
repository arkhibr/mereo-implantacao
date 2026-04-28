# SOP 04 — Validação dos Dados Transformados

**Versão:** 1.0  
**Fase anterior:** [SOP 03 — Transformação](../03_transformacao/)  
**Fase seguinte:** [SOP 05 — Importação](../05_importacao/)

---

## Objetivo

Garantir que os arquivos gerados em `output/` estão corretos, completos e prontos para importação na plataforma — antes de qualquer dado entrar no ambiente do cliente.

## Quando usar

Após a conclusão do SOP 03, com todos os arquivos de output gerados e o `log_transformacao.md` fechado.

## Responsável

Consultor de implantação. Recomendado: revisão por um segundo consultor quando o volume ou complexidade for alto.

---

## Pré-requisitos

- SOP 03 concluído (checklist confirmado)
- Arquivos de output presentes em `clientes/<nome_cliente>/output/`
- `log_transformacao.md` fechado e sem pendências críticas em aberto
- Templates de referência disponíveis em `templates/`

---

## Princípios desta fase

**Validar contra o template, não contra a intuição.** O critério de aprovação é o que o template da plataforma exige — não o que "parece certo".

**Separar erros de alertas.** Nem todo problema é bloqueador. Classifique cada achado como erro (impede importação) ou alerta (importação possível, mas com risco).

**Não corrigir aqui.** Se um problema for encontrado, volte ao SOP 03, corrija em `staging/` e gere o output novamente. Nunca edite diretamente os arquivos de `output/`.

---

## Níveis de severidade

| Nível | Descrição | O que fazer |
|---|---|---|
| **Crítico** | Impede a importação ou corrompe dados na plataforma | Bloquear. Corrigir antes de avançar. |
| **Alto** | Dado importado mas com valor incorreto, pode gerar inconsistência | Corrigir antes de avançar. |
| **Médio** | Dado importado mas incompleto em campo não obrigatório | Avaliar com o cliente se é aceitável. |
| **Baixo** | Desvio cosmético ou de padronização sem impacto funcional | Registrar, corrigir se possível. |

---

## Procedimento

### Passo 1 — Validação de schema

Para cada arquivo em `output/`, verifique conformidade com o template correspondente:

#### 1.1 Cabeçalho
- [ ] O nome de cada coluna é idêntico ao do template (incluindo acentuação, maiúsculas e `*`)?
- [ ] A ordem das colunas é a mesma do template?
- [ ] Não há colunas a mais nem a menos?

#### 1.2 Campos obrigatórios
Campos marcados com `*` no template não podem estar vazios em nenhuma linha.

| Template | Campos obrigatórios |
|---|---|
| Áreas | Código da Área, Descrição da Área, Código da Filial |
| Colaboradores | Login, Nome completo, E-mail, Cód. Grupo Permissões, Código da Área, Idioma, Workflow de Ações, Ativo |
| Indicadores | Código do Indicador, Descrição, Cód. Unidade de Medida, Cód. Faixa de Farol, Cód. Frequência, Polaridade, Ativo |
| Metas Individuais | Código da Meta, Código da Área, Login Responsável, Login Data-Provider, Cód. Indicador, Cód. Pilar, Objetivo, Peso, Tipo de Agregação |
| Metas Compartilhadas | Código da Meta, Código da Área, Login Responsável, Cód. Meta Compartilhada, Peso |
| Metas Projeto | Código da Meta, Código da Área, Login Responsável, Cód. Indicador, Cód. Pilar, Objetivo, Peso |
| Curva de Alcance | Código da Meta, Tipo de Valor |

Para cada campo obrigatório vazio encontrado: registrar arquivo, coluna e linha(s) afetadas.

#### 1.3 Tipos e formatos de dados
Verifique campo a campo se os valores estão no formato esperado:

| Tipo esperado | Verificação |
|---|---|
| Código (texto) | Sem espaços no início/fim, sem caracteres especiais inesperados |
| Numérico inteiro | Sem letras, sem vírgula, sem ponto decimal |
| Numérico decimal | Separador decimal correto para a plataforma (verificar se é `.` ou `,`) |
| Booleano (0/1) | Apenas `0` ou `1`, não `true/false`, `sim/não`, etc. |
| Data | Formato correto conforme exigido pela plataforma |
| Pipe-separado | Sem espaços ao redor do `|`, sem `|` no início ou fim |
| E-mail | Formato válido (`nome@dominio.ext`) |

---

### Passo 2 — Validação de unicidade

Campos que devem ser únicos dentro do arquivo:

| Arquivo | Campo único |
|---|---|
| Áreas | Código da Área |
| Colaboradores | Login |
| Indicadores | Código do Indicador |
| Metas Individuais | Código da Meta |
| Metas Compartilhadas | Código da Meta |
| Metas Projeto | Código da Meta |

Adicionalmente: o `Código da Meta` deve ser único **entre todos os três tipos de metas** — não pode haver uma meta individual e uma compartilhada com o mesmo código.

---

### Passo 3 — Validação referencial

Verifique se cada código referenciado existe de fato no arquivo onde deveria estar:

| Campo | Onde referencia | Arquivo onde deve existir |
|---|---|---|
| Código da Área (em Colaboradores) | → | output de Áreas |
| Código da Área (em Metas) | → | output de Áreas |
| Login do Responsável (em Metas) | → | output de Colaboradores |
| Login do Data-Provider (em Metas Individuais) | → | output de Colaboradores |
| Código do Indicador (em Metas) | → | output de Indicadores |
| Código das Metas Superiores (em Metas) | → | output de qualquer tipo de Meta |
| Código da Meta a ser compartilhada (em Compartilhadas) | → | output de qualquer tipo de Meta |
| Código da Meta (em Curva de Alcance) | → | output de qualquer tipo de Meta |
| Código da Meta (em Valores Previstos) | → | output de qualquer tipo de Meta |
| Código da Meta (em Valores Realizados) | → | output de qualquer tipo de Meta |

Qualquer referência apontando para um código inexistente é erro **Crítico**.

---

### Passo 4 — Validação de regras de negócio

Verifique regras que a plataforma pode não checar automaticamente mas que afetam a consistência dos dados:

#### 4.1 Pesos das metas
- A soma dos pesos de todas as metas de um colaborador deve ser 100%
- A soma dos pesos de todas as metas de uma área deve ser 100%
- Tolerância: até ±0,01 por arredondamento
- Desvios acima disso: nível **Alto**

#### 4.2 Hierarquia de áreas
- Nenhuma área pode ser sua própria área superior (ciclo direto)
- Nenhuma área pode ter um ancestral que também seja seu descendente (ciclo indireto)
- Toda área superior referenciada deve existir como área no arquivo
- Uma área raiz (sem superior) deve existir

#### 4.3 Hierarquia de metas
- Metas superiores não podem criar ciclos
- O nível de hierarquia deve ser consistente com o tipo de meta

#### 4.4 Curva de alcance
- Toda meta com curva de alcance deve ter pelo menos o valor mínimo e máximo preenchidos
- Os percentuais/valores devem estar em ordem crescente (ou decrescente, conforme polaridade)

#### 4.5 Colaboradores e áreas de responsabilidade
- As áreas listadas em "Códigos das Áreas sob sua Responsabilidade" devem existir no arquivo de Áreas
- O campo aceita múltiplos valores separados por `/` — verificar o delimitador correto para este campo

---

### Passo 5 — Validação de completude

Compare o que foi entregue com o que era esperado:

| Verificação | Como checar |
|---|---|
| Qtd. de áreas transformadas vs. identificadas no diagnóstico | Comparar contagens |
| Qtd. de colaboradores transformados vs. recebidos no raw | Comparar contagens |
| Qtd. de metas transformadas vs. identificadas no diagnóstico | Comparar por tipo |
| Linhas omitidas durante a transformação | Conferir no `log_transformacao.md` |

Para cada discrepância, justificar: foi omissão intencional (registrada no log) ou perda acidental?

---

### Passo 6 — Revisão por amostragem (spot check)

Selecione aleatoriamente 5–10% das linhas de cada arquivo e faça rastreabilidade manual:

1. Pegue a linha no `output/`
2. Localize o registro correspondente no `raw/`
3. Verifique se a transformação foi aplicada corretamente campo a campo
4. Verifique se o código no dicionário (`dicionario_codigos.csv`) bate

Qualquer divergência encontrada no spot check deve disparar uma revisão mais ampla daquela entidade.

---

### Passo 7 — Gerar o relatório de validação

Crie o arquivo `clientes/<nome_cliente>/relatorios/relatorio_validacao.md` com:

```
# Relatório de Validação — <Nome do Cliente>

Data:
Consultor:
Versão dos arquivos de output validados:

## Resumo

| Entidade | Linhas | Críticos | Altos | Médios | Baixos | Status |
|---|---|---|---|---|---|---|
| Áreas | | | | | | ✅ Aprovado / ❌ Bloqueado |
| Colaboradores | | | | | | |
| Indicadores | | | | | | |
| Metas Individuais | | | | | | |
| Metas Compartilhadas | | | | | | |
| Metas Projeto | | | | | | |
| Curva de Alcance | | | | | | |
| Valores Previstos | | | | | | |
| Valores Realizados | | | | | | |

## Status geral
✅ Aprovado para importação / ❌ Bloqueado — retornar ao SOP 03

## Detalhamento dos achados

| # | Severidade | Arquivo | Campo | Linha(s) | Descrição | Ação |
|---|---|---|---|---|---|---|
```

---

## Critério de aprovação

O conjunto de arquivos está **aprovado para importação** quando:

- Nenhum achado de nível **Crítico** em aberto
- Nenhum achado de nível **Alto** em aberto
- Achados de nível **Médio** e **Baixo** documentados e aceitos pelo cliente ou pelo consultor responsável
- Spot check executado sem divergências não explicadas
- Relatório de validação assinado (data + consultor)

---

## Checklist de conclusão

Antes de avançar para o SOP 05, confirme:

- [ ] Validação de schema executada para todos os 9 arquivos
- [ ] Validação de unicidade executada
- [ ] Validação referencial executada (nenhuma referência órfã)
- [ ] Regras de negócio verificadas (pesos, hierarquias, curvas)
- [ ] Validação de completude executada e discrepâncias justificadas
- [ ] Spot check executado (mínimo 5% das linhas por entidade)
- [ ] Relatório de validação gerado em `relatorios/`
- [ ] Nenhum achado Crítico ou Alto em aberto
- [ ] Achados Médios e Baixos documentados e aceitos

---

## Saídas deste SOP

| Artefato | Localização |
|---|---|
| Relatório de validação | `clientes/<nome_cliente>/relatorios/relatorio_validacao.md` |
| Arquivos aprovados para importação | `clientes/<nome_cliente>/output/` |

---

## Alertas e situações comuns

**Encontrei um erro durante a validação. Devo corrigir direto no output?**
Não. Volte ao SOP 03, corrija na raiz (em `staging/`), gere o output novamente e revalide. Editar `output/` diretamente cria inconsistência com `staging/` e o `log_transformacao.md`.

**A contagem de linhas no output é menor do que no raw — é problema?**
Não necessariamente. Linhas omitidas por erro, duplicatas removidas ou registros fora do escopo do ciclo são casos legítimos. O que importa é que cada omissão esteja registrada no `log_transformacao.md` com justificativa.

**O peso das metas não fecha 100% mas o cliente disse que está correto.**
Registrar a confirmação do cliente no relatório de validação e rebaixar o achado para nível Baixo ou aceito. A responsabilidade pela consistência do modelo de metas é do cliente.

**Não há dados de Valores Previstos ou Realizados.**
É válido. Nem todo ciclo de implantação inclui esses dados. Documentar no relatório como "não aplicável neste ciclo".

**O spot check encontrou uma divergência em um campo não obrigatório.**
Investigar se é um erro sistêmico (afeta todas as linhas) ou pontual (afeta apenas aquela linha). Se sistêmico, voltar ao SOP 03. Se pontual, avaliar severidade e decidir.
