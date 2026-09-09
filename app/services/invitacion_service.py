import io
import os
import secrets
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.utils import formatdate, make_msgid

import requests
from flask import current_app

from app.extensions import db
from app.models.invitacion import Invitacion
from app.models.evento import Evento
from app.services.evento_sync import _woo_eventos_url, _woo_eventos_auth
from app.services.mail_prensa import remitente_prensa, enviar_smtp_prensa

# Datos del evento para el cuerpo del email — aún no cerrados del todo,
# se dejan aquí como constantes fáciles de editar sin tocar el resto de
# la lógica de envío.
EVENTO_NOMBRE = "V Autocross Feeling Academy"
EVENTO_FECHA  = "27 de septiembre de 2027"
EVENTO_HORA   = "10:00 a 15:00"
EVENTO_LUGAR  = "Circuito La Dehesa, Alcolea del Pinar (Guadalajara)"
EVENTO_MAPA_URL = "https://maps.app.goo.gl/9BTq38WniUuZmJb27"

# Tono del texto de invitación según el tipo de invitado — editable aquí
# sin tocar la lógica de envío.
_TEXTOS_INVITACION = {
    "institucion": (
        f"Nos complace invitarles al <strong>{EVENTO_NOMBRE}</strong>, que se celebrará "
        "en el Circuito Auto Club La Dehesa (Alcolea del Pinar, Guadalajara).<br><br>"
        "Sería un placer contar con su presencia."
    ),
    "patrocinador": (
        f"Como patrocinador de <strong>{EVENTO_NOMBRE}</strong>, "
        "queremos invitarle a vivir el evento en primera persona. "
        "Gracias por hacer esto posible."
    ),
    "vip": (
        f"¡Nos encantaría contar contigo en el <strong>{EVENTO_NOMBRE}</strong>! "
        "Aquí tienes tu invitación personal para disfrutar del día en el circuito."
    ),
    "otro": (
        f"Queremos invitarte al <strong>{EVENTO_NOMBRE}</strong>. "
        "Será un placer contar contigo ese día."
    ),
}


def texto_invitacion(tipo):
    return _TEXTOS_INVITACION.get(tipo, _TEXTOS_INVITACION["otro"])


# ── EVENTO OBJETIVO ────────────────────────────────────────────────────────
def evento_objetivo():
    """El evento al que se asignan las invitaciones: el único marcado como
    activo (mismo criterio de respaldo que usa evento_sync para pedidos sin
    producto configurado en ningún evento)."""
    return Evento.query.filter_by(activo=True).order_by(Evento.id.desc()).first()


def asegurar_producto_registrado(evento):
    """Añade WOO_PRODUCT_ID_INVITACION a la lista de productos del evento si
    no está ya, para que el pedido de invitación (creado directamente vía
    API) lo recoja el webhook/sincronización como una entrada más — así el
    escaneo de QR el día del evento no necesita ninguna lógica nueva."""
    pid = str(current_app.config.get("WOO_PRODUCT_ID_INVITACION", "")).strip()
    if not pid or not evento:
        return
    ids = evento.producto_ids_lista
    if pid not in ids:
        ids.append(pid)
        evento.woo_producto_ids = ",".join(ids)
        db.session.commit()


# ── TOKEN ────────────────────────────────────────────────────────────────
def generar_token_unico():
    for _ in range(10):
        token = secrets.token_urlsafe(18)
        if not Invitacion.query.filter_by(token=token).first():
            return token
    raise RuntimeError("No se pudo generar un token único para la invitación tras varios intentos.")


# ── WOOCOMMERCE ────────────────────────────────────────────────────────────
def crear_pedido_woo_invitacion(nombre, email, tipo, token):
    product_id = current_app.config.get("WOO_PRODUCT_ID_INVITACION", "")
    if not product_id:
        raise RuntimeError("Falta configurar WOO_PRODUCT_ID_INVITACION en el .env.")

    resp = requests.post(
        _woo_eventos_url("orders"),
        json={
            "status": "completed",
            "billing": {"first_name": nombre, "email": email},
            "line_items": [{"product_id": int(product_id), "quantity": 1}],
            "meta_data": [
                {"key": "token_pase", "value": token},
                {"key": "tipo_invitacion", "value": tipo},
            ],
        },
        auth=_woo_eventos_auth(),
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["id"]


# ── QR ───────────────────────────────────────────────────────────────────
def _qr_dir():
    path = os.path.join(current_app.root_path, "static", "uploads", "autoclub", "invitaciones")
    os.makedirs(path, exist_ok=True)
    return path


def generar_qr_bytes(token):
    import qrcode
    img = qrcode.make(token)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generar_qr_archivo(token):
    """Genera el PNG del QR y lo guarda en disco. Devuelve la ruta relativa
    a static/ (para usar con url_for('static', filename=...))."""
    data = generar_qr_bytes(token)
    filename = f"{token}.png"
    with open(os.path.join(_qr_dir(), filename), "wb") as f:
        f.write(data)
    return f"uploads/autoclub/invitaciones/{filename}"


# ── EMAIL ────────────────────────────────────────────────────────────────
def _html_invitacion(invitacion):
    verde = "#16a34a"
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:'Segoe UI',Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:32px 16px">
  <tr><td align="center">
    <table width="480" cellpadding="0" cellspacing="0" style="max-width:480px;width:100%;background:#fff;border-radius:12px;overflow:hidden;border-top:4px solid {verde}">
      <tr>
        <td style="background:#0D0D0D;padding:22px 32px">
          <span style="font-size:18px;font-weight:900;color:#fff">AUTOCLUB LA DEHESA</span>
        </td>
      </tr>
      <tr>
        <td style="padding:32px">
          <span style="display:inline-block;background:#dcfce7;color:{verde};font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.5px;padding:4px 10px;border-radius:20px;margin-bottom:10px">
            Invitación
          </span>
          <h1 style="margin:0 0 12px;font-size:22px;font-weight:800;color:#0D0D0D">
            {EVENTO_NOMBRE}
          </h1>
          <p style="margin:0 0 16px;font-size:15px;color:#333;line-height:1.5">
            Hola <strong>{invitacion.nombre}</strong>,
          </p>
          <p style="margin:0 0 20px;font-size:15px;color:#333;line-height:1.6">
            {texto_invitacion(invitacion.tipo)}
          </p>
          <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;margin-bottom:24px">
            <tr>
              <td style="padding:14px 18px;font-size:13px;color:#444;line-height:1.8;border-left:3px solid {verde}">
                <strong style="color:{verde}">Fecha:</strong> {EVENTO_FECHA}<br>
                <strong style="color:{verde}">Hora:</strong> {EVENTO_HORA}<br>
                <strong style="color:{verde}">Lugar:</strong> {EVENTO_LUGAR}
                &nbsp;·&nbsp;<a href="{EVENTO_MAPA_URL}" style="color:{verde};font-weight:700;text-decoration:none">Cómo llegar</a>
              </td>
            </tr>
          </table>
          <table width="100%" cellpadding="0" cellspacing="0">
            <tr><td align="center" style="padding-bottom:10px">
              <img src="cid:qr_image" alt="Código QR de tu invitación" width="220" height="220" style="display:block;border:2px solid {verde};border-radius:8px">
            </td></tr>
            <tr><td align="center" style="padding-bottom:22px">
              <span style="font-size:11px;color:#999;word-break:break-all">{invitacion.token}</span>
            </td></tr>
          </table>
          <p style="margin:0;font-size:13px;color:#666;line-height:1.6">
            Presenta este código QR (en el móvil o impreso) en el control de acceso el día del evento.
          </p>
        </td>
      </tr>
      <tr>
        <td style="background:#0D0D0D;padding:16px 32px;font-size:11px;color:#777">
          Autoclub La Dehesa
        </td>
      </tr>
    </table>
  </td></tr>
</table>
</body>
</html>"""


def _texto_plano_invitacion(invitacion):
    import re as _re
    cuerpo = _re.sub(r"<[^>]+>", "", texto_invitacion(invitacion.tipo))
    return (
        f"Invitación · {EVENTO_NOMBRE}\n\n"
        f"Hola {invitacion.nombre},\n\n{cuerpo}\n\n"
        f"Fecha: {EVENTO_FECHA}\nHora: {EVENTO_HORA}\nLugar: {EVENTO_LUGAR}\n"
        f"Cómo llegar: {EVENTO_MAPA_URL}\n\n"
        f"Tu código: {invitacion.token}\n\n"
        "Presenta el QR adjunto (o este código) en el control de acceso el día del evento."
    )


def _construir_mime_invitacion(invitacion, qr_bytes, sender_user, sender_domain):
    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(_texto_plano_invitacion(invitacion), "plain", "utf-8"))
    alt.attach(MIMEText(_html_invitacion(invitacion), "html", "utf-8"))

    outer = MIMEMultipart("related")
    outer.attach(alt)

    img = MIMEImage(qr_bytes, _subtype="png")
    img.add_header("Content-ID", "<qr_image>")
    img.add_header("Content-Disposition", "inline", filename=f"{invitacion.token}.png")
    outer.attach(img)

    outer["Subject"] = f"Invitación · {EVENTO_NOMBRE}"
    outer["From"] = sender_user
    outer["To"] = invitacion.email
    outer["Date"] = formatdate(localtime=True)
    outer["Message-ID"] = make_msgid(domain=sender_domain)
    return outer


def enviar_email_invitacion(invitacion):
    """Envía (o reenvía) el email con el QR incrustado. No genera token ni
    pedido nuevo — reutiliza los ya guardados en la invitación."""
    try:
        qr_file = None
        if invitacion.qr_path:
            qr_file = os.path.join(current_app.root_path, "static", invitacion.qr_path.replace("/", os.sep))
            if not os.path.isfile(qr_file):
                qr_file = None
        if not qr_file:
            # Autocurativo: si la invitación se quedó sin QR (p.ej. el
            # paquete "qrcode" no estaba instalado en el momento de
            # crearla), lo generamos ahora con el mismo token — no hace
            # falta un pedido nuevo, el token ya es el mismo.
            invitacion.qr_path = generar_qr_archivo(invitacion.token)
            db.session.commit()
            qr_file = os.path.join(current_app.root_path, "static", invitacion.qr_path.replace("/", os.sep))
        with open(qr_file, "rb") as f:
            qr_bytes = f.read()

        sender, domain = remitente_prensa()
        mime_msg = _construir_mime_invitacion(invitacion, qr_bytes, sender, domain)
        enviar_smtp_prensa(mime_msg, invitacion.email)

        invitacion.email_enviado = True
        invitacion.email_enviado_en = datetime.utcnow()
        invitacion.email_error = None
        db.session.commit()
        return True
    except Exception as e:
        current_app.logger.error(f"Error enviando email de invitación {invitacion.id}: {e}")
        invitacion.email_error = str(e)[:500]
        db.session.commit()
        return False


# ── ORQUESTACIÓN: crear una invitación completa ───────────────────────────
def crear_invitacion(nombre, email, tipo, notas, usuario_id=None):
    """Ejecuta token → pedido WooCommerce → QR → guardar → email, en ese
    orden. Si falla la creación del pedido en WooCommerce no se guarda nada
    en la tabla local (nada de registros a medias). Si el QR o el email
    fallan DESPUÉS de crear el pedido, el registro sí se guarda (el pedido
    ya existe en WooCommerce) mostrando el error para poder reintentar el
    envío desde "reenviar" sin duplicar el pedido."""
    token = generar_token_unico()
    woo_order_id = crear_pedido_woo_invitacion(nombre, email, tipo, token)

    evento = evento_objetivo()
    asegurar_producto_registrado(evento)

    invitacion = Invitacion(
        nombre=nombre, email=email, tipo=tipo, notas=notas or None,
        token=token, woo_order_id=woo_order_id, creado_por_id=usuario_id,
    )
    db.session.add(invitacion)
    db.session.commit()

    try:
        invitacion.qr_path = generar_qr_archivo(token)
        db.session.commit()
    except Exception as e:
        invitacion.email_error = f"Error generando el QR: {e}"
        db.session.commit()
        return invitacion

    enviar_email_invitacion(invitacion)
    return invitacion


# ── CARGA POR LOTE (CSV) ───────────────────────────────────────────────────
CSV_HEADERS = ["nombre", "email", "tipo", "notas"]
_EMAIL_RE_INV = None


def _email_valido(email):
    global _EMAIL_RE_INV
    if _EMAIL_RE_INV is None:
        import re as _re
        _EMAIL_RE_INV = _re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    return bool(_EMAIL_RE_INV.match(email or ""))


def plantilla_csv_bytes():
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf)
    w.writerow(CSV_HEADERS)
    w.writerow(["Ejemplo Ayuntamiento", "contacto@ejemplo.es", "institucion", "Concejal de Deportes"])
    return buf.getvalue().encode("utf-8-sig")


def parsear_csv_invitaciones(file_stream):
    """Valida el CSV completo antes de devolver nada. Devuelve
    (filas_validas, errores) — si hay errores, filas_validas está vacío:
    no se procesa nada del lote hasta que el CSV esté limpio."""
    import csv as _csv
    from app.models.invitacion import TIPOS_INVITACION_KEYS

    try:
        texto = file_stream.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return [], [{"fila": 0, "campo": "archivo", "error": "El archivo no está en formato UTF-8."}]

    reader = _csv.DictReader(io.StringIO(texto))
    cabeceras = [h.strip() for h in (reader.fieldnames or [])]
    if cabeceras != CSV_HEADERS:
        return [], [{
            "fila": 0, "campo": "cabeceras",
            "error": f"Las cabeceras deben ser exactamente: {','.join(CSV_HEADERS)} (encontrado: {','.join(cabeceras) or 'vacío'}).",
        }]

    errores = []
    filas = []
    for i, row in enumerate(reader, start=2):  # fila 1 = cabeceras
        nombre = (row.get("nombre") or "").strip()
        email = (row.get("email") or "").strip()
        tipo = (row.get("tipo") or "").strip()
        notas = (row.get("notas") or "").strip()

        if not nombre:
            errores.append({"fila": i, "campo": "nombre", "error": "El nombre no puede estar vacío."})
        if not email:
            errores.append({"fila": i, "campo": "email", "error": "El email no puede estar vacío."})
        elif not _email_valido(email):
            errores.append({"fila": i, "campo": "email", "error": f"Email con formato no válido: {email}"})
        if tipo not in TIPOS_INVITACION_KEYS:
            errores.append({"fila": i, "campo": "tipo", "error": f"Tipo no válido: «{tipo}». Debe ser uno de {', '.join(TIPOS_INVITACION_KEYS)}."})

        filas.append({"fila": i, "nombre": nombre, "email": email, "tipo": tipo, "notas": notas})

    if errores:
        return [], errores

    # Duplicados: invitaciones ya existentes con el mismo email — se marcan
    # para excluirlas del envío por defecto en la previsualización.
    emails = [f["email"] for f in filas]
    existentes = {
        inv.email for inv in Invitacion.query.filter(Invitacion.email.in_(emails)).all()
    } if emails else set()
    for f in filas:
        f["ya_invitado"] = f["email"] in existentes

    return filas, []


def procesar_lote(filas, usuario_id=None):
    """Crea una invitación por fila, reutilizando crear_invitacion(). Un
    fallo en una fila no aborta el resto — se recopila un resumen final."""
    resultado = {"ok": [], "fallidas": []}
    for f in filas:
        try:
            crear_invitacion(f["nombre"], f["email"], f["tipo"], f.get("notas", ""), usuario_id)
            resultado["ok"].append(f)
        except Exception as e:
            current_app.logger.error(f"Error creando invitación por lote para {f.get('email')}: {e}")
            resultado["fallidas"].append({**f, "error": str(e)[:300]})
    return resultado
