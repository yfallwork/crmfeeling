"""
Envío SMTP de bajo nivel usando la cuenta de correo "prensa / AutoClub"
(MAIL_PRENSA_* — escuderia@autoclubladehesa.com, cuenta separada en
Dondominio). Se usa para todo lo que sale a nombre de AutoClub La Dehesa
que no pasa por el Flask-Mail genérico del CRM (invitaciones de Eventos,
mailing de Selección Femenina): permite adjuntos con Content-ID inline y
un control fino del propio mensaje MIME que Flask-Mail no da.
"""
import smtplib
import ssl
import base64 as _b64

from flask import current_app


def remitente_prensa():
    """(direccion_from, dominio) para construir cabeceras Message-ID/From."""
    sender = current_app.config.get("MAIL_PRENSA_SENDER", "") or current_app.config.get("MAIL_PRENSA_USERNAME", "")
    domain = sender.split("@")[-1] if "@" in sender else "mail.local"
    return sender, domain


def enviar_smtp_prensa(mime_msg, destinatario):
    """Envía un email.mime ya construido a un único destinatario, autenticado
    con la cuenta MAIL_PRENSA_*. Lanza RuntimeError/smtplib.* si algo falla —
    quien llame decide cómo registrar el error, no se traga excepciones."""
    user   = current_app.config.get("MAIL_PRENSA_USERNAME", "")
    passwd = current_app.config.get("MAIL_PRENSA_PASSWORD", "")
    server = current_app.config.get("MAIL_PRENSA_SERVER", "smtp.arsys.es")
    port   = current_app.config.get("MAIL_PRENSA_PORT", 587)
    if not user or not passwd:
        raise RuntimeError("Falta configurar MAIL_PRENSA_USERNAME / MAIL_PRENSA_PASSWORD en el .env.")

    context = ssl.create_default_context()
    if port == 465:
        conn = smtplib.SMTP_SSL(server, port, context=context, timeout=20)
    else:
        conn = smtplib.SMTP(server, port, timeout=20)
        conn.ehlo()
        conn.starttls(context=context)
    try:
        conn.ehlo()
        creds = _b64.b64encode(f"\x00{user}\x00{passwd}".encode("utf-8")).decode()
        code, msg = conn.docmd("AUTH PLAIN", creds)
        if code != 235:
            raise smtplib.SMTPAuthenticationError(code, msg)
        # as_bytes(), no as_string(): el cuerpo va en UTF-8 con
        # Content-Transfer-Encoding 8bit (tildes, "ñ", etc. tal cual). Si se
        # pasa un str, smtplib intenta un .encode('ascii') antes de enviar y
        # revienta con cualquier carácter no-ASCII — como bytes ya
        # codificados, se envían tal cual (el servidor anuncia 8BITMIME).
        conn.sendmail(user, [destinatario], mime_msg.as_bytes())
    finally:
        try:
            conn.quit()
        except Exception:
            pass
