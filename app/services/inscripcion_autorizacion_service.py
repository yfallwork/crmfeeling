"""
Formulario de "Inscripción y Autorización General del Proceso de
Selección" — email disparado al pasar una candidata a "apta_inscripcion",
enlace público de un solo uso al formulario, y email de confirmación al
completarse. Reutiliza la cuenta MAIL_PRENSA_* y la plantilla roja/negro/
blanco de app/services/seleccion_femenina_mail.py.
"""
import secrets
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from flask import current_app, url_for

from app.extensions import db
from app.models.inscripcion_autorizacion import InscripcionAutorizacion
from app.models.preinscripcion_carcross import MailingSeleccionFemenina
from app.services.mail_prensa import remitente_prensa, enviar_smtp_prensa
from app.services.seleccion_femenina_mail import ROJO, NEGRO, BLANCO

ASUNTO_INSCRIPCION = "Siguiente paso: inscripción y autorización · Selección Femenina de Pilotos"

# Datos de la jornada de entrevistas — editables aquí sin tocar el resto
# del envío.
ENTREVISTAS_FECHA_LIMITE = "13 de septiembre de 2026"
ENTREVISTAS_LUGAR = "Circuito La Dehesa, Alcolea del Pinar (Guadalajara)"
ENTREVISTAS_MAPA_URL = "https://share.google/aaQTqIiUMpHvKp8HB"
ENTREVISTAS_HORA_INICIO = "10:30"
ENTREVISTAS_FECHA_HORARIOS = "viernes 11 de septiembre de 2026"
ASUNTO_CONFIRMACION = "Inscripción recibida · Selección Femenina de Pilotos"


def generar_token_unico():
    for _ in range(10):
        token = secrets.token_urlsafe(32)
        if not InscripcionAutorizacion.query.filter_by(token=token).first():
            return token
    raise RuntimeError("No se pudo generar un token único para la inscripción tras varios intentos.")


def obtener_o_crear_inscripcion(preinscripcion):
    """Idempotente: si ya existe (p.ej. se reenvía el estado por error), no
    genera un token nuevo ni duplica el registro — reutiliza el existente."""
    if preinscripcion.inscripcion_autorizacion:
        return preinscripcion.inscripcion_autorizacion
    inscripcion = InscripcionAutorizacion(
        preinscripcion_id=preinscripcion.id, token=generar_token_unico(),
    )
    db.session.add(inscripcion)
    db.session.commit()
    return inscripcion


def _enlace_inscripcion(token):
    return url_for("seleccion_femenina.inscripcion_formulario", token=token, _external=True)


def _html_base(nombre_completo, titulo, cuerpo_html):
    primer_nombre = (nombre_completo or "").strip().split(" ")[0] or "candidata"
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:32px 16px">
  <tr><td align="center">
    <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;background:{BLANCO};border-radius:12px;overflow:hidden;border-top:4px solid {ROJO}">
      <tr>
        <td style="background:{NEGRO};padding:24px 32px">
          <span style="font-size:18px;font-weight:900;color:{BLANCO};letter-spacing:-.3px">SELECCIÓN FEMENINA</span><br>
          <span style="font-size:12px;color:{ROJO};font-weight:700;letter-spacing:1px;text-transform:uppercase">Pilotos de Carcross</span>
        </td>
      </tr>
      <tr>
        <td style="padding:32px">
          <h1 style="margin:0 0 16px;font-size:20px;font-weight:800;color:#111">{titulo}</h1>
          <p style="margin:0 0 16px;font-size:15px;color:#222">Hola <strong>{primer_nombre}</strong>,</p>
          <div style="font-size:15px;color:#222;line-height:1.7">{cuerpo_html}</div>
        </td>
      </tr>
      <tr>
        <td style="background:{NEGRO};padding:16px 32px;font-size:11px;color:#999">
          Selección Femenina de Pilotos de Carcross — AutoClub La Dehesa
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def _enviar(destinatario, asunto, html, texto):
    sender, domain = remitente_prensa()
    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(texto, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    msg["Subject"] = asunto
    msg["From"] = sender
    msg["To"] = destinatario
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=domain)
    enviar_smtp_prensa(msg, destinatario)


def enviar_email_inscripcion(preinscripcion, inscripcion):
    """Email inicial con el enlace único al formulario. Se registra también
    en el historial de mailing de la candidata (mismo mecanismo que el
    mailing masivo) para que el equipo vea en su ficha que se le envió."""
    enlace = _enlace_inscripcion(inscripcion.token)
    cuerpo_html = f"""
        <p>¡Enhorabuena, has superado la preinscripción! El siguiente paso es que tu madre, padre o
        tutor/a legal (o ambos, si aplica) rellenen y firmen el documento de
        <strong>Inscripción y Autorización General del Proceso de Selección</strong> — sustituye al papel
        y recoge los datos necesarios para poder convocarte a la entrevista.</p>
        <table cellpadding="0" cellspacing="0" style="margin:20px 0">
          <tr><td style="background:{ROJO};border-radius:8px">
            <a href="{enlace}" style="display:inline-block;padding:14px 28px;color:#fff;font-weight:700;text-decoration:none;font-size:15px">
              Rellenar inscripción y autorización
            </a>
          </td></tr>
        </table>
        <p style="font-size:13px;color:#666">Si el botón no funciona, copia y pega este enlace en el navegador:<br>
        <a href="{enlace}" style="color:{ROJO};word-break:break-all">{enlace}</a></p>
        <p style="font-size:13px;color:#666">Este enlace es personal e intransferible, y caduca una vez completado el formulario.</p>
        <table cellpadding="0" cellspacing="0" width="100%" style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;margin:22px 0">
          <tr><td style="padding:14px 18px;font-size:13px;color:#444;line-height:1.8">
            <strong style="color:{ROJO}">Importante — hay que rellenarlo antes del {ENTREVISTAS_FECHA_LIMITE}.</strong><br>
            Ese día se celebran las entrevistas en el <strong>{ENTREVISTAS_LUGAR}</strong>
            (<a href="{ENTREVISTAS_MAPA_URL}" style="color:{ROJO}">ver ubicación</a>),
            a partir de las <strong>{ENTREVISTAS_HORA_INICIO}</strong>.<br>
            La hora exacta de la entrevista de cada chica se enviará el <strong>{ENTREVISTAS_FECHA_HORARIOS}</strong>.<br>
            A la entrevista deben acudir <strong>uno o ambos progenitores/tutores legales</strong>.
          </td></tr>
        </table>
    """
    texto = (
        f"¡Enhorabuena, has superado la preinscripción!\n\n"
        "El siguiente paso es que tu madre, padre o tutor/a legal (o ambos, si aplica) rellenen y firmen "
        "el documento de Inscripción y Autorización General del Proceso de Selección.\n\n"
        f"Enlace: {enlace}\n\n"
        "Este enlace es personal e intransferible, y caduca una vez completado el formulario.\n\n"
        f"IMPORTANTE — hay que rellenarlo antes del {ENTREVISTAS_FECHA_LIMITE}. Ese día se celebran las "
        f"entrevistas en {ENTREVISTAS_LUGAR} ({ENTREVISTAS_MAPA_URL}), a partir de las {ENTREVISTAS_HORA_INICIO}.\n"
        f"La hora exacta de la entrevista de cada chica se enviará el {ENTREVISTAS_FECHA_HORARIOS}.\n"
        "A la entrevista deben acudir uno o ambos progenitores/tutores legales."
    )
    html = _html_base(preinscripcion.nombre_completo, "¡Un paso más cerca!", cuerpo_html)

    try:
        _enviar(preinscripcion.email, ASUNTO_INSCRIPCION, html, texto)
        db.session.add(MailingSeleccionFemenina(
            preinscripcion_id=preinscripcion.id, asunto=ASUNTO_INSCRIPCION,
            cuerpo="Email automático con el enlace de inscripción y autorización.", enviado_ok=True,
        ))
        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando email de inscripción a {preinscripcion.email}: {e}")
        db.session.add(MailingSeleccionFemenina(
            preinscripcion_id=preinscripcion.id, asunto=ASUNTO_INSCRIPCION,
            cuerpo="Email automático con el enlace de inscripción y autorización.",
            enviado_ok=False, error=str(e)[:500],
        ))
        db.session.commit()
        return False


def _resumen_html(inscripcion):
    filas = "".join(
        f"<tr><td style='padding:4px 0;font-size:13px;color:#444'><strong>Tutor/a {t.numero}:</strong> "
        f"{t.nombre_completo} ({t.email}) — firmado {t.firma_en.strftime('%d/%m/%Y %H:%M') if t.firma_en else '—'}</td></tr>"
        for t in inscripcion.tutores
    )
    return f"<table cellpadding='0' cellspacing='0' width='100%'>{filas}</table>"


def enviar_confirmacion_inscripcion(preinscripcion, inscripcion):
    """Al completarse el formulario: email de confirmación a cada tutor
    firmante, con un resumen de lo enviado para que quede constancia en su
    bandeja de entrada."""
    cuerpo_html = f"""
        <p>Hemos recibido correctamente la inscripción y autorización de <strong>{preinscripcion.nombre_completo}</strong>
        para el proceso de Selección Femenina de Pilotos de Carcross.</p>
        <p>Nos pondremos en contacto próximamente para concretar la entrevista personal.</p>
        {_resumen_html(inscripcion)}
    """
    html = _html_base(preinscripcion.nombre_completo, "Inscripción recibida", cuerpo_html)
    texto = (
        f"Hemos recibido correctamente la inscripción y autorización de {preinscripcion.nombre_completo}.\n"
        "Nos pondremos en contacto próximamente para concretar la entrevista personal."
    )
    for t in inscripcion.tutores:
        try:
            _enviar(t.email, ASUNTO_CONFIRMACION, html, texto)
        except Exception as e:
            current_app.logger.error(f"Error enviando confirmación de inscripción a {t.email}: {e}")

    db.session.add(MailingSeleccionFemenina(
        preinscripcion_id=preinscripcion.id, asunto=ASUNTO_CONFIRMACION,
        cuerpo="Confirmación automática de inscripción y autorización completada.", enviado_ok=True,
    ))
    db.session.commit()


def notificar_equipo_interno(preinscripcion, inscripcion=None):
    from app.models.notificacion import Notificacion
    mensaje = f"{preinscripcion.nombre_completo} ha completado la inscripción y autorización. Ya se puede convocar a entrevista."
    tipo = "info"
    if inscripcion is not None and inscripcion.necesita_revision_custodia:
        mensaje += " Falta el documento de custodia (solo firmó un tutor) — pídeselo a la familia."
        tipo = "warning"
    db.session.add(Notificacion(
        tipo=tipo,
        titulo="Inscripción y autorización completada",
        mensaje=mensaje,
        url=f"/autoclub/seleccion-femenina/{preinscripcion.id}/editar",
        referencia=f"preinscripcion_carcross:{preinscripcion.id}",
    ))
    db.session.commit()
