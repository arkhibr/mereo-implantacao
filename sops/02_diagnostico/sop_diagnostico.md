# SOP 02 — Diagnóstico dos Dados do Cliente

**Versão:** 1.0  
**Fase anterior:** [SOP 01 — Coleta](../01_coleta/)  
**Fase seguinte:** [SOP 03 — Transformação](../03_transformacao/)

---

## Objetivo

Produzir um diagnóstico completo dos dados do cliente: entender sua estrutura, avaliar a qualidade, mapear campos para os templates da plataforma e identificar todas as transformações necessárias antes de escrever qualquer código ou mover qualquer dado.

## Quando usar

Após a conclusão do SOP 01, com os arquivos em `raw/` e o `recebimento.md` preenchido.

## Responsável

Consultor de implantação, com suporte do agente de diagnóstico quando disponível.

---

## Pré-requisitos

- SOP 01 concluído (checklist confirmado)
- `clientes/<nome_cliente>/config/recebimento.md` preenchido
- Templates de referência disponíveis em `templates/`

---

## Procedimento

### Passo 1 — Análise estrutural de cada arquivo

Para cada arquivo em `raw/`, documente sua anatomia **sem interpretar ainda**:

| Pergunta | O que registrar |
|---|---|
| Quantas abas/sheets? | Nome e número de linhas de cada uma |
| Há abas de instrução? | Sim/não — se sim, quais |
| Os cabeçalhos estão na linha 1? | Se não, em qual linha começam |
| Há linhas de totais ou rodapé? | Identificar e marcar para excluir |
| Qual o encoding do arquivo? | UTF-8, Latin-1, Windows-1252 |
| Datas estão em qual formato? | Serial Excel, DD/MM/AAAA, texto, etc. |
| Números usam vírgula ou ponto decimal? | Impacta conversão |

Registre no arquivo `clientes/<nome_cliente>/config/diagnostico.md` (criado neste passo).

---

### Passo 2 — Mapeamento de entidades

Relacione cada aba ou seção do arquivo do cliente com a entidade correspondente na plataforma:

| Aba / Seção do cliente | Entidade da plataforma | Certeza | Observação |
|---|---|---|---|
| ex: "Hierarquia" | Áreas | Alta | |
| ex: "Colaboradores" | Colaboradores | Alta | |
| ex: "Metas Compostas" | Metas Compartilhadas | Média | verificar se há metas de projeto misturadas |
| ex: "MEREO" | indefinida | Baixa | parece metas, mas tipo não está claro |

**Certeza:**
- **Alta** — correspondência direta e inequívoca
- **Média** — provável, mas há ambiguidade
- **Baixa** — inferência; requer confirmação com o cliente

---

### Passo 3 — Mapeamento de campos

Para cada entidade identificada no Passo 2, faça o mapeamento campo a campo entre o dado do cliente e o template da plataforma.

Use o template de mapeamento abaixo — crie uma tabela por entidade:

```
## Mapeamento: <Entidade>

Arquivo origem: <nome do arquivo>
Aba origem: <nome da aba>
Template destino: <nome do template>

| Campo no cliente | Coluna no template | Tipo de transformação | Obrigatório? | Observação |
|---|---|---|---|---|
| nome_colaborador | Nome completo* | Direto | Sim | |
| cod_area | Código da Área* | Recodificação | Sim | código interno → código plataforma |
| dt_admissao | — | Sem destino | — | não existe no template, descartar |
| — | Login* | Derivado | Sim | precisa ser criado: primeiro.ultimo@empresa |
```

**Tipos de transformação:**

| Tipo | Descrição | Exemplo |
|---|---|---|
| **Direto** | Copiar sem alteração | nome → Nome completo |
| **Recodificação** | Traduzir de um domínio para outro | código 289 → COD_289 |
| **Derivado** | Campo novo calculado a partir de outros | login = nome + sobrenome |
| **Quebrar** | Um campo vira vários | "João Silva / TI" → nome + área |
| **Juntar** | Vários campos viram um | nome + sobrenome → nome completo |
| **Converter** | Mudança de tipo ou formato | serial 44197 → 2021-01-01 |
| **Normalizar** | Padronizar domínio (lista de valores) | "Sim"/"S"/"1" → 1 |
| **Pipe-separar** | Múltiplos valores → um campo pipe-delimitado | linhas → "SUP01\|SUP02" |
| **Sem destino** | Campo existe no cliente, não existe no template | descartar ou documentar |
| **Ausente** | Campo obrigatório no template não existe no cliente | bloquear — resolver com cliente |

---

### Passo 4 — Análise de qualidade

Percorra os dados e catalogue os problemas encontrados por categoria:

#### 4.1 Erros de fórmula
- Células com `#N/A`, `#REF!`, `#VALOR!`, `#DIV/0!`
- Registrar: qual aba, qual coluna, quantas linhas afetadas, impacto (campo obrigatório?)

#### 4.2 Valores ausentes
- Campos obrigatórios no template sem valor correspondente no cliente
- Distinguir: ausente em todas as linhas vs. ausente em algumas

#### 4.3 Inconsistências de domínio
- Valores que deveriam ser de uma lista fechada mas têm variações (ex: "Ativo", "ativo", "A", "1", "Sim")
- Identificadores com formatos misturados (ex: "001", "1", "COD001")

#### 4.4 Duplicatas
- Identificadores que aparecem mais de uma vez quando deveriam ser únicos
- Verificar principalmente: código de área, login, código de meta, código de indicador

#### 4.5 Referências cruzadas quebradas
- Um campo referencia um código que não existe em outra aba (ex: meta referencia área inexistente)
- Listar: campo, valor referenciado, onde deveria existir

#### 4.6 Dados sensíveis (PII)
- CPF, RG, data de nascimento, salário, e-mail pessoal
- Registrar quais campos contêm PII e em quais abas

**Para cada problema encontrado, registre:**

```
| # | Categoria | Arquivo | Aba | Campo | Qtd. afetada | Obrigatório? | Ação sugerida |
|---|---|---|---|---|---|---|---|
| 1 | Erro fórmula | Evolução Midia.xlsx | Plan1 | col D | 12 linhas | Sim | escalar para cliente |
| 2 | Ausente | Holding.xlsx | individuais | Login DP | 100% | Sim | derivar do nome |
```

---

### Passo 5 — Classificação de metas (quando aplicável)

Se o cliente enviou metas, identifique o tipo de cada uma, pois os templates são distintos:

| Tipo | Como reconhecer |
|---|---|
| **Meta Individual** | Associada a um colaborador específico; tem indicador (KPI) vinculado |
| **Meta Compartilhada** | Associada a uma área; referencia uma meta-base; pode ter peso fracionado |
| **Meta de Projeto** | Prazo definido; não necessariamente vinculada a KPI contínuo; pode ter entregáveis |

Quando o tipo não estiver explícito nos dados, registre como "indefinida" e inclua na lista de dúvidas (Passo 6).

---

### Passo 6 — Levantamento de dúvidas para o cliente

Liste tudo que não pode ser resolvido internamente — ambiguidades que exigem confirmação do cliente antes de transformar:

```
## Dúvidas para o cliente — <Nome do Cliente>

| # | Entidade | Dúvida | Impacto se não resolvida |
|---|---|---|---|
| 1 | Metas | As metas na aba "MEREO" são individuais ou compartilhadas? | Não é possível preencher o template correto |
| 2 | Colaboradores | O campo "login" deve seguir qual padrão? (ex: nome.sobrenome?) | Campo obrigatório sem origem clara |
| 3 | Áreas | O código "9" aparece como área superior em várias linhas mas não existe como área — é a raiz? | Hierarquia inválida sem confirmação |
```

---

### Passo 7 — Avaliação de complexidade

Consolide o diagnóstico em uma avaliação geral para orientar o planejamento da transformação:

| Dimensão | Avaliação | Justificativa |
|---|---|---|
| Completude dos dados | Alta / Média / Baixa | |
| Qualidade dos dados | Alta / Média / Baixa | |
| Complexidade de mapeamento | Alta / Média / Baixa | |
| Nº de dúvidas em aberto | — | quantidade |
| Estimativa de esforço | P / M / G | |
| Bloqueadores críticos | Sim / Não | descrever se sim |

---

## Checklist de conclusão

Antes de avançar para o SOP 03, confirme:

- [ ] `diagnostico.md` criado em `clientes/<nome_cliente>/config/`
- [ ] Estrutura de todos os arquivos documentada (Passo 1)
- [ ] Todas as entidades identificadas e mapeadas (Passo 2)
- [ ] Mapeamento de campos concluído por entidade (Passo 3)
- [ ] Problemas de qualidade catalogados (Passo 4)
- [ ] Tipo de cada meta definido ou sinalizado como dúvida (Passo 5)
- [ ] Lista de dúvidas para o cliente gerada (Passo 6)
- [ ] Avaliação de complexidade preenchida (Passo 7)
- [ ] Dúvidas críticas enviadas ao cliente (bloqueadores resolvidos antes de avançar)

---

## Saídas deste SOP

| Artefato | Localização |
|---|---|
| Diagnóstico completo | `clientes/<nome_cliente>/config/diagnostico.md` |
| Mapeamento de campos por entidade | dentro do `diagnostico.md` |
| Lista de dúvidas para o cliente | dentro do `diagnostico.md` |
| Avaliação de complexidade | dentro do `diagnostico.md` |

---

## Alertas e situações comuns

**O cliente tem abas de "instrução" junto com os dados.**
Leia as instruções antes de mapear os campos — elas frequentemente explicam o significado dos códigos numéricos usados.

**Os identificadores do cliente são puramente numéricos (ex: 289, 1510).**
Registre o sistema de codificação na seção de mapeamento. Será necessário criar um dicionário de tradução na transformação.

**Um mesmo colaborador aparece com logins ou IDs diferentes em abas distintas.**
É duplicata com variação — não tratar como dois registros. Registrar como problema de qualidade e definir qual é o registro canônico.

**Campos obrigatórios do template não têm nenhuma origem nos dados do cliente.**
São bloqueadores. Não avançar para transformação sem resolução — ou o cliente fornece o dado, ou existe uma regra de derivação acordada.

**Os dados de metas referenciam áreas ou colaboradores que não estão nos dados enviados.**
Integridade referencial quebrada. Registrar como problema crítico e escalar para o cliente antes de transformar.
