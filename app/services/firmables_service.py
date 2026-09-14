"""
Orquestación de los 3 documentos firmables: el enlace de un solo uso al
wizard (igual que el de Inscripción y Autorización General — se puede
enviar por email, copiar para otro medio, o abrir directamente para
firmar presencialmente), a quién enviar la copia al terminar una sesión,
construcción del email con los 3 PDFs adjuntos, y envío reutilizando la
cuenta MAIL_PRENSA_* ya usada por el resto del proyecto.
"""
import secrets
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid

from flask import current_app, url_for

from app.extensions import db
from app.models.firmable import SesionFirmables
from app.models.preinscripcion_carcross import MailingSeleccionFemenina
from app.services.mail_prensa import remitente_prensa, enviar_smtp_prensa
from app.services.seleccion_femenina_mail import ROJO, NEGRO, BLANCO
from app.services.firmables_pdf import generar_pdf_documento
from app.services.firmables_textos import TIPOS_FIRMABLE_LABELS, TIPOS_FIRMABLE_KEYS

ASUNTO_COPIA_FIRMABLES = "Copia de las autorizaciones firmadas · Selección Femenina de Pilotos"
ASUNTO_ENLACE_FIRMABLES = "Autorizaciones pendientes de firmar · Selección Femenina de Pilotos"


def _generar_token_unico():
    for _ in range(10):
        token = secrets.token_urlsafe(32)
        if not SesionFirmables.query.filter_by(token=token).first():
            return token
    raise RuntimeError("No se pudo generar un token único para los firmables tras varios intentos.")


def obtener_o_crear_sesion_pendiente(preinscripcion, usuario_staff_id=None):
    """Reutiliza la sesión en_progreso existente (si la hay) o crea una
    nueva con su token — idempotente, para que pulsar "enviar" varias veces
    no genere enlaces distintos mientras la sesión siga sin completarse."""
    sesion = SesionFirmables.query.filter_by(preinscripcion_id=preinscripcion.id, estado="en_progreso").first()
    if sesion and sesion.token and not sesion.token_expirado:
        return sesion
    if not sesion:
        sesion = SesionFirmables(preinscripcion_id=preinscripcion.id, usuario_staff_id=usuario_staff_id)
        db.session.add(sesion)
    sesion.token = _generar_token_unico()
    sesion.token_creado_en = datetime.utcnow()
    db.session.commit()
    return sesion


def enlace_firmables(token):
    return url_for("seleccion_femenina.firmables_formulario", token=token, _external=True)


def _html_enlace(preinscripcion, enlace):
    primer_nombre = (preinscripcion.nombre_completo or "").strip().split(" ")[0] or "familia"
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:32px 16px">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:{BLANCO};border-radius:12px;overflow:hidden;border-top:4px solid {ROJO}">
      <tr><td style="background:{NEGRO};padding:24px 32px">
        <span style="font-size:18px;font-weight:900;color:{BLANCO}">SELECCIÓN FEMENINA</span><br>
        <span style="font-size:12px;color:{ROJO};font-weight:700;letter-spacing:1px;text-transform:uppercase">Pilotos de Carcross</span>
      </td></tr>
      <tr><td style="padding:32px">
        <p style="margin:0 0 14px;font-size:15px;color:#222">Hola {primer_nombre},</p>
        <p style="margin:0 0 18px;font-size:15px;color:#222;line-height:1.6">
          Quedan 3 autorizaciones por firmar para <strong>{preinscripcion.nombre_completo}</strong>
          (declaración de aptitud médica, asunción de riesgo, y disclaimer de la prueba de conducción).
        </p>
        <table cellpadding="0" cellspacing="0" style="margin:8px 0 20px">
          <tr><td style="background:{ROJO};border-radius:8px">
            <a href="{enlace}" style="display:inline-block;padding:14px 28px;color:#fff;font-weight:700;text-decoration:none;font-size:15px">
              Firmar autorizaciones
            </a>
          </td></tr>
        </table>
        <p style="font-size:13px;color:#666">Si el botón no funciona, copia y pega este enlace en el navegador:<br>
        <a href="{enlace}" style="color:{ROJO};word-break:break-all">{enlace}</a></p>
        <p style="font-size:13px;color:#666">Este enlace es personal e intransferible, y caduca una vez completadas las 3 autorizaciones.</p>
      </td></tr>
      <tr><td style="background:{NEGRO};padding:16px 32px;font-size:11px;color:#999">
        Selección Femenina de Pilotos de Carcross — AutoClub La Dehesa
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def enviar_email_firmables(preinscripcion, sesion):
    """Envía el enlace de los firmables al email de contacto conocido.
    Registra el resultado en el historial de mailing de la candidata."""
    destinatarios = emails_tutores_conocidos(preinscripcion)
    if not destinatarios:
        return False

    enlace = enlace_firmables(sesion.token)
    sender, domain = remitente_prensa()
    html = _html_enlace(preinscripcion, enlace)
    texto = f"Quedan autorizaciones por firmar para {preinscripcion.nombre_completo}.\n\nEnlace: {enlace}"

    ok_general = True
    for destinatario in destinatarios:
        try:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(texto, "plain", "utf-8"))
            msg.attach(MIMEText(html, "html", "utf-8"))
            msg["Subject"] = ASUNTO_ENLACE_FIRMABLES
            msg["From"] = sender
            msg["To"] = destinatario
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain=domain)
            enviar_smtp_prensa(msg, destinatario)
        except Exception as e:
            current_app.logger.error(f"Error enviando enlace de firmables a {destinatario}: {e}")
            ok_general = False

    db.session.add(MailingSeleccionFemenina(
        preinscripcion_id=preinscripcion.id, asunto=ASUNTO_ENLACE_FIRMABLES,
        cuerpo=f"Enlace de firmables enviado a: {', '.join(destinatarios)}.",
        enviado_ok=ok_general,
        error="" if ok_general else "Falló el envío a algún destinatario, ver logs del servidor.",
    ))
    db.session.commit()
    return ok_general


def siguiente_paso_pendiente(sesion):
    """Primer tipo de documento de la sesión que todavía no se ha creado en
    ella — para poder pausar y retomar (o abrir el mismo enlace dos veces)
    sin perder progreso."""
    from app.models.firmable import DocumentoFirmado
    tipos_ya_hechos = {d.tipo for d in sesion.documentos}
    for i, tipo in enumerate(TIPOS_FIRMABLE_KEYS, start=1):
        if tipo not in tipos_ya_hechos:
            return i
    return len(TIPOS_FIRMABLE_KEYS)  # todos hechos (no debería quedar en_progreso)


def completar_sesion_firmables(sesion, preinscripcion):
    """Marca la sesión como completada y envía la copia por email. Es
    idempotente: si ya estaba completada, no hace nada (se puede llamar
    tanto justo tras firmar el paso 3 como, de refuerzo, al recargar la
    pantalla de cierre)."""
    from app.models.firmable import DocumentoFirmado
    if sesion.estado != "en_progreso":
        return True
    documentos = DocumentoFirmado.query.filter_by(sesion_id=sesion.id).all()
    if len(documentos) < len(TIPOS_FIRMABLE_KEYS):
        return None  # todavía no están los 3 documentos
    sesion.estado = "completada"
    sesion.completada_en = datetime.utcnow()
    db.session.commit()
    enviado = enviar_copia_firmables(preinscripcion, documentos)
    from app.services.log_service import registrar_log
    registrar_log("cambiar_estado", "preinscripcion_carcross", preinscripcion.id,
                  f"Firmables completados: {preinscripcion.nombre_completo}")
    return enviado


def emails_tutores_conocidos(preinscripcion):
    """A quién enviar la copia: los emails de los tutores ya recogidos en
    la Inscripción y Autorización General (si existe), o si no el email de
    contacto de la propia preinscripción."""
    insc = preinscripcion.inscripcion_autorizacion
    if insc and insc.tutores:
        emails = [t.email for t in insc.tutores if t.email]
        if emails:
            return emails
    return [preinscripcion.email] if preinscripcion.email else []


def _html_confirmacion(preinscripcion, documentos):
    filas = "".join(
        f"<li>{TIPOS_FIRMABLE_LABELS.get(d.tipo, d.tipo)} (v{d.version})</li>" for d in documentos
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:32px 16px">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:{BLANCO};border-radius:12px;overflow:hidden;border-top:4px solid {ROJO}">
      <tr><td style="background:{NEGRO};padding:24px 32px">
        <span style="font-size:18px;font-weight:900;color:{BLANCO}">SELECCIÓN FEMENINA</span><br>
        <span style="font-size:12px;color:{ROJO};font-weight:700;letter-spacing:1px;text-transform:uppercase">Pilotos de Carcross</span>
      </td></tr>
      <tr><td style="padding:32px">
        <p style="margin:0 0 14px;font-size:15px;color:#222">
          Se han registrado correctamente las siguientes autorizaciones de <strong>{preinscripcion.nombre_completo}</strong>:
        </p>
        <ul style="font-size:14px;color:#222;padding-left:20px">{filas}</ul>
        <p style="margin:14px 0 0;font-size:13px;color:#666">Adjuntamos una copia en PDF de cada documento firmado.</p>
      </td></tr>
      <tr><td style="background:{NEGRO};padding:16px 32px;font-size:11px;color:#999">
        Selección Femenina de Pilotos de Carcross — AutoClub La Dehesa
      </td></tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def enviar_copia_firmables(preinscripcion, documentos):
    """documentos: lista de DocumentoFirmado (los creados en la sesión que
    se acaba de completar). Envía un único email con los PDF adjuntos a
    cada tutor conocido. No aborta si falla — se registra el error en el
    historial de mailing para que el equipo pueda reenviarlo a mano."""
    destinatarios = emails_tutores_conocidos(preinscripcion)
    if not destinatarios:
        return False

    sender, domain = remitente_prensa()
    html = _html_confirmacion(preinscripcion, documentos)
    texto = "Se han registrado las autorizaciones firmadas. Adjuntamos copia en PDF de cada documento."

    ok_general = True
    for destinatario in destinatarios:
        try:
            msg = MIMEMultipart("mixed")
            alt = MIMEMultipart("alternative")
            alt.attach(MIMEText(texto, "plain", "utf-8"))
            alt.attach(MIMEText(html, "html", "utf-8"))
            msg.attach(alt)
            for d in documentos:
                pdf_bytes = generar_pdf_documento(preinscripcion, d)
                nombre = f"{d.tipo}_v{d.version}.pdf"
                adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
                adjunto.add_header("Content-Disposition", "attachment", filename=nombre)
                msg.attach(adjunto)

            msg["Subject"] = ASUNTO_COPIA_FIRMABLES
            msg["From"] = sender
            msg["To"] = destinatario
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain=domain)
            enviar_smtp_prensa(msg, destinatario)
        except Exception as e:
            current_app.logger.error(f"Error enviando copia de firmables a {destinatario}: {e}")
            ok_general = False

    db.session.add(MailingSeleccionFemenina(
        preinscripcion_id=preinscripcion.id, asunto=ASUNTO_COPIA_FIRMABLES,
        cuerpo=f"Copia de {len(documentos)} documento(s) firmado(s) enviada a: {', '.join(destinatarios)}.",
        enviado_ok=ok_general,
        error="" if ok_general else "Falló el envío a algún destinatario, ver logs del servidor.",
    ))
    db.session.commit()
    return ok_general
