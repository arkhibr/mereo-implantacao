"""
Grupos de carga — a arquitetura modular do pipeline de implantação.

As cargas não são uma coisa só: formam **grandes grupos** com uma relação de
dependência. No centro está o **núcleo** (as pessoas e seu entorno:
colaboradores, áreas e hierarquias) — a base seminal sobre a qual a plataforma
RHTec/Mereo é construída. Tudo o mais é **predicado** sobre o núcleo: cada grupo
de agregação (indicadores, metas, e outros que virão, como competências)
acrescenta significado e valor aos colaboradores, e por isso **depende do
núcleo**.

O modelo tem dois níveis:

1. **Topo (radial):** cada grupo declara de quem depende. Os predicados apontam
   para o núcleo. Adicionar um grupo novo é só acrescentar uma entrada aqui —
   nada nos grupos existentes muda.
2. **Domínio (interno):** a ordem de `etapas` dentro de cada grupo é a rede de
   dependências específica daquele domínio (ex.: dentro de Metas, primeiro
   `metas`, depois `curva_alcance` e `valores`, que se apoiam nelas).

Esta é a fonte única de verdade: tanto o orquestrador determinista quanto o
orquestrador LLM derivam daqui a ordem de execução, os bloqueadores e a
apresentação. **O gate de "núcleo pronto" não é imposto automaticamente** — o
consultor de implantação tem o domínio do processo e decide. A ferramenta apenas
torna a dependência explícita e, no máximo, avisa.
"""
from __future__ import annotations

# Cada grande grupo de carga.
#   titulo / descricao  → apresentação ao consultor
#   seminal             → True apenas para o núcleo (a base de tudo)
#   depende_de          → grupos de topo dos quais este depende (radial)
#   etapas              → agentes determinísticos do grupo, em ordem de domínio
GRUPOS: dict[str, dict] = {
    "nucleo": {
        "titulo": "Núcleo (base seminal)",
        "descricao": (
            "As pessoas e seu entorno: colaboradores, áreas e hierarquias. "
            "É a plataforma sobre a qual todo o resto é predicado — sem ela não "
            "faz sentido falar das demais cargas."
        ),
        "seminal": True,
        "depende_de": [],
        "etapas": ["areas", "colaboradores"],
    },
    "indicadores": {
        "titulo": "Indicadores",
        "descricao": "Indicadores/KPIs predicados sobre o núcleo.",
        "seminal": False,
        "depende_de": ["nucleo"],
        "etapas": ["indicadores"],
    },
    "metas": {
        "titulo": "Metas",
        "descricao": (
            "Metas e o que as acompanha — curva de alcance e valores "
            "previstos/realizados — predicadas sobre o núcleo."
        ),
        "seminal": False,
        "depende_de": ["nucleo"],
        "etapas": ["metas", "curva_alcance", "valores"],
    },
}


# ── Validação do registro ─────────────────────────────────────────────────────

def _validar(registro: dict = GRUPOS) -> None:
    """Garante que o registro é um DAG coerente.

    Levanta ValueError em: dependência para grupo inexistente, ciclo, ausência
    de exatamente um grupo seminal, ou etapa repetida entre grupos (cada etapa
    pertence a um único domínio).
    """
    nomes = set(registro)

    seminais = [g for g, info in registro.items() if info.get("seminal")]
    if len(seminais) != 1:
        raise ValueError(
            f"O registro deve ter exatamente um grupo seminal; encontrados: {seminais}"
        )

    vistas: dict[str, str] = {}
    for grupo, info in registro.items():
        for dep in info.get("depende_de", []):
            if dep not in nomes:
                raise ValueError(f"Grupo '{grupo}' depende de '{dep}', que não existe.")
        for etapa in info.get("etapas", []):
            if etapa in vistas:
                raise ValueError(
                    f"Etapa '{etapa}' aparece em '{grupo}' e em '{vistas[etapa]}'; "
                    "cada etapa pertence a um único grupo."
                )
            vistas[etapa] = grupo

    # Detecta ciclo tentando ordenar topologicamente.
    ordem_topologica(registro)


# ── Consultas estruturais ──────────────────────────────────────────────────────

def ordem_topologica(registro: dict = GRUPOS) -> list[str]:
    """Ordem dos grupos respeitando `depende_de` (dependências antes).

    Empate é resolvido pela ordem de inserção no registro, para resultado
    estável e previsível.
    """
    pendentes = {g: list(info.get("depende_de", [])) for g, info in registro.items()}
    desconhecidas = {d for deps in pendentes.values() for d in deps} - set(registro)
    if desconhecidas:
        raise ValueError(f"Dependências para grupos inexistentes: {sorted(desconhecidas)}")

    ordem: list[str] = []
    resolvidos: set[str] = set()
    while pendentes:
        prontos = [g for g in registro if g in pendentes
                   and all(d in resolvidos for d in pendentes[g])]
        if not prontos:
            raise ValueError(f"Ciclo de dependência entre grupos: {sorted(pendentes)}")
        for g in prontos:
            ordem.append(g)
            resolvidos.add(g)
            del pendentes[g]
    return ordem


def grupo_seminal(registro: dict = GRUPOS) -> str:
    """Nome do grupo seminal (o núcleo)."""
    for grupo, info in registro.items():
        if info.get("seminal"):
            return grupo
    raise ValueError("Nenhum grupo seminal definido no registro.")


def etapas_do_grupo(grupo: str, registro: dict = GRUPOS) -> list[str]:
    """Etapas de um grupo, na ordem de domínio."""
    return list(registro[grupo]["etapas"])


def grupo_de_etapa(etapa: str, registro: dict = GRUPOS) -> str | None:
    """Grupo ao qual uma etapa pertence, ou None se a etapa não é uma carga."""
    for grupo, info in registro.items():
        if etapa in info.get("etapas", []):
            return grupo
    return None


def etapas_em_ordem(registro: dict = GRUPOS) -> list[str]:
    """Todas as etapas de carga, em ordem global: grupos em ordem topológica,
    etapas internas em ordem de domínio. Núcleo sempre primeiro."""
    return [etapa for grupo in ordem_topologica(registro)
            for etapa in registro[grupo]["etapas"]]


def dependencias_de(grupo: str, registro: dict = GRUPOS) -> list[str]:
    """Dependências transitivas de um grupo (não inclui o próprio), em ordem
    topológica."""
    alvo = set()
    fronteira = list(registro[grupo].get("depende_de", []))
    while fronteira:
        dep = fronteira.pop()
        if dep in alvo:
            continue
        alvo.add(dep)
        fronteira.extend(registro[dep].get("depende_de", []))
    return [g for g in ordem_topologica(registro) if g in alvo]


# Nome do grupo seminal, resolvido uma vez. Validação roda no import: um erro
# de registro falha rápido, na carga do módulo, em vez de silenciosamente.
_validar()
GRUPO_SEMINAL = grupo_seminal()
