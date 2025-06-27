# extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session

db = SQLAlchemy()
session_ext = Session()  # Renomeado para evitar conflito com session do Flask
