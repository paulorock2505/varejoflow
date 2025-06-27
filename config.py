# config.py
import os

class Config:
    # Tente obter os valores de variáveis de ambiente ou use valores padrão
    SECRET_KEY = os.environ.get("SECRET_KEY") or "muito_secreto_aqui"
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or "postgresql://postgres:P4ul0L31t3@localhost/omnirider"
    SESSION_TYPE = "filesystem"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
