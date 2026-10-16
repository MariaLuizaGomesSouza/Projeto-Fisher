from datetime import datetime
from extensions import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Tanque(db.Model):
    __tablename__ = 'tanque'
    
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especie = db.Column(db.String(100), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Biometria(db.Model):
    __tablename__ = 'biometria'
    
    id = db.Column(db.Integer, primary_key=True)
    peso_medio_gramas = db.Column(db.Float, nullable=False)
    temperatura_agua = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    tanque_id = db.Column(db.Integer, db.ForeignKey('tanque.id'), nullable=False)

class EstoqueRacao(db.Model):
    __tablename__ = 'estoque_racao'
    
    id = db.Column(db.Integer, primary_key=True)
    quantidade_kg = db.Column(db.Float, nullable=False, default=0.0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class RegistroTrato(db.Model):
    __tablename__ = 'registro_trato'
    
    id = db.Column(db.Integer, primary_key=True)
    quantidade_kg = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    tanque_id = db.Column(db.Integer, db.ForeignKey('tanque.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)