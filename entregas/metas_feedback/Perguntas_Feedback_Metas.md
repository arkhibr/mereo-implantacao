# Feedback de Metas — Perguntas para Alinhamento

**Data:** 07/07/2026
**Referência:** feedback recebido em 16/06/2026 (módulo de metas)
**Objetivo:** levantar as informações necessárias para corrigir os 6 pontos apontados. A maior parte das correções depende de tabelas de códigos que existem apenas dentro da plataforma — sem elas, o pipeline não tem como traduzir os textos do cliente para os códigos esperados na importação. Cada seção abaixo traz um exemplo concreto do que precisamos esclarecer.

---

## Pedido geral (destrava quase tudo)

1. **Existe documentação oficial dos templates de importação** com a legenda dos campos codificados? Os modelos que temos trazem apenas uma linha de exemplo, sem legenda. Exemplo real do template `Import_Metas Individuais`:

   ```
   Código da Meta *: MET_1234
   Código do Indicador *: IND_1234
   Código do Pilar Estratégico *: DIR_1234
   Tipo de Agregação *: 3          ← 3 significa o quê? Soma? Média?
   Tipo de Definição do Valor *:   ← vazio no exemplo; quais valores são válidos?
   ```

2. **Podem nos enviar os arquivos usados no teste** (planilhas de entrada e o resultado importado/avaliado)? Com os casos concretos em mãos, conseguimos reproduzir cada apontamento e validar as correções contra eles.

---

## 1. Utilização de códigos em vez de descrições (indicadores, pilares)

Hoje o pipeline gera códigos próprios para os indicadores que ele mesmo importa, mas não tem nenhuma tabela de tradução para cadastros que já existem na plataforma (como pilares estratégicos). O que acontece na prática:

| Campo | Como sai hoje | O que a plataforma espera |
|---|---|---|
| `Código do Pilar Estratégico *` | `Metas Setoriais` (o texto que veio na planilha do cliente) | `DIR_1234` (código do pilar já cadastrado) |
| `Código do Indicador *` | `IND_Faturamento Líquido Mensal` (código gerado a partir do nome) | `IND_1234` (curto) — ou o código do indicador já existente? |

3. **Pilares estratégicos:** podem nos enviar a lista de pilares cadastrados no ambiente do cliente, com **código e nome**? Precisamos de algo como:

   | Código | Nome |
   |---|---|
   | `DIR_0001` | Crescimento Sustentável |
   | `DIR_0002` | Excelência Operacional |

   Existe uma tela ou exportação da plataforma de onde tirar isso?

4. **Indicadores:** os indicadores já estão cadastrados na plataforma (e devemos referenciar os códigos existentes) ou serão importados junto com as metas (e os códigos que geramos valem)? Exemplo da dúvida: se o cliente tem a meta "Atingir 95% de SLA" e a plataforma já tem o indicador `IND_0042 — SLA de Atendimento`, a meta deve apontar para `IND_0042` — mas hoje não temos como saber que esse indicador existe.
5. **Padrão de códigos:** há regra de formação exigida (tamanho máximo, caracteres permitidos, prefixos reservados)? Ex.: um código como `METI_Reduzir_Custo_Operacional_2026` seria aceito ou estoura limite?

## 2. Unidades de medida

Hoje, quando a fonte do cliente não traz a unidade, o pipeline preenche um código padrão único — por isso todas saíram iguais. Exemplo do sintoma:

| Meta do cliente | Unidade real | Como saiu |
|---|---|---|
| "Reduzir inadimplência para 2%" | Percentual | `Código da Unidade de Medida * = 1` |
| "Faturar R$ 120 milhões" | Moeda (R$) | `Código da Unidade de Medida * = 1` |
| "Entregar 45 projetos" | Quantidade | `Código da Unidade de Medida * = 1` |

6. **Tabela de unidades de medida** cadastradas no ambiente do cliente (código + descrição). Ex.: qual código corresponde a `%`? E a `R$`, `dias`, `quantidade`?
7. As unidades de medida são um **cadastro fixo da plataforma ou por cliente**? (Define se a tabela vale para as próximas implantações.)
8. Quando a unidade **não vem explícita** na base do cliente — no exemplo acima, ela está embutida no texto da meta ("2%", "R$ 120 milhões") — o que preferem: a IA **inferir** a unidade a partir do contexto (com relatório do que foi inferido para conferência) ou **marcar para revisão manual** antes da importação?

## 3. Periodicidade das metas (mensal × anual)

9. **Tabela de códigos de frequência** (campo `Código de Frequência de Acompanhamento *` do indicador): quais são os códigos válidos e a que periodicidade correspondem? Ex.: `1 = mensal? anual?` — o template de exemplo usa `1` sem legenda.
10. **Regra esperada:** a periodicidade da meta deve sempre seguir a frequência do indicador associado? Ex.: se o indicador `IND_0042` é mensal, toda meta ligada a ele deve ter valores mensais, sem exceção?
11. Na prática, **como identificar na base do cliente** quais metas são mensais e quais são anuais? Exemplo do que costuma vir nas planilhas: a meta "Faturamento" tem colunas Jan–Dez preenchidas (parece mensal) e a meta "Certificação ISO" tem um único valor no ano (parece anual) — é seguro usar essa estrutura como critério, ou existe um campo/convenção que devemos exigir do cliente?
12. **Impacto nos valores:** para uma meta mensal, a plataforma espera 12 linhas de valores previstos/realizados (uma por mês) e, para anual, uma única? Como a importação distingue os dois casos — pela frequência do indicador ou pelas datas informadas?

## 4. Campos que exigem valores codificados

Hoje apenas a Polaridade tem tabela de tradução no pipeline (`maior melhor → 1`, `menor melhor → 2`, `nominal → 3`). Os demais campos passam o texto original adiante. Exemplo do sintoma:

| Campo | Veio na planilha do cliente | Como sai hoje | O que a plataforma espera |
|---|---|---|---|
| `Tipo de Agregação *` | "Definido pelo usuário" | `Definido pelo usuário` | `3`? (código do exemplo do template) |
| `Tipo de Agregação *` | "Soma" | `Soma` | `?` |
| `Tipo de Definição do Valor *` | (vazio) | `Manual` (texto padrão nosso) | `?` |

13. **Tipo de Agregação:** tabela completa de códigos. Precisamos de algo como: `Soma = ?`, `Média = ?`, `Repetição = ?`, `Definido pelo usuário = ?`.
14. **Tipo de Definição do Valor:** quais são os valores/códigos válidos? Quando o cliente não informa nada, qual é o padrão correto?
15. Há **outros campos codificados** que devemos conhecer além desses dois? Candidatos que vemos nos templates: `Código da Faixa de Farol *` (exemplo mostra `FXF01`), `Tipo de Valor *` da curva de alcance (exemplo mostra `1`), `Ativo *` (`1` = ativo?). Se sim, as respectivas tabelas.

## 5. Código do responsável / login

Hoje o pipeline extrai o login do e-mail (parte antes do `@`, em minúsculas): `maria.santos@empresa.com.br → maria.santos`. Quando a base traz **apenas o nome** da pessoa, não há de onde derivar o login — e o nome vaza para o campo:

| Veio na planilha do cliente | Como sai hoje | O que a plataforma espera |
|---|---|---|
| `maria.santos@empresa.com.br` | `maria.santos` ✓ | `maria.santos` |
| `Maria Silva Santos` | `Maria Silva Santos` ✗ | `maria.santos`? `msantos`? |

16. **Fonte de verdade dos logins:** podem exportar a lista de usuários já cadastrados no ambiente (login + nome completo + e-mail)? Com ela, cruzamos por nome quando o e-mail não existir na base.
17. **Regra de formação do login** na plataforma: é sempre o e-mail sem domínio? `nome.sobrenome`? Definido caso a caso na criação do usuário?
18. Quando **não houver correspondência** confiável — ex.: a planilha diz "Maria Santos" e existem duas Marias Santos cadastradas — qual o comportamento esperado: deixar em branco e listar para revisão, ou bloquear a linha na importação?

## 6. Curva de alcance

O dado existia na base do cliente mas não chegou ao resultado final — para diagnosticar a causa exata, precisamos dos casos.

19. **Exemplos concretos:** em quais metas/arquivos a curva existia na origem e não veio no resultado? Basta apontar 2–3 casos, ex.: "meta FIN01 do arquivo X tinha a régua 80% → nota 1, 100% → nota 10 na coluna Y, e o resultado saiu sem curva". Reproduzimos daí.
20. **Formato esperado:** o template traz `Tipo de Valor *` e colunas de notas. A linha de exemplo é:

    ```
    Código da Meta*: MET_0001 | Tipo de Valor*: 1 | 1ª Nota: 10 | 2ª Nota: (vazio) | Nota n: 100
    ```

    Qual a tabela de códigos de `Tipo de Valor` (`1` = percentual de atingimento? valor absoluto?) e quantas notas o ambiente do cliente utiliza (escala 1–5? 1–10?)?
21. A curva de alcance é **obrigatória para toda meta**, ou quando ausente a plataforma aplica uma curva padrão? Ex.: se a meta "Certificação ISO" não tem régua na base do cliente, podemos omiti-la do arquivo de curvas sem quebrar a importação?

---

## Resumo do que pedimos

| # | Item | Formato ideal |
|---|------|---------------|
| 1 | Documentação/legenda dos campos codificados dos templates | PDF ou planilha |
| 2 | Arquivos de entrada e resultado do teste que gerou o feedback | Planilhas |
| 3 | Pilares estratégicos do cliente (código + nome) | Exportação da plataforma |
| 4 | Indicadores já cadastrados (código + descrição), se houver | Exportação da plataforma |
| 5 | Unidades de medida (código + descrição) | Exportação da plataforma |
| 6 | Códigos de frequência de acompanhamento | Tabela |
| 7 | Códigos de Tipo de Agregação e Tipo de Definição do Valor | Tabela |
| 8 | Usuários cadastrados (login + nome + e-mail) | Exportação da plataforma |
| 9 | Códigos de Tipo de Valor da curva de alcance | Tabela |

Com esses insumos, conseguimos corrigir os 6 pontos e incluir validações que impedem a reincidência (nenhum campo de código sai com texto descritivo sem passar por tradução ou revisão).
