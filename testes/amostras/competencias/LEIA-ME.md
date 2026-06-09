# Amostras de competências (corpus de teste)

Coleção de fontes **reais de clientes** usada para endurecer os transformadores
`competencias` e `formularios`. O objetivo aqui **não é gerenciar clientes** — é
ter variância suficiente para o transformador ser robusto.

Por isso:

- A **origem (cliente) não importa**. Não há vínculo com `clientes/`.
- Cada arquivo é nomeado pela **característica de variância** que ele cobre, não
  pelo cliente. O nome documenta o caso de teste.

## Convenção de nomes

`<caracteristica>[_<detalhe>].<ext>`

Exemplos:

- `desnormalizado_1comp_Nfatores.xls` — 1 competência × N fatores em N linhas
- `sem_codigo_fator.xlsx` — fatores sem código próprio (precisam ser inferidos)
- `pesos_em_texto.xlsx` — pesos por avaliador vêm como texto, não número
- `competencias_sem_fator.xlsx` — competências sem sub-dimensão (fator)
- `formulario_separado.xlsx` — formulário em arquivo/aba separada do catálogo

Acrescente novos nomes conforme aparecem casos novos. Se dois arquivos cobrem a
mesma característica, sufixe `_a`, `_b`.

## Como referenciar nos testes

Os testes de integração (`testes/integracao/`) leem deste diretório. Cada amostra
deve, idealmente, ter um caso correspondente que verifique que o transformador
lida com aquela variância — seja transformando corretamente, seja falhando de
forma explícita e diagnosticável.
