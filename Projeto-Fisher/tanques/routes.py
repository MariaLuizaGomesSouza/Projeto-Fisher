import csv
import io
from datetime import timedelta

from flask import (
    Blueprint, Response, flash, jsonify, redirect, render_template,
    request, url_for
)
from flask_login import current_user, login_required
from sqlalchemy import func

import racao
from extensions import db
from models import Biometria, RegistroTrato, Tanque
from servicos import (
    avaliar, consumo_semana, ler_formulario_tanque, listar_atividades,
    obter_estoque, obter_tanque, registrar_atividade,
    tanques_visiveis, ultima_biometria, voltar_para
)
from utils import agora, numero

tanques_bp = Blueprint('tanques', __name__)


# =========================================================
# LISTA DE TANQUES
# =========================================================

@tanques_bp.route('/tanques')
@login_required
def listar_tanques():

    referencia = agora()

    itens = [
        {'tanque': t, 'av': avaliar(t, referencia)}
        for t in tanques_visiveis()
    ]

    com_nota = [i for i in itens if i['av']['score'] is not None]

    resumo = {
        'total': len(itens),
        'peixes': sum(i['tanque'].quantidade for i in itens),
        'biomassa': round(sum(
            i['av']['calc']['biomassa_kg']
            for i in itens if i['av']['calc']
        ), 1),
        'media': (
            round(sum(i['av']['score'] for i in com_nota) / len(com_nota))
            if com_nota else None
        ),
        'atencao': sum(
            1 for i in itens
            if i['av']['nivel'] in ('atencao', 'critico')
        ),
    }

    especies = sorted({i['tanque'].especie for i in itens})

    return render_template(
        'tanques.html',
        itens=itens,
        resumo=resumo,
        especies=especies
    )


# =========================================================
# CADASTRAR TANQUE
# =========================================================

@tanques_bp.route('/cadastrar_tanque', methods=['GET', 'POST'])
@login_required
def cadastrar_tanque():

    if request.method == 'POST':

        dados, erro = ler_formulario_tanque()

        if erro:

            flash(erro, 'erro')

            return render_template(
                'cadastrar_tanque.html',
                form=request.form
            )

        tanque = Tanque(user_id=current_user.id, **dados)

        db.session.add(tanque)

        db.session.flush()

        registrar_atividade(
            'tanque',
            f'Tanque "{tanque.nome}" criado com '
            f'{tanque.quantidade} {tanque.especie}.',
            tanque.id
        )

        db.session.commit()

        flash('Tanque cadastrado com sucesso! Agora registre a primeira biometria.', 'sucesso')

        return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

    return render_template('cadastrar_tanque.html', form={})


# =========================================================
# EDITAR TANQUE
# =========================================================

@tanques_bp.route('/editar_tanque/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def editar_tanque(tanque_id):

    tanque = obter_tanque(tanque_id, 'editar')

    if tanque is None:

        return redirect(url_for('tanques.listar_tanques'))

    if request.method == 'POST':

        dados, erro = ler_formulario_tanque(tanque.id)

        if erro:

            flash(erro, 'erro')

            return render_template(
                'editar_tanque.html',
                tanque=tanque,
                form=request.form
            )

        mudancas = []

        if dados['nome'] != tanque.nome:

            mudancas.append(f'nome para "{dados["nome"]}"')

        if dados['especie'] != tanque.especie:

            mudancas.append(f'espécie para {dados["especie"]}')

        if dados['quantidade'] != tanque.quantidade:

            mudancas.append(
                f'quantidade de {tanque.quantidade} para {dados["quantidade"]}'
            )

        if dados['volume_m3'] != tanque.volume_m3:

            mudancas.append('volume')

        if dados['observacoes'] != tanque.observacoes:

            mudancas.append('observações')

        nome_antigo = tanque.nome

        for campo, valor in dados.items():

            setattr(tanque, campo, valor)

        if mudancas:

            registrar_atividade(
                'tanque',
                f'Tanque "{nome_antigo}" editado: alterou '
                + ', '.join(mudancas) + '.',
                tanque.id
            )

        db.session.commit()

        flash('Tanque atualizado com sucesso!', 'sucesso')

        return redirect(url_for('tanques.listar_tanques'))

    return render_template(
        'editar_tanque.html',
        tanque=tanque,
        form={}
    )


# =========================================================
# DUPLICAR TANQUE
# =========================================================

@tanques_bp.route('/duplicar_tanque/<int:tanque_id>', methods=['POST'])
@login_required
def duplicar_tanque(tanque_id):

    original = obter_tanque(tanque_id, 'duplicar')

    if original is None:

        return redirect(url_for('tanques.listar_tanques'))

    base = f'{original.nome} (cópia)'

    nome = base

    contador = 2

    while Tanque.query.filter(
        func.lower(Tanque.nome) == nome.lower(),
        Tanque.user_id == current_user.id
    ).first():

        nome = f'{base} {contador}'

        contador += 1

    copia = Tanque(
        nome=nome,
        especie=original.especie,
        quantidade=original.quantidade,
        volume_m3=original.volume_m3,
        observacoes=original.observacoes,
        user_id=current_user.id
    )

    db.session.add(copia)

    db.session.flush()

    registrar_atividade(
        'tanque',
        f'Tanque "{original.nome}" duplicado como "{copia.nome}".',
        copia.id
    )

    db.session.commit()

    flash('Tanque duplicado. Revise o nome e os dados abaixo.', 'sucesso')

    return redirect(url_for('tanques.editar_tanque', tanque_id=copia.id))


# =========================================================
# DELETAR TANQUE
# =========================================================

@tanques_bp.route('/deletar_tanque/<int:tanque_id>', methods=['POST'])
@login_required
def deletar_tanque(tanque_id):

    tanque = obter_tanque(tanque_id, 'deletar')

    if tanque is None:

        return redirect(url_for('tanques.listar_tanques'))

    registrar_atividade(
        'tanque',
        f'Tanque "{tanque.nome}" excluído junto com o histórico dele.',
        tanque.id
    )

    # Biometrias e tratos são apagados junto (cascade)

    db.session.delete(tanque)

    db.session.commit()

    flash('Tanque deletado com sucesso!', 'sucesso')

    return redirect(url_for('tanques.listar_tanques'))


# =========================================================
# BIOMETRIA / PÁGINA DO TANQUE
# =========================================================

@tanques_bp.route('/biometria/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def biometria(tanque_id):

    tanque = obter_tanque(tanque_id, 'acessar')

    if tanque is None:

        return redirect(url_for('tanques.listar_tanques'))

    if request.method == 'POST':

        peso = numero(request.form.get('peso_medio'), 0.01, 50000)

        temperatura = numero(request.form.get('temperatura'), 0, 50)

        if peso is None or temperatura is None:

            flash(
                'Digite valores válidos: peso médio entre 0,01 e 50.000 g '
                'e temperatura entre 0 e 50 °C.',
                'erro'
            )

            return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

        db.session.add(Biometria(
            peso_medio_gramas=peso,
            temperatura_agua=temperatura,
            tanque_id=tanque.id,
            data=agora()
        ))

        calc = racao.calcular_racao(
            tanque.especie,
            tanque.quantidade,
            peso,
            temperatura
        )

        registrar_atividade(
            'biometria',
            f'Biometria em "{tanque.nome}": {peso:g} g a {temperatura:g} °C. '
            f'Ração recomendada: {calc["total_kg"]:.2f} kg/dia.',
            tanque.id
        )

        db.session.commit()

        flash('Biometria registrada! A ração foi recalculada.', 'sucesso')

        return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

    historico = Biometria.query.filter_by(
        tanque_id=tanque.id
    ).order_by(
        Biometria.data.desc(),
        Biometria.id.desc()
    ).all()

    tratos = RegistroTrato.query.filter_by(
        tanque_id=tanque.id
    ).order_by(
        RegistroTrato.data.desc(),
        RegistroTrato.id.desc()
    ).limit(12).all()

    av = avaliar(tanque)

    # ----- crescimento -----

    crescimento = None

    if len(historico) >= 2:

        primeira, ultima = historico[-1], historico[0]

        dias = max(1, (ultima.data - primeira.data).days)

        ganho = ultima.peso_medio_gramas - primeira.peso_medio_gramas

        crescimento = {
            'ganho_g': round(ganho, 1),
            'dias': dias,
            'gpd': round(ganho / dias, 2),
            'percentual': round(ganho / primeira.peso_medio_gramas * 100),
        }

    # ----- dados para os gráficos -----

    serie = [
        {
            'data': b.data.strftime('%d/%m'),
            'peso': b.peso_medio_gramas,
            'temp': b.temperatura_agua,
        }
        for b in reversed(historico[:20])
    ]

    _, perfil = racao.perfil_da_especie(tanque.especie)

    recomendado = av['calc']['total_kg'] if av['calc'] else 0

    registro_estoque = obter_estoque()

    estoque = racao.avaliar_estoque(
        registro_estoque.quantidade_kg,
        registro_estoque.capacidade_kg,
        recomendado
    )

    return render_template(
        'biometria.html',
        tanque=tanque,
        av=av,
        perfil=perfil,
        biometrias=historico,
        ultima=historico[0] if historico else None,
        tratos=tratos,
        crescimento=crescimento,
        serie=serie,
        semana=consumo_semana([tanque.id], recomendado),
        estoque=estoque,
        atividades=[
            a for a in listar_atividades(limite=60)
            if a.tanque_id == tanque.id
        ][:6]
    )


@tanques_bp.route(
    '/biometria/<int:tanque_id>/excluir/<int:bio_id>',
    methods=['POST']
)
@login_required
def excluir_biometria(tanque_id, bio_id):

    tanque = obter_tanque(tanque_id, 'alterar')

    if tanque is None:

        return redirect(url_for('tanques.listar_tanques'))

    bio = db.get_or_404(Biometria, bio_id)

    if bio.tanque_id == tanque.id:

        registrar_atividade(
            'biometria',
            f'Biometria de {bio.data.strftime("%d/%m/%Y")} '
            f'({bio.peso_medio_gramas:g} g) removida de "{tanque.nome}".',
            tanque.id
        )

        db.session.delete(bio)

        db.session.commit()

        flash('Biometria removida. A ração foi recalculada.', 'sucesso')

    return redirect(url_for('tanques.biometria', tanque_id=tanque.id))


# =========================================================
# TRATO (ração fornecida)
# =========================================================

@tanques_bp.route('/trato/<int:tanque_id>', methods=['POST'])
@login_required
def registrar_trato(tanque_id):

    tanque = obter_tanque(tanque_id, 'alimentar')

    if tanque is None:

        return redirect(url_for('tanques.listar_tanques'))

    quantidade = numero(request.form.get('quantidade'), 0.001, 10000)

    if quantidade is None:

        flash('Digite a quantidade de ração em kg (maior que zero).', 'erro')

        return voltar_para('tanques.biometria', tanque_id=tanque.id)

    estoque = obter_estoque()

    descontado = min(quantidade, estoque.quantidade_kg)

    estoque.quantidade_kg = round(estoque.quantidade_kg - descontado, 3)

    db.session.add(RegistroTrato(
        quantidade_kg=quantidade,
        descontado_kg=descontado,
        tanque_id=tanque.id,
        user_id=current_user.id,
        data=agora()
    ))

    registrar_atividade(
        'trato',
        f'{quantidade:g} kg de ração fornecidos em "{tanque.nome}".',
        tanque.id
    )

    db.session.commit()

    if descontado < quantidade:

        flash(
            'Trato registrado, mas o estoque não tinha ração suficiente. '
            'Atualize o estoque para manter o controle correto.',
            'info'
        )

    else:

        flash('Trato registrado e descontado do estoque.', 'sucesso')

    return voltar_para('tanques.biometria', tanque_id=tanque.id)


@tanques_bp.route(
    '/trato/<int:tanque_id>/excluir/<int:trato_id>',
    methods=['POST']
)
@login_required
def excluir_trato(tanque_id, trato_id):

    tanque = obter_tanque(tanque_id, 'alterar')

    if tanque is None:

        return redirect(url_for('tanques.listar_tanques'))

    trato = db.get_or_404(RegistroTrato, trato_id)

    if trato.tanque_id == tanque.id:

        estoque = obter_estoque()

        estoque.quantidade_kg = round(
            min(
                estoque.capacidade_kg,
                estoque.quantidade_kg + (trato.descontado_kg or 0)
            ),
            3
        )

        registrar_atividade(
            'trato',
            f'Trato de {trato.quantidade_kg:g} kg desfeito em "{tanque.nome}". '
            f'A ração voltou ao estoque.',
            tanque.id
        )

        db.session.delete(trato)

        db.session.commit()

        flash('Trato desfeito e ração devolvida ao estoque.', 'sucesso')

    return redirect(url_for('tanques.biometria', tanque_id=tanque.id))


# =========================================================
# MORTALIDADE
# =========================================================

@tanques_bp.route('/mortalidade/<int:tanque_id>', methods=['POST'])
@login_required
def registrar_mortalidade(tanque_id):

    tanque = obter_tanque(tanque_id, 'alterar')

    if tanque is None:

        return redirect(url_for('tanques.listar_tanques'))

    perdas = numero(request.form.get('perdas'), 1)

    if perdas is None or perdas != int(perdas) or perdas > tanque.quantidade:

        flash(
            f'Informe um número inteiro entre 1 e {tanque.quantidade}.',
            'erro'
        )

        return redirect(url_for('tanques.biometria', tanque_id=tanque.id))

    perdas = int(perdas)

    antes = tanque.quantidade

    tanque.quantidade = antes - perdas

    registrar_atividade(
        'mortalidade',
        f'{perdas} peixe(s) perdido(s) em "{tanque.nome}" '
        f'({antes} → {tanque.quantidade}). A ração foi recalculada.',
        tanque.id
    )

    db.session.commit()

    flash('Baixa registrada. A quantidade de peixes e a ração foram atualizadas.', 'sucesso')

    return redirect(url_for('tanques.biometria', tanque_id=tanque.id))


# =========================================================
# ESTOQUE DE RAÇÃO
# =========================================================

@tanques_bp.route('/estoque', methods=['GET', 'POST'])
@login_required
def estoque():

    registro = obter_estoque()

    if request.method == 'POST':

        acao = request.form.get('acao')

        valor = numero(request.form.get('valor'), 0, 100000)

        if valor is None:

            flash('Digite um valor válido em kg.', 'erro')

            return redirect(url_for('tanques.estoque'))

        if acao == 'repor' and valor > 0:

            registro.quantidade_kg = round(registro.quantidade_kg + valor, 3)

            if registro.quantidade_kg > registro.capacidade_kg:

                registro.capacidade_kg = registro.quantidade_kg

            registrar_atividade(
                'estoque',
                f'{valor:g} kg de ração adicionados. '
                f'Estoque agora: {registro.quantidade_kg:g} kg.'
            )

            flash('Estoque reposto.', 'sucesso')

        elif acao == 'ajustar':

            registro.quantidade_kg = valor

            if valor > registro.capacidade_kg:

                registro.capacidade_kg = valor

            registrar_atividade(
                'estoque',
                f'Estoque ajustado manualmente para {valor:g} kg.'
            )

            flash('Estoque ajustado.', 'sucesso')

        elif acao == 'capacidade' and valor > 0:

            registro.capacidade_kg = valor

            if registro.quantidade_kg > valor:

                registro.quantidade_kg = valor

            registrar_atividade(
                'estoque',
                f'Capacidade do depósito definida em {valor:g} kg.'
            )

            flash('Capacidade atualizada.', 'sucesso')

        else:

            flash('Ação inválida.', 'erro')

        db.session.commit()

        return redirect(url_for('tanques.estoque'))

    tanques = tanques_visiveis()

    consumo = 0

    por_tanque = []

    for t in tanques:

        av = avaliar(t)

        if av['calc']:

            consumo += av['calc']['total_kg']

            por_tanque.append({
                'tanque': t,
                'kg': av['calc']['total_kg']
            })

    por_tanque.sort(key=lambda x: -x['kg'])

    return render_template(
        'estoque.html',
        estoque=racao.avaliar_estoque(
            registro.quantidade_kg,
            registro.capacidade_kg,
            consumo
        ),
        por_tanque=por_tanque,
        movimentos=listar_atividades(limite=10, tipo='estoque')
    )


# =========================================================
# HISTÓRICO DE ATIVIDADES
# =========================================================

@tanques_bp.route('/historico')
@login_required
def historico():

    tipo = request.args.get('tipo')

    atividades = listar_atividades(limite=300, tipo=tipo)

    hoje = agora().date()

    grupos = []

    for a in atividades:

        dia = a.criado_em.date()

        if dia == hoje:

            rotulo = 'Hoje'

        elif dia == hoje - timedelta(days=1):

            rotulo = 'Ontem'

        else:

            rotulo = dia.strftime('%d/%m/%Y')

        if not grupos or grupos[-1][0] != rotulo:

            grupos.append((rotulo, []))

        grupos[-1][1].append(a)

    return render_template(
        'historico.html',
        grupos=grupos,
        total=len(atividades),
        tipo=tipo
    )


# =========================================================
# EXPORTAR TANQUES (CSV para Excel)
# =========================================================

@tanques_bp.route('/exportar_tanques.csv')
@login_required
def exportar_tanques():

    saida = io.StringIO()

    escritor = csv.writer(saida, delimiter=';')

    escritor.writerow([
        'Tanque', 'Espécie', 'Peixes', 'Volume (m³)',
        'Peso médio (g)', 'Biomassa (kg)', 'Temperatura (°C)',
        'Ração diária (kg)', 'Bem-estar (%)', 'Cadastro'
    ])

    def virgula(valor):

        return '' if valor is None else str(valor).replace('.', ',')

    for t in tanques_visiveis():

        av = avaliar(t)

        bio = ultima_biometria(t.id)

        escritor.writerow([
            t.nome,
            t.especie,
            t.quantidade,
            virgula(t.volume_m3),
            virgula(bio.peso_medio_gramas if bio else None),
            virgula(av['calc']['biomassa_kg'] if av['calc'] else None),
            virgula(bio.temperatura_agua if bio else None),
            virgula(av['calc']['total_kg'] if av['calc'] else None),
            av['score'] if av['score'] is not None else '',
            t.criado_em.strftime('%d/%m/%Y') if t.criado_em else ''
        ])

    # O BOM no início faz o Excel abrir os acentos corretamente

    return Response(
        '\ufeff' + saida.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={
            'Content-Disposition':
                'attachment; filename=tanques_fisher.csv'
        }
    )


# =========================================================
# API: SIMULADOR DE RAÇÃO (usado pelo formulário ao vivo)
# =========================================================

@tanques_bp.route('/api/simular/<int:tanque_id>')
@login_required
def api_simular(tanque_id):

    tanque = db.get_or_404(Tanque, tanque_id)

    if not current_user.is_admin and tanque.user_id != current_user.id:

        return jsonify({'erro': 'Sem permissão'}), 403

    peso = numero(request.args.get('peso'), 0.01, 50000)

    temperatura = numero(request.args.get('temp'), 0, 50)

    if peso is None or temperatura is None:

        return jsonify({'erro': 'Valores inválidos'}), 400

    calc = racao.calcular_racao(
        tanque.especie,
        tanque.quantidade,
        peso,
        temperatura
    )

    calc['temp_ideal'] = list(calc['temp_ideal'])

    return jsonify(calc)
