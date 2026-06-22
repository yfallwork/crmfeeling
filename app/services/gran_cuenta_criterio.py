"""
Servicio de etiqueta Gran Cuenta B2B con criterio configurable.

Se asigna automáticamente cuando la empresa supera los umbrales configurados:
  - criterio_min_empleados: número mínimo de empleados
  - criterio_min_gasto: gasto acumulado mínimo en eventos TB (reservas no canceladas)

Ambos criterios son opcionales; si se definen los dos, ambos deben cumplirse (AND).
Se retira si deja de cumplirlos.

Se llama desde:
  - etiquetas_nueva / etiquetas_editar → escaneo inmediato tras guardar
  - teambuilding.empresas_nueva / empresas_editar → re-evaluar empresa afectada
  - reservas.cambiar_estado → re-evaluar empresa tras cambios de gasto
  - job diario del scheduler
"""
import logging
from sqlalchemy import func as sqlfunc

log = logging.getLogger(__name__)

ESTADOS_VALIDOS = ("pendiente", "reservado", "disfrutado")
SLUG = "gran_cuenta_b2b"


def evaluar_gran_cuenta(tag_id=None):
    """
    Escanea todas las empresas contra los tags Gran Cuenta activos.
    Devuelve dict con estadísticas.
    """
    stats = {"asignadas": 0, "quitadas": 0, "errores": 0}
    try:
        _evaluar_todos(tag_id, stats)
    except Exception as e:
        log.error(f"[GranCuenta] evaluar_gran_cuenta error: {e}")
        stats["errores"] += 1
    return stats


def evaluar_empresa_gran_cuenta(empresa_id):
    """
    Re-evalúa una empresa concreta. Llamado desde rutas de teambuilding y reservas.
    """
    try:
        _evaluar_empresa(empresa_id)
    except Exception as e:
        log.error(f"[GranCuenta] evaluar_empresa_gran_cuenta(#{empresa_id}) error: {e}")


# ── Internos ──────────────────────────────────────────────────────────────────

def _tags_criterio(tag_id=None):
    from app.models.tag import Tag
    q = Tag.query.filter_by(tipo="sistematica", activo=True).filter(
        (Tag.criterio_min_empleados.isnot(None)) | (Tag.criterio_min_gasto.isnot(None))
    ).filter_by(entidad="empresa")
    if tag_id:
        q = q.filter_by(id=tag_id)
    return q.all()


def _stats_empresa(empresa_id):
    """Devuelve (gasto_total, num_empleados) para una empresa."""
    from app.models.reserva import Reserva
    from app.models.empresa import Empresa
    from app.extensions import db

    row = db.session.query(
        sqlfunc.coalesce(sqlfunc.sum(Reserva.precio), 0.0),
    ).filter(
        Reserva.empresa_id == empresa_id,
        Reserva.estado.in_(ESTADOS_VALIDOS),
    ).first()
    gasto = float(row[0])

    empresa = Empresa.query.get(empresa_id)
    empleados = empresa.num_empleados or 0 if empresa else 0
    return gasto, empleados


def _cumple_criterio(tag, gasto, empleados):
    ok_gasto    = (tag.criterio_min_gasto     is None) or (gasto    >= tag.criterio_min_gasto)
    ok_empleados = (tag.criterio_min_empleados is None) or (empleados >= tag.criterio_min_empleados)
    return ok_gasto and ok_empleados


def _tiene_tag(empresa_id, tag_id):
    from app.models.tag import EmpresaTag
    return EmpresaTag.query.filter_by(empresa_id=empresa_id, tag_id=tag_id).first()


def _nombre_empresa(empresa_id):
    try:
        from app.models.empresa import Empresa
        e = Empresa.query.get(empresa_id)
        return e.nombre if e else str(empresa_id)
    except Exception:
        return str(empresa_id)


def _asignar(empresa_id, tag, nombre, gasto, empleados):
    from app.models.tag import EmpresaTag
    from app.extensions import db
    from app.services.log_service import registrar_marketing_log

    db.session.add(EmpresaTag(empresa_id=empresa_id, tag_id=tag.id, origen="sistema"))
    db.session.flush()

    partes = []
    if tag.criterio_min_gasto     is not None: partes.append(f"{gasto:.0f}€ ≥ {tag.criterio_min_gasto:.0f}€")
    if tag.criterio_min_empleados is not None: partes.append(f"{empleados} ≥ {tag.criterio_min_empleados} empleados")

    registrar_marketing_log(
        "tag_asignada", "ok",
        tag_id=tag.id, tag_nombre=tag.nombre,
        entidad="empresa", entidad_id=empresa_id, entidad_nombre=nombre,
        detalle=f"Tag «{tag.nombre}» asignado por criterio Gran Cuenta: {', '.join(partes)}",
        origen="sistema",
    )
    log.info(f"[GranCuenta] Gran Cuenta asignada a empresa #{empresa_id} ({nombre})")

    try:
        from app.services.trigger_engine import _disparar_por_tag_nuevo
        _disparar_por_tag_nuevo(tag.id, "empresa", empresa_id)
    except Exception:
        pass


def _retirar(empresa_id, tag, nombre, gasto, empleados):
    from app.models.tag import EmpresaTag
    from app.extensions import db
    from app.services.log_service import registrar_marketing_log

    et = EmpresaTag.query.filter_by(empresa_id=empresa_id, tag_id=tag.id).first()
    if not et:
        return
    db.session.delete(et)
    db.session.flush()

    partes = []
    if tag.criterio_min_gasto     is not None: partes.append(f"{gasto:.0f}€ < {tag.criterio_min_gasto:.0f}€ mín.")
    if tag.criterio_min_empleados is not None: partes.append(f"{empleados} < {tag.criterio_min_empleados} empleados mín.")

    registrar_marketing_log(
        "tag_eliminada", "ok",
        tag_id=tag.id, tag_nombre=tag.nombre,
        entidad="empresa", entidad_id=empresa_id, entidad_nombre=nombre,
        detalle=f"Tag «{tag.nombre}» retirado por criterio Gran Cuenta: {', '.join(partes)}",
        origen="sistema",
    )
    log.info(f"[GranCuenta] Gran Cuenta retirada de empresa #{empresa_id} ({nombre})")


def _evaluar_todos(tag_id, stats):
    from app.models.empresa import Empresa
    from app.extensions import db

    tags = _tags_criterio(tag_id)
    if not tags:
        return

    empresa_ids = [r[0] for r in db.session.query(Empresa.id).all()]

    for tag in tags:
        for eid in empresa_ids:
            try:
                gasto, empleados = _stats_empresa(eid)
                nombre = _nombre_empresa(eid)
                tiene  = _tiene_tag(eid, tag.id)
                cumple = _cumple_criterio(tag, gasto, empleados)

                if cumple and not tiene:
                    _asignar(eid, tag, nombre, gasto, empleados)
                    stats["asignadas"] += 1
                elif not cumple and tiene:
                    _retirar(eid, tag, nombre, gasto, empleados)
                    stats["quitadas"] += 1
            except Exception as e:
                log.error(f"[GranCuenta] Error evaluando empresa #{eid} tag {tag.id}: {e}")
                stats["errores"] += 1

        db.session.commit()


def _evaluar_empresa(empresa_id):
    from app.extensions import db

    tags = _tags_criterio()
    if not tags:
        return

    gasto, empleados = _stats_empresa(empresa_id)
    nombre = _nombre_empresa(empresa_id)

    for tag in tags:
        tiene  = _tiene_tag(empresa_id, tag.id)
        cumple = _cumple_criterio(tag, gasto, empleados)
        if cumple and not tiene:
            _asignar(empresa_id, tag, nombre, gasto, empleados)
        elif not cumple and tiene:
            _retirar(empresa_id, tag, nombre, gasto, empleados)

    db.session.commit()
