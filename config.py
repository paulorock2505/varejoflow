# config.py

import os

# diretório base do projeto para arquivos locais
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # segurança da sessão em cookie
    SECRET_KEY = os.environ.get("SECRET_KEY") or "muito_secreto_aqui"

    # URI do banco (prioriza var. de ambiente DATABASE_URL, senão SQLite local)
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL")
        or f"sqlite:///{os.path.join(BASE_DIR, 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask-Session em sistema de arquivos
    SESSION_TYPE       = "filesystem"
    SESSION_FILE_DIR   = os.environ.get("SESSION_FILE_DIR") or os.path.join(BASE_DIR, "flask_session")
    SESSION_PERMANENT  = False
    SESSION_USE_SIGNER = True
    SESSION_FILE_MODE  = 0o600

    # APScheduler (cron/data única) no horário de São Paulo
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE    = "America/Sao_Paulo"
