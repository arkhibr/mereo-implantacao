"""
Skill: Detecção e normalização de encoding
Detecta o encoding de arquivos texto e converte para UTF-8.
"""
from pathlib import Path


def detectar(caminho: str) -> dict:
    """Detecta o encoding de um arquivo texto."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    try:
        import chardet
        with open(caminho, "rb") as f:
            amostra = f.read(50_000)
        det = chardet.detect(amostra)
        encoding = det.get("encoding") or "utf-8"
        confianca = det.get("confidence", 0.0)
        resultado["dados"]["encoding_detectado"] = encoding
        resultado["dados"]["confianca"] = round(confianca, 3)
        if confianca < 0.7:
            resultado["avisos"].append(
                f"Confiança baixa na detecção ({confianca:.0%}). Verificar manualmente."
            )
    except ImportError:
        resultado["dados"]["encoding_detectado"] = _fallback(caminho)
        resultado["dados"]["confianca"] = None
        resultado["avisos"].append("chardet não disponível — detecção por tentativa.")
    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))

    return resultado


def normalizar(caminho: str, destino: str = None, encoding_origem: str = None) -> dict:
    """Converte arquivo para UTF-8. Retorna caminho do arquivo convertido."""
    resultado = {"status": "ok", "dados": {}, "erros": [], "avisos": []}

    try:
        if encoding_origem is None:
            det = detectar(caminho)
            if det["status"] == "erro":
                return det
            encoding_origem = det["dados"]["encoding_detectado"]

        path_in = Path(caminho)
        path_out = Path(destino) if destino else path_in.with_stem(path_in.stem + "_utf8")

        with open(caminho, "r", encoding=encoding_origem, errors="replace") as f:
            conteudo = f.read()
        with open(path_out, "w", encoding="utf-8") as f:
            f.write(conteudo)

        resultado["dados"]["encoding_origem"] = encoding_origem
        resultado["dados"]["encoding_destino"] = "utf-8"
        resultado["dados"]["arquivo_convertido"] = str(path_out)

    except Exception as e:
        resultado["status"] = "erro"
        resultado["erros"].append(str(e))

    return resultado


def _fallback(caminho: str) -> str:
    for enc in ("utf-8-sig", "utf-8", "windows-1252", "latin-1", "iso-8859-1"):
        try:
            with open(caminho, "r", encoding=enc) as f:
                f.read(10_000)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return "utf-8"
