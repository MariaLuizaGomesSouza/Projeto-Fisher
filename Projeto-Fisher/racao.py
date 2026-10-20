"""
=========================================================
FISHER - MOTOR DE CÁLCULO DE RAÇÃO E BEM-ESTAR
=========================================================

Este arquivo NÃO depende do Flask nem do banco de dados.
Ele recebe números e devolve números, então é fácil de
testar e de ajustar.

Os valores abaixo são REFERÊNCIAS GERAIS de manejo
(faixas de temperatura e taxas de arraçoamento por faixa
de peso). Cada propriedade tem suas particularidades
(qualidade da água, linhagem, tipo de ração, oxigênio).
Ajuste os números da tabela PERFIS conforme a orientação
do seu zootecnista ou técnico de extensão rural.
"""

import unicodedata


# =========================================================
# PERFIS POR ESPÉCIE
# =========================================================
#
# temp_ideal    -> faixa em que o peixe come e cresce melhor
# temp_tolerada -> faixa em que ele sobrevive bem, mas com
#                  apetite/crescimento reduzidos
# faixas        -> (peso_maximo_g, taxa_%_do_peso_vivo_por_dia,
#                   refeicoes_por_dia, proteina_bruta_%)

PERFIS = {

    'tilapia': {
        'nome': 'Tilápia',
        'palavras': ['tilapia', 'oreochromis'],
        'temp_ideal': (26, 30),
        'temp_tolerada': (22, 32),
        'faixas': [
            (10, 8.0, 5, 40),
            (50, 5.0, 4, 36),
            (200, 3.5, 3, 32),
            (500, 2.2, 2, 30),
            (float('inf'), 1.5, 2, 28),
        ],
    },

    'tambaqui': {
        'nome': 'Tambaqui',
        'palavras': ['tambaqui', 'tambacu', 'colossoma'],
        'temp_ideal': (26, 30),
        'temp_tolerada': (24, 32),
        'faixas': [
            (10, 10.0, 5, 42),
            (50, 6.0, 4, 36),
            (200, 4.0, 3, 32),
            (500, 2.5, 3, 28),
            (1000, 1.8, 2, 28),
            (float('inf'), 1.2, 2, 26),
        ],
    },

    'pacu': {
        'nome': 'Pacu',
        'palavras': ['pacu', 'piaractus'],
        'temp_ideal': (25, 29),
        'temp_tolerada': (22, 32),
        'faixas': [
            (10, 8.0, 5, 40),
            (50, 5.0, 4, 36),
            (200, 3.5, 3, 32),
            (500, 2.5, 3, 28),
            (1000, 1.8, 2, 28),
            (float('inf'), 1.2, 2, 26),
        ],
    },

    'pintado': {
        'nome': 'Pintado / Surubim',
        'palavras': ['pintado', 'surubim', 'pseudoplatystoma'],
        'temp_ideal': (25, 29),
        'temp_tolerada': (22, 32),
        'faixas': [
            (10, 10.0, 5, 50),
            (50, 6.0, 4, 45),
            (200, 4.0, 3, 42),
            (500, 2.5, 3, 40),
            (float('inf'), 1.5, 2, 38),
        ],
    },

    'carpa': {
        'nome': 'Carpa',
        'palavras': ['carpa', 'cyprinus'],
        'temp_ideal': (22, 28),
        'temp_tolerada': (16, 32),
        'faixas': [
            (10, 8.0, 4, 38),
            (50, 5.0, 3, 34),
            (200, 3.5, 3, 30),
            (500, 2.5, 2, 28),
            (float('inf'), 1.5, 2, 28),
        ],
    },

    # Usado quando o nome da espécie não é reconhecido
    'padrao': {
        'nome': 'Espécie personalizada',
        'palavras': [],
        'temp_ideal': (24, 30),
        'temp_tolerada': (20, 32),
        'faixas': [
            (10, 8.0, 4, 36),
            (50, 5.0, 3, 34),
            (200, 3.5, 3, 32),
            (500, 2.5, 2, 30),
            (float('inf'), 1.5, 2, 28),
        ],
    },
}


# Pesos de cada critério na nota final de bem-estar (somam 100)

PESO_TEMPERATURA = 40
PESO_ALIMENTACAO = 35
PESO_MONITORAMENTO = 25

# Horário em que os tratos costumam acontecer (para avaliar o "hoje")

INICIO_TRATO = 7
FIM_TRATO = 17


# =========================================================
# IDENTIFICAÇÃO DA ESPÉCIE
# =========================================================

def normalizar(texto):
    """Minúsculo e sem acentos: 'Tilápia' -> 'tilapia'."""

    texto = unicodedata.normalize('NFD', texto or '')

    texto = ''.join(
        c for c in texto
        if unicodedata.category(c) != 'Mn'
    )

    return texto.lower().strip()


def perfil_da_especie(especie):
    """Devolve (chave, perfil) da espécie informada."""

    nome = normalizar(especie)

    for chave, perfil in PERFIS.items():

        for palavra in perfil['palavras']:

            if palavra in nome:

                return chave, perfil

    return 'padrao', PERFIS['padrao']


def perfis_para_formulario():
    """Versão enxuta dos perfis para o JavaScript dos formulários."""

    saida = {}

    for chave, p in PERFIS.items():

        saida[chave] = {
            'nome': p['nome'],
            'palavras': p['palavras'],
            'temp_ideal': list(p['temp_ideal']),
            'temp_tolerada': list(p['temp_tolerada']),
            'taxa_min': min(f[1] for f in p['faixas']),
            'taxa_max': max(f[1] for f in p['faixas']),
            'proteina_min': min(f[3] for f in p['faixas']),
            'proteina_max': max(f[3] for f in p['faixas']),
        }

    return saida


# =========================================================
# TEMPERATURA
# =========================================================

def fator_temperatura(temp, perfil):
    """
    Quanto do apetite normal o peixe tem nessa temperatura.

    1.0  -> dentro da faixa ideal (ração 100%)
    0.7  -> na borda da faixa tolerada
    0.0  -> longe demais da tolerância (suspender o trato)

    Acima da tolerância o fator cai mais rápido, porque
    água quente tem pouco oxigênio dissolvido.
    """

    ideal_min, ideal_max = perfil['temp_ideal']
    tol_min, tol_max = perfil['temp_tolerada']

    if ideal_min <= temp <= ideal_max:

        return 1.0

    if temp < ideal_min:

        if temp >= tol_min:

            return 1 - 0.3 * (ideal_min - temp) / (ideal_min - tol_min)

        return max(0.0, 0.7 - 0.7 * (tol_min - temp) / 4)

    if temp <= tol_max:

        return 1 - 0.3 * (temp - ideal_max) / (tol_max - ideal_max)

    return max(0.0, 0.7 - 0.7 * (temp - tol_max) / 3)


def situacao_temperatura(temp, perfil):
    """Devolve (chave, rótulo, mensagem) para a temperatura."""

    ideal_min, ideal_max = perfil['temp_ideal']
    fator = fator_temperatura(temp, perfil)

    if fator >= 1.0:

        return (
            'otimo',
            'Ideal',
            f'{temp:.1f}°C está dentro da faixa ideal '
            f'({ideal_min}–{ideal_max}°C).'
        )

    if temp < ideal_min:

        if fator > 0:

            return (
                'atencao' if fator >= 0.7 else 'critico',
                'Água fria',
                f'{temp:.1f}°C: o metabolismo está lento. '
                f'A ração foi reduzida para {round(fator * 100)}%.'
            )

        return (
            'critico',
            'Muito fria',
            f'{temp:.1f}°C: frio demais para alimentar. '
            f'Suspenda o trato até a água aquecer.'
        )

    if fator > 0:

        return (
            'atencao' if fator >= 0.7 else 'critico',
            'Água quente',
            f'{temp:.1f}°C: o oxigênio dissolvido cai com o calor. '
            f'A ração foi reduzida para {round(fator * 100)}% '
            f'e vale reforçar a aeração.'
        )

    return (
        'critico',
        'Muito quente',
        f'{temp:.1f}°C: risco alto de falta de oxigênio. '
        f'Suspenda o trato e reforce a aeração.'
    )


# =========================================================
# CÁLCULO DA RAÇÃO
# =========================================================

def faixa_de_peso(perfil, peso_g):
    """Escolhe a linha da tabela de acordo com o peso médio."""

    for faixa in perfil['faixas']:

        if peso_g <= faixa[0]:

            return faixa

    return perfil['faixas'][-1]


def calcular_racao(especie, quantidade, peso_g, temperatura):
    """
    Calcula a ração do dia.

    Fórmula:
        biomassa (kg) = peso médio (g) x nº de peixes / 1000
        taxa ajustada = taxa da faixa de peso x fator da temperatura
        ração (kg)    = biomassa x taxa ajustada / 100
    """

    chave, perfil = perfil_da_especie(especie)

    limite, taxa_base, refeicoes, proteina = faixa_de_peso(
        perfil,
        peso_g
    )

    fator = fator_temperatura(temperatura, perfil)

    biomassa_kg = peso_g * quantidade / 1000

    taxa_ajustada = taxa_base * fator

    total_kg = biomassa_kg * taxa_ajustada / 100

    if fator <= 0:

        refeicoes = 0

    por_refeicao = total_kg / refeicoes if refeicoes else 0

    chave_temp, rotulo_temp, msg_temp = situacao_temperatura(
        temperatura,
        perfil
    )

    return {
        'perfil_chave': chave,
        'perfil_nome': perfil['nome'],
        'biomassa_kg': round(biomassa_kg, 2),
        'taxa_base': taxa_base,
        'fator_temperatura': round(fator, 2),
        'taxa_ajustada': round(taxa_ajustada, 2),
        'total_kg': round(total_kg, 2),
        'refeicoes': refeicoes,
        'por_refeicao_kg': round(por_refeicao, 3),
        'proteina': proteina,
        'temp_ideal': perfil['temp_ideal'],
        'temp_chave': chave_temp,
        'temp_rotulo': rotulo_temp,
        'temp_mensagem': msg_temp,
    }


# =========================================================
# NOTAS (0 a 100)
# =========================================================

def nota_cobertura(cobertura):
    """
    cobertura = ração fornecida / ração recomendada.

    Entre 90% e 110% é nota máxima. Abaixo disso o peixe
    passa fome; acima, sobra ração e a água piora.
    """

    if cobertura < 0.9:

        return 100 * cobertura / 0.9

    if cobertura <= 1.1:

        return 100.0

    return max(20.0, 100 - (cobertura - 1.1) * 150)


def nota_monitoramento(dias):
    """Quanto mais antiga a última biometria, menor a nota."""

    if dias <= 14:

        return 100.0

    if dias <= 30:

        return 100 - (dias - 14) * (40 / 16)

    if dias <= 60:

        return 60 - (dias - 30) * (40 / 30)

    return 20.0


def nivel_do_score(score):
    """Devolve (chave, rótulo) usados para cor e texto."""

    if score is None:

        return 'vazio', 'Sem dados'

    if score >= 85:

        return 'otimo', 'Ótimo'

    if score >= 70:

        return 'bom', 'Bom'

    if score >= 50:

        return 'atencao', 'Atenção'

    return 'critico', 'Crítico'


def fracao_do_dia(agora):
    """Quanto do 'expediente de trato' (7h-17h) já passou."""

    hora = agora.hour + agora.minute / 60

    return min(1.0, max(0.0, (hora - INICIO_TRATO) / (FIM_TRATO - INICIO_TRATO)))


# =========================================================
# AVALIAÇÃO COMPLETA DE UM TANQUE
# =========================================================

def avaliar_tanque(
    especie,
    quantidade,
    ultima_bio,
    tratos_por_dia,
    primeiro_trato,
    agora
):
    """
    ultima_bio      -> (peso_g, temperatura, datetime) ou None
    tratos_por_dia  -> {date: kg_fornecidos}
    primeiro_trato  -> date do primeiro trato registrado ou None
    """

    hoje = agora.date()

    resultado = {
        'tem_biometria': ultima_bio is not None,
        'calc': None,
        'score': None,
        'nivel': 'vazio',
        'rotulo': 'Sem dados',
        'temperatura': None,
        'alimentacao': None,
        'monitoramento': None,
        'alertas': [],
    }

    # Sem biometria não dá para calcular nada

    if ultima_bio is None:

        resultado['alertas'].append((
            'info',
            'Ainda sem biometria. Registre a primeira pesagem '
            'para liberar o cálculo de ração.'
        ))

        return resultado

    peso, temp, data_bio = ultima_bio

    calc = calcular_racao(especie, quantidade, peso, temp)

    resultado['calc'] = calc

    recomendado = calc['total_kg']

    # ---------- TEMPERATURA ----------

    nota_temp = round(calc['fator_temperatura'] * 100)

    resultado['temperatura'] = {
        'valor': temp,
        'nota': nota_temp,
        'chave': calc['temp_chave'],
        'rotulo': calc['temp_rotulo'],
        'mensagem': calc['temp_mensagem'],
        'ideal': calc['temp_ideal'],
    }

    if calc['temp_chave'] in ('atencao', 'critico'):

        resultado['alertas'].append((
            calc['temp_chave'],
            calc['temp_mensagem']
        ))

    # ---------- MONITORAMENTO ----------

    dias_bio = max(0, (hoje - data_bio.date()).days)

    nota_mon = round(nota_monitoramento(dias_bio))

    resultado['monitoramento'] = {
        'dias': dias_bio,
        'nota': nota_mon,
    }

    if dias_bio > 30:

        resultado['alertas'].append((
            'atencao',
            f'A última biometria tem {dias_bio} dias. '
            f'Pese uma amostra para manter a ração precisa.'
        ))

    # ---------- ALIMENTAÇÃO ----------

    fornecido_hoje = tratos_por_dia.get(hoje, 0.0)

    cobertura_hoje = (
        fornecido_hoje / recomendado
        if recomendado > 0
        else 0
    )

    coberturas = []

    if primeiro_trato is not None and recomendado > 0:

        fracao = fracao_do_dia(agora)

        # Hoje (proporcional ao horário) e os dois dias anteriores

        for deslocamento in (0, 1, 2):

            dia = hoje.fromordinal(hoje.toordinal() - deslocamento)

            if dia < primeiro_trato:

                continue

            fornecido = tratos_por_dia.get(dia, 0.0)

            if deslocamento == 0:

                if fracao < 0.1 and fornecido == 0:

                    continue

                esperado = recomendado * max(fracao, 0.1)

                if fornecido > recomendado * 1.1:

                    cob = fornecido / recomendado

                else:

                    cob = min(1.0, fornecido / esperado)

            else:

                cob = fornecido / recomendado

            coberturas.append(cob)

    sem_registros = primeiro_trato is None

    if coberturas:

        nota_ali = round(
            sum(nota_cobertura(c) for c in coberturas) / len(coberturas)
        )

    else:

        nota_ali = 50

    resultado['alimentacao'] = {
        'nota': nota_ali,
        'recomendado_kg': recomendado,
        'fornecido_hoje_kg': round(fornecido_hoje, 2),
        'cobertura_hoje': round(cobertura_hoje, 2),
        'sem_registros': sem_registros,
        'falta_kg': round(max(0.0, recomendado - fornecido_hoje), 2),
    }

    if sem_registros:

        resultado['alertas'].append((
            'info',
            'Nenhum trato registrado ainda. Registre a ração '
            'fornecida para acompanhar o bem-estar.'
        ))

    elif cobertura_hoje > 1.15:

        resultado['alertas'].append((
            'atencao',
            f'Hoje já foi fornecido {round(cobertura_hoje * 100)}% '
            f'da ração recomendada. Excesso piora a qualidade da água.'
        ))

    elif agora.hour >= 12 and fornecido_hoje == 0 and recomendado > 0:

        resultado['alertas'].append((
            'atencao',
            f'Nenhum trato registrado hoje. A meta do dia '
            f'é {recomendado:.2f} kg.'
        ))

    # ---------- NOTA FINAL ----------

    media = (
        nota_temp * PESO_TEMPERATURA
        + nota_ali * PESO_ALIMENTACAO
        + nota_mon * PESO_MONITORAMENTO
    ) / 100

    # 70% é a média ponderada e 30% é o ponto mais fraco.
    # Assim um problema sério (ex.: peixe com fome) não fica
    # escondido atrás de outros critérios que estão ótimos.

    mais_fraco = min(nota_temp, nota_ali, nota_mon)

    score = round(media * 0.7 + mais_fraco * 0.3)

    nivel, rotulo = nivel_do_score(score)

    resultado['score'] = score
    resultado['nivel'] = nivel
    resultado['rotulo'] = rotulo

    return resultado


# =========================================================
# ESTOQUE DE RAÇÃO
# =========================================================

def avaliar_estoque(kg_atual, capacidade_kg, consumo_diario_kg):
    """Nível do depósito e quantos dias a ração ainda dura."""

    percentual = (
        min(100, round(kg_atual / capacidade_kg * 100))
        if capacidade_kg > 0
        else 0
    )

    dias = (
        kg_atual / consumo_diario_kg
        if consumo_diario_kg > 0
        else None
    )

    if kg_atual <= 0:

        nivel = 'critico'

    elif dias is None:

        # Sem consumo estimado: avalia só pela porcentagem do depósito

        if percentual >= 30:

            nivel = 'bom'

        elif percentual >= 10:

            nivel = 'atencao'

        else:

            nivel = 'critico'

    elif dias >= 7:

        nivel = 'otimo'

    elif dias >= 3:

        nivel = 'atencao'

    else:

        nivel = 'critico'

    return {
        'kg': round(kg_atual, 1),
        'capacidade': round(capacidade_kg, 1),
        'percentual': percentual,
        'dias': None if dias is None else round(dias, 1),
        'nivel': nivel,
        'consumo_diario': round(consumo_diario_kg, 2),
    }
