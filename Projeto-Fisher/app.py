import os
import click
from flask import Flask, render_template
from flask_login import current_user, login_required
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash

import racao
from extensions import csrf, db, login_manager
from models import User
from servicos import (
    ICONES_ATIVIDADE, ROTULOS_ATIVIDADE, listar_atividades, montar_painel
)
from utils import agora


# =========================================================
# FILTROS PERSONALIZADOS DO JINJA2
# =========================================================

def formatar_br(valor, casas=1):
    """1234.5 -> 1.234,5 (formato brasileiro)."""
    if valor is None:
        return '-'
    try:
        texto = f'{float(valor):,.{casas}f}'
        return texto.replace(',', '#').replace('.', ',').replace('#', '.')
    except (ValueError, TypeError):
        return valor


def data_br(dt):
    return dt.strftime('%d/%m/%Y') if dt else '-'


def data_hora_br(dt):
    return dt.strftime('%d/%m/%Y às %H:%M') if dt else '-'


def quando(dt):
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


# =========================================================
# ATUALIZAÇÃO AUTOMÁTICA DO BANCO
# =========================================================
#
# db.create_all() cria tabelas novas, mas NÃO adiciona colunas em
# tabelas que já existem. Esta função adiciona as colunas que a
# versão completa do sistema usa, sem apagar nenhum dado.
#
# Se o usuário do banco não tiver permissão de ALTER/CREATE
# (como o fisher_app do schema.sql), o sistema avisa no terminal
# e o administrador roda banco/migracao_v2.sql uma única vez.

COLUNAS_NOVAS = {
    'tanque': {
        'volume_m3': 'FLOAT',
        'observacoes': 'TEXT',
        'criado_em': 'DATETIME',
    },
    'registro_trato': {
        'descontado_kg': 'FLOAT',
    },
    'estoque_racao': {
        'capacidade_kg': 'FLOAT',
    },
}


def atualizar_banco(app):
    try:
        db.create_all()

        inspetor = inspect(db.engine)

        with db.engine.begin() as conexao:
            for tabela, colunas in COLUNAS_NOVAS.items():
                existentes = {
                    c['name'] for c in inspetor.get_columns(tabela)
                }
                for nome, tipo in colunas.items():
                    if nome not in existentes:
                        conexao.execute(text(
                            f'ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}'
                        ))

            # Valores padrão para registros que já existiam
            conexao.execute(text(
                'UPDATE estoque_racao SET capacidade_kg = 500 '
                'WHERE capacidade_kg IS NULL'
            ))
            conexao.execute(text(
                'UPDATE registro_trato SET descontado_kg = quantidade_kg '
                'WHERE descontado_kg IS NULL'
            ))

    except Exception as erro:  # noqa: BLE001
        app.logger.warning(
            'Não foi possível atualizar o banco automaticamente (%s). '
            'Rode banco/migracao_v2.sql com o usuário administrador do '
            'MySQL (fisher_admin).', erro
        )


# =========================================================
# APLICAÇÃO FLASK (APPLICATION FACTORY)
# =========================================================

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    app.jinja_env.filters['br'] = formatar_br
    app.jinja_env.filters['data_br'] = data_br
    app.jinja_env.filters['data_hora_br'] = data_hora_br
    app.jinja_env.filters['quando'] = quando
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///bancodedados.db')
    
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor, faça login para acessar esta página.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.context_processor
    def variaveis_globais():
        return {
            'ICONES_ATIVIDADE': ICONES_ATIVIDADE,
            'ROTULOS_ATIVIDADE': ROTULOS_ATIVIDADE,
            'PERFIS_JSON': racao.perfis_para_formulario(),
        }

    from auth.routes import auth_bp
    from tanques.routes import tanques_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(tanques_bp)

    # -----------------------------------------------------
    # PAINEL CENTRAL
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # COMANDOS DE ADMINISTRADOR (terminal)
    # -----------------------------------------------------

    @app.cli.command('init-admin')
    def init_admin():
        """Cria ou atualiza o administrador padrão (adm@gmail.com)."""
        email_admin = 'adm@gmail.com'
        senha_admin = 'Adm123456'

        admin = User.query.filter_by(email=email_admin).first()

        if not admin:
            admin = User(
                nome='Administrador',
                email=email_admin,
                senha=generate_password_hash(senha_admin),
                is_admin=True
            )
            db.session.add(admin)
            click.echo('Administrador padrão (adm@gmail.com) criado!')
        else:
            admin.is_admin = True
            admin.senha = generate_password_hash(senha_admin)
            click.echo('Administrador padrão (adm@gmail.com) atualizado!')

        db.session.commit()

    @app.cli.command('promover-admin')
    @click.argument('email')
    def promover_admin(email):
        """Transforma uma conta que já existe em administrador."""
        usuario = User.query.filter_by(email=email.strip().lower()).first()

        if not usuario:
            click.echo(f'Nenhuma conta encontrada com o e-mail {email}.')
            return

        usuario.is_admin = True
        db.session.commit()
        click.echo(f'{usuario.nome} ({usuario.email}) agora é administrador.')

    @app.cli.command('criar-admin')
    def criar_admin():
        """Cria um usuário administrador pelo terminal."""
        nome = click.prompt('Nome do Administrador')
        email = click.prompt('E-mail').strip().lower()
        senha = click.prompt('Senha', hide_input=True)

        if User.query.filter_by(email=email).first():
            click.echo('Erro: e-mail já cadastrado!')
            return

        db.session.add(User(
            nome=nome,
            email=email,
            senha=generate_password_hash(senha),
            is_admin=True
        ))
        db.session.commit()
        click.echo('Administrador criado com sucesso!')

    with app.app_context():
        atualizar_banco(app)

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=os.environ.get('FLASK_DEBUG') == '1')
