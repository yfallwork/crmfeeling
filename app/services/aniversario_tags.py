"""
Servicio de etiquetas de mes aniversario.

Asigna la etiqueta cuando el mes actual coincide con el mes de creación
del cliente/empresa (su "aniversario" con nosotros).
Se retira automáticamente en cuanto cambia el mes.

Se llama desde:
  - job diario del scheduler (07:30)
"""
import logging
from datetime import date

log = logging.getLogger(__name__)

SLUG_CLIENTE = "mes_aniversario_cliente"
SLUG_EMPRESA = "mes_aniversario_empresa"


def evaluar_aniversarios():
    """Evalúa y sincroniza las etiquetas de aniversario para clientes y empresas."""
    stats = {"asignadas": 0, "quitadas": 0, "errores": 0}
    mes_actual = date.today().month
    _evaluar_entidad("cliente", SLUG_CLIENTE, mes_actual, stats)
    _evaluar_entidad("empresa", SLUG_EMPRESA, mes_actual, stats)
    return stats


# ── Internos ──────────────────────────────────────────────────────────────────

def _evaluar_entidad(tipo, slug, mes_actual, stats):
    from app.extensions import db
    from app.models.tag import Tag, ClienteTag, EmpresaTag

    tag = Tag.query.filter_by(slug=slug, activo=True).first()
    if not tag:
        return

    if tipo == "cliente":
        from app.models.cliente import Cliente
        entidades = Cliente.query.all()
        TagModel  = ClienteTag
        fk_kwarg  = "cliente_id"
    else:
        from app.models.empresa import Empresa
        entidades = Empresa.query.filter_by(activo=True).all()
        TagModel  = EmpresaTag
        fk_kwarg  = "empresa_id"

    for entidad in entidades:
        try:
            eid = entidad.id
            if not entidad.creado_en:
                continue

            cumple = entidad.creado_en.month == mes_actual
            tiene  = TagModel.query.filter_by(**{fk_kwarg: eid}, tag_id=tag.id).first()

            if cumple and not tiene:
                db.session.add(TagModel(**{fk_kwarg: eid}, tag_id=tag.id, origen="sistema"))
                db.session.flush()
                _registrar(tag, tipo, eid, entidad, "asignada")
                stats["asignadas"] += 1
                try:
                    from app.services.trigger_engine import _disparar_por_tag_nuevo
                    _disparar_por_tag_nuevo(tag.id, tipo, eid)
                except Exception:
                    pass

            elif not cumple and tiene:
                db.session.delete(tiene)
                db.session.flush()
                _registrar(tag, tipo, eid, entidad, "quitada")
                stats["quitadas"] += 1

        except Exception as e:
            log.error(f"[Aniversario] Error {tipo} #{entidad.id}: {e}")
            stats["errores"] += 1

    db.session.commit()


def _registrar(tag, tipo, eid, entidad, accion):
    from app.services.log_service import registrar_marketing_log
    try:
        nombre = (
            getattr(entidad, "nombre_completo", None)
            or getattr(entidad, "nombre", str(eid))
        )
        mes_str = entidad.creado_en.strftime("%B") if entidad.creado_en else "?"
        registrar_marketing_log(
            "tag_asignada" if accion == "asignada" else "tag_eliminada", "ok",
            tag_id=tag.id, tag_nombre=tag.nombre,
            entidad=tipo, entidad_id=eid, entidad_nombre=nombre,
            detalle=f"Tag «{tag.nombre}» {accion} — mes de alta: {mes_str}",
            origen="sistema",
        )
    except Exception:
        pass
