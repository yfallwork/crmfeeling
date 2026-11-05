"""
Sección "Mecánica" — independiente de AutoClub y de Experiencias, pero de la
mano con ellas: comparte el mismo modelo Vehiculo (y por tanto los mismos
registros) que ya usa AutoClub en /autoclub/vehiculos, para no duplicar
datos de un vehículo que es una única entidad física vista desde dos
ángulos distintos (gestión del club vs. mecánica/taller).

Primer apartado: CRUD de vehículos. Los campos y el flujo son deliberadamente
los mismos que en autoclub/vehiculos (mismo modelo, mismos atributos).
"""
from datetime import date as _date

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.vehiculo import Vehiculo
from app.models.piloto import Piloto
from app.models.mantenimiento_vehiculo import MantenimientoVehiculo, CATALOGO_OPERACIONES, OPERACIONES_LABELS
from app.services.log_service import registrar_log

mecanica_bp = Blueprint("mecanica", __name__)


def _parse_date(raw):
    if not raw:
        return None
    try:
        return _date.fromisoformat(raw.strip())
    except ValueError:
        return None


def _parse_int(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _parse_float(raw):
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


@mecanica_bp.route("/vehiculos")
@login_required
def vehiculos_lista():
    q    = request.args.get("q", "").strip()
    tipo = request.args.get("tipo_vehiculo", "")
    page = request.args.get("page", 1, type=int)

    query = Vehiculo.query
    if tipo:
        query = query.filter_by(tipo_vehiculo=tipo)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            Vehiculo.cc_chasis_marca.ilike(like),
            Vehiculo.cc_chasis_modelo.ilike(like),
            Vehiculo.div_marca.ilike(like),
            Vehiculo.div_modelo.ilike(like),
            Vehiculo.dorsal.ilike(like),
        ))

    vehiculos = query.order_by(Vehiculo.creado_en.desc()).paginate(page=page, per_page=25, error_out=False)
    return render_template("mecanica/vehiculos/lista.html",
                           vehiculos=vehiculos, q=q, tipo_vehiculo=tipo)


@mecanica_bp.route("/vehiculos/nuevo", methods=["GET", "POST"])
@login_required
def vehiculos_nuevo():
    pilotos = Piloto.query.filter_by(activo=True).order_by(Piloto.nombre.asc()).all()
    piloto_id_pre = request.args.get("piloto_id", type=int)
    if request.method == "POST":
        v = Vehiculo(
            tipo_vehiculo=request.form.get("tipo_vehiculo", "car_cross"),
            categoria=request.form.get("categoria", "").strip(),
            cc_chasis_marca=request.form.get("cc_chasis_marca", "").strip(),
            cc_chasis_modelo=request.form.get("cc_chasis_modelo", "").strip(),
            cc_num_chasis=request.form.get("cc_num_chasis", "").strip(),
            cc_pasaporte_rfeda=request.form.get("cc_pasaporte_rfeda", "").strip(),
            cc_pasaporte_autonomico=request.form.get("cc_pasaporte_autonomico", "").strip(),
            cc_num_homologacion=request.form.get("cc_num_homologacion", "").strip(),
            cc_motor_marca=request.form.get("cc_motor_marca", "").strip(),
            cc_motor_modelo=request.form.get("cc_motor_modelo", "").strip(),
            cc_motor_anio=request.form.get("cc_motor_anio", "").strip(),
            cc_cilindrada=_parse_int(request.form.get("cc_cilindrada")),
            cc_num_motor=request.form.get("cc_num_motor", "").strip(),
            div_marca=request.form.get("div_marca", "").strip(),
            div_modelo=request.form.get("div_modelo", "").strip(),
            div_num_bastidor=request.form.get("div_num_bastidor", "").strip(),
            div_pasaporte_rfeda=request.form.get("div_pasaporte_rfeda", "").strip(),
            div_pasaporte_autonomico=request.form.get("div_pasaporte_autonomico", "").strip(),
            div_homologacion=request.form.get("div_homologacion", "").strip(),
            div_motor_disposicion=request.form.get("div_motor_disposicion", "").strip(),
            div_motor_aspiracion=request.form.get("div_motor_aspiracion", "").strip(),
            div_cilindrada=_parse_int(request.form.get("div_cilindrada")),
            div_factor_correccion=_parse_float(request.form.get("div_factor_correccion")),
            div_traccion=request.form.get("div_traccion", "").strip(),
            arnes_marca=request.form.get("arnes_marca", "").strip(),
            arnes_homologacion=request.form.get("arnes_homologacion", "").strip(),
            arnes_caducidad=_parse_date(request.form.get("arnes_caducidad")),
            asiento_marca=request.form.get("asiento_marca", "").strip(),
            asiento_homologacion=request.form.get("asiento_homologacion", "").strip(),
            asiento_caducidad=_parse_date(request.form.get("asiento_caducidad")),
            extincion_marca=request.form.get("extincion_marca", "").strip(),
            extincion_tipo=request.form.get("extincion_tipo", "").strip(),
            extincion_revision=_parse_date(request.form.get("extincion_revision")),
            deposito_marca=request.form.get("deposito_marca", "").strip(),
            deposito_caducidad=_parse_date(request.form.get("deposito_caducidad")),
            red_estado=request.form.get("red_estado", "").strip(),
            red_homologacion=request.form.get("red_homologacion", "").strip(),
            dorsal=request.form.get("dorsal", "").strip(),
            num_transponder=request.form.get("num_transponder", "").strip(),
            piloto_id=_parse_int(request.form.get("piloto_id")),
        )
        db.session.add(v)
        db.session.commit()
        registrar_log("crear", "vehiculo", v.id, f"Vehículo creado (desde Mecánica): {v.nombre_display}")
        flash(f"Vehículo {v.nombre_display} creado correctamente.", "success")
        return redirect(url_for("mecanica.vehiculos_detalle", id=v.id))
    return render_template("mecanica/vehiculos/form.html", vehiculo=None,
                           pilotos=pilotos, piloto_id_pre=piloto_id_pre)


@mecanica_bp.route("/vehiculos/<int:id>")
@login_required
def vehiculos_detalle(id):
    vehiculo = Vehiculo.query.get_or_404(id)
    mantenimientos = vehiculo.mantenimientos.all()
    coste_total = sum(m.coste or 0 for m in mantenimientos)
    ultimas_vueltas = max((m.vueltas for m in mantenimientos if m.vueltas is not None), default=None)
    proximo = next((m for m in mantenimientos if m.proxima_fecha or m.proximas_vueltas is not None), None)
    proximo_vencido = bool(proximo and (
        (proximo.proxima_fecha and proximo.proxima_fecha < _date.today())
        or (proximo.proximas_vueltas is not None and ultimas_vueltas is not None
            and ultimas_vueltas >= proximo.proximas_vueltas)
    ))
    return render_template("mecanica/vehiculos/detalle.html", vehiculo=vehiculo,
                           mantenimientos=mantenimientos, coste_total=coste_total,
                           ultimas_vueltas=ultimas_vueltas,
                           proximo=proximo, proximo_vencido=proximo_vencido,
                           hoy=_date.today())


@mecanica_bp.route("/vehiculos/<int:id>/editar", methods=["GET", "POST"])
@login_required
def vehiculos_editar(id):
    vehiculo = Vehiculo.query.get_or_404(id)
    pilotos = Piloto.query.filter_by(activo=True).order_by(Piloto.nombre.asc()).all()
    if request.method == "POST":
        vehiculo.tipo_vehiculo = request.form.get("tipo_vehiculo", "car_cross")
        vehiculo.categoria = request.form.get("categoria", "").strip()
        vehiculo.cc_chasis_marca = request.form.get("cc_chasis_marca", "").strip()
        vehiculo.cc_chasis_modelo = request.form.get("cc_chasis_modelo", "").strip()
        vehiculo.cc_num_chasis = request.form.get("cc_num_chasis", "").strip()
        vehiculo.cc_pasaporte_rfeda = request.form.get("cc_pasaporte_rfeda", "").strip()
        vehiculo.cc_pasaporte_autonomico = request.form.get("cc_pasaporte_autonomico", "").strip()
        vehiculo.cc_num_homologacion = request.form.get("cc_num_homologacion", "").strip()
        vehiculo.cc_motor_marca = request.form.get("cc_motor_marca", "").strip()
        vehiculo.cc_motor_modelo = request.form.get("cc_motor_modelo", "").strip()
        vehiculo.cc_motor_anio = request.form.get("cc_motor_anio", "").strip()
        vehiculo.cc_cilindrada = _parse_int(request.form.get("cc_cilindrada"))
        vehiculo.cc_num_motor = request.form.get("cc_num_motor", "").strip()
        vehiculo.div_marca = request.form.get("div_marca", "").strip()
        vehiculo.div_modelo = request.form.get("div_modelo", "").strip()
        vehiculo.div_num_bastidor = request.form.get("div_num_bastidor", "").strip()
        vehiculo.div_pasaporte_rfeda = request.form.get("div_pasaporte_rfeda", "").strip()
        vehiculo.div_pasaporte_autonomico = request.form.get("div_pasaporte_autonomico", "").strip()
        vehiculo.div_homologacion = request.form.get("div_homologacion", "").strip()
        vehiculo.div_motor_disposicion = request.form.get("div_motor_disposicion", "").strip()
        vehiculo.div_motor_aspiracion = request.form.get("div_motor_aspiracion", "").strip()
        vehiculo.div_cilindrada = _parse_int(request.form.get("div_cilindrada"))
        vehiculo.div_factor_correccion = _parse_float(request.form.get("div_factor_correccion"))
        vehiculo.div_traccion = request.form.get("div_traccion", "").strip()
        vehiculo.arnes_marca = request.form.get("arnes_marca", "").strip()
        vehiculo.arnes_homologacion = request.form.get("arnes_homologacion", "").strip()
        vehiculo.arnes_caducidad = _parse_date(request.form.get("arnes_caducidad"))
        vehiculo.asiento_marca = request.form.get("asiento_marca", "").strip()
        vehiculo.asiento_homologacion = request.form.get("asiento_homologacion", "").strip()
        vehiculo.asiento_caducidad = _parse_date(request.form.get("asiento_caducidad"))
        vehiculo.extincion_marca = request.form.get("extincion_marca", "").strip()
        vehiculo.extincion_tipo = request.form.get("extincion_tipo", "").strip()
        vehiculo.extincion_revision = _parse_date(request.form.get("extincion_revision"))
        vehiculo.deposito_marca = request.form.get("deposito_marca", "").strip()
        vehiculo.deposito_caducidad = _parse_date(request.form.get("deposito_caducidad"))
        vehiculo.red_estado = request.form.get("red_estado", "").strip()
        vehiculo.red_homologacion = request.form.get("red_homologacion", "").strip()
        vehiculo.dorsal = request.form.get("dorsal", "").strip()
        vehiculo.num_transponder = request.form.get("num_transponder", "").strip()
        vehiculo.piloto_id = _parse_int(request.form.get("piloto_id"))
        db.session.commit()
        registrar_log("editar", "vehiculo", vehiculo.id, f"Vehículo editado (desde Mecánica): {vehiculo.nombre_display}")
        flash("Vehículo actualizado correctamente.", "success")
        return redirect(url_for("mecanica.vehiculos_detalle", id=vehiculo.id))
    return render_template("mecanica/vehiculos/form.html", vehiculo=vehiculo, pilotos=pilotos, piloto_id_pre=None)


@mecanica_bp.route("/vehiculos/<int:id>/eliminar", methods=["POST"])
@login_required
def vehiculos_eliminar(id):
    vehiculo = Vehiculo.query.get_or_404(id)
    nombre = vehiculo.nombre_display
    db.session.delete(vehiculo)
    db.session.commit()
    registrar_log("eliminar", "vehiculo", id, f"Vehículo eliminado (desde Mecánica): {nombre}")
    flash(f"Vehículo {nombre} eliminado.", "success")
    return redirect(url_for("mecanica.vehiculos_lista"))


# ══════════════════════════════════════════════════════════════════════════
#  MANTENIMIENTOS — registro histórico por vehículo. El desgaste se controla
#  por número de vueltas (contador propio del equipo), no por horas ni km.
# ══════════════════════════════════════════════════════════════════════════

def _leer_entero(form, campo, errores):
    raw = (form.get(campo) or "").strip().replace(".", "").replace(" ", "")
    if not raw:
        return None
    valor = _parse_int(raw)
    if valor is None or valor < 0:
        errores[campo] = "Debe ser un número entero positivo."
    return valor


def _leer_form_mantenimiento(form, errores):
    fecha = _parse_date(form.get("fecha"))
    if not fecha:
        errores["fecha"] = "Indica la fecha del mantenimiento."

    # Sin duplicados y en el orden del catálogo, para que se lean igual siempre.
    orden = list(OPERACIONES_LABELS)
    operaciones = sorted({k for k in form.getlist("operaciones") if k in OPERACIONES_LABELS}, key=orden.index)
    if not operaciones:
        errores["operaciones"] = "Marca al menos una operación realizada."

    descripcion = form.get("descripcion", "").strip()
    if operaciones == ["otro"] and not descripcion:
        errores["descripcion"] = "Describe el trabajo realizado."

    coste = None
    raw_coste = (form.get("coste") or "").strip().replace(",", ".")
    if raw_coste:
        coste = _parse_float(raw_coste)
        if coste is None or coste < 0:
            errores["coste"] = "Debe ser un número positivo."

    return {
        "fecha": fecha,
        "operaciones": ",".join(operaciones),
        "titulo": form.get("titulo", "").strip(),
        "descripcion": descripcion,
        "piezas": form.get("piezas", "").strip(),
        "realizado_por": form.get("realizado_por", "").strip(),
        "vueltas": _leer_entero(form, "vueltas", errores),
        "coste": coste,
        "proxima_fecha": _parse_date(form.get("proxima_fecha")),
        "proximas_vueltas": _leer_entero(form, "proximas_vueltas", errores),
    }


def _datos_form(form=None, m=None):
    """Valores para repoblar el formulario: desde el POST con errores o
    desde un mantenimiento existente."""
    if form is not None:
        datos = {k: form.get(k, "") for k in (
            "fecha", "titulo", "descripcion", "piezas", "realizado_por",
            "vueltas", "coste", "proxima_fecha", "proximas_vueltas")}
        datos["operaciones"] = form.getlist("operaciones")
        return datos
    if m is not None:
        return {
            "fecha": m.fecha.isoformat() if m.fecha else "",
            "operaciones": m.operaciones_lista,
            "titulo": m.titulo or "", "descripcion": m.descripcion or "",
            "piezas": m.piezas or "", "realizado_por": m.realizado_por or "",
            "vueltas": "" if m.vueltas is None else str(m.vueltas),
            "coste": "" if m.coste is None else f"{m.coste:g}",
            "proxima_fecha": m.proxima_fecha.isoformat() if m.proxima_fecha else "",
            "proximas_vueltas": "" if m.proximas_vueltas is None else str(m.proximas_vueltas),
        }
    return {"fecha": _date.today().isoformat(), "operaciones": []}


def _ultimas_vueltas(vehiculo, excluir_id=None):
    q = db.session.query(db.func.max(MantenimientoVehiculo.vueltas)).filter(
        MantenimientoVehiculo.vehiculo_id == vehiculo.id)
    if excluir_id:
        q = q.filter(MantenimientoVehiculo.id != excluir_id)
    return q.scalar()


def _render_form(vehiculo, mantenimiento, datos, errores):
    return render_template(
        "mecanica/mantenimientos/form.html", vehiculo=vehiculo, mantenimiento=mantenimiento,
        datos=datos, errores=errores, catalogo=CATALOGO_OPERACIONES,
        ultimas_vueltas=_ultimas_vueltas(vehiculo, mantenimiento.id if mantenimiento else None),
    ), (400 if errores else 200)


def _mantenimiento_de(vehiculo_id, mid):
    m = MantenimientoVehiculo.query.get_or_404(mid)
    if m.vehiculo_id != vehiculo_id:
        abort(404)
    return m


@mecanica_bp.route("/vehiculos/<int:id>/mantenimientos/nuevo", methods=["GET", "POST"])
@login_required
def mantenimiento_nuevo(id):
    vehiculo = Vehiculo.query.get_or_404(id)
    errores = {}
    if request.method == "POST":
        datos = _leer_form_mantenimiento(request.form, errores)
        if not errores:
            m = MantenimientoVehiculo(vehiculo_id=vehiculo.id, creado_por_id=current_user.id, **datos)
            db.session.add(m)
            db.session.commit()
            registrar_log("crear", "mantenimiento_vehiculo", m.id,
                          f"Mantenimiento «{m.titulo_display}» en {vehiculo.nombre_display}")
            flash("Mantenimiento registrado.", "success")
            return redirect(url_for("mecanica.vehiculos_detalle", id=vehiculo.id) + "#mantenimientos")
        flash("Revisa los campos marcados.", "danger")
        return _render_form(vehiculo, None, _datos_form(form=request.form), errores)
    return _render_form(vehiculo, None, _datos_form(), errores)


@mecanica_bp.route("/vehiculos/<int:id>/mantenimientos/<int:mid>/editar", methods=["GET", "POST"])
@login_required
def mantenimiento_editar(id, mid):
    vehiculo = Vehiculo.query.get_or_404(id)
    m = _mantenimiento_de(vehiculo.id, mid)
    errores = {}
    if request.method == "POST":
        datos = _leer_form_mantenimiento(request.form, errores)
        if not errores:
            for campo, valor in datos.items():
                setattr(m, campo, valor)
            db.session.commit()
            registrar_log("editar", "mantenimiento_vehiculo", m.id,
                          f"Mantenimiento «{m.titulo_display}» editado en {vehiculo.nombre_display}")
            flash("Mantenimiento actualizado.", "success")
            return redirect(url_for("mecanica.vehiculos_detalle", id=vehiculo.id) + "#mantenimientos")
        flash("Revisa los campos marcados.", "danger")
        return _render_form(vehiculo, m, _datos_form(form=request.form), errores)
    return _render_form(vehiculo, m, _datos_form(m=m), errores)


@mecanica_bp.route("/vehiculos/<int:id>/mantenimientos/<int:mid>/eliminar", methods=["POST"])
@login_required
def mantenimiento_eliminar(id, mid):
    vehiculo = Vehiculo.query.get_or_404(id)
    m = _mantenimiento_de(vehiculo.id, mid)
    titulo = m.titulo_display
    db.session.delete(m)
    db.session.commit()
    registrar_log("eliminar", "mantenimiento_vehiculo", mid,
                  f"Mantenimiento «{titulo}» eliminado de {vehiculo.nombre_display}")
    flash("Mantenimiento eliminado.", "success")
    return redirect(url_for("mecanica.vehiculos_detalle", id=vehiculo.id) + "#mantenimientos")
