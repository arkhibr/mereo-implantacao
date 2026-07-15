#!/usr/bin/env python3
"""
CLI de implantação — ponto de entrada para operações com clientes.

Uso:
  ./implantacao novo        <cliente>
  ./implantacao analisar    <cliente>
  ./implantacao transformar <cliente>
  ./implantacao rodar       <cliente>
  ./implantacao grupos                                  (lista os módulos de carga)
  ./implantacao grupo       <grupo> <cliente>           (roda um módulo: nucleo, indicadores, metas, competencias)
  ./implantacao demo        <cliente>                   (agente LLM de validação)
  ./implantacao diagnosticar <cliente>                  (agente LLM de diagnóstico)
  ./implantacao mapear      <cliente>                   (agente LLM de mapeamento)
  ./implantacao validar     <cliente>                   (agente LLM de validação final)
  ./implantacao inferir     <cliente>                   (agente LLM de inferência — fabrica entidades faltantes)
  ./implantacao pilotar     <cliente>                   (agente LLM orquestrador — decide próximo passo)
  ./implantacao responder   <cliente> <sessao_id>       (retoma agente em HITL)
  ./implantacao depara      <cliente> [tipo]            (lista ou cria de-para manuais de códigos)
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
    "grupos":       ("listar_grupos","Lista os módulos de carga e suas dependências"),
    "grupo":        ("rodar_grupo",  "Roda um módulo de carga (nucleo, indicadores, metas, competencias)"),
    "demo":         ("agente_llm",   "Roda o agente LLM de demonstração (validação da infra)"),
    "diagnosticar": ("agente_llm",   "Roda o agente LLM de diagnóstico (substitui o determinista quando estabilizado)"),
    "mapear":       ("agente_llm",   "Roda o agente LLM de mapeamento (substitui o determinista quando estabilizado)"),
    "validar":      ("agente_llm",   "Roda o agente LLM de validação final (substitui o determinista quando estabilizado)"),
    "inferir":      ("agente_llm",   "Roda o agente LLM de inferência (fabrica entidades canônicas que o cliente não enviou)"),
    "pilotar":      ("agente_llm",   "Roda o agente LLM orquestrador (decide o próximo passo a partir do estado)"),
    "responder":    ("retomar_hitl", "Retoma agente LLM pausado aguardando resposta humana"),
    "depara":       ("depara",       "Lista ou cria de-para manuais (texto do cliente → código da plataforma)"),
}

# De-para manuais suportados: tipo → (arquivo em config/, onde é aplicado, exemplo de linha).
# Os agentes aplicam automaticamente quando o arquivo existe; formato id_origem;id_destino.
DE_PARA = {
    "pilares":             ("dicionario_pilares.csv",
                            "Metas — Código do Pilar Estratégico (padrão sem de-para: DZ001)",
                            "Metas Setoriais;DZ001"),
    "grupos":              ("dicionario_grupos_permissao.csv",
                            "Colaboradores — Código do Grupo de Permissões (padrão: GRP_4)",
                            "Administrador Global;GRP_4"),
    "indicadores":         ("dicionario_indicadores.csv",
                            "Indicadores e Metas — Código do Indicador",
                            "SLA de Atendimento;IND_0042"),
    "areas":               ("dicionario_areas.csv",
                            "Áreas (código e área superior), Colaboradores e Metas",
                            "Diretoria Comercial;1.2"),
    "colaboradores":       ("dicionario_colaboradores.csv",
                            "Metas — logins de responsável/data-provider",
                            "Maria Silva Santos;maria.santos"),
    "metas-individual":    ("dicionario_metas_individual.csv",
                            "Metas individuais, Curva de Alcance e Valores",
                            "FIN01;MT_0001"),
    "metas-compartilhada": ("dicionario_metas_compartilhada.csv",
                            "Metas compartilhadas, Curva de Alcance e Valores",
                            "FIN01;MT_0001"),
    "metas-projeto":       ("dicionario_metas_projeto.csv",
                            "Metas de projeto, Curva de Alcance e Valores",
                            "PRJ01;MT_0100"),
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


def listar_grupos_cli():
    sys.path.insert(0, str(BASE))
    from nucleo import grupos
    v = _visual()
    print()
    print(v.titulo("MÓDULOS DE CARGA"))
    print(v.fraco("  Núcleo (base seminal) ← grupos predicados."))
    print(v.fraco("  O consultor decide quando a base está pronta; a ferramenta apenas avisa."))
    print()
    from agentes.orquestrador import agente as orc
    for g in grupos.ordem_topologica():
        info = grupos.GRUPOS[g]
        marca = "◆" if info.get("seminal") else "◇"
        deps = info.get("depende_de", [])
        dep_txt = "depende de: " + ", ".join(deps) if deps else "base seminal"
        print(f"  {marca} {v.comando(g)}  {info['titulo']}  {v.fraco('(' + dep_txt + ')')}")
        etapas_fmt = [
            e if e in orc.ETAPAS_IMPLEMENTADAS else f"{e} (a implementar)"
            for e in info["etapas"]
        ]
        print(f"      {v.fraco('etapas: ' + ', '.join(etapas_fmt))}")
    print()
    print(v.fraco("  Rodar um módulo:  ") + v.comando("./implantacao grupo nucleo <cliente>"))
    print()


def rodar_grupo(pasta: Path, nome_grupo: str):
    sys.path.insert(0, str(BASE))
    from nucleo import grupos
    if nome_grupo not in grupos.GRUPOS:
        _erro(
            f"Grupo desconhecido: {nome_grupo!r}.  "
            f"Válidos: {', '.join(grupos.ordem_topologica())}.\n"
            f"  Para listar:  ./implantacao grupos"
        )

    info = grupos.GRUPOS[nome_grupo]
    escopo = grupos.etapas_do_grupo(nome_grupo)
    v = _visual()
    print()
    print(v.cabecalho(
        largura=v.largura_terminal(default=60),
        Cliente=pasta.name,
        Etapa=f"Módulo: {info['titulo']}",
        Iniciado=v.agora(),
    ))
    print()

    from agentes.orquestrador import agente as orc
    implementadas = [e for e in escopo if e in orc.ETAPAS_IMPLEMENTADAS]
    nao_impl = [e for e in escopo if e not in orc.ETAPAS_IMPLEMENTADAS]

    if not implementadas:
        print(v.warning(
            f"  Módulo '{info['titulo']}' está registrado na arquitetura, mas seus "
            "agentes de transformação ainda não foram implementados."
        ))
        print(v.fraco(f"  Etapas previstas (a implementar): {', '.join(escopo)}"))
        print(v.fraco("  Faltam os templates de import deste módulo para construir os agentes."))
        print()
        sys.exit(0)

    if nao_impl:
        print(v.fraco(f"  Etapas ainda não implementadas, ignoradas: {', '.join(nao_impl)}"))
        print()

    resultado = orc.executar(str(pasta), escopo=implementadas)
    _imprimir_resultado(resultado)

    status = resultado.get("status", "erro")
    sys.exit(0 if status in ("ok", "aviso") else 1)


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


def gerenciar_depara(pasta: Path, tipo: str = None):
    v = _visual()
    config = pasta / "config"

    if tipo is None:
        print()
        print(v.titulo("DE-PARA MANUAIS DE CÓDIGOS"))
        print(v.fraco("  Traduzem o que veio na base do cliente para o código da plataforma."))
        print(v.fraco("  Formato: id_origem;id_destino — aplicados automaticamente quando o arquivo existe."))
        print()
        for nome, (arquivo, aplicado_em, _ex) in DE_PARA.items():
            caminho = config / arquivo
            if caminho.exists():
                n = max(0, sum(1 for _ in caminho.open(encoding="utf-8")) - 1)
                status = v.success(f"{n} entrada(s)")
            else:
                status = v.fraco("— não criado")
            print(f"  {v.comando(f'{nome:<20}')} {status}")
            print(f"      {v.fraco(arquivo + '  ·  aplica em: ' + aplicado_em)}")
        print()
        print(v.fraco("  Criar um de-para:  ") + v.comando(f"./implantacao depara {pasta.name} <tipo>"))
        print()
        return

    if tipo not in DE_PARA:
        _erro(
            f"Tipo de de-para desconhecido: {tipo!r}.\n"
            f"  Válidos: {', '.join(DE_PARA)}\n"
            f"  Para listar:  ./implantacao depara {pasta.name}"
        )

    arquivo, aplicado_em, exemplo = DE_PARA[tipo]
    caminho = config / arquivo
    print()
    if caminho.exists():
        n = max(0, sum(1 for _ in caminho.open(encoding="utf-8")) - 1)
        print(f"  {v.info(f'Já existe com {n} entrada(s):')} {v.caminho(f'clientes/{pasta.name}/config/{arquivo}')}")
    else:
        config.mkdir(exist_ok=True)
        caminho.write_text("id_origem;id_destino\n", encoding="utf-8")
        print(f"  {v.success('Criado:')} {v.caminho(f'clientes/{pasta.name}/config/{arquivo}')}")
    print()
    print(f"  {v.titulo('Como preencher')} {v.fraco('(uma linha por tradução, separada por ;)')}")
    print(f"    id_origem;id_destino")
    print(f"    {v.comando(exemplo)}")
    print()
    print(f"  {v.fraco('Aplicado em: ' + aplicado_em)}")
    print(f"  {v.fraco('O pipeline aplica automaticamente na próxima execução de')} "
          f"{v.comando(f'./implantacao transformar {pasta.name}')}")
    print()


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


# Ajuda detalhada por comando: ./implantacao ajuda <comando>  ou  <comando> --help
AJUDA_COMANDOS = {
    "novo": {
        "uso": "./implantacao novo <cliente>",
        "descricao": "Cria clientes/<cliente>/ a partir do modelo, com as pastas raw/ "
                     "(arquivos originais do cliente, somente leitura), config/, staging/, "
                     "output/ e relatorios/.",
        "produz": "Estrutura de pastas vazia do cliente.",
        "exemplo": "./implantacao novo acme",
        "apos": "Coloque os Excel/CSV enviados pelo cliente em clientes/<cliente>/raw/ "
                "e rode 'analisar' (determinista) ou 'pilotar' (agente LLM decide).",
    },
    "analisar": {
        "uso": "./implantacao analisar <cliente>",
        "descricao": "Perfila todos os arquivos de raw/ (abas, colunas, tipos, qualidade) e "
                     "gera o mapeamento automático campo a campo entre a base do cliente e "
                     "os templates da plataforma.",
        "produz": "config/diagnostico.json, config/diagnostico_resumo.md e config/mapeamento.json.",
        "exemplo": "./implantacao analisar acme",
        "apos": "Revise config/mapeamento.json, ajuste o que for preciso e adicione "
                "\"travado\": true para impedir sobrescrita. Depois rode 'transformar'.",
    },
    "transformar": {
        "uso": "./implantacao transformar <cliente>",
        "descricao": "Roda as transformações (áreas, colaboradores, indicadores, metas, curva "
                     "de alcance, valores) aplicando os de-para manuais de config/, e valida "
                     "tudo contra os templates: schema, campos obrigatórios, códigos e limites "
                     "da plataforma, integridade referencial e periodicidade.",
        "produz": "staging/ (CSVs intermediários), relatorios/relatorio_validacao.md e, se "
                  "aprovado, output/<data>/*.xlsx prontos para importar na plataforma.",
        "exemplo": "./implantacao transformar acme",
        "apos": "Se bloquear, abra relatorios/relatorio_validacao.md — para texto no lugar "
                "de código, crie o de-para com './implantacao depara <cliente>'.",
    },
    "rodar": {
        "uso": "./implantacao rodar <cliente>",
        "descricao": "Pipeline completo de uma vez: 'analisar' seguido de 'transformar'. "
                     "Use quando o mapeamento automático costuma acertar (ou já está travado).",
        "produz": "Tudo que 'analisar' e 'transformar' produzem.",
        "exemplo": "./implantacao rodar acme",
        "apos": "Confira o status final e o relatório de validação.",
    },
    "depara": {
        "uso": "./implantacao depara <cliente> [tipo]",
        "descricao": "Gerencia os de-para manuais que traduzem o que veio na base do cliente "
                     "para o código da plataforma (formato id_origem;id_destino, um por linha). "
                     "Sem [tipo], lista os suportados e o status de cada um. Com [tipo], cria o "
                     "CSV com o nome e cabeçalho corretos.\n"
                     "  Tipos: pilares, grupos, indicadores, areas, colaboradores, "
                     "metas-individual, metas-compartilhada, metas-projeto.",
        "produz": "clientes/<cliente>/config/dicionario_<tipo>.csv — aplicado automaticamente "
                  "na próxima transformação.",
        "exemplo": "./implantacao depara acme pilares",
        "apos": "Preencha o CSV (ex.: Metas Setoriais;DZ001) e rode 'transformar' de novo.",
    },
    "grupos": {
        "uso": "./implantacao grupos",
        "descricao": "Lista os módulos de carga (núcleo, indicadores, metas, competências), "
                     "suas etapas e dependências. O núcleo (áreas + colaboradores) é a base; "
                     "os demais módulos acrescentam significado sobre ela.",
        "produz": "Apenas listagem em tela.",
        "exemplo": "./implantacao grupos",
        "apos": "Rode um módulo específico com './implantacao grupo <grupo> <cliente>'.",
    },
    "grupo": {
        "uso": "./implantacao grupo <grupo> <cliente>",
        "descricao": "Roda apenas as etapas de um módulo de carga (nucleo, indicadores, metas "
                     "ou competencias). Útil para reprocessar um módulo sem tocar nos outros. "
                     "A ferramenta avisa se o núcleo ainda não estiver pronto, mas não bloqueia "
                     "— a decisão é do consultor.",
        "produz": "Staging e validação das etapas do módulo escolhido.",
        "exemplo": "./implantacao grupo metas acme",
        "apos": "Valide o resultado com 'transformar' ou 'validar'.",
    },
    "diagnosticar": {
        "uso": "./implantacao diagnosticar <cliente>",
        "descricao": "Versão com agente LLM do diagnóstico: percorre raw/, perfila os arquivos "
                     "e escreve o resultado com análise narrativa. Requer MEREO_LLM_API_KEY "
                     "no .env.",
        "produz": "config/diagnostico.json e resumo legível.",
        "exemplo": "./implantacao diagnosticar acme",
        "apos": "Siga para 'mapear'.",
    },
    "mapear": {
        "uso": "./implantacao mapear <cliente>",
        "descricao": "Versão com agente LLM do mapeamento: sugere a correspondência campo a "
                     "campo com nível de confiança e pergunta ao consultor quando está em "
                     "dúvida (pausa HITL). Requer MEREO_LLM_API_KEY no .env.",
        "produz": "config/mapeamento.json.",
        "exemplo": "./implantacao mapear acme",
        "apos": "Se pausar com pergunta, responda com './implantacao responder <cliente> <sessao>'.",
    },
    "inferir": {
        "uso": "./implantacao inferir <cliente>",
        "descricao": "Agente LLM que fabrica entidades que o cliente não enviou, a partir do "
                     "que enviou (hoje: indicadores a partir das metas), com nível de confiança "
                     "por campo. Nada entra no pipeline sem o consultor apontar a fonte no "
                     "mapeamento.",
        "produz": "inferencia/Indicadores_inferidos.csv e relatorios/relatorio_inferencia.md.",
        "exemplo": "./implantacao inferir acme",
        "apos": "Revise o CSV e, se aprovar, aponte-o como fonte no mapeamento.",
    },
    "validar": {
        "uso": "./implantacao validar <cliente>",
        "descricao": "Versão com agente LLM da validação final: mesmos checks do determinista "
                     "+ análise narrativa dos achados. Três estados: aprovado, aprovado com "
                     "ressalvas (pede confirmação humana) e bloqueado.",
        "produz": "relatorios/relatorio_validacao.md e, se aprovado, output/<data>/*.xlsx.",
        "exemplo": "./implantacao validar acme",
        "apos": "Importe as planilhas de output/<data>/ na plataforma.",
    },
    "pilotar": {
        "uso": "./implantacao pilotar <cliente>",
        "descricao": "Agente LLM orquestrador: olha o estado do cliente (o que já existe em "
                     "config/, staging/, output/) e decide sozinho o próximo passo, executando "
                     "as etapas na ordem certa e pausando para perguntas quando necessário.",
        "produz": "O que cada etapa executada produz + relatorios/log_pipeline.json.",
        "exemplo": "./implantacao pilotar acme",
        "apos": "Acompanhe as pausas HITL com 'responder'.",
    },
    "responder": {
        "uso": "./implantacao responder <cliente> <sessao_id>",
        "descricao": "Retoma um agente LLM pausado aguardando resposta humana. Mostra a "
                     "pergunta, o contexto e as opções; a resposta é digitada no terminal "
                     "(Enter duplo para enviar).",
        "produz": "Continuação da sessão de onde parou.",
        "exemplo": "./implantacao responder acme 20260715_142037_a3f1c2",
        "apos": "O id da sessão aparece na mensagem de pausa do agente.",
    },
    "demo": {
        "uso": "./implantacao demo <cliente>",
        "descricao": "Smoke test da infraestrutura LLM: roda o agente de exemplo com uma "
                     "chamada mínima ao gateway. Use após a instalação para confirmar que "
                     "rede, proxy e chave estão OK antes de usar dados reais.",
        "produz": "Uma sessão de teste em sessoes/.",
        "exemplo": "./implantacao novo teste && ./implantacao demo teste",
        "apos": "Se funcionar, pode remover o cliente de teste: rm -rf clientes/teste",
    },
    "ajuda": {
        "uso": "./implantacao ajuda [comando]",
        "descricao": "Sem argumento, mostra a visão geral (comandos por categoria + fluxo "
                     "típico). Com um comando, mostra esta ajuda detalhada. '<comando> --help' "
                     "funciona igual.",
        "produz": "Apenas texto em tela.",
        "exemplo": "./implantacao ajuda depara",
        "apos": "",
    },
}

_CATEGORIAS_AJUDA = [
    ("SETUP", [
        ("novo",         "<cliente>",          "Cria estrutura de pastas para um novo cliente"),
    ]),
    ("PIPELINE DETERMINISTA", [
        ("analisar",     "<cliente>",          "Diagnóstico + mapeamento automático"),
        ("transformar",  "<cliente>",          "Roda transformações + validação"),
        ("rodar",        "<cliente>",          "Pipeline completo (analisar + transformar)"),
    ]),
    ("CORREÇÕES DE CÓDIGO", [
        ("depara",       "<cliente> [tipo]",   "Lista ou cria de-para manuais (texto → código da plataforma)"),
    ]),
    ("CARGAS POR MÓDULO", [
        ("grupos",       "",                   "Lista os módulos e suas dependências"),
        ("grupo",        "<grupo> <cliente>",  "Roda um módulo (nucleo, indicadores, metas, competencias)"),
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
        ("ajuda",        "[comando]",          "Visão geral, ou detalhes de um comando"),
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
    _imprimir_fluxo_tipico()
    _imprimir_lista_comandos()
    print(v.titulo("EXEMPLOS"))
    print(f"  ./implantacao {v.comando('novo acme')}")
    print(f"  ./implantacao {v.comando('pilotar acme')}")
    print(f"  ./implantacao {v.comando('responder acme 20260428_142037_a3f1c2')}")
    print()
    print(v.fraco("Documentação: README.md  ·  ARCHITECTURE.md"))
    print(v.fraco("Provider LLM: configurado via .env (MEREO_LLM_API_KEY)"))
    print()


def _imprimir_fluxo_tipico():
    v = _visual()
    print(v.titulo("FLUXO TÍPICO"))
    passos = [
        ("1.", "novo acme",         "cria a estrutura; deposite os arquivos em clientes/acme/raw/"),
        ("2.", "analisar acme",     "diagnóstico + mapeamento automático (revise config/mapeamento.json)"),
        ("3.", "transformar acme",  "transforma, valida e gera output/<data>/*.xlsx"),
        ("4.", "depara acme <tipo>","se a validação bloquear código, crie o de-para e repita o passo 3"),
    ]
    for num, cmd_ex, desc in passos:
        print(f"  {num} {v.comando(f'./implantacao {cmd_ex:<18}')} {v.fraco(desc)}")
    print(v.fraco("  Alternativa com IA: ./implantacao pilotar acme — o agente decide e executa os passos."))
    print()


def _ajuda_comando(cmd: str):
    v = _visual()
    info = AJUDA_COMANDOS.get(cmd)
    if info is None:
        _ajuda_compacta()
        return
    print()
    print(f"  {v.titulo(cmd)} — {SUBCOMANDOS.get(cmd, ('', 'ajuda do CLI'))[1]}")
    print()
    print(f"  {v.titulo('Uso:')}      {v.comando(info['uso'])}")
    print()
    for linha in info["descricao"].splitlines():
        print(f"  {linha}")
    print()
    print(f"  {v.titulo('Produz:')}   {info['produz']}")
    print(f"  {v.titulo('Exemplo:')}  {v.comando(info['exemplo'])}")
    if info["apos"]:
        print(f"  {v.titulo('Depois:')}   {v.fraco(info['apos'])}")
    print()
    print(v.fraco("  Visão geral de todos os comandos:  ./implantacao ajuda"))
    print()


def _ajuda_compacta():
    v = _visual()
    from nucleo import __version__
    print()
    print(f"  Implantação RHTec/Mereo {v.fraco(f'· v{__version__}')}")
    print()
    print(f"  {v.titulo('Uso:')}  ./implantacao {v.comando('<comando>')} {v.comando('<cliente>')} [args]")
    print()
    _imprimir_fluxo_tipico()
    _imprimir_lista_comandos()
    print(v.fraco("  Detalhes de um comando:  ./implantacao ajuda <comando>   (ou  <comando> --help)"))
    print(v.fraco("  Para a tela completa (banner + descrição), rode  ./implantacao  sem argumentos."))
    print()


def main():
    if len(sys.argv) < 2:
        _welcome()
        sys.exit(0)
    if sys.argv[1] in ("-h", "--help", "ajuda"):
        if len(sys.argv) > 2 and sys.argv[2] in AJUDA_COMANDOS:
            _ajuda_comando(sys.argv[2])
        else:
            _ajuda_compacta()
        sys.exit(0)

    cmd = sys.argv[1]

    # <comando> --help / -h / ajuda → ajuda detalhada do comando
    if cmd in SUBCOMANDOS and len(sys.argv) > 2 and sys.argv[2] in ("-h", "--help", "ajuda"):
        _ajuda_comando(cmd)
        sys.exit(0)

    if cmd not in SUBCOMANDOS:
        v = _visual()
        print(f"\n{v.error(f'Comando desconhecido: ' + repr(cmd))}", file=sys.stderr)
        _ajuda_compacta()
        sys.exit(1)

    # 'grupos' não recebe cliente — lista a estrutura modular e sai.
    if cmd == "grupos":
        listar_grupos_cli()
        return

    # 'grupo' tem layout próprio: <grupo> <cliente>.
    if cmd == "grupo":
        if len(sys.argv) < 4:
            _erro(
                "Uso: ./implantacao grupo <grupo> <cliente>\n"
                "  Para listar os grupos:  ./implantacao grupos"
            )
        nome_grupo = sys.argv[2]
        nome_cli = sys.argv[3]
        pasta_cli = CLIENTES_DIR / nome_cli
        if not pasta_cli.exists():
            _erro(f"Cliente '{nome_cli}' não encontrado.\n  Para criar:  ./implantacao novo {nome_cli}")
        rodar_grupo(pasta_cli, nome_grupo)
        return

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

    if acao == "depara":
        gerenciar_depara(pasta, sys.argv[3] if len(sys.argv) > 3 else None)
        return

    rodar_etapa(pasta, acao)


if __name__ == "__main__":
    main()
