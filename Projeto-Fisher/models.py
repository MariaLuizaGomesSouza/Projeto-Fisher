from flask_login import UserMixin

from extensions import db
from utils import agora


class User(UserMixin, db.Model):
    __tablename__ = 'user'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

    tanques = db.relationship(
        'Tanque', backref='dono', lazy=True,
        cascade='all, delete-orphan'
    )


class Tanque(db.Model):
    __tablename__ = 'tanque'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especie = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    volume_m3 = db.Column(db.Float, nullable=True)
    observacoes = db.Column(db.Text, nullable=True)
    criado_em = db.Column(db.DateTime, default=agora)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    biometrias = db.relationship(
        'Biometria', backref='tanque', lazy=True,
        cascade='all, delete-orphan'
    )
    tratos = db.relationship(
        'RegistroTrato', backref='tanque', lazy=True,
        cascade='all, delete-orphan'
    )


class Biometria(db.Model):
    __tablename__ = 'biometria'

    id = db.Column(db.Integer, primary_key=True)
    peso_medio_gramas = db.Column(db.Float, nullable=False)
    temperatura_agua = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=agora)
    tanque_id = db.Column(db.Integer, db.ForeignKey('tanque.id'), nullable=False)


class RegistroTrato(db.Model):
    """Cada vez que o produtor joga ração no tanque."""
    __tablename__ = 'registro_trato'

    id = db.Column(db.Integer, primary_key=True)
    quantidade_kg = db.Column(db.Float, nullable=False)
    # Quanto realmente saiu do estoque (pode ser menos que o trato,
    # se o estoque estava acabando). Usado para desfazer o trato.
    descontado_kg = db.Column(db.Float, default=0)
    data = db.Column(db.DateTime, default=agora)
    tanque_id = db.Column(db.Integer, db.ForeignKey('tanque.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class EstoqueRacao(db.Model):
    """Depósito de ração de cada usuário."""
    __tablename__ = 'estoque_racao'

    id = db.Column(db.Integer, primary_key=True)
    quantidade_kg = db.Column(db.Float, nullable=False, default=0.0)
    capacidade_kg = db.Column(db.Float, default=500)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


class Atividade(db.Model):
    """Histórico de tudo que foi feito no sistema."""
    __tablename__ = 'atividade'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    autor = db.Column(db.String(100))
    # tanque | biometria | trato | estoque | mortalidade
    tipo = db.Column(db.String(30), nullable=False)
    descricao = db.Column(db.String(300), nullable=False)
    # Sem ForeignKey de propósito: o histórico continua existindo
    # mesmo depois que o tanque é excluído.
    tanque_id = db.Column(db.Integer, nullable=True)
    criado_em = db.Column(db.DateTime, default=agora)
