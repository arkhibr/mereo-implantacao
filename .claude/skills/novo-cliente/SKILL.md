---
name: novo-cliente
description: Configura a estrutura completa de pastas para um novo cliente no projeto de implantação RHTec. Cria o diretório do cliente a partir do modelo, orienta o onboarding inicial e garante que os dados brutos serão protegidos como somente leitura. Use ao iniciar a implantação de um novo cliente.
argument-hint: <nome-do-cliente>
allowed-tools: Bash Read
---

# Onboarding de Novo Cliente

Cliente: `$ARGUMENTS`

## Passos a executar

### 1. Criar estrutura de pastas

```bash
cp -r clientes/_modelo "clientes/$ARGUMENTS"
echo "Estrutura criada para: $ARGUMENTS"
ls "clientes/$ARGUMENTS"
```

### 2. Confirmar estrutura criada

Verifique se as seguintes pastas existem:
- `clientes/$ARGUMENTS/raw/` — dados brutos do cliente (imutável)
- `clientes/$ARGUMENTS/config/` — configurações e mapeamentos
- `clientes/$ARGUMENTS/staging/` — dados em transformação
- `clientes/$ARGUMENTS/output/` — arquivos prontos para importação
- `clientes/$ARGUMENTS/relatorios/` — relatórios de validação e importação

### 3. Orientar o consultor

Informe ao usuário:

**Próximos passos (seguir SOP 01):**

1. Receba os arquivos do cliente e coloque-os em `clientes/$ARGUMENTS/raw/`
2. Após colocar os arquivos, proteja-os como somente leitura:
   ```bash
   chmod -R 444 "clientes/$ARGUMENTS/raw/"
   find "clientes/$ARGUMENTS/raw/" -type d -exec chmod 555 {} \;
   ```
3. Preencha o registro de recebimento:
   ```bash
   cat sops/01_coleta/sop_coleta_dados_cliente.md
   ```
4. Quando os dados estiverem em `raw/`, execute `/diagnosticar-cliente $ARGUMENTS`

### 4. Lembrete de segurança

Se os dados contiverem CPF, e-mail ou outros dados pessoais:
- Restrinja o acesso à pasta `clientes/$ARGUMENTS/` às pessoas envolvidas na implantação
- Registre a presença de PII no `config/recebimento.md`
