import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('FISHER_SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = os.environ.get('FISHER_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuração de Sessão Segura (Segurança da Informação)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'