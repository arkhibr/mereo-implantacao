"""
Heurísticas determinísticas para inferir indicadores a partir de metas.

Funções puras (sem I/O, sem dependência de pandas) para serem testáveis
isoladas e expostas como tool pelo agente de inferência.
"""
import re
from dataclasses import dataclass, field
from typing import Iterable


# Campos exatos do template Import_Indicadores (KPI).csv (latin-1, separador ';').
# A ordem importa: o CSV inferido segue esta sequência.
COLUNAS_TEMPLATE = [
    "Código do Indicador *",
    "Descrição do Indicador *",
    "Código da Unidade de Medida *",
    "Código da Faixa de Farol *",
    "Código de Frequência de Acompanhamento *",
    "Polaridade *",
    "Memória de Cálculo",
    "Ativo *",
    "Personalizar parâmetros de alerta via e-mail para este indicador",
    "Frequência de recorrência de e-mail",
    "Envio de e-mail de data limite a partir do dia",
    "Envio de e-mail de alerta a partir do dia",
    "Dias de atraso para notificação dos Stakeholders",
    "Stakeholders a serem notificados",
]

COLUNAS_AUXILIARES = ["_origem", "_confianca", "_derivado_de", "_observacao"]

PLACEHOLDER = "<DEFINIR>"

# Polaridade — palavras-chave em PT-BR. Match parcial em texto lowercase.
PALAVRAS_MENOR = [
    "despesa", "custo", "atraso", "erro", "redução", "queda", "perda",
    "absenteísmo", "absenteismo", "rotatividade", "turnover", "desperdício",
    "desperdicio", "retrabalho", "defeito", "reclamação", "reclamacao",
    "tempo médio", "tempo medio", "lead time", "tma",
]

PALAVRAS_MAIOR = [
    "venda", "vendas", "receita", "lucro", "crescimento", "produtividade",
    "satisfação", "satisfacao", "engajamento", "alcance", "atingimento",
    "conversão", "conversao", "ebitda", "margem", "rentabilidade",
    "nps", "csat",
]


# Unidade de medida — sinais de texto → código padrão da plataforma.
# Ordem importa: percentual vence (meta "atingir 95% de R$ X" costuma medir o percentual).
SINAIS_UNIDADE = [
    (r"%|\bpercentual\b|\bporcentagem\b", "UM001"),
    (r"(r\$|\breais\b|\breal\b).{0,30}?(\bmilh[õo]es\b|\bmm\b)|(\bmilh[õo]es\b|\bmm\b).{0,10}?(r\$|\breais\b)", "UM004"),
    (r"(r\$|\breais\b).{0,30}?\bmil\b|\bmil\b.{0,10}?(r\$|\breais\b)", "UM003"),
    (r"r\$|\breais\b", "UM002"),
    (r"\bdias?\b", "UM005"),
    (r"\bhoras?\b", "UM006"),
    (r"\bm³\b|\bm3\b|metros? c[úu]bicos?", "UM008"),
    (r"\bhectares?\b", "UM009"),
    (r"\bscore\b", "UM012"),
]


def inferir_unidade(descricao: str) -> str:
    """
    Devolve o código da unidade de medida inferido do texto, ou None quando não
    há sinal confiável (o chamador decide o fallback).
    """
    if not descricao:
        return None
    texto = str(descricao).lower()
    for padrao, codigo in SINAIS_UNIDADE:
        if re.search(padrao, texto):
            return codigo
    return None


@dataclass
class CandidatoIndicador:
    """Indicador único extraído das metas, com rastreabilidade."""
    codigo: str
    descricao_canonica: str
    descricoes_observadas: list = field(default_factory=list)
    linhas_origem: list = field(default_factory=list)


def normalizar_descricao(descricao: str) -> str:
    """
    Limpa sufixos temporais comuns ('(2024+)', '(Entregas 2024+)', '- 2025') e
    espaços extras. Mantém o resto intacto — não tenta padronizar capitalização.
    """
    if descricao is None:
        return ""
    texto = str(descricao).strip()
    # Remove parênteses contendo ano (4 dígitos começando com 19xx ou 20xx).
    texto = re.sub(r"\s*\([^)]*\b(19|20)\d{2}\b[^)]*\)\s*", " ", texto)
    # Remove sufixo "- ANO" no final.
    texto = re.sub(r"\s*[-–]\s*\b(19|20)\d{2}\b\s*$", "", texto)
    # Colapsa espaços.
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def inferir_polaridade(descricao: str) -> tuple:
    """
    Devolve (polaridade, confianca):
      - 'Menor é Melhor' / 'media'  se bater em PALAVRAS_MENOR
      - 'Maior é Melhor' / 'media'  se bater em PALAVRAS_MAIOR
      - 'Maior é Melhor' / 'baixa'  default quando sem sinal
    Match parcial; primeira lista a bater define o resultado.
    """
    if not descricao:
        return ("Maior é Melhor", "baixa")
    texto = descricao.lower()
    for palavra in PALAVRAS_MENOR:
        if palavra in texto:
            return ("Menor é Melhor", "media")
    for palavra in PALAVRAS_MAIOR:
        if palavra in texto:
            return ("Maior é Melhor", "media")
    return ("Maior é Melhor", "baixa")


def extrair_candidatos(metas: Iterable[dict], campo_codigo: str, campo_descricao: str) -> list:
    """
    Recebe um iterável de dicts (uma meta por dict, chaves = nomes de coluna do
    cliente) e devolve lista de CandidatoIndicador, agrupada por `campo_codigo`.

    A descrição canônica de cada grupo é a `normalizar_descricao` da descrição
    mais frequente entre as metas com o mesmo código. Empate de frequência:
    fica a primeira observada.
    """
    grupos: dict[str, dict] = {}

    for idx, meta in enumerate(metas, start=1):
        codigo = meta.get(campo_codigo)
        if codigo is None:
            continue
        codigo = str(codigo).strip()
        if not codigo:
            continue

        descricao_raw = meta.get(campo_descricao, "") or ""
        descricao_raw = str(descricao_raw).strip()

        if codigo not in grupos:
            grupos[codigo] = {
                "descricoes": [],
                "linhas": [],
            }
        grupos[codigo]["descricoes"].append(descricao_raw)
        grupos[codigo]["linhas"].append(idx)

    candidatos = []
    for codigo, info in grupos.items():
        # Descrição canônica: a mais frequente entre as observadas, normalizada.
        contagem: dict[str, int] = {}
        for d in info["descricoes"]:
            contagem[d] = contagem.get(d, 0) + 1
        descricao_mais_frequente = max(contagem.items(), key=lambda x: x[1])[0]
        descricao_canonica = normalizar_descricao(descricao_mais_frequente)

        candidatos.append(CandidatoIndicador(
            codigo=codigo,
            descricao_canonica=descricao_canonica or descricao_mais_frequente or codigo,
            descricoes_observadas=sorted(set(info["descricoes"])),
            linhas_origem=info["linhas"],
        ))

    candidatos.sort(key=lambda c: c.codigo)
    return candidatos


def montar_linha(candidato: CandidatoIndicador, fonte_arquivo: str, fonte_aba: str) -> dict:
    """
    Constrói a linha do CSV inferido (14 colunas do template + 4 auxiliares).
    Confiança agregada considera apenas os campos efetivamente inferidos —
    placeholders <DEFINIR> são pendência do consultor, não falha de inferência.
    """
    polaridade, conf_polaridade = inferir_polaridade(candidato.descricao_canonica)

    descricao_diferentes = len(set(candidato.descricoes_observadas)) > 1

    # Confiança da identidade: alta se descrição única, media se variantes.
    conf_identidade = "alta" if not descricao_diferentes else "media"

    # Agregada: pior caso entre identidade (alta/media) e polaridade (media/baixa).
    ordem = {"alta": 3, "media": 2, "baixa": 1, "nenhuma": 0}
    pior = min(ordem[conf_identidade], ordem[conf_polaridade])
    confianca = next(k for k, v in ordem.items() if v == pior)

    linhas_str = ",".join(str(n) for n in candidato.linhas_origem[:5])
    if len(candidato.linhas_origem) > 5:
        linhas_str += f",... ({len(candidato.linhas_origem)} no total)"
    derivado_de = f"{fonte_arquivo}:{fonte_aba}:linhas {linhas_str}"

    observacoes = []
    if descricao_diferentes:
        variantes = "; ".join(candidato.descricoes_observadas[:3])
        observacoes.append(f"variações de descrição agrupadas pelo código: {variantes}")

    linha = {
        "Código do Indicador *": candidato.codigo,
        "Descrição do Indicador *": candidato.descricao_canonica,
        "Código da Unidade de Medida *": PLACEHOLDER,
        "Código da Faixa de Farol *": PLACEHOLDER,
        "Código de Frequência de Acompanhamento *": PLACEHOLDER,
        "Polaridade *": polaridade,
        "Memória de Cálculo": "",
        "Ativo *": "Sim",
        "Personalizar parâmetros de alerta via e-mail para este indicador": "",
        "Frequência de recorrência de e-mail": "",
        "Envio de e-mail de data limite a partir do dia": "",
        "Envio de e-mail de alerta a partir do dia": "",
        "Dias de atraso para notificação dos Stakeholders": "",
        "Stakeholders a serem notificados": "",
        "_origem": "inferido",
        "_confianca": confianca,
        "_derivado_de": derivado_de,
        "_observacao": " | ".join(observacoes),
    }
    return linha
