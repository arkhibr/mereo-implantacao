# SOP 05 — Importação na Plataforma

**Versão:** 1.0  
**Fase anterior:** [SOP 04 — Validação](../04_validacao/)

---

## Objetivo

Executar a importação dos arquivos validados no ambiente da plataforma RHTec, na ordem correta, monitorando erros em cada etapa e garantindo que o ambiente do cliente esteja íntegro ao final.

## Quando usar

Após a conclusão do SOP 04, com o relatório de validação aprovado (nenhum achado Crítico ou Alto em aberto).

## Responsável

Consultor de implantação com acesso ao ambiente do cliente na plataforma.

---

## Pré-requisitos

- SOP 04 concluído e relatório de validação aprovado
- Acesso ao ambiente do cliente na plataforma (credenciais válidas)
- Confirmação de qual ambiente será utilizado: **homologação** ou **produção**
- Janela de importação acordada com o cliente (evitar horário de uso intenso)
- Backup do estado atual do ambiente (se já houver dados cadastrados)

---

## Princípios desta fase

**Nunca importar direto em produção sem homologação.** Se o ambiente de homologação estiver disponível, execute lá primeiro.

**Importar na ordem de dependência.** A plataforma rejeita registros que referenciam entidades ainda não cadastradas.

**Parar ao primeiro erro crítico.** Um erro de importação em Áreas invalida toda a cadeia. Não avançar para a próxima entidade sem confirmar que a anterior foi importada com sucesso.

**Não reprocessar sem entender o erro.** Se uma importação falhar, diagnosticar a causa antes de tentar novamente — reprocessar sem correção pode criar duplicatas ou dados inconsistentes.

---

## Ordem obrigatória de importação

A mesma ordem da transformação, pela mesma razão de dependências:

```
1. Áreas
2. Colaboradores
3. Indicadores (KPI)
4. Metas Individuais
5. Metas Compartilhadas
6. Metas de Projeto
7. Curva de Alcance
8. Valores Previstos das Metas
9. Valores Realizados das Metas
```

---

## Procedimento

### Passo 1 — Preparar o ambiente

#### 1.1 Confirmar o ambiente alvo

Antes de qualquer ação, confirme explicitamente com o cliente:

```
Ambiente alvo desta importação: [ ] Homologação  [ ] Produção
Confirmado por (cliente): ___________________
Data/hora: ___________________
```

Nunca assuma. Registrar no `relatorio_importacao.md` (criado no Passo 2).

#### 1.2 Verificar estado atual do ambiente

Acesse a plataforma e verifique:

- [ ] Há dados já cadastrados neste ambiente?
- [ ] Se sim: é uma importação incremental (adicionar) ou substituição (limpar e reimportar)?
- [ ] O plano de implantação prevê limpeza prévia de alguma entidade?

Se for substituição, confirmar com o cliente e registrar autorização formal antes de qualquer exclusão.

#### 1.3 Fazer backup do estado atual (se aplicável)

Se o ambiente já contiver dados, exporte ou documente o estado atual antes de importar. Em caso de falha crítica, isso permite rollback.

---

### Passo 2 — Criar o relatório de importação

Crie `clientes/<nome_cliente>/relatorios/relatorio_importacao.md`:

```
# Relatório de Importação — <Nome do Cliente>

Data de início:
Consultor responsável:
Ambiente: Homologação / Produção
Confirmado pelo cliente: sim / não

## Progresso

| # | Entidade | Arquivo | Linhas enviadas | Linhas importadas | Erros | Status | Hora |
|---|---|---|---|---|---|---|---|
| 1 | Áreas | Import_Áreas... | | | | | |
| 2 | Colaboradores | Import_Colaboradores... | | | | | |
| 3 | Indicadores | Import_Indicadores... | | | | | |
| 4 | Metas Individuais | Import_Metas Individuais... | | | | | |
| 5 | Metas Compartilhadas | Import_Metas Compartilhadas... | | | | | |
| 6 | Metas Projeto | Import_Metas Projeto... | | | | | |
| 7 | Curva de Alcance | Import_Curva de Alcance... | | | | | |
| 8 | Valores Previstos | Import_Valores Previstos... | | | | | |
| 9 | Valores Realizados | Import_Valores Realizados... | | | | | |

## Erros encontrados

| # | Entidade | Linha | Mensagem de erro da plataforma | Ação tomada |
|---|---|---|---|---|

## Observações gerais
```

---

### Passo 3 — Executar a importação por entidade

Para cada entidade, siga o ciclo:

```
Acessar a tela de importação → Selecionar o arquivo → Executar → Conferir resultado → Registrar
```

#### 3.1 Durante a importação

- Use exclusivamente os arquivos de `output/` — nunca de `staging/` ou `raw/`
- Confirme que está selecionando o arquivo correto (nome e data de modificação)
- Se a plataforma oferecer modo "simulação" ou "dry run", utilize antes de confirmar

#### 3.2 Após cada importação

Verifique na plataforma:
- [ ] Quantos registros foram importados com sucesso?
- [ ] Quantos foram rejeitados?
- [ ] A plataforma gerou um arquivo de log ou relatório de erros? Se sim, salvar em `relatorios/`
- [ ] O número de registros importados bate com o número de linhas do arquivo (descontando o cabeçalho)?

Preencha a linha correspondente no `relatorio_importacao.md` antes de avançar para a próxima entidade.

#### 3.3 Critério de avanço

Só avance para a próxima entidade se:
- 100% dos registros foram importados, **ou**
- Os registros rejeitados são de linhas previamente identificadas no log de transformação como omissões aceitas

Qualquer rejeição inesperada deve ser investigada antes de continuar.

---

### Passo 4 — Tratamento de erros de importação

Quando a plataforma rejeitar um ou mais registros:

#### 4.1 Categorizar o erro

| Categoria | Descrição | Exemplo |
|---|---|---|
| **Formato** | O valor não está no formato esperado pela plataforma | data em formato errado, booleano como texto |
| **Domínio** | O valor não pertence ao conjunto de valores aceitos | código de unidade de medida inválido |
| **Referência** | O código referenciado não existe na plataforma | área inexistente, login inexistente |
| **Unicidade** | O código já existe e não é permitido duplicar | reimportação sem limpeza prévia |
| **Negócio** | Regra de negócio da plataforma violada | peso total ≠ 100%, hierarquia circular |

#### 4.2 Decidir a ação

| Categoria | Ação |
|---|---|
| Formato / Domínio | Corrigir no `staging/`, regenerar output, reimportar |
| Referência | Verificar se a entidade referenciada foi importada corretamente; corrigir e reimportar |
| Unicidade | Verificar se é duplicata real ou reimportação indevida; limpar se autorizado |
| Negócio | Escalar para o cliente se a regra não puder ser resolvida tecnicamente |

#### 4.3 Registrar

Toda rejeição, causa e ação tomada deve ser registrada na tabela de erros do `relatorio_importacao.md`.

---

### Passo 5 — Verificação pós-importação na plataforma

Após importar todas as entidades, faça uma verificação diretamente na interface da plataforma:

#### 5.1 Verificação de contagens
- [ ] Total de áreas cadastradas bate com o arquivo importado?
- [ ] Total de colaboradores cadastrados bate?
- [ ] Total de metas por tipo bate?

#### 5.2 Spot check na plataforma
Selecione 3–5 registros de cada entidade e verifique na tela da plataforma:

- Os dados estão exibidos corretamente?
- A hierarquia de áreas está visualmente correta?
- As metas estão vinculadas aos colaboradores e indicadores corretos?
- Os pesos estão corretos?

#### 5.3 Verificação de relacionamentos
- [ ] Um colaborador está associado à área correta?
- [ ] Uma meta individual está vinculada ao colaborador e indicador corretos?
- [ ] Uma meta compartilhada aparece nas áreas corretas?
- [ ] A curva de alcance está associada à meta correta?

---

### Passo 6 — Aceite do cliente

Após a verificação pós-importação, apresente os resultados ao cliente:

1. Compartilhe o `relatorio_importacao.md` com o resumo de cada entidade importada
2. Solicite que o cliente faça sua própria verificação na plataforma (spot check do lado deles)
3. Documente o aceite formal:

```
## Aceite do cliente

Verificação realizada pelo cliente: sim / não
Responsável (cliente): ___________________
Data/hora do aceite: ___________________
Observações do cliente: ___________________
Status final: ✅ Aceito / ⚠️ Aceito com ressalvas / ❌ Não aceito
```

---

### Passo 7 — Fechamento e arquivamento

Com o aceite confirmado:

- [ ] Fechar o `relatorio_importacao.md` com data, status final e assinatura do consultor
- [ ] Mover os arquivos de output para uma subpasta com data: `output/AAAA-MM-DD/`
- [ ] Comprimir e arquivar a pasta completa do cliente se o projeto estiver encerrado
- [ ] Registrar as lições aprendidas (ver seção abaixo)

---

## Checklist de conclusão

- [ ] Ambiente alvo confirmado com o cliente antes do início
- [ ] Backup do estado anterior realizado (se aplicável)
- [ ] Importação executada na ordem obrigatória (1–9)
- [ ] Resultado de cada entidade registrado no relatório antes de avançar
- [ ] Nenhum erro de importação inesperado em aberto
- [ ] Verificação pós-importação executada na plataforma
- [ ] Aceite do cliente registrado
- [ ] `relatorio_importacao.md` fechado e arquivado
- [ ] Lições aprendidas registradas

---

## Saídas deste SOP

| Artefato | Localização |
|---|---|
| Relatório de importação com aceite | `clientes/<nome_cliente>/relatorios/relatorio_importacao.md` |
| Logs de erro da plataforma (se gerados) | `clientes/<nome_cliente>/relatorios/` |
| Output arquivado com data | `clientes/<nome_cliente>/output/AAAA-MM-DD/` |

---

## Lições aprendidas

Ao encerrar uma implantação, registre em `docs/licoes_aprendidas.md` (arquivo compartilhado entre clientes):

```
| Data | Cliente (anonimizado) | Entidade | Problema encontrado | Como foi resolvido | Virou skill? |
|---|---|---|---|---|---|
```

Este registro alimenta a evolução das skills e dos próprios SOPs. Toda vez que um problema novo for resolvido aqui, avaliar se a solução deve se tornar uma skill reutilizável em `skills/`.

---

## Alertas e situações comuns

**A plataforma rejeitou todos os registros de uma entidade.**
Parar imediatamente. Investigar a mensagem de erro — provavelmente é um problema de formato (encoding, delimitador, cabeçalho). Não tentar reimportar sem diagnóstico.

**A plataforma aceitou os registros mas os dados estão exibidos incorretamente.**
Pode ser problema de encoding (caracteres especiais corrompidos) ou de separador decimal. Verificar o arquivo de output com um editor de texto antes de reimportar.

**O cliente quer ajustar um dado após a importação.**
Pequenos ajustes podem ser feitos diretamente na plataforma. Ajustes em massa exigem nova rodada de transformação e reimportação da entidade afetada.

**Foi importado para produção quando deveria ser homologação (ou vice-versa).**
Se for homologação importada em produção: parar, documentar, avaliar rollback com o cliente. Se for produção importada em homologação: sem impacto nos dados reais, mas documentar o incidente.

**O cliente não faz o aceite formal mas diz que "está ok".**
Registrar a confirmação verbal com data e nome do responsável. Aceite informal é melhor do que nenhum registro.
