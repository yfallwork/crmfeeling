import csv
import io
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required
from app.extensions import db
from app.models.reserva import Reserva, ESTADOS
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.experiencia import TipoExperiencia
from app.services.log_service import registrar_log

reservas_bp = Blueprint("reservas", __name__)


SORT_COLUMNS = {
    "id":             Reserva.id,
    "cliente":        Cliente.nombre,
    "fecha_compra":   Reserva.fecha_compra,
    "fecha_disfrute": Reserva.fecha_disfrute,
    "estado":         Reserva.estado,
    "precio":         Reserva.precio,
    "woo":            Reserva.woo_order_id,
}


def _base_query():
    return (
        Reserva.query
        .outerjoin(Cliente, Reserva.cliente_id == Cliente.id)
        .outerjoin(Empresa, Reserva.empresa_id == Empresa.id)
        .join(TipoExperiencia, Reserva.tipo_experiencia_id == TipoExperiencia.id)
    )


@reservas_bp.route("/")
@login_required
def lista():
    estado  = request.args.get("estado", "")
    tipo_id = request.args.get("tipo_id", "", type=int)
    origen  = request.args.get("origen", "")   # "" | "individual" | "teambuilding"
    q       = request.args.get("q", "").strip()
    page    = request.args.get("page", 1, type=int)
    sort    = request.args.get("sort", "fecha_disfrute")
    dir_    = request.args.get("dir", "asc")

    if sort not in SORT_COLUMNS:
        sort = "fecha_disfrute"
    if dir_ not in ("asc", "desc"):
        dir_ = "asc"

    query = _base_query()

    if origen == "individual":
        query = query.filter(Reserva.cliente_id.isnot(None))
    elif origen == "teambuilding":
        query = query.filter(Reserva.empresa_id.isnot(None))

    if estado:
        query = query.filter(Reserva.estado == estado)
    if tipo_id:
        query = query.filter(Reserva.tipo_experiencia_id == tipo_id)
    if q:
        like = f"%{q}%"
        if origen == "teambuilding":
            query = query.filter(Empresa.nombre.ilike(like))
        elif origen == "individual":
            query = query.filter(db.or_(
                Cliente.nombre.ilike(like),
                Cliente.email.ilike(like),
            ))
        else:
            query = query.filter(db.or_(
                Cliente.nombre.ilike(like),
                Cliente.email.ilike(like),
                Empresa.nombre.ilike(like),
            ))

    col = SORT_COLUMNS[sort]
    order = col.asc().nullslast() if dir_ == "asc" else col.desc().nullslast()
    reservas = query.order_by(order).paginate(page=page, per_page=25, error_out=False)

    tipos = TipoExperiencia.query.filter_by(activo=True).all()
    return render_template(
        "reservas/lista.html",
        reservas=reservas,
        tipos=tipos,
        estados=ESTADOS,
        estado=estado,
        tipo_id=tipo_id,
        origen=origen,
        q=q,
        sort=sort,
        dir=dir_,
    )


@reservas_bp.route("/exportar")
@login_required
def exportar():
    estado  = request.args.get("estado", "")
    tipo_id = request.args.get("tipo_id", "", type=int)
    origen  = request.args.get("origen", "")
    q       = request.args.get("q", "").strip()

    query = _base_query()
    if origen == "individual":
        query = query.filter(Reserva.cliente_id.isnot(None))
    elif origen == "teambuilding":
        query = query.filter(Reserva.empresa_id.isnot(None))
    if estado:
        query = query.filter(Reserva.estado == estado)
    if tipo_id:
        query = query.filter(Reserva.tipo_experiencia_id == tipo_id)
    if q:
        like = f"%{q}%"
        if origen == "teambuilding":
            query = query.filter(Empresa.nombre.ilike(like))
        elif origen == "individual":
            query = query.filter(db.or_(Cliente.nombre.ilike(like), Cliente.email.ilike(like)))
        else:
            query = query.filter(db.or_(
                Cliente.nombre.ilike(like),
                Cliente.email.ilike(like),
                Empresa.nombre.ilike(like),
            ))
    reservas = query.order_by(Reserva.fecha_disfrute.asc().nullslast()).all()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow([
        "ID", "WC_Order", "Tipo", "Nombre", "Email", "Telefono",
        "Experiencia", "Variante", "Fecha_compra", "Fecha_disfrute",
        "Horario", "Estado", "Precio_EUR", "Participantes",
    ])
    for r in reservas:
        if r.es_teambuilding:
            nombre   = r.empresa.nombre if r.empresa else ""
            email    = r.empresa.email if r.empresa else ""
            telefono = r.empresa.telefono if r.empresa else ""
            tipo_str = "TeamBuilding"
            partic   = r.num_participantes or ""
        else:
            nombre   = r.cliente.nombre_completo if r.cliente else ""
            email    = r.cliente.email if r.cliente else ""
            telefono = r.cliente.telefono if r.cliente else ""
            tipo_str = "Individual"
            partic   = ""
        writer.writerow([
            r.id, r.woo_order_id or "",
            tipo_str, nombre, email, telefono,
            r.tipo_experiencia.nombre, r.variante or "",
            r.fecha_compra.strftime("%d/%m/%Y") if r.fecha_compra else "",
            r.fecha_disfrute.strftime("%d/%m/%Y %H:%M") if r.fecha_disfrute else "",
            r.horario or "", r.estado,
            f"{r.precio:.2f}".replace(".", ","),
            partic,
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
    empresas = Empresa.query.filter_by(activo=True).order_by(Empresa.nombre).all()
    tipos = TipoExperiencia.query.filter_by(activo=True).all()

    if request.method == "POST":
        tipo_reserva = request.form.get("tipo_reserva", "individual")

        if tipo_reserva == "teambuilding":
            empresa_id = request.form.get("empresa_id", type=int)
            cliente_id = None
        else:
            cliente_id = request.form.get("cliente_id", type=int)
            empresa_id = None

        tipo_id = request.form.get("tipo_experiencia_id", type=int)
        fecha_disfrute_str = request.form.get("fecha_disfrute", "").strip()
        fecha_compra_str   = request.form.get("fecha_compra", "").strip()

        fecha_disfrute = None
        if fecha_disfrute_str:
            for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
                try:
                    fecha_disfrute = datetime.strptime(fecha_disfrute_str, fmt)
                    break
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
            empresa_id=empresa_id,
            tipo_experiencia_id=tipo_id,
            fecha_compra=fecha_compra,
            fecha_disfrute=fecha_disfrute,
            estado=request.form.get("estado", "pendiente"),
            precio=float(request.form.get("precio", 0) or 0),
            notas=request.form.get("notas", "").strip(),
            num_participantes=int(request.form.get("num_participantes") or 1),
            nombre_grupo=request.form.get("nombre_grupo", "").strip(),
        )
        db.session.add(reserva)
        db.session.commit()
        registrar_log("crear", "reserva", reserva.id,
                      f"Reserva creada: {reserva.nombre_reservante} - {reserva.tipo_experiencia.nombre}")
        from app.services.trigger_engine import disparar_trigger
        # Quitar etiquetas temporales de inactividad si la entidad vuelve a reservar
        if reserva.estado in ("pendiente", "reservado"):
            try:
                from app.services.temporal_tags import quitar_tags_temporales_por_reserva
                if cliente_id:
                    quitar_tags_temporales_por_reserva("cliente", cliente_id)
                elif empresa_id:
                    quitar_tags_temporales_por_reserva("empresa", empresa_id)
            except Exception:
                pass
            if cliente_id:
                disparar_trigger("crm.reserva.creada", "cliente", cliente_id)
        elif reserva.estado == "disfrutado":
            if cliente_id:
                disparar_trigger("crm.reserva.disfrutada", "cliente", cliente_id)
            elif empresa_id:
                disparar_trigger("crm.reserva.disfrutada", "empresa", empresa_id)
        # Re-evaluar criterios VIP del cliente
        if cliente_id:
            try:
                from app.services.vip_criterio import evaluar_cliente_vip
                evaluar_cliente_vip(cliente_id)
            except Exception:
                pass
        flash("Reserva creada correctamente.", "success")
        return redirect(url_for("reservas.detalle", id=reserva.id))

    cliente_id_pre = request.args.get("cliente_id", type=int)
    return render_template(
        "reservas/form.html",
        reserva=None,
        clientes=clientes,
        empresas=empresas,
        tipos=tipos,
        estados=ESTADOS,
        cliente_id_preselecto=cliente_id_pre,
    )


@reservas_bp.route("/<int:id>")
@login_required
def detalle(id):
    reserva = Reserva.query.get_or_404(id)
    return render_template("reservas/detalle.html", reserva=reserva, estados=ESTADOS)


@reservas_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    reserva  = Reserva.query.get_or_404(id)
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    empresas = Empresa.query.filter_by(activo=True).order_by(Empresa.nombre).all()
    tipos    = TipoExperiencia.query.filter_by(activo=True).all()

    if request.method == "POST":
        tipo_reserva = request.form.get("tipo_reserva", "individual")

        if tipo_reserva == "teambuilding":
            reserva.empresa_id       = request.form.get("empresa_id", type=int)
            reserva.cliente_id       = None
            reserva.num_participantes = int(request.form.get("num_participantes") or 1)
            reserva.nombre_grupo     = request.form.get("nombre_grupo", "").strip()
        else:
            reserva.cliente_id  = request.form.get("cliente_id", type=int)
            reserva.empresa_id  = None

        fecha_disfrute_str = request.form.get("fecha_disfrute", "").strip()
        reserva.fecha_disfrute = None
        if fecha_disfrute_str:
            for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d"):
                try:
                    reserva.fecha_disfrute = datetime.strptime(fecha_disfrute_str, fmt)
                    break
                except ValueError:
                    pass

        reserva.tipo_experiencia_id = request.form.get("tipo_experiencia_id", type=int)
        reserva.estado = request.form.get("estado", reserva.estado)
        reserva.precio = float(request.form.get("precio", reserva.precio) or 0)
        reserva.notas  = request.form.get("notas", "").strip()
        db.session.commit()
        registrar_log("editar", "reserva", reserva.id,
                      f"Reserva editada: {reserva.nombre_reservante} - {reserva.estado}")
        flash("Reserva actualizada correctamente.", "success")
        return redirect(url_for("reservas.detalle", id=reserva.id))

    return render_template(
        "reservas/form.html",
        reserva=reserva,
        clientes=clientes,
        empresas=empresas,
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
        estado_anterior = reserva.estado
        reserva.estado  = nuevo_estado
        db.session.commit()
        registrar_log("cambiar_estado", "reserva", id,
                      f"Estado: {estado_anterior} -> {nuevo_estado} ({reserva.nombre_reservante})")
        from app.services.trigger_engine import disparar_trigger
        # Si la reserva pasa a activa, quitar etiquetas de inactividad
        if nuevo_estado in ("pendiente", "reservado") and estado_anterior == "cancelado":
            try:
                from app.services.temporal_tags import quitar_tags_temporales_por_reserva
                if reserva.cliente_id:
                    quitar_tags_temporales_por_reserva("cliente", reserva.cliente_id)
                elif reserva.empresa_id:
                    quitar_tags_temporales_por_reserva("empresa", reserva.empresa_id)
            except Exception:
                pass
            if reserva.cliente_id:
                disparar_trigger("crm.reserva.creada", "cliente", reserva.cliente_id)
        # Disparar disfrutada → experiencia_realizada / evento_empresa_realizado
        if nuevo_estado == "disfrutado":
            if reserva.cliente_id:
                disparar_trigger("crm.reserva.disfrutada", "cliente", reserva.cliente_id)
            elif reserva.empresa_id:
                disparar_trigger("crm.reserva.disfrutada", "empresa", reserva.empresa_id)
        # Re-evaluar VIP al cambiar a disfrutado (suma real de gasto)
        if reserva.cliente_id and nuevo_estado in ("disfrutado", "reservado", "cancelado"):
            try:
                from app.services.vip_criterio import evaluar_cliente_vip
                evaluar_cliente_vip(reserva.cliente_id)
            except Exception:
                pass
        # Re-evaluar Gran Cuenta al cambiar estado de reserva TB
        if reserva.empresa_id and nuevo_estado in ("disfrutado", "reservado", "cancelado"):
            try:
                from app.services.gran_cuenta_criterio import evaluar_empresa_gran_cuenta
                evaluar_empresa_gran_cuenta(reserva.empresa_id)
            except Exception:
                pass
        flash(f"Estado cambiado a {nuevo_estado}.", "success")
    return redirect(request.referrer or url_for("reservas.detalle", id=id))


@reservas_bp.route("/<int:id>/eliminar", methods=["POST"])
@login_required
def eliminar(id):
    reserva = Reserva.query.get_or_404(id)
    detalle = f"Reserva eliminada: {reserva.nombre_reservante} - {reserva.tipo_experiencia.nombre}"
    db.session.delete(reserva)
    db.session.commit()
    registrar_log("eliminar", "reserva", id, detalle)
    flash("Reserva eliminada.", "info")
    return redirect(url_for("reservas.lista"))
