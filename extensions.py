# extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from flask_apscheduler import APScheduler

# instâncias das extensões
db          = SQLAlchemy()
session_ext = Session()

# usa Flask-APScheduler em vez de BackgroundScheduler puro,
# para respeitar SCHEDULER_TIMEZONE definido em config.py
scheduler   = APScheduler()

def init_app(app):
    """
    Inicializa todas as extensões no app Flask.
    Deve ser chamado em app.py após app.config.
    """
    db.init_app(app)
    session_ext.init_app(app)
    scheduler.init_app(app)
    scheduler.start()
