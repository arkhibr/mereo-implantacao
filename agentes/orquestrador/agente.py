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
from agentes.validacao      import agente as ag_validacao

PIPELINE = [
    ("diagnostico",    ag_diagnostico,    "Analisando arquivos do cliente..."),
    ("mapeamento",     ag_mapeamento,     "Construindo mapeamento de campos..."),
    ("areas",          ag_areas,          "Transformando áreas..."),
    ("colaboradores",  ag_colaboradores,  "Transformando colaboradores..."),
    ("indicadores",    ag_indicadores,    "Transformando indicadores..."),
    ("metas",          ag_metas,          "Transformando metas..."),
    ("curva_alcance",  ag_curva_alcance,  "Transformando curva de alcance..."),
    ("valores",        ag_valores,        "Transformando valores..."),
    ("validacao",      ag_validacao,      "Validando e gerando output..."),
]

# Agentes que, se falharem, bloqueiam todos os seguintes
BLOQUEADORES = {"diagnostico", "mapeamento", "areas"}


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

    _log(f"\n{'='*50}")
    _log(f"Iniciando pipeline — cliente: {base.name}")
    _log(f"Etapas: {agentes_executar}")
    _log(f"{'='*50}\n")

    for nome, modulo, mensagem in PIPELINE:
        if nome not in agentes_executar:
            continue

        _log(f"[{nome.upper()}] {mensagem}")

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
        if status == "erro":
            _log(f"  ❌ Falhou: {res.get('erros', [])}")
            if parar_em_erro and nome in BLOQUEADORES:
                resultado["status"] = "erro"
                resultado["erros"].append(f"Pipeline interrompido em '{nome}' (agente bloqueador).")
                break
        elif status == "aviso":
            _log(f"  ⚠️  Concluído com avisos: {res.get('avisos', [])[:2]}")
        else:
            dados = res.get("dados", {})
            _log(f"  ✅ OK — {_resumir_dados(dados)}")

    resultado["fim"] = datetime.now().isoformat()

    status_final = _calcular_status_final(resultado["etapas"])
    resultado["status"] = status_final

    # Persistir log do pipeline
    _salvar_log(resultado, base / "relatorios" / "log_pipeline.json")

    _log(f"\n{'='*50}")
    _log(f"Pipeline concluído — status: {status_final.upper()}")
    _log(f"Erros: {len(resultado['erros'])} | Avisos: {len(resultado['avisos'])}")
    _log(f"{'='*50}\n")

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


def _log(msg: str):
    print(msg)
