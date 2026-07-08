from datetime import datetime, date as _date
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from sqlalchemy.orm import joinedload
from app.extensions import db
from app.models.reserva import Reserva
from app.services.log_service import registrar_log

calendario_bp = Blueprint("calendario", __name__)


@calendario_bp.route("/")
@login_required
def index():
    from app.models.experiencia import TipoExperiencia
    tipos = TipoExperiencia.query.filter_by(activo=True).order_by(TipoExperiencia.nombre).all()
    return render_template("calendario/index.html", tipos_experiencia=tipos)


def _con_relaciones(query):
    """Precarga cliente, empresa y tipo_experiencia en una sola consulta (evita N+1)."""
    return query.options(
        joinedload(Reserva.cliente),
        joinedload(Reserva.empresa),
        joinedload(Reserva.tipo_experiencia),
    )


@calendario_bp.route("/eventos")
@login_required
def eventos():
    # Devolvemos todos los eventos con fecha; FullCalendar filtra los visibles
    # según la vista actual. Evitamos el filtro por rango que SQLite maneja
    # de forma inconsistente con los timestamps de FullCalendar.
    reservas = (
        _con_relaciones(Reserva.query)
        .filter(Reserva.fecha_disfrute.isnot(None))
        .order_by(Reserva.fecha_disfrute)
        .all()
    )
    return jsonify([r.to_calendar_event() for r in reservas])


@calendario_bp.route("/pendientes")
@login_required
def pendientes():
    reservas = (
        _con_relaciones(Reserva.query)
        .filter(Reserva.fecha_disfrute.is_(None))
        .filter(Reserva.estado.in_(["pendiente", "reservado"]))
        .order_by(Reserva.fecha_compra.desc())
        .all()
    )

    def contacto(r, campo):
        if r.cliente:
            return getattr(r.cliente, campo) or ""
        if r.empresa:
            return getattr(r.empresa, campo) or ""
        return ""

    return jsonify([
        {
            "id": r.id,
            "cliente": r.nombre_reservante,
            "email": contacto(r, "email"),
            "telefono": contacto(r, "telefono"),
            "experiencia": r.tipo_experiencia.nombre,
            "fecha_compra": r.fecha_compra.strftime("%d/%m/%Y") if r.fecha_compra else "",
            "estado": r.estado,
            "color": r.color,
            "woo_order_id": r.woo_order_id,
            "es_teambuilding": r.es_teambuilding,
        }
        for r in reservas
    ])


@calendario_bp.route("/aperturas")
@login_required
def aperturas():
    from app.models.fecha_apertura import FechaApertura
    items = (
        FechaApertura.query
        .options(joinedload(FechaApertura.tipo_experiencia))
        .order_by(FechaApertura.fecha)
        .all()
    )

    # Una sola consulta agrupada por fecha en vez de 1 COUNT por apertura.
    conteos_raw = (
        db.session.query(
            db.func.date(Reserva.fecha_disfrute).label("fecha"),
            db.func.count(Reserva.id).label("n"),
        )
        .filter(Reserva.fecha_disfrute.isnot(None))
        .group_by("fecha")
        .all()
    )
    conteos = {c.fecha: c.n for c in conteos_raw}

    result = []
    for a in items:
        n = conteos.get(a.fecha.isoformat(), 0)
        label = a.tipo_experiencia.nombre if a.tipo_experiencia else "Todas"
        ocupacion = f"{n}/{a.capacidad_ideal}" if a.capacidad_ideal else str(n)
        result.append({
            "id":    f"apertura-{a.id}",
            "title": f"🟢 {label} ({ocupacion})",
            "start": a.fecha.isoformat(),
            "allDay": True,
            "backgroundColor": "#bbf7d0",
            "borderColor":     "#16a34a",
            "textColor":       "#15803d",
            "extendedProps": {
                "tipo":           "apertura",
                "apertura_id":    a.id,
                "notas":          a.notas or "",
                "n_reservas":     n,
                "capacidad_ideal": a.capacidad_ideal,
                "tipo_exp_id":    a.tipo_experiencia_id,
                "tipo_exp_nombre": label,
                "fecha_iso":      a.fecha.isoformat(),
            },
        })
    return jsonify(result)


@calendario_bp.route("/aperturas/disponibles")
@login_required
def aperturas_disponibles():
    """Fechas de apertura futuras, para ofrecerlas como opción al asignar
    fecha de disfrute a una reserva (con su ocupación actual)."""
    from app.models.fecha_apertura import FechaApertura
    hoy = _date.today()
    items = (
        FechaApertura.query
        .options(joinedload(FechaApertura.tipo_experiencia))
        .filter(FechaApertura.fecha >= hoy)
        .order_by(FechaApertura.fecha)
        .all()
    )

    conteos_raw = (
        db.session.query(
            db.func.date(Reserva.fecha_disfrute).label("fecha"),
            db.func.count(Reserva.id).label("n"),
        )
        .filter(Reserva.fecha_disfrute.isnot(None))
        .group_by("fecha")
        .all()
    )
    conteos = {c.fecha: c.n for c in conteos_raw}

    return jsonify([
        {
            "id": a.id,
            "fecha": a.fecha.isoformat(),
            "tipo_experiencia_id": a.tipo_experiencia_id,
            "tipo_exp_nombre": a.tipo_experiencia.nombre if a.tipo_experiencia else "Todas",
            "n_reservas": conteos.get(a.fecha.isoformat(), 0),
            "capacidad_ideal": a.capacidad_ideal,
        }
        for a in items
    ])


@calendario_bp.route("/aperturas/nueva", methods=["POST"])
@login_required
def apertura_nueva():
    from app.models.fecha_apertura import FechaApertura
    data = request.get_json(silent=True) or {}
    fecha_str = (data.get("fecha") or "").strip()
    if not fecha_str:
        return jsonify({"ok": False, "error": "Fecha requerida"}), 400
    try:
        fecha = _date.fromisoformat(fecha_str)
    except ValueError:
        return jsonify({"ok": False, "error": "Fecha inválida"}), 400
    tipo_id = data.get("tipo_experiencia_id")
    capacidad_ideal = data.get("capacidad_ideal")
    a = FechaApertura(
        fecha=fecha,
        tipo_experiencia_id=int(tipo_id) if tipo_id else None,
        capacidad_ideal=int(capacidad_ideal) if capacidad_ideal else None,
        notas=data.get("notas", "").strip(),
    )
    db.session.add(a)
    db.session.commit()
    registrar_log("crear", "reserva", a.id, f"Fecha apertura anotada: {fecha.strftime('%d/%m/%Y')}")
    return jsonify({"ok": True, "id": a.id})


@calendario_bp.route("/aperturas/<int:id>/editar", methods=["POST"])
@login_required
def apertura_editar(id):
    from app.models.fecha_apertura import FechaApertura
    a = FechaApertura.query.get_or_404(id)
    data = request.get_json(silent=True) or {}

    if "capacidad_ideal" in data:
        capacidad_ideal = data.get("capacidad_ideal")
        a.capacidad_ideal = int(capacidad_ideal) if capacidad_ideal else None
    if "notas" in data:
        a.notas = (data.get("notas") or "").strip()
    if "tipo_experiencia_id" in data:
        tipo_id = data.get("tipo_experiencia_id")
        a.tipo_experiencia_id = int(tipo_id) if tipo_id else None

    db.session.commit()
    return jsonify({"ok": True, "id": a.id, "capacidad_ideal": a.capacidad_ideal})


@calendario_bp.route("/aperturas/<int:id>/eliminar", methods=["POST"])
@login_required
def apertura_eliminar(id):
    from app.models.fecha_apertura import FechaApertura
    a = FechaApertura.query.get_or_404(id)
    db.session.delete(a)
    db.session.commit()
    return jsonify({"ok": True})


@calendario_bp.route("/mover/<int:id>", methods=["POST"])
@login_required
def mover(id):
    reserva = _con_relaciones(Reserva.query).filter_by(id=id).first_or_404()
    data = request.get_json(silent=True) or {}
    nueva_fecha_str = data.get("fecha")
    if not nueva_fecha_str:
        return jsonify({"ok": False, "error": "Fecha requerida"}), 400

    try:
        nueva_fecha = datetime.fromisoformat(nueva_fecha_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Fecha inválida"}), 400

    reserva.fecha_disfrute = nueva_fecha.replace(tzinfo=None)
    if reserva.estado == "pendiente":
        reserva.estado = "reservado"
    db.session.commit()

    registrar_log("asignar_fecha", "reserva", id,
                  f"Fecha asignada vía calendario: {reserva.fecha_disfrute.strftime('%d/%m/%Y %H:%M')} — {reserva.nombre_reservante}")
    return jsonify({"ok": True, "estado": reserva.estado})
