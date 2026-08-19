from datetime import datetime

from flask import Blueprint, render_template, request, abort

from app.extensions import db
from app.models.reserva import Reserva

seguro_bp = Blueprint("seguro", __name__)


@seguro_bp.route("/<token>", methods=["GET", "POST"])
def formulario(token):
    reserva = Reserva.query.filter_by(token_seguro=token).first()
    if not reserva:
        abort(404)

    # Una vez rellenado, el enlace queda bloqueado: no se puede volver a
    # editar desde aquí (si hace falta corregir algo, lo hace un admin
    # desde la propia ficha de la reserva en el CRM).
    ya_bloqueado = reserva.tiene_datos_seguro
    guardado = False
    error = None

    if request.method == "POST" and not ya_bloqueado:
        nombre = request.form.get("piloto_nombre", "").strip()
        primer_apellido = request.form.get("piloto_primer_apellido", "").strip()
        dni = request.form.get("piloto_dni", "").strip()
        fnac_str = request.form.get("piloto_fecha_nacimiento", "").strip()

        if not nombre or not primer_apellido or not dni or not fnac_str:
            error = "Nombre, primer apellido, DNI y fecha de nacimiento son obligatorios."
        else:
            fecha_nacimiento = None
            try:
                fecha_nacimiento = datetime.strptime(fnac_str, "%Y-%m-%d").date()
            except ValueError:
                error = "La fecha de nacimiento no es válida."

            if not error:
                reserva.piloto_nombre = nombre
                reserva.piloto_primer_apellido = primer_apellido
                reserva.piloto_segundo_apellido = request.form.get("piloto_segundo_apellido", "").strip()
                reserva.piloto_dni = dni
                reserva.piloto_fecha_nacimiento = fecha_nacimiento
                db.session.commit()
                guardado = True
                ya_bloqueado = True

    return render_template("seguro_publico/formulario.html", reserva=reserva,
                            guardado=guardado, error=error, bloqueado=ya_bloqueado)
