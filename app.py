# app.py
from flask import Flask, redirect, url_for, session
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError
from config import Config
from extensions import db, session_ext
from models import User

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Inicializa extensões
    db.init_app(app)
    session_ext.init_app(app)

    # Cria schema e faz seed seguro com tratamento de concorrência
    with app.app_context():
        db.create_all()
        admin = User(
            username="admin",
            first_name="Admin",
            last_name="User",
            phone="",
            document_number="",
            password_hash=generate_password_hash("senha123"),
            is_admin=True,
            perm_trends=True,
            perm_generate_content=True,
            perm_amazon=True
        )
        try:
            db.session.add(admin)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()  # Já existe um admin, ignora erro

    # Registra blueprints
    from routes import (
        main_routes, auth_routes,
        amazon_routes, admin_routes,
        dashboard_routes
    )
    app.register_blueprint(main_routes.bp)
    app.register_blueprint(auth_routes.bp, url_prefix="/auth")
    app.register_blueprint(amazon_routes.bp)
    app.register_blueprint(admin_routes.bp)
    app.register_blueprint(dashboard_routes.bp, url_prefix="/dashboard")

    # URL extra
    from routes.amazon_routes import list_products_manage
    app.add_url_rule(
        "/amazon/products",
        endpoint="amazon.list_products",
        view_func=list_products_manage
    )

    @app.route("/")
    def index():
        if not session.get("logged_in"):
            return redirect(url_for("auth.login"))
        return redirect(url_for("main.index"))

    return app

# Garante 'app' para Gunicorn
app = create_app()

if __name__ == "__main__":
    app.run()
