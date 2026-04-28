"""
Registro de tools disponíveis aos agentes LLM.

Uma Tool aqui é um trio:
  - definicao: dict no formato esperado pela API Anthropic (name, description, input_schema)
  - funcao:   callable Python que executa a operação e devolve string ou dict
  - paralela: marca read-only para hint de paralelismo (não usado pelo loop atual)

O runner consulta o registro pelo nome para executar cada tool_use que o
modelo emite. Mantemos as definições explícitas em vez de auto-gerar do
docstring — fica mais legível e dá controle fino sobre as descrições, que
são o que o modelo usa para decidir.
"""
import json
from dataclasses import dataclass, field
from typing import Callable, Any


class SinalControle(Exception):
    """Exceções desta hierarquia NÃO são tratadas como erro de tool: propagam ao runner.

    Usada para casos como pausa para HITL, em que o controle deve voltar ao
    loop em vez de devolver um tool_result de erro ao modelo.
    """


@dataclass
class Tool:
    nome: str
    descricao: str
    input_schema: dict
    funcao: Callable[..., Any]
    paralela: bool = False

    def definicao(self) -> dict:
        """Devolve a tool no formato function-calling da OpenAI."""
        return {
            "type": "function",
            "function": {
                "name": self.nome,
                "description": self.descricao,
                "parameters": self.input_schema,
            },
        }


@dataclass
class RegistroTools:
    tools: dict[str, Tool] = field(default_factory=dict)

    def registrar(self, tool: Tool) -> None:
        if tool.nome in self.tools:
            raise ValueError(f"Tool '{tool.nome}' já registrada.")
        self.tools[tool.nome] = tool

    def definicoes(self) -> list[dict]:
        return [t.definicao() for t in self.tools.values()]

    def executar(self, nome: str, entrada: dict) -> str:
        if nome not in self.tools:
            return json.dumps(
                {"status": "erro", "erros": [f"Tool desconhecida: {nome}"]},
                ensure_ascii=False,
            )
        try:
            resultado = self.tools[nome].funcao(**entrada)
        except SinalControle:
            raise
        except TypeError as e:
            return json.dumps(
                {"status": "erro", "erros": [f"Argumentos inválidos para '{nome}': {e}"]},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"status": "erro", "erros": [f"Falha ao executar '{nome}': {e}"]},
                ensure_ascii=False,
            )
        return _serializar(resultado)


def _serializar(valor: Any) -> str:
    if isinstance(valor, str):
        return valor
    try:
        return json.dumps(valor, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(valor)
