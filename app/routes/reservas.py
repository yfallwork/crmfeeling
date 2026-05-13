import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required
from app.extensions import db
from app.models.reserva import Reserva, ESTADOS
from app.models.cliente import Cliente
from app.models.experiencia import TipoExperiencia

reservas_bp = Blueprint("reservas", __name__)


@reservas_bp.route("/")
@login_required
def lista():
    estado = request.args.get("estado", "")
    tipo_id = request.args.get("tipo_id", "", type=int)
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    query = Reserva.query.join(Cliente).join(TipoExperiencia)

    if estado:
        query = query.filter(Reserva.estado == estado)
    if tipo_id:
        query = query.filter(Reserva.tipo_experiencia_id == tipo_id)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Cliente.nombre.ilike(like), Cliente.email.ilike(like))
        )

    reservas = query.order_by(Reserva.fecha_disfrute.asc().nullslast()).paginate(
        page=page, per_page=25, error_out=False
    )
    tipos = TipoExperiencia.query.filter_by(activo=True).all()
    return render_template(
        "reservas/lista.html",
        reservas=reservas,
        tipos=tipos,
        estados=ESTADOS,
        estado=estado,
        tipo_id=tipo_id,
        q=q,
    )


@reservas_bp.route("/exportar")
@login_required
def exportar():
    estado  = request.args.get("estado", "")
    tipo_id = request.args.get("tipo_id", "", type=int)
    q       = request.args.get("q", "").strip()

    query = Reserva.query.join(Cliente).join(TipoExperiencia)
    if estado:
        query = query.filter(Reserva.estado == estado)
    if tipo_id:
        query = query.filter(Reserva.tipo_experiencia_id == tipo_id)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Cliente.nombre.ilike(like), Cliente.email.ilike(like)))
    reservas = query.order_by(Reserva.fecha_disfrute.asc().nullslast()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "ID", "WC_Order", "Cliente", "Email", "Telefono",
        "Experiencia", "Variante", "Fecha_compra", "Fecha_disfrute",
        "Horario", "Estado", "Precio_EUR",
    ])
    for r in reservas:
        writer.writerow([
            r.id, r.woo_order_id or "",
            r.cliente.nombre_completo, r.cliente.email, r.cliente.telefono,
            r.tipo_experiencia.nombre, r.variante or "",
            r.fecha_compra.strftime("%d/%m/%Y") if r.fecha_compra else "",
            r.fecha_disfrute.strftime("%d/%m/%Y %H:%M") if r.fecha_disfrute else "",
            r.horario or "", r.estado,
            f"{r.precio:.2f}".replace(".", ","),
        ])

    return Response(
        "﻿" + output.getvalue(),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=reservas.csv"},
    )


@reservas_bp.route("/nueva", methods=["GET", "POST"])
@login_required
def nueva():
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    tipos = TipoExperiencia.query.filter_by(activo=True).all()

    if request.method == "POST":
        cliente_id = request.form.get("cliente_id", type=int)
        tipo_id = request.form.get("tipo_experiencia_id", type=int)
        fecha_disfrute_str = request.form.get("fecha_disfrute", "").strip()
        fecha_compra_str = request.form.get("fecha_compra", "").strip()

        fecha_disfrute = None
        if fecha_disfrute_str:
            try:
                fecha_disfrute = datetime.strptime(fecha_disfrute_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                try:
                    fecha_disfrute = datetime.strptime(fecha_disfrute_str, "%Y-%m-%d")
                except ValueError:
                    pass

        fecha_compra = datetime.utcnow()
        if fecha_compra_str:
            try:
                fecha_compra = datetime.strptime(fecha_compra_str, "%Y-%m-%d")
            except ValueError:
                pass

        reserva = Reserva(
            cliente_id=cliente_id,
            tipo_experiencia_id=tipo_id,
            fecha_compra=fecha_compra,
            fecha_disfrute=fecha_disfrute,
            estado=request.form.get("estado", "pendiente"),
            precio=float(request.form.get("precio", 0) or 0),
            notas=request.form.get("notas", "").strip(),
        )
        db.session.add(reserva)
        db.session.commit()
        flash("Reserva creada correctamente.", "success")
        return redirect(url_for("reservas.detalle", id=reserva.id))

    cliente_id = request.args.get("cliente_id", type=int)
    return render_template(
        "reservas/form.html",
        reserva=None,
        clientes=clientes,
        tipos=tipos,
        estados=ESTADOS,
        cliente_id_preselecto=cliente_id,
    )


@reservas_bp.route("/<int:id>")
@login_required
def detalle(id):
    reserva = Reserva.query.get_or_404(id)
    return render_template("reservas/detalle.html", reserva=reserva, estados=ESTADOS)


@reservas_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    reserva = Reserva.query.get_or_404(id)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    tipos = TipoExperiencia.query.filter_by(activo=True).all()

    if request.method == "POST":
        fecha_disfrute_str = request.form.get("fecha_disfrute", "").strip()
        reserva.fecha_disfrute = None
        if fecha_disfrute_str:
            try:
                reserva.fecha_disfrute = datetime.strptime(fecha_disfrute_str, "%Y-%m-%dT%H:%M")
            except ValueError:
                try:
                    reserva.fecha_disfrute = datetime.strptime(fecha_disfrute_str, "%Y-%m-%d")
                except ValueError:
                    pass

        reserva.cliente_id = request.form.get("cliente_id", type=int)
        reserva.tipo_experiencia_id = request.form.get("tipo_experiencia_id", type=int)
        reserva.estado = request.form.get("estado", reserva.estado)
        reserva.precio = float(request.form.get("precio", reserva.precio) or 0)
        reserva.notas = request.form.get("notas", "").strip()
        db.session.commit()
        flash("Reserva actualizada correctamente.", "success")
        return redirect(url_for("reservas.detalle", id=reserva.id))

    return render_template(
        "reservas/form.html",
        reserva=reserva,
        clientes=clientes,
        tipos=tipos,
        estados=ESTADOS,
        cliente_id_preselecto=reserva.cliente_id,
    )


@reservas_bp.route("/<int:id>/estado", methods=["POST"])
@login_required
def cambiar_estado(id):
    reserva = Reserva.query.get_or_404(id)
    nuevo_estado = request.form.get("estado")
    if nuevo_estado in ESTADOS:
        reserva.estado = nuevo_estado
        db.session.commit()
        flash(f"Estado cambiado a {nuevo_estado}.", "success")
    return redirect(request.referrer or url_for("reservas.detalle", id=id))


@reservas_bp.route("/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar(id):
    reserva = Reserva.query.get_or_404(id)
    db.session.delete(reserva)
    db.session.commit()
    flash("Reserva eliminada.", "info")
    return redirect(url_for("reservas.lista"))
