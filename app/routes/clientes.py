import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required
from app.extensions import db
from app.models.cliente import Cliente
from app.models.reserva import Reserva

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
        flash(f"Cliente {cliente.nombre_completo} creado correctamente.", "success")
        return redirect(url_for("clientes.detalle", id=cliente.id))

    return render_template("clientes/form.html", cliente=None, datos={})


@clientes_bp.route("/<int:id>")
@login_required
def detalle(id):
    cliente = Cliente.query.get_or_404(id)
    reservas = cliente.reservas.order_by(Reserva.fecha_compra.desc()).all()
    return render_template("clientes/detalle.html", cliente=cliente, reservas=reservas)


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
    clientes = query.order_by(Cliente.creado_en.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Nombre", "Apellido", "Email", "Telefono",
                     "DNI", "Origen", "Total_reservas", "Alta"])
    for c in clientes:
        writer.writerow([
            c.id, c.nombre, c.apellido, c.email, c.telefono,
            c.dni, c.fuente, c.total_reservas,
            c.creado_en.strftime("%d/%m/%Y") if c.creado_en else "",
        ])

    return Response(
        "﻿" + output.getvalue(),   # BOM para Excel
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=clientes.csv"},
    )


@clientes_bp.route("/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar(id):
    cliente = Cliente.query.get_or_404(id)
    nombre = cliente.nombre_completo
    db.session.delete(cliente)
    db.session.commit()
    flash(f"Cliente {nombre} eliminado.", "info")
    return redirect(url_for("clientes.lista"))
