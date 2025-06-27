# routes/__init__.py
from .auth_routes import bp as auth_bp
from .amazon_routes import bp as amazon_bp

# Essa atribuição permite importar de app.py com:
# from routes import auth_bp, amazon_bp
