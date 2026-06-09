from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.extensions import db
from app.models.agenda import (
    EntradaAgenda, Tematica,
    EMPRESAS, TIPOS, REDES, ESTADOS,
)

agenda_bp = Blueprint("agenda", __name__)


@agenda_bp.route("/")
@login_required
def index():
    tematicas = (
        Tematica.query
        .filter_by(activo=True)
        .order_by(Tematica.empresa, Tematica.nombre)
        .all()
    )
    return render_template("agenda/index.html", tematicas=tematicas)


@agenda_bp.route("/api/eventos")
@login_required
def api_eventos():
    empresa = request.args.get("empresa", "")
    tipo    = request.args.get("tipo",    "")

    q = EntradaAgenda.query
    if empresa:
        q = q.filter(EntradaAgenda.empresa == empresa)
    if tipo:
        q = q.filter(EntradaAgenda.tipo == tipo)

    entradas = q.order_by(EntradaAgenda.fecha).all()
    return jsonify([e.to_calendar_event() for e in entradas])


# ── ENTRADAS ──────────────────────────────────────────────────────

@agenda_bp.route("/entradas/nueva", methods=["GET", "POST"])
@login_required
def nueva_entrada():
    tematicas = (
        Tematica.query.filter_by(activo=True)
        .order_by(Tematica.empresa, Tematica.nombre).all()
    )

    if request.method == "POST":
        titulo    = request.form.get("titulo", "").strip()
        fecha_str = request.form.get("fecha", "").strip()

        if not titulo or not fecha_str:
            flash("La fecha y el título son obligatorios.", "danger")
            return _render_form(None, tematicas, request.form)

        try:
            fecha = date.fromisoformat(fecha_str)
        except ValueError:
            flash("Fecha inválida.", "danger")
            return _render_form(None, tematicas, request.form)

        entrada = EntradaAgenda(
            fecha       = fecha,
            titulo      = titulo,
            empresa     = request.form.get("empresa", "ambas"),
            tipo        = request.form.get("tipo", "otro"),
            red_social  = request.form.get("red_social", ""),
            descripcion = request.form.get("descripcion", "").strip(),
            url         = request.form.get("url", "").strip(),
            estado      = request.form.get("estado", "planificado"),
            notas       = request.form.get("notas", "").strip(),
        )

        ids = [int(i) for i in request.form.getlist("tematicas") if i.isdigit()]
        if ids:
            entrada.tematicas = Tematica.query.filter(Tematica.id.in_(ids)).all()

        db.session.add(entrada)
        db.session.commit()
        flash("Entrada añadida a la agenda.", "success")
        return redirect(url_for("agenda.index"))

    fecha_prefill = request.args.get("fecha", "")
    return _render_form(None, tematicas, {"fecha": fecha_prefill})


@agenda_bp.route("/entradas/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_entrada(id):
    entrada  = EntradaAgenda.query.get_or_404(id)
    tematicas = (
        Tematica.query.filter_by(activo=True)
        .order_by(Tematica.empresa, Tematica.nombre).all()
    )

    if request.method == "POST":
        titulo    = request.form.get("titulo", "").strip()
        fecha_str = request.form.get("fecha", "").strip()

        if not titulo or not fecha_str:
            flash("La fecha y el título son obligatorios.", "danger")
            return _render_form(entrada, tematicas, request.form)

        try:
            entrada.fecha = date.fromisoformat(fecha_str)
        except ValueError:
            flash("Fecha inválida.", "danger")
            return _render_form(entrada, tematicas, request.form)

        entrada.titulo      = titulo
        entrada.empresa     = request.form.get("empresa", "ambas")
        entrada.tipo        = request.form.get("tipo", "otro")
        entrada.red_social  = request.form.get("red_social", "")
        entrada.descripcion = request.form.get("descripcion", "").strip()
        entrada.url         = request.form.get("url", "").strip()
        entrada.estado      = request.form.get("estado", "planificado")
        entrada.notas       = request.form.get("notas", "").strip()
        entrada.actualizado_en = datetime.utcnow()

        ids = [int(i) for i in request.form.getlist("tematicas") if i.isdigit()]
        entrada.tematicas = Tematica.query.filter(Tematica.id.in_(ids)).all() if ids else []

        db.session.commit()
        flash("Entrada actualizada.", "success")
        return redirect(url_for("agenda.index"))

    return _render_form(entrada, tematicas)


@agenda_bp.route("/entradas/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar_entrada(id):
    entrada = EntradaAgenda.query.get_or_404(id)
    db.session.delete(entrada)
    db.session.commit()
    flash("Entrada eliminada.", "success")
    return redirect(url_for("agenda.index"))


# ── TEMÁTICAS ─────────────────────────────────────────────────────

@agenda_bp.route("/tematicas")
@login_required
def tematicas():
    lista = (
        Tematica.query
        .order_by(Tematica.empresa, Tematica.nombre)
        .all()
    )
    return render_template(
        "agenda/tematicas.html",
        tematicas=lista,
        empresas=EMPRESAS,
        tipos=TIPOS,
    )


@agenda_bp.route("/tematicas/nueva", methods=["POST"])
@login_required
def nueva_tematica():
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        flash("El nombre es obligatorio.", "danger")
        return redirect(url_for("agenda.tematicas"))

    t = Tematica(
        nombre      = nombre,
        descripcion = request.form.get("descripcion", "").strip(),
        empresa     = request.form.get("empresa", "ambas"),
        tipo        = request.form.get("tipo", "otro"),
        color       = request.form.get("color", "#6B7280"),
    )
    db.session.add(t)
    db.session.commit()
    flash(f'Temática "{t.nombre}" creada.', "success")
    return redirect(url_for("agenda.tematicas"))


@agenda_bp.route("/tematicas/<int:id>/editar", methods=["POST"])
@login_required
def editar_tematica(id):
    t = Tematica.query.get_or_404(id)
    nombre = request.form.get("nombre", "").strip()
    if not nombre:
        flash("El nombre es obligatorio.", "danger")
        return redirect(url_for("agenda.tematicas"))

    t.nombre      = nombre
    t.descripcion = request.form.get("descripcion", "").strip()
    t.empresa     = request.form.get("empresa", "ambas")
    t.tipo        = request.form.get("tipo", "otro")
    t.color       = request.form.get("color", "#6B7280")
    t.activo      = request.form.get("activo") == "1"
    db.session.commit()
    flash(f'Temática "{t.nombre}" actualizada.', "success")
    return redirect(url_for("agenda.tematicas"))


@agenda_bp.route("/tematicas/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar_tematica(id):
    t = Tematica.query.get_or_404(id)
    nombre = t.nombre
    db.session.delete(t)
    db.session.commit()
    flash(f'Temática "{nombre}" eliminada.', "success")
    return redirect(url_for("agenda.tematicas"))


# ── Helper ────────────────────────────────────────────────────────

def _render_form(entrada, tematicas, prefill=None):
    return render_template(
        "agenda/entrada_form.html",
        entrada   = entrada,
        tematicas = tematicas,
        empresas  = EMPRESAS,
        tipos     = TIPOS,
        redes     = REDES,
        estados   = ESTADOS,
        prefill   = prefill or {},
    )
