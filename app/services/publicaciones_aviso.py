"""
Avisos por email del contenido de redes pendiente de subir. Un resumen
diario (job del scheduler) a los destinatarios configurados, y avisos
sueltos de una publicación desde su ficha.
"""
from datetime import date, datetime, timedelta
from html import escape

from flask import current_app, has_request_context, url_for
from flask_mail import Message

from app.extensions import db, mail
from app.models.configuracion import Configuracion
from app.models.publicacion_rrss import PublicacionRRSS, DestinatarioAvisoRRSS

# Las atrasadas se siguen recordando durante una semana como máximo.
DIAS_ATRASO_MAX = 7


def destinatarios_activos():
    return [d.email for d in DestinatarioAvisoRRSS.query.filter_by(activo=True).order_by(DestinatarioAvisoRRSS.email)]


def pendientes_para_aviso(dias_antelacion, hoy=None):
    """Contenido que hay que subir antes de su fecha (no incluye lo que se
    graba y publica en el momento)."""
    hoy = hoy or date.today()
    return (PublicacionRRSS.query
            .filter(PublicacionRRSS.estado == "pendiente",
                    PublicacionRRSS.en_directo.is_(False),
                    PublicacionRRSS.fecha >= hoy - timedelta(days=DIAS_ATRASO_MAX),
                    PublicacionRRSS.fecha <= hoy + timedelta(days=dias_antelacion))
            .order_by(PublicacionRRSS.fecha, PublicacionRRSS.id).all())


def en_directo_de_hoy(hoy=None):
    """Lo que se graba y publica en el momento: solo se recuerda su mismo día."""
    hoy = hoy or date.today()
    return (PublicacionRRSS.query
            .filter(PublicacionRRSS.estado == "pendiente",
                    PublicacionRRSS.en_directo.is_(True),
                    PublicacionRRSS.fecha == hoy)
            .order_by(PublicacionRRSS.id).all())


def _url(endpoint, **kw):
    # Desde el job programado no hay petición activa: se compone con APP_BASE_URL.
    if has_request_context():
        return url_for(endpoint, _external=True, **kw)
    base = current_app.config.get("APP_BASE_URL", "").rstrip("/")
    with current_app.test_request_context():
        return base + url_for(endpoint, **kw)


def _enlace(p):
    return _url("marketing.publicaciones_detalle", id=p.id)


def _fila_html(p, hoy):
    color, fondo = p.categoria_info[1], p.categoria_info[2]
    if p.en_directo and p.fecha == hoy:
        cuando = "<span style='color:#C2410C;font-weight:700'>Hoy · en el momento</span>"
    elif p.fecha < hoy:
        cuando = f"<span style='color:#DC2626;font-weight:700'>Atrasada ({p.fecha.strftime('%d/%m')})</span>"
    elif p.fecha == hoy:
        cuando = "<span style='color:#C2410C;font-weight:700'>Hoy</span>"
    else:
        cuando = p.fecha.strftime("%a %d/%m").capitalize()
    enlace = _enlace(p)
    titulo = escape(p.titulo)
    if enlace:
        titulo = f"<a href='{enlace}' style='color:#111;text-decoration:none'>{titulo}</a>"
    detalle = " · ".join(x for x in (p.tipo_info[0], escape(p.formato or ""), p.produccion_label if p.produccion else "") if x)
    indic = escape(p.indicaciones or "")
    if len(indic) > 220:
        indic = indic[:220] + "…"
    return f"""
<tr><td style="padding:12px 0;border-bottom:1px solid #eee">
  <div style="font-size:12px;margin-bottom:3px">{cuando}
    <span style="background:{fondo};color:{color};border-radius:10px;padding:1px 8px;font-size:11px;font-weight:700;margin-left:6px">{escape(p.categoria_info[0])}</span>
  </div>
  <div style="font-size:15px;font-weight:700">{titulo}</div>
  <div style="font-size:12px;color:#666;margin-top:2px">{detalle}</div>
  {f'<div style="font-size:12px;color:#444;margin-top:6px">{indic}</div>' if indic else ''}
</td></tr>"""


def _html(publicaciones, hoy, intro, directo=()):
    filas = "".join(_fila_html(p, hoy) for p in publicaciones)
    if directo:
        filas_directo = "".join(_fila_html(p, hoy) for p in directo)
        bloque_directo = (f"<h3 style='margin:22px 0 4px;font-size:16px'>Para grabar y publicar hoy</h3>"
                          f"<p style='margin:0 0 4px;color:#555;font-size:13px'>No hay que subirlo antes: se hace en el momento.</p>"
                          f"<table width='100%' cellpadding='0' cellspacing='0'>{filas_directo}</table>")
    else:
        bloque_directo = ""
    if publicaciones:
        bloque_subir = (f"<p style='margin:0 0 8px;color:#555;font-size:14px'>Sube el vídeo o la foto y la descripción en su ficha del CRM; al subirlo deja de avisarse.</p>"
                        f"<table width='100%' cellpadding='0' cellspacing='0'>{filas}</table>")
    else:
        bloque_subir = ""
    calendario = _url("marketing.publicaciones_calendario")
    boton = (f"<p style='margin:20px 0 0'><a href='{calendario}' style='background:#AD1726;color:#fff;padding:10px 18px;"
             f"border-radius:8px;text-decoration:none;font-weight:700'>Abrir el calendario</a></p>") if calendario else ""
    return f"""<!DOCTYPE html><html><body style="margin:0;background:#f4f4f4;font-family:Segoe UI,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px"><tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border-radius:12px;border-top:4px solid #AD1726">
<tr><td style="padding:24px 28px">
  <div style="font-size:12px;color:#AD1726;font-weight:700;letter-spacing:1px;text-transform:uppercase">Calendario de publicaciones</div>
  <h2 style="margin:6px 0 10px;font-size:20px">{escape(intro)}</h2>
  {bloque_subir}
  {bloque_directo}
  {boton}
</td></tr></table></td></tr></table></body></html>"""


def _enviar(destinatarios, asunto, html):
    msg = Message(asunto, recipients=destinatarios, html=html)
    mail.send(msg)


def enviar_resumen(forzar=False, hoy=None):
    """Envía el resumen de pendientes. Devuelve (n_publicaciones, n_destinatarios, error)."""
    hoy = hoy or date.today()
    config = Configuracion.get()
    if not forzar:
        if not config.rrss_aviso_activo or config.rrss_ultimo_resumen == hoy:
            return 0, 0, None
    destinatarios = destinatarios_activos()
    if not destinatarios:
        return 0, 0, "No hay correos añadidos para recibir los avisos."
    pubs = pendientes_para_aviso(config.rrss_aviso_dias, hoy)
    directo = en_directo_de_hoy(hoy)
    if not pubs and not directo:
        return 0, len(destinatarios), None
    partes = []
    if pubs:
        n_hoy = sum(1 for p in pubs if p.fecha <= hoy)
        partes.append(f"{len(pubs)} contenido{'s' if len(pubs) != 1 else ''} por subir"
                      + (f" ({n_hoy} para hoy o atrasado{'s' if n_hoy != 1 else ''})" if n_hoy else ""))
    if directo:
        partes.append(f"{len(directo)} para grabar y publicar hoy")
    asunto = "Redes: " + " · ".join(partes)
    intro = "Contenido pendiente de subir" if pubs else "Hoy toca grabar y publicar"
    try:
        _enviar(destinatarios, asunto, _html(pubs, hoy, intro, directo))
    except Exception as e:
        current_app.logger.error(f"Aviso de publicaciones fallido: {e}")
        return 0, len(destinatarios), str(e)
    ahora = datetime.utcnow()
    for p in pubs + directo:
        p.ultimo_aviso_en = ahora
    config.rrss_ultimo_resumen = hoy
    db.session.commit()
    return len(pubs) + len(directo), len(destinatarios), None


def enviar_aviso_publicacion(publicacion):
    """Aviso suelto de una publicación. Devuelve (n_destinatarios, error)."""
    destinatarios = destinatarios_activos()
    if not destinatarios:
        return 0, "No hay correos añadidos para recibir los avisos."
    fecha = publicacion.fecha.strftime('%d/%m')
    if publicacion.en_directo:
        asunto = f"Redes: hay que grabar y publicar «{publicacion.titulo}» ({fecha})"
        html = _html([], date.today(), "Para grabar y publicar en el momento", [publicacion])
    else:
        asunto = f"Redes: hay que subir «{publicacion.titulo}» ({fecha})"
        html = _html([publicacion], date.today(), "Contenido pendiente de subir")
    try:
        _enviar(destinatarios, asunto, html)
    except Exception as e:
        current_app.logger.error(f"Aviso de publicación {publicacion.id} fallido: {e}")
        return len(destinatarios), str(e)
    publicacion.ultimo_aviso_en = datetime.utcnow()
    db.session.commit()
    return len(destinatarios), None
