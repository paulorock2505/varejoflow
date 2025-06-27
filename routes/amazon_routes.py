from flask import Blueprint, render_template, request, session, redirect, url_for, flash, send_file
from models import AmazonProduct  # Este modelo utiliza o "db" importado de extensions.py
from extensions import db
import datetime
import csv
from io import StringIO, BytesIO
from amazon_scraper import amazon_scrap_selenium
import re  # Para uso de expressões regulares
from sqlalchemy import func, asc, desc  # Para agregação e ordenação

bp = Blueprint('amazon', __name__, url_prefix='/amazon')

def safe_float(val):
    """
    Tenta converter o valor para float.
    Se não conseguir, tenta extrair o primeiro número da string utilizando regex.
    Se nada for encontrado, retorna 0.0.
    """
    try:
        return float(val)
    except (ValueError, TypeError):
        matches = re.findall(r"[-+]?\d*[\.,]?\d+", str(val))
        if matches:
            try:
                return float(matches[0].replace(',', '.'))
            except Exception:
                return 0.0
        return 0.0

@bp.route("/search", methods=["GET", "POST"])
def amazon_search():
    # Verifica se o usuário está autenticado e possui permissão
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
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
            # Se houver linhas de modelo, gera uma query para cada linha; senão, usa somente o termo genérico.
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
    # Verifica se o usuário está autenticado e tem permissão
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
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


@bp.route("/dashboard", methods=["GET"])
def dashboard():
    # Rota para o dashboard com filtros por data, lista, marca e ranking
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    
    selected_date = request.args.get("date", str(datetime.date.today()))
    order = request.args.get("order", "asc")
    selected_list = request.args.get("list_name", "")
    selected_brand = request.args.get("brand", "")
    ranking_order = request.args.get("ranking_order", "desc")
    
    try:
        start_date = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
    except Exception:
        start_date = datetime.datetime.today()
        selected_date = str(start_date.date())
    end_date = start_date + datetime.timedelta(days=1)
    
    price_func = func.min(AmazonProduct.price) if order == "asc" else func.max(AmazonProduct.price)
    
    query = db.session.query(
        AmazonProduct.brand,
        price_func.label("price_index")
    ).filter(
        AmazonProduct.user_id == user_id,
        AmazonProduct.created_at >= start_date,
        AmazonProduct.created_at < end_date
    )
    if selected_list:
        query = query.filter(AmazonProduct.list_name == selected_list)
    query = query.group_by(AmazonProduct.brand)
    query = query.order_by(asc(price_func) if order == "asc" else desc(price_func))
    results = query.all()
    chart_data = [{"brand": r[0], "price_index": r[1]} for r in results]
    
    lists_query = db.session.query(AmazonProduct.list_name).filter(
        AmazonProduct.user_id == user_id,
        AmazonProduct.list_name.isnot(None),
        AmazonProduct.list_name != ""
    ).distinct().all()
    available_lists = sorted({l[0] for l in lists_query})
    
    brand_query = None
    if selected_list:
        brand_query = db.session.query(AmazonProduct.brand).filter(
            AmazonProduct.user_id == user_id,
            AmazonProduct.list_name == selected_list,
            AmazonProduct.brand.isnot(None),
            AmazonProduct.brand != ""
        ).distinct().all()
    else:
        brand_query = db.session.query(AmazonProduct.brand).filter(
            AmazonProduct.user_id == user_id,
            AmazonProduct.brand.isnot(None),
            AmazonProduct.brand != ""
        ).distinct().all()
    available_brands = sorted({b[0] for b in brand_query})
    
    ranking_query = db.session.query(
        AmazonProduct.title,
        AmazonProduct.price
    ).filter(
        AmazonProduct.user_id == user_id,
        AmazonProduct.created_at >= start_date,
        AmazonProduct.created_at < end_date
    )
    if selected_list:
        ranking_query = ranking_query.filter(AmazonProduct.list_name == selected_list)
    if selected_brand:
        ranking_query = ranking_query.filter(AmazonProduct.brand == selected_brand)
    ranking_query = ranking_query.order_by(asc(AmazonProduct.price) if ranking_order == "asc" else desc(AmazonProduct.price)).limit(10)
    ranking_results = ranking_query.all()
    ranking_data = [{"title": r.title, "price_index": float(r.price)} for r in ranking_results]
    
    return render_template("dashboard.html",
                           selected_date=selected_date,
                           order=order,
                           selected_list=selected_list,
                           selected_brand=selected_brand,
                           ranking_order=ranking_order,
                           available_lists=available_lists,
                           available_brands=available_brands,
                           chart_data=chart_data,
                           ranking_data=ranking_data)

# ===== ROTAS PARA GERENCIAR OS PRODUTOS =====

# Rota para listar os produtos com opção de filtrar por nome de lista e por data
@bp.route("/products/manage", methods=["GET"])
def list_products_manage():
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    
    selected_list = request.args.get("list_name", None)
    selected_date = request.args.get("date", None)
    
    query = AmazonProduct.query.filter_by(user_id=user_id)
    if selected_list:
        query = query.filter(AmazonProduct.list_name == selected_list)
    if selected_date:
        try:
            date_obj = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
            next_day = date_obj + datetime.timedelta(days=1)
            query = query.filter(AmazonProduct.created_at >= date_obj,
                                 AmazonProduct.created_at < next_day)
        except ValueError:
            flash("Formato de data inválido. Utilize AAAA-MM-DD.", "danger")
    
    products = query.order_by(AmazonProduct.created_at.desc()).all()
    
    list_names = [l[0] for l in db.session.query(AmazonProduct.list_name)
                  .filter(AmazonProduct.user_id == user_id,
                          AmazonProduct.list_name.isnot(None),
                          AmazonProduct.list_name != "")
                  .distinct().all()]
    
    return render_template("amazon_products_list.html",
                           products=products,
                           list_names=list_names,
                           selected_list=selected_list,
                           selected_date=selected_date)

# Rota para editar um produto
@bp.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    product = AmazonProduct.query.filter_by(id=product_id, user_id=user_id).first_or_404()
    if request.method == "POST":
        product.title = request.form.get("title", product.title)
        product.brand = request.form.get("brand", product.brand)
        try:
            product.price = float(request.form.get("price", product.price))
        except ValueError:
            flash("Preço inválido.", "danger")
            return redirect(url_for("amazon.edit_product", product_id=product.id))
        product.technical_details = request.form.get("technical_details", product.technical_details)
        product.additional_info = request.form.get("additional_info", product.additional_info)
        product.about_item = request.form.get("about_item", product.about_item)
        db.session.commit()
        flash("Produto atualizado com sucesso!", "success")
        return redirect(url_for("amazon.list_products_manage"))
    return render_template("amazon_edit_product.html", product=product)

# Rota para excluir um produto via POST
@bp.route("/products/delete/<int:product_id>", methods=["POST"])
def delete_product(product_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    product = AmazonProduct.query.filter_by(id=product_id, user_id=user_id).first_or_404()
    db.session.delete(product)
    db.session.commit()
    flash("Produto excluído com sucesso!", "success")
    return redirect(url_for("amazon.list_products_manage"))
