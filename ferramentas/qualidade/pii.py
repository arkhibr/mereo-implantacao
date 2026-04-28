"""
Skill: Detecção de PII (Dados Pessoais)
Identifica colunas com potencial conteúdo de dados pessoais sensíveis.
"""
import re
import pandas as pd

_NOME_COLUNA = re.compile(
    r"(cpf|cnpj|rg|e.?mail|nome|name|nascimento|birth|salari|salary|"
    r"telefone|phone|celular|mobile|endereco|address|cep|passaporte|passport)",
    re.IGNORECASE,
)
_CPF = re.compile(r"^\d{3}\.?\d{3}\.?\d{3}-?\d{2}$")
_EMAIL = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_CNPJ = re.compile(r"^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$")


def detectar(df: pd.DataFrame) -> dict:
    """Identifica colunas com potencial conteúdo de dados pessoais (PII)."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}
    suspeitos = []

    for col in df.columns:
        motivos = []

        if _NOME_COLUNA.search(str(col)):
            motivos.append("nome_da_coluna")

        amostra = df[col].dropna().astype(str).head(30)
        if amostra.str.match(_CPF).any():
            motivos.append("padrao_cpf")
        if amostra.str.match(_EMAIL).any():
            motivos.append("padrao_email")
        if amostra.str.match(_CNPJ).any():
            motivos.append("padrao_cnpj")

        if motivos:
            suspeitos.append({
                "coluna": str(col),
                "motivos": motivos,
                "amostra_reduzida": amostra.head(2).tolist(),
            })

    resultado["dados"]["colunas_suspeitas"] = suspeitos
    resultado["dados"]["total"] = len(suspeitos)

    if suspeitos:
        resultado["status"] = "aviso"
        resultado["avisos"].append(
            f"{len(suspeitos)} coluna(s) com potencial PII. Restringir acesso antes de compartilhar."
        )

    return resultado
