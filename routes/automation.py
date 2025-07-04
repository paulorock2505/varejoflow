# routes/automation.py

from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, jsonify,
    session, abort
)
from datetime import datetime
from extensions import db, scheduler
from models import AutomationJob, AmazonProduct
from routes.amazon_routes import run_amazon_search, safe_float

automation_bp = Blueprint(
    'automation',
    __name__,
    url_prefix='/automation'
)


@automation_bp.route('/', methods=['GET'])
def view():
    return render_template('automation.html')


@automation_bp.route('/api/jobs')
def api_jobs():
    jobs = AutomationJob.query.order_by(AutomationJob.run_at).all()
    data = []
    for j in jobs:
        # pega primeiro nome de lista se houver
        ln = (j.params or {}).get('list_name_group', [])
        data.append({
            'id': j.id,
            'title': j.name or f"Job#{j.id}",
            'list_name': ln[0] if ln else None,
            'start': j.run_at.isoformat(),
            'allDay': False,
            'executed': j.executed
        })
    return jsonify(data)


@automation_bp.route('/api/jobs/<int:job_id>', methods=['DELETE'])
def delete_job(job_id):
    """
    Cancela e remove um job agendado.
    """
    job = AutomationJob.query.get(job_id)
    if not job:
        abort(404, "Job não encontrado")

    # remove do scheduler
    scheduler_id = f"automation_job_{job.id}"
    try:
        scheduler.remove_job(scheduler_id)
    except Exception:
        pass

    # apaga do banco
    db.session.delete(job)
    db.session.commit()
    return jsonify({"success": True, "message": "Automação removida"}), 200


@automation_bp.route('/schedule', methods=['POST'])
def schedule():
    # pega o usuário da sessão
    user_id = session.get('user_id')
    if not user_id:
        flash("Sessão expirada. Faça login novamente.", "danger")
        return redirect(url_for('auth.login'))

    generics   = request.form.getlist('generic[]')
    tags       = request.form.getlist('tag[]')
    models     = request.form.getlist('models[]')
    list_names = request.form.getlist('list_name_group[]')

    date_str = request.form.get('schedule_date', '').strip()
    time_str = request.form.get('schedule_time', '').strip()
    everyday = (request.form.get('everyday') == '1')

    if not everyday and not date_str:
        flash("Escolha uma data ou marque 'Todos os Dias'.", 'danger')
        return redirect(url_for('automation.view'))
    if not time_str:
        flash("Informe o horário no formato HH:MM.", 'danger')
        return redirect(url_for('automation.view'))

    try:
        hour, minute = map(int, time_str.split(':'))
    except ValueError:
        flash("Horário inválido. Use HH:MM.", 'danger')
        return redirect(url_for('automation.view'))

    run_at = None
    if not everyday:
        try:
            run_at = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        except ValueError:
            flash("Data ou hora inválida.", 'danger')
            return redirect(url_for('automation.view'))

    # monta params
    params = {
        'generic': generics,
        'tag': tags,
        'models': models,
        'list_name_group': list_names,
        'user_id': user_id
    }

    # cria e persiste o job
    job = AutomationJob(
        name=request.form.get('search_name', 'Agendamento'),
        params=params,
        run_at=run_at or datetime.utcnow()
    )
    db.session.add(job)
    db.session.commit()

    # agenda no scheduler
    jid = f"automation_job_{job.id}"
    if everyday:
        scheduler.add_job(
            func=_execute_job,
            trigger='cron',
            hour=hour,
            minute=minute,
            id=jid,
            args=[job.id],
            replace_existing=True
        )
    else:
        scheduler.add_job(
            func=_execute_job,
            trigger='date',
            run_date=run_at,
            id=jid,
            args=[job.id],
            replace_existing=True
        )

    flash("Automação agendada com sucesso!", "success")
    return redirect(url_for('automation.view'))


def _execute_job(job_id: int):
    # abre app context para poder usar o db
    app = scheduler.app
    with app.app_context():
        job = AutomationJob.query.get(job_id)
        if not job or job.executed:
            return

        params     = job.params or {}
        generics   = params.get('generic', [])
        tags       = params.get('tag', [])
        models     = params.get('models', [])
        list_names = params.get('list_name_group', [])
        user_id    = params.get('user_id')

        # executa scraping
        scraped = run_amazon_search(generics, tags, models)

        # persiste resultados
        scheduled_list = list_names[0] if list_names else None
        for product in scraped:
            new = AmazonProduct(
                product_type      = generics[0] if generics else "Geral",
                list_name         = scheduled_list,
                title             = product.get("Title", "")[:255],
                brand             = product.get("Marca do Produto", "")[:255],
                currency          = product.get("Moeda", "")[:10],
                price             = safe_float(product.get("Preço", 0)),
                image_url         = product.get("Imagem", "")[:1000],
                product_link      = product.get("Link do produto", "")[:1000],
                technical_details = product.get("Detalhes Técnicos", ""),
                additional_info   = product.get("Informações Adicionais", ""),
                about_item        = product.get("Sobre este Item", ""),
                user_id           = user_id
            )
            db.session.add(new)

        job.executed = True
        db.session.commit()
