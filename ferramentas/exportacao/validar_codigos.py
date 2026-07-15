"""
Skill: Validação de campos codificados
Detecta texto descritivo onde a plataforma espera código: valor fora do domínio,
código acima do limite de tamanho e espaço/acento em campo de código.
Limites e domínios vêm de ferramentas.transformacao.dominios_plataforma.
"""
import unicodedata
import pandas as pd


def _tem_acento(texto: str) -> bool:
    return any(unicodedata.category(c) == "Mn" for c in unicodedata.normalize("NFD", texto))


def validar(df: pd.DataFrame, regras: dict) -> dict:
    """
    Valida colunas codificadas de um DataFrame.

    regras: {"coluna": {"tipo": "codigo", "max": 10, "estrito": bool, "conhecidos": set}
             ou {"tipo": "dominio", "valores": set}, ...}
    Valores vazios são ignorados (obrigatoriedade é papel da validação de schema).
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}
    achados = []

    for coluna, regra in regras.items():
        if coluna not in df.columns:
            continue
        serie = df[coluna].dropna().astype(str).str.strip()
        serie = serie[serie != ""]
        if serie.empty:
            continue

        if regra["tipo"] == "dominio":
            invalidos = serie[~serie.isin(regra["valores"])].unique().tolist()
            if invalidos:
                achados.append({
                    "severidade": "critico",
                    "tipo": "dominio_invalido",
                    "coluna": coluna,
                    "detalhe": f"Valores fora do domínio {sorted(regra['valores'])}. "
                               f"Ex: {invalidos[:3]}",
                })

        elif regra["tipo"] == "codigo":
            excedem = serie[serie.str.len() > regra["max"]].unique().tolist()
            if excedem:
                achados.append({
                    "severidade": "critico",
                    "tipo": "codigo_excede_limite",
                    "coluna": coluna,
                    "detalhe": f"Limite da plataforma: Texto({regra['max']}). "
                               f"Ex: {excedem[:3]}",
                })

            suspeitos = serie[serie.apply(lambda v: " " in v or _tem_acento(v))].unique().tolist()
            if suspeitos:
                achados.append({
                    "severidade": "critico" if regra.get("estrito") else "medio",
                    "tipo": "texto_em_campo_codigo",
                    "coluna": coluna,
                    "detalhe": f"Espaço/acento sugere descrição no lugar de código. "
                               f"Ex: {suspeitos[:3]}",
                })

            conhecidos = regra.get("conhecidos")
            if conhecidos:
                desconhecidos = serie[~serie.isin(conhecidos)].unique().tolist()
                if desconhecidos:
                    achados.append({
                        "severidade": "medio",
                        "tipo": "codigo_fora_da_lista_padrao",
                        "coluna": coluna,
                        "detalhe": f"Fora da lista padrão da plataforma "
                                   f"{sorted(conhecidos)}. Ex: {desconhecidos[:3]}",
                    })

    resultado["dados"]["total_achados"] = len(achados)
    resultado["dados"]["achados"] = achados

    severidades = {a["severidade"] for a in achados}
    if "critico" in severidades or "alto" in severidades:
        resultado["status"] = "erro"
    elif severidades:
        resultado["status"] = "aviso"

    return resultado
