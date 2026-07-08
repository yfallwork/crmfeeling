from flask import Blueprint, jsonify, request
from flask_login import login_required
from app.extensions import db
from app.models.cliente import Cliente
from app.models.reserva import Reserva, ESTADOS
from app.models.experiencia import TipoExperiencia
from app.services.email_service import enviar_confirmacion, enviar_recordatorio
from app.services.whatsapp_service import enviar_confirmacion_whatsapp, enviar_recordatorio_whatsapp

api_bp = Blueprint("api", __name__)


@api_bp.route("/clientes")
@login_required
def api_clientes():
    q = request.args.get("q", "").strip()
    query = Cliente.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Cliente.nombre.ilike(like), Cliente.apellido.ilike(like), Cliente.email.ilike(like))
        )
    clientes = query.limit(20).all()
    return jsonify([c.to_dict() for c in clientes])


@api_bp.route("/reservas")
@login_required
def api_reservas():
    estado = request.args.get("estado", "")
    query = Reserva.query
    if estado:
        query = query.filter_by(estado=estado)
    reservas = query.order_by(Reserva.fecha_disfrute).limit(50).all()
    return jsonify([r.to_dict() for r in reservas])


@api_bp.route("/reservas/<int:id>/fecha", methods=["PATCH"])
@login_required
def api_actualizar_fecha(id):
    from sqlalchemy.orm import joinedload
    reserva = (
        Reserva.query
        .options(joinedload(Reserva.cliente), joinedload(Reserva.empresa))
        .filter_by(id=id).first_or_404()
    )
    data = request.get_json(silent=True) or {}
    from datetime import datetime
    fecha_str = data.get("fecha_disfrute", "")
    if not fecha_str:
        return jsonify({"ok": False, "error": "Fecha requerida"}), 400

    try:
        nueva_fecha = datetime.fromisoformat(fecha_str.replace("Z", ""))
    except (ValueError, TypeError):
        return jsonify({"ok": False, "error": "Fecha inválida"}), 400

    reserva.fecha_disfrute = nueva_fecha
    if reserva.estado == "pendiente":
        reserva.estado = "reservado"
    db.session.commit()

    from app.services.log_service import registrar_log
    registrar_log("asignar_fecha", "reserva", id,
                  f"Fecha asignada vía sidebar calendario: {reserva.fecha_disfrute.strftime('%d/%m/%Y %H:%M')} — {reserva.nombre_reservante}")
    return jsonify({"ok": True, "reserva": reserva.to_dict()})


@api_bp.route("/reservas/<int:id>/preview")
@login_required
def api_preview(id):
    from app.services.email_service import build_preview_email
    from app.services.whatsapp_service import build_preview_whatsapp
    reserva = Reserva.query.get_or_404(id)
    tipo  = request.args.get("tipo", "confirmacion")
    canal = request.args.get("canal", "email")
    if canal == "email":
        asunto, html = build_preview_email(reserva, tipo)
        return jsonify({"asunto": asunto, "html": html, "destinatario": reserva.cliente.email or ""})
    elif canal == "whatsapp":
        telefono, mensaje = build_preview_whatsapp(reserva, tipo)
        return jsonify({"telefono": telefono, "mensaje": mensaje})
    return jsonify({"ok": False, "error": "Canal no válido"}), 400


@api_bp.route("/reservas/<int:id>/notificar", methods=["POST"])
@login_required
def api_notificar(id):
    from app.models.comunicacion import ComunicacionLog
    from app.services.email_service import enviar_email_personalizado
    reserva = Reserva.query.get_or_404(id)
    data  = request.json or {}
    tipo  = data.get("tipo", "confirmacion")
    canal = data.get("canal", "email")

    if canal == "email":
        asunto_custom = data.get("asunto")
        html_custom   = data.get("html")
        if asunto_custom and html_custom:
            ok = enviar_email_personalizado(reserva, tipo, asunto_custom, html_custom)
        else:
            ok = enviar_confirmacion(reserva) if tipo == "confirmacion" else enviar_recordatorio(reserva)
        return jsonify({"ok": ok, "canal": "email"})

    elif canal == "whatsapp":
        mensaje_custom = data.get("mensaje")
        if mensaje_custom:
            from app.services.whatsapp_service import _formatear_telefono, _enviar_whatsapp
            telefono = _formatear_telefono(reserva.cliente.telefono)
            if not telefono:
                return jsonify({"ok": False, "error": "Sin teléfono"}), 400
            ok, sid = _enviar_whatsapp(telefono, mensaje_custom)
        else:
            ok, sid = (
                enviar_confirmacion_whatsapp(reserva)
                if tipo == "confirmacion"
                else enviar_recordatorio_whatsapp(reserva)
            )
        try:
            db.session.add(ComunicacionLog(
                reserva_id=reserva.id, tipo=tipo, canal="whatsapp",
                ok=ok, error="" if ok else str(sid),
            ))
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"ok": ok, "canal": "whatsapp", "sid": sid})

    return jsonify({"ok": False, "error": "Canal no válido"}), 400


@api_bp.route("/buscar")
@login_required
def api_buscar():
    from flask import url_for
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"clientes": [], "reservas": []})

    like = f"%{q}%"

    clientes = Cliente.query.filter(
        db.or_(
            Cliente.nombre.ilike(like),
            Cliente.apellido.ilike(like),
            Cliente.email.ilike(like),
            Cliente.telefono.ilike(like),
        )
    ).limit(6).all()

    reservas = Reserva.query.join(Reserva.cliente).filter(
        db.or_(
            Cliente.nombre.ilike(like),
            Cliente.apellido.ilike(like),
            Cliente.email.ilike(like),
            Reserva.woo_order_id.ilike(like),
        )
    ).order_by(Reserva.fecha_compra.desc()).limit(6).all()

    return jsonify({
        "clientes": [
            {
                "url": url_for("clientes.detalle", id=c.id),
                "nombre": c.nombre_completo,
                "email": c.email or "",
                "telefono": c.telefono or "",
            }
            for c in clientes
        ],
        "reservas": [
            {
                "url": url_for("reservas.detalle", id=r.id),
                "cliente": r.cliente.nombre_completo,
                "experiencia": r.tipo_experiencia.nombre,
                "fecha": r.fecha_compra.strftime("%d/%m/%Y") if r.fecha_compra else "—",
                "estado": r.estado,
            }
            for r in reservas
        ],
    })


@api_bp.route("/test-email")
@login_required
def api_test_email():
    """Envía un email de prueba. Acepta ?dest=email para elegir destinatario."""
    from flask import current_app
    from flask_mail import Message
    from app.extensions import mail
    dest = request.args.get("dest") or current_app.config.get("MAIL_USERNAME", "")
    try:
        msg = Message(
            subject="Test SMTP — CRM Feeling Experience",
            recipients=[dest],
            html="""<!DOCTYPE html>
<html><body style="font-family:sans-serif;background:#f4f4f4;padding:32px">
<div style="max-width:480px;margin:0 auto;background:#fff;border-radius:12px;overflow:hidden;
            box-shadow:0 4px 20px rgba(0,0,0,.08)">
  <div style="background:#0D0D0D;padding:24px 28px;border-left:5px solid #AD1726">
    <span style="font-size:18px;font-weight:900;color:#fff">FEELING</span>
    <span style="font-size:18px;font-weight:900;color:#AD1726"> EXPERIENCE</span>
  </div>
  <div style="padding:28px">
    <h2 style="color:#AD1726;margin-top:0">Conexion SMTP correcta</h2>
    <p style="color:#333">El servidor de correo esta configurado y funcionando correctamente.</p>
    <p style="color:#888;font-size:12px;margin-bottom:0">
      Feeling Experience · reservas@regaloexperiencias.com
    </p>
  </div>
</div>
</body></html>""",
        )
        mail.send(msg)
        return jsonify({"ok": True, "enviado_a": dest,
                        "consejo": "Si no llega a Gmail, revisa la carpeta de spam o anade el registro SPF."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e),
                        "consejo": "Verifica MAIL_SERVER, MAIL_PORT y MAIL_PASSWORD en el .env"})


@api_bp.route("/stats/dashboard")
@login_required
def api_stats():
    from datetime import timedelta, datetime
    from sqlalchemy import func
    hace_30 = datetime.utcnow() - timedelta(days=30)
    return jsonify({
        "total_clientes": Cliente.query.count(),
        "reservas_pendientes": Reserva.query.filter_by(estado="pendiente").count(),
        "ingresos_mes": db.session.query(func.sum(Reserva.precio)).filter(
            Reserva.fecha_compra >= hace_30
        ).scalar() or 0,
    })
