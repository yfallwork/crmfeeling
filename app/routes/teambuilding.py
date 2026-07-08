import os
import uuid
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, jsonify)
from flask_login import login_required
from app.extensions import db
from app.models.empresa import Empresa
from app.models.empresa_nota import EmpresaNota
from app.models.reserva import Reserva
from app.models.tag import Tag, EmpresaTag
from app.services.log_service import registrar_log, registrar_marketing_log
from app.routes.autoclub import SECTORES_ESPAÑA

teambuilding_bp = Blueprint("teambuilding", __name__)

LOGO_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp", "svg"}


# ── CONTEXT PROCESSOR ──────────────────────────────────────────────────────────

@teambuilding_bp.context_processor
def inject_ctx():
    return {"sectores_espana": SECTORES_ESPAÑA}


# ── HELPERS UPLOAD ─────────────────────────────────────────────────────────────

def _logo_dir():
    path = os.path.join(current_app.root_path, "static", "uploads", "teambuilding", "empresas")
    os.makedirs(path, exist_ok=True)
    return path


def _save_logo(file, old_filename=None):
    if not file or not file.filename:
        return None
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in LOGO_EXTENSIONS:
        return None
    filename = f"{uuid.uuid4().hex}.{ext}"
    file.save(os.path.join(_logo_dir(), filename))
    if old_filename:
        _delete_logo(old_filename)
    return filename


def _delete_logo(filename):
    if not filename:
        return
    try:
        os.remove(os.path.join(_logo_dir(), filename))
    except OSError:
        pass


def _extract_logos(empresa=None):
    """Procesa los 3 logos del formulario. Devuelve dict con los campos que cambian."""
    changes = {}
    for attr, field in [
        ("logo_positivo_filename", "logo_positivo"),
        ("logo_negativo_filename", "logo_negativo"),
        ("logo_banner_filename",   "logo_banner"),
    ]:
        file = request.files.get(field)
        new_fn = _save_logo(file, old_filename=getattr(empresa, attr) if empresa else None)
        if new_fn:
            changes[attr] = new_fn
        elif empresa and request.form.get(f"eliminar_{field}") == "1":
            _delete_logo(getattr(empresa, attr))
            changes[attr] = ""
    return changes


# ── DASHBOARD TEAM BUILDING ───────────────────────────────────────────────────

@teambuilding_bp.route("/")
@login_required
def index():
    return redirect(url_for("teambuilding.empresas_lista"))


# ══════════════════════════════════════════════════════════════════════════════
#  EMPRESAS
# ══════════════════════════════════════════════════════════════════════════════

@teambuilding_bp.route("/empresas/")
@login_required
def empresas_lista():
    q      = request.args.get("q", "").strip()
    estado = request.args.get("estado", "activas")
    page   = request.args.get("page", 1, type=int)

    query = Empresa.query
    if estado == "activas":
        query = query.filter_by(activo=True)
    elif estado == "inactivas":
        query = query.filter_by(activo=False)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Empresa.nombre.ilike(like),
            Empresa.sector.ilike(like),
            Empresa.persona_contacto.ilike(like),
            Empresa.email.ilike(like),
        ))

    empresas = query.order_by(Empresa.nombre.asc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("teambuilding/empresas/lista.html",
                           empresas=empresas, q=q, estado=estado)


@teambuilding_bp.route("/empresas/nueva", methods=["GET", "POST"])
@login_required
def empresas_nueva():
    if request.method == "POST":
        logos = _extract_logos()
        num_emp_raw = request.form.get("num_empleados", "").strip()
        e = Empresa(
            nombre           = request.form.get("nombre", "").strip(),
            sector           = request.form.get("sector", "").strip(),
            persona_contacto = request.form.get("persona_contacto", "").strip(),
            email            = request.form.get("email", "").strip().lower(),
            telefono         = request.form.get("telefono", "").strip(),
            web              = request.form.get("web", "").strip(),
            instagram        = request.form.get("instagram", "").strip(),
            facebook         = request.form.get("facebook", "").strip(),
            twitter          = request.form.get("twitter", "").strip(),
            linkedin         = request.form.get("linkedin", "").strip(),
            tiktok           = request.form.get("tiktok", "").strip(),
            youtube          = request.form.get("youtube", "").strip(),
            logo_positivo_filename = logos.get("logo_positivo_filename", ""),
            logo_negativo_filename = logos.get("logo_negativo_filename", ""),
            logo_banner_filename   = logos.get("logo_banner_filename", ""),
            notas         = request.form.get("notas", "").strip(),
            num_empleados = int(num_emp_raw) if num_emp_raw.isdigit() else None,
        )
        db.session.add(e)
        db.session.commit()
        registrar_log("crear", "empresa", e.id, f"Empresa TB creada: {e.nombre}")
        flash(f"Empresa {e.nombre} creada correctamente.", "success")
        from app.services.trigger_engine import disparar_trigger
        disparar_trigger("crm.empresa.creada", "empresa", e.id)
        try:
            from app.services.gran_cuenta_criterio import evaluar_empresa_gran_cuenta
            evaluar_empresa_gran_cuenta(e.id)
        except Exception:
            pass
        return redirect(url_for("teambuilding.empresas_detalle", id=e.id))

    return render_template("teambuilding/empresas/form.html", e=None, datos={})


@teambuilding_bp.route("/empresas/<int:id>")
@login_required
def empresas_detalle(id):
    e = Empresa.query.get_or_404(id)
    empresa_tags = EmpresaTag.query.filter_by(empresa_id=id).all()
    tag_ids_asignados = {et.tag_id for et in empresa_tags}
    tags_disponibles = (Tag.query
                        .filter_by(entidad="empresa", activo=True)
                        .filter(Tag.id.notin_(tag_ids_asignados))
                        .order_by(Tag.nombre).all())
    return render_template("teambuilding/empresas/detalle.html", e=e,
                           empresa_tags=empresa_tags,
                           tags_disponibles=tags_disponibles)


@teambuilding_bp.route("/empresas/<int:id>/tags/add", methods=["POST"])
@login_required
def empresas_tag_add(id):
    Empresa.query.get_or_404(id)
    tag_id = request.form.get("tag_id", type=int)
    e = Empresa.query.get_or_404(id)
    if tag_id and not EmpresaTag.query.filter_by(empresa_id=id, tag_id=tag_id).first():
        db.session.add(EmpresaTag(empresa_id=id, tag_id=tag_id, origen="manual"))
        db.session.commit()
        tag = Tag.query.get(tag_id)
        tag_slug = tag.slug if tag else str(tag_id)
        registrar_log("editar", "empresa", id, f"Etiqueta añadida: {tag_slug}")
        registrar_marketing_log(
            "tag_asignada", resultado="ok",
            tag_id=tag_id, tag_nombre=tag.nombre if tag else tag_slug,
            entidad="empresa", entidad_id=id,
            entidad_nombre=e.nombre,
            detalle=f"Etiqueta '{tag.nombre if tag else tag_slug}' asignada manualmente",
            origen="manual",
        )
    return redirect(url_for("teambuilding.empresas_detalle", id=id))


@teambuilding_bp.route("/empresas/<int:id>/tags/remove", methods=["POST"])
@login_required
def empresas_tag_remove(id):
    e = Empresa.query.get_or_404(id)
    tag_id = request.form.get("tag_id", type=int)
    if tag_id:
        et = EmpresaTag.query.filter_by(empresa_id=id, tag_id=tag_id).first()
        if et:
            tag = Tag.query.get(tag_id)
            tag_slug = tag.slug if tag else str(tag_id)
            db.session.delete(et)
            db.session.commit()
            registrar_log("editar", "empresa", id, f"Etiqueta eliminada: {tag_slug}")
            registrar_marketing_log(
                "tag_eliminada", resultado="ok",
                tag_id=tag_id, tag_nombre=tag.nombre if tag else tag_slug,
                entidad="empresa", entidad_id=id,
                entidad_nombre=e.nombre,
                detalle=f"Etiqueta '{tag.nombre if tag else tag_slug}' eliminada manualmente",
                origen="manual",
            )
    return redirect(url_for("teambuilding.empresas_detalle", id=id))


@teambuilding_bp.route("/empresas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def empresas_editar(id):
    e = Empresa.query.get_or_404(id)
    if request.method == "POST":
        logos = _extract_logos(e)
        for attr, val in logos.items():
            setattr(e, attr, val)

        num_emp_raw = request.form.get("num_empleados", "").strip()
        e.nombre           = request.form.get("nombre", "").strip()
        e.sector           = request.form.get("sector", "").strip()
        e.persona_contacto = request.form.get("persona_contacto", "").strip()
        e.email            = request.form.get("email", "").strip().lower()
        e.telefono         = request.form.get("telefono", "").strip()
        e.web              = request.form.get("web", "").strip()
        e.instagram        = request.form.get("instagram", "").strip()
        e.facebook         = request.form.get("facebook", "").strip()
        e.twitter          = request.form.get("twitter", "").strip()
        e.linkedin         = request.form.get("linkedin", "").strip()
        e.tiktok           = request.form.get("tiktok", "").strip()
        e.youtube          = request.form.get("youtube", "").strip()
        e.notas            = request.form.get("notas", "").strip()
        e.num_empleados    = int(num_emp_raw) if num_emp_raw.isdigit() else None
        db.session.commit()
        registrar_log("editar", "empresa", e.id, f"Empresa TB editada: {e.nombre}")
        flash("Empresa actualizada correctamente.", "success")
        try:
            from app.services.gran_cuenta_criterio import evaluar_empresa_gran_cuenta
            evaluar_empresa_gran_cuenta(e.id)
        except Exception:
            pass
        return redirect(url_for("teambuilding.empresas_detalle", id=e.id))

    return render_template("teambuilding/empresas/form.html", e=e, datos={})


@teambuilding_bp.route("/empresas/<int:id>/estado", methods=["POST"])
@login_required
def empresas_estado(id):
    e = Empresa.query.get_or_404(id)
    if e.activo:
        e.activo = False
        registrar_log("cambiar_estado", "empresa", e.id, f"Empresa TB desactivada: {e.nombre}")
        flash(f"{e.nombre} marcada como inactiva.", "warning")
    else:
        e.activo = True
        registrar_log("cambiar_estado", "empresa", e.id, f"Empresa TB reactivada: {e.nombre}")
        flash(f"{e.nombre} reactivada correctamente.", "success")
    db.session.commit()
    return redirect(url_for("teambuilding.empresas_detalle", id=e.id))


@teambuilding_bp.route("/empresas/<int:id>/eliminar", methods=["POST"])
@login_required
def empresas_eliminar(id):
    e = Empresa.query.get_or_404(id)
    nombre = e.nombre
    for fn in [e.logo_positivo_filename, e.logo_negativo_filename, e.logo_banner_filename]:
        _delete_logo(fn)
    # Sin esto, las reservas de esta empresa quedarían huérfanas (empresa_id
    # apuntando a una fila ya borrada) y romperían dashboard/listados al
    # intentar acceder a reserva.empresa. Se borran una a una (no con un bulk
    # delete) para que la cascada ORM también elimine sus comunicaciones_log.
    reservas_empresa = Reserva.query.filter_by(empresa_id=id).all()
    n_reservas = len(reservas_empresa)
    for r in reservas_empresa:
        db.session.delete(r)
    db.session.delete(e)
    db.session.commit()
    registrar_log("eliminar", "empresa", id,
                  f"Empresa TB eliminada: {nombre} (junto con {n_reservas} reserva(s) asociada(s))")
    flash(f"Empresa {nombre} eliminada"
          f"{f', junto con {n_reservas} reserva(s) asociada(s)' if n_reservas else ''}.", "info")
    return redirect(url_for("teambuilding.empresas_lista"))


# ── NOTAS DE EMPRESA ──────────────────────────────────────────────────────────

@teambuilding_bp.route("/notas")
@login_required
def notas_lista():
    q    = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = EmpresaNota.query.join(Empresa)
    if q:
        query = query.filter(
            db.or_(
                Empresa.nombre.ilike(f"%{q}%"),
                EmpresaNota.contenido.ilike(f"%{q}%"),
            )
        )
    notas = query.order_by(EmpresaNota.creado_en.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    total = EmpresaNota.query.count()
    return render_template("teambuilding/notas/lista.html",
                           notas=notas, q=q, total=total)


@teambuilding_bp.route("/empresas/<int:id>/notas/nueva", methods=["POST"])
@login_required
def empresas_nota_nueva(id):
    from flask_login import current_user
    e         = Empresa.query.get_or_404(id)
    contenido = request.form.get("contenido", "").strip()
    if not contenido:
        flash("La nota no puede estar vacía.", "warning")
    else:
        nota = EmpresaNota(
            empresa_id     = e.id,
            contenido      = contenido,
            usuario_nombre = current_user.nombre if hasattr(current_user, "nombre") else "Usuario",
        )
        db.session.add(nota)
        db.session.commit()
        flash("Nota añadida correctamente.", "success")
    return_to = request.form.get("return_to", "detalle")
    if return_to == "lista":
        return redirect(url_for("teambuilding.empresas_lista"))
    return redirect(url_for("teambuilding.empresas_detalle", id=id) + "#notas")


@teambuilding_bp.route("/empresas/<int:id>/notas/<int:nid>/eliminar", methods=["POST"])
@login_required
def empresas_nota_eliminar(id, nid):
    nota = EmpresaNota.query.filter_by(id=nid, empresa_id=id).first_or_404()
    db.session.delete(nota)
    db.session.commit()
    flash("Nota eliminada.", "info")
    return_to = request.form.get("return_to", "detalle")
    if return_to == "lista":
        return redirect(url_for("teambuilding.notas_lista"))
    return redirect(url_for("teambuilding.empresas_detalle", id=id) + "#notas")
