"""
Servicio de etiquetas temporales.

Una etiqueta temporal se asigna cuando la entidad lleva más de
`tag.tiempo_sin_reserva_dias` días sin una reserva no-cancelada,
contando desde la última reserva activa o, si nunca reservó, desde
su fecha de creación.

Se llama desde:
  - etiquetas_nueva / etiquetas_editar (escaneo inmediato al guardar)
  - job diario del scheduler (_job_temporal_tags)
  - reservas.nueva / reservas.cambiar_estado (para quitar etiquetas al volver a reservar)
"""
import logging
from datetime import datetime, timedelta

log = logging.getLogger(__name__)

ESTADOS_ACTIVOS = ("pendiente", "reservado", "disfrutado")


def evaluar_tags_temporales(tag_id=None):
    """
    Escanea todas las etiquetas temporales activas (o solo la indicada)
    y asigna / quita la etiqueta según corresponda.

    Devuelve dict con estadísticas: asignadas, quitadas, errores.
    """
    stats = {"asignadas": 0, "quitadas": 0, "errores": 0}
    try:
        _evaluar(tag_id, stats)
    except Exception as e:
        log.error(f"[TemporalTags] evaluar_tags_temporales error: {e}")
        stats["errores"] += 1
    return stats


def quitar_tags_temporales_por_reserva(entidad_tipo, entidad_id):
    """
    Elimina las etiquetas temporales de una entidad porque acaba de
    hacer una reserva activa (ya no es inactivo).
    Solo quita etiquetas que ya no apliquen dada la nueva reserva.
    """
    try:
        _quitar_por_reserva(entidad_tipo, entidad_id)
    except Exception as e:
        log.error(f"[TemporalTags] quitar_tags_temporales_por_reserva error: {e}")


# ── Internos ──────────────────────────────────────────────────────────────────

def _ultima_reserva_activa(entidad_tipo, entidad_id):
    """Fecha de la última reserva con estado no-cancelado. None si nunca reservó."""
    from app.models.reserva import Reserva
    q = Reserva.query.filter(Reserva.estado.in_(ESTADOS_ACTIVOS))
    if entidad_tipo == "cliente":
        q = q.filter_by(cliente_id=entidad_id)
    else:
        q = q.filter_by(empresa_id=entidad_id)
    reserva = q.order_by(Reserva.fecha_compra.desc()).first()
    return reserva.fecha_compra if reserva else None


def _fecha_referencia(entidad_tipo, entidad_id):
    """
    Devuelve la fecha base para calcular inactividad:
    - Si tiene reservas activas: fecha de la última
    - Si nunca reservó: fecha de creación de la entidad
    """
    from app.models.cliente import Cliente
    from app.models.empresa import Empresa

    ultima = _ultima_reserva_activa(entidad_tipo, entidad_id)
    if ultima:
        return ultima

    if entidad_tipo == "cliente":
        e = Cliente.query.get(entidad_id)
    else:
        e = Empresa.query.get(entidad_id)
    return e.creado_en if e and e.creado_en else datetime.utcnow()


def _get_entity_ids(entidad_tipo):
    from app.models.cliente import Cliente
    from app.models.empresa import Empresa
    if entidad_tipo == "cliente":
        return [c.id for c in Cliente.query.with_entities(Cliente.id).all()]
    else:
        return [e.id for e in Empresa.query.with_entities(Empresa.id).filter_by(activo=True).all()]


def _tiene_tag(entidad_tipo, entidad_id, tag_id):
    from app.models.tag import ClienteTag, EmpresaTag
    if entidad_tipo == "cliente":
        return ClienteTag.query.filter_by(cliente_id=entidad_id, tag_id=tag_id).first()
    return EmpresaTag.query.filter_by(empresa_id=entidad_id, tag_id=tag_id).first()


def _asignar_tag(entidad_tipo, entidad_id, tag_id, entidad_nombre, tag):
    from app.models.tag import ClienteTag, EmpresaTag
    from app.extensions import db
    from app.services.log_service import registrar_marketing_log

    if entidad_tipo == "cliente":
        db.session.add(ClienteTag(cliente_id=entidad_id, tag_id=tag_id, origen="sistema"))
    else:
        db.session.add(EmpresaTag(empresa_id=entidad_id, tag_id=tag_id, origen="sistema"))
    db.session.flush()

    registrar_marketing_log(
        "tag_asignada", "ok",
        tag_id=tag_id, tag_nombre=tag.nombre,
        entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
        detalle=f"Tag temporal «{tag.nombre}» asignado (+{tag.tiempo_sin_reserva_dias}d sin reservar)",
        origen="sistema",
    )
    log.info(f"[TemporalTags] Asignado «{tag.nombre}» → {entidad_tipo} #{entidad_id}")


def _quitar_tag(entidad_tipo, entidad_id, tag_id, entidad_nombre, tag):
    from app.models.tag import ClienteTag, EmpresaTag
    from app.extensions import db
    from app.services.log_service import registrar_marketing_log

    if entidad_tipo == "cliente":
        ct = ClienteTag.query.filter_by(cliente_id=entidad_id, tag_id=tag_id).first()
    else:
        ct = EmpresaTag.query.filter_by(empresa_id=entidad_id, tag_id=tag_id).first()

    if ct:
        db.session.delete(ct)
        db.session.flush()
        registrar_marketing_log(
            "tag_eliminada", "ok",
            tag_id=tag_id, tag_nombre=tag.nombre,
            entidad=entidad_tipo, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
            detalle=f"Tag temporal «{tag.nombre}» retirado (nueva reserva activa detectada)",
            origen="sistema",
        )
        log.info(f"[TemporalTags] Retirado «{tag.nombre}» → {entidad_tipo} #{entidad_id}")


def _nombre_entidad(entidad_tipo, entidad_id):
    try:
        if entidad_tipo == "cliente":
            from app.models.cliente import Cliente
            c = Cliente.query.get(entidad_id)
            return c.nombre_completo if c else str(entidad_id)
        else:
            from app.models.empresa import Empresa
            e = Empresa.query.get(entidad_id)
            return e.nombre if e else str(entidad_id)
    except Exception:
        return str(entidad_id)


def _evaluar(tag_id, stats):
    from app.models.tag import Tag
    from app.extensions import db

    query = Tag.query.filter_by(tipo="temporal", activo=True)
    if tag_id:
        query = query.filter_by(id=tag_id)
    tags = query.all()

    if not tags:
        return

    ahora = datetime.utcnow()

    for tag in tags:
        if not tag.tiempo_sin_reserva_dias:
            continue

        umbral_dias = tag.tiempo_sin_reserva_dias
        entidad_tipo = tag.entidad
        entity_ids = _get_entity_ids(entidad_tipo)

        for eid in entity_ids:
            try:
                fecha_ref = _fecha_referencia(entidad_tipo, eid)
                dias_inactivo = (ahora - fecha_ref).days
                nombre = _nombre_entidad(entidad_tipo, eid)
                tiene = _tiene_tag(entidad_tipo, eid, tag.id)

                if dias_inactivo >= umbral_dias:
                    if not tiene:
                        _asignar_tag(entidad_tipo, eid, tag.id, nombre, tag)
                        stats["asignadas"] += 1
                        # Disparar normas que requieran este tag
                        try:
                            from app.services.trigger_engine import _disparar_por_tag_nuevo
                            _disparar_por_tag_nuevo(tag.id, entidad_tipo, eid)
                        except Exception:
                            pass
                else:
                    if tiene:
                        _quitar_tag(entidad_tipo, eid, tag.id, nombre, tag)
                        stats["quitadas"] += 1

            except Exception as e:
                log.error(f"[TemporalTags] Error evaluando {entidad_tipo} #{eid} con tag {tag.id}: {e}")
                stats["errores"] += 1

        db.session.commit()


def _quitar_por_reserva(entidad_tipo, entidad_id):
    """Llamado tras nueva reserva activa: retira tags temporales que ya no apliquen."""
    from app.models.tag import Tag
    from app.extensions import db

    tags_temporales = Tag.query.filter_by(tipo="temporal", activo=True, entidad=entidad_tipo).all()
    if not tags_temporales:
        return

    ahora = datetime.utcnow()
    nombre = _nombre_entidad(entidad_tipo, entidad_id)

    for tag in tags_temporales:
        if not tag.tiempo_sin_reserva_dias:
            continue
        fecha_ref = _fecha_referencia(entidad_tipo, entidad_id)
        dias_inactivo = (ahora - fecha_ref).days
        if dias_inactivo < tag.tiempo_sin_reserva_dias:
            _quitar_tag(entidad_tipo, entidad_id, tag.id, nombre, tag)

    db.session.commit()
