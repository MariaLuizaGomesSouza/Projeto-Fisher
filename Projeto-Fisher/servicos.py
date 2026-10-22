"""Regras e consultas do sistema (usadas pelo painel e pelas rotas)."""

from collections import defaultdict
from datetime import datetime, time, timedelta

from flask import flash, redirect, request, url_for
from flask_login import current_user
from sqlalchemy import func

import racao
from extensions import db
from models import (
    Atividade, Biometria, EstoqueRacao, RegistroTrato, Tanque
)
from utils import agora, numero

ICONES_ATIVIDADE = {
    'tanque': 'fa-water',
    'biometria': 'fa-scale-balanced',
    'trato': 'fa-utensils',
    'estoque': 'fa-boxes-stacked',
    'mortalidade': 'fa-heart-crack',
}

ROTULOS_ATIVIDADE = {
    'tanque': 'Tanques',
    'biometria': 'Biometrias',
    'trato': 'Tratos',
    'estoque': 'Estoque',
    'mortalidade': 'Mortalidade',
}

DIAS_SEMANA = ['seg', 'ter', 'qua', 'qui', 'sex', 'sáb', 'dom']


def tanques_visiveis():
    """Admin vê todos os tanques; produtor vê só os seus."""

    consulta = Tanque.query

    if not current_user.is_admin:

        consulta = consulta.filter_by(user_id=current_user.id)

    return consulta.order_by(Tanque.nome).all()


def obter_tanque(tanque_id, acao='acessar'):
    """Busca o tanque e confere a permissão. Devolve None se negado."""

    tanque = db.get_or_404(Tanque, tanque_id)

    if not current_user.is_admin and tanque.user_id != current_user.id:

        flash(f'Você não tem permissão para {acao} este tanque.', 'erro')

        return None

    return tanque


def voltar_para(endpoint, **parametros):
    """Volta para a página de origem (campo 'next') ou para o padrão."""

    destino = request.form.get('next', '')

    if destino.startswith('/') and not destino.startswith('//'):

        return redirect(destino)

    return redirect(url_for(endpoint, **parametros))


def registrar_atividade(tipo, descricao, tanque_id=None):

    db.session.add(Atividade(
        user_id=current_user.id,
        autor=current_user.nome,
        tipo=tipo,
        descricao=descricao,
        tanque_id=tanque_id,
        criado_em=agora()
    ))


def obter_estoque():
    """Estoque do usuário logado (cria se ainda não existir)."""

    estoque = EstoqueRacao.query.filter_by(
        user_id=current_user.id
    ).first()

    if estoque is None:

        estoque = EstoqueRacao(
            user_id=current_user.id,
            quantidade_kg=0,
            capacidade_kg=500
        )

        db.session.add(estoque)

        db.session.commit()

    return estoque


def ultima_biometria(tanque_id):

    return Biometria.query.filter_by(
        tanque_id=tanque_id
    ).order_by(
        Biometria.data.desc(),
        Biometria.id.desc()
    ).first()


def avaliar(tanque, referencia=None):
    """Roda a avaliação completa (ração + bem-estar) de um tanque."""

    referencia = referencia or agora()

    bio = ultima_biometria(tanque.id)

    inicio = datetime.combine(
        referencia.date() - timedelta(days=2),
        time.min
    )

    tratos = RegistroTrato.query.filter(
        RegistroTrato.tanque_id == tanque.id,
        RegistroTrato.data >= inicio
    ).all()

    por_dia = defaultdict(float)

    for trato in tratos:

        por_dia[trato.data.date()] += trato.quantidade_kg

    primeiro = db.session.query(
        func.min(RegistroTrato.data)
    ).filter(
        RegistroTrato.tanque_id == tanque.id
    ).scalar()

    return racao.avaliar_tanque(
        especie=tanque.especie,
        quantidade=tanque.quantidade,
        ultima_bio=(
            (bio.peso_medio_gramas, bio.temperatura_agua, bio.data)
            if bio else None
        ),
        tratos_por_dia=por_dia,
        primeiro_trato=primeiro.date() if primeiro else None,
        agora=referencia
    )


def consumo_semana(tanque_ids, recomendado_kg):
    """Ração fornecida x recomendada nos últimos 7 dias."""

    hoje = agora().date()

    inicio = datetime.combine(hoje - timedelta(days=6), time.min)

    por_dia = defaultdict(float)

    if tanque_ids:

        tratos = RegistroTrato.query.filter(
            RegistroTrato.tanque_id.in_(tanque_ids),
            RegistroTrato.data >= inicio
        ).all()

        for trato in tratos:

            por_dia[trato.data.date()] += trato.quantidade_kg

    dias = []

    for i in range(6, -1, -1):

        dia = hoje - timedelta(days=i)

        dias.append({
            'rotulo': DIAS_SEMANA[dia.weekday()],
            'data': dia.strftime('%d/%m'),
            'dado': round(por_dia.get(dia, 0.0), 2),
            'hoje': i == 0,
        })

    topo = max(
        [recomendado_kg] + [d['dado'] for d in dias] + [0.01]
    )

    for d in dias:

        d['altura'] = round(d['dado'] / topo * 100)

    return {
        'dias': dias,
        'meta_altura': round(recomendado_kg / topo * 100),
        'meta_kg': round(recomendado_kg, 2),
        'total_dado': round(sum(d['dado'] for d in dias), 2),
    }


def listar_atividades(limite=10, tipo=None):
    """Últimas atividades (admin vê tudo, produtor vê as suas)."""

    consulta = Atividade.query

    if not current_user.is_admin:

        consulta = consulta.filter_by(user_id=current_user.id)

    if tipo in ICONES_ATIVIDADE:

        consulta = consulta.filter_by(tipo=tipo)

    itens = consulta.order_by(
        Atividade.criado_em.desc(),
        Atividade.id.desc()
    ).limit(limite).all()

    ids_existentes = {t.id for t in tanques_visiveis()}

    for item in itens:

        item.link_ok = item.tanque_id in ids_existentes

    return itens


def montar_painel():
    """Reúne tudo que o painel central precisa."""

    referencia = agora()

    tanques = tanques_visiveis()

    itens = [
        {'tanque': t, 'av': avaliar(t, referencia)}
        for t in tanques
    ]

    com_nota = [i for i in itens if i['av']['score'] is not None]

    # ----- bem-estar geral -----

    if com_nota:

        geral = round(
            sum(i['av']['score'] for i in com_nota) / len(com_nota)
        )

    else:

        geral = None

    nivel_geral, rotulo_geral = racao.nivel_do_score(geral)

    # ----- totais -----

    total_peixes = sum(t.quantidade for t in tanques)

    biomassa = sum(
        i['av']['calc']['biomassa_kg']
        for i in itens if i['av']['calc']
    )

    racao_recomendada = sum(
        i['av']['calc']['total_kg']
        for i in itens if i['av']['calc']
    )

    racao_fornecida = sum(
        i['av']['alimentacao']['fornecido_hoje_kg']
        for i in itens if i['av']['alimentacao']
    )

    # ----- temperatura -----

    com_temp = [i for i in itens if i['av']['temperatura']]

    if com_temp:

        temps = [i['av']['temperatura']['valor'] for i in com_temp]

        ideais = sum(
            1 for i in com_temp
            if i['av']['temperatura']['chave'] == 'otimo'
        )

        nota_temp = round(
            sum(i['av']['temperatura']['nota'] for i in com_temp)
            / len(com_temp)
        )

        temperatura = {
            'media': round(sum(temps) / len(temps), 1),
            'minima': min(temps),
            'maxima': max(temps),
            'ideais': ideais,
            'total': len(com_temp),
            'nota': nota_temp,
            'nivel': racao.nivel_do_score(nota_temp)[0],
        }

    else:

        temperatura = None

    # ----- estoque -----

    estoque_db = obter_estoque()

    estoque = racao.avaliar_estoque(
        estoque_db.quantidade_kg,
        estoque_db.capacidade_kg,
        racao_recomendada
    )

    # ----- alertas -----

    alertas = []

    for i in itens:

        for nivel, mensagem in i['av']['alertas']:

            alertas.append({
                'nivel': nivel,
                'texto': mensagem,
                'tanque': i['tanque'],
            })

    if estoque['kg'] <= 0:

        alertas.append({
            'nivel': 'critico',
            'texto': 'O estoque de ração está zerado.',
            'tanque': None,
        })

    elif estoque['dias'] is not None and estoque['dias'] < 7:

        alertas.append({
            'nivel': 'critico' if estoque['dias'] < 3 else 'atencao',
            'texto': (
                f"A ração em estoque dura cerca de "
                f"{estoque['dias']:.0f} dia(s) no ritmo atual."
            ),
            'tanque': None,
        })

    ordem = {'critico': 0, 'atencao': 1, 'info': 2}

    alertas.sort(key=lambda a: ordem.get(a['nivel'], 3))

    # ----- tanques em cada situação -----

    situacoes = defaultdict(int)

    for i in itens:

        situacoes[i['av']['nivel']] += 1

    return {
        'itens': itens,
        'geral': geral,
        'nivel_geral': nivel_geral,
        'rotulo_geral': rotulo_geral,
        'situacoes': dict(situacoes),
        'total_tanques': len(tanques),
        'total_peixes': total_peixes,
        'biomassa': round(biomassa, 1),
        'racao_recomendada': round(racao_recomendada, 2),
        'racao_fornecida': round(racao_fornecida, 2),
        'racao_pct': (
            round(racao_fornecida / racao_recomendada * 100)
            if racao_recomendada > 0 else 0
        ),
        'temperatura': temperatura,
        'estoque': estoque,
        'alertas': alertas[:6],
        'total_alertas': len(alertas),
        'semana': consumo_semana(
            [t.id for t in tanques],
            racao_recomendada
        ),
    }


def ler_formulario_tanque(tanque_id=None):
    """Valida o formulário de cadastro/edição. Devolve (dados, erro)."""

    nome = request.form.get('nome', '').strip()

    especie = request.form.get('especie', '').strip()

    if not nome or not especie:

        return None, 'Preencha o nome e a espécie do tanque.'

    quantidade = numero(request.form.get('quantidade'), minimo=1)

    if quantidade is None or quantidade != int(quantidade):

        return None, 'A quantidade de peixes deve ser um número inteiro maior que zero.'

    volume = None

    texto_volume = request.form.get('volume_m3', '').strip()

    if texto_volume:

        volume = numero(texto_volume, minimo=0.01)

        if volume is None:

            return None, 'O volume do tanque deve ser um número maior que zero.'

    duplicado = Tanque.query.filter(
        func.lower(Tanque.nome) == nome.lower(),
        Tanque.user_id == current_user.id
    )

    if tanque_id:

        duplicado = duplicado.filter(Tanque.id != tanque_id)

    if duplicado.first():

        return None, f'Você já tem um tanque chamado "{nome}". Escolha outro nome.'

    return {
        'nome': nome,
        'especie': especie,
        'quantidade': int(quantidade),
        'volume_m3': volume,
        'observacoes': request.form.get('observacoes', '').strip() or None,
    }, None
