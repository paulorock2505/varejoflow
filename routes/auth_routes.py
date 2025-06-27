from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from models import User
from models import AmazonProduct
from extensions import db
import datetime
import csv
from io import StringIO, BytesIO
from amazon_scraper import amazon_scrap_selenium
import re  # Importa o módulo re para usar regex

# Criação do blueprint com nome único 'amazon_routes'
bp = Blueprint('amazon_routes', __name__, url_prefix='/amazon')

def safe_float(val):
    """
    Tenta converter o valor para float.
    Se não conseguir (por exemplo, se o valor for uma string como "2 capacidades"),
    tenta extrair o primeiro número da string usando expressão regular e convertê-lo.
    Se nada for encontrado, retorna 0.0.
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        # Procura por números (podem conter ponto ou vírgula)
        matches = re.findall(r"[-+]?\d*[\.,]?\d+", str(val))
        if matches:
            try:
                return float(matches[0].replace(',', '.'))
            except Exception:
                return 0.0
        return 0.0
    
# Criação do blueprint com nome 'auth'
bp = Blueprint('auth', __name__)

@bp.route("/login", methods=["GET", "POST"])
def login():
    # Se o usuário já estiver logado, redireciona para a página principal
    if session.get("logged_in"):
        return redirect(url_for("main.index"))
    
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            # Limpa a sessão e define as variáveis necessárias
            session.clear()
            session["logged_in"] = True
            session["user_id"] = user.id
            session["username"] = user.username
            session["is_admin"] = user.is_admin  
            session["perm_amazon"] = user.perm_amazon
            flash("Login realizado com sucesso!", "success")
            return redirect(url_for("main.index"))
        else:
            error = "Credenciais inválidas."
    return render_template("login.html", error=error)

@bp.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sessão.", "info")
    return redirect(url_for("auth.login"))

@bp.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        phone = request.form.get("phone")
        document_number = request.form.get("document_number")
        password = request.form.get("password")
        if not username or not first_name or not last_name or not phone or not document_number or not password:
            error = "Todos os campos devem ser preenchidos."
        else:
            if User.query.filter_by(username=username).first():
                error = "Usuário já existe."
            else:
                new_user = User(
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    phone=phone,
                    document_number=document_number,
                    password_hash=generate_password_hash(password)
                )
                db.session.add(new_user)
                db.session.commit()
                flash("Usuário registrado com sucesso!", "success")
                return redirect(url_for("auth.login"))
    return render_template("register.html", error=error)

@bp.route("/change_password", methods=["GET", "POST"])
def change_password():
    if not session.get("logged_in"):
        flash("Você precisa estar logado para alterar a senha.", "warning")
        return redirect(url_for("auth.login"))
    
    error = None
    if request.method == "POST":
        old_password = request.form.get("old_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        user = User.query.get(session.get("user_id"))
        if user is None:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("auth.login"))
        if not check_password_hash(user.password_hash, old_password):
            error = "A senha atual está incorreta."
        elif new_password != confirm_password:
            error = "A nova senha e a confirmação não coincidem."
        else:
            user.password_hash = generate_password_hash(new_password)
            db.session.commit()
            flash("Senha alterada com sucesso!", "success")
            return redirect(url_for("main.index"))
    return render_template("change_password.html", error=error)

@bp.route("/search", methods=["GET", "POST"])
def amazon_search():
    # Verifica se o usuário está autenticado
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    
    # Verifica a permissão para o módulo Amazon Search
    if not session.get("perm_amazon", False):
        flash("Você não tem acesso ao módulo Amazon Search.", "danger")
        return redirect(url_for("main.index"))
    
    if request.method == "POST":
        generics = request.form.getlist("generic[]")
        tags = request.form.getlist("tag[]")
        models_list = request.form.getlist("models[]")
        list_names = request.form.getlist("list_name_group[]")  # Nomes das listas

        aggregated_products = []
        for i in range(len(generics)):
            generic = generics[i].strip()
            affiliate_tag = tags[i].strip() if i < len(tags) else ""
            models_str = models_list[i].strip() if i < len(models_list) else ""
            list_name = list_names[i].strip() if i < len(list_names) else ""
            # Se houver linhas de modelo em modelos_str, gera uma query para cada linha; caso contrário, usa apenas o termo genérico.
            queries = [f"{generic} {model.strip()}" for model in models_str.splitlines() if model.strip()] or [generic]
            for q in queries:
                produtos = amazon_scrap_selenium(q, affiliate_tag, nome_lista=list_name)
                aggregated_products.extend(produtos)
                
        print("Total de produtos extraídos:", len(aggregated_products))
        
        inserted_products = []
        for product in aggregated_products:
            new_product = AmazonProduct(
                product_type = generics[0].strip() if generics and generics[0].strip() else "Geral",
                list_name = product.get("Nome da Lista"),
                title = product.get("Title", "")[:255],
                brand = product.get("Marca do Produto", "")[:255],
                currency = product.get("Moeda", "")[:10],
                price = safe_float(product.get("Preço", 0)),
                image_url = product.get("Imagem", "")[:1000],
                product_link = product.get("Link do produto", "")[:1000],
                technical_details = product.get("Detalhes Técnicos", ""),
                additional_info = product.get("Informações Adicionais", ""),
                about_item = product.get("Sobre este Item", ""),
                user_id = user_id
            )
            db.session.add(new_product)
            inserted_products.append(new_product)
        
        db.session.commit()
        return render_template("amazon_result.html", results=inserted_products)
    else:
        return render_template("amazon_search.html")


@bp.route("/export", methods=["GET", "POST"])
def export_csv():
    # Verifica se o usuário está autenticado
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    
    # Verifica a permissão para o módulo Amazon Search
    if not session.get("perm_amazon", False):
        flash("Você não tem acesso ao módulo Amazon Search.", "danger")
        return redirect(url_for("main.index"))
    
    try:
        start_date = request.form.get("start_date")
        start_date_obj = datetime.datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.datetime.min
    except Exception:
        start_date_obj = datetime.datetime.min
        
    try:
        end_date = request.form.get("end_date")
        end_date_obj = datetime.datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.datetime.max
        end_date_obj += datetime.timedelta(days=1)
    except Exception:
        end_date_obj = datetime.datetime.max
        
    # Consulta para preencher os dropdowns
    product_types = [pt for pt, in db.session.query(AmazonProduct.product_type)
                     .filter(
                         AmazonProduct.user_id == user_id,
                         AmazonProduct.created_at >= start_date_obj,
                         AmazonProduct.created_at < end_date_obj
                     ).distinct().all()]
                     
    product_lists = [lst if lst else "Sem Nome" for lst, in
                     db.session.query(AmazonProduct.list_name)
                     .filter(
                         AmazonProduct.user_id == user_id,
                         AmazonProduct.created_at >= start_date_obj,
                         AmazonProduct.created_at < end_date_obj
                     ).distinct().all()]
    
    if request.method == "POST":
        selected_type = request.form.get("product_type_filter", "").strip()
        selected_list_name = request.form.get("list_name_filter", "").strip()
        
        query = AmazonProduct.query.filter(
            AmazonProduct.user_id == user_id,
            AmazonProduct.created_at >= start_date_obj,
            AmazonProduct.created_at < end_date_obj
        )
        if selected_type:
            query = query.filter(AmazonProduct.product_type == selected_type)
        if selected_list_name:
            query = query.filter(AmazonProduct.list_name == selected_list_name)
        
        products = query.all()
        
        si = StringIO()
        writer = csv.writer(si)
        
        fields = request.form.getlist("fields")
        if not fields:
            fields = ["product_type", "list_name", "created_at", "title", "brand", "currency",
                      "price", "image_url", "product_link", "technical_details", "additional_info", "about_item"]
        
        headers = []
        for field in fields:
            if field == "product_type":
                headers.append("Tipo de Produto")
            elif field == "list_name":
                headers.append("Nome da Lista")
            elif field == "created_at":
                headers.append("Data da Pesquisa")
            elif field == "title":
                headers.append("Title")
            elif field == "brand":
                headers.append("Marca do Produto")
            elif field == "currency":
                headers.append("Moeda")
            elif field == "price":
                headers.append("Preço")
            elif field == "image_url":
                headers.append("Imagem")
            elif field == "product_link":
                headers.append("Link do Produto")
            elif field == "technical_details":
                headers.append("Detalhes Técnicos")
            elif field == "additional_info":
                headers.append("Informações Adicionais")
            elif field == "about_item":
                headers.append("Sobre este item")
            else:
                headers.append(field)
        writer.writerow(headers)
        
        for product in products:
            row = []
            for field in fields:
                value = getattr(product, field, "")
                if isinstance(value, datetime.datetime):
                    value = value.strftime("%Y-%m-%d %H:%M:%S")
                row.append(value)
            writer.writerow(row)
        
        output = si.getvalue()
        si.close()
        mem = BytesIO()
        mem.write(output.encode("utf-8"))
        mem.seek(0)
        return send_file(mem, as_attachment=True, download_name="resultados.csv", mimetype="text/csv")
    else:
        return render_template("amazon_export.html", product_types=product_types, product_lists=product_lists)
