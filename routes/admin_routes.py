# routes/admin_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from functools import wraps
from werkzeug.security import generate_password_hash
from models import User
from extensions import db

bp = Blueprint('admin', __name__, url_prefix='/admin')

# Decorator para exigir acesso de administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in") or not session.get("is_admin"):
            flash("Acesso restrito para administradores.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

# Exibir a lista de usuários
@bp.route("/users")
@admin_required
def list_users():
    users = User.query.all()
    return render_template("admin/users.html", users=users)

# Rota para criar um novo usuário
@bp.route("/users/create", methods=["GET", "POST"])
@admin_required
def create_user():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        phone = request.form.get("phone")
        document_number = request.form.get("document_number")
        password = request.form.get("password")
        is_admin = bool(request.form.get("is_admin"))
        
        # Verifica se todos os campos obrigatórios foram preenchidos
        if not username or not password or not first_name or not last_name or not phone or not document_number:
            error = "Todos os campos obrigatórios devem ser preenchidos."
        elif User.query.filter_by(username=username).first():
            error = "Usuário já existe."
        else:
            new_user = User(
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                document_number=document_number,
                password_hash=generate_password_hash(password),
                is_admin=is_admin,
                perm_trends=True,
                perm_generate_content=True,
                perm_amazon=True
            )
            db.session.add(new_user)
            db.session.commit()
            flash("Usuário criado com sucesso!", "success")
            return redirect(url_for("admin.list_users"))
    return render_template("admin/create_user.html", error=error)

# Rota para editar um usuário
@bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
        return redirect(url_for("admin.list_users"))
    
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        phone = request.form.get("phone", "").strip()
        document_number = request.form.get("document_number", "").strip()
        password = request.form.get("password", "").strip()  # Pode ser vazio se não quiser alterar a senha

        # Converter os valores de 'is_admin' e 'amazon_search_permission'
        is_admin = "True" in request.form.getlist("is_admin")
        # Se o select envia "False" quando negado, a comparação abaixo deve funcionar:
        perm_amazon = request.form.get("amazon_search_permission") == "True"
        
        # Verifica se todos os campos obrigatórios foram preenchidos
        if not username or not first_name or not last_name or not phone or not document_number:
            error = "Todos os campos obrigatórios devem ser preenchidos."
        else:
            user.username = username
            user.first_name = first_name
            user.last_name = last_name
            user.phone = phone
            user.document_number = document_number
            user.is_admin = is_admin
            user.perm_amazon = perm_amazon  # Atualiza a permissão do módulo Amazon Search
            if password:
                user.password_hash = generate_password_hash(password)
            db.session.commit()
            flash("Usuário atualizado com sucesso!", "success")
            
            # Se o usuário editado for o usuário logado, força a atualização da sessão:
            if user.id == session.get("user_id"):
                updated_user = User.query.get(user.id)
                session["is_admin"] = updated_user.is_admin
                session["perm_amazon"] = updated_user.perm_amazon
                # Log para debugar
                print("Sessão atualizada: perm_amazon =", session.get("perm_amazon"))
                print("Sessão atualizada: is_admin =", session.get("is_admin"))
            
            return redirect(url_for("admin.list_users"))
    return render_template("admin/edit_user.html", user=user, error=error)



# Rota para excluir um usuário
@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("Usuário não encontrado.", "danger")
    else:
        try:
            db.session.delete(user)
            db.session.commit()
            flash("Usuário excluído com sucesso!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao excluir usuário: {str(e)}", "danger")
    return redirect(url_for("admin.list_users"))
