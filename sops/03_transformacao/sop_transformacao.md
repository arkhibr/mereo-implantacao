# SOP 03 — Transformação dos Dados

**Versão:** 1.0  
**Fase anterior:** [SOP 02 — Diagnóstico](../02_diagnostico/)  
**Fase seguinte:** [SOP 04 — Validação](../04_validacao/)

---

## Objetivo

Transformar os dados brutos do cliente nos arquivos prontos para importação na plataforma, seguindo o mapeamento produzido no diagnóstico e respeitando a ordem de dependência entre entidades.

## Quando usar

Após a conclusão do SOP 02, com o `diagnostico.md` completo, todas as dúvidas críticas respondidas pelo cliente e nenhum bloqueador em aberto.

## Responsável

Consultor de implantação com suporte dos agentes de transformação.

---

## Pré-requisitos

- SOP 02 concluído (checklist confirmado)
- `clientes/<nome_cliente>/config/diagnostico.md` completo
- Dúvidas críticas do Passo 6 do SOP 02 respondidas pelo cliente
- Nenhum bloqueador em aberto (campos obrigatórios sem origem)

---

## Princípios desta fase

**Nunca transformar sobre `raw/`.** Todo trabalho acontece em `staging/` e o resultado final vai para `output/`. Os dados originais do cliente permanecem intocados.

**Transformar na ordem de dependência.** Algumas entidades referenciam outras. Transformar fora de ordem gera referências inválidas nos arquivos de saída.

**Registrar cada decisão.** Toda escolha não trivial feita durante a transformação deve ser anotada no `log_transformacao.md`. Isso garante rastreabilidade e facilita revisões futuras.

---

## Ordem obrigatória de transformação

As entidades têm dependências entre si. Respeite esta sequência:

```
1. Áreas               ← sem dependências externas
2. Colaboradores       ← depende de: Áreas
3. Indicadores (KPI)   ← sem dependências externas
4. Metas Individuais   ← depende de: Áreas, Colaboradores, Indicadores
5. Metas Compartilhadas← depende de: Áreas, Colaboradores, Metas Individuais
6. Metas de Projeto    ← depende de: Áreas, Colaboradores, Indicadores
7. Curva de Alcance    ← depende de: todas as Metas
8. Valores Previstos   ← depende de: todas as Metas
9. Valores Realizados  ← depende de: todas as Metas
```

---

## Procedimento

### Passo 1 — Preparar o ambiente de staging

Crie a estrutura de trabalho dentro de `staging/`:

```
clientes/<nome_cliente>/staging/
├── 01_areas/
├── 02_colaboradores/
├── 03_indicadores/
├── 04_metas_individuais/
├── 05_metas_compartilhadas/
├── 06_metas_projeto/
├── 07_curva_alcance/
├── 08_valores_previstos/
└── 09_valores_realizados/
```

Crie também o arquivo de log:

```
clientes/<nome_cliente>/config/log_transformacao.md
```

Com o cabeçalho:

```
# Log de Transformação — <Nome do Cliente>

Data de início:
Consultor responsável:

## Decisões e observações

| # | Entidade | Campo | Decisão tomada | Motivo |
|---|---|---|---|---|
```

---

### Passo 2 — Construir o dicionário de recodificação (quando necessário)

Se o cliente usa identificadores numéricos internos (ex: `289`, `1510`), construa um dicionário de tradução antes de transformar qualquer entidade.

O dicionário mapeia o código do cliente para o código que será usado na plataforma:

```
clientes/<nome_cliente>/config/dicionario_codigos.csv

tipo_entidade ; codigo_cliente ; codigo_plataforma ; descricao
area          ; 55             ; AREA_055          ; Diretoria Comercial
colaborador   ; 289            ; COL_289           ; João da Silva
indicador     ; 1437           ; IND_1437          ; Receita Bruta
meta          ; 1510           ; MET_1510          ; Meta Vendas Q1
```

**Regras para geração de códigos da plataforma:**

| Entidade | Prefixo sugerido | Exemplo |
|---|---|---|
| Área | `AREA_` | `AREA_055` |
| Colaborador | `COL_` | `COL_289` |
| Indicador | `IND_` | `IND_1437` |
| Meta Individual | `METI_` | `METI_1510` |
| Meta Compartilhada | `METC_` | `METC_1864` |
| Meta de Projeto | `METP_` | `METP_0042` |

> O dicionário é o artefato central desta fase. Ele garante consistência referencial — o mesmo código de área usado em Colaboradores e em Metas deve ser exatamente o mesmo.

---

### Passo 3 — Executar a transformação por entidade

Para cada entidade, siga o ciclo:

```
Ingerir → Transformar campo a campo → Validar localmente → Salvar em staging/
```

#### 3.1 Ingestão

- Leia o arquivo de `raw/` referenciado no `diagnostico.md`
- Identifique a aba correta
- Elimine linhas de cabeçalho extras, rodapés e linhas totalmente vazias
- Corrija encoding se necessário (UTF-8 como padrão de saída)

#### 3.2 Transformação campo a campo

Execute cada transformação conforme o mapeamento do diagnóstico. Referência rápida por tipo:

| Tipo | O que fazer |
|---|---|
| **Direto** | Copiar o valor sem alteração |
| **Recodificação** | Substituir pelo código correspondente no dicionário |
| **Derivado** | Aplicar a regra acordada (ex: `login = nome.sobrenome`) |
| **Quebrar** | Separar o campo em múltiplos usando o delimitador identificado |
| **Juntar** | Concatenar campos com separador adequado |
| **Converter data** | Serial Excel → data: `data = serial - 25569` dias desde 01/01/1970; formatar como `DD/MM/AAAA` |
| **Normalizar** | Aplicar tabela de equivalências (ex: "Sim"/"S"/"1" → `1`) |
| **Pipe-separar** | Agregar múltiplas linhas de um mesmo registro em um campo `val1\|val2\|val3` |
| **Ausente com padrão** | Preencher com valor default acordado com o cliente |

#### 3.3 Tratamento de erros residuais

Para linhas com `#N/A` ou `#REF!` que não foram resolvidos antes:

- **Opção A — Corrigir:** se a origem do erro for identificável (ex: referência a outra aba), buscar o valor correto
- **Opção B — Omitir:** excluir a linha do output e registrar no log com justificativa
- **Opção C — Escalar:** pausar a transformação desta entidade e retornar ao cliente

Nunca preencher com valor inventado. Registrar toda decisão no `log_transformacao.md`.

#### 3.4 Salvar o intermediário em staging

Salve o resultado de cada entidade transformada em sua pasta dentro de `staging/`:

```
staging/01_areas/areas_transformadas.csv
staging/02_colaboradores/colaboradores_transformados.csv
...
```

---

### Passo 4 — Validação cruzada entre entidades

Após transformar todas as entidades, verifique a integridade referencial entre elas:

| Verificação | O que checar |
|---|---|
| Colaboradores → Áreas | Cada `Código da Área` em Colaboradores existe em Áreas? |
| Metas → Colaboradores | Cada `Login do Responsável` em Metas existe em Colaboradores? |
| Metas → Indicadores | Cada `Código do Indicador` em Metas existe em Indicadores? |
| Metas → Metas (superior) | Cada `Código de Meta Superior` existe como meta? |
| Curva → Metas | Cada `Código da Meta` em Curva existe em alguma tabela de Metas? |
| Valores → Metas | Cada `Código da Meta` em Valores existe em alguma tabela de Metas? |

Qualquer referência inválida deve ser registrada e resolvida antes de gerar o output final.

---

### Passo 5 — Gerar os arquivos de output

Com os intermediários em `staging/` validados, gere os arquivos finais em `output/` no formato exato do template:

```
clientes/<nome_cliente>/output/
├── Import_Áreas (Estrutura Hierárquica).csv
├── Import_Colaboradores.csv
├── Import_Indicadores (KPI).csv
├── Import_Metas Individuais.csv
├── Import_Metas Compartilhadas.csv
├── Import_Metas Projeto.csv
├── Import_Curva de Alcance.csv
├── Import_Valores Previstos das Metas.xlsx
└── Import_Valores Realizados das Metas.xlsx
```

**Requisitos dos arquivos de saída:**

- CSV: delimitador `;` (ponto e vírgula), encoding UTF-8, sem BOM
- Campos multi-valor: separador `|` (pipe) dentro da célula
- Primeira linha: cabeçalho exatamente igual ao template (incluindo `*` nos obrigatórios)
- Sem linhas extras de exemplo ou instrução
- Sem colunas a mais além das do template

---

### Passo 6 — Fechar o log de transformação

Ao final, complete o `log_transformacao.md` com:

```
## Resumo final

Data de conclusão:
Entidades transformadas: X de 9
Linhas omitidas por erro (total): X
Dicionário de códigos: sim / não (não necessário)
Pendências abertas: sim / não

## Pendências (se houver)
| # | Entidade | Descrição | Status |
|---|---|---|---|
```

---

## Checklist de conclusão

Antes de avançar para o SOP 04, confirme:

- [ ] Todas as entidades transformadas na ordem correta
- [ ] Dicionário de recodificação criado (se aplicável)
- [ ] Erros residuais tratados (corrigidos, omitidos ou escalados — nunca inventados)
- [ ] Validação cruzada entre entidades executada sem referências inválidas
- [ ] Arquivos de output gerados com formato exato dos templates
- [ ] `log_transformacao.md` completo e fechado
- [ ] Nenhuma linha com valor fictício ou placeholder nos arquivos de output

---

## Saídas deste SOP

| Artefato | Localização |
|---|---|
| Dados intermediários por entidade | `clientes/<nome_cliente>/staging/` |
| Dicionário de recodificação | `clientes/<nome_cliente>/config/dicionario_codigos.csv` |
| Arquivos prontos para importação | `clientes/<nome_cliente>/output/` |
| Log de decisões da transformação | `clientes/<nome_cliente>/config/log_transformacao.md` |

---

## Alertas e situações comuns

**Um código de área aparece em Colaboradores mas não existe em Áreas.**
Integridade referencial quebrada. Não gerar o arquivo de Colaboradores até que a área exista. Voltar ao SOP 02 se necessário.

**O cliente tem metas com pesos que somam mais de 100%.**
Registrar no log e escalar para o cliente — a plataforma pode rejeitar na importação. Não corrigir automaticamente.

**A hierarquia de áreas tem ciclos (área A é superior de B, B é superior de A).**
Erro crítico de modelagem. A plataforma não aceita hierarquias circulares. Escalar para o cliente imediatamente.

**Dois colaboradores têm o mesmo login derivado.**
O login deve ser único. Aplicar desambiguação acordada (ex: adicionar inicial do meio, número sequencial) e registrar no log.

**Os valores previstos/realizados têm uma estrutura de colunas que não bate com o template XLSX.**
Os templates de valores têm colunas numéricas (0–13) que representam períodos. Confirmar com o cliente a correspondência entre os períodos do arquivo deles e os índices do template antes de preencher.
