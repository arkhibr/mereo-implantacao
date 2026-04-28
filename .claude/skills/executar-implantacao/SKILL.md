---
name: executar-implantacao
description: Executa o pipeline completo de implantação para um cliente no projeto RHTec — transforma os dados brutos em arquivos prontos para importação na plataforma, valida tudo e gera o output final. Use após o mapeamento estar revisado e aprovado, sem bloqueadores em aberto.
argument-hint: <nome-do-cliente> [etapas-separadas-por-virgula]
allowed-tools: Bash Read
---

# Pipeline de Implantação

Cliente: `$ARGUMENTS`

## Pré-condições obrigatórias

```bash
# Verificar que mapeamento existe e foi revisado
ls "clientes/$ARGUMENTS/config/mapeamento.json" 2>/dev/null || echo "FALTA mapeamento.json"

# Verificar que não há bloqueadores abertos
grep -c "bloqueador\|ausente" "clientes/$ARGUMENTS/config/mapeamento.json" 2>/dev/null || echo "OK"
```

Só avance se o mapeamento existir e não houver campos obrigatórios sem origem.

## Execução do pipeline completo

```bash
.venv/bin/python -c "
import json, sys
sys.path.insert(0, '.')
from agentes.orquestrador import agente

res = agente.executar('clientes/$ARGUMENTS')
print('=== RESULTADO FINAL ===')
print('Status:', res['status'])
print('Cliente:', res['cliente'])
print()
print('Etapas:')
for etapa, info in res['etapas'].items():
    icone = '✅' if info['status'] == 'ok' else ('⚠️' if info['status'] == 'aviso' else '❌')
    print(f'  {icone} {etapa}: {info[\"dados_resumo\"]}')
print()
if res['erros']:
    print('Erros:')
    for e in res['erros']:
        print(' ❌', e)
if res['avisos']:
    print('Avisos:')
    for a in res['avisos'][:5]:
        print(' ⚠️', a)
"
```

## Executar apenas etapas específicas (opcional)

Para reprocessar apenas algumas etapas:

```bash
.venv/bin/python -c "
import sys
sys.path.insert(0, '.')
from agentes.orquestrador import agente
res = agente.executar('clientes/$ARGUMENTS', escopo=['areas', 'colaboradores', 'validacao'])
print(res['status'])
"
```

## Interpretar o resultado

Após a execução, leia o relatório de validação:

```bash
cat "clientes/$ARGUMENTS/relatorios/relatorio_validacao.md"
```

### Se aprovado ✅
Os arquivos foram copiados para `clientes/$ARGUMENTS/output/<data>/`.

Apresente ao usuário:
1. Quais arquivos foram gerados e estão prontos
2. Caminho exato para cada template preenchido
3. Instrução: seguir o SOP 05 para importar na plataforma

### Se bloqueado ❌
1. Liste cada entidade bloqueada e o motivo
2. Para cada bloqueador, indique onde corrigir (staging ou mapeamento)
3. Após a correção, execute novamente apenas a etapa afetada + validação

## Log completo

```bash
cat "clientes/$ARGUMENTS/relatorios/log_pipeline.json"
```
