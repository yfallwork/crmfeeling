import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
from flask_login import login_required
from app.extensions import db
from app.models.cliente import Cliente
from app.models.reserva import Reserva
from app.models.tag import Tag, ClienteTag
from app.services.log_service import registrar_log, registrar_marketing_log

clientes_bp = Blueprint("clientes", __name__)


@clientes_bp.route("/")
@login_required
def lista():
    q = request.args.get("q", "").strip()
    fuente = request.args.get("fuente", "")
    page = request.args.get("page", 1, type=int)

    query = Cliente.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Cliente.nombre.ilike(like),
                Cliente.apellido.ilike(like),
                Cliente.email.ilike(like),
                Cliente.telefono.ilike(like),
            )
        )
    if fuente:
        query = query.filter_by(fuente=fuente)

    clientes = query.order_by(Cliente.creado_en.desc()).paginate(
        page=page, per_page=25, error_out=False
    )
    return render_template("clientes/lista.html", clientes=clientes, q=q, fuente=fuente)


@clientes_bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if Cliente.query.filter_by(email=email).first():
            flash("Ya existe un cliente con ese email.", "warning")
            return render_template("clientes/form.html", cliente=None, datos=request.form)

        cliente = Cliente(
            nombre=request.form.get("nombre", "").strip(),
            apellido=request.form.get("apellido", "").strip(),
            email=email,
            telefono=request.form.get("telefono", "").strip(),
            dni=request.form.get("dni", "").strip(),
            notas=request.form.get("notas", "").strip(),
            fuente="manual",
        )
        db.session.add(cliente)
        db.session.commit()
        registrar_log("crear", "cliente", cliente.id, f"Cliente creado: {cliente.nombre_completo} ({cliente.email})")
        flash(f"Cliente {cliente.nombre_completo} creado correctamente.", "success")
        # Disparar automatizaciones de marketing para nuevo cliente
        from app.services.trigger_engine import disparar_trigger
        disparar_trigger("crm.cliente.creado", "cliente", cliente.id)
        return redirect(url_for("clientes.detalle", id=cliente.id))

    return render_template("clientes/form.html", cliente=None, datos={})


@clientes_bp.route("/<int:id>")
@login_required
def detalle(id):
    cliente = Cliente.query.get_or_404(id)
    reservas = cliente.reservas.order_by(Reserva.fecha_compra.desc()).all()
    cliente_tags = ClienteTag.query.filter_by(cliente_id=id).all()
    tag_ids_asignados = {ct.tag_id for ct in cliente_tags}
    tags_disponibles = (Tag.query
                        .filter_by(entidad="cliente", activo=True)
                        .filter(Tag.id.notin_(tag_ids_asignados))
                        .order_by(Tag.nombre).all())
    return render_template("clientes/detalle.html",
                           cliente=cliente, reservas=reservas,
                           cliente_tags=cliente_tags,
                           tags_disponibles=tags_disponibles)


@clientes_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    cliente = Cliente.query.get_or_404(id)

    if request.method == "POST":
        nuevo_email = request.form.get("email", "").strip().lower()
        existente = Cliente.query.filter_by(email=nuevo_email).first()
        if existente and existente.id != cliente.id:
            flash("Ese email ya está en uso por otro cliente.", "warning")
            return render_template("clientes/form.html", cliente=cliente, datos=request.form)

        cliente.nombre = request.form.get("nombre", "").strip()
        cliente.apellido = request.form.get("apellido", "").strip()
        cliente.email = nuevo_email
        cliente.telefono = request.form.get("telefono", "").strip()
        cliente.dni = request.form.get("dni", "").strip()
        cliente.notas = request.form.get("notas", "").strip()
        db.session.commit()
        registrar_log("editar", "cliente", cliente.id, f"Cliente editado: {cliente.nombre_completo}")
        flash("Cliente actualizado correctamente.", "success")
        return redirect(url_for("clientes.detalle", id=cliente.id))

    return render_template("clientes/form.html", cliente=cliente, datos={})


@clientes_bp.route("/exportar")
@login_required
def exportar():
    q      = request.args.get("q", "").strip()
    fuente = request.args.get("fuente", "")
    query  = Cliente.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Cliente.nombre.ilike(like), Cliente.apellido.ilike(like),
            Cliente.email.ilike(like), Cliente.telefono.ilike(like),
        ))
    if fuente:
        query = query.filter_by(fuente=fuente)
    query = query.order_by(Cliente.creado_en.desc())

    def generar_csv():
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";")

        buffer.write("﻿")  # BOM para Excel
        writer.writerow(["ID", "Nombre", "Apellido", "Email", "Telefono",
                         "DNI", "Origen", "Total_reservas", "Alta"])
        yield buffer.getvalue()
        buffer.seek(0); buffer.truncate(0)

        # yield_per evita cargar toda la tabla de clientes en memoria de golpe
        for c in query.yield_per(200):
            writer.writerow([
                c.id, c.nombre, c.apellido, c.email, c.telefono,
                c.dni, c.fuente, c.total_reservas,
                c.creado_en.strftime("%d/%m/%Y") if c.creado_en else "",
            ])
            yield buffer.getvalue()
            buffer.seek(0); buffer.truncate(0)

    return Response(
        stream_with_context(generar_csv()),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=clientes.csv"},
    )


@clientes_bp.route("/<int:id>/tags/add", methods=["POST"])
@login_required
def tag_add(id):
    cliente = Cliente.query.get_or_404(id)
    tag_id = request.form.get("tag_id", type=int)
    if tag_id and not ClienteTag.query.filter_by(cliente_id=id, tag_id=tag_id).first():
        db.session.add(ClienteTag(cliente_id=id, tag_id=tag_id, origen="manual"))
        db.session.commit()
        tag = Tag.query.get(tag_id)
        tag_slug = tag.slug if tag else str(tag_id)
        registrar_log("editar", "cliente", id, f"Etiqueta añadida: {tag_slug}")
        registrar_marketing_log(
            "tag_asignada", resultado="ok",
            tag_id=tag_id, tag_nombre=tag.nombre if tag else tag_slug,
            entidad="cliente", entidad_id=id,
            entidad_nombre=cliente.nombre_completo,
            detalle=f"Etiqueta '{tag.nombre if tag else tag_slug}' asignada manualmente",
            origen="manual",
        )
    return redirect(url_for("clientes.detalle", id=id))


@clientes_bp.route("/<int:id>/tags/remove", methods=["POST"])
@login_required
def tag_remove(id):
    cliente = Cliente.query.get_or_404(id)
    tag_id = request.form.get("tag_id", type=int)
    if tag_id:
        ct = ClienteTag.query.filter_by(cliente_id=id, tag_id=tag_id).first()
        if ct:
            tag = Tag.query.get(tag_id)
            tag_slug = tag.slug if tag else str(tag_id)
            db.session.delete(ct)
            db.session.commit()
            registrar_log("editar", "cliente", id, f"Etiqueta eliminada: {tag_slug}")
            registrar_marketing_log(
                "tag_eliminada", resultado="ok",
                tag_id=tag_id, tag_nombre=tag.nombre if tag else tag_slug,
                entidad="cliente", entidad_id=id,
                entidad_nombre=cliente.nombre_completo,
                detalle=f"Etiqueta '{tag.nombre if tag else tag_slug}' eliminada manualmente",
                origen="manual",
            )
    return redirect(url_for("clientes.detalle", id=id))


@clientes_bp.route("/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar(id):
    cliente = Cliente.query.get_or_404(id)
    nombre = cliente.nombre_completo
    db.session.delete(cliente)
    db.session.commit()
    registrar_log("eliminar", "cliente", id, f"Cliente eliminado: {nombre}")
    flash(f"Cliente {nombre} eliminado.", "info")
    return redirect(url_for("clientes.lista"))
