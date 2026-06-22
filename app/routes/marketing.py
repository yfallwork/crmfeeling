from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.extensions import db
from app.models.tag import Tag, ClienteTag, EmpresaTag
from app.models.rule import PlantillaEmail, Rule, RuleTag, RuleAccion, Notificacion
from app.models.campana import Campana, CampanaTag, CampanaLog, PlantillaWA
from app.services.log_service import registrar_log, registrar_marketing_log

marketing_bp = Blueprint("marketing", __name__)

# Etiquetas sistemáticas con lógica de backend — no se pueden borrar desde la UI
SLUGS_PROTEGIDOS = frozenset({
    # B2C — todas las sistemáticas tienen trigger programado
    "lead_particular_nuevo",
    "carrito_abandonado",
    "experiencia_reservada",
    "experiencia_realizada",
    "compro_para_regalo",
    # B2B — todas menos descargo_dossier (pendiente de decidir)
    "lead_empresa_nuevo",
    "identificado_como_empresa",
    "evento_empresa_realizado",
    # Criterio VIP — protegida pero con criterios editables
    "cliente_vip_particular",
    # Aniversario — evaluación automática diaria
    "mes_aniversario_cliente",
    "mes_aniversario_empresa",
    # Gran Cuenta B2B — criterios configurables de empleados y gasto
    "gran_cuenta_b2b",
})

ICONOS_DISPONIBLES = [
    "bi-tag-fill", "bi-tags-fill", "bi-person-plus-fill", "bi-person-badge-fill",
    "bi-star-fill", "bi-lightning-fill", "bi-bell-fill", "bi-heart-fill",
    "bi-trophy-fill", "bi-calendar-check-fill", "bi-buildings-fill", "bi-briefcase-fill",
    "bi-gift-fill", "bi-cart-check-fill", "bi-clock-fill", "bi-moon-fill",
    "bi-sun-fill", "bi-flag-fill", "bi-award-fill", "bi-bookmark-fill",
    "bi-envelope-fill", "bi-telephone-fill", "bi-chat-dots-fill", "bi-send-fill",
    "bi-eye-fill", "bi-hand-thumbs-up-fill", "bi-currency-euro", "bi-graph-up-arrow",
    "bi-shield-check", "bi-fire", "bi-gem", "bi-rocket-takeoff-fill",
]

DELAY_OPCIONES = [
    (0,   "Inmediato"),
    (1,   "1 hora"),
    (6,   "6 horas"),
    (12,  "12 horas"),
    (24,  "1 día (24h)"),
    (48,  "2 días (48h)"),
    (72,  "3 días (72h)"),
    (168, "1 semana (168h)"),
]


@marketing_bp.context_processor
def inject_notif_count():
    try:
        count = Notificacion.query.filter_by(resuelta=False).count()
    except Exception:
        count = 0
    return {"notif_pendientes": count}


# ─────────────────────────────────────────────────────────────────────────────
#  Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@marketing_bp.route("/")
@login_required
def index():
    stats = {
        "total":         Tag.query.filter_by(activo=True).count(),
        "sistematicas":  Tag.query.filter_by(tipo="sistematica", activo=True).count(),
        "dinamicas":     Tag.query.filter_by(tipo="dinamica",    activo=True).count(),
        "temporales":    Tag.query.filter_by(tipo="temporal",    activo=True).count(),
        "b2c":           Tag.query.filter_by(segmento="b2c",     activo=True).count(),
        "b2b":           Tag.query.filter_by(segmento="b2b",     activo=True).count(),
        "asig_clientes": ClienteTag.query.count(),
        "asig_empresas": EmpresaTag.query.count(),
        "plantillas":    PlantillaEmail.query.filter_by(activo=True).count(),
        "normas":        Rule.query.filter_by(activo=True).count(),
        "notificaciones": Notificacion.query.filter_by(resuelta=False).count(),
    }
    tags_b2c_sis = Tag.query.filter_by(segmento="b2c", tipo="sistematica", activo=True).order_by(Tag.nombre).all()
    tags_b2c_din = Tag.query.filter_by(segmento="b2c", tipo="dinamica",    activo=True).order_by(Tag.nombre).all()
    tags_b2c_tmp = Tag.query.filter_by(segmento="b2c", tipo="temporal",    activo=True).order_by(Tag.nombre).all()
    tags_b2b_sis = Tag.query.filter_by(segmento="b2b", tipo="sistematica", activo=True).order_by(Tag.nombre).all()
    tags_b2b_din = Tag.query.filter_by(segmento="b2b", tipo="dinamica",    activo=True).order_by(Tag.nombre).all()
    tags_b2b_tmp = Tag.query.filter_by(segmento="b2b", tipo="temporal",    activo=True).order_by(Tag.nombre).all()
    normas_activas = Rule.query.filter_by(activo=True).order_by(Rule.nombre).limit(5).all()
    notifs_recientes = Notificacion.query.filter_by(resuelta=False).order_by(Notificacion.creado_en.desc()).limit(5).all()
    return render_template(
        "marketing/index.html",
        stats=stats,
        tags_b2c_sis=tags_b2c_sis, tags_b2c_din=tags_b2c_din, tags_b2c_tmp=tags_b2c_tmp,
        tags_b2b_sis=tags_b2b_sis, tags_b2b_din=tags_b2b_din, tags_b2b_tmp=tags_b2b_tmp,
        normas_activas=normas_activas,
        notifs_recientes=notifs_recientes,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Etiquetas
# ─────────────────────────────────────────────────────────────────────────────

def _post_save_scan(tag):
    """Lanza escaneo inmediato tras guardar una etiqueta con lógica automática."""
    if tag.tipo == "temporal" and tag.tiempo_sin_reserva_dias:
        from app.services.temporal_tags import evaluar_tags_temporales
        stats = evaluar_tags_temporales(tag_id=tag.id)
        flash(f"Escaneo temporal: {stats['asignadas']} asignadas, {stats['quitadas']} retiradas.", "info")
    if tag.tipo == "sistematica" and tag.entidad == "empresa" and (
        tag.criterio_min_gasto is not None or tag.criterio_min_empleados is not None
    ):
        from app.services.gran_cuenta_criterio import evaluar_gran_cuenta
        stats = evaluar_gran_cuenta(tag_id=tag.id)
        flash(f"Escaneo Gran Cuenta: {stats['asignadas']} empresas promovidas, "
              f"{stats['quitadas']} retiradas.", "info")
    if tag.tipo == "sistematica" and tag.entidad == "cliente" and (
        tag.criterio_min_gasto is not None or tag.criterio_min_reservas is not None
    ):
        from app.services.vip_criterio import evaluar_vip_criterio
        stats = evaluar_vip_criterio(tag_id=tag.id)
        flash(f"Escaneo VIP: {stats['asignadas']} clientes promovidos a VIP, "
              f"{stats['quitadas']} retirados.", "info")


@marketing_bp.route("/etiquetas")
@login_required
def etiquetas_lista():
    segmento = request.args.get("segmento", "")
    tipo     = request.args.get("tipo", "")
    query = Tag.query
    if segmento: query = query.filter_by(segmento=segmento)
    if tipo:     query = query.filter_by(tipo=tipo)
    tags = query.order_by(Tag.segmento, Tag.tipo, Tag.nombre).all()
    return render_template("marketing/etiquetas/lista.html", tags=tags,
                           segmento=segmento, tipo=tipo,
                           slugs_protegidos=SLUGS_PROTEGIDOS)


@marketing_bp.route("/etiquetas/nueva", methods=["GET", "POST"])
@login_required
def etiquetas_nueva():
    if request.method == "POST":
        slug = request.form.get("slug", "").strip().lower().replace(" ", "_")
        if Tag.query.filter_by(slug=slug).first():
            flash(f"Ya existe una etiqueta con el slug '{slug}'.", "danger")
            return redirect(url_for("marketing.etiquetas_nueva"))
        tipo = request.form.get("tipo", "sistematica")
        dias_raw = request.form.get("tiempo_sin_reserva_dias", "").strip()
        tiempo_dias = int(dias_raw) if tipo == "temporal" and dias_raw.isdigit() else None
        gasto_raw     = request.form.get("criterio_min_gasto", "").strip().replace(",", ".")
        reservas_raw  = request.form.get("criterio_min_reservas", "").strip()
        empleados_raw = request.form.get("criterio_min_empleados", "").strip()
        criterio_gasto     = float(gasto_raw)     if gasto_raw             else None
        criterio_reservas  = int(reservas_raw)    if reservas_raw.isdigit()  else None
        criterio_empleados = int(empleados_raw)   if empleados_raw.isdigit() else None
        tag = Tag(
            slug=slug,
            nombre=request.form.get("nombre", "").strip(),
            descripcion=request.form.get("descripcion", "").strip(),
            tipo=tipo,
            entidad=request.form.get("entidad", "cliente"),
            segmento=request.form.get("segmento", "b2c"),
            color=request.form.get("color", "#6B7280"),
            icono=request.form.get("icono", "bi-tag-fill"),
            trigger_evento=request.form.get("trigger_evento", "").strip(),
            filtro_descripcion=request.form.get("filtro_descripcion", "").strip(),
            tiempo_sin_reserva_dias=tiempo_dias,
            criterio_min_gasto=criterio_gasto,
            criterio_min_reservas=criterio_reservas,
            criterio_min_empleados=criterio_empleados,
        )
        db.session.add(tag)
        db.session.commit()
        registrar_log("crear", "tag", tag.id, f"Etiqueta creada: {tag.slug}")
        flash(f"Etiqueta '{tag.nombre}' creada.", "success")
        _post_save_scan(tag)
        return redirect(url_for("marketing.etiquetas_lista"))
    return render_template("marketing/etiquetas/form.html", tag=None, iconos=ICONOS_DISPONIBLES,
                           slugs_protegidos=SLUGS_PROTEGIDOS)


@marketing_bp.route("/etiquetas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def etiquetas_editar(id):
    tag = Tag.query.get_or_404(id)
    if request.method == "POST":
        new_slug = request.form.get("slug", "").strip().lower().replace(" ", "_")
        existing = Tag.query.filter_by(slug=new_slug).first()
        if existing and existing.id != tag.id:
            flash(f"Ya existe otra etiqueta con el slug '{new_slug}'.", "danger")
            return redirect(url_for("marketing.etiquetas_editar", id=id))
        nuevo_tipo = request.form.get("tipo", tag.tipo)
        dias_raw = request.form.get("tiempo_sin_reserva_dias", "").strip()
        tiempo_dias = int(dias_raw) if nuevo_tipo == "temporal" and dias_raw.isdigit() else None
        gasto_raw     = request.form.get("criterio_min_gasto", "").strip().replace(",", ".")
        reservas_raw  = request.form.get("criterio_min_reservas", "").strip()
        empleados_raw = request.form.get("criterio_min_empleados", "").strip()
        tag.slug                    = new_slug
        tag.nombre                  = request.form.get("nombre", "").strip()
        tag.descripcion             = request.form.get("descripcion", "").strip()
        tag.tipo                    = nuevo_tipo
        tag.entidad                 = request.form.get("entidad", tag.entidad)
        tag.segmento                = request.form.get("segmento", tag.segmento)
        tag.color                   = request.form.get("color", tag.color)
        tag.icono                   = request.form.get("icono", tag.icono)
        tag.trigger_evento          = request.form.get("trigger_evento", "").strip()
        tag.filtro_descripcion      = request.form.get("filtro_descripcion", "").strip()
        tag.tiempo_sin_reserva_dias = tiempo_dias
        tag.criterio_min_gasto      = float(gasto_raw)     if gasto_raw              else None
        tag.criterio_min_reservas   = int(reservas_raw)   if reservas_raw.isdigit()  else None
        tag.criterio_min_empleados  = int(empleados_raw)  if empleados_raw.isdigit() else None
        db.session.commit()
        registrar_log("editar", "tag", tag.id, f"Etiqueta editada: {tag.slug}")
        flash(f"Etiqueta '{tag.nombre}' actualizada.", "success")
        _post_save_scan(tag)
        return redirect(url_for("marketing.etiquetas_lista"))
    return render_template("marketing/etiquetas/form.html", tag=tag, iconos=ICONOS_DISPONIBLES,
                           slugs_protegidos=SLUGS_PROTEGIDOS)


@marketing_bp.route("/etiquetas/<int:id>/eliminar", methods=["POST"])
@login_required
def etiquetas_eliminar(id):
    tag = Tag.query.get_or_404(id)
    if tag.slug in SLUGS_PROTEGIDOS:
        flash(f"La etiqueta «{tag.nombre}» está protegida y no puede eliminarse "
              f"porque tiene lógica de automatización en el backend.", "danger")
        return redirect(url_for("marketing.etiquetas_lista"))
    slug, nombre = tag.slug, tag.nombre
    db.session.delete(tag)
    db.session.commit()
    registrar_log("eliminar", "tag", id, f"Etiqueta eliminada: {slug}")
    flash(f"Etiqueta '{nombre}' eliminada.", "info")
    return redirect(url_for("marketing.etiquetas_lista"))


@marketing_bp.route("/etiquetas/<int:id>/toggle", methods=["POST"])
@login_required
def etiquetas_toggle(id):
    tag = Tag.query.get_or_404(id)
    tag.activo = not tag.activo
    db.session.commit()
    flash(f"Etiqueta '{tag.nombre}' {'activada' if tag.activo else 'desactivada'}.", "success")
    return redirect(url_for("marketing.etiquetas_lista"))


# ─────────────────────────────────────────────────────────────────────────────
#  Plantillas de email
# ─────────────────────────────────────────────────────────────────────────────

@marketing_bp.route("/plantillas")
@login_required
def plantillas_lista():
    segmento = request.args.get("segmento", "")
    query = PlantillaEmail.query
    if segmento:
        query = query.filter(
            (PlantillaEmail.segmento == segmento) | (PlantillaEmail.segmento == "ambos")
        )
    plantillas = query.order_by(PlantillaEmail.nombre).all()
    return render_template("marketing/plantillas/lista.html", plantillas=plantillas, segmento=segmento)


@marketing_bp.route("/plantillas/nueva", methods=["GET", "POST"])
@login_required
def plantillas_nueva():
    if request.method == "POST":
        p = PlantillaEmail(
            nombre=request.form.get("nombre", "").strip(),
            asunto=request.form.get("asunto", "").strip(),
            descripcion=request.form.get("descripcion", "").strip(),
            segmento=request.form.get("segmento", "ambos"),
            cuerpo_html=request.form.get("cuerpo_html", "").strip(),
        )
        db.session.add(p)
        db.session.commit()
        registrar_log("crear", "plantilla", p.id, f"Plantilla creada: {p.nombre}")
        flash(f"Plantilla '{p.nombre}' creada.", "success")
        return redirect(url_for("marketing.plantillas_lista"))
    return render_template("marketing/plantillas/form.html", plantilla=None)


@marketing_bp.route("/plantillas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def plantillas_editar(id):
    p = PlantillaEmail.query.get_or_404(id)
    if request.method == "POST":
        p.nombre      = request.form.get("nombre", "").strip()
        p.asunto      = request.form.get("asunto", "").strip()
        p.descripcion = request.form.get("descripcion", "").strip()
        p.segmento    = request.form.get("segmento", p.segmento)
        p.cuerpo_html = request.form.get("cuerpo_html", "").strip()
        db.session.commit()
        registrar_log("editar", "plantilla", p.id, f"Plantilla editada: {p.nombre}")
        flash(f"Plantilla '{p.nombre}' actualizada.", "success")
        return redirect(url_for("marketing.plantillas_lista"))
    return render_template("marketing/plantillas/form.html", plantilla=p)


@marketing_bp.route("/plantillas/<int:id>/eliminar", methods=["POST"])
@login_required
def plantillas_eliminar(id):
    p = PlantillaEmail.query.get_or_404(id)
    nombre = p.nombre
    db.session.delete(p)
    db.session.commit()
    registrar_log("eliminar", "plantilla", id, f"Plantilla eliminada: {nombre}")
    flash(f"Plantilla '{nombre}' eliminada.", "info")
    return redirect(url_for("marketing.plantillas_lista"))


@marketing_bp.route("/plantillas/<int:id>/toggle", methods=["POST"])
@login_required
def plantillas_toggle(id):
    p = PlantillaEmail.query.get_or_404(id)
    p.activo = not p.activo
    db.session.commit()
    flash(f"Plantilla '{p.nombre}' {'activada' if p.activo else 'desactivada'}.", "success")
    return redirect(url_for("marketing.plantillas_lista"))


# ─────────────────────────────────────────────────────────────────────────────
#  Normas (Rules)  —  multi-action
# ─────────────────────────────────────────────────────────────────────────────

def _save_rule_tags(rule, req_ids, exc_ids):
    RuleTag.query.filter_by(rule_id=rule.id).delete()
    req_set = set(req_ids)
    exc_set = set(exc_ids) - req_set
    for tid in req_set:
        db.session.add(RuleTag(rule_id=rule.id, tag_id=tid, tipo="requerida"))
    for tid in exc_set:
        db.session.add(RuleTag(rule_id=rule.id, tag_id=tid, tipo="excluida"))


def _save_rule_acciones(rule_id, form):
    """Parse indexed accion_tipo_N fields and create RuleAccion records."""
    RuleAccion.query.filter_by(rule_id=rule_id).delete()
    count = int(form.get("acciones_count", 0) or 0)
    orden = 0
    for i in range(count):
        tipo = form.get(f"accion_tipo_{i}", "").strip()
        if not tipo:
            continue
        plantilla_id = form.get(f"accion_plantilla_id_{i}", type=int) or None
        msg_wa   = form.get(f"accion_msg_wa_{i}", "").strip()
        msg_notif = form.get(f"accion_msg_notif_{i}", "").strip()
        db.session.add(RuleAccion(
            rule_id=rule_id,
            tipo=tipo,
            plantilla_id=plantilla_id if tipo == "email" else None,
            mensaje_whatsapp=msg_wa     if tipo == "whatsapp"    else "",
            mensaje_notificacion=msg_notif if tipo == "notificacion" else "",
            orden=orden,
        ))
        orden += 1


def _plantillas_json():
    ps = PlantillaEmail.query.filter_by(activo=True).order_by(PlantillaEmail.nombre).all()
    return [{"id": p.id, "nombre": p.nombre, "segmento": p.segmento} for p in ps]


def _plantillas_wa_json():
    ps = PlantillaWA.query.filter_by(activo=True).order_by(PlantillaWA.nombre).all()
    return [{"id": p.id, "nombre": p.nombre, "cuerpo": p.cuerpo} for p in ps]


@marketing_bp.route("/normas")
@login_required
def normas_lista():
    segmento = request.args.get("segmento", "")
    query = Rule.query
    if segmento:
        query = query.filter(
            (Rule.segmento == segmento) | (Rule.segmento == "ambos")
        )
    normas = query.order_by(Rule.nombre).all()
    return render_template("marketing/normas/lista.html", normas=normas, segmento=segmento)


@marketing_bp.route("/normas/nueva", methods=["GET", "POST"])
@login_required
def normas_nueva():
    all_tags   = Tag.query.filter_by(activo=True).order_by(Tag.segmento, Tag.tipo, Tag.nombre).all()
    plantillas = PlantillaEmail.query.filter_by(activo=True).order_by(PlantillaEmail.nombre).all()
    if request.method == "POST":
        rule = Rule(
            nombre=request.form.get("nombre", "").strip(),
            descripcion=request.form.get("descripcion", "").strip(),
            segmento=request.form.get("segmento", "b2c"),
            entidad=request.form.get("entidad", "cliente"),
            delay_horas=int(request.form.get("delay_horas", 0) or 0),
        )
        db.session.add(rule)
        db.session.flush()
        req_ids = [int(x) for x in request.form.getlist("tags_requeridas")]
        exc_ids = [int(x) for x in request.form.getlist("tags_excluidas")]
        _save_rule_tags(rule, req_ids, exc_ids)
        _save_rule_acciones(rule.id, request.form)
        db.session.commit()
        registrar_log("crear", "rule", rule.id, f"Norma creada: {rule.nombre}")
        flash(f"Norma '{rule.nombre}' creada.", "success")
        return redirect(url_for("marketing.normas_lista"))
    return render_template(
        "marketing/normas/form.html",
        rule=None, all_tags=all_tags,
        plantillas=plantillas, delay_opciones=DELAY_OPCIONES,
        plantillas_json=_plantillas_json(),
        plantillas_wa_json=_plantillas_wa_json(),
        req_ids=set(), exc_ids=set(),
    )


@marketing_bp.route("/normas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def normas_editar(id):
    rule       = Rule.query.get_or_404(id)
    all_tags   = Tag.query.filter_by(activo=True).order_by(Tag.segmento, Tag.tipo, Tag.nombre).all()
    plantillas = PlantillaEmail.query.filter_by(activo=True).order_by(PlantillaEmail.nombre).all()
    if request.method == "POST":
        rule.nombre      = request.form.get("nombre", "").strip()
        rule.descripcion = request.form.get("descripcion", "").strip()
        rule.segmento    = request.form.get("segmento", rule.segmento)
        rule.entidad     = request.form.get("entidad",   rule.entidad)
        rule.delay_horas = int(request.form.get("delay_horas", 0) or 0)
        req_ids = [int(x) for x in request.form.getlist("tags_requeridas")]
        exc_ids = [int(x) for x in request.form.getlist("tags_excluidas")]
        _save_rule_tags(rule, req_ids, exc_ids)
        _save_rule_acciones(rule.id, request.form)
        db.session.commit()
        registrar_log("editar", "rule", rule.id, f"Norma editada: {rule.nombre}")
        flash(f"Norma '{rule.nombre}' actualizada.", "success")
        return redirect(url_for("marketing.normas_lista"))
    req_ids = {rt.tag_id for rt in rule.rule_tags if rt.tipo == "requerida"}
    exc_ids = {rt.tag_id for rt in rule.rule_tags if rt.tipo == "excluida"}
    return render_template(
        "marketing/normas/form.html",
        rule=rule, all_tags=all_tags,
        plantillas=plantillas, delay_opciones=DELAY_OPCIONES,
        plantillas_json=_plantillas_json(),
        plantillas_wa_json=_plantillas_wa_json(),
        req_ids=req_ids, exc_ids=exc_ids,
    )


@marketing_bp.route("/normas/<int:id>/eliminar", methods=["POST"])
@login_required
def normas_eliminar(id):
    rule = Rule.query.get_or_404(id)
    nombre = rule.nombre
    db.session.delete(rule)
    db.session.commit()
    registrar_log("eliminar", "rule", id, f"Norma eliminada: {nombre}")
    flash(f"Norma '{nombre}' eliminada.", "info")
    return redirect(url_for("marketing.normas_lista"))


@marketing_bp.route("/normas/<int:id>/toggle", methods=["POST"])
@login_required
def normas_toggle(id):
    rule = Rule.query.get_or_404(id)
    rule.activo = not rule.activo
    db.session.commit()
    evento = "norma_activada" if rule.activo else "norma_desactivada"
    flash(f"Norma '{rule.nombre}' {'activada' if rule.activo else 'desactivada'}.", "success")
    registrar_log("cambiar_estado", "rule", id,
                  f"Norma '{rule.nombre}' {'activada' if rule.activo else 'desactivada'}")
    registrar_marketing_log(
        evento, resultado="ok",
        rule_id=rule.id, rule_nombre=rule.nombre,
        detalle=f"Norma «{rule.nombre}» {'activada' if rule.activo else 'desactivada'} manualmente",
        origen="manual",
    )
    return redirect(url_for("marketing.normas_lista"))


# ─────────────────────────────────────────────────────────────────────────────
#  Notificaciones
# ─────────────────────────────────────────────────────────────────────────────

@marketing_bp.route("/notificaciones")
@login_required
def notificaciones_lista():
    estado   = request.args.get("estado", "pendiente")   # pendiente | resuelta | todas
    tipo     = request.args.get("tipo", "")
    prioridad = request.args.get("prioridad", "")

    query = Notificacion.query
    if estado == "pendiente":
        query = query.filter_by(resuelta=False)
    elif estado == "resuelta":
        query = query.filter_by(resuelta=True)
    if tipo:
        query = query.filter_by(tipo=tipo)
    if prioridad:
        query = query.filter_by(prioridad=prioridad)

    notificaciones = query.order_by(
        Notificacion.resuelta.asc(),
        Notificacion.creado_en.desc()
    ).all()

    pendientes = Notificacion.query.filter_by(resuelta=False).count()
    return render_template(
        "marketing/notificaciones/lista.html",
        notificaciones=notificaciones,
        estado=estado, tipo=tipo, prioridad=prioridad,
        pendientes=pendientes,
    )


@marketing_bp.route("/api/buscar-entidad")
@login_required
def api_buscar_entidad():
    from app.models.cliente import Cliente
    from app.models.empresa import Empresa
    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify([])
    like = f"%{q}%"
    results = []
    for c in Cliente.query.filter(
        db.or_(
            (Cliente.nombre + " " + Cliente.apellido).ilike(like),
            Cliente.email.ilike(like),
            Cliente.telefono.ilike(like),
        )
    ).limit(8).all():
        results.append({
            "id": c.id, "tipo": "cliente",
            "nombre": c.nombre_completo,
            "subtitulo": c.email or c.telefono,
        })
    for e in Empresa.query.filter(
        db.or_(
            Empresa.nombre.ilike(like),
            Empresa.persona_contacto.ilike(like),
            Empresa.email.ilike(like),
        )
    ).limit(5).all():
        results.append({
            "id": e.id, "tipo": "empresa",
            "nombre": e.nombre,
            "subtitulo": e.persona_contacto or e.email,
        })
    return jsonify(results)


@marketing_bp.route("/notificaciones/nueva", methods=["POST"])
@login_required
def notificaciones_nueva():
    entidad_id     = request.form.get("entidad_id", type=int) or None
    entidad        = request.form.get("entidad", "cliente")
    entidad_nombre = request.form.get("entidad_nombre", "").strip()
    titulo         = request.form.get("titulo", "").strip()
    n = Notificacion(
        titulo=titulo,
        mensaje=request.form.get("mensaje", "").strip(),
        tipo=request.form.get("tipo", "llamada"),
        prioridad=request.form.get("prioridad", "media"),
        entidad=entidad,
        entidad_id=entidad_id,
        entidad_nombre=entidad_nombre,
    )
    db.session.add(n)
    db.session.commit()
    flash("Notificación creada.", "success")
    registrar_marketing_log(
        "notificacion_creada", resultado="ok",
        entidad=entidad, entidad_id=entidad_id, entidad_nombre=entidad_nombre,
        detalle=f"Notificación creada manualmente: «{titulo}»",
        origen="manual",
    )
    return redirect(url_for("marketing.notificaciones_lista"))


@marketing_bp.route("/notificaciones/<int:id>/resolver", methods=["POST"])
@login_required
def notificaciones_resolver(id):
    n = Notificacion.query.get_or_404(id)
    n.resuelta = True
    n.resuelta_en = datetime.utcnow()
    db.session.commit()
    flash("Notificación marcada como resuelta.", "success")
    registrar_marketing_log(
        "notificacion_resuelta", resultado="ok",
        entidad=n.entidad or "", entidad_id=n.entidad_id, entidad_nombre=n.entidad_nombre or "",
        detalle=f"Notificación resuelta: «{n.titulo}»",
        origen="manual",
    )
    return redirect(url_for("marketing.notificaciones_lista",
                             estado=request.args.get("estado", "pendiente"),
                             tipo=request.args.get("tipo", ""),
                             prioridad=request.args.get("prioridad", "")))


@marketing_bp.route("/notificaciones/<int:id>/eliminar", methods=["POST"])
@login_required
def notificaciones_eliminar(id):
    n = Notificacion.query.get_or_404(id)
    db.session.delete(n)
    db.session.commit()
    flash("Notificación eliminada.", "info")
    return redirect(url_for("marketing.notificaciones_lista"))


# ─────────────────────────────────────────────────────────────────────────────
#  Trazabilidad por cliente / empresa
# ─────────────────────────────────────────────────────────────────────────────

# Eventos que representan comunicaciones reales (email / WA / campañas)
_EVENTOS_COMUNICACION = {
    "accion_email", "accion_whatsapp",
    "campana_email_ok", "campana_wa_ok", "campana_enviada",
    "accion_notificacion",
}

@marketing_bp.route("/trazabilidad")
@login_required
def trazabilidad():
    from app.models.marketing_log import MarketingLog

    q       = request.args.get("q", "").strip()
    tipo    = request.args.get("tipo", "")   # cliente | empresa | ""
    page    = request.args.get("page", 1, type=int)

    # Obtener entidades únicas con actividad, con su última fecha y total de eventos
    subq = (
        db.session.query(
            MarketingLog.entidad,
            MarketingLog.entidad_id,
            MarketingLog.entidad_nombre,
            db.func.count(MarketingLog.id).label("total"),
            db.func.max(MarketingLog.fecha).label("ultima"),
        )
        .filter(MarketingLog.entidad_id.isnot(None))
        .group_by(MarketingLog.entidad, MarketingLog.entidad_id, MarketingLog.entidad_nombre)
    )
    if q:
        subq = subq.filter(MarketingLog.entidad_nombre.ilike(f"%{q}%"))
    if tipo:
        subq = subq.filter(MarketingLog.entidad == tipo)

    resultados = subq.order_by(db.text("ultima DESC")).paginate(
        page=page, per_page=30, error_out=False
    )

    total_entidades = db.session.query(
        db.func.count(db.func.distinct(MarketingLog.entidad_id))
    ).filter(MarketingLog.entidad_id.isnot(None)).scalar() or 0

    return render_template(
        "marketing/trazabilidad.html",
        resultados=resultados,
        q=q, tipo=tipo,
        total_entidades=total_entidades,
    )


@marketing_bp.route("/trazabilidad/<entidad>/<int:eid>")
@login_required
def trazabilidad_detalle(entidad, eid):
    from app.models.marketing_log import MarketingLog
    from app.models.campana import CampanaLog
    from app.models.tag import ClienteTag, EmpresaTag, Tag
    from app.models.cliente import Cliente
    from app.models.empresa import Empresa

    if entidad == "cliente":
        obj = Cliente.query.get_or_404(eid)
        nombre    = obj.nombre_completo
        email     = obj.email
        telefono  = obj.telefono
        subtitulo = f"Cliente B2C · {obj.fuente}"
        url_ficha = url_for("clientes.detalle", id=eid)
        tags_act  = (
            db.session.query(Tag)
            .join(ClienteTag, ClienteTag.tag_id == Tag.id)
            .filter(ClienteTag.cliente_id == eid)
            .order_by(Tag.nombre)
            .all()
        )
    elif entidad == "empresa":
        obj = Empresa.query.get_or_404(eid)
        nombre    = obj.nombre
        email     = obj.email
        telefono  = obj.telefono
        subtitulo = f"Empresa B2B · {obj.sector or '—'}"
        url_ficha = url_for("teambuilding.empresas_detalle", id=eid)
        tags_act  = (
            db.session.query(Tag)
            .join(EmpresaTag, EmpresaTag.tag_id == Tag.id)
            .filter(EmpresaTag.empresa_id == eid)
            .order_by(Tag.nombre)
            .all()
        )
    else:
        return redirect(url_for("marketing.trazabilidad"))

    # Timeline: todos los marketing logs de esta entidad
    timeline = (
        MarketingLog.query
        .filter_by(entidad=entidad, entidad_id=eid)
        .order_by(MarketingLog.fecha.desc())
        .all()
    )

    # Campañas recibidas
    campana_logs = (
        CampanaLog.query
        .filter_by(entidad=entidad, entidad_id=eid)
        .order_by(CampanaLog.enviado_en.desc())
        .all()
    )

    # Stats rápidas
    stats = {
        "total":     len(timeline),
        "emails":    sum(1 for l in timeline if l.evento in ("accion_email", "campana_email_ok")),
        "whatsapp":  sum(1 for l in timeline if l.evento in ("accion_whatsapp", "campana_wa_ok")),
        "campanas":  len({cl.campana_id for cl in campana_logs}),
        "tags_hist": sum(1 for l in timeline if l.evento == "tag_asignada"),
    }

    return render_template(
        "marketing/trazabilidad_detalle.html",
        entidad=entidad, eid=eid,
        nombre=nombre, email=email, telefono=telefono,
        subtitulo=subtitulo, url_ficha=url_ficha,
        tags_act=tags_act,
        timeline=timeline,
        campana_logs=campana_logs,
        stats=stats,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Logs de automatización
# ─────────────────────────────────────────────────────────────────────────────

@marketing_bp.route("/logs")
@login_required
def logs_lista():
    from app.models.marketing_log import MarketingLog

    evento    = request.args.get("evento", "")
    resultado = request.args.get("resultado", "")
    origen    = request.args.get("origen", "")
    page      = request.args.get("page", 1, type=int)

    query = MarketingLog.query
    if evento:
        query = query.filter_by(evento=evento)
    if resultado:
        query = query.filter_by(resultado=resultado)
    if origen:
        query = query.filter_by(origen=origen)

    logs = query.order_by(MarketingLog.fecha.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    # Stats para la cabecera
    total   = MarketingLog.query.count()
    errores = MarketingLog.query.filter_by(resultado="error").count()
    hoy     = MarketingLog.query.filter(
        MarketingLog.fecha >= datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    ).count()

    # Tipos de eventos presentes (para el filtro)
    from sqlalchemy import func as sqlfunc, distinct
    eventos_presentes = [
        r[0] for r in
        db.session.query(distinct(MarketingLog.evento))
        .order_by(MarketingLog.evento).all()
    ]

    return render_template(
        "marketing/logs/lista.html",
        logs=logs,
        evento=evento, resultado=resultado, origen=origen,
        total=total, errores=errores, hoy=hoy,
        eventos_presentes=eventos_presentes,
    )


@marketing_bp.route("/logs/limpiar", methods=["POST"])
@login_required
def logs_limpiar():
    """Elimina los logs de marketing más antiguos de 90 días."""
    from app.models.marketing_log import MarketingLog
    from datetime import timedelta
    corte = datetime.utcnow() - timedelta(days=90)
    borrados = MarketingLog.query.filter(MarketingLog.fecha < corte).delete()
    db.session.commit()
    flash(f"Se eliminaron {borrados} registros de log anteriores a 90 días.", "info")
    return redirect(url_for("marketing.logs_lista"))


# ─────────────────────────────────────────────────────────────────────────────
#  Plantillas WhatsApp
# ─────────────────────────────────────────────────────────────────────────────

@marketing_bp.route("/plantillas_wa")
@login_required
def plantillas_wa_lista():
    plantillas = PlantillaWA.query.order_by(PlantillaWA.nombre).all()
    return render_template("marketing/plantillas_wa/lista.html", plantillas=plantillas)


@marketing_bp.route("/plantillas_wa/nueva", methods=["GET", "POST"])
@login_required
def plantillas_wa_nueva():
    if request.method == "POST":
        p = PlantillaWA(
            nombre      = request.form.get("nombre", "").strip(),
            descripcion = request.form.get("descripcion", "").strip(),
            cuerpo      = request.form.get("cuerpo", "").strip(),
            activo      = request.form.get("activo") == "1",
        )
        db.session.add(p)
        db.session.commit()
        flash(f"Plantilla WhatsApp «{p.nombre}» creada.", "success")
        return redirect(url_for("marketing.plantillas_wa_lista"))
    return render_template("marketing/plantillas_wa/form.html", p=None)


@marketing_bp.route("/plantillas_wa/<int:id>/editar", methods=["GET", "POST"])
@login_required
def plantillas_wa_editar(id):
    p = PlantillaWA.query.get_or_404(id)
    if request.method == "POST":
        p.nombre      = request.form.get("nombre", "").strip()
        p.descripcion = request.form.get("descripcion", "").strip()
        p.cuerpo      = request.form.get("cuerpo", "").strip()
        p.activo      = request.form.get("activo") == "1"
        db.session.commit()
        flash("Plantilla WhatsApp actualizada.", "success")
        return redirect(url_for("marketing.plantillas_wa_lista"))
    return render_template("marketing/plantillas_wa/form.html", p=p)


@marketing_bp.route("/plantillas_wa/<int:id>/eliminar", methods=["POST"])
@login_required
def plantillas_wa_eliminar(id):
    p = PlantillaWA.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash("Plantilla WhatsApp eliminada.", "info")
    return redirect(url_for("marketing.plantillas_wa_lista"))


# ─────────────────────────────────────────────────────────────────────────────
#  Campañas
# ─────────────────────────────────────────────────────────────────────────────

@marketing_bp.route("/campanas/calendario")
@login_required
def campanas_calendario():
    return render_template("marketing/campanas/calendario.html")


@marketing_bp.route("/campanas/calendario/eventos")
@login_required
def campanas_calendario_eventos():
    _COLOR = {
        "borrador":   "#9CA3AF",
        "programada": "#F59E0B",
        "enviando":   "#3B82F6",
        "enviada":    "#10B981",
        "error":      "#EF4444",
    }
    campanas = Campana.query.filter(Campana.fecha_envio.isnot(None)).all()
    events = []
    for c in campanas:
        color = _COLOR.get(c.estado, "#9CA3AF")
        events.append({
            "id":              c.id,
            "title":           c.nombre,
            "start":           c.fecha_envio.isoformat(),
            "url":             url_for("marketing.campanas_detalle", id=c.id),
            "backgroundColor": color,
            "borderColor":     color,
            "extendedProps": {
                "estado":      c.estado_label,
                "canal":       c.canal,
                "descripcion": c.descripcion or "",
            },
        })
    return jsonify(events)


@marketing_bp.route("/campanas")
@login_required
def campanas_lista():
    estado = request.args.get("estado", "")
    query  = Campana.query
    if estado:
        query = query.filter_by(estado=estado)
    campanas = query.order_by(Campana.creado_en.desc()).all()
    return render_template("marketing/campanas/lista.html", campanas=campanas, estado=estado)


@marketing_bp.route("/campanas/nueva", methods=["GET", "POST"])
@login_required
def campanas_nueva():
    if request.method == "POST":
        campana = _campana_from_form(None)
        db.session.add(campana)
        db.session.flush()
        _save_campana_tags(campana)
        if campana.estado == "programada":
            registrar_marketing_log(
                "campana_programada", resultado="ok",
                campana_id=campana.id, campana_nombre=campana.nombre,
                detalle=f"Programada para {campana.fecha_envio.strftime('%d/%m/%Y %H:%M') if campana.fecha_envio else '—'}",
                origen="manual",
            )
        db.session.commit()
        flash(f"Campaña «{campana.nombre}» creada.", "success")
        return redirect(url_for("marketing.campanas_detalle", id=campana.id))
    all_tags       = Tag.query.filter_by(activo=True).order_by(Tag.segmento, Tag.nombre).all()
    plantillas_e   = PlantillaEmail.query.filter_by(activo=True).order_by(PlantillaEmail.nombre).all()
    plantillas_wa  = PlantillaWA.query.filter_by(activo=True).order_by(PlantillaWA.nombre).all()
    fecha_inicial  = request.args.get("fecha", "")
    return render_template("marketing/campanas/form.html",
                           campana=None, all_tags=all_tags,
                           inc_ids=set(), exc_ids=set(),
                           plantillas_e=plantillas_e, plantillas_wa=plantillas_wa,
                           fecha_inicial=fecha_inicial)


@marketing_bp.route("/campanas/<int:id>")
@login_required
def campanas_detalle(id):
    campana = Campana.query.get_or_404(id)
    logs    = CampanaLog.query.filter_by(campana_id=id).order_by(CampanaLog.enviado_en.desc()).limit(200).all()
    return render_template("marketing/campanas/detalle.html", campana=campana, logs=logs)


@marketing_bp.route("/campanas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def campanas_editar(id):
    campana = Campana.query.get_or_404(id)
    if campana.estado in ("enviando", "enviada"):
        flash("No se puede editar una campaña ya enviada.", "warning")
        return redirect(url_for("marketing.campanas_detalle", id=id))
    if request.method == "POST":
        _campana_from_form(campana)
        CampanaTag.query.filter_by(campana_id=campana.id).delete()
        _save_campana_tags(campana)
        db.session.commit()
        flash("Campaña actualizada.", "success")
        return redirect(url_for("marketing.campanas_detalle", id=campana.id))
    all_tags      = Tag.query.filter_by(activo=True).order_by(Tag.segmento, Tag.nombre).all()
    plantillas_e  = PlantillaEmail.query.filter_by(activo=True).order_by(PlantillaEmail.nombre).all()
    plantillas_wa = PlantillaWA.query.filter_by(activo=True).order_by(PlantillaWA.nombre).all()
    inc_ids = {ct.tag_id for ct in campana.campana_tags if ct.modo == "incluir"}
    exc_ids = {ct.tag_id for ct in campana.campana_tags if ct.modo == "excluir"}
    return render_template("marketing/campanas/form.html",
                           campana=campana, all_tags=all_tags,
                           inc_ids=inc_ids, exc_ids=exc_ids,
                           plantillas_e=plantillas_e, plantillas_wa=plantillas_wa,
                           fecha_inicial="")


@marketing_bp.route("/campanas/<int:id>/eliminar", methods=["POST"])
@login_required
def campanas_eliminar(id):
    campana = Campana.query.get_or_404(id)
    nombre  = campana.nombre
    db.session.delete(campana)
    db.session.commit()
    flash(f"Campaña «{nombre}» eliminada.", "info")
    return redirect(url_for("marketing.campanas_lista"))


@marketing_bp.route("/campanas/<int:id>/enviar", methods=["POST"])
@login_required
def campanas_enviar(id):
    campana = Campana.query.get_or_404(id)
    if campana.estado == "enviando":
        flash("La campaña ya se está enviando.", "warning")
        return redirect(url_for("marketing.campanas_detalle", id=id))
    from app.services.campana_service import ejecutar_campana
    stats = ejecutar_campana(id)
    flash(f"Campaña enviada: {stats['enviados']} OK, {stats['errores']} errores.", "success")
    return redirect(url_for("marketing.campanas_detalle", id=id))


@marketing_bp.route("/campanas/<int:id>/duplicar", methods=["POST"])
@login_required
def campanas_duplicar(id):
    original = Campana.query.get_or_404(id)
    copia = Campana(
        nombre             = f"Copia de {original.nombre}",
        descripcion        = original.descripcion,
        canal              = original.canal,
        segmento           = original.segmento,
        plantilla_email_id = original.plantilla_email_id,
        plantilla_wa_id    = original.plantilla_wa_id,
        fecha_envio        = None,
        estado             = "borrador",
    )
    db.session.add(copia)
    db.session.flush()
    for ct in original.campana_tags:
        db.session.add(CampanaTag(campana_id=copia.id, tag_id=ct.tag_id, modo=ct.modo))
    db.session.commit()
    flash(f"Campaña duplicada como «{copia.nombre}».", "success")
    return redirect(url_for("marketing.campanas_editar", id=copia.id))


# ── helpers ───────────────────────────────────────────────────────────────────

def _campana_from_form(campana):
    """Crea o actualiza una Campana con los datos del formulario."""
    nombre      = request.form.get("nombre", "").strip()
    descripcion = request.form.get("descripcion", "").strip()
    canal       = request.form.get("canal", "email")
    segmento    = request.form.get("segmento", "todos")
    pe_id_raw   = request.form.get("plantilla_email_id", "")
    wa_id_raw   = request.form.get("plantilla_wa_id", "")
    fecha_raw   = request.form.get("fecha_envio", "").strip()
    programar   = request.form.get("programar") == "1"

    plantilla_email_id = int(pe_id_raw) if pe_id_raw.isdigit() else None
    plantilla_wa_id    = int(wa_id_raw) if wa_id_raw.isdigit() else None

    fecha_envio = None
    if programar and fecha_raw:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                fecha_envio = datetime.strptime(fecha_raw, fmt)
                break
            except ValueError:
                pass

    if campana is None:
        campana = Campana()
    campana.nombre             = nombre
    campana.descripcion        = descripcion
    campana.canal              = canal
    campana.segmento           = segmento
    campana.plantilla_email_id = plantilla_email_id
    campana.plantilla_wa_id    = plantilla_wa_id
    campana.fecha_envio        = fecha_envio
    campana.estado             = "programada" if programar and fecha_envio else "borrador"
    return campana


def _save_campana_tags(campana):
    for tag_id in request.form.getlist("tags_incluidas"):
        if tag_id.isdigit():
            db.session.add(CampanaTag(campana_id=campana.id, tag_id=int(tag_id), modo="incluir"))
    for tag_id in request.form.getlist("tags_excluidas"):
        if tag_id.isdigit():
            db.session.add(CampanaTag(campana_id=campana.id, tag_id=int(tag_id), modo="excluir"))
