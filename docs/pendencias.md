# Pendências — Feedback de Metas (16/06/2026)

Status de cada ponto do feedback recebido do time Mereo e das definições derivadas.
Atualizado em: **15/07/2026**.

## Resolvidas

| # | Pendência | Decisão / solução | Onde |
|---|---|---|---|
| 1 | Códigos vs descrições (pilares) | Sem cadastro prévio de pilares nas implantações — tudo aponta para o padrão **`DZ001`**. De-para manual (`config/dicionario_pilares.csv`) fica para exceções; texto na fonte sem de-para bloqueia na validação (não descartamos dado do cliente em silêncio). | `agentes/metas` |
| 1 | Códigos vs descrições (grupos de permissão) | Padrão **`GRP_4`**; de-para manual em `config/dicionario_grupos_permissao.csv` para perfis descritivos ("Administrador Global" etc.). | `agentes/colaboradores` |
| 1/5 | Indicadores | **Não há cadastro prévio — tudo é importado junto.** Sem fonte própria de indicadores, o arquivo de importação é gerado 1:1 a partir das metas (descrição = objetivo, polaridade por heurística). | `agentes/metas` |
| 2 | Unidades de medida | Tabela oficial `UM001`–`UM40` codificada; inferência determinista por sinal de texto (% → UM001, R$ → UM002/003/004, dias, horas…); sem sinal → **`UM007`** (Número) com aviso. | `ferramentas/inferencia` |
| 3 | Periodicidade mensal × anual | Critério aprovado: **1 valor no ano = anual (8), 2+ = mensal (1)**, detectado pela estrutura dos valores da fonte. Indicador derivado recebe a frequência detectada; valores saem no layout do template (colunas MM/AAAA); validação bloqueia anual com >1 valor. | `ferramentas/transformacao/periodicidade.py` |
| 4 | Valores codificados (Agregação, Definição do Valor, Polaridade) | Tabelas oficiais da planilha de padrões codificadas em `dominios_plataforma.py`; texto normalizado para código; validação bloqueia valor fora do domínio. Polaridade só aceita 1/2 (código 3 não existe). | `ferramentas/transformacao/dominios_plataforma.py` |
| 5 | Login responsável da área | Campo não obrigatório (`Texto(50)`); coluna adicionada ao template; e-mail vira login, **nome não vaza** (fica vazio com aviso); literal `NULL` = remover responsável, preservado até o xlsx. | `agentes/areas` |
| — | Prefixos inventados (`AREA_`, `METI_`, `IND_`…) | Removidos — o código do cliente passa como está; dicionários viraram de-para manual opcional. | todos os agentes |
| — | Output em xlsx | A plataforma importa Excel — output final sai em `.xlsx` (antes CSV). | `ferramentas/exportacao/exportar_output.py` |

## Aguardando o cliente

| # | Pendência | O que falta | Referência |
|---|---|---|---|
| 5 | Login do responsável pela meta (obrigatório) | Exportação de usuários do ambiente (login + nome + e-mail) para cruzar quando a base traz só o nome. Alternativa: `config/dicionario_logins.csv` manual. Enquanto isso, nome no campo de login **bloqueia** na validação (correto). | Insumo 8 do relatório de perguntas |
| 6 | Curva de alcance | Respostas ao documento de alinhamento: casos concretos do teste, legenda de "Tipo de Valor" e relação Curva de Notas × Curva de Alcance. | `entregas/metas_feedback/Curva_de_Alcance_Alinhamento.pdf` |
| — | Arquivos do teste original | Planilhas de entrada e resultado do teste que gerou o feedback (para reproduzir os apontamentos restantes). | Insumo 2 do relatório de perguntas |

## Referências

- Perguntas enviadas ao cliente: `entregas/metas_feedback/Perguntas_Feedback_Metas.md`
- Padrões recebidos: `feedback/mereo/padroes_2026-07-15.xlsx`
- De-para manuais suportados: ver tabela no `sops/03_transformacao/sop_transformacao.md`
