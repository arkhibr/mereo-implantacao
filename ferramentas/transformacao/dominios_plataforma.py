"""
Domínios oficiais da plataforma para campos codificados.
Fonte: planilha de padrões enviada pela Mereo (feedback/mereo/padroes_2026-07-15.xlsx),
em resposta ao relatório entregas/metas_feedback/Perguntas_Feedback_Metas.md.

Formato das equivalências: {"código canônico": ["variação aceita", ...], ...}
— consumido por ferramentas.transformacao.normalizar_dominio.
"""

# Polaridade * (indicadores) — a plataforma só aceita 1 e 2 (não existe código 3/nominal).
EQUIVALENCIAS_POLARIDADE = {
    "1": ["1", "para cima", "maior melhor", "maior_melhor", "maior é melhor", "maior e melhor",
          "crescente", "positivo", "asc"],
    "2": ["2", "para baixo", "menor melhor", "menor_melhor", "menor é melhor", "menor e melhor",
          "decrescente", "negativo", "desc"],
}

# Código de Frequência de Acompanhamento * (indicadores) — não existem códigos 4 e 5.
EQUIVALENCIAS_FREQUENCIA = {
    "1": ["1", "mensal", "mês", "mes"],
    "2": ["2", "bimestral"],
    "3": ["3", "trimestral"],
    "6": ["6", "quadrimestral"],
    "7": ["7", "semestral"],
    "8": ["8", "anual", "ano"],
}

# Código da Unidade de Medida * (indicadores) — lista padrão da plataforma.
EQUIVALENCIAS_UNIDADE_MEDIDA = {
    "UM001": ["percentual", "%", "porcentagem", "percent"],
    "UM002": ["reais", "r$", "real", "moeda"],
    "UM003": ["reais (x 1.000)", "reais mil", "r$ mil", "milhares de reais"],
    "UM004": ["reais (x 1mm)", "r$ mm", "milhões de reais", "milhoes de reais"],
    "UM005": ["dias", "dia"],
    "UM006": ["hora", "horas"],
    "UM007": ["número", "numero", "quantidade", "qtd"],
    "UM008": ["m³", "m3", "metro cúbico", "metro cubico", "metros cúbicos"],
    "UM009": ["ha", "hectare", "hectares"],
    "UM012": ["score"],
    "UM40":  ["unidade", "unidades", "und", "un"],
}

# Tipo de Agregação * (metas).
EQUIVALENCIAS_AGREGACAO = {
    "1": ["1", "repetir pontual", "repetição", "repeticao", "repetir", "pontual"],
    "2": ["2", "soma simples", "soma"],
    "3": ["3", "média simples", "media simples", "média", "media"],
    "4": ["4", "informada pelo usuário", "informada pelo usuario",
          "informado pelo usuário", "informado pelo usuario",
          "definido pelo usuário", "definido pelo usuario"],
    "5": ["5", "automático", "automatico"],
}

# Tipo de Definição do Valor * (metas).
EQUIVALENCIAS_DEFINICAO_VALOR = {
    "1": ["1", "definido pelo usuário", "definido pelo usuario", "manual"],
    "2": ["2", "expressão de cálculo", "expressao de calculo", "expressão de calculo",
          "expressão", "expressao", "fórmula", "formula", "cálculo", "calculo"],
}

_BINARIO = {"0", "1"}

# Regras de validação dos campos codificados por entidade (chaves = colunas dos templates).
# "codigo": comprimento máximo do campo na plataforma; "estrito" marca campos que
#   referenciam cadastros internos (texto com espaço/acento ali é sempre erro).
# "dominio": conjunto fechado de valores aceitos.
# "conhecidos": lista padrão da plataforma — valor fora dela vira aviso, não bloqueio
#   (a lista pode variar por tenant; pergunta 7 do relatório segue em aberto).
REGRAS_CODIGOS = {
    "areas": {
        "Código da Área*":          {"tipo": "codigo", "max": 50},
        "Código da Filial*":        {"tipo": "codigo", "max": 50},
        "Código da Área Superior":  {"tipo": "codigo", "max": 20},
        "Status da Área":           {"tipo": "dominio", "valores": _BINARIO},
        "Login Responsável da Área": {"tipo": "codigo", "max": 50, "estrito": True},
    },
    "colaboradores": {
        "Login*":                          {"tipo": "codigo", "max": 50, "estrito": True},
        "Código do Grupo de Permissões*":  {"tipo": "codigo", "max": 10, "estrito": True},
        "Código da Área*":                 {"tipo": "codigo", "max": 50},
        "Workflow de Ações*":              {"tipo": "dominio", "valores": _BINARIO},
        "Ativo*":                          {"tipo": "dominio", "valores": _BINARIO},
        "Autenticação do Windows":         {"tipo": "dominio", "valores": _BINARIO},
    },
    "indicadores": {
        "Código do Indicador *":           {"tipo": "codigo", "max": 10, "estrito": True},
        "Código da Unidade de Medida *":   {"tipo": "codigo", "max": 10, "estrito": True,
                                            "conhecidos": set(EQUIVALENCIAS_UNIDADE_MEDIDA)},
        "Código da Faixa de Farol *":      {"tipo": "codigo", "max": 10, "estrito": True},
        "Código de Frequência de Acompanhamento *":
            {"tipo": "dominio", "valores": set(EQUIVALENCIAS_FREQUENCIA)},
        "Polaridade *":                    {"tipo": "dominio",
                                            "valores": set(EQUIVALENCIAS_POLARIDADE)},
        "Ativo *":                         {"tipo": "dominio", "valores": _BINARIO},
    },
    "metas_individuais": {
        "Código da Meta *":                 {"tipo": "codigo", "max": 20},
        "Código da Área *":                 {"tipo": "codigo", "max": 50},
        "Login do Responsável pela Meta *": {"tipo": "codigo", "max": 20, "estrito": True},
        "Login do Data-Provider *":         {"tipo": "codigo", "max": 20, "estrito": True},
        "Código do Indicador *":            {"tipo": "codigo", "max": 10, "estrito": True},
        "Código do Pilar Estratégico *":    {"tipo": "codigo", "max": 10, "estrito": True},
        "Código da Curva de Notas":         {"tipo": "codigo", "max": 10, "estrito": True},
        "Tipo de Agregação *":              {"tipo": "dominio",
                                             "valores": set(EQUIVALENCIAS_AGREGACAO)},
        "Tipo de Definição do Valor *":     {"tipo": "dominio",
                                             "valores": set(EQUIVALENCIAS_DEFINICAO_VALOR)},
        " Meta Qualificadora":              {"tipo": "dominio", "valores": _BINARIO},
        "Meta Auditável":                   {"tipo": "dominio", "valores": _BINARIO},
    },
    "metas_compartilhadas": {
        "Código da Meta *":                     {"tipo": "codigo", "max": 20},
        "Código da Área *":                     {"tipo": "codigo", "max": 50},
        "Login do Responsável pela Meta *":     {"tipo": "codigo", "max": 20, "estrito": True},
        "Código da meta a ser compartilhada *": {"tipo": "codigo", "max": 20},
        " Meta Qualificadora":                  {"tipo": "dominio", "valores": _BINARIO},
    },
    "metas_projeto": {
        "Código da Meta *":                 {"tipo": "codigo", "max": 20},
        "Código da Área *":                 {"tipo": "codigo", "max": 50},
        "Login do Responsável pela Meta *": {"tipo": "codigo", "max": 20, "estrito": True},
        "Código do Indicador *":            {"tipo": "codigo", "max": 10, "estrito": True},
        "Código do Pilar Estratégico *":    {"tipo": "codigo", "max": 10, "estrito": True},
        "Código da Curva de Notas":         {"tipo": "codigo", "max": 10, "estrito": True},
        "Meta Auditável":                   {"tipo": "dominio", "valores": _BINARIO},
    },
}
