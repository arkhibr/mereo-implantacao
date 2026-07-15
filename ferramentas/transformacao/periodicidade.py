"""
Skill: Periodicidade das metas
Detecta colunas de período (meses) e infere a frequência de acompanhamento de cada
meta pela estrutura dos valores: 1 valor no ano = anual (8), 2+ = mensal (1).
Critério aprovado pelo consultor em 15/07/2026 (feedback 3 / pergunta 11).
"""
import re
from datetime import datetime

import pandas as pd

_MESES = {
    "jan": 1, "janeiro": 1, "fev": 2, "fevereiro": 2, "mar": 3, "março": 3, "marco": 3,
    "abr": 4, "abril": 4, "mai": 5, "maio": 5, "jun": 6, "junho": 6,
    "jul": 7, "julho": 7, "ago": 8, "agosto": 8, "set": 9, "setembro": 9,
    "out": 10, "outubro": 10, "nov": 11, "novembro": 11, "dez": 12, "dezembro": 12,
}
_RE_MM_AAAA = re.compile(r"^(0?[1-9]|1[0-2])\s*/\s*((19|20)\d{2})$")
_RE_AAAA_MM = re.compile(r"^((19|20)\d{2})\s*-\s*(0?[1-9]|1[0-2])$")
_RE_MES_ANO = re.compile(r"^([a-zç]+)\s*[/\-]?\s*((19|20)\d{2})?$")

FREQUENCIA_MENSAL = "1"
FREQUENCIA_ANUAL = "8"


def interpretar_periodo(rotulo) -> tuple:
    """Devolve (mes, ano) se o rótulo da coluna representa um período; senão None."""
    if isinstance(rotulo, (datetime, pd.Timestamp)):
        return (rotulo.month, rotulo.year)
    texto = str(rotulo).strip().lower()
    m = _RE_MM_AAAA.match(texto)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = _RE_AAAA_MM.match(texto)
    if m:
        return (int(m.group(3)), int(m.group(1)))
    m = _RE_MES_ANO.match(texto)
    if m and m.group(1) in _MESES:
        ano = int(m.group(2)) if m.group(2) else None
        return (_MESES[m.group(1)], ano)
    return None


def colunas_periodo(df: pd.DataFrame) -> dict:
    """Mapeia coluna → (mes, ano) para as colunas que representam períodos."""
    encontradas = {}
    for col in df.columns:
        periodo = interpretar_periodo(col)
        if periodo:
            encontradas[col] = periodo
    # Uma coluna de mês isolada é ruído provável; período de verdade vem em série.
    return encontradas if len(encontradas) >= 2 else {}


def rotulo_template(mes: int, ano: int) -> str:
    """Rótulo no formato do template de valores da plataforma (MM/AAAA)."""
    return f"{mes:02d}/{ano}"


def detectar_frequencias(df: pd.DataFrame, coluna_meta: str) -> dict:
    """
    Infere a frequência por meta pela quantidade de períodos preenchidos:
    1 valor → anual (8); 2 ou mais → mensal (1).

    Devolve {"frequencias": {codigo_meta: codigo}, "colunas_periodo": {...}}.
    Sem colunas de período detectáveis, devolve frequências vazias.
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    periodos = colunas_periodo(df)
    resultado["dados"]["colunas_periodo"] = periodos
    frequencias = {}

    if periodos and coluna_meta in df.columns:
        cols = list(periodos)
        for _, linha in df.iterrows():
            codigo = linha.get(coluna_meta)
            if pd.isna(codigo) or str(codigo).strip() == "":
                continue
            preenchidos = sum(
                1 for c in cols
                if pd.notna(linha[c]) and str(linha[c]).strip() != ""
            )
            if preenchidos == 0:
                continue
            frequencias[str(codigo).strip()] = (
                FREQUENCIA_ANUAL if preenchidos == 1 else FREQUENCIA_MENSAL
            )

    resultado["dados"]["frequencias"] = frequencias
    if not periodos:
        resultado["avisos"].append("Nenhuma coluna de período (mês/ano) detectada.")
    return resultado
