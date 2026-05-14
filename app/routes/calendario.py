from datetime import datetime
from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from app.extensions import db
from app.models.reserva import Reserva
from app.services.log_service import registrar_log

calendario_bp = Blueprint("calendario", __name__)


@calendario_bp.route("/")
@login_required
def index():
    return render_template("calendario/index.html")


@calendario_bp.route("/eventos")
@login_required
def eventos():
    # Devolvemos todos los eventos con fecha; FullCalendar filtra los visibles
    # según la vista actual. Evitamos el filtro por rango que SQLite maneja
    # de forma inconsistente con los timestamps de FullCalendar.
    reservas = (
        Reserva.query
        .filter(Reserva.fecha_disfrute.isnot(None))
        .order_by(Reserva.fecha_disfrute)
        .all()
    )
    return jsonify([r.to_calendar_event() for r in reservas])


@calendario_bp.route("/pendientes")
@login_required
def pendientes():
    reservas = (
        Reserva.query
        .filter(Reserva.fecha_disfrute.is_(None))
        .filter(Reserva.estado.in_(["pendiente", "reservado"]))
        .order_by(Reserva.fecha_compra.desc())
        .all()
    )
    return jsonify([
        {
            "id": r.id,
            "cliente": r.cliente.nombre_completo,
            "email": r.cliente.email,
            "telefono": r.cliente.telefono or "",
            "experiencia": r.tipo_experiencia.nombre,
            "fecha_compra": r.fecha_compra.strftime("%d/%m/%Y") if r.fecha_compra else "",
            "estado": r.estado,
            "color": r.color,
            "woo_order_id": r.woo_order_id,
        }
        for r in reservas
    ])


@calendario_bp.route("/mover/<int:id>", methods=["POST"])
@login_required
def mover(id):
    reserva = Reserva.query.get_or_404(id)
    data = request.get_json()
    nueva_fecha_str = data.get("fecha")

    try:
        nueva_fecha = datetime.fromisoformat(nueva_fecha_str.replace("Z", "+00:00"))
        reserva.fecha_disfrute = nueva_fecha.replace(tzinfo=None)
        if reserva.estado == "pendiente":
            reserva.estado = "reservado"
        db.session.commit()
        registrar_log("asignar_fecha", "reserva", id,
                      f"Fecha asignada vía calendario: {reserva.fecha_disfrute.strftime('%d/%m/%Y %H:%M')} — {reserva.cliente.nombre_completo}")
        return jsonify({"ok": True, "estado": reserva.estado})
    except Exception as e:
        db.session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 400
