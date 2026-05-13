import calendar
from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models.cliente import Cliente
from app.models.reserva import Reserva
from app.models.experiencia import TipoExperiencia

estadisticas_bp = Blueprint("estadisticas", __name__)


def _rango_mes(año, mes):
    primer_dia = datetime(año, mes, 1)
    ultimo_dia = datetime(año, mes, calendar.monthrange(año, mes)[1], 23, 59, 59)
    return primer_dia, ultimo_dia


def _iterar_meses(n):
    """Devuelve los últimos n meses como (año, mes) empezando por el más antiguo."""
    hoy = datetime.utcnow()
    meses = []
    for i in range(n - 1, -1, -1):
        mes = hoy.month - i
        año = hoy.year
        while mes <= 0:
            mes += 12
            año -= 1
        meses.append((año, mes))
    return meses


@estadisticas_bp.route("/estadisticas")
@login_required
def index():
    hoy = datetime.utcnow()

    # ── KPIs globales ────────────────────────────────────────────────────────
    total_reservas   = Reserva.query.count()
    total_ingresos   = db.session.query(func.sum(Reserva.precio)).scalar() or 0
    ticket_medio     = total_ingresos / total_reservas if total_reservas else 0
    total_disfrutados = Reserva.query.filter_by(estado="disfrutado").count()
    tasa_disfrute    = round(total_disfrutados / total_reservas * 100, 1) if total_reservas else 0
    total_clientes   = Cliente.query.count()
    sin_fecha        = Reserva.query.filter(Reserva.fecha_disfrute.is_(None),
                                            Reserva.estado != "cancelado").count()

    hace_30 = hoy - timedelta(days=30)
    hace_60 = hoy - timedelta(days=60)
    ingresos_30 = db.session.query(func.sum(Reserva.precio)).filter(
        Reserva.fecha_compra >= hace_30).scalar() or 0
    ingresos_60_30 = db.session.query(func.sum(Reserva.precio)).filter(
        Reserva.fecha_compra >= hace_60, Reserva.fecha_compra < hace_30).scalar() or 0
    variacion_ingresos = round(
        (ingresos_30 - ingresos_60_30) / ingresos_60_30 * 100, 1
    ) if ingresos_60_30 else None

    # ── Ingresos y reservas por mes (12 meses) ───────────────────────────────
    ingresos_mensuales = []
    reservas_mensuales = []
    for año, mes in _iterar_meses(12):
        inicio, fin = _rango_mes(año, mes)
        label = inicio.strftime("%b %y").capitalize()
        total_mes = db.session.query(func.sum(Reserva.precio)).filter(
            Reserva.fecha_compra >= inicio, Reserva.fecha_compra <= fin
        ).scalar() or 0
        count_mes = Reserva.query.filter(
            Reserva.fecha_compra >= inicio, Reserva.fecha_compra <= fin
        ).count()
        ingresos_mensuales.append({"mes": label, "total": round(total_mes, 2)})
        reservas_mensuales.append({"mes": label, "count": count_mes})

    # ── Por estado ───────────────────────────────────────────────────────────
    estados_raw = db.session.query(
        Reserva.estado, func.count(Reserva.id)
    ).group_by(Reserva.estado).all()
    estados_data = {e: c for e, c in estados_raw}

    # ── Por tipo de experiencia ──────────────────────────────────────────────
    por_tipo_raw = db.session.query(
        TipoExperiencia.nombre,
        TipoExperiencia.color,
        func.count(Reserva.id).label("n"),
        func.coalesce(func.sum(Reserva.precio), 0).label("ingresos"),
    ).outerjoin(Reserva, TipoExperiencia.id == Reserva.tipo_experiencia_id)\
     .group_by(TipoExperiencia.id)\
     .order_by(func.count(Reserva.id).desc())\
     .all()

    por_tipo = [
        {"nombre": r.nombre, "color": r.color,
         "count": r.n, "ingresos": round(r.ingresos, 2)}
        for r in por_tipo_raw
    ]

    # ── Reservas por día de la semana (fecha_disfrute) ───────────────────────
    # SQLite strftime %w: 0=Dom, 1=Lun, …, 6=Sáb
    dias_raw = db.session.query(
        func.strftime("%w", Reserva.fecha_disfrute).label("dia"),
        func.count(Reserva.id).label("n"),
    ).filter(Reserva.fecha_disfrute.isnot(None))\
     .group_by("dia").all()

    dias_map  = {str(d): c for d, c in dias_raw}
    dias_keys = ["1", "2", "3", "4", "5", "6", "0"]  # Lun → Dom
    dias_nombres = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    dias_data = [
        {"dia": dias_nombres[i], "count": dias_map.get(dias_keys[i], 0)}
        for i in range(7)
    ]

    # ── Horarios más populares ───────────────────────────────────────────────
    horarios_raw = db.session.query(
        Reserva.horario, func.count(Reserva.id).label("n")
    ).filter(Reserva.horario.isnot(None), Reserva.horario != "")\
     .group_by(Reserva.horario)\
     .order_by(func.count(Reserva.id).desc())\
     .limit(8).all()
    horarios_data = [{"horario": h, "count": c} for h, c in horarios_raw]

    # ── Clientes nuevos por mes (12 meses) ───────────────────────────────────
    clientes_mensuales = []
    for año, mes in _iterar_meses(12):
        inicio, fin = _rango_mes(año, mes)
        label = inicio.strftime("%b %y").capitalize()
        count = Cliente.query.filter(
            Cliente.creado_en >= inicio, Cliente.creado_en <= fin
        ).count()
        clientes_mensuales.append({"mes": label, "count": count})

    # ── Origen de clientes ───────────────────────────────────────────────────
    fuentes_raw = db.session.query(
        Cliente.fuente, func.count(Cliente.id)
    ).group_by(Cliente.fuente).all()
    fuentes_data = {f or "manual": c for f, c in fuentes_raw}

    # ── Top clientes por gasto ───────────────────────────────────────────────
    top_clientes_raw = db.session.query(
        Cliente.nombre,
        Cliente.apellido,
        func.count(Reserva.id).label("total_reservas"),
        func.coalesce(func.sum(Reserva.precio), 0).label("total_gasto"),
    ).join(Reserva, Cliente.id == Reserva.cliente_id)\
     .group_by(Cliente.id)\
     .order_by(func.sum(Reserva.precio).desc())\
     .limit(8).all()

    max_gasto = top_clientes_raw[0].total_gasto if top_clientes_raw else 1
    top_clientes = [
        {
            "nombre": f"{r.nombre} {r.apellido}".strip(),
            "total_reservas": r.total_reservas,
            "total_gasto": round(r.total_gasto, 2),
            "pct": round(r.total_gasto / max_gasto * 100, 1) if max_gasto else 0,
        }
        for r in top_clientes_raw
    ]

    # ── Reservas próximas 30 días ─────────────────────────────────────────────
    proximas_30 = Reserva.query.filter(
        Reserva.fecha_disfrute >= hoy,
        Reserva.fecha_disfrute <= hoy + timedelta(days=30),
        Reserva.estado.in_(["reservado", "pendiente"]),
    ).count()

    return render_template(
        "estadisticas/index.html",
        # KPIs
        total_reservas=total_reservas,
        total_ingresos=total_ingresos,
        ticket_medio=ticket_medio,
        tasa_disfrute=tasa_disfrute,
        total_clientes=total_clientes,
        sin_fecha=sin_fecha,
        ingresos_30=ingresos_30,
        variacion_ingresos=variacion_ingresos,
        proximas_30=proximas_30,
        # Gráficos
        ingresos_mensuales=ingresos_mensuales,
        reservas_mensuales=reservas_mensuales,
        estados_data=estados_data,
        por_tipo=por_tipo,
        dias_data=dias_data,
        horarios_data=horarios_data,
        clientes_mensuales=clientes_mensuales,
        fuentes_data=fuentes_data,
        top_clientes=top_clientes,
    )
