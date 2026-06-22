"""
Servicio de etiquetas con criterio VIP configurable.

Una etiqueta con criterios (criterio_min_gasto / criterio_min_reservas) se asigna
automáticamente cuando el cliente supera los umbrales configurados, calculados sobre
sus reservas no canceladas.

Ambos campos son opcionales; si solo se define uno se comprueba solo ese.
Si se definen los dos, ambos deben cumplirse (AND).

Se llama desde:
  - etiquetas_nueva / etiquetas_editar  → escaneo inmediato tras guardar
  - reservas.nueva / reservas.cambiar_estado → re-evaluar el cliente afectado
  - job diario del scheduler
"""
import logging
from sqlalchemy import func as sqlfunc

log = logging.getLogger(__name__)

ESTADOS_VALIDOS = ("pendiente", "reservado", "disfrutado")


def evaluar_vip_criterio(tag_id=None):
    """
    Escanea todos los tags con criterios activos (o solo el indicado) y
    asigna/retira la etiqueta a cada cliente según corresponda.
    Devuelve dict con estadísticas.
    """
    stats = {"asignadas": 0, "quitadas": 0, "errores": 0}
    try:
        _evaluar_todos(tag_id, stats)
    except Exception as e:
        log.error(f"[VipCriterio] evaluar_vip_criterio error: {e}")
        stats["errores"] += 1
    return stats


def evaluar_cliente_vip(cliente_id):
    """
    Re-evalúa un cliente concreto contra todos los tags con criterio activos.
    Llamado desde rutas de reservas para actualizar el estado VIP al instante.
    """
    try:
        _evaluar_cliente(cliente_id)
    except Exception as e:
        log.error(f"[VipCriterio] evaluar_cliente_vip(#{cliente_id}) error: {e}")


# ── Internos ──────────────────────────────────────────────────────────────────

def _tags_criterio(tag_id=None):
    from app.models.tag import Tag
    q = Tag.query.filter_by(tipo="sistematica", activo=True).filter(
        (Tag.criterio_min_gasto.isnot(None)) | (Tag.criterio_min_reservas.isnot(None))
    )
    if tag_id:
        q = q.filter_by(id=tag_id)
    return q.all()


def _stats_cliente(cliente_id):
    """Devuelve (gasto_total, num_reservas) sobre reservas no canceladas."""
    from app.models.reserva import Reserva
    from app.extensions import db
    row = db.session.query(
        sqlfunc.coalesce(sqlfunc.sum(Reserva.precio), 0.0),
        sqlfunc.count(Reserva.id),
    ).filter(
        Reserva.cliente_id == cliente_id,
        Reserva.estado.in_(ESTADOS_VALIDOS),
    ).first()
    return float(row[0]), int(row[1])


def _cumple_criterio(tag, gasto, num_reservas):
    ok_gasto    = (tag.criterio_min_gasto    is None) or (gasto      >= tag.criterio_min_gasto)
    ok_reservas = (tag.criterio_min_reservas is None) or (num_reservas >= tag.criterio_min_reservas)
    return ok_gasto and ok_reservas


def _tiene_tag(cliente_id, tag_id):
    from app.models.tag import ClienteTag
    return ClienteTag.query.filter_by(cliente_id=cliente_id, tag_id=tag_id).first()


def _asignar(cliente_id, tag, nombre_cliente, gasto, num_reservas):
    from app.models.tag import ClienteTag
    from app.extensions import db
    from app.services.log_service import registrar_marketing_log

    db.session.add(ClienteTag(cliente_id=cliente_id, tag_id=tag.id, origen="sistema"))
    db.session.flush()

    partes = []
    if tag.criterio_min_gasto    is not None: partes.append(f"{gasto:.0f}€ ≥ {tag.criterio_min_gasto:.0f}€")
    if tag.criterio_min_reservas is not None: partes.append(f"{num_reservas} ≥ {tag.criterio_min_reservas} exp.")
    detalle = f"Tag «{tag.nombre}» asignado por criterio VIP: {', '.join(partes)}"

    registrar_marketing_log(
        "tag_asignada", "ok",
        tag_id=tag.id, tag_nombre=tag.nombre,
        entidad="cliente", entidad_id=cliente_id, entidad_nombre=nombre_cliente,
        detalle=detalle, origen="sistema",
    )
    log.info(f"[VipCriterio] VIP asignado a cliente #{cliente_id} ({nombre_cliente})")

    # Disparar normas que requieran este tag
    try:
        from app.services.trigger_engine import _disparar_por_tag_nuevo
        _disparar_por_tag_nuevo(tag.id, "cliente", cliente_id)
    except Exception:
        pass


def _retirar(cliente_id, tag, nombre_cliente, gasto, num_reservas):
    from app.models.tag import ClienteTag
    from app.extensions import db
    from app.services.log_service import registrar_marketing_log

    ct = ClienteTag.query.filter_by(cliente_id=cliente_id, tag_id=tag.id).first()
    if not ct:
        return
    db.session.delete(ct)
    db.session.flush()

    partes = []
    if tag.criterio_min_gasto    is not None: partes.append(f"{gasto:.0f}€ < {tag.criterio_min_gasto:.0f}€ mín.")
    if tag.criterio_min_reservas is not None: partes.append(f"{num_reservas} < {tag.criterio_min_reservas} exp. mín.")
    detalle = f"Tag «{tag.nombre}» retirado por criterio VIP: {', '.join(partes)}"

    registrar_marketing_log(
        "tag_eliminada", "ok",
        tag_id=tag.id, tag_nombre=tag.nombre,
        entidad="cliente", entidad_id=cliente_id, entidad_nombre=nombre_cliente,
        detalle=detalle, origen="sistema",
    )
    log.info(f"[VipCriterio] VIP retirado de cliente #{cliente_id} ({nombre_cliente})")


def _nombre_cliente(cliente_id):
    try:
        from app.models.cliente import Cliente
        c = Cliente.query.get(cliente_id)
        return c.nombre_completo if c else str(cliente_id)
    except Exception:
        return str(cliente_id)


def _evaluar_todos(tag_id, stats):
    from app.models.cliente import Cliente
    from app.extensions import db

    tags = _tags_criterio(tag_id)
    if not tags:
        return

    cliente_ids = [r[0] for r in db.session.query(Cliente.id).all()]

    for tag in tags:
        for cid in cliente_ids:
            try:
                gasto, num_res = _stats_cliente(cid)
                nombre = _nombre_cliente(cid)
                tiene = _tiene_tag(cid, tag.id)
                cumple = _cumple_criterio(tag, gasto, num_res)

                if cumple and not tiene:
                    _asignar(cid, tag, nombre, gasto, num_res)
                    stats["asignadas"] += 1
                elif not cumple and tiene:
                    _retirar(cid, tag, nombre, gasto, num_res)
                    stats["quitadas"] += 1
            except Exception as e:
                log.error(f"[VipCriterio] Error evaluando cliente #{cid} tag {tag.id}: {e}")
                stats["errores"] += 1

        db.session.commit()


def _evaluar_cliente(cliente_id):
    from app.extensions import db

    tags = _tags_criterio()
    if not tags:
        return

    gasto, num_res = _stats_cliente(cliente_id)
    nombre = _nombre_cliente(cliente_id)

    for tag in tags:
        tiene  = _tiene_tag(cliente_id, tag.id)
        cumple = _cumple_criterio(tag, gasto, num_res)
        if cumple and not tiene:
            _asignar(cliente_id, tag, nombre, gasto, num_res)
        elif not cumple and tiene:
            _retirar(cliente_id, tag, nombre, gasto, num_res)

    db.session.commit()
