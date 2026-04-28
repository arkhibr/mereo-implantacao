#!/usr/bin/env python3
"""
CLI de implantação — ponto de entrada para operações com clientes.

Uso:
  ./implantacao novo        <cliente>
  ./implantacao analisar    <cliente>
  ./implantacao transformar <cliente>
  ./implantacao rodar       <cliente>
  ./implantacao demo        <cliente>                   (agente LLM de validação)
  ./implantacao diagnosticar <cliente>                  (agente LLM de diagnóstico)
  ./implantacao mapear      <cliente>                   (agente LLM de mapeamento)
  ./implantacao validar     <cliente>                   (agente LLM de validação final)
  ./implantacao pilotar     <cliente>                   (agente LLM orquestrador — decide próximo passo)
  ./implantacao responder   <cliente> <sessao_id>       (retoma agente em HITL)
"""
import argparse
import importlib
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).parent
CLIENTES_DIR = BASE / "clientes"
MODELO_DIR = CLIENTES_DIR / "_modelo"

ETAPAS_DIAGNOSTICO = ["diagnostico", "mapeamento"]
ETAPAS_TRANSFORMACAO = [
    "areas", "colaboradores", "indicadores",
    "metas", "curva_alcance", "valores", "validacao",
]

SUBCOMANDOS = {
    "novo":         ("criar",        "Cria a estrutura de pastas para um novo cliente"),
    "analisar":     ("diagnostico",  "Roda diagnóstico determinista e gera mapeamento automático"),
    "transformar":  ("transformacao","Transforma os dados e gera o output final"),
    "rodar":        ("completo",     "Pipeline completo (analisar + transformar)"),
    "demo":         ("agente_llm",   "Roda o agente LLM de demonstração (validação da infra)"),
    "diagnosticar": ("agente_llm",   "Roda o agente LLM de diagnóstico (substitui o determinista quando estabilizado)"),
    "mapear":       ("agente_llm",   "Roda o agente LLM de mapeamento (substitui o determinista quando estabilizado)"),
    "validar":      ("agente_llm",   "Roda o agente LLM de validação final (substitui o determinista quando estabilizado)"),
    "pilotar":      ("agente_llm",   "Roda o agente LLM orquestrador (decide o próximo passo a partir do estado)"),
    "responder":    ("retomar_hitl", "Retoma agente LLM pausado aguardando resposta humana"),
}

AGENTES_LLM = {
    "demo":         "agentes.exemplo_llm.agente",
    "diagnosticar": "agentes.diagnostico_llm.agente",
    "mapear":       "agentes.mapeamento_llm.agente",
    "validar":      "agentes.validacao_llm.agente",
    "pilotar":      "agentes.orquestrador_llm.agente",
}


def criar_cliente(nome: str) -> Path:
    destino = CLIENTES_DIR / nome
    if destino.exists():
        _erro(f"Cliente '{nome}' já existe em {destino}")
    if not MODELO_DIR.exists():
        _erro(f"Diretório-modelo não encontrado: {MODELO_DIR}")
    shutil.copytree(MODELO_DIR, destino)
    print(f"\n  ✓ Estrutura criada para '{nome}'")
    print(f"  Deposite os arquivos do cliente em:  clientes/{nome}/raw/\n")
    return destino


def rodar_etapa(pasta: Path, etapa: str):
    sys.path.insert(0, str(BASE))

    if etapa == "diagnostico":
        escopo = ETAPAS_DIAGNOSTICO
        titulo = "Diagnóstico + Mapeamento automático"
        aviso_pos = (
            "\n  ► Próximo passo: revise e ajuste  clientes/{}/config/mapeamento.json\n"
            "    Quando estiver pronto, adicione  \"travado\": true  e rode:\n\n"
            "    ./implantacao transformar {}\n"
        ).format(pasta.name, pasta.name)
    elif etapa == "transformacao":
        escopo = ETAPAS_TRANSFORMACAO
        titulo = "Transformação + Validação"
        aviso_pos = None
    elif etapa == "completo":
        escopo = ETAPAS_DIAGNOSTICO + ETAPAS_TRANSFORMACAO
        titulo = "Pipeline completo"
        aviso_pos = None
    else:
        _erro(f"Etapa desconhecida: {etapa}")

    print(f"\n{'='*55}")
    print(f"  Cliente : {pasta.name}")
    print(f"  Etapa   : {titulo}")
    print(f"{'='*55}\n")

    from agentes.orquestrador import agente as orc
    resultado = orc.executar(str(pasta), escopo=escopo)

    _imprimir_resultado(resultado)

    if aviso_pos:
        print(aviso_pos)

    status = resultado.get("status", "erro")
    sys.exit(0 if status in ("ok", "aviso") else 1)


def rodar_agente_llm(pasta: Path, comando: str):
    sys.path.insert(0, str(BASE))
    if comando not in AGENTES_LLM:
        _erro(f"Agente LLM desconhecido para o comando: {comando}")

    modulo = importlib.import_module(AGENTES_LLM[comando])
    print(f"\n{'='*55}")
    print(f"  Cliente : {pasta.name}")
    print(f"  Agente  : {comando} (LLM)")
    print(f"{'='*55}\n")

    try:
        resultado = modulo.executar(str(pasta))
    except RuntimeError as e:
        _erro(str(e))

    _imprimir_resultado_llm(pasta, resultado)
    sys.exit(0 if resultado.status in ("concluida", "pausada_hitl") else 1)


def retomar_hitl(pasta: Path, sessao_id: str):
    sys.path.insert(0, str(BASE))
    from nucleo import sessoes as nuc_sessoes
    from nucleo.runner import retomar_agente

    try:
        sessao = nuc_sessoes.Sessao.carregar(pasta, sessao_id)
    except FileNotFoundError:
        _erro(f"Sessão não encontrada: clientes/{pasta.name}/sessoes/{sessao_id}")

    metadata = sessao.metadata()
    nome_agente = metadata.get("agente")
    comando = next((cmd for cmd, mod in AGENTES_LLM.items() if mod.endswith(f"{nome_agente}.agente")), None)
    if comando is None:
        _erro(f"Agente '{nome_agente}' da sessão não está mapeado em AGENTES_LLM.")

    estado = sessao.carregar_estado()
    if not estado:
        _erro(f"Sessão {sessao_id} não está pausada aguardando resposta humana.")

    print(f"\n  Pergunta pendente: {estado.get('pergunta', '')}")
    if estado.get("contexto"):
        print(f"\n  Contexto: {estado['contexto']}")
    if estado.get("opcoes"):
        print("\n  Opções sugeridas:")
        for opcao in estado["opcoes"]:
            print(f"    - {opcao}")
    print("\n  Digite a resposta (Enter duplo para enviar):\n")
    linhas = []
    while True:
        try:
            linha = input()
        except EOFError:
            break
        if linha == "" and linhas and linhas[-1] == "":
            linhas.pop()
            break
        linhas.append(linha)
    resposta = "\n".join(linhas).strip()
    if not resposta:
        _erro("Resposta vazia. Operação cancelada.")

    modulo = importlib.import_module(AGENTES_LLM[comando])
    registro = modulo.construir_registro(str(pasta), sessao=sessao)

    print("\n  Retomando agente...\n")
    resultado = retomar_agente(pasta, sessao_id, resposta, registro, sessao=sessao)
    _imprimir_resultado_llm(pasta, resultado)
    sys.exit(0 if resultado.status in ("concluida", "pausada_hitl") else 1)


def _imprimir_resultado_llm(pasta: Path, resultado):
    icone = {"concluida": "✓", "pausada_hitl": "⏸", "erro": "✗", "ativa": "…"}.get(resultado.status, "?")
    print(f"  {icone} Status: {resultado.status.upper()}")
    print(f"    Sessão: clientes/{pasta.name}/sessoes/{resultado.sessao_id}")

    if resultado.status == "concluida":
        if resultado.resposta_final:
            print("\n  Resposta do agente:\n")
            for linha in resultado.resposta_final.splitlines():
                print(f"    {linha}")
        print()

    elif resultado.status == "pausada_hitl" and resultado.pergunta_humana:
        ph = resultado.pergunta_humana
        print(f"\n  ❓ Pergunta: {ph['pergunta']}")
        if ph.get("contexto"):
            print(f"\n     Contexto: {ph['contexto']}")
        if ph.get("opcoes"):
            print("\n     Opções:")
            for opcao in ph["opcoes"]:
                print(f"       - {opcao}")
        print(f"\n  ► Para responder:  ./implantacao responder {pasta.name} {resultado.sessao_id}\n")

    elif resultado.status == "erro" and resultado.erro:
        print(f"\n  ✗ {resultado.erro}\n")


def _imprimir_resultado(resultado: dict):
    etapas = resultado.get("etapas", {})
    erros_globais = resultado.get("erros", [])

    for nome, etapa in etapas.items():
        status = etapa.get("status", "?")
        icone = {"ok": "✓", "aviso": "⚠", "erro": "✗"}.get(status, "?")
        resumo = etapa.get("dados_resumo", "")
        linha = f"  {icone} {nome:<20} {status:<8}"
        if resumo:
            linha += f"  {resumo}"
        print(linha)
        for e in etapa.get("erros", []):
            print(f"      ✗ {e}")
        for a in etapa.get("avisos", []):
            print(f"      · {a}")

    status_final = resultado.get("status", "erro")
    print(f"\n  Status final: {status_final.upper()}")

    if erros_globais:
        print()
        for e in erros_globais:
            print(f"  ✗ {e}")


def _erro(msg: str):
    print(f"\nErro: {msg}\n", file=sys.stderr)
    sys.exit(1)


def _ajuda():
    print("""
Uso:  ./implantacao <comando> <cliente> [args]

Comandos (deterministas):
  novo         <cliente>               Cria a estrutura de pastas para um novo cliente
  analisar     <cliente>               Diagnóstico + mapeamento automático (versão determinista)
  transformar  <cliente>               Transforma os dados e gera o output final
  rodar        <cliente>               Pipeline completo (analisar + transformar)

Comandos (agentes LLM):
  demo         <cliente>               Agente exemplo (valida infra LLM)
  diagnosticar <cliente>               Diagnóstico via agente LLM
  mapear       <cliente>               Mapeamento via agente LLM
  validar      <cliente>               Validação final via agente LLM
  pilotar      <cliente>               Orquestrador (decide o próximo passo)
  responder    <cliente> <sessao_id>   Retoma agente LLM pausado em human-in-the-loop

Exemplos:
  ./implantacao novo         acme
  ./implantacao analisar     acme
  ./implantacao diagnosticar acme
  ./implantacao mapear       acme
  ./implantacao validar      acme
  ./implantacao pilotar      acme
  ./implantacao responder    acme 20260426_142037_a3f1c2
""")


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "ajuda"):
        _ajuda()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd not in SUBCOMANDOS:
        print(f"\nComando desconhecido: '{cmd}'", file=sys.stderr)
        _ajuda()
        sys.exit(1)

    if len(sys.argv) < 3:
        _erro(f"Informe o nome do cliente.  Ex: ./implantacao {cmd} nome-do-cliente")

    nome = sys.argv[2]
    acao, _ = SUBCOMANDOS[cmd]

    if acao == "criar":
        criar_cliente(nome)
        return

    pasta = CLIENTES_DIR / nome
    if not pasta.exists():
        _erro(
            f"Cliente '{nome}' não encontrado.\n"
            f"  Para criar:  ./implantacao novo {nome}"
        )

    if acao == "agente_llm":
        rodar_agente_llm(pasta, cmd)
        return

    if acao == "retomar_hitl":
        if len(sys.argv) < 4:
            _erro("Informe o id da sessão.  Ex: ./implantacao responder cliente <sessao_id>")
        retomar_hitl(pasta, sys.argv[3])
        return

    rodar_etapa(pasta, acao)


if __name__ == "__main__":
    main()
