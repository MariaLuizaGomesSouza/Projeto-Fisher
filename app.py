from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime


# =========================================================
# CONFIGURAÇÃO DO FLASK
# =========================================================

app = Flask(__name__)

app.config['SECRET_KEY'] = 'chave_secreta_fisher_2026'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fisher.db'

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
# MODELO USUÁRIO
# =========================================================

class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    senha = db.Column(
        db.String(200),
        nullable=False
    )

    is_admin = db.Column(
        db.Boolean,
        default=False
    )

    tanques = db.relationship(
        'Tanque',
        backref='dono',
        lazy=True,
        cascade='all, delete-orphan'
    )


# =========================================================
# MODELO TANQUE
# =========================================================

class Tanque(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    nome = db.Column(
        db.String(100),
        nullable=False
    )

    especie = db.Column(
        db.String(100),
        nullable=False
    )

    quantidade = db.Column(
        db.Integer,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )


# =========================================================
# MODELO BIOMETRIA
# =========================================================

class Biometria(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    peso_medio_gramas = db.Column(
        db.Float,
        nullable=False
    )

    temperatura_agua = db.Column(
        db.Float,
        nullable=False
    )

    data = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    tanque_id = db.Column(
        db.Integer,
        db.ForeignKey('tanque.id'),
        nullable=False
    )


# =========================================================
# LOGIN MANAGER
# =========================================================

@login_manager.user_loader
def load_user(user_id):

    return db.session.get(
        User,
        int(user_id)
    )


# =========================================================
# AUTENTICAÇÃO
# =========================================================

@app.route('/registrar', methods=['GET', 'POST'])
def registrar():

    if request.method == 'POST':

        nome = request.form.get('nome', '').strip()

        email = request.form.get('email', '').strip().lower()

        senha = request.form.get('senha', '')


        if not nome or not email or not senha:

            flash('Preencha todos os campos.')

            return redirect(
                url_for('registrar')
            )


        usuario_existente = User.query.filter_by(
            email=email
        ).first()


        if usuario_existente:

            flash('Este e-mail já está cadastrado!')

            return redirect(
                url_for('registrar')
            )


        # Primeiro usuário vira administrador

        is_admin = User.query.count() == 0


        novo_user = User(

            nome=nome,

            email=email,

            senha=generate_password_hash(senha),

            is_admin=is_admin
        )


        db.session.add(novo_user)

        db.session.commit()


        flash('Conta criada com sucesso! Faça login.')


        return redirect(
            url_for('login')
        )


    return render_template(
        'registrar.html'
    )


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form.get(
            'email',
            ''
        ).strip().lower()

        senha = request.form.get(
            'senha',
            ''
        )


        user = User.query.filter_by(
            email=email
        ).first()


        if user and check_password_hash(
            user.senha,
            senha
        ):

            login_user(user)

            return redirect(
                url_for('dashboard')
            )


        flash(
            'E-mail ou senha incorretos.'
        )


    return render_template(
        'login.html'
    )


@app.route('/logout')
@login_required
def logout():

    logout_user()

    return redirect(
        url_for('login')
    )


# =========================================================
# DASHBOARD
# =========================================================

@app.route('/')
@login_required
def dashboard():

    if current_user.is_admin:

        meus_tanques = Tanque.query.all()

    else:

        meus_tanques = Tanque.query.filter_by(
            user_id=current_user.id
        ).all()


    total_tanques = len(
        meus_tanques
    )


    return render_template(
        'index.html',
        total_tanques=total_tanques
    )


# =========================================================
# LISTA DE TANQUES
# =========================================================

@app.route('/tanques')
@login_required
def listar_tanques():

    if current_user.is_admin:

        tanques = Tanque.query.all()

    else:

        tanques = Tanque.query.filter_by(
            user_id=current_user.id
        ).all()


    return render_template(
        'tanques.html',
        tanques=tanques
    )


# =========================================================
# CADASTRAR TANQUE
# =========================================================

@app.route(
    '/cadastrar_tanque',
    methods=['GET', 'POST']
)
@login_required
def cadastrar_tanque():

    if request.method == 'POST':

        nome = request.form.get(
            'nome',
            ''
        ).strip()

        especie = request.form.get(
            'especie',
            ''
        ).strip()

        quantidade = request.form.get(
            'quantidade',
            ''
        )


        if not nome or not especie or not quantidade:

            flash(
                'Preencha todos os campos.'
            )

            return redirect(
                url_for('cadastrar_tanque')
            )


        try:

            quantidade = int(
                quantidade
            )

            if quantidade <= 0:

                raise ValueError


        except ValueError:

            flash(
                'A quantidade de peixes deve ser um número maior que zero.'
            )

            return redirect(
                url_for('cadastrar_tanque')
            )


        novo_tanque = Tanque(

            nome=nome,

            especie=especie,

            quantidade=quantidade,

            user_id=current_user.id

        )


        db.session.add(
            novo_tanque
        )

        db.session.commit()


        flash(
            'Tanque cadastrado com sucesso!'
        )


        return redirect(
            url_for('listar_tanques')
        )


    return render_template(
        'cadastrar_tanque.html'
    )


# =========================================================
# BIOMETRIA
# =========================================================

@app.route(
    '/biometria/<int:tanque_id>',
    methods=['GET', 'POST']
)
@login_required
def biometria(tanque_id):

    tanque = Tanque.query.get_or_404(
        tanque_id
    )


    if (
        not current_user.is_admin
        and tanque.user_id != current_user.id
    ):

        flash(
            'Você não tem permissão para acessar este tanque.'
        )

        return redirect(
            url_for('listar_tanques')
        )


    if request.method == 'POST':

        try:

            peso_medio = float(
                request.form.get(
                    'peso_medio'
                )
            )

            temperatura = float(
                request.form.get(
                    'temperatura'
                )
            )

            if peso_medio <= 0:

                raise ValueError

        except (TypeError, ValueError):

            flash(
                'Digite valores válidos para peso e temperatura.'
            )

            return redirect(
                url_for(
                    'biometria',
                    tanque_id=tanque.id
                )
            )


        nova_biometria = Biometria(

            peso_medio_gramas=peso_medio,

            temperatura_agua=temperatura,

            tanque_id=tanque.id

        )


        db.session.add(
            nova_biometria
        )

        db.session.commit()


        flash(
            'Biometria registrada com sucesso!'
        )


        return redirect(
            url_for(
                'biometria',
                tanque_id=tanque.id
            )
        )


    historico = Biometria.query.filter_by(

        tanque_id=tanque.id

    ).order_by(

        Biometria.data.desc()

    ).all()


    # =====================================================
    # CÁLCULO DE RAÇÃO
    # =====================================================

    racao_sugerida = 0

    if historico:

        ultima_medicao = historico[0]


        biomassa_kg = (

            ultima_medicao.peso_medio_gramas
            * tanque.quantidade

        ) / 1000


        taxa = 0.03


        if ultima_medicao.temperatura_agua < 22:

            taxa = 0.01

        elif ultima_medicao.temperatura_agua > 32:

            taxa = 0.015


        racao_sugerida = round(
            biomassa_kg * taxa,
            2
        )


    return render_template(

        'biometria.html',

        tanque=tanque,

        racao_sugerida=racao_sugerida,

        biometrias=historico

    )


# =========================================================
# EDITAR TANQUE
# =========================================================

@app.route(
    '/editar_tanque/<int:tanque_id>',
    methods=['GET', 'POST']
)
@login_required
def editar_tanque(tanque_id):

    tanque = Tanque.query.get_or_404(
        tanque_id
    )


    if (
        not current_user.is_admin
        and tanque.user_id != current_user.id
    ):

        flash(
            'Você não tem permissão para editar este tanque.'
        )

        return redirect(
            url_for('listar_tanques')
        )


    if request.method == 'POST':

        nome = request.form.get(
            'nome',
            ''
        ).strip()

        especie = request.form.get(
            'especie',
            ''
        ).strip()

        quantidade = request.form.get(
            'quantidade',
            ''
        )


        try:

            quantidade = int(
                quantidade
            )

            if quantidade <= 0:

                raise ValueError

        except ValueError:

            flash(
                'A quantidade deve ser maior que zero.'
            )

            return redirect(
                url_for(
                    'editar_tanque',
                    tanque_id=tanque.id
                )
            )


        tanque.nome = nome

        tanque.especie = especie

        tanque.quantidade = quantidade


        db.session.commit()


        flash(
            'Tanque atualizado com sucesso!'
        )


        return redirect(
            url_for('listar_tanques')
        )


    return render_template(
        'editar_tanques.html',
        tanque=tanque
    )


# =========================================================
# DELETAR TANQUE
# =========================================================

@app.route(
    '/deletar_tanque/<int:tanque_id>',
    methods=['POST']
)
@login_required
def deletar_tanque(tanque_id):

    tanque = Tanque.query.get_or_404(
        tanque_id
    )


    if (
        not current_user.is_admin
        and tanque.user_id != current_user.id
    ):

        flash(
            'Você não tem permissão para deletar este tanque.'
        )

        return redirect(
            url_for('listar_tanques')
        )


    # Remove as biometrias do tanque

    Biometria.query.filter_by(
        tanque_id=tanque.id
    ).delete()


    db.session.delete(
        tanque
    )

    db.session.commit()


    flash(
        'Tanque deletado com sucesso!'
    )


    return redirect(
        url_for('listar_tanques')
    )


# =========================================================
# BANCO DE DADOS
# =========================================================

with app.app_context():

    db.create_all()


# =========================================================
# EXECUÇÃO
# =========================================================

if __name__ == '__main__':

    app.run(
        debug=True
    )