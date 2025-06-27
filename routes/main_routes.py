# routes/main_routes.py
from functools import wraps
from flask import Blueprint, render_template, session, redirect, url_for

bp = Blueprint("main", __name__)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            # Se o usuário não estiver logado, redireciona para a página de login
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

@bp.route("/")
@login_required
def index():
    return render_template("index.html")
