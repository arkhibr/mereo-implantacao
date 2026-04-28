# Avaliação do Cenário de Implantação

## O que existe

**9 templates de destino** (pasta `Templates/`) — cada um representa uma entidade do sistema:

| Template | Formato | Colunas | Obs |
|---|---|---|---|
| Áreas | CSV | 5 | hierarquia pai-filho |
| Colaboradores | CSV | 15 | login, email, permissões, área |
| Indicadores (KPI) | CSV | 14 | polaridade, frequência, alertas |
| Metas Compartilhadas | CSV | 8 | peso, metas superiores |
| Metas Individuais | CSV | 17 | mais complexo |
| Metas Projeto | CSV | 13 | |
| Curva de Alcance | CSV | 5 | faixas de pontuação |
| Valores Previstos | XLSX | matriz numérica | |
| Valores Realizados | XLSX | matriz numérica | |

**Dados do cliente** em dois níveis de complexidade:

- **Simples** — 1 arquivo Excel, 8 abas pareadas (`Instrução X` + `X`), ~2.200 linhas, estrutura referenciada por códigos numéricos internos (ex: código 289, 1437). Relativamente limpo.
- **Complexos** — 2 arquivos Excel pesados (~650 KB), múltiplas abas de trabalho, referências quebradas (`#N/A`, `#REF!`), dados reais de colaboradores (nomes, CPF), estruturas de metas paralelas (ex: "Novos Clientes" vs "Produtividade"), aba de erros dedicada (`nao achei a meta`).

---

## Desafios identificados

**1. Recodificação de identificadores**
Os dados do cliente usam códigos numéricos internos (ex: `1510`, `289`). Os templates exigem códigos semânticos (ex: `COD_12`, `MET_1234`, `IND_1234`). Não é renomear — é criar um mapa de tradução entre dois sistemas de identidade.

**2. Resolução de referências quebradas**
Os arquivos complexos têm `#N/A` e `#REF!` em campos-chave. Antes de qualquer transformação, esses registros precisam ser triados: corrigir, ignorar, ou escalar pro cliente.

**3. Desnormalização vs. estrutura do template**
O cliente empacota entidades relacionadas em múltiplas abas com cross-references. Os templates são flat — cada um é uma tabela independente. A transformação exige "explodir" relações e montar cada template de forma autossuficiente.

**4. Campos multi-valor**
Os templates usam pipe como separador de listas dentro de uma célula (ex: `SUP01|SUP02`, `Rótulo1|Rótulo2`). Os dados do cliente provavelmente têm isso distribuído em linhas ou colunas separadas.

**5. Metas: hierarquia e tipos**
As metas têm 3 tipos no template (Individual, Compartilhada, Projeto) com schemas diferentes. Nos dados do cliente, a distinção entre tipos pode estar implícita na estrutura, não em um campo explícito. Classificar cada meta no tipo certo exige lógica, não apenas mapeamento.

**6. Curva de alcance e valores de metas**
Os dois templates XLSX (Previstos/Realizados) têm colunas numéricas (0–13) que parecem representar períodos ou faixas — a semântica exata não está clara só pelos templates. Isso vai exigir entendimento do modelo de dados da plataforma.

**7. Datas em formato serial Excel**
Datas no arquivo simples estão como seriais Excel (ex: `44197` = jan/2021). Precisam ser convertidas para o formato esperado pelo template.

**8. Dados de PII**
Os arquivos complexos contêm CPF e nomes reais. O processo precisa tratar isso com cuidado — não expor em logs, saídas intermediárias, etc.

**9. Heterogeneidade entre clientes**
Os dados "complexos" mostram que cada cliente entrega o dado num formato diferente. Isso sugere que a solução não pode ser um script hardcoded para um cliente — precisa ter algum grau de flexibilidade ou configurabilidade.

---

## Complexidade geral

| Dimensão | Avaliação |
|---|---|
| Volume de dados | Moderado (mil linhas por entidade) |
| Qualidade dos dados | Baixa a média nos complexos |
| Complexidade de transformação | Alta (recodificação, tipagem, hierarquia) |
| Ambiguidade semântica | Alta (campos implícitos, tipos inferidos) |
| Repetibilidade (multi-cliente) | Alta exigência |

---

## Conclusão

Este não é um problema de ETL simples. É um problema de **reconciliação semântica entre dois modelos de domínio**: o modelo "como o cliente organiza seus dados" vs. o modelo "como a plataforma espera receber". Além de transformação técnica, vai exigir regras de negócio codificadas (o que é uma meta individual vs. compartilhada? como mapear a hierarquia de áreas?) e provavelmente um ciclo iterativo com o cliente para resolver as ambiguidades.
