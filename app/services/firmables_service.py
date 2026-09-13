"""
Orquestación de los 3 documentos firmables: a quién enviar la copia al
terminar una sesión, construcción del email con los 3 PDFs adjuntos, y
envío reutilizando la cuenta MAIL_PRENSA_* ya usada por el resto del
proyecto de Selección Femenina.
"""
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formatdate, make_msgid

from flask import current_app

from app.extensions import db
from app.models.preinscripcion_carcross import MailingSeleccionFemenina
from app.services.mail_prensa import remitente_prensa, enviar_smtp_prensa
from app.services.seleccion_femenina_mail import ROJO, NEGRO, BLANCO
from app.services.firmables_pdf import generar_pdf_documento
from app.services.firmables_textos import TIPOS_FIRMABLE_LABELS

ASUNTO_COPIA_FIRMABLES = "Copia de las autorizaciones firmadas · Selección Femenina de Pilotos"


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
