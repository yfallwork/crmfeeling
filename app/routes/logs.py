from flask import Blueprint, render_template, request
from flask_login import login_required
from app.models.log import Log
from app.models.usuario import Usuario
from app.extensions import db

logs_bp = Blueprint("logs", __name__)


@logs_bp.route("/actividad")
@login_required
def index():
    page      = request.args.get("page", 1, type=int)
    usuario   = request.args.get("usuario", "")
    accion    = request.args.get("accion", "")
    origen    = request.args.get("origen", "")
    fecha_ini = request.args.get("fecha_ini", "")
    fecha_fin = request.args.get("fecha_fin", "")

    query = Log.query

    if usuario:
        query = query.filter(Log.usuario_nombre.ilike(f"%{usuario}%"))
    if accion:
        query = query.filter(Log.accion == accion)
    if origen:
        query = query.filter(Log.origen == origen)
    if fecha_ini:
        from datetime import datetime
        try:
            query = query.filter(Log.fecha >= datetime.strptime(fecha_ini, "%Y-%m-%d"))
        except ValueError:
            pass
    if fecha_fin:
        from datetime import datetime, timedelta
        try:
            query = query.filter(Log.fecha < datetime.strptime(fecha_fin, "%Y-%m-%d") + timedelta(days=1))
        except ValueError:
            pass

    logs = query.order_by(Log.fecha.desc()).paginate(page=page, per_page=40, error_out=False)

    acciones_distintas = [r[0] for r in db.session.query(Log.accion).distinct().all()]
    usuarios_distintos = [r[0] for r in db.session.query(Log.usuario_nombre).distinct().all()]

    return render_template(
        "logs/index.html",
        logs=logs,
        acciones=sorted(acciones_distintas),
        usuarios=sorted(usuarios_distintos),
        filtro_usuario=usuario,
        filtro_accion=accion,
        filtro_origen=origen,
        filtro_fecha_ini=fecha_ini,
        filtro_fecha_fin=fecha_fin,
    )
