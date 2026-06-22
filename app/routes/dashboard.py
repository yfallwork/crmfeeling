from datetime import datetime, timedelta
from flask import Blueprint, render_template
from flask_login import login_required
from sqlalchemy import func
from app.extensions import db
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.reserva import Reserva

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    hoy    = datetime.utcnow().date()
    hace_30 = datetime.utcnow() - timedelta(days=30)

    stats = {
        "total_clientes":      Cliente.query.count(),
        "clientes_mes":        Cliente.query.filter(Cliente.creado_en >= hace_30).count(),
        "reservas_pendientes": Reserva.query.filter(
            Reserva.cliente_id.isnot(None), Reserva.estado == "pendiente"
        ).count(),
        "reservas_reservadas": Reserva.query.filter(
            Reserva.cliente_id.isnot(None), Reserva.estado == "reservado"
        ).count(),
        "proximas_7_dias": Reserva.query.filter(
            Reserva.cliente_id.isnot(None),
            Reserva.fecha_disfrute >= datetime.utcnow(),
            Reserva.fecha_disfrute <= datetime.utcnow() + timedelta(days=7),
            Reserva.estado.in_(["reservado", "pendiente"]),
        ).count(),
        "ingresos_mes": db.session.query(func.sum(Reserva.precio)).filter(
            Reserva.fecha_compra >= hace_30
        ).scalar() or 0,
    }

    tb_stats = {
        "total_empresas": Empresa.query.filter_by(activo=True).count(),
        "reservas_pendientes": Reserva.query.filter(
            Reserva.empresa_id.isnot(None), Reserva.estado == "pendiente"
        ).count(),
        "proximas_7_dias": Reserva.query.filter(
            Reserva.empresa_id.isnot(None),
            Reserva.fecha_disfrute >= datetime.utcnow(),
            Reserva.fecha_disfrute <= datetime.utcnow() + timedelta(days=7),
            Reserva.estado.in_(["reservado", "pendiente"]),
        ).count(),
        "ingresos_mes": db.session.query(func.sum(Reserva.precio)).filter(
            Reserva.empresa_id.isnot(None),
            Reserva.fecha_compra >= hace_30,
        ).scalar() or 0,
    }

    proximas = (
        Reserva.query
        .filter(
            Reserva.cliente_id.isnot(None),
            Reserva.fecha_disfrute >= datetime.utcnow(),
            Reserva.estado.in_(["reservado", "pendiente"]),
        )
        .order_by(Reserva.fecha_disfrute)
        .limit(10)
        .all()
    )

    proximas_tb = (
        Reserva.query
        .filter(
            Reserva.empresa_id.isnot(None),
            Reserva.fecha_disfrute >= datetime.utcnow(),
            Reserva.estado.in_(["reservado", "pendiente"]),
        )
        .order_by(Reserva.fecha_disfrute)
        .limit(5)
        .all()
    )

    sin_fecha = (
        Reserva.query
        .filter(
            Reserva.cliente_id.isnot(None),
            Reserva.fecha_disfrute.is_(None),
            Reserva.estado == "pendiente",
        )
        .order_by(Reserva.fecha_compra.desc())
        .limit(8)
        .all()
    )

    _MESES_ES = ["Ene","Feb","Mar","Abr","May","Jun","Jul","Ago","Sep","Oct","Nov","Dic"]
    meses_data = []
    anyo_act, mes_act = datetime.utcnow().year, datetime.utcnow().month
    for i in range(5, -1, -1):
        m = mes_act - i
        y = anyo_act
        while m <= 0:
            m += 12
            y -= 1
        inicio = datetime(y, m, 1)
        fin    = datetime(y + 1, 1, 1) if m == 12 else datetime(y, m + 1, 1)
        count  = Reserva.query.filter(
            Reserva.fecha_compra >= inicio, Reserva.fecha_compra < fin
        ).count()
        meses_data.append({"mes": f"{_MESES_ES[m - 1]} {y}", "count": count})

    return render_template(
        "dashboard/index.html",
        stats=stats,
        tb_stats=tb_stats,
        proximas=proximas,
        proximas_tb=proximas_tb,
        sin_fecha=sin_fecha,
        meses_data=meses_data,
        hoy=hoy,
    )
