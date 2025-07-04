# app.py

import os
from flask import Flask, redirect, url_for, session
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

from config import Config
from extensions import db, init_app as init_extensions, scheduler
from models import User

from routes import init_app as register_routes
from routes.main_routes import bp as main_bp
from routes.amazon_routes import list_products_manage


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # garante que haja uma SECRET_KEY (cookie‐session)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.urandom(24)

    # inicializa SQLAlchemy, Flask-Session e APScheduler
    init_extensions(app)

    # cria tabelas e usuário admin
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
            db.session.rollback()

    # registra blueprints
    register_routes(app)
    app.register_blueprint(main_bp, url_prefix="/main")

    # rota extra Amazon
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


app = create_app()

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="0.0.0.0", port=8000)
