---
name: mapear-cliente
description: Constrói o mapeamento semântico campo a campo entre os dados do cliente e os templates da plataforma RHTec. Gera config/mapeamento.json com sugestões de correspondência, nível de confiança e lista de dúvidas em aberto. Use após o diagnóstico e antes da transformação.
argument-hint: <nome-do-cliente>
allowed-tools: Bash Read
---

# Mapeamento de Campos — Cliente

Cliente: `$ARGUMENTS`

## Pré-condições

```bash
ls "clientes/$ARGUMENTS/config/diagnostico.json" 2>/dev/null || echo "FALTA: execute /diagnosticar-cliente $ARGUMENTS primeiro"
```

## Execução

```bash
.venv/bin/python -c "
import json, sys
sys.path.insert(0, '.')
from agentes.mapeamento import agente
res = agente.executar('clientes/$ARGUMENTS')
print('Status:', res['status'])
print('Dúvidas em aberto:', res['dados']['total_duvidas'])
for av in res.get('avisos', []):
    print('⚠️', av)
"
```

## Revisar o mapeamento gerado

```bash
cat "clientes/$ARGUMENTS/config/mapeamento.json"
```

## O que revisar obrigatoriamente

Para cada entidade no `mapeamento.json`, verifique:

1. **`arquivo_sugerido` e `aba_sugerida`** — o agente apontou para o arquivo/aba correto?
2. **Campos com `confianca: baixa`** — revisar manualmente
3. **Campos com `campo_cliente: null`** — campo obrigatório sem origem → bloqueador
4. **Campos com observação `⚠️`** — requerem atenção

## Como corrigir o mapeamento

Edite `clientes/$ARGUMENTS/config/mapeamento.json` diretamente:

```json
{
  "areas": {
    "arquivo_sugerido": "raw/simples/arquivo.xlsx",
    "aba_sugerida": "Hierarquia",
    "campos": [
      {
        "campo_template": "Código da Área*",
        "campo_cliente": "col_codigo",
        "transformacao": "recodificacao",
        "confianca": "alta",
        "observacao": ""
      }
    ]
  }
}
```

## Dúvidas abertas

Liste as dúvidas identificadas e para cada uma indique:
- O campo em questão
- Por que é uma dúvida (campo ausente, ambíguo, ou múltiplas origens possíveis)
- O que o cliente precisa confirmar

## Próximo passo

Quando o mapeamento estiver revisado e sem bloqueadores:
> "Execute `/executar-implantacao $ARGUMENTS` para rodar o pipeline completo."
