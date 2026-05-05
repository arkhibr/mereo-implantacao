# Plano — Agente de Inferência

**Data**: 2026-05-05
**Status**: aguardando aprovação dos 5 pontos antes de implementar
**Sessão de origem**: discussão sobre completar entidades faltantes (indicadores) a partir de outras informações enviadas pelo cliente (metas individuais).

---

## Motivação

O cliente nem sempre entende o escopo completo do que precisa enviar. Tipicamente manda metas individuais, mas esquece (ou não tem) o catálogo de indicadores/KPIs explícito. Como as metas referenciam o indicador (nome, código, e às vezes unidade/polaridade), é viável **inferir** o template `Import_Indicadores (KPI).csv` a partir das metas — desde que a inferência seja claramente marcada e revisável pelo consultor.

A mesma lógica vale para outras entidades em graus variados de viabilidade.

---

## Estratégia geral

**Premissa**: inferência é uma etapa **distinta** de mapeamento.
- Mapeamento decide *de onde vem cada coisa*.
- Inferência fabrica *o que falta* a partir do que existe.

Mantém os contratos atuais intactos e dá pra desligar a inferência inteira sem afetar o resto do pipeline.

**Forma**: novo agente LLM (`inferencia_llm`), espelhando o padrão dos outros 4 (SOP-prompt + tools deterministas + HITL). Não vira tool do mapeamento — separação de mandato.

**Saída**: pasta nova `clientes/<cliente>/inferencia/` (paralela a `raw/`, `config/`, `staging/`, `output/`, `relatorios/`, `sessoes/`), contendo `<entidade>_inferidos.csv` no formato exato do template da plataforma + colunas auxiliares (`_origem`, `_confianca`, `_derivado_de`).

**Por que pasta nova e não reusar uma existente:**
- `raw/` é **imutável** — só guarda o que o cliente enviou. Princípio de auditoria do projeto. Nada derivado entra ali, nem em subpasta.
- `staging/` é resultado de transformação determinista a partir de fonte já mapeada. Inferência é pré-fonte: alimenta o mapeamento, não consome dele.
- `config/` é planejamento (diagnóstico, mapeamento, dicionários). Inferência produz dados, não planejamento.
- `output/` é entrega final. Inferência é intermediário pra revisão do consultor.

Razões para a forma escolhida:
- O pipeline de transformação roda normal em cima do arquivo (depois que o consultor aponta a fonte no mapeamento).
- O consultor pode abrir e editar antes de aprovar.
- A pasta `inferencia/` na raiz do cliente torna a auditoria evidente — fica claro o que veio do cliente vs o que foi fabricado.
- Não modificamos `mapeamento.json` automaticamente — o consultor decide se aponta a entidade pro arquivo inferido depois de revisar.

**Princípio de honestidade**:
- Campos identitários (código, nome) podem ser inferidos com `alta`.
- Campos semânticos (polaridade, unidade, periodicidade) saem com `media` ou `baixa` por default.
- O relatório destaca cada um — o consultor revisa antes de virar entrada.

---

## MVP (Fase 1) — escopo mínimo

1. **Só indicadores**, **só a partir de metas individuais**.

2. **Tools do agente**:
   - `obter_metas_individuais_brutas` — lê o arquivo/aba que o `mapeamento.json` aponta como fonte de `metas_individuais`. Se mapeamento ausente ou sem essa entidade, falha com mensagem orientada.
   - `obter_amostras_aba` (já existe, reaproveitar) — pra inspecionar valores quando o nome não é claro.
   - `extrair_candidatos_indicadores` — heurística determinista que extrai conjunto único de (código, nome) das metas e propõe deduplicação por similaridade. LLM revisa e ajusta.
   - `gravar_indicadores_inferidos` — grava o CSV em `inferencia/Indicadores_inferidos.csv` + relatório em `relatorios/relatorio_inferencia.md`.
   - `perguntar_humano` — para ambiguidades (ex: dois nomes muito parecidos, dedup ou separar?).

3. **Comando CLI novo**: `./implantacao inferir <cliente>` (sem subargumento por enquanto).

4. **SOP**: `sops/agentes/sop_inferencia.md` com regras de honestidade (níveis de confiança por tipo de campo, quando perguntar).

5. **Validação E2E**: rodar no cliente demo. Esperar que ele extraia indicadores únicos das metas existentes e gere o CSV + relatório. Se o consultor aprovar manualmente, ele edita o `mapeamento.json` pra apontar `indicadores.arquivo_sugerido` pra `inferencia/Indicadores_inferidos.csv` — e a transformação determinista normal roda em cima.

---

## O que fica de fora do MVP (Fase 2+)

- Atualização automática do `mapeamento.json` (com HITL) — só depois que o MVP estiver maduro.
- Integração com orquestrador (decidir `inferir` quando uma entidade canônica está sem fonte).
- Outras entidades:
  - Áreas a partir de metas
  - Colaboradores a partir de metas
  - Detecção de "compartilhada vs individual" por estrutura
- Inferência cruzada (ex: usar metas de projeto + individuais + compartilhadas para um conjunto único de indicadores).

---

## Inferências possíveis em ordem de viabilidade (referência futura)

| Entidade | Sinal | Fonte primária | Risco principal |
|---|---|---|---|
| **Indicadores** | alto | metas individuais | dedup (mesma KPI com nomes ligeiramente diferentes) |
| **Áreas** | médio | departamento/área nas metas | hierarquia perdida; só vale como fallback ou validação cruzada quando cliente também manda |
| **Colaboradores** | médio | login/email/nome nas metas | bom para detectar gente em meta que não está no roster (sintoma) |
| **Tipo de meta** (compartilhada/projeto vs individual) | baixo estrutural | múltiplos colaboradores em mesmo código | frágil sem flag explícita do cliente |
| **Curva de alcance / valores** | baixo | — | quase sempre vem de outra fonte; inferir é arriscado |

**Tradeoff que importa**: atributos como polaridade, periodicidade e fórmula de cálculo são **decisões de negócio** do cliente. Identidade do indicador (nome, código, unidade) é seguro de inferir; semântica do KPI não.

---

## Pontos pendentes de aprovação

Os 5 pontos abaixo estão aguardando "OK" do consultor antes de qualquer linha de código:

1. **Agente separado** (não tool do mapeamento). OK?
2. **Saída em pasta nova `clientes/<cliente>/inferencia/<entidade>_inferidos.csv`** (paralela a raw/, staging/, etc) com colunas extras de auditoria. OK?
3. **Não alterar `mapeamento.json` automaticamente no MVP** — consultor revisa o CSV e atualiza manualmente. OK?
4. **Escopo MVP = só indicadores, só a partir de metas individuais**. OK?
5. **Comando `./implantacao inferir <cliente>`** (sem subargumento por enquanto). OK?

Se aprovar os 5, próximo passo é detalhar:
- Formato exato do CSV inferido (quais colunas do template + auxiliares).
- Esqueleto do SOP-prompt (regras de honestidade, gates de HITL).

Antes de virar diff.
