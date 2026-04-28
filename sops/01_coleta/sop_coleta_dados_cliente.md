# SOP 01 — Coleta e Recebimento de Dados do Cliente

**Versão:** 1.0  
**Fase seguinte:** [SOP 02 — Diagnóstico](../02_diagnostico/)

---

## Objetivo

Garantir que os dados recebidos de um novo cliente sejam organizados, protegidos e documentados corretamente antes de qualquer análise ou transformação.

## Quando usar

Toda vez que um cliente enviar arquivos de dados para iniciar ou retomar um processo de implantação.

## Responsável

Consultor de implantação.

---

## Pré-requisitos

- Acesso à estrutura de pastas do projeto (`clientes/`)
- Nome ou código identificador do cliente definido
- Confirmação de qual ciclo/período os dados se referem (ex: "metas 2024", "estrutura vigente")

---

## Procedimento

### Passo 1 — Criar a pasta do cliente

Copie a estrutura modelo para um novo cliente:

```bash
cp -r clientes/_modelo clientes/<nome_cliente>
```

Use um nome curto, sem espaços e em minúsculo (ex: `holding_abc`, `midia_xyz`).

### Passo 2 — Receber os arquivos

Coloque os arquivos exatamente como recebidos dentro de `clientes/<nome_cliente>/raw/`.

Organize em subpastas se houver mais de um conjunto:

```
raw/
├── simples/       ← dados mais estruturados (ex: planilha única com abas)
└── complexos/     ← dados fragmentados, com múltiplas versões ou erros
```

> **Regra inviolável:** nenhum arquivo dentro de `raw/` deve ser editado, renomeado ou deletado. Esses são os dados originais do cliente. Qualquer problema encontrado será tratado nas etapas seguintes, nunca na origem.

### Passo 3 — Proteger os arquivos como somente leitura

```bash
chmod -R 444 clientes/<nome_cliente>/raw/
find clientes/<nome_cliente>/raw/ -type d -exec chmod 555 {} \;
```

### Passo 4 — Registrar o que foi recebido

Crie o arquivo `clientes/<nome_cliente>/config/recebimento.md` com as informações abaixo:

```
# Recebimento de Dados — <Nome do Cliente>

Data de recebimento:
Responsável pelo envio (cliente):
Consultor responsável:
Período/ciclo de referência dos dados:

## Arquivos recebidos

| Arquivo | Formato | Abas / Sheets | Observações |
|---------|---------|---------------|-------------|
|         |         |               |             |

## Canal de recebimento
(ex: e-mail, SharePoint, Google Drive, WhatsApp)

## Pendências na entrega
(campos em branco, arquivos prometidos e não enviados, dúvidas abertas)
```

### Passo 5 — Identificar as entidades presentes

Para cada arquivo recebido, identifique quais entidades do sistema estão presentes. Use a tabela abaixo como guia:

| Entidade | Template correspondente | Presente? |
|---|---|---|
| Áreas (hierarquia) | `Import_Áreas (Estrutura Hierárquica).csv` | |
| Colaboradores | `Import_Colaboradores.csv` | |
| Indicadores / KPIs | `Import_Indicadores (KPI).csv` | |
| Metas Individuais | `Import_Metas Individuais.csv` | |
| Metas Compartilhadas | `Import_Metas Compartilhadas.csv` | |
| Metas de Projeto | `Import_Metas Projeto.csv` | |
| Curva de Alcance | `Import_Curva de Alcance.csv` | |
| Valores Previstos | `Import_Valores Previstos das Metas.xlsx` | |
| Valores Realizados | `Import_Valores Realizados das Metas.xlsx` | |

Registre no `recebimento.md` quais estão presentes, quais estão ausentes e quais são dúvida.

### Passo 6 — Primeiro contato com os dados

Abra cada arquivo recebido e responda as perguntas abaixo **sem editar nada**:

**Estrutura:**
- [ ] Os dados estão em uma aba única ou em múltiplas abas?
- [ ] Há abas de instrução ou legenda junto com os dados?
- [ ] Há abas claramente de rascunho ou descartáveis (ex: "Planilha1", "teste")?

**Qualidade:**
- [ ] Há células com erro (`#N/A`, `#REF!`, `#VALOR!`)?
- [ ] Há linhas completamente vazias no meio dos dados?
- [ ] Há colunas sem cabeçalho?
- [ ] Os identificadores parecem consistentes (mesma formatação, sem mistura de tipo)?

**Sensibilidade:**
- [ ] Os dados contêm CPF, e-mail ou outros dados pessoais?
- [ ] Há dados salariais ou de avaliação individual?

Registre as respostas no `recebimento.md` para guiar o diagnóstico.

---

## Checklist de conclusão

Antes de avançar para o SOP 02, confirme:

- [ ] Pasta do cliente criada em `clientes/<nome_cliente>/`
- [ ] Todos os arquivos estão em `raw/` com permissão somente leitura
- [ ] `recebimento.md` preenchido em `config/`
- [ ] Entidades presentes e ausentes identificadas
- [ ] Primeiro contato com os dados feito e registrado

---

## Saídas deste SOP

| Artefato | Localização |
|---|---|
| Dados brutos do cliente | `clientes/<nome_cliente>/raw/` |
| Registro de recebimento | `clientes/<nome_cliente>/config/recebimento.md` |

---

## Alertas e situações comuns

**O cliente enviou uma versão nova de um arquivo já recebido.**
Não substitua o arquivo original. Crie uma subpasta com data (`raw/v2_2024-05/`) e coloque a nova versão lá. Documente no `recebimento.md`.

**O arquivo veio com fórmulas quebradas (`#REF!`, `#N/A`).**
Não tente corrigir agora. Registre a ocorrência no `recebimento.md`. A resolução acontece no SOP 02.

**Os dados contêm CPF ou outros dados pessoais sensíveis.**
Sinalize no `recebimento.md`. Certifique-se de que o acesso à pasta do cliente está restrito às pessoas envolvidas na implantação.

**Não está claro a qual entidade um arquivo pertence.**
Registre como "entidade indefinida" no `recebimento.md` e sinalize para revisão no SOP 02.
