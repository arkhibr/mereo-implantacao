# Curva de Alcance — Alinhamento para Correção

**Data:** 15/07/2026
**Referência:** feedback de 16/06/2026 (módulo de metas), ponto 6 — *"a curva de alcance existia na base do cliente, mas não chegou ao resultado final"*
**Objetivo:** fechar as três definições que faltam para corrigirmos o tratamento da curva de alcance de forma definitiva. Os demais pontos do feedback (códigos de pilar, grupos de permissão, indicadores, unidades de medida e login) já foram tratados com as informações que vocês enviaram — a curva é o principal item em aberto.

---

## O que entendemos por curva de alcance

É a régua que converte o atingimento da meta em nota. Exemplo típico do que vemos nas bases dos clientes:

| Atingimento da meta | Nota |
|---|---|
| até 79% | 0 |
| 80% | 1 |
| 90% | 5 |
| 100% ou mais | 10 |

No modelo de importação da plataforma, essa régua vira uma linha por meta:

```
Código da Meta* ; Tipo de Valor* ; Percentual/Valor 1º Nota ; Percentual/Valor 2º Nota ; ... ; Percentual/Valor Nota n
MET_0001        ; 1              ; 10                       ; (vazio)                  ;     ; 100
```

## O que já está esclarecido

Com a planilha de padrões que vocês enviaram, já sabemos que **a curva é opcional**: o campo "Código da Curva de Notas" da meta só é obrigatório *"para a meta que possui curva"*. Ou seja, metas sem régua definida podem ser importadas sem esse campo, sem quebrar nada — e é assim que estamos operando até este alinhamento se concluir.

## O que precisamos definir (3 itens)

### 1. Os casos concretos em que a curva se perdeu

Para corrigir com segurança, precisamos reproduzir exatamente o que aconteceu no teste de vocês. Bastam **2 ou 3 exemplos**, no formato:

> "Na planilha *X*, aba *Y*, a meta *FIN01* tinha a régua *80% → nota 1, 100% → nota 10* nas colunas *Z*; no arquivo importado, essa meta saiu sem curva."

Nossa hipótese principal é que a régua estava registrada num formato/aba que o processo de transformação não reconheceu como curva (por exemplo, colunas de percentual dentro da própria planilha de metas). Com os exemplos em mãos, ajustamos o reconhecimento e validamos a correção contra os próprios casos.

**Ideal:** reenviar a planilha de entrada usada no teste e o resultado importado (já pedimos esses arquivos no relatório anterior — item 2).

### 2. A legenda do campo "Tipo de Valor"

O modelo de importação traz `Tipo de Valor* = 1` no exemplo, sem legenda — e esse campo não veio na planilha de padrões. Precisamos da tabela completa, no mesmo formato das outras que vocês enviaram:

| Código | Significado |
|---|---|
| 1 | Percentual de atingimento? |
| 2 | Valor absoluto? |
| ... | ... |

Junto com ela: **quantas notas** o ambiente de vocês utiliza (escala 0–10? 1–5? livre por meta?).

### 3. A relação entre "Curva de Notas" e "Curva de Alcance"

Identificamos dois conceitos que precisam ser conectados:

- No modelo de **metas**, existe o campo `Código da Curva de Notas` (código curto, ex. formato de cadastro) — sugere que as curvas são **cadastradas uma vez e reutilizadas** por várias metas.
- O modelo de importação de **Curva de Alcance** é preenchido **meta a meta**, sem código de curva.

Perguntas para fechar o desenho:

1. Existe um **cadastro de curvas** na plataforma (como existe para pilares e faixas de farol)? Se sim, podem exportar a lista (código + descrição da régua)?
2. Ao importar o arquivo de Curva de Alcance, a plataforma **cria** esse código automaticamente e o associa à meta — ou precisamos **referenciar um código já cadastrado** no campo da meta?
3. Quando a meta não tem curva, existe uma **curva padrão** aplicada pela plataforma (ex. linear 0–100%)? Qual?

## Resumo do que pedimos

| # | Item | Formato ideal |
|---|---|---|
| 1 | 2–3 casos concretos de curva perdida no teste (planilha de entrada + resultado) | Planilhas |
| 2 | Tabela de códigos de "Tipo de Valor" + escala de notas utilizada | Tabela |
| 3 | Cadastro de curvas do ambiente (se existir) e regra de associação curva × meta | Exportação / descrição |

## O que faremos com as respostas

1. Reproduzir os casos enviados e corrigir o reconhecimento da curva na origem.
2. Codificar a tabela de "Tipo de Valor" no processo, com validação automática (nenhuma curva sai com valor fora da tabela — mesmo mecanismo já aplicado a polaridade, agregação e unidades).
3. Garantir a associação correta curva × meta conforme a regra da plataforma, com verificação de consistência antes de gerar os arquivos (curva referenciando meta inexistente passa a ser bloqueada).

Enquanto isso, as metas seguem sendo geradas **sem** o campo de curva — comportamento seguro confirmado pela planilha de padrões.
