"""
Skill: Exportação do output final
Converte os CSVs de staging em planilhas .xlsx no formato de importação da
plataforma (que só aceita Excel), nomeadas pelo template correspondente.
"""
from datetime import date
from pathlib import Path

import pandas as pd


def exportar(pasta_cliente, arquivos: dict, data: str = None) -> dict:
    """
    Gera output/<data>/<template>.xlsx a partir dos CSVs de staging.

    arquivos: {caminho_staging_relativo: nome_do_template, ...}
              (staging ausente é reportado, não é erro)
    data: YYYY-MM-DD; default = hoje.
    """
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    base = Path(pasta_cliente)
    data_str = data or date.today().isoformat()
    output = base / "output" / data_str
    output.mkdir(parents=True, exist_ok=True)

    gerados = []
    ausentes = []
    for staging_rel, nome_template in arquivos.items():
        src = base / staging_rel
        if not src.exists():
            ausentes.append(nome_template)
            continue
        # dtype=str preserva códigos como texto ("1" não vira 1.0 na planilha);
        # keep_default_na preserva o literal NULL (semântica da plataforma: remover valor)
        df = pd.read_csv(str(src), sep=";", encoding="utf-8-sig", dtype=str,
                         keep_default_na=False)
        nome_xlsx = Path(nome_template).stem + ".xlsx"
        df.to_excel(str(output / nome_xlsx), index=False, sheet_name="Plan1", engine="openpyxl")
        gerados.append(nome_xlsx)

    resultado["dados"]["diretorio_output"] = str(output)
    resultado["dados"]["data"] = data_str
    resultado["dados"]["arquivos_gerados"] = gerados
    resultado["dados"]["ausentes"] = ausentes
    return resultado
