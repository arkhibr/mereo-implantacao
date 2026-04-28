"""
Runner do agente LLM — loop manual de tool use com suporte a HITL.

Usa Chat Completions (OpenAI-compatible) com formato function-calling.
O loop é manual em vez do tool-runner do SDK porque precisamos parar
de forma controlada quando o agente chama `perguntar_humano` e gravar
estado para retomada posterior.

Fluxo:

  executar_agente(...)        cria sessão nova, dispara o loop
       │
       ▼
  _loop(...)                  conversa com o modelo até concluir ou pausar
       │
       ├── finish=stop        → status=concluida
       ├── HITL levantada     → grava estado, status=pausada_hitl
       └── max iteracoes      → status=erro

  retomar_agente(...)         carrega sessão pausada, injeta resposta humana,
                              continua o mesmo _loop
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from openai import OpenAI, OpenAIError

from . import cliente_llm, sessoes
from .hitl import HITLPausaSolicitada
from .registro_tools import RegistroTools


@dataclass
class ResultadoExecucao:
    status: str           # ativa | pausada_hitl | concluida | erro
    sessao_id: str
    resposta_final: str = ""
    pergunta_humana: dict | None = None  # {pergunta, contexto, opcoes}
    erro: str | None = None


def executar_agente(
    cliente_path: Path,
    agente: str,
    prompt_sistema: str,
    tarefa: str,
    registro: RegistroTools,
) -> ResultadoExecucao:
    """Cria sessão nova e roda o agente até concluir ou pausar para HITL."""
    sessao = sessoes.Sessao.criar(cliente_path, agente, prompt_sistema, tarefa)

    mensagens: list[dict] = [{"role": "user", "content": tarefa}]
    sessao.append_mensagem(mensagens[0])

    cliente = cliente_llm.construir_cliente()
    return _loop(cliente, sessao, prompt_sistema, registro, mensagens)


def retomar_agente(
    cliente_path: Path,
    sessao_id: str,
    resposta_humana: str,
    registro: RegistroTools,
) -> ResultadoExecucao:
    """Carrega sessão pausada, entrega a resposta humana e continua o loop."""
    sessao = sessoes.Sessao.carregar(cliente_path, sessao_id)
    estado = sessao.carregar_estado()

    if estado is None or estado.get("tipo") != "hitl":
        return ResultadoExecucao(
            status="erro",
            sessao_id=sessao_id,
            erro="Sessão não está pausada aguardando resposta humana.",
        )

    mensagens = sessao.carregar_mensagens()
    prompt_sistema = estado["prompt_sistema"]

    # Reconstruir as mensagens role=tool acumuladas + a resposta humana
    # + stubs para tool_calls que ficaram para trás.
    novas: list[dict] = list(estado.get("tool_results_parciais", []))
    novas.append({
        "role": "tool",
        "tool_call_id": estado["tool_call_id_hitl"],
        "content": resposta_humana,
    })
    for tcid in estado.get("tool_call_ids_nao_executados", []):
        novas.append({
            "role": "tool",
            "tool_call_id": tcid,
            "content": "Execução pausada antes desta chamada para aguardar resposta humana. Reavalie se ainda é necessário executá-la.",
        })

    for msg in novas:
        mensagens.append(msg)
        sessao.append_mensagem(msg)

    sessao.limpar_estado()
    sessao.atualizar_metadata(status=sessoes.STATUS_ATIVA)

    cliente = cliente_llm.construir_cliente()
    return _loop(cliente, sessao, prompt_sistema, registro, mensagens)


def _loop(
    cliente: OpenAI,
    sessao: sessoes.Sessao,
    prompt_sistema: str,
    registro: RegistroTools,
    mensagens: list[dict],
) -> ResultadoExecucao:
    """Loop manual do agente. Executa até finish_reason=stop, HITL ou max iteracoes."""

    parametros = cliente_llm.parametros_padrao()
    max_iter = cliente_llm.max_iteracoes()
    tools = registro.definicoes()

    for _ in range(max_iter):
        mensagens_api = [{"role": "system", "content": prompt_sistema}] + mensagens

        try:
            resposta = cliente.chat.completions.create(
                messages=mensagens_api,
                tools=tools if tools else None,
                **parametros,
            )
        except OpenAIError as e:
            sessao.atualizar_metadata(status=sessoes.STATUS_ERRO)
            return ResultadoExecucao(
                status=sessoes.STATUS_ERRO,
                sessao_id=sessao.id,
                erro=f"Erro na API LLM: {e}",
            )

        choice = resposta.choices[0]
        message_dict = _serializar_message(choice.message)
        mensagens.append(message_dict)
        sessao.append_mensagem(message_dict)

        finish = choice.finish_reason

        if finish == "stop":
            texto_final = (message_dict.get("content") or "").strip()
            sessao.atualizar_metadata(status=sessoes.STATUS_CONCLUIDA)
            return ResultadoExecucao(
                status=sessoes.STATUS_CONCLUIDA,
                sessao_id=sessao.id,
                resposta_final=texto_final,
            )

        if finish != "tool_calls":
            sessao.atualizar_metadata(status=sessoes.STATUS_ERRO)
            motivo = {
                "length": "max_completion_tokens atingido sem conclusão",
                "content_filter": "filtro de conteúdo do provider",
            }.get(finish, f"finish_reason inesperado: {finish}")
            return ResultadoExecucao(
                status=sessoes.STATUS_ERRO,
                sessao_id=sessao.id,
                erro=motivo,
            )

        tool_calls = message_dict.get("tool_calls") or []
        tool_results: list[dict] = []
        hitl: HITLPausaSolicitada | None = None
        index_hitl: int = -1

        for i, tc in enumerate(tool_calls):
            nome = tc["function"]["name"]
            try:
                argumentos = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError as e:
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(
                        {"status": "erro", "erros": [f"JSON inválido em arguments: {e}"]},
                        ensure_ascii=False,
                    ),
                })
                continue

            try:
                conteudo = registro.executar(nome, argumentos)
                tool_results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": conteudo,
                })
            except HITLPausaSolicitada as e:
                hitl = e
                hitl.tool_use_id = tc["id"]  # reusando o campo, agora é o tool_call_id
                index_hitl = i
                break

        if hitl is not None:
            ids_nao_executados = [t["id"] for t in tool_calls[index_hitl + 1:]]
            estado = {
                "tipo": "hitl",
                "prompt_sistema": prompt_sistema,
                "tool_call_id_hitl": hitl.tool_use_id,
                "tool_results_parciais": tool_results,
                "tool_call_ids_nao_executados": ids_nao_executados,
                "pergunta": hitl.pergunta,
                "contexto": hitl.contexto,
                "opcoes": hitl.opcoes,
            }
            sessao.gravar_estado(estado)
            sessao.atualizar_metadata(status=sessoes.STATUS_PAUSADA_HITL)
            return ResultadoExecucao(
                status=sessoes.STATUS_PAUSADA_HITL,
                sessao_id=sessao.id,
                pergunta_humana={
                    "pergunta": hitl.pergunta,
                    "contexto": hitl.contexto,
                    "opcoes": hitl.opcoes,
                },
            )

        for msg in tool_results:
            mensagens.append(msg)
            sessao.append_mensagem(msg)

    sessao.atualizar_metadata(status=sessoes.STATUS_ERRO)
    return ResultadoExecucao(
        status=sessoes.STATUS_ERRO,
        sessao_id=sessao.id,
        erro=f"Limite de {max_iter} iterações atingido sem conclusão.",
    )


def _serializar_message(message: Any) -> dict:
    """Converte ChatCompletionMessage do SDK em dict serializável e re-enviável."""
    if hasattr(message, "model_dump"):
        return message.model_dump(exclude_none=True, exclude_unset=False)
    if isinstance(message, dict):
        return message
    return json.loads(json.dumps(message, default=str))
