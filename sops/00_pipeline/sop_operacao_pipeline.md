# SOP 00 — Operação do Pipeline de Implantação

**Versão:** 1.0  
**Fase seguinte:** [SOP 01 — Coleta](../01_coleta/)

---

## Objetivo

Guiar o consultor na execução do pipeline de implantação de ponta a ponta para um novo cliente, desde a criação da estrutura de pastas até a geração do output final pronto para importação na plataforma.

## Quando usar

Toda vez que um novo cliente for incorporado ao processo de implantação, ou quando for necessário reprocessar os dados de um cliente existente (ex: nova carga, correção de dados, novo ciclo).

## Responsável

Consultor de implantação.

---

## Visão geral do fluxo

```
Receber dados do cliente
        │
        ▼
1. Inicializar estrutura        ./implantacao novo <cliente>
        │
        ▼
2. Depositar arquivos em        clientes/<cliente>/raw/
        │
        ▼
3. Rodar diagnóstico            ./implantacao analisar <cliente>
        │
        ▼
4. ── PONTO DE REVISÃO ──────────────────────────────────────────
   │  Revisar mapeamento.json                                    │
   │  Interagir com o cliente se necessário                      │
   │  Solicitar novos arquivos se necessário                     │
   └────────────────────────────────────────────────────────────
        │
        ▼
5. Travar o mapeamento          "travado": true  em mapeamento.json
        │
        ▼
6. Rodar transformação          ./implantacao transformar <cliente>
        │
        ▼
7. Verificar output             clientes/<cliente>/output/<data>/
```

O passo 4 é o único passo manual e não tem duração previsível — depende do cliente e da qualidade dos dados. Todos os outros passos são executados por comando.

---

## Pré-requisitos

- Repositório do projeto clonado e acessível
- Python 3.10+ instalado com as dependências de `requirements.txt`
- Terminal aberto na raiz do projeto (`implantacao/`)
- Arquivos do cliente recebidos e prontos para depositar

---

## Procedimento

### Passo 1 — Inicializar a estrutura do cliente

```bash
./implantacao novo <nome_cliente>
```

Use um identificador curto, sem espaços e em minúsculas (ex: `holding_abc`, `midia_xyz`, `varejo_sul`).

O comando cria a seguinte estrutura:

```
clientes/<nome_cliente>/
├── raw/          ← arquivos brutos do cliente (nunca editar)
├── config/       ← diagnóstico, mapeamento e dicionários gerados
├── staging/      ← dados transformados por entidade
├── output/       ← CSVs finais prontos para importação
└── relatorios/   ← relatório de validação e log do pipeline
```

**Se o cliente já existe**, o comando retorna erro. Para reprocessar, não recrie — use a pasta existente e limpe apenas as saídas se necessário (ver seção de alertas).

---

### Passo 2 — Depositar os arquivos do cliente

Coloque os arquivos exatamente como recebidos em `clientes/<nome_cliente>/raw/`.

Organize em subpastas quando houver arquivos de natureza diferente:

```
raw/
├── simples/       ← planilhas bem estruturadas
└── complexos/     ← arquivos fragmentados, com múltiplas versões ou problemas
```

> **Regra inviolável:** nenhum arquivo em `raw/` deve ser editado, renomeado ou deletado.  
> Os dados brutos do cliente são a fonte de verdade. Qualquer problema encontrado é tratado no mapeamento ou na transformação, nunca na origem.

Após depositar, proteja os arquivos contra edição acidental:

```bash
chmod -R 444 clientes/<nome_cliente>/raw/
find clientes/<nome_cliente>/raw/ -type d -exec chmod 555 {} \;
```

---

### Passo 3 — Rodar o diagnóstico

```bash
./implantacao analisar <nome_cliente>
```

Este comando executa dois agentes em sequência:

1. **Diagnóstico** — percorre todos os arquivos em `raw/`, identifica abas, colunas, tipos de dados e produz `config/diagnostico.json`
2. **Mapeamento automático** — lê o diagnóstico e tenta associar automaticamente cada coluna do cliente aos campos dos templates da plataforma, produzindo `config/mapeamento.json`

Ao final, o terminal exibe o resumo e orienta o próximo passo:

```
  ✓ diagnostico          ok        3 arquivos
  ⚠ mapeamento           aviso     concluído

  ► Próximo passo: revise e ajuste  clientes/<cliente>/config/mapeamento.json
    Quando estiver pronto, adicione  "travado": true  e rode:

    ./implantacao transformar <cliente>
```

O status `aviso` no mapeamento é normal quando o arquivo ainda não está travado.

---

### Passo 4 — Revisar o mapeamento (ponto de human-in-the-loop)

Este é o único passo inteiramente manual. Abra `clientes/<nome_cliente>/config/mapeamento.json`.

O arquivo tem uma entrada por entidade. Para cada uma, verifique:

**`arquivo_sugerido` e `aba_sugerida`**  
O agente tentou identificar de qual arquivo e aba vêm os dados. Se errou ou ficou `null`, corrija manualmente:

```json
"metas_individuais": {
  "arquivo_sugerido": "raw/simples/dados_cliente.xlsx",
  "aba_sugerida": "Metas Individuais",
  "header_linha": 1
}
```

Use `"header_linha": 1` quando o cabeçalho real da planilha estiver na segunda linha (linha 2 no Excel), o que é comum em planilhas com linha de título acima do cabeçalho.

**`campos`** — lista de mapeamentos campo a campo  
Cada entrada tem a forma:

```json
{
  "campo_template": "Login do Responsável pela Meta *",
  "campo_cliente": "login_responsavel",
  "confianca": "alta",
  "transformacao": "direto",
  "obrigatorio": true,
  "observacao": ""
}
```

Verifique especialmente:
- Campos com `"confianca": "baixa"` — o agente não encontrou uma correspondência clara
- Campos com `"campo_cliente": null` — o agente não encontrou nenhuma origem
- Campos marcados com `"⚠️ baixa confiança — revisar manualmente"` na observação

**Campos obrigatórios sem origem** são bloqueadores. Se existirem, não avance — resolva primeiro com o cliente (ver Passo 4.1).

#### Passo 4.1 — Interação com o cliente (quando necessário)

Se houver campos obrigatórios sem origem clara, abas com função ambígua, ou dados que parecem inconsistentes, reúna as dúvidas e contate o cliente antes de continuar.

Situações típicas que exigem retorno ao cliente:

| Situação | O que fazer |
|---|---|
| Campo obrigatório ausente em todos os registros | Perguntar se existe em outro arquivo ou se pode ser derivado |
| Tipo de meta ambíguo (individual vs. compartilhada) | Confirmar com o cliente antes de mapear |
| Código de área que não fecha com a hierarquia | Pedir confirmação da estrutura correta |
| Login em formato diferente do esperado | Alinhar o padrão antes de transformar |
| Arquivo prometido não enviado | Solicitar reenvio antes de avançar |

Se o cliente enviar arquivos novos, deposite-os em `raw/` e rode novamente o diagnóstico:

```bash
./implantacao analisar <nome_cliente>
```

O mapeamento será regenerado automaticamente (enquanto não estiver travado).

#### Passo 4.2 — Travar o mapeamento

Quando o mapeamento estiver correto e revisado, adicione `"travado": true` como **primeira chave** do arquivo:

```json
{
  "travado": true,
  "areas": { ... },
  "colaboradores": { ... },
  ...
}
```

A partir deste momento, o agente de mapeamento não sobrescreverá mais o arquivo, mesmo que o diagnóstico seja rerodado.

> Para desbloquear e regenerar automaticamente, remova a linha `"travado": true` ou altere para `false`.

---

### Passo 5 — Rodar a transformação

```bash
./implantacao transformar <nome_cliente>
```

Este comando executa sete agentes em sequência:

| Agente | O que faz |
|---|---|
| `areas` | Transforma hierarquia de áreas, aplica recodificação, preenche filial padrão |
| `colaboradores` | Transforma colaboradores, normaliza logins, preenche campos obrigatórios com defaults |
| `indicadores` | Transforma indicadores/KPIs (ignorado se não mapeado) |
| `metas` | Transforma metas individuais, compartilhadas e de projeto; extrai login de e-mail; deriva indicador se ausente |
| `curva_alcance` | Transforma curva de alcance (ignorado se não mapeado) |
| `valores` | Transforma valores previstos e realizados (ignorado se não mapeado) |
| `validacao` | Valida todos os staging contra os templates, verifica integridade referencial e gera output |

Entidades não mapeadas (arquivo `null`) são ignoradas com aviso — isso é esperado e não bloqueia o pipeline.

---

### Passo 6 — Interpretar o resultado

#### Status possíveis

| Status | Significado | O que fazer |
|---|---|---|
| `OK` | Todas as entidades passaram na validação | Avançar para importação |
| `AVISO` | Pipeline concluiu, mas há observações | Ler os avisos; decidir se exigem correção |
| `ERRO` | Uma ou mais entidades bloquearam | Ler os erros, corrigir, rerrodar |

#### Erros mais comuns

**Referências inválidas** — logins das metas não encontrados nos colaboradores, ou áreas referenciadas que não existem.  
→ Verificar se a transformação de cada entidade foi bem-sucedida. Geralmente é um problema de normalização (caixa, caracteres especiais) ou dado ausente.

**Campo obrigatório vazio** — uma coluna obrigatória do template ficou sem valores.  
→ Voltar ao `mapeamento.json`, corrigir o campo origem e rerrodar `transformar`.

**Entidade bloqueada por duplicatas** — o mesmo código de área ou login aparece mais de uma vez.  
→ Verificar o dado de origem. Pode ser necessário deduplicar na fonte ou aplicar uma regra de merge.

---

### Passo 7 — Verificar o output

Se a validação aprovada, os arquivos finais ficam em:

```
clientes/<nome_cliente>/output/<data-de-hoje>/
├── Import_Áreas (Estrutura Hierárquica).csv
├── Import_Colaboradores.csv
├── Import_Indicadores (KPI).csv
├── Import_Metas Individuais.csv
└── ...
```

Antes de importar na plataforma, faça uma conferência rápida:

- [ ] O número de linhas de áreas é compatível com o esperado?
- [ ] O número de colaboradores bate com o informado pelo cliente?
- [ ] As metas têm o número de registros esperado?
- [ ] Os códigos de área nas metas existem no arquivo de áreas?
- [ ] Os logins nas metas existem no arquivo de colaboradores?

O relatório detalhado de validação está em `clientes/<nome_cliente>/relatorios/relatorio_validacao.md`.

---

## Checklist de conclusão

- [ ] Estrutura do cliente criada com `./implantacao novo`
- [ ] Arquivos depositados em `raw/` e protegidos contra edição
- [ ] Diagnóstico rodado com `./implantacao analisar`
- [ ] `mapeamento.json` revisado campo a campo
- [ ] Dúvidas com o cliente resolvidas (se houver)
- [ ] `mapeamento.json` travado com `"travado": true`
- [ ] Transformação rodada com `./implantacao transformar`
- [ ] Status final `OK` ou avisos avaliados e aceitos
- [ ] Output conferido antes de importar

---

## Saídas deste SOP

| Artefato | Localização |
|---|---|
| Diagnóstico estrutural | `clientes/<cliente>/config/diagnostico.json` |
| Resumo do diagnóstico | `clientes/<cliente>/config/diagnostico_resumo.md` |
| Mapeamento de campos | `clientes/<cliente>/config/mapeamento.json` |
| Dicionário de recodificação de áreas | `clientes/<cliente>/config/dicionario_areas.csv` |
| Dicionário de recodificação de metas | `clientes/<cliente>/config/dicionario_metas_<tipo>.csv` |
| Arquivos transformados | `clientes/<cliente>/staging/` |
| Output para importação | `clientes/<cliente>/output/<data>/` |
| Relatório de validação | `clientes/<cliente>/relatorios/relatorio_validacao.md` |
| Log do pipeline | `clientes/<cliente>/relatorios/log_pipeline.json` |

---

## Alertas e situações comuns

**Preciso reprocessar um cliente que já foi rodado antes.**  
Não recrie a estrutura. Limpe apenas as saídas geradas e mantenha o `mapeamento.json` travado:

```bash
rm -rf clientes/<cliente>/staging \
       clientes/<cliente>/output \
       clientes/<cliente>/relatorios \
       clientes/<cliente>/config/diagnostico.json \
       clientes/<cliente>/config/diagnostico_resumo.md \
       clientes/<cliente>/config/dicionario_*.csv
```

Depois rode normalmente:

```bash
./implantacao analisar    <cliente>   # gera novo diagnóstico (mapeamento preservado)
./implantacao transformar <cliente>
```

**O cliente enviou uma versão nova de um arquivo.**  
Não substitua o arquivo original. Crie uma subpasta com data (`raw/v2_2025-05/`) e deposite lá. Se o `mapeamento.json` precisar apontar para o novo arquivo, atualize `arquivo_sugerido` — não é necessário destravá-lo para isso, apenas edite o campo.

**O mapeamento automático ficou muito ruim (muitos campos errados).**  
Isso acontece quando o cliente usa nomes de coluna muito diferentes do padrão. Edite manualmente o `mapeamento.json` — é mais rápido do que tentar fazer o agente acertar. O travamento garante que seu trabalho não será perdido.

**A transformação falhou em uma entidade mas as outras estão certas.**  
O pipeline não para em erros de entidades não-bloqueadoras. Você pode rerrodar apenas as etapas necessárias usando o orquestrador diretamente com `escopo`:

```python
from agentes.orquestrador import agente as orc
orc.executar("clientes/<cliente>", escopo=["colaboradores", "validacao"])
```

**A validação aprovou mas os números parecem errados.**  
A validação verifica estrutura e referências, não a correção do negócio. A conferência manual do Passo 7 é obrigatória.
