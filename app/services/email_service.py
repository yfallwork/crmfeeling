from flask import current_app
from flask_mail import Message
from app.extensions import mail


# ── PLANTILLA BASE HTML ───────────────────────────────────────────────────────
def _base_email(contenido_html, titulo_preheader=""):
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{titulo_preheader}</title>
</head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:32px 16px">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%">

      <!-- CABECERA MARCA -->
      <tr>
        <td style="background:#0D0D0D;padding:24px 36px;border-radius:12px 12px 0 0;text-align:center">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td align="left" style="border-left:4px solid #AD1726;padding-left:16px">
                <span style="font-size:22px;font-weight:900;color:#ffffff;letter-spacing:-0.5px">FEELING</span>
                <span style="font-size:22px;font-weight:900;color:#AD1726;letter-spacing:-0.5px"> EXPERIENCE</span>
                <div style="font-size:11px;color:#666;margin-top:2px;letter-spacing:1px;text-transform:uppercase">
                  Experiencias de conduccion
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>

      <!-- CONTENIDO -->
      <tr>
        <td style="background:#ffffff;padding:36px 36px 28px">
          {contenido_html}
        </td>
      </tr>

      <!-- PIE -->
      <tr>
        <td style="background:#0D0D0D;padding:20px 36px;border-radius:0 0 12px 12px">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="color:#555;font-size:11px;line-height:1.6">
                <strong style="color:#AD1726">Feeling Experience</strong> &mdash;
                Experiencias de conduccion de carcross<br>
                <a href="https://www.regaloexperiencias.com" style="color:#AD1726;text-decoration:none">
                  www.regaloexperiencias.com
                </a>
                &nbsp;&middot;&nbsp;
                <a href="mailto:reservas@regaloexperiencias.com" style="color:#AD1726;text-decoration:none">
                  reservas@regaloexperiencias.com
                </a>
              </td>
            </tr>
          </table>
        </td>
      </tr>

    </table>
  </td></tr>
</table>
</body>
</html>"""


# ── COMPONENTES REUTILIZABLES ─────────────────────────────────────────────────
def _bloque_fecha(reserva):
    if not reserva.fecha_disfrute:
        return """
        <tr>
          <td style="background:#fff8e1;border:1px solid #fcd34d;border-radius:8px;
                     padding:14px 18px;margin-bottom:20px">
            <span style="color:#92400e;font-size:13px;font-weight:600">
              Fecha: pendiente de confirmar
            </span><br>
            <span style="color:#b45309;font-size:12px">
              Nos pondremos en contacto contigo para fijar la fecha.
            </span>
          </td>
        </tr>"""

    return f"""
        <tr>
          <td style="background:#0D0D0D;border-radius:8px;padding:18px 22px;margin-bottom:20px">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <div style="color:#AD1726;font-size:11px;font-weight:700;
                              text-transform:uppercase;letter-spacing:1px">
                    Fecha de tu experiencia
                  </div>
                  <div style="color:#ffffff;font-size:22px;font-weight:800;margin-top:4px">
                    {reserva.fecha_disfrute.strftime('%A, %d de %B de %Y').capitalize()}
                  </div>
                  {f'<div style="color:#AD1726;font-size:15px;font-weight:700;margin-top:2px">{reserva.horario}</div>' if reserva.horario else ''}
                </td>
              </tr>
            </table>
          </td>
        </tr>"""


def _bloque_experiencia(reserva):
    variante = ""
    if reserva.variante:
        variante_limpia = reserva.variante.replace("-", " ").title()
        variante = f"""<div style="color:#AD1726;font-size:12px;margin-top:3px">{variante_limpia}</div>"""
    return f"""
        <tr>
          <td style="padding-bottom:20px">
            <table cellpadding="0" cellspacing="0">
              <tr>
                <td style="background:#AD1726;border-radius:4px;
                           padding:3px 10px;font-size:11px;font-weight:700;color:#fff">
                  EXPERIENCIA
                </td>
              </tr>
              <tr>
                <td style="font-size:18px;font-weight:700;color:#0D0D0D;padding-top:6px">
                  {reserva.tipo_experiencia.nombre}
                </td>
              </tr>
              <tr><td>{variante}</td></tr>
            </table>
          </td>
        </tr>"""


# ── BUILDERS (construyen sin enviar) ─────────────────────────────────────────
def _build_confirmacion(reserva):
    nombre = reserva.cliente.nombre
    contenido = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
      <tr>
        <td style="padding-bottom:24px">
          <h1 style="margin:0;font-size:26px;font-weight:800;color:#0D0D0D;line-height:1.2">
            Reserva confirmada
          </h1>
          <p style="margin:8px 0 0;font-size:15px;color:#555">
            Hola <strong>{nombre}</strong>, tu reserva esta lista.
          </p>
        </td>
      </tr>
      {_bloque_experiencia(reserva)}
      {_bloque_fecha(reserva)}
      <tr><td style="height:24px"></td></tr>
      <tr>
        <td style="border-top:1px solid #f0f0f0;padding-top:20px">
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr>
              <td style="width:50%;padding-right:10px;vertical-align:top">
                <div style="font-size:11px;color:#999;text-transform:uppercase;
                            letter-spacing:.5px;margin-bottom:4px">Pedido</div>
                <div style="font-size:13px;font-weight:600;color:#333">
                  #{reserva.woo_order_id or reserva.id}
                </div>
              </td>
              <td style="width:50%;padding-left:10px;vertical-align:top">
                <div style="font-size:11px;color:#999;text-transform:uppercase;
                            letter-spacing:.5px;margin-bottom:4px">Precio</div>
                <div style="font-size:13px;font-weight:600;color:#333">
                  {reserva.precio:.0f} EUR
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding-top:24px">
          <p style="margin:0;font-size:14px;color:#555;line-height:1.6">
            Si tienes cualquier pregunta o necesitas cambiar algo, contacta con nosotros
            respondiendo a este email o llamando directamente.
          </p>
          <p style="margin:16px 0 0;font-size:15px;font-weight:700;color:#0D0D0D">
            Nos vemos en el circuito. Preparate para disfrutar.
          </p>
        </td>
      </tr>
    </table>"""
    asunto = f"Reserva confirmada — {reserva.tipo_experiencia.nombre}"
    return asunto, _base_email(contenido, "Reserva confirmada")


def _build_recordatorio(reserva):
    nombre = reserva.cliente.nombre
    cuando = "manana" if reserva.dias_hasta_disfrute == 1 else "pronto"
    contenido = f"""
    <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse">
      <tr>
        <td style="padding-bottom:24px">
          <h1 style="margin:0;font-size:26px;font-weight:800;color:#0D0D0D;line-height:1.2">
            Tu experiencia es {cuando}
          </h1>
          <p style="margin:8px 0 0;font-size:15px;color:#555">
            Hola <strong>{nombre}</strong>, te recordamos que tu reserva esta muy cerca.
          </p>
        </td>
      </tr>
      {_bloque_experiencia(reserva)}
      {_bloque_fecha(reserva)}
      <tr><td style="height:20px"></td></tr>
      <tr>
        <td style="background:#f9f9f9;border-radius:8px;padding:18px 20px">
          <div style="font-size:12px;font-weight:700;color:#AD1726;
                      text-transform:uppercase;letter-spacing:.8px;margin-bottom:10px">
            Antes de venir
          </div>
          <table cellpadding="0" cellspacing="0">
            <tr><td style="padding:4px 0;font-size:13px;color:#444">
              Llega con <strong>15 minutos de antelacion</strong>
            </td></tr>
            <tr><td style="padding:4px 0;font-size:13px;color:#444">Ropa comoda y zapato cerrado</td></tr>
            <tr><td style="padding:4px 0;font-size:13px;color:#444">Si tienes dudas, respondenos a este email</td></tr>
          </table>
        </td>
      </tr>
      <tr>
        <td style="padding-top:24px">
          <p style="margin:0;font-size:15px;font-weight:700;color:#0D0D0D">
            Que lo disfrutes al maximo. Te esperamos.
          </p>
        </td>
      </tr>
    </table>"""
    asunto = f"Tu experiencia es {cuando} — {reserva.tipo_experiencia.nombre}"
    return asunto, _base_email(contenido, f"Tu experiencia es {cuando}")


def build_preview_email(reserva, tipo):
    """Devuelve (asunto, html) sin enviar nada."""
    if tipo == "confirmacion":
        return _build_confirmacion(reserva)
    return _build_recordatorio(reserva)


# ── EMAIL: CONFIRMACION ───────────────────────────────────────────────────────
def enviar_confirmacion(reserva):
    if not reserva.cliente.email:
        return False
    asunto, html = _build_confirmacion(reserva)
    return _enviar(reserva.cliente.email, asunto, html, reserva.id, "confirmacion")


# ── EMAIL: RECORDATORIO ───────────────────────────────────────────────────────
def enviar_recordatorio(reserva):
    if not reserva.cliente.email:
        return False
    asunto, html = _build_recordatorio(reserva)
    return _enviar(reserva.cliente.email, asunto, html, reserva.id, "recordatorio")


# ── ENVIO CON CONTENIDO PERSONALIZADO ────────────────────────────────────────
def enviar_email_personalizado(reserva, tipo, asunto, html):
    """Envía un email con asunto y cuerpo HTML ya editados por el usuario."""
    if not reserva.cliente.email:
        return False
    return _enviar(reserva.cliente.email, asunto, html, reserva.id, tipo)


# ── ENVIO ─────────────────────────────────────────────────────────────────────
def _enviar(destinatario, asunto, cuerpo, reserva_id=None, tipo=None):
    try:
        msg = Message(asunto, recipients=[destinatario], html=cuerpo)
        mail.send(msg)
        _log(reserva_id, tipo, "email", ok=True)
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando email a {destinatario}: {e}")
        _log(reserva_id, tipo, "email", ok=False, error=str(e))
        return False


def _log(reserva_id, tipo, canal, ok, error=""):
    if not reserva_id or not tipo:
        return
    try:
        from app.models.comunicacion import ComunicacionLog
        from app.extensions import db
        db.session.add(ComunicacionLog(
            reserva_id=reserva_id, tipo=tipo, canal=canal,
            ok=ok, error=str(error)[:500],
        ))
        db.session.commit()
    except Exception as ex:
        current_app.logger.warning(f"No se pudo guardar log de comunicacion: {ex}")
