"""
Persistência de sessões de agentes LLM.

Cada execução de um agente LLM gera uma sessão sob
`clientes/<cliente>/sessoes/<id>/`, com:

  metadata.json   — agente, cliente, status, timestamps
  prompt.md       — system prompt + tarefa inicial usados
  transcript.jsonl — uma linha por mensagem da conversa (formato Anthropic)
  estado.json     — estado pendente para retomar após HITL (quando aplicável)

A sessão é o que permite auditoria, retomada após pergunta humana e replay
para depuração.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STATUS_ATIVA = "ativa"
STATUS_PAUSADA_HITL = "pausada_hitl"
STATUS_CONCLUIDA = "concluida"
STATUS_ERRO = "erro"


def _agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Sessao:
    """Representa uma sessão em disco. Stateless quanto a mensagens — usa append no jsonl."""

    def __init__(self, base: Path, sessao_id: str):
        self.base = base
        self.id = sessao_id
        self.dir = base / "sessoes" / sessao_id

    @property
    def metadata_path(self) -> Path:
        return self.dir / "metadata.json"

    @property
    def transcript_path(self) -> Path:
        return self.dir / "transcript.jsonl"

    @property
    def prompt_path(self) -> Path:
        return self.dir / "prompt.md"

    @property
    def estado_path(self) -> Path:
        return self.dir / "estado.json"

    @classmethod
    def criar(
        cls,
        base_cliente: Path,
        agente: str,
        prompt_sistema: str,
        tarefa_inicial: str,
    ) -> "Sessao":
        sid = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        sessao = cls(base_cliente, sid)
        sessao.dir.mkdir(parents=True, exist_ok=True)

        metadata = {
            "id": sid,
            "agente": agente,
            "cliente": base_cliente.name,
            "status": STATUS_ATIVA,
            "criada_em": _agora_iso(),
            "atualizada_em": _agora_iso(),
        }
        sessao._gravar_json(sessao.metadata_path, metadata)
        sessao.prompt_path.write_text(
            f"# System prompt\n\n{prompt_sistema}\n\n# Tarefa inicial\n\n{tarefa_inicial}\n",
            encoding="utf-8",
        )
        return sessao

    @classmethod
    def carregar(cls, base_cliente: Path, sessao_id: str) -> "Sessao":
        sessao = cls(base_cliente, sessao_id)
        if not sessao.metadata_path.exists():
            raise FileNotFoundError(f"Sessão não encontrada: {sessao.dir}")
        return sessao

    def metadata(self) -> dict:
        return json.loads(self.metadata_path.read_text(encoding="utf-8"))

    def atualizar_metadata(self, **mudancas: Any) -> None:
        meta = self.metadata()
        meta.update(mudancas)
        meta["atualizada_em"] = _agora_iso()
        self._gravar_json(self.metadata_path, meta)

    def append_mensagem(self, mensagem: dict) -> None:
        """Acrescenta uma mensagem ao transcript (role + content da API Anthropic)."""
        with self.transcript_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(mensagem, ensure_ascii=False, default=str) + "\n")

    def carregar_mensagens(self) -> list[dict]:
        if not self.transcript_path.exists():
            return []
        mensagens: list[dict] = []
        for linha in self.transcript_path.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if linha:
                mensagens.append(json.loads(linha))
        return mensagens

    def gravar_estado(self, estado: dict) -> None:
        self._gravar_json(self.estado_path, estado)

    def carregar_estado(self) -> dict | None:
        if not self.estado_path.exists():
            return None
        return json.loads(self.estado_path.read_text(encoding="utf-8"))

    def limpar_estado(self) -> None:
        if self.estado_path.exists():
            self.estado_path.unlink()

    @staticmethod
    def _gravar_json(caminho: Path, dados: dict) -> None:
        caminho.write_text(
            json.dumps(dados, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
