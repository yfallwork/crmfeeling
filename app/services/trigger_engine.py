"""
Motor de triggers de marketing.
Cómo usarlo:
    from app.services.trigger_engine import disparar_trigger
    disparar_trigger('crm.cliente.creado', 'cliente', cliente.id)

Eventos predefinidos:
    crm.cliente.creado          — nuevo cliente (manual o WooCommerce)
    crm.empresa.creada          — nueva empresa TB
    crm.reserva.creada          — reserva nueva en estado pendiente/reservado
    crm.reserva.disfrutada      — reserva marcada como disfrutada
    woo.order.gift              — pedido WooCommerce con fecha abierta (regalo/voucher)
    woo.cart.abandoned          — carrito abandonado (via webhook WooCommerce — externo)
    crm.empresa.cualificada         — (pendiente: sin botón de cualificación)
"""
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


def _marketing_activo():
    """Interruptor global desde Configuración general. Si está desactivado,
    ninguna automatización de marketing debe ejecutarse."""
    try:
        from app.models.configuracion import Configuracion
        return Configuracion.get().marketing_activo
    except Exception:
        return True  # fail-open: un error de BD no debe bloquear el flujo normal


# ── Sustitución de variables ──────────────────────────────────────────────────

def _sustituir(texto, ctx):
    """Reemplaza {{variable}} con valores del contexto."""
    if not texto:
        return ""
    for k, v in ctx.items():
        texto = texto.replace("{{" + k + "}}", str(v or ""))
    return texto


# ── Contexto por tipo de entidad ──────────────────────────────────────────────

def _get_contexto(entidad_tipo, entidad_id):
    try:
        if entidad_tipo == "cliente":
            from app.models.cliente import Cliente
            c = Cliente.query.get(entidad_id)
            if not c:
                return None
            return {
                "nombre":         c.nombre or "",
                "apellido":       c.apellido or "",
                "nombre_completo": c.nombre_completo,
                "email":          c.email or "",
                "telefono":       c.telefono or "",
                "experiencia":    "",
            }
        else:
            from app.models.empresa import Empresa
            e = Empresa.query.get(entidad_id)
            if not e:
                return None
            nombre_contacto = e.persona_contacto or e.nombre or ""
            return {
                "nombre":         nombre_contacto,
                "apellido":       "",
                "nombre_completo": e.nombre or "",
                "email":          e.email or "",
                "telefono":       e.telefono or "",
                "contacto":       e.persona_contacto or "",
                "sector":         e.sector or "",
                "experiencia":    "",
            }
    except Exception as e:
        log.error(f"[TriggerEngine] _get_contexto error: {e}")
        return None


def _get_nombre(entidad_tipo, entidad_id):
    ctx = _get_contexto(entidad_tipo, entidad_id)
    if not ctx:
        return ""
    return ctx.get("nombre_completo") or ctx.get("nombre") or ""


def _get_entity_tag_ids(entidad_tipo, entidad_id):
    try:
        if entidad_tipo == "cliente":
            from app.models.tag import ClienteTag
            return {ct.tag_id for ct in
                    ClienteTag.query.filter_by(cliente_id=entidad_id).all()}
        else:
            from app.models.tag import EmpresaTag
            return {et.tag_id for et in
                    EmpresaTag.query.filter_by(empresa_id=entidad_id).all()}
    except Exception:
        return set()


# ── Ejecución de acciones ─────────────────────────────────────────────────────

def _ejecutar_email(accion, ctx, entidad_tipo, entidad_id, entidad_nombre, rule):
    from app.services.log_service import registrar_marketing_log
    if not accion.plantilla:
        registrar_marketing_log(
            "accion_error", "error",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="email",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle="Sin plantilla asignada a la acción de email", origen="sistema",
        )
        return

    email = ctx.get("email", "")
    if not email:
        registrar_marketing_log(
            "accion_error", "error",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="email",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle="La entidad no tiene dirección de email", origen="sistema",
        )
        return

    try:
        from flask_mail import Message
        from app.extensions import mail
        from app.services.email_service import _base_email

        asunto = _sustituir(accion.plantilla.asunto, ctx)
        cuerpo = _sustituir(accion.plantilla.cuerpo_html or "", ctx)
        html   = _base_email(cuerpo, asunto)

        msg = Message(asunto, recipients=[email], html=html)
        mail.send(msg)

        registrar_marketing_log(
            "accion_email", "ok",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="email",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"Email enviado a {email} — Asunto: {asunto}",
            origen="sistema",
        )
        log.info(f"[TriggerEngine] Email enviado a {email} — {asunto}")

    except Exception as e:
        registrar_marketing_log(
            "accion_error", "error",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="email",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"Error al enviar email: {str(e)[:300]}",
            origen="sistema",
        )
        log.error(f"[TriggerEngine] Error email: {e}")


def _ejecutar_whatsapp(accion, ctx, entidad_tipo, entidad_id, entidad_nombre, rule):
    from app.services.log_service import registrar_marketing_log

    telefono = ctx.get("telefono", "")
    if not telefono:
        registrar_marketing_log(
            "accion_error", "error",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="whatsapp",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle="La entidad no tiene teléfono", origen="sistema",
        )
        return

    mensaje = _sustituir(accion.mensaje_whatsapp or "", ctx)
    if not mensaje:
        return

    try:
        from app.services.whatsapp_service import _formatear_telefono, _enviar_whatsapp
        tel = _formatear_telefono(telefono)
        if not tel:
            raise ValueError("Teléfono no válido")
        ok, sid = _enviar_whatsapp(tel, mensaje)

        registrar_marketing_log(
            "accion_whatsapp" if ok else "accion_error",
            "ok" if ok else "error",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="whatsapp",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"WhatsApp → {tel} ({sid}): {mensaje[:80]}",
            origen="sistema",
        )
    except Exception as e:
        registrar_marketing_log(
            "accion_error", "error",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="whatsapp",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"Error WhatsApp: {str(e)[:300]}",
            origen="sistema",
        )
        log.error(f"[TriggerEngine] Error WhatsApp: {e}")


def _ejecutar_notificacion(accion, ctx, entidad_tipo, entidad_id, entidad_nombre, rule):
    from app.services.log_service import registrar_marketing_log
    try:
        from app.models.rule import Notificacion
        from app.extensions import db

        titulo = _sustituir(accion.mensaje_notificacion or rule.nombre, ctx)
        n = Notificacion(
            titulo=titulo[:200],
            mensaje=f"Generada automáticamente por la norma: «{rule.nombre}»",
            tipo="recordatorio",
            prioridad="media",
            entidad=entidad_tipo,
            entidad_id=entidad_id,
            entidad_nombre=entidad_nombre,
            rule_id=rule.id,
        )
        db.session.add(n)
        db.session.commit()

        registrar_marketing_log(
            "accion_notificacion", "ok",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="notificacion",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"Notificación creada: {titulo[:80]}",
            origen="sistema",
        )
    except Exception as e:
        registrar_marketing_log(
            "accion_error", "error",
            rule_id=rule.id, rule_nombre=rule.nombre, accion_tipo="notificacion",
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"Error creando notificación: {str(e)[:300]}",
            origen="sistema",
        )
        log.error(f"[TriggerEngine] Error notificación: {e}")


def _ejecutar_rule_acciones(rule_id, entidad_tipo, entidad_id):
    """Ejecuta todas las acciones de una norma para una entidad. Llamado inmediato o desde scheduler."""
    try:
        from app.models.rule import Rule
        from app.services.log_service import registrar_marketing_log

        rule = Rule.query.get(rule_id)
        if not rule or not rule.activo:
            return

        ctx = _get_contexto(entidad_tipo, entidad_id)
        if ctx is None:
            return

        entidad_nombre = ctx.get("nombre_completo") or ctx.get("nombre") or ""

        registrar_marketing_log(
            "norma_evaluada_ok", "ok",
            rule_id=rule.id, rule_nombre=rule.nombre,
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"Norma «{rule.nombre}» ejecutada ({len(rule.acciones)} acciones)",
            origen="sistema",
        )

        for accion in rule.acciones:
            if accion.tipo == "email":
                _ejecutar_email(accion, ctx, entidad_tipo, entidad_id, entidad_nombre, rule)
            elif accion.tipo == "whatsapp":
                _ejecutar_whatsapp(accion, ctx, entidad_tipo, entidad_id, entidad_nombre, rule)
            elif accion.tipo == "notificacion":
                _ejecutar_notificacion(accion, ctx, entidad_tipo, entidad_id, entidad_nombre, rule)

    except Exception as e:
        log.error(f"[TriggerEngine] _ejecutar_rule_acciones error (rule={rule_id}): {e}")


# ── Evaluación de normas por tag asignado (para tags temporales) ─────────────

def _disparar_por_tag_nuevo(tag_id, entidad_tipo, entidad_id):
    """
    Evalúa normas activas que requieran tag_id, igual que _disparar()
    pero partiendo de un tag ya asignado (no de un evento).
    """
    if not _marketing_activo():
        log.info("[TriggerEngine] Procesos de marketing desactivados — se omite evaluación de normas")
        return

    from sqlalchemy.orm import joinedload
    from app.models.rule import Rule
    active_tag_ids = _get_entity_tag_ids(entidad_tipo, entidad_id)

    reglas = (
        Rule.query
        .options(joinedload(Rule.rule_tags))
        .filter_by(activo=True)
        .all()
    )
    for rule in reglas:
        req_ids = {rt.tag_id for rt in rule.rule_tags if rt.tipo == "requerida"}
        exc_ids = {rt.tag_id for rt in rule.rule_tags if rt.tipo == "excluida"}

        if tag_id not in req_ids:
            continue
        if req_ids and not req_ids.issubset(active_tag_ids):
            continue
        if exc_ids & active_tag_ids:
            continue

        if rule.delay_horas == 0:
            _ejecutar_rule_acciones(rule.id, entidad_tipo, entidad_id)
        else:
            _programar_rule(rule, entidad_tipo, entidad_id,
                            _get_nombre(entidad_tipo, entidad_id))


# ── Motor principal ───────────────────────────────────────────────────────────

def disparar_trigger(evento, entidad_tipo, entidad_id):
    """
    Punto de entrada principal. Seguro llamar desde cualquier ruta — nunca propaga excepciones.

    Flujo:
      1. Busca tags sistemáticas con trigger_evento == evento y entidad == entidad_tipo
      2. Asigna los tags que aún no tiene la entidad
      3. Evalúa normas activas que requieran esos tags
      4. Ejecuta las acciones (inmediato si delay=0, programado si delay>0)
    """
    if not _marketing_activo():
        log.info(f"[TriggerEngine] Procesos de marketing desactivados — se omite '{evento}'")
        return
    try:
        _disparar(evento, entidad_tipo, entidad_id)
    except Exception as e:
        log.error(f"[TriggerEngine] disparar_trigger('{evento}') error: {e}")


def _disparar(evento, entidad_tipo, entidad_id):
    from app.models.tag import Tag, ClienteTag, EmpresaTag
    from app.models.rule import Rule
    from app.extensions import db
    from app.services.log_service import registrar_marketing_log

    # 1. Tags que coinciden con este evento
    tags_candidatos = Tag.query.filter_by(
        trigger_evento=evento,
        entidad=entidad_tipo,
        activo=True,
        tipo="sistematica",
    ).all()

    if not tags_candidatos:
        return

    entidad_nombre = _get_nombre(entidad_tipo, entidad_id)
    nuevos_tag_ids = set()

    # 2. Asignar tags nuevos
    for tag in tags_candidatos:
        ya_tiene = (
            ClienteTag.query.filter_by(cliente_id=entidad_id, tag_id=tag.id).first()
            if entidad_tipo == "cliente"
            else EmpresaTag.query.filter_by(empresa_id=entidad_id, tag_id=tag.id).first()
        )
        if not ya_tiene:
            if entidad_tipo == "cliente":
                db.session.add(ClienteTag(cliente_id=entidad_id, tag_id=tag.id, origen="sistema"))
            else:
                db.session.add(EmpresaTag(empresa_id=entidad_id, tag_id=tag.id, origen="sistema"))
            db.session.flush()
            nuevos_tag_ids.add(tag.id)

            registrar_marketing_log(
                "tag_trigger", "ok",
                tag_id=tag.id, tag_nombre=tag.nombre,
                entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
                detalle=f"Tag «{tag.nombre}» asignado automáticamente (trigger: {evento})",
                origen="sistema",
            )
            log.info(f"[TriggerEngine] Tag '{tag.slug}' → {entidad_tipo} #{entidad_id}")

    db.session.commit()

    if not nuevos_tag_ids:
        return  # todos los tags ya estaban asignados

    # 3. Tags activos de la entidad tras la asignación
    active_tag_ids = _get_entity_tag_ids(entidad_tipo, entidad_id)

    # 4. Evaluar normas
    from sqlalchemy.orm import joinedload
    reglas = (
        Rule.query
        .options(joinedload(Rule.rule_tags))
        .filter_by(activo=True)
        .all()
    )
    for rule in reglas:
        req_ids = {rt.tag_id for rt in rule.rule_tags if rt.tipo == "requerida"}
        exc_ids = {rt.tag_id for rt in rule.rule_tags if rt.tipo == "excluida"}

        # La norma debe tener al menos un tag recién asignado como requerido
        if not (req_ids & nuevos_tag_ids):
            continue

        # Todos los tags requeridos deben estar presentes
        if req_ids and not req_ids.issubset(active_tag_ids):
            continue

        # Ningún tag excluido debe estar presente
        if exc_ids & active_tag_ids:
            continue

        # 5. Ejecutar acciones
        if rule.delay_horas == 0:
            log.info(f"[TriggerEngine] Ejecutando norma '{rule.nombre}' (inmediata)")
            _ejecutar_rule_acciones(rule.id, entidad_tipo, entidad_id)
        else:
            _programar_rule(rule, entidad_tipo, entidad_id, entidad_nombre)


def _programar_rule(rule, entidad_tipo, entidad_id, entidad_nombre):
    """Programa la ejecución de la norma con APScheduler para el delay configurado."""
    from app.services.log_service import registrar_marketing_log

    run_at = datetime.utcnow() + timedelta(hours=rule.delay_horas)
    job_id = f"mktg_rule_{rule.id}_{entidad_tipo}_{entidad_id}"

    try:
        from app.scheduler import get_scheduler
        from apscheduler.triggers.date import DateTrigger
        from flask import current_app

        app = current_app._get_current_object()
        sched = get_scheduler()

        def _job(rid=rule.id, et=entidad_tipo, eid=entidad_id, a=app):
            with a.app_context():
                _ejecutar_rule_acciones(rid, et, eid)

        if sched and sched.running:
            sched.add_job(
                func=_job,
                trigger=DateTrigger(run_date=run_at, timezone="UTC"),
                id=job_id,
                replace_existing=True,
                misfire_grace_time=3600,
            )
            detalle = (f"Norma «{rule.nombre}» programada para {run_at.strftime('%d/%m/%Y %H:%M')} UTC "
                       f"(+{rule.delay_label})")
        else:
            detalle = (f"Norma «{rule.nombre}» con delay de {rule.delay_label} — "
                       f"scheduler no disponible, ejecutar manualmente")

    except Exception as e:
        log.error(f"[TriggerEngine] No se pudo programar norma {rule.id}: {e}")
        detalle = f"Norma «{rule.nombre}» delay={rule.delay_label} — error al programar: {str(e)[:200]}"

    registrar_marketing_log(
        "norma_evaluada_ok", "skip",
        rule_id=rule.id, rule_nombre=rule.nombre,
        entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
        detalle=detalle,
        origen="sistema",
    )
    log.info(f"[TriggerEngine] Norma '{rule.nombre}' programada para {run_at}")
