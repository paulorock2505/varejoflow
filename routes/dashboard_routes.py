# routes/dashboard_routes.py
from flask import Blueprint, render_template, request, session, redirect, url_for, flash
from sqlalchemy import func, asc, desc
from models import AmazonProduct
from extensions import db
import datetime

bp = Blueprint('dashboard_routes', __name__, url_prefix='/dashboard')

@bp.route("/", methods=["GET"])
def dashboard():
    if not session.get("logged_in"):
        flash("Usuário não autenticado.", "danger")
        return redirect(url_for("auth.login"))
    
    # Pega o parâmetro de ordenação: 'asc' (menor preço) ou 'desc' (maior preço)
    order = request.args.get("order", "asc")
    
    # Define o período (por exemplo, produtos do dia atual)
    today = datetime.date.today()
    start = datetime.datetime.combine(today, datetime.time.min)
    end = datetime.datetime.combine(today, datetime.time.max)
    
    # Seleciona a função de agregação de acordo com a ordenação
    if order == "asc":
        price_func = func.min(AmazonProduct.price)
    else:
        price_func = func.max(AmazonProduct.price)
    
    # Agrega os dados por marca
    data_query = db.session.query(
        AmazonProduct.brand,
        price_func.label("price_index")
    ).filter(
        AmazonProduct.user_id == session.get("user_id"),
        AmazonProduct.created_at >= start,
        AmazonProduct.created_at <= end
    ).group_by(AmazonProduct.brand)
    
    if order == "asc":
        data_query = data_query.order_by(asc(price_func))
    else:
        data_query = data_query.order_by(desc(price_func))
    
    results = data_query.all()
    chart_data = [{"brand": r[0], "price_index": r[1]} for r in results]
    
    return render_template("dashboard.html", chart_data=chart_data, order=order)
