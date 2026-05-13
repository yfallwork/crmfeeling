from flask import current_app

MSG_CONFIRMACION = (
    "¡Hola {nombre}! 👋\n\n"
    "Tu reserva para *{experiencia}* ha sido confirmada.\n"
    "📅 Fecha: {fecha}\n\n"
    "Si necesitas cambiar algo, escríbenos. ¡Hasta pronto! 🏁"
)

MSG_RECORDATORIO = (
    "¡Hola {nombre}! 🏎️\n\n"
    "Te recordamos que *mañana* tienes tu experiencia de *{experiencia}*.\n"
    "📅 {fecha}\n\n"
    "Recuerda llegar 15 min antes. ¡Te esperamos!"
)


def _formatear_telefono(telefono):
    t = "".join(c for c in (telefono or "") if c.isdigit() or c == "+")
    if t and not t.startswith("+"):
        t = "+34" + t
    return t


def _build_mensaje(reserva, tipo):
    plantilla = MSG_CONFIRMACION if tipo == "confirmacion" else MSG_RECORDATORIO
    return plantilla.format(
        nombre=reserva.cliente.nombre,
        experiencia=reserva.tipo_experiencia.nombre,
        fecha=reserva.fecha_disfrute.strftime("%d/%m/%Y %H:%M") if reserva.fecha_disfrute else "Por confirmar",
    )


def build_preview_whatsapp(reserva, tipo):
    """Devuelve (telefono, mensaje) sin enviar nada."""
    telefono = _formatear_telefono(reserva.cliente.telefono) or ""
    return telefono, _build_mensaje(reserva, tipo)


def enviar_confirmacion_whatsapp(reserva):
    telefono = _formatear_telefono(reserva.cliente.telefono)
    if not telefono:
        return False, "Sin teléfono"
    return _enviar_whatsapp(telefono, _build_mensaje(reserva, "confirmacion"))


def enviar_recordatorio_whatsapp(reserva):
    telefono = _formatear_telefono(reserva.cliente.telefono)
    if not telefono:
        return False, "Sin teléfono"
    return _enviar_whatsapp(telefono, _build_mensaje(reserva, "recordatorio"))


def _enviar_whatsapp(telefono, mensaje):
    sid = current_app.config.get("TWILIO_ACCOUNT_SID", "")
    token = current_app.config.get("TWILIO_AUTH_TOKEN", "")
    from_number = current_app.config.get("TWILIO_WHATSAPP_FROM", "")

    if not sid or not token or sid.startswith("AC") is False:
        # Modo mock: registrar en log
        current_app.logger.info(f"[WhatsApp MOCK] → {telefono}: {mensaje}")
        return True, "mock"

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        msg = client.messages.create(
            body=mensaje,
            from_=from_number,
            to=f"whatsapp:{telefono}",
        )
        return True, msg.sid
    except Exception as e:
        current_app.logger.error(f"Error WhatsApp a {telefono}: {e}")
        return False, str(e)
