"""
Mailing masivo a las inscritas en "Selección Femenina de Pilotos de
Carcross". Usa la cuenta MAIL_PRENSA_* (escuderia@autoclubladehesa.com,
ver app/services/mail_prensa.py) y una plantilla con los colores propios
del proyecto: rojo, negro y blanco (los mismos de la landing pública).
"""
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from flask import current_app

from app.extensions import db
from app.models.preinscripcion_carcross import PreinscripcionCarcross, MailingSeleccionFemenina
from app.services.mail_prensa import remitente_prensa, enviar_smtp_prensa

ROJO   = "#AD1726"
NEGRO  = "#0D0D0D"
BLANCO = "#FFFFFF"


def _primer_nombre(nombre_completo):
    return (nombre_completo or "").strip().split(" ")[0] or "candidata"


def _html_mailing(nombre_completo, cuerpo_html):
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
          <p style="margin:0 0 18px;font-size:15px;color:#222">
            Hola <strong>{_primer_nombre(nombre_completo)}</strong>,
          </p>
          <div style="font-size:15px;color:#222;line-height:1.7">
            {cuerpo_html}
          </div>
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


def _texto_plano_mailing(nombre_completo, cuerpo_texto):
    return f"Hola {_primer_nombre(nombre_completo)},\n\n{cuerpo_texto}"


def destinatarias_mailing(estados=None):
    """Lista de PreinscripcionCarcross que recibirían el mailing con este
    filtro de estados (None/[] = todas). Se usa tanto para el recuento en
    la previsualización como para el envío real — misma consulta."""
    query = PreinscripcionCarcross.query
    if estados:
        query = query.filter(PreinscripcionCarcross.estado.in_(estados))
    return query.order_by(PreinscripcionCarcross.nombre_completo.asc()).all()


def enviar_mailing_masivo(asunto, cuerpo_texto, estados=None):
    """Envía el mailing a cada destinataria por separado (personalizado con
    su nombre). Un fallo puntual (ej. email inválido) no aborta el resto —
    se recopila un resumen final, igual que el lote de invitaciones."""
    destinatarias = destinatarias_mailing(estados)
    cuerpo_html = (cuerpo_texto or "").replace("\n", "<br>")
    sender, domain = remitente_prensa()
    resultado = {"enviados": [], "fallidos": []}

    for p in destinatarias:
        try:
            msg = MIMEMultipart("alternative")
            msg.attach(MIMEText(_texto_plano_mailing(p.nombre_completo, cuerpo_texto), "plain", "utf-8"))
            msg.attach(MIMEText(_html_mailing(p.nombre_completo, cuerpo_html), "html", "utf-8"))
            msg["Subject"] = asunto
            msg["From"] = sender
            msg["To"] = p.email
            msg["Date"] = formatdate(localtime=True)
            msg["Message-ID"] = make_msgid(domain=domain)
            enviar_smtp_prensa(msg, p.email)
            resultado["enviados"].append(p.id)
            db.session.add(MailingSeleccionFemenina(
                preinscripcion_id=p.id, asunto=asunto, cuerpo=cuerpo_texto, enviado_ok=True,
            ))
        except Exception as e:
            current_app.logger.error(f"Error enviando mailing a {p.email}: {e}")
            resultado["fallidos"].append({"id": p.id, "nombre": p.nombre_completo, "email": p.email, "error": str(e)[:300]})
            db.session.add(MailingSeleccionFemenina(
                preinscripcion_id=p.id, asunto=asunto, cuerpo=cuerpo_texto, enviado_ok=False, error=str(e)[:500],
            ))
        # Se hace commit en cada vuelta (no al final) para que, si el envío
        # se corta a medias, no se pierda el registro de lo que sí llegó.
        db.session.commit()

    return resultado
