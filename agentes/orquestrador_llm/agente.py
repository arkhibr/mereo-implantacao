"""
Agente Orquestrador — versão LLM.

Decide o próximo passo no pipeline de implantação a partir do estado em
disco do cliente. Executa diretamente as transformações determinísticas
e delega os agentes LLM (diagnóstico, mapeamento, validação) via HITL —
quando precisa que outro agente LLM rode, pausa a própria sessão e pede
ao consultor para rodar o comando correspondente, no espírito de manter
um único modelo de pausa/retomada em todos os pontos.
"""
import json
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agentes.areas         import agente as ag_areas
from agentes.colaboradores import agente as ag_colaboradores
from agentes.indicadores   import agente as ag_indicadores
from agentes.metas         import agente as ag_metas
from agentes.curva_alcance import agente as ag_curva_alcance
from agentes.valores       import agente as ag_valores
from nucleo.hitl import HITLPausaSolicitada, construir_tool_hitl
from nucleo.registro_tools import RegistroTools, Tool
from nucleo.runner import executar_agente
from nucleo.sessoes import Sessao


BASE_PROJETO = Path(__file__).parent.parent.parent

# 6 transformações determinísticas que o orquestrador roda direto.
ETAPAS_DETERMINISTAS = {
    "areas":          ag_areas,
    "colaboradores":  ag_colaboradores,
    "indicadores":    ag_indicadores,
    "metas":          ag_metas,
    "curva_alcance":  ag_curva_alcance,
    "valores":        ag_valores,
}

# Agentes LLM que devem ser delegados via HITL — não são invocados em-processo.
AGENTES_LLM_DELEGAVEIS = {
    "diagnosticar": "Roda o agente LLM de diagnóstico — gera config/diagnostico.json a partir de raw/.",
    "mapear":       "Roda o agente LLM de mapeamento — gera config/mapeamento.json a partir do diagnóstico. Pode pausar para HITL próprio.",
    "validar":      "Roda o agente LLM de validação — valida staging contra templates e gera output/<data>/ se aprovado.",
}

PROMPT_SISTEMA = (
    (BASE_PROJETO / "prompts/sistema/base_agente.md").read_text(encoding="utf-8")
    + "\n\n---\n\n"
    + (BASE_PROJETO / "sops/agentes/sop_orquestrador.md").read_text(encoding="utf-8")
)

PROMPT_TAREFA = (
    "Inspecione o estado atual do cliente, decida e execute os próximos passos "
    "razoáveis no pipeline. Delegue agentes LLM via HITL quando necessário e "
    "registre tudo em relatorios/log_pipeline.json ao final."
)

# Mapping staging → entidade (espelha o do agente de validação).
STAGING_ENTIDADES = {
    "areas":                "staging/01_areas/areas_transformadas.csv",
    "colaboradores":        "staging/02_colaboradores/colaboradores_transformados.csv",
    "indicadores":          "staging/03_indicadores/indicadores_transformados.csv",
    "metas_individuais":    "staging/04_metas_individuais/metas_individual_transformadas.csv",
    "metas_compartilhadas": "staging/05_metas_compartilhadas/metas_compartilhada_transformadas.csv",
    "metas_projeto":        "staging/06_metas_projeto/metas_projeto_transformadas.csv",
    "curva_alcance":        "staging/07_curva_alcance/curva_alcance_transformada.csv",
}


def construir_registro(pasta_cliente: str, sessao: Sessao | None = None) -> RegistroTools:
    base = Path(pasta_cliente)
    relatorios = base / "relatorios"
    relatorios.mkdir(exist_ok=True)

    # Etapas executadas em-processo. Persistidas em sessao/orquestrador.json
    # para sobreviver à pausa/retomada por HITL — do contrário, o registro é
    # reconstruído na retomada e a lista zera, deixando log_pipeline.json
    # com etapas: [].
    estado_path = sessao.dir / "orquestrador.json" if sessao else None
    executadas: list[dict] = []
    if estado_path and estado_path.exists():
        try:
            executadas = json.loads(estado_path.read_text(encoding="utf-8")).get("executadas", [])
        except json.JSONDecodeError:
            pass

    def _persistir():
        if estado_path:
            estado_path.write_text(
                json.dumps({"executadas": executadas}, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )

    # ── Tools ────────────────────────────────────────────────────────────────

    def t_inspecionar() -> dict:
        config = base / "config"
        raw = base / "raw"
        relatorios_dir = base / "relatorios"
        output_dir = base / "output"

        # raw/
        arquivos_raw = []
        if raw.exists():
            for f in raw.rglob("*"):
                if f.is_file() and f.suffix.lower() in {".xlsx", ".xls", ".csv"}:
                    arquivos_raw.append(str(f.relative_to(base)))

        # config/
        diag_path = config / "diagnostico.json"
        map_path = config / "mapeamento.json"
        mapeamento_travado = False
        entidades_mapeadas = []
        if map_path.exists():
            try:
                m = json.loads(map_path.read_text(encoding="utf-8"))
                mapeamento_travado = bool(m.get("travado"))
                entidades_mapeadas = [
                    k for k, v in m.items()
                    if k != "travado" and isinstance(v, dict) and v.get("arquivo_sugerido")
                ]
            except json.JSONDecodeError:
                pass

        dicionarios = []
        if config.exists():
            for f in config.glob("dicionario_*.csv"):
                dicionarios.append(f.name)

        # staging/
        entidades_em_staging = []
        for ent, rel in STAGING_ENTIDADES.items():
            if (base / rel).exists():
                entidades_em_staging.append(ent)

        # output/<data>/
        outputs = []
        if output_dir.exists():
            for d in sorted(output_dir.iterdir()):
                if d.is_dir():
                    arquivos = sorted([f.name for f in d.iterdir() if f.is_file()])
                    outputs.append({"data": d.name, "arquivos": arquivos})
        output_hoje = datetime.now().date().isoformat()

        # relatorios/
        tem_relatorio_validacao = (relatorios_dir / "relatorio_validacao.md").exists()

        return {
            "status": "ok",
            "dados": {
                "arquivos_raw": arquivos_raw,
                "tem_diagnostico": diag_path.exists(),
                "tem_mapeamento": map_path.exists(),
                "mapeamento_travado": mapeamento_travado,
                "entidades_mapeadas_com_fonte": entidades_mapeadas,
                "dicionarios_presentes": dicionarios,
                "entidades_em_staging": entidades_em_staging,
                "outputs_existentes": outputs,
                "output_de_hoje_existe": any(o["data"] == output_hoje for o in outputs),
                "tem_relatorio_validacao": tem_relatorio_validacao,
            },
        }

    def t_executar_etapa(etapa: str) -> dict:
        if etapa not in ETAPAS_DETERMINISTAS:
            return {
                "status": "erro",
                "erros": [
                    f"Etapa '{etapa}' não é um agente determinístico de transformação. "
                    f"Válidos: {sorted(ETAPAS_DETERMINISTAS)}. Para diagnosticar, mapear ou "
                    f"validar, use 'acionar_agente_llm'."
                ],
            }

        modulo = ETAPAS_DETERMINISTAS[etapa]
        try:
            res = modulo.executar(str(base))
        except Exception as e:
            executadas.append({"etapa": etapa, "status": "erro", "detalhe": f"Exceção: {e}"})
            _persistir()
            return {
                "status": "erro",
                "erros": [f"Falha ao executar '{etapa}': {e}"],
            }

        executadas.append({
            "etapa": etapa,
            "status": res.get("status", "?"),
            "erros": res.get("erros", []),
            "avisos": res.get("avisos", []),
            "dados_resumo": _resumir_dados(res.get("dados", {})),
        })
        _persistir()
        return {
            "status": res.get("status", "?"),
            "dados": {
                "etapa": etapa,
                "resumo": _resumir_dados(res.get("dados", {})),
            },
            "erros": res.get("erros", []),
            "avisos": res.get("avisos", []),
        }

    def t_acionar_llm(nome: str, contexto: str = "") -> str:
        if nome not in AGENTES_LLM_DELEGAVEIS:
            return json.dumps(
                {
                    "status": "erro",
                    "erros": [
                        f"Agente LLM desconhecido: '{nome}'. "
                        f"Válidos: {sorted(AGENTES_LLM_DELEGAVEIS)}."
                    ],
                },
                ensure_ascii=False,
            )

        descricao = AGENTES_LLM_DELEGAVEIS[nome]
        cliente = base.name
        pergunta = (
            f"Por favor rode o agente LLM '{nome}' para o cliente '{cliente}' "
            f"e, ao terminar, responda aqui descrevendo o resultado (ou simplesmente 'feito')."
        )
        contexto_full = (
            f"Comando para executar:\n  ./implantacao {nome} {cliente}\n\n"
            f"O que esse agente faz: {descricao}\n\n"
            "Esta sessão do orquestrador será pausada até sua resposta. "
            "Para retomar:\n"
            f"  ./implantacao responder {cliente} <id_desta_sessao>\n"
        )
        if contexto:
            contexto_full += f"\nContexto adicional do orquestrador:\n{contexto}\n"

        # Levanta SinalControle — runner captura, salva estado e pausa a sessão.
        raise HITLPausaSolicitada(
            pergunta=pergunta,
            contexto=contexto_full,
            opcoes=None,
        )

    def t_gravar_log(
        recomendacao: str,
        etapas_extras: list = None,
    ) -> dict:
        agora = datetime.now().isoformat(timespec="seconds")

        # Junta etapas do orquestrador atual + extras informados pelo modelo
        # (ex: registros de delegações concluídas via HITL).
        etapas_finais = list(executadas)
        if etapas_extras:
            for e in etapas_extras:
                if isinstance(e, dict):
                    etapas_finais.append(e)

        log = {
            "agente": "orquestrador_llm",
            "cliente": base.name,
            "atualizado_em": agora,
            "etapas": etapas_finais,
            "recomendacao": recomendacao,
        }

        caminho = relatorios / "log_pipeline.json"
        # Append-friendly: se já existe, preserva histórico em "anteriores".
        if caminho.exists():
            try:
                anterior = json.loads(caminho.read_text(encoding="utf-8"))
                log["anteriores"] = anterior.get("anteriores", []) + [
                    {k: v for k, v in anterior.items() if k != "anteriores"}
                ]
            except json.JSONDecodeError:
                pass

        caminho.write_text(
            json.dumps(log, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        return {
            "status": "ok",
            "dados": {
                "arquivo": str(caminho.relative_to(base)),
                "total_etapas": len(etapas_finais),
            },
        }

    # ── Registro ─────────────────────────────────────────────────────────────

    registro = RegistroTools()
    registro.registrar(Tool(
        nome="inspecionar_estado",
        descricao=(
            "Inspeciona o estado em disco do cliente: arquivos em raw/, presença de "
            "diagnostico.json, mapeamento (e se está travado), dicionários de recodificação, "
            "entidades em staging, outputs já gerados. Use no início de cada execução para "
            "decidir o próximo passo."
        ),
        input_schema={"type": "object", "properties": {}},
        funcao=t_inspecionar,
        paralela=True,
    ))
    registro.registrar(Tool(
        nome="executar_etapa_determinista",
        descricao=(
            "Executa um dos 6 agentes determinísticos de transformação em-processo. "
            "Devolve status, resumo e erros/avisos. Cada etapa lê de raw/ + config/ e grava em "
            "staging/. Use após mapeamento estar travado e dicionários presentes. Pode chamar "
            "várias em paralelo se forem independentes (areas é dependência das demais)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "etapa": {
                    "type": "string",
                    "enum": sorted(ETAPAS_DETERMINISTAS.keys()),
                },
            },
            "required": ["etapa"],
        },
        funcao=t_executar_etapa,
    ))
    registro.registrar(Tool(
        nome="acionar_agente_llm",
        descricao=(
            "Pausa esta sessão do orquestrador e instrui o consultor a rodar um agente LLM "
            "(diagnosticar, mapear ou validar) num comando separado. A sessão é retomada quando "
            "o consultor responder com o resultado. Use para qualquer etapa LLM — não há outra "
            "forma de invocá-las daqui."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nome": {
                    "type": "string",
                    "enum": sorted(AGENTES_LLM_DELEGAVEIS.keys()),
                },
                "contexto": {
                    "type": "string",
                    "description": "Texto opcional explicando POR QUE você está acionando agora (ex: 'mapeamento.json não está travado, preciso de revisão').",
                },
            },
            "required": ["nome"],
        },
        funcao=t_acionar_llm,
    ))
    registro.registrar(Tool(
        nome="gravar_log_pipeline",
        descricao=(
            "Escreve relatorios/log_pipeline.json com o histórico de etapas executadas nesta "
            "sessão e a recomendação final para o consultor. Chame UMA vez no fim. Pode incluir "
            "etapas_extras (ex: registros de delegações concluídas via HITL, conforme você "
            "interpretar das respostas humanas)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "recomendacao": {
                    "type": "string",
                    "description": "Próximo passo concreto sugerido (comando, ação humana, ou 'pipeline pronto').",
                },
                "etapas_extras": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "Lista opcional de etapas para registrar além das executadas em-processo (ex: delegações HITL confirmadas).",
                },
            },
            "required": ["recomendacao"],
        },
        funcao=t_gravar_log,
    ))
    registro.registrar(construir_tool_hitl())
    return registro


def executar(pasta_cliente: str):
    base = Path(pasta_cliente)
    # Cria a sessão antes do registro para que o registro possa persistir
    # 'executadas' em sessao/orquestrador.json e sobreviver à pausa HITL.
    sessao = Sessao.criar(base, "orquestrador_llm", PROMPT_SISTEMA, PROMPT_TAREFA)
    registro = construir_registro(pasta_cliente, sessao=sessao)
    return executar_agente(
        cliente_path=base,
        agente="orquestrador_llm",
        prompt_sistema=PROMPT_SISTEMA,
        tarefa=PROMPT_TAREFA,
        registro=registro,
        sessao=sessao,
    )


# ── helpers ──────────────────────────────────────────────────────────────────

def _resumir_dados(dados: dict) -> str:
    if not isinstance(dados, dict):
        return "concluído"
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
