---
name: diagnosticar-cliente
description: Executa o diagnóstico completo dos dados brutos de um cliente no projeto de implantação RHTec. Analisa todos os arquivos em raw/, detecta problemas de qualidade, identifica entidades presentes e gera o relatório de diagnóstico em config/. Use após receber e organizar os dados do cliente em raw/.
argument-hint: <nome-do-cliente>
allowed-tools: Bash Read
---

# Diagnóstico de Dados do Cliente

Cliente: `$ARGUMENTS`

## Pré-condições

Verifique antes de executar:

```bash
ls "clientes/$ARGUMENTS/raw/"
```

Se a pasta estiver vazia, oriente o usuário a colocar os dados do cliente antes de continuar.

## Execução

```bash
.venv/bin/python -c "
import json, sys
sys.path.insert(0, '.')
from agentes.diagnostico import agente
res = agente.executar('clientes/$ARGUMENTS')
print('Status:', res['status'])
print('Arquivos analisados:', res['dados']['total_arquivos'])
for av in res.get('avisos', []):
    print('⚠️', av)
for err in res.get('erros', []):
    print('❌', err)
print()
print('Arquivos gerados:')
for f in res['dados'].get('arquivos_gerados', []):
    print(' -', f)
"
```

## Após a execução

Leia o resumo gerado:

```bash
cat "clientes/$ARGUMENTS/config/diagnostico_resumo.md"
```

## Interpretar os resultados

Com base no diagnóstico gerado, responda ao usuário:

1. **Quais entidades foram encontradas** nos arquivos (áreas, colaboradores, metas, etc.)
2. **Principais problemas de qualidade** detectados por arquivo e aba
3. **Dados pessoais (PII)** identificados e onde estão
4. **Dúvidas que precisam ser respondidas pelo cliente** antes de avançar

## Próximo passo

Se o diagnóstico não tiver bloqueadores críticos:
> "Execute `/mapear-cliente $ARGUMENTS` para construir o mapeamento de campos."

Se houver bloqueadores:
> Liste cada bloqueador com a ação necessária antes de avançar.
