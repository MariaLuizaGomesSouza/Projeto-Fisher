import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db
from models import User
from functools import wraps
from flask import abort
from flask_login import current_user

auth_bp = Blueprint('auth', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)  # Retorna erro HTTP 403 (Proibido)
        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/admin/usuarios')
@login_required
@admin_required
def listar_usuarios():
    usuarios = User.query.all()
    return render_template('admin_usuarios.html', usuarios=usuarios)

@auth_bp.route('/admin/usuarios/<int:user_id>/toggle-admin', methods=['POST'])
@login_required
@admin_required
def alternar_admin(user_id):
    usuario = User.query.get_or_404(user_id)
    
    # Evita que o próprio admin remova as suas permissões
    if usuario.id == current_user.id:
        flash('Você não pode alterar a sua própria permissão de administrador.', 'erro')
        return redirect(url_for('auth.listar_usuarios'))
        
    usuario.is_admin = not usuario.is_admin
    db.session.commit()
    
    status = "promovido a Admin" if usuario.is_admin else "rebaixado para Produtor"
    flash(f'{usuario.nome} {status} com sucesso!', 'sucesso')
    return redirect(url_for('auth.listar_usuarios'))

# Configuração dos Logs de Segurança
seg_logger = logging.getLogger('seguranca')
if not seg_logger.handlers:
    handler = logging.FileHandler('seguranca.log')
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    seg_logger.addHandler(handler)
    seg_logger.setLevel(logging.INFO)

@auth_bp.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        if not nome or not email or not senha:
            flash('Preencha todos os campos.', 'erro')
            return redirect(url_for('auth.registrar'))

        if User.query.filter_by(email=email).first():
            flash('Este e-mail já está cadastrado!', 'erro')
            return redirect(url_for('auth.registrar'))

        if len(senha) < 6:
            flash('A senha precisa ter pelo menos 6 caracteres.', 'erro')
            return redirect(url_for('auth.registrar'))

        # Se o sistema ainda não tem nenhum administrador, a primeira
        # conta criada vira administradora. Depois disso, novas contas
        # são sempre Produtor (o admin promove pelo Painel Admin ou
        # pelo terminal: flask --app app promover-admin EMAIL).
        primeiro_admin = not User.query.filter_by(is_admin=True).first()

        novo_user = User(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha),
            is_admin=primeiro_admin
        )

        db.session.add(novo_user)
        db.session.commit()

        flash('Conta criada com sucesso! Faça login.', 'sucesso')
        return redirect(url_for('auth.login'))

    return render_template('registrar.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        senha = request.form.get('senha', '')

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.senha, senha):
            login_user(user)
            seg_logger.info(f'sucesso_login email={email} ip={request.remote_addr}')
            return redirect(url_for('dashboard'))

        seg_logger.warning(f'falha_login email={email} ip={request.remote_addr}')
        flash('E-mail ou senha incorretos.', 'erro')

    return render_template('login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))