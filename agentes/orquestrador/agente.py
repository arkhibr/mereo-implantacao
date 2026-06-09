"""
Agente Orquestrador
Coordena o pipeline completo para um cliente.
Chama todos os agentes na ordem correta, gerencia falhas e produz relatório final.
"""
import json
from pathlib import Path
from datetime import datetime
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentes.diagnostico    import agente as ag_diagnostico
from agentes.mapeamento     import agente as ag_mapeamento
from agentes.areas          import agente as ag_areas
from agentes.colaboradores  import agente as ag_colaboradores
from agentes.indicadores    import agente as ag_indicadores
from agentes.metas          import agente as ag_metas
from agentes.curva_alcance  import agente as ag_curva_alcance
from agentes.valores        import agente as ag_valores
from agentes.competencias   import agente as ag_competencias
from agentes.formularios     import agente as ag_formularios
from agentes.validacao      import agente as ag_validacao
from nucleo import visual
from nucleo import grupos

# Bookends que não são grupos de carga: setup (diagnóstico + mapeamento) e
# validação final. As cargas no meio vêm do registro de grupos (nucleo/grupos.py),
# fonte única de verdade da ordem e da dependência entre módulos.
_SETUP = [
    ("diagnostico", ag_diagnostico, "Analisando arquivos do cliente..."),
    ("mapeamento",  ag_mapeamento,  "Construindo mapeamento de campos..."),
]
_FINAL = [
    ("validacao",   ag_validacao,   "Validando e gerando output..."),
]
_MODULOS_CARGA = {
    "areas":         (ag_areas,         "Transformando áreas..."),
    "colaboradores": (ag_colaboradores, "Transformando colaboradores..."),
    "indicadores":   (ag_indicadores,   "Transformando indicadores..."),
    "metas":         (ag_metas,         "Transformando metas..."),
    "curva_alcance": (ag_curva_alcance, "Transformando curva de alcance..."),
    "valores":       (ag_valores,       "Transformando valores..."),
    "competencias":  (ag_competencias,  "Transformando competências e fatores..."),
    "formularios":   (ag_formularios,   "Montando formulários de avaliação..."),
}

# Staging do núcleo — usado só para o aviso soft (não é gate). Espelha o
# mapeamento de entidades da validação.
_NUCLEO_STAGING = {
    "areas":         "staging/01_areas/areas_transformadas.csv",
    "colaboradores": "staging/02_colaboradores/colaboradores_transformados.csv",
}


# Etapas de carga que já têm agente de transformação. Um grupo pode estar
# registrado em grupos.py com etapas ainda sem agente (módulo recém-adicionado,
# aguardando os templates) — essas etapas ficam de fora do pipeline executável
# até o agente existir, mas continuam visíveis em `listar_grupos`.
ETAPAS_IMPLEMENTADAS = set(_MODULOS_CARGA)


def _montar_pipeline():
    seq = list(_SETUP)
    for etapa in grupos.etapas_em_ordem():
        if etapa not in _MODULOS_CARGA:
            continue
        modulo, msg = _MODULOS_CARGA[etapa]
        seq.append((etapa, modulo, msg))
    seq.extend(_FINAL)
    return seq


PIPELINE = _montar_pipeline()

# Etapas que, se falharem, bloqueiam as seguintes: setup + núcleo seminal
# (derivado do registro — o núcleo é dependência forte de todos os predicados).
BLOQUEADORES = {"diagnostico", "mapeamento"} | set(grupos.etapas_do_grupo(grupos.GRUPO_SEMINAL))


def _nucleo_pronto(base: Path, executadas_ok: set) -> bool:
    """Núcleo pronto = todas as etapas seminais rodaram OK nesta execução ou já
    têm staging em disco. Sinal usado apenas para o aviso, nunca para bloquear."""
    for etapa in grupos.etapas_do_grupo(grupos.GRUPO_SEMINAL):
        if etapa in executadas_ok:
            continue
        rel = _NUCLEO_STAGING.get(etapa)
        if rel and (base / rel).exists():
            continue
        return False
    return True


def executar(pasta_cliente: str, escopo: list = None, parar_em_erro: bool = True) -> dict:
    """
    Executa o pipeline completo de implantação para um cliente.

    pasta_cliente: caminho para clientes/<nome_cliente>/
    escopo: lista de agentes a executar (None = todos)
            ex: ["diagnostico", "mapeamento", "areas"]
    parar_em_erro: se True, para ao encontrar erro em agente bloqueador
    """
    resultado = {
        "status": "ok",
        "agente": "orquestrador",
        "cliente": str(Path(pasta_cliente).name),
        "inicio": datetime.now().isoformat(),
        "fim": None,
        "etapas": {},
        "erros": [],
        "avisos": [],
    }

    agentes_executar = escopo or [nome for nome, _, _ in PIPELINE]
    base = Path(pasta_cliente)

    # Cabeçalho/rodapé "===" antigos ficaram só na resposta do CLI; o
    # orquestrador agora emite apenas eventos por etapa, com paleta semântica.

    executadas_ok: set = set()       # etapas concluídas sem erro nesta execução
    grupo_anterior = "<inicio>"      # controla quando imprimir o cabeçalho do módulo
    grupos_avisados: set = set()     # aviso soft de núcleo emitido só uma vez por grupo

    for nome, modulo, mensagem in PIPELINE:
        if nome not in agentes_executar:
            continue

        # Cabeçalho do módulo de carga quando entramos num grupo novo.
        grupo = grupos.grupo_de_etapa(nome)
        if grupo != grupo_anterior:
            grupo_anterior = grupo
            if grupo is not None:
                info = grupos.GRUPOS[grupo]
                marca = "◆ núcleo" if info.get("seminal") else "◇ predicado"
                print()
                print(visual.titulo(f"  {info['titulo']}  {visual.fraco('(' + marca + ')')}"))
                # Aviso soft: predicado rodando sem o núcleo pronto. Não bloqueia —
                # o consultor tem o domínio do processo e decide.
                if not info.get("seminal") and grupo not in grupos_avisados:
                    grupos_avisados.add(grupo)
                    if not _nucleo_pronto(base, executadas_ok):
                        print(visual.warning(
                            f"  '{info['titulo']}' é predicado sobre o núcleo, que ainda "
                            "não foi carregado. Confirme que a base já está na plataforma "
                            "antes de seguir."
                        ))

        print(visual.info(f"{nome}: {mensagem}"))

        try:
            res = modulo.executar(str(pasta_cliente))
        except Exception as e:
            res = {"status": "erro", "erros": [f"Exceção não capturada: {e}"], "avisos": []}

        resultado["etapas"][nome] = {
            "status": res.get("status", "erro"),
            "erros": res.get("erros", []),
            "avisos": res.get("avisos", []),
            "dados_resumo": _resumir_dados(res.get("dados", {})),
        }

        if res.get("erros"):
            resultado["erros"].extend([f"[{nome}] {e}" for e in res["erros"]])
        if res.get("avisos"):
            resultado["avisos"].extend([f"[{nome}] {a}" for a in res["avisos"]])

        status = res.get("status", "erro")
        if status in ("ok", "aviso"):
            executadas_ok.add(nome)
        if status == "erro":
            erros = res.get("erros", [])
            primeiro = erros[0] if erros else "erro sem detalhes"
            print(visual.error(f"{nome}: {primeiro}"))
            if parar_em_erro and nome in BLOQUEADORES:
                resultado["status"] = "erro"
                resultado["erros"].append(f"Pipeline interrompido em '{nome}' (agente bloqueador).")
                break
        elif status == "aviso":
            avisos = res.get("avisos", [])
            primeiro = avisos[0] if avisos else "concluído com aviso"
            print(visual.warning(f"{nome}: {primeiro}"))
        else:
            resumo = _resumir_dados(res.get("dados", {})) or "concluído"
            print(visual.success(f"{nome}: {resumo}"))

    resultado["fim"] = datetime.now().isoformat()

    status_final = _calcular_status_final(resultado["etapas"])
    resultado["status"] = status_final

    # Persistir log do pipeline
    _salvar_log(resultado, base / "relatorios" / "log_pipeline.json")

    return resultado


def _calcular_status_final(etapas: dict) -> str:
    statuses = [e["status"] for e in etapas.values()]
    if "erro" in statuses:
        return "erro"
    if "aviso" in statuses:
        return "aviso"
    return "ok"


def _resumir_dados(dados: dict) -> str:
    partes = []
    if "linhas_transformadas" in dados:
        partes.append(f"{dados['linhas_transformadas']} linhas")
    if "total_arquivos" in dados:
        partes.append(f"{dados['total_arquivos']} arquivos")
    if "status_geral" in dados:
        partes.append(f"validação: {dados['status_geral']}")
    if "contagens" in dados:
        for k, v in dados["contagens"].items():
            partes.append(f"{k}: {v}")
    return " | ".join(partes) if partes else "concluído"


def _salvar_log(resultado: dict, caminho: Path):
    try:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(resultado, f, ensure_ascii=False, indent=2, default=str)
    except Exception:
        pass
