"""
Resolução de templates por nome de arquivo, independente da subpasta.

`templates/` é organizado por módulo (`nucleo/`, `indicadores/`, `metas/`,
`competencias/`, …). Os agentes referenciam os templates pelo **nome do
arquivo**; este helper acha o arquivo em qualquer subpasta. Assim o layout
físico das pastas não acopla os agentes — mover um template de pasta não exige
mexer em código.
"""
from pathlib import Path


def localizar(pasta_templates, nome_arquivo: str) -> Path | None:
    """Caminho do template com esse nome em `pasta_templates` (ou em qualquer
    subpasta), ou None se não existir.

    Procura primeiro na raiz (compatível com o layout plano antigo) e depois
    recursivamente. Compara por nome exato — não usa glob — para não tropeçar em
    metacaracteres de padrão nos nomes de arquivo (ex.: parênteses, colchetes).
    """
    base = Path(pasta_templates)
    direto = base / nome_arquivo
    if direto.is_file():
        return direto
    for caminho in base.rglob("*"):
        if caminho.is_file() and caminho.name == nome_arquivo:
            return caminho
    return None
