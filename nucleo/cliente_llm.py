"""
Configuração do cliente LLM e parâmetros padrão para os agentes.

Usamos o SDK OpenAI apontando para um gateway OpenAI-compatible
(default: Abacus RouteLLM). Trocar o `MEREO_LLM_BASE_URL` e a
`MEREO_LLM_API_KEY` permite migrar para outro gateway (OpenAI direto,
Together, Groq, vLLM local, etc.) sem mexer em código.

Parâmetros como `reasoning_effort` ou `thinking` são provider-específicos
e não são propagados aqui — os agentes podem injetá-los caso saibam que
o modelo escolhido suporta.
"""
import os
from openai import OpenAI


BASE_URL_PADRAO = "https://routellm.abacus.ai/v1"
MODELO_PADRAO = "gpt-5"
MAX_TOKENS_PADRAO = 16000
MAX_ITERACOES_PADRAO = 50


def construir_cliente() -> OpenAI:
    """Cria cliente OpenAI configurado para o gateway escolhido."""
    api_key = os.environ.get("MEREO_LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "MEREO_LLM_API_KEY não definida. "
            "Exporte a variável antes de rodar agentes LLM:  "
            "export MEREO_LLM_API_KEY=..."
        )
    base_url = os.environ.get("MEREO_LLM_BASE_URL", BASE_URL_PADRAO)
    return OpenAI(base_url=base_url, api_key=api_key)


def parametros_padrao() -> dict:
    """Parâmetros default usados pelo runner em cada chamada à API."""
    return {
        "model": os.environ.get("MEREO_LLM_MODEL", MODELO_PADRAO),
        "max_completion_tokens": int(os.environ.get("MEREO_MAX_TOKENS", MAX_TOKENS_PADRAO)),
    }


def max_iteracoes() -> int:
    """Limite de iterações do loop agente para evitar loops infinitos."""
    return int(os.environ.get("MEREO_MAX_ITERACOES", MAX_ITERACOES_PADRAO))
