import os
import datetime
import click
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db, login_manager, csrf
from models import User, Tanque

# =========================================================
# FILTROS PERSONALIZADOS DO JINJA2
# =========================================================

def formatar_br(valor, casas=1):
    if valor is None:
        return '-'
    try:
        val = float(valor)
        return f"{val:,.{casas}f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (ValueError, TypeError):
        return valor

def data_br(val):
    if not val:
        return '-'
    if isinstance(val, str):
        return val
    return val.strftime('%d/%m/%Y')

def data_hora_br(val):
    if not val:
        return '-'
    if isinstance(val, str):
        return val
    return val.strftime('%d/%m/%Y às %H:%M')

def quando(val):
    if not val:
        return '-'
    if isinstance(val, (datetime.date, datetime.datetime)):
        return val.strftime('%d/%m/%Y')
    return str(val)


# =========================================================
# APLICAÇÃO FLASK (APPLICATION FACTORY)
# =========================================================

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    # Registo dos Filtros no Jinja2
    app.jinja_env.filters['br'] = formatar_br
    app.jinja_env.filters['data_br'] = data_br
    app.jinja_env.filters['data_hora_br'] = data_hora_br
    app.jinja_env.filters['quando'] = quando

    # Inicialização das extensões
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = "Por favor, faça login para acessar esta página."

    @app.context_processor
    def inject_globals():
        rotulos = {
            'trato': 'Tratos',
            'biometria': 'Biometrias'
        }
        perfis_especies = {
            'tilapia': {'temp_ideal': 28, 'taxa_trato': 0.03},
            'tambaqui': {'temp_ideal': 30, 'taxa_trato': 0.025}
        }
        return dict(ROTULOS_ATIVIDADE=rotulos, PERFIS_JSON=perfis_especies)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Registo dos Blueprints
    from auth.routes import auth_bp
    from tanques.routes import tanques_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(tanques_bp)

    # Rota Principal
    @app.route('/')
    @login_required
    def dashboard():
        if current_user.is_admin:
            meus_tanques = Tanque.query.all()
        else:
            meus_tanques = Tanque.query.filter_by(user_id=current_user.id).all()

        total_tanques = len(meus_tanques)
        return render_template('index.html', total_tanques=total_tanques)

    # Comando CLI para criar/redefinir o Administrador Padrão
    @app.cli.command("init-admin")
    def init_admin():
        """Cria ou atualiza o usuário administrador padrão (Adm@gmail.com)."""
        email_admin = "adm@gmail.com"
        senha_admin = "Adm123456"
        
        admin = User.query.filter_by(email=email_admin).first()
        
        if not admin:
            admin = User(
                nome="Administrador",
                email=email_admin,
                senha=generate_password_hash(senha_admin),
                is_admin=True
            )
            db.session.add(admin)
            click.echo("Administrador padrão (Adm@gmail.com) criado com sucesso!")
        else:
            admin.is_admin = True
            admin.senha = generate_password_hash(senha_admin)
            click.echo("Administrador padrão (Adm@gmail.com) atualizado com sucesso!")
            
        db.session.commit()

    # Comando CLI para criar outro administrador de forma interativa
    @app.cli.command("criar-admin")
    def criar_admin():
        """Cria um usuário administrador pelo terminal."""
        nome = click.prompt("Nome do Administrador")
        email = click.prompt("E-mail").strip().lower()
        senha = click.prompt("Senha", hide_input=True)

        if User.query.filter_by(email=email).first():
            click.echo("Erro: E-mail já cadastrado!")
            return

        admin = User(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha),
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()
        click.echo("Administrador criado com sucesso!")

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')