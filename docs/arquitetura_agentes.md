# Arquitetura de Agentes

---

## Princípio de separação

| Camada | Responsabilidade | Exemplo |
|---|---|---|
| **Skills** | Capacidade técnica, universal, sem domínio | "detectar #N/A em qualquer planilha" |
| **Agentes** | Conhecimento de domínio + orquestração de skills | "entender que essa coluna é o Login do Responsável pela Meta" |
| **Orquestrador** | Sequência, dependências, falhas, relatório final | "transformar Áreas antes de Colaboradores" |

A inteligência de negócio mora nos agentes. A inteligência técnica mora nas skills.

---

## Visão geral da arquitetura

```
                        ┌─────────────────────┐
                        │    Orquestrador     │
                        └──────────┬──────────┘
                                   │ coordena
          ┌───────────┬────────────┼────────────┬───────────┐
          ▼           ▼            ▼            ▼           ▼
   ┌─────────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Diagnóstico │ │Mapeamento│ │Transforma│ │Hierarquia│ │ Validação│
   │             │ │          │ │  -ção    │ │          │ │          │
   └─────────────┘ └──────────┘ └────┬─────┘ └──────────┘ └──────────┘
                                     │
              ┌──────────┬───────────┼───────────┬──────────┐
              ▼          ▼           ▼           ▼          ▼
           Áreas   Colaboradores Indicadores  Metas     Valores
```

---

## Os 9 agentes

### 1. Agente Orquestrador
**Papel:** Coordena o pipeline completo para um cliente.

- Recebe: nome do cliente + escopo (quais entidades processar)
- Chama os agentes na ordem correta respeitando dependências
- Monitora falhas e decide: tentar novamente, pular ou escalar
- Produz o relatório final de execução
- **Não transforma dados** — só orquestra quem transforma

**Ordem de execução que conhece:**
```
Diagnóstico → Mapeamento → Áreas → Colaboradores → Indicadores
→ Metas → Valores → Validação
```

---

### 2. Agente de Diagnóstico
**Papel:** Entender o que o cliente enviou antes de qualquer transformação.

- Recebe: caminho da pasta `raw/` do cliente
- Usa skills: perfilamento tabular, detecção de encoding, diagnóstico de erros, detecção de duplicatas, detecção de PII
- Produz: `config/diagnostico.md` preenchido com estrutura, qualidade e entidades identificadas
- **É o único agente que lê diretamente de `raw/`**

---

### 3. Agente de Mapeamento
**Papel:** Construir a ponte semântica entre o esquema do cliente e o esquema da plataforma.

- Recebe: `diagnostico.md` + templates de referência
- Analisa cada campo do cliente e decide: qual coluna do template corresponde? que transformação é necessária?
- Produz: `config/mapeamento.json` — um mapeamento campo a campo por entidade
- **É o agente mais intensivo em raciocínio LLM** — lida com ambiguidade semântica
- Quando não consegue mapear com confiança, gera lista de dúvidas para o consultor

**Estrutura do mapeamento produzido:**
```json
{
  "areas": [
    {
      "campo_cliente": "cod_unidade",
      "campo_template": "Código da Área*",
      "transformacao": "recodificacao",
      "confianca": "alta",
      "observacao": ""
    }
  ]
}
```

---

### 4. Agente de Áreas
**Papel:** Transformar dados de estrutura organizacional.

- Recebe: dados brutos de áreas (via staging) + `mapeamento.json`
- Usa skills: encoding, recodificação, validação de hierarquia, reconstrução de hierarquia
- Produz: `staging/01_areas/areas_transformadas.csv`
- Conhecimento de domínio: o que é área raiz, como tratar área sem superior, formatos de código aceitos pela plataforma

---

### 5. Agente de Colaboradores
**Papel:** Transformar o cadastro de pessoas.

- Recebe: dados brutos de colaboradores + `mapeamento.json` + output de Áreas (para validar referências)
- Usa skills: encoding, recodificação, normalização de domínio, quebra/junção de campos
- Produz: `staging/02_colaboradores/colaboradores_transformados.csv`
- Conhecimento de domínio: regras de geração de login, campos booleanos da plataforma (Ativo, Autenticação Windows, etc.), formato de áreas de responsabilidade

---

### 6. Agente de Indicadores
**Papel:** Transformar definições de KPIs.

- Recebe: dados brutos de indicadores + `mapeamento.json`
- Usa skills: encoding, recodificação, normalização de domínio
- Produz: `staging/03_indicadores/indicadores_transformados.csv`
- Conhecimento de domínio: polaridade (maior melhor vs. menor melhor), unidades de medida aceitas, faixas de farol, frequências de acompanhamento

---

### 7. Agente de Metas
**Papel:** Transformar metas — o dado mais complexo do pipeline.

- Recebe: dados brutos de metas + `mapeamento.json` + outputs de Áreas, Colaboradores e Indicadores
- Usa skills: encoding, recodificação, normalização, pipe-separação, quebra/junção
- Produz:
  - `staging/04_metas_individuais/`
  - `staging/05_metas_compartilhadas/`
  - `staging/06_metas_projeto/`
- Conhecimento de domínio: **classificar o tipo de cada meta** (individual/compartilhada/projeto), regras de peso, tipos de agregação, tipos de definição de valor
- É o agente com maior risco de ambiguidade — pode precisar acionar o consultor humano

---

### 8. Agente de Valores
**Papel:** Transformar valores previstos e realizados das metas.

- Recebe: dados brutos de valores + `mapeamento.json` + outputs de Metas
- Usa skills: conversão de datas Excel, recodificação, normalização
- Produz:
  - `staging/08_valores_previstos/`
  - `staging/09_valores_realizados/`
- Conhecimento de domínio: correspondência entre períodos do cliente e índices de coluna do template XLSX (0–13)

---

### 9. Agente de Validação
**Papel:** Validar todos os arquivos de staging antes de gerar o output final.

- Recebe: todos os arquivos de staging + templates de referência
- Usa skills: validação de schema, validação de integridade referencial, detecção de duplicatas
- Verifica: schema, unicidade, referências cruzadas, regras de negócio (pesos, hierarquias)
- Produz: `relatorios/relatorio_validacao.md` + arquivos aprovados em `output/`
- Decide: aprovado para importação ou bloqueado com lista de problemas

---

## Mapa agentes × skills

| Agente | Wave 1 | Wave 2 | Wave 3 | Wave 4 | Wave 5 | Wave 6 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| Diagnóstico | ✅ | ✅ | | | | |
| Mapeamento | ✅ | | | | | |
| Áreas | ✅ | | ✅ | | ✅ | |
| Colaboradores | ✅ | | ✅ | ✅ | | |
| Indicadores | ✅ | | ✅ | ✅ | | |
| Metas | ✅ | | ✅ | ✅ | | |
| Valores | ✅ | | ✅ | ✅ | | |
| Validação | | ✅ | | | ✅ | ✅ |

---

## Gap na estrutura de pastas atual

A estrutura de `agentes/` criada tem 6 pastas. Precisamos adicionar 3:

```
agentes/
├── areas/             ✅ existe
├── colaboradores/     ✅ existe
├── diagnostico/       ❌ falta
├── indicadores/       ✅ existe
├── mapeamento/        ❌ falta
├── metas/             ✅ existe
├── orquestrador/      ✅ existe
├── validacao/         ❌ falta
└── valores/           ✅ existe
```

---

## Fluxo de dados entre agentes

```
raw/ (somente leitura)
  └─► Diagnóstico ──► config/diagnostico.md
                            │
                            ▼
                      Mapeamento ──► config/mapeamento.json
                            │
              ┌─────────────┼──────────────────┐
              ▼             ▼                  ▼
           Áreas      Indicadores        (paralelo possível)
              │             │
              ▼             │
        Colaboradores       │
              │             │
              └──────┬──────┘
                     ▼
                   Metas
                     │
                     ▼
                  Valores
                     │
                     ▼
               Validação ──► output/ + relatorio_validacao.md
```

**Paralelismo possível:** Áreas e Indicadores não dependem um do outro — podem rodar simultaneamente.
