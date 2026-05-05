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
  ./implantacao inferir     <cliente>                   (agente LLM de inferência — fabrica entidades faltantes)
  ./implantacao pilotar     <cliente>                   (agente LLM orquestrador — decide próximo passo)
  ./implantacao responder   <cliente> <sessao_id>       (retoma agente em HITL)
"""
import argparse
import importlib
import os
import shutil
import sys
from pathlib import Path

BASE = Path(__file__).parent
CLIENTES_DIR = BASE / "clientes"
MODELO_DIR = CLIENTES_DIR / "_modelo"

# Lazy import (depois que sys.path estiver ajustado em tempo de execução).
def _visual():
    sys.path.insert(0, str(BASE))
    from nucleo import visual
    return visual


def _carregar_env(arquivo: Path) -> None:
    """Carrega variáveis de um .env simples (KEY=VALUE por linha) em os.environ.

    Variáveis já definidas no ambiente NÃO são sobrescritas. Linhas em branco e
    comentários (#) são ignorados. Aspas simples/duplas em volta do valor são
    removidas. Mantemos o parser local para evitar uma dependência nova
    (python-dotenv) e funcionar igual em Linux, macOS e Windows sem o wrapper
    shell.
    """
    if not arquivo.is_file():
        return
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave and chave not in os.environ:
            os.environ[chave] = valor


_carregar_env(BASE / ".env")

# Garante UTF-8 no stdout para os ícones (✓ ⏸ ✗) e textos acentuados — em
# Windows o cmd.exe historicamente usava cp1252 e quebrava esses caracteres.
# reconfigure existe em Python 3.7+; o try protege ambientes que redirecionam
# stdout para algo que não é TextIOWrapper (testes, pipes binários).
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

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
    "inferir":      ("agente_llm",   "Roda o agente LLM de inferência (fabrica entidades canônicas que o cliente não enviou)"),
    "pilotar":      ("agente_llm",   "Roda o agente LLM orquestrador (decide o próximo passo a partir do estado)"),
    "responder":    ("retomar_hitl", "Retoma agente LLM pausado aguardando resposta humana"),
}

AGENTES_LLM = {
    "demo":         "agentes.exemplo_llm.agente",
    "diagnosticar": "agentes.diagnostico_llm.agente",
    "mapear":       "agentes.mapeamento_llm.agente",
    "validar":      "agentes.validacao_llm.agente",
    "inferir":      "agentes.inferencia_llm.agente",
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

    v = _visual()
    print()
    print(v.cabecalho(
        largura=v.largura_terminal(default=60),
        Cliente=pasta.name,
        Etapa=titulo,
        Iniciado=v.agora(),
    ))
    print()

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
    v = _visual()
    print()
    print(v.cabecalho(
        largura=v.largura_terminal(default=60),
        Cliente=pasta.name,
        Agente=f"{comando} (LLM)",
        Iniciado=v.agora(),
    ))
    print()

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

    v = _visual()
    print(f"\n  {v.titulo('Pergunta pendente:')} {estado.get('pergunta', '')}")
    if estado.get("contexto"):
        print(f"\n  {v.titulo('Contexto:')} {estado['contexto']}")
    if estado.get("opcoes"):
        print(f"\n  {v.titulo('Opções sugeridas:')}")
        for opcao in estado["opcoes"]:
            print(f"    - {opcao}")
    print(f"\n  {v.info('Digite a resposta (Enter duplo para enviar):')}\n")
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

    print(f"\n  {v.info('Retomando agente...')}\n")
    resultado = retomar_agente(pasta, sessao_id, resposta, registro, sessao=sessao)
    _imprimir_resultado_llm(pasta, resultado)
    sys.exit(0 if resultado.status in ("concluida", "pausada_hitl") else 1)


def _imprimir_resultado_llm(pasta: Path, resultado):
    v = _visual()
    marca = {
        "concluida": v.success,
        "pausada_hitl": v.pausa,
        "erro": v.error,
        "ativa": v.info,
    }.get(resultado.status, v.info)
    print(f"  {marca(f'Status: {resultado.status.upper()}')}")
    print(f"    {v.fraco('Sessão:')} {v.caminho(f'clientes/{pasta.name}/sessoes/{resultado.sessao_id}')}")

    if resultado.status == "concluida":
        if resultado.resposta_final:
            print(f"\n  {v.titulo('Resposta do agente:')}\n")
            for linha in resultado.resposta_final.splitlines():
                print(f"    {linha}")
        print()

    elif resultado.status == "pausada_hitl" and resultado.pergunta_humana:
        ph = resultado.pergunta_humana
        print(f"\n  {v.colorir('❓', v.MAGENTA)} {v.titulo('Pergunta:')} {ph['pergunta']}")
        if ph.get("contexto"):
            print(f"\n     {v.titulo('Contexto:')} {ph['contexto']}")
        if ph.get("opcoes"):
            print(f"\n     {v.titulo('Opções:')}")
            for opcao in ph["opcoes"]:
                print(f"       - {opcao}")
        cmd_resp = f"./implantacao responder {pasta.name} {resultado.sessao_id}"
        print(f"\n  {v.info(f'Para responder: {v.comando(cmd_resp)}')}\n")

    elif resultado.status == "erro" and resultado.erro:
        print(f"\n  {v.error(resultado.erro)}\n")


def _imprimir_resultado(resultado: dict):
    v = _visual()
    etapas = resultado.get("etapas", {})
    erros_globais = resultado.get("erros", [])

    for nome, etapa in etapas.items():
        status = etapa.get("status", "?")
        marca = {"ok": v.success, "aviso": v.warning, "erro": v.error}.get(status, v.info)
        resumo = etapa.get("dados_resumo", "")
        linha = f"  {marca(f'{nome:<20} {status:<8}')}"
        if resumo:
            linha += f"  {v.fraco(resumo)}"
        print(linha)
        for e in etapa.get("erros", []):
            print(f"      {v.error(e)}")
        for a in etapa.get("avisos", []):
            print(f"      · {v.fraco(a)}")

    status_final = resultado.get("status", "erro")
    marca_final = {"ok": v.success, "aviso": v.warning}.get(status_final, v.error)
    print(f"\n  {marca_final(f'Status final: {status_final.upper()}')}")

    if erros_globais:
        print()
        for e in erros_globais:
            print(f"  {v.error(e)}")


def _erro(msg: str):
    print(f"\nErro: {msg}\n", file=sys.stderr)
    sys.exit(1)


_CATEGORIAS_AJUDA = [
    ("SETUP", [
        ("novo",         "<cliente>",          "Cria estrutura de pastas para um novo cliente"),
    ]),
    ("PIPELINE DETERMINISTA", [
        ("analisar",     "<cliente>",          "Diagnóstico + mapeamento automático"),
        ("transformar",  "<cliente>",          "Roda transformações + validação"),
        ("rodar",        "<cliente>",          "Pipeline completo (analisar + transformar)"),
    ]),
    ("AGENTES LLM", [
        ("diagnosticar", "<cliente>",          "Diagnóstico"),
        ("mapear",       "<cliente>",          "Mapeamento"),
        ("inferir",      "<cliente>",          "Inferência (fabrica entidades faltantes)"),
        ("validar",      "<cliente>",          "Validação final"),
        ("pilotar",      "<cliente>",          "Orquestrador (decide próximo passo)"),
    ]),
    ("HUMAN-IN-THE-LOOP", [
        ("responder",    "<cliente> <sessao>", "Retoma agente pausado aguardando resposta"),
    ]),
    ("OUTROS", [
        ("demo",         "<cliente>",          "Smoke test do agente exemplo (valida LLM)"),
        ("ajuda",        "",                   "Mostra esta tela"),
    ]),
]


def _imprimir_lista_comandos():
    v = _visual()
    for categoria, comandos in _CATEGORIAS_AJUDA:
        print(v.titulo(categoria))
        for nome_cmd, args, desc in comandos:
            sig = f"{nome_cmd:<13} {args:<20}"
            print(f"  {v.comando(sig)} {desc}")
        print()


def _welcome():
    v = _visual()
    from nucleo import __version__
    print()
    print(v.banner(versao=__version__))
    print()
    print("Transforma dados brutos de clientes corporativos nos arquivos")
    print("de importação da plataforma Mereo. Combina pipelines deterministas")
    print("+ agentes LLM com human-in-the-loop assíncrono.")
    print()
    print(f"{v.titulo('USO BÁSICO')}")
    print(f"  ./implantacao {v.comando('<comando>')} {v.comando('<cliente>')}")
    print()
    _imprimir_lista_comandos()
    print(v.titulo("EXEMPLOS"))
    print(f"  ./implantacao {v.comando('novo acme')}")
    print(f"  ./implantacao {v.comando('pilotar acme')}")
    print(f"  ./implantacao {v.comando('responder acme 20260428_142037_a3f1c2')}")
    print()
    print(v.fraco("Documentação: README.md  ·  ARCHITECTURE.md"))
    print(v.fraco("Provider LLM: configurado via .env (MEREO_LLM_API_KEY)"))
    print()


def _ajuda_compacta():
    v = _visual()
    from nucleo import __version__
    print()
    print(f"  Implantação RHTec/Mereo {v.fraco(f'· v{__version__}')}")
    print()
    print(f"  {v.titulo('Uso:')}  ./implantacao {v.comando('<comando>')} {v.comando('<cliente>')} [args]")
    print()
    _imprimir_lista_comandos()
    print(v.fraco("  Para a tela completa (banner + descrição), rode  ./implantacao  sem argumentos."))
    print()


def main():
    if len(sys.argv) < 2:
        _welcome()
        sys.exit(0)
    if sys.argv[1] in ("-h", "--help", "ajuda"):
        _ajuda_compacta()
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd not in SUBCOMANDOS:
        v = _visual()
        print(f"\n{v.error(f'Comando desconhecido: ' + repr(cmd))}", file=sys.stderr)
        _ajuda_compacta()
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
