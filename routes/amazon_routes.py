# routes/amazon_routes.py

from flask import (
    Blueprint, render_template, request, session,
    redirect, url_for, flash, send_file, jsonify
)
from models import AmazonProduct, List
from extensions import db
import datetime
import csv
from io import StringIO, BytesIO
from amazon_scraper import amazon_scrap_selenium
import re
from sqlalchemy import func, asc, desc
from math import ceil

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


@bp.route('/save_list', methods=['POST'])
def save_list():
    """
    Rota AJAX para salvar uma nova lista de buscas.
    Recebe JSON { list_name: "<nome>" }.
    """
    data = request.get_json() or {}
    name = data.get('list_name', '').strip()
    if not name:
        return jsonify(error="O nome da lista é obrigatório"), 400

    if List.query.filter_by(name=name).first():
        return jsonify(error="Já existe uma lista com esse nome."), 409

    nova = List(name=name)
    db.session.add(nova)
    db.session.commit()
    return jsonify(message="Lista salva com sucesso"), 201


@bp.route("/search", methods=["GET", "POST"])
def amazon_search():
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    if not session.get("perm_amazon", False):
        flash("Você não tem acesso ao módulo Amazon Search.", "danger")
        return redirect(url_for("main.index"))

    if request.method == "POST":
        generics    = request.form.getlist("generic[]")
        tags        = request.form.getlist("tag[]")
        models_list = request.form.getlist("models[]")
        list_names  = request.form.getlist("list_name_group[]")

        aggregated_products = []
        for i in range(len(generics)):
            generic       = generics[i].strip()
            affiliate_tag = tags[i].strip() if i < len(tags) else ""
            models_str    = models_list[i].strip() if i < len(models_list) else ""
            list_name     = list_names[i].strip() if i < len(list_names) else ""
            queries = [f"{generic} {m.strip()}" for m in models_str.splitlines() if m.strip()] or [generic]

            for q in queries:
                produtos = amazon_scrap_selenium(q, affiliate_tag, nome_lista=list_name)
                aggregated_products.extend(produtos)

        inserted_products = []
        for product in aggregated_products:
            new_product = AmazonProduct(
                product_type       = generics[0].strip() if generics and generics[0].strip() else "Geral",
                list_name          = product.get("Nome da Lista"),
                title              = product.get("Title", "")[:255],
                brand              = product.get("Marca do Produto", "")[:255],
                currency           = product.get("Moeda", "")[:10],
                price              = safe_float(product.get("Preço", 0)),
                image_url          = product.get("Imagem", "")[:1000],
                product_link       = product.get("Link do produto", "")[:1000],
                technical_details  = product.get("Detalhes Técnicos", ""),
                additional_info    = product.get("Informações Adicionais", ""),
                about_item         = product.get("Sobre este Item", ""),
                user_id            = user_id
            )
            db.session.add(new_product)
            inserted_products.append(new_product)

        db.session.commit()
        return render_template("amazon_result.html", results=inserted_products)
    else:
        return render_template("amazon_search.html")


@bp.route("/export", methods=["GET", "POST"])
def export_csv():
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    if not session.get("perm_amazon", False):
        flash("Você não tem acesso ao módulo Amazon Search.", "danger")
        return redirect(url_for("main.index"))

    # Filtrar datas
    try:
        start_date = request.form.get("start_date")
        dt_start   = datetime.datetime.strptime(start_date, "%Y-%m-%d") if start_date else datetime.datetime.min
    except:
        dt_start = datetime.datetime.min

    try:
        end_date = request.form.get("end_date")
        dt_end   = (datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1)) if end_date else datetime.datetime.max
    except:
        dt_end = datetime.datetime.max

    # Montar filtros dinâmicos para dropdowns
    product_types = [pt for pt, in db.session.query(AmazonProduct.product_type)
                     .filter(AmazonProduct.user_id==user_id,
                             AmazonProduct.created_at>=dt_start,
                             AmazonProduct.created_at<dt_end)
                     .distinct().all()]

    product_lists = [lst if lst else "Sem Nome" for lst, in
                     db.session.query(AmazonProduct.list_name)
                     .filter(AmazonProduct.user_id==user_id,
                             AmazonProduct.created_at>=dt_start,
                             AmazonProduct.created_at<dt_end)
                     .distinct().all()]

    if request.method == "POST":
        selected_type      = request.form.get("product_type_filter", "").strip()
        selected_list_name = request.form.get("list_name_filter", "").strip()

        query = AmazonProduct.query.filter(
            AmazonProduct.user_id==user_id,
            AmazonProduct.created_at>=dt_start,
            AmazonProduct.created_at<dt_end
        )
        if selected_type:
            query = query.filter(AmazonProduct.product_type==selected_type)
        if selected_list_name:
            query = query.filter(AmazonProduct.list_name==selected_list_name)

        products = query.all()

        si = StringIO()
        writer = csv.writer(si)

        fields = request.form.getlist("fields") or [
            "product_type","list_name","created_at","title","brand","currency",
            "price","image_url","product_link","technical_details","additional_info","about_item"
        ]

        # Cabeçalhos
        headers = []
        for field in fields:
            mapping = {
                "product_type": "Tipo de Produto",
                "list_name":    "Nome da Lista",
                "created_at":   "Data da Pesquisa",
                "title":        "Title",
                "brand":        "Marca do Produto",
                "currency":     "Moeda",
                "price":        "Preço",
                "image_url":    "Imagem",
                "product_link": "Link do Produto",
                "technical_details": "Detalhes Técnicos",
                "additional_info":   "Informações Adicionais",
                "about_item":        "Sobre este item"
            }
            headers.append(mapping.get(field, field))
        writer.writerow(headers)

        # Linhas
        for product in products:
            row = []
            for field in fields:
                val = getattr(product, field, "")
                if isinstance(val, datetime.datetime):
                    val = val.strftime("%Y-%m-%d %H:%M:%S")
                row.append(val)
            writer.writerow(row)

        output = si.getvalue()
        si.close()
        mem = BytesIO()
        mem.write(output.encode("utf-8"))
        mem.seek(0)
        return send_file(mem,
                         as_attachment=True,
                         download_name="resultados.csv",
                         mimetype="text/csv")
    else:
        return render_template("amazon_export.html",
                               product_types=product_types,
                               product_lists=product_lists)


@bp.route("/dashboard", methods=["GET"])
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))

    selected_date   = request.args.get("date", str(datetime.date.today()))
    order           = request.args.get("order", "asc")
    selected_list   = request.args.get("list_name", "")
    selected_brand  = request.args.get("brand", "")
    ranking_order   = request.args.get("ranking_order", "desc")

    try:
        dt = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
    except:
        dt = datetime.datetime.today()
        selected_date = str(dt.date())
    dt_end = dt + datetime.timedelta(days=1)

    price_func = func.min(AmazonProduct.price) if order == "asc" else func.max(AmazonProduct.price)
    q = db.session.query(
        AmazonProduct.brand,
        price_func.label("price_index")
    ).filter(
        AmazonProduct.user_id==user_id,
        AmazonProduct.created_at>=dt,
        AmazonProduct.created_at<dt_end
    )
    if selected_list:
        q = q.filter(AmazonProduct.list_name==selected_list)
    q = q.group_by(AmazonProduct.brand)
    q = q.order_by(asc(price_func) if order=="asc" else desc(price_func))
    results = q.all()
    chart_data   = [{"brand": r[0], "price_index": r[1]} for r in results]

    lists_query = db.session.query(AmazonProduct.list_name).filter(
        AmazonProduct.user_id==user_id,
        AmazonProduct.list_name.isnot(None),
        AmazonProduct.list_name!=""
    ).distinct().all()
    available_lists = sorted({l[0] for l in lists_query})

    if selected_list:
        brand_query = db.session.query(AmazonProduct.brand).filter(
            AmazonProduct.user_id==user_id,
            AmazonProduct.list_name==selected_list,
            AmazonProduct.brand.isnot(None),
            AmazonProduct.brand!=""
        ).distinct().all()
    else:
        brand_query = db.session.query(AmazonProduct.brand).filter(
            AmazonProduct.user_id==user_id,
            AmazonProduct.brand.isnot(None),
            AmazonProduct.brand!=""
        ).distinct().all()
    available_brands = sorted({b[0] for b in brand_query})

    ranking_q = db.session.query(
        AmazonProduct.title,
        AmazonProduct.price
    ).filter(
        AmazonProduct.user_id==user_id,
        AmazonProduct.created_at>=dt,
        AmazonProduct.created_at<dt_end
    )
    if selected_list:
        ranking_q = ranking_q.filter(AmazonProduct.list_name==selected_list)
    if selected_brand:
        ranking_q = ranking_q.filter(AmazonProduct.brand==selected_brand)
    ranking_q = ranking_q.order_by(
        asc(AmazonProduct.price) if ranking_order=="asc" else desc(AmazonProduct.price)
    ).limit(10)
    ranking_results = ranking_q.all()
    ranking_data    = [{"title": r.title, "price_index": float(r.price)} for r in ranking_results]

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


@bp.route("/products/manage", methods=["GET"])
def list_products_manage():
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))

    # filtros
    selected_list = request.args.get("list_name", None)
    selected_date = request.args.get("date", None)

    # paginação
    page      = request.args.get("page", 1, type=int)
    raw_limit = request.args.get("limit", 10)
    limit     = None if raw_limit == 'Todos' else int(raw_limit)

    # consulta base
    query = AmazonProduct.query.filter_by(user_id=user_id)
    if selected_list:
        query = query.filter(AmazonProduct.list_name == selected_list)
    if selected_date:
        try:
            dt_obj   = datetime.datetime.strptime(selected_date, "%Y-%m-%d")
            next_day = dt_obj + datetime.timedelta(days=1)
            query = query.filter(
                AmazonProduct.created_at >= dt_obj,
                AmazonProduct.created_at < next_day
            )
        except ValueError:
            flash("Formato de data inválido. Utilize AAAA-MM-DD.", "danger")

    # total de itens
    total_items = query.count()

    # aplica paginação
    if not limit:
        products     = query.order_by(AmazonProduct.created_at.desc()).all()
        total_pages  = 1
        current_page = 1
    else:
        total_pages  = ceil(total_items / limit) or 1
        current_page = max(1, min(page, total_pages))
        offset       = (current_page - 1) * limit
        products     = (query
                          .order_by(AmazonProduct.created_at.desc())
                          .offset(offset)
                          .limit(limit)
                          .all())

    # nomes de lista para filtro
    list_names = [l[0] for l in db.session.query(AmazonProduct.list_name)
                  .filter(
                      AmazonProduct.user_id==user_id,
                      AmazonProduct.list_name.isnot(None),
                      AmazonProduct.list_name!=""
                  ).distinct().all()]

    return render_template(
        "amazon_products_list.html",
        products=products,
        total_items=total_items,
        current_page=current_page,
        total_pages=total_pages,
        selected_limit=raw_limit,
        list_names=list_names,
        selected_list=selected_list,
        selected_date=selected_date
    )


@bp.route("/products/edit/<int:product_id>", methods=["GET", "POST"])
def edit_product(product_id):
    user_id = session.get("user_id")
    if not user_id:
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))

    product = AmazonProduct.query.filter_by(id=product_id, user_id=user_id).first_or_404()

    if request.method == "POST":
        product.title              = request.form.get("title", product.title)
        product.brand              = request.form.get("brand", product.brand)
        try:
            product.price = float(request.form.get("price", product.price))
        except ValueError:
            flash("Preço inválido.", "danger")
            return redirect(url_for("amazon.edit_product", product_id=product.id))
        product.technical_details  = request.form.get("technical_details", product.technical_details)
        product.additional_info    = request.form.get("additional_info", product.additional_info)
        product.about_item         = request.form.get("about_item", product.about_item)
        db.session.commit()
        flash("Produto atualizado com sucesso!", "success")
        return redirect(url_for("amazon.list_products_manage"))

    return render_template("amazon_edit_product.html", product=product)


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


def run_amazon_search(generic_terms, tags, models):
    """
    Executa buscas na Amazon para combinações de termos, tags e modelos.
    Utilizado por outros módulos, ex. routes.automation.
    """
    results = []
    for i in range(len(generic_terms)):
        generic    = generic_terms[i].strip()
        tag        = tags[i].strip() if i < len(tags) else ""
        model_lines = models[i].strip().splitlines() if i < len(models) else []

        queries = [f"{generic} {m.strip()}" for m in model_lines if m.strip()] or [generic]
        for query in queries:
            produtos = amazon_scrap_selenium(query, tag)
            results.extend(produtos)

    print(f"Busca automática retornou {len(results)} produtos.")
    return results
