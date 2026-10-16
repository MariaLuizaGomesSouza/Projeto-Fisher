import csv
import io
import os
from collections import defaultdict
from datetime import datetime, time, timedelta

from flask import (
    Flask,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func, inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

import racao


# =========================================================
# CONFIGURAÇÃO DO FLASK
# =========================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get(
    'FISHER_SECRET_KEY',
    'chave_secreta_fisher_2026'
)

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'FISHER_DATABASE_URI',
    'sqlite:///fisher.db'
)

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False


# =========================================================
# BANCO DE DADOS
# =========================================================

db = SQLAlchemy(app)


# =========================================================
# LOGIN
# =========================================================

login_manager = LoginManager(app)

login_manager.login_view = 'login'

login_manager.login_message = (
    "Por favor, faça login para acessar esta página."
)


# =========================================================
# UTILITÁRIOS
# =========================================================

def agora():
    """Data e hora local (usada em todos os registros novos)."""

    return datetime.now()


# =========================================================
# MODELOS
# =========================================================

class User(UserMixin, db.Model):

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)

    email = db.Column(db.String(100), unique=True, nullable=False)

    senha = db.Column(db.String(200), nullable=False)

    is_admin = db.Column(db.Boolean, default=False)

    tanques = db.relationship(
        'Tanque',
        backref='dono',
        lazy=True,
        cascade='all, delete-orphan'
    )


class Tanque(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(100), nullable=False)

    especie = db.Column(db.String(100), nullable=False)

    quantidade = db.Column(db.Integer, nullable=False)

    # NOVOS CAMPOS (opcionais)

    volume_m3 = db.Column(db.Float, nullable=True)

    observacoes = db.Column(db.Text, nullable=True)

    criado_em = db.Column(db.DateTime, default=agora)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    biometrias = db.relationship(
        'Biometria',
        backref='tanque',
        lazy=True,
        cascade='all, delete-orphan'
    )

    tratos = db.relationship(
        'RegistroTrato',
        backref='tanque',
        lazy=True,
        cascade='all, delete-orphan'
    )


class Biometria(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    peso_medio_gramas = db.Column(db.Float, nullable=False)

    temperatura_agua = db.Column(db.Float, nullable=False)

    data = db.Column(db.DateTime, default=agora)

    tanque_id = db.Column(
        db.Integer,
        db.ForeignKey('tanque.id'),
        nullable=False
    )


class RegistroTrato(db.Model):
    """Cada vez que o produtor joga ração no tanque."""

    id = db.Column(db.Integer, primary_key=True)

    quantidade_kg = db.Column(db.Float, nullable=False)

    # Quanto realmente saiu do estoque (pode ser menos que o
    # trato, se o estoque estava acabando). Usado para desfazer.

    descontado_kg = db.Column(db.Float, default=0)

    data = db.Column(db.DateTime, default=agora)

    tanque_id = db.Column(
        db.Integer,
        db.ForeignKey('tanque.id'),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )


class EstoqueRacao(db.Model):
    """Depósito de ração de cada usuário."""

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        unique=True,
        nullable=False
    )

    quantidade_kg = db.Column(db.Float, default=0)

    capacidade_kg = db.Column(db.Float, default=500)


class Atividade(db.Model):
    """Histórico de tudo que foi feito no sistema."""

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, nullable=False)

    autor = db.Column(db.String(100))

    # tanque | biometria | trato | estoque | mortalidade

    tipo = db.Column(db.String(30), nullable=False)

    descricao = db.Column(db.String(300), nullable=False)

    # Sem ForeignKey de propósito: o histórico continua
    # existindo mesmo depois que o tanque é deletado.

    tanque_id = db.Column(db.Integer, nullable=True)

    criado_em = db.Column(db.DateTime, default=agora)


@login_manager.user_loader
def load_user(user_id):

    return db.session.get(User, int(user_id))


# =========================================================
# ATUALIZAÇÃO AUTOMÁTICA DO BANCO
# =========================================================
#
# O db.create_all() cria tabelas novas, mas NÃO adiciona
# colunas em tabelas que já existem. Esta função adiciona
# as colunas novas do tanque sem apagar nenhum dado.

def atualizar_banco():

    db.create_all()

    colunas = {
        c['name']
        for c in inspect(db.engine).get_columns('tanque')
    }

    novas = {
        'volume_m3': 'FLOAT',
        'observacoes': 'TEXT',
        'criado_em': 'DATETIME',
    }

    with db.engine.begin() as conexao:

        for nome, tipo in novas.items():

            if nome not in colunas:

                conexao.execute(
                    text(f'ALTER TABLE tanque ADD COLUMN {nome} {tipo}')
                )


# =========================================================
# FILTROS E VARIÁVEIS PARA OS TEMPLATES
# =========================================================

ICONES_ATIVIDADE = {
    'tanque': 'fa-water',
    'biometria': 'fa-scale-balanced',
    'trato': 'fa-bowl-food',
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


@app.template_filter('br')
def filtro_numero_br(valor, casas=1):
    """1234.5 -> 1.234,5 (formato brasileiro)."""

    if valor is None:

        return '-'

    texto = f'{float(valor):,.{casas}f}'

    return texto.replace(',', '#').replace('.', ',').replace('#', '.')


@app.template_filter('data_br')
def filtro_data_br(dt):

    return dt.strftime('%d/%m/%Y') if dt else '-'


@app.template_filter('data_hora_br')
def filtro_data_hora_br(dt):

    return dt.strftime('%d/%m/%Y às %H:%M') if dt else '-'


@app.template_filter('quando')
def filtro_quando(dt):
    """Tempo relativo: 'há 5 min', 'há 3 h', 'ontem'."""

    if not dt:

        return ''

    segundos = max(0, (agora() - dt).total_seconds())

    if segundos < 60:

        return 'agora mesmo'

    if segundos < 3600:

        return f'há {int(segundos // 60)} min'

    if segundos < 86400:

        return f'há {int(segundos // 3600)} h'

    if segundos < 172800:

        return 'ontem'

    return dt.strftime('%d/%m/%Y')


@app.context_processor
def variaveis_globais():

    return {
        'ICONES_ATIVIDADE': ICONES_ATIVIDADE,
        'ROTULOS_ATIVIDADE': ROTULOS_ATIVIDADE,
        'PERFIS_JSON': racao.perfis_para_formulario(),
    }


# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================

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


def numero(texto, minimo=None, maximo=None):
    """Converte '12,5' ou '12.5' em float. Devolve None se inválido."""

    try:

        valor = float(str(texto).strip().replace(',', '.'))

    except (TypeError, ValueError):

        return None

    if valor != valor:

        return None

    if minimo is not None and valor < minimo:

        return None

    if maximo is not None and valor > maximo:

        return None

    return valor


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


# =========================================================
# AUTENTICAÇÃO
# =========================================================

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():

    if current_user.is_authenticated:

        return redirect(url_for('dashboard'))

    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()

        email = request.form.get('email', '').strip().lower()

        senha = request.form.get('senha', '')

        if not nome or not email or not senha:

            flash('Preencha todos os campos.', 'erro')

            return redirect(url_for('registrar'))

        if len(senha) < 6:

            flash('A senha precisa ter pelo menos 6 caracteres.', 'erro')

            return redirect(url_for('registrar'))

        if User.query.filter_by(email=email).first():

            flash('Este e-mail já está cadastrado!', 'erro')

            return redirect(url_for('registrar'))

        # Primeiro usuário vira administrador

        is_admin = User.query.count() == 0

        db.session.add(User(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha),
            is_admin=is_admin
        ))

        db.session.commit()

        flash('Conta criada com sucesso! Faça login.', 'sucesso')

        return redirect(url_for('login'))

    return render_template('registrar.html')


@app.route('/login', methods=['GET', 'POST'])
def login():

    if current_user.is_authenticated:

        return redirect(url_for('dashboard'))

    if request.method == 'POST':

        email = request.form.get('email', '').strip().lower()

        senha = request.form.get('senha', '')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.senha, senha):

            login_user(user)

            return redirect(url_for('dashboard'))

        flash('E-mail ou senha incorretos.', 'erro')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():

    logout_user()

    return redirect(url_for('login'))


# =========================================================
# DASHBOARD
# =========================================================

@app.route('/')
@login_required
def dashboard():

    hora = agora().hour

    if hora < 12:

        saudacao = 'Bom dia'

    elif hora < 18:

        saudacao = 'Boa tarde'

    else:

        saudacao = 'Boa noite'

    return render_template(
        'index.html',
        painel=montar_painel(),
        atividades=listar_atividades(limite=8),
        saudacao=saudacao,
        primeiro_nome=current_user.nome.split()[0]
    )


# =========================================================
# LISTA DE TANQUES
# =========================================================

@app.route('/tanques')
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

@app.route('/cadastrar_tanque', methods=['GET', 'POST'])
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

        return redirect(url_for('biometria', tanque_id=tanque.id))

    return render_template('cadastrar_tanque.html', form={})


# =========================================================
# EDITAR TANQUE
# =========================================================

@app.route('/editar_tanque/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def editar_tanque(tanque_id):

    tanque = obter_tanque(tanque_id, 'editar')

    if tanque is None:

        return redirect(url_for('listar_tanques'))

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

        return redirect(url_for('listar_tanques'))

    return render_template(
        'editar_tanque.html',
        tanque=tanque,
        form={}
    )


# =========================================================
# DUPLICAR TANQUE
# =========================================================

@app.route('/duplicar_tanque/<int:tanque_id>', methods=['POST'])
@login_required
def duplicar_tanque(tanque_id):

    original = obter_tanque(tanque_id, 'duplicar')

    if original is None:

        return redirect(url_for('listar_tanques'))

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

    return redirect(url_for('editar_tanque', tanque_id=copia.id))


# =========================================================
# DELETAR TANQUE
# =========================================================

@app.route('/deletar_tanque/<int:tanque_id>', methods=['POST'])
@login_required
def deletar_tanque(tanque_id):

    tanque = obter_tanque(tanque_id, 'deletar')

    if tanque is None:

        return redirect(url_for('listar_tanques'))

    registrar_atividade(
        'tanque',
        f'Tanque "{tanque.nome}" excluído junto com o histórico dele.',
        tanque.id
    )

    # Biometrias e tratos são apagados junto (cascade)

    db.session.delete(tanque)

    db.session.commit()

    flash('Tanque deletado com sucesso!', 'sucesso')

    return redirect(url_for('listar_tanques'))


# =========================================================
# BIOMETRIA / PÁGINA DO TANQUE
# =========================================================

@app.route('/biometria/<int:tanque_id>', methods=['GET', 'POST'])
@login_required
def biometria(tanque_id):

    tanque = obter_tanque(tanque_id, 'acessar')

    if tanque is None:

        return redirect(url_for('listar_tanques'))

    if request.method == 'POST':

        peso = numero(request.form.get('peso_medio'), 0.01, 50000)

        temperatura = numero(request.form.get('temperatura'), 0, 50)

        if peso is None or temperatura is None:

            flash(
                'Digite valores válidos: peso médio entre 0,01 e 50.000 g '
                'e temperatura entre 0 e 50 °C.',
                'erro'
            )

            return redirect(url_for('biometria', tanque_id=tanque.id))

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

        return redirect(url_for('biometria', tanque_id=tanque.id))

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


@app.route(
    '/biometria/<int:tanque_id>/excluir/<int:bio_id>',
    methods=['POST']
)
@login_required
def excluir_biometria(tanque_id, bio_id):

    tanque = obter_tanque(tanque_id, 'alterar')

    if tanque is None:

        return redirect(url_for('listar_tanques'))

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

    return redirect(url_for('biometria', tanque_id=tanque.id))


# =========================================================
# TRATO (ração fornecida)
# =========================================================

@app.route('/trato/<int:tanque_id>', methods=['POST'])
@login_required
def registrar_trato(tanque_id):

    tanque = obter_tanque(tanque_id, 'alimentar')

    if tanque is None:

        return redirect(url_for('listar_tanques'))

    quantidade = numero(request.form.get('quantidade'), 0.001, 10000)

    if quantidade is None:

        flash('Digite a quantidade de ração em kg (maior que zero).', 'erro')

        return voltar_para('biometria', tanque_id=tanque.id)

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

    return voltar_para('biometria', tanque_id=tanque.id)


@app.route(
    '/trato/<int:tanque_id>/excluir/<int:trato_id>',
    methods=['POST']
)
@login_required
def excluir_trato(tanque_id, trato_id):

    tanque = obter_tanque(tanque_id, 'alterar')

    if tanque is None:

        return redirect(url_for('listar_tanques'))

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

    return redirect(url_for('biometria', tanque_id=tanque.id))


# =========================================================
# MORTALIDADE
# =========================================================

@app.route('/mortalidade/<int:tanque_id>', methods=['POST'])
@login_required
def registrar_mortalidade(tanque_id):

    tanque = obter_tanque(tanque_id, 'alterar')

    if tanque is None:

        return redirect(url_for('listar_tanques'))

    perdas = numero(request.form.get('perdas'), 1)

    if perdas is None or perdas != int(perdas) or perdas > tanque.quantidade:

        flash(
            f'Informe um número inteiro entre 1 e {tanque.quantidade}.',
            'erro'
        )

        return redirect(url_for('biometria', tanque_id=tanque.id))

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

    return redirect(url_for('biometria', tanque_id=tanque.id))


# =========================================================
# ESTOQUE DE RAÇÃO
# =========================================================

@app.route('/estoque', methods=['GET', 'POST'])
@login_required
def estoque():

    registro = obter_estoque()

    if request.method == 'POST':

        acao = request.form.get('acao')

        valor = numero(request.form.get('valor'), 0, 100000)

        if valor is None:

            flash('Digite um valor válido em kg.', 'erro')

            return redirect(url_for('estoque'))

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

        return redirect(url_for('estoque'))

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

@app.route('/historico')
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

@app.route('/exportar_tanques.csv')
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

@app.route('/api/simular/<int:tanque_id>')
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


# =========================================================
# BANCO DE DADOS
# =========================================================

with app.app_context():

    atualizar_banco()


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == '__main__':

    app.run(debug=True)
