"""
Servicio de ejecución de campañas de marketing.
Resuelve destinatarios, envía emails/WA y registra resultados.
"""
import logging
from datetime import datetime

from app.extensions import db

log = logging.getLogger(__name__)


def check_scheduled_campaigns():
    """Llamado por el scheduler: lanza campañas cuya fecha_envio ya pasó."""
    from app.models.campana import Campana
    now = datetime.utcnow()
    pendientes = Campana.query.filter(
        Campana.estado == "programada",
        Campana.fecha_envio <= now,
    ).all()
    for c in pendientes:
        ejecutar_campana(c.id)
    return len(pendientes)


def ejecutar_campana(campana_id):
    """
    Ejecuta una campaña: resuelve destinatarios, envía emails/WA, actualiza stats.
    Devuelve dict con enviados, errores, omitidos.
    """
    from app.models.campana import Campana, CampanaLog
    from app.models.cliente import Cliente
    from app.models.empresa import Empresa
    from app.models.tag import ClienteTag, EmpresaTag

    campana = Campana.query.get(campana_id)
    if not campana:
        return {"enviados": 0, "errores": 0, "omitidos": 0}
    if campana.estado == "enviando":
        return {"enviados": 0, "errores": 0, "omitidos": 0}

    campana.estado = "enviando"
    db.session.commit()

    stats = {"enviados": 0, "errores": 0, "omitidos": 0}

    try:
        incluir_ids = {ct.tag_id for ct in campana.campana_tags if ct.modo == "incluir"}
        excluir_ids = {ct.tag_id for ct in campana.campana_tags if ct.modo == "excluir"}

        destinatarios = []  # list of (tipo, id, nombre, email, obj)

        if campana.segmento in ("clientes", "todos"):
            for c in Cliente.query.all():
                tag_ids = {ct.tag_id for ct in ClienteTag.query.filter_by(cliente_id=c.id)}
                if incluir_ids and not (incluir_ids & tag_ids):
                    continue
                if excluir_ids and (excluir_ids & tag_ids):
                    continue
                destinatarios.append(("cliente", c.id, c.nombre_completo, c.email, c))

        if campana.segmento in ("empresas", "todos"):
            for e in Empresa.query.filter_by(activo=True).all():
                tag_ids = {et.tag_id for et in EmpresaTag.query.filter_by(empresa_id=e.id)}
                if incluir_ids and not (incluir_ids & tag_ids):
                    continue
                if excluir_ids and (excluir_ids & tag_ids):
                    continue
                destinatarios.append(("empresa", e.id, e.nombre, e.email, e))

        canales = ["email", "whatsapp"] if campana.canal == "ambos" else [campana.canal]

        for (tipo, eid, nombre, email, obj) in destinatarios:
            for canal in canales:
                if canal == "email":
                    ok, error_msg = _enviar_email(campana, obj, tipo, nombre, email)
                else:
                    ok, error_msg = _enviar_wa(campana, obj, tipo, nombre)

                db.session.add(CampanaLog(
                    campana_id=campana.id,
                    entidad=tipo,
                    entidad_id=eid,
                    entidad_nombre=nombre,
                    entidad_email=email or "",
                    canal=canal,
                    estado="ok" if ok else "error",
                    error_msg=error_msg,
                ))

                _mlog(campana, tipo, eid, nombre, canal, ok, error_msg)

                if ok:
                    stats["enviados"] += 1
                else:
                    stats["errores"] += 1

        campana.estado = "enviada" if stats["errores"] == 0 else "error"
        campana.enviado_en = datetime.utcnow()
        campana.total_enviados += stats["enviados"]
        campana.total_errores  += stats["errores"]
        db.session.commit()

        from app.services.log_service import registrar_marketing_log
        registrar_marketing_log(
            "campana_enviada" if stats["errores"] == 0 else "campana_error",
            resultado="ok" if stats["errores"] == 0 else "error",
            campana_id=campana.id,
            campana_nombre=campana.nombre,
            detalle=f"{stats['enviados']} enviados, {stats['errores']} errores",
            origen="scheduler",
        )

    except Exception as ex:
        db.session.rollback()
        try:
            campana.estado = "error"
            db.session.commit()
        except Exception:
            pass
        stats["errores"] += 1
        log.error(f"Error ejecutando campaña {campana_id}: {ex}")

    return stats


# ─── Envío email ──────────────────────────────────────────────────────────────

def _enviar_email(campana, obj, tipo, nombre, email):
    if not email:
        return False, "Sin email registrado"
    if not campana.plantilla_email_id:
        return False, "Sin plantilla email"
    try:
        from flask_mail import Message
        from app.extensions import mail
        from app.models.rule import PlantillaEmail

        plantilla = PlantillaEmail.query.get(campana.plantilla_email_id)
        if not plantilla:
            return False, "Plantilla email no encontrada"

        html   = _render(plantilla.cuerpo_html, obj, tipo, nombre)
        asunto = _render(plantilla.asunto, obj, tipo, nombre)

        msg = Message(asunto, recipients=[email], html=html)
        mail.send(msg)
        return True, ""
    except Exception as e:
        return False, str(e)[:300]


# ─── Envío WhatsApp (stub — requiere integración externa) ─────────────────────

def _enviar_wa(campana, obj, tipo, nombre):
    if not campana.plantilla_wa_id:
        return False, "Sin plantilla WhatsApp"
    from app.models.campana import PlantillaWA
    plantilla = PlantillaWA.query.get(campana.plantilla_wa_id)
    if not plantilla:
        return False, "Plantilla WhatsApp no encontrada"
    # WhatsApp real requiere Meta Cloud API / Twilio.
    # Por ahora se registra como OK (pendiente de integración).
    return True, ""


# ─── Renderizado de variables ─────────────────────────────────────────────────

def _render(texto, obj, tipo, nombre):
    from app.models.cliente import Cliente
    from app.models.empresa import Empresa

    vars_map = {
        "nombre":     nombre,
        "fecha_hoy":  datetime.utcnow().strftime("%d/%m/%Y"),
    }
    if tipo == "cliente" and isinstance(obj, Cliente):
        vars_map.update({
            "nombre_completo": obj.nombre_completo,
            "nombre":          obj.nombre,
            "apellido":        obj.apellido or "",
            "email":           obj.email or "",
            "telefono":        obj.telefono or "",
            "total_reservas":  str(obj.total_reservas),
        })
    elif tipo == "empresa" and isinstance(obj, Empresa):
        vars_map.update({
            "nombre_empresa":  obj.nombre,
            "empresa":         obj.nombre,
            "email":           obj.email or "",
            "sector":          obj.sector or "",
            "contacto":        obj.persona_contacto or "",
        })
    for var, val in vars_map.items():
        texto = texto.replace("{{" + var + "}}", val)
    return texto


# ─── Log individual por destinatario ─────────────────────────────────────────

def _mlog(campana, tipo, eid, nombre, canal, ok, error_msg):
    try:
        from app.services.log_service import registrar_marketing_log
        evento = f"campana_{canal}_ok" if ok else f"campana_{canal}_error"
        registrar_marketing_log(
            evento,
            resultado="ok" if ok else "error",
            campana_id=campana.id,
            campana_nombre=campana.nombre,
            entidad=tipo,
            entidad_id=eid,
            entidad_nombre=nombre,
            accion_tipo=canal,
            detalle=error_msg if not ok else f"Enviado vía {canal}",
            origen="scheduler",
        )
    except Exception:
        pass
