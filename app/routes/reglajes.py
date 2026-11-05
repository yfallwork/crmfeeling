"""
Reglajes de carcross por evento (sección Mecánica). Las rutas se registran
sobre mecanica_bp. Ver app/models/reglaje.py.
"""
import json
from datetime import date, datetime

import re

from flask import render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required

from app.extensions import db
from app.models.piloto import Piloto
from app.models.vehiculo import Vehiculo
from app.models.reglaje import (
    EventoReglaje, SesionReglaje, FichaSuspension, CURVAS_POR_DEFECTO,
    RUEDAS, PARAMETROS_SETUP, AJUSTES_SUSPENSION, PROBLEMAS_CURVA, FASES_CURVA,
    SENSACIONES, RESULTADOS, DECISIONES,
)
from app.routes.mecanica import mecanica_bp
from app.services.log_service import registrar_log
from app.utils import safe_next_url


SECCIONES_HOJA = {"datos", "setup", "piloto", "diagnostico", "cierre"}


def _fecha(raw):
    try:
        return date.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def _num(raw, tipo=float, minimo=None, maximo=None):
    raw = (raw or "").strip().replace(",", ".")
    if not raw:
        return None
    try:
        valor = tipo(float(raw)) if tipo is int else tipo(raw)
    except ValueError:
        return None
    if minimo is not None and valor < minimo or maximo is not None and valor > maximo:
        return None
    return valor


def _txt(form, campo, largo=None):
    valor = (form.get(campo) or "").strip()
    return valor[:largo] if largo else valor


# ── Eventos ───────────────────────────────────────────────────────────────

@mecanica_bp.route("/reglajes")
@login_required
def reglajes_eventos():
    eventos = EventoReglaje.query.order_by(EventoReglaje.fecha_inicio.desc()).all()
    return render_template("mecanica/reglajes/eventos.html", eventos=eventos,
                           curvas_defecto=CURVAS_POR_DEFECTO, hoy=date.today())


def _guardar_evento(evento, form):
    nombre = _txt(form, "nombre", 150)
    inicio = _fecha(form.get("fecha_inicio"))
    fin = _fecha(form.get("fecha_fin"))
    if not nombre or not inicio or (fin and fin < inicio):
        return "Indica el nombre y unas fechas válidas."
    evento.nombre, evento.fecha_inicio, evento.fecha_fin = nombre, inicio, fin
    evento.circuito = _txt(form, "circuito", 150)
    curvas = "\n".join(c.strip() for c in (form.get("curvas_texto") or "").splitlines() if c.strip())
    evento.curvas_texto = curvas or CURVAS_POR_DEFECTO
    evento.notas = _txt(form, "notas")
    return None


@mecanica_bp.route("/reglajes/eventos/nuevo", methods=["POST"])
@login_required
def reglajes_evento_nuevo():
    evento = EventoReglaje()
    error = _guardar_evento(evento, request.form)
    if error:
        flash(error, "danger")
        return redirect(url_for("mecanica.reglajes_eventos"))
    db.session.add(evento)
    db.session.commit()
    registrar_log("crear", "evento_reglaje", evento.id, f"Evento de reglajes: {evento.nombre}")
    flash("Evento creado. Ahora añade las sesiones de cada coche.", "success")
    return redirect(url_for("mecanica.reglajes_evento", id=evento.id))


@mecanica_bp.route("/reglajes/eventos/<int:id>", methods=["GET", "POST"])
@login_required
def reglajes_evento(id):
    evento = EventoReglaje.query.get_or_404(id)
    if request.method == "POST":
        error = _guardar_evento(evento, request.form)
        if error:
            flash(error, "danger")
        else:
            db.session.commit()
            flash("Evento actualizado.", "success")
        return redirect(url_for("mecanica.reglajes_evento", id=evento.id))

    por_coche = {}
    for s in evento.sesiones:
        por_coche.setdefault(s.vehiculo, []).append(s)
    vehiculos = Vehiculo.query.order_by(Vehiculo.dorsal, Vehiculo.id).all()
    # Para cada coche: nombre de la siguiente salida y piloto de la última,
    # así "Nueva salida" queda lista con un toque.
    sugerencias = {}
    for v in vehiculos:
        sesiones = por_coche.get(v, [])
        ultima = sesiones[-1] if sesiones else (
            SesionReglaje.query.filter_by(vehiculo_id=v.id).order_by(SesionReglaje.creado_en.desc()).first())
        sugerencias[v.id] = {
            "sesion": _siguiente_nombre(sesiones[-1].sesion) if sesiones else "Entrenos 1",
            "piloto_id": ultima.piloto_id if ultima else None,
            "piloto_nombre": ultima.piloto_nombre if ultima and not ultima.piloto_id else "",
        }
    return render_template(
        "mecanica/reglajes/evento.html", evento=evento, por_coche=por_coche, sugerencias=sugerencias,
        vehiculos=vehiculos,
        pilotos=Piloto.query.filter_by(activo=True).order_by(Piloto.nombre).all(),
        ahora=datetime.now().strftime("%Y-%m-%dT%H:%M"),
    )


@mecanica_bp.route("/reglajes/eventos/<int:id>/eliminar", methods=["POST"])
@login_required
def reglajes_evento_eliminar(id):
    evento = EventoReglaje.query.get_or_404(id)
    nombre = evento.nombre
    db.session.delete(evento)
    db.session.commit()
    registrar_log("eliminar", "evento_reglaje", id, f"Evento de reglajes eliminado: {nombre}")
    flash("Evento y sus sesiones eliminados.", "success")
    return redirect(url_for("mecanica.reglajes_eventos"))


# ── Sesiones ──────────────────────────────────────────────────────────────

def _siguiente_nombre(nombre):
    """"Manga 1" → "Manga 2"; "Final" → "Final 2"."""
    m = re.match(r"^(.*?)(\d+)\s*$", nombre or "")
    if m:
        return f"{m.group(1)}{int(m.group(2)) + 1}"
    return f"{nombre} 2" if nombre else "Entrenos 1"

@mecanica_bp.route("/reglajes/eventos/<int:id>/sesiones/nueva", methods=["POST"])
@login_required
def reglajes_sesion_nueva(id):
    evento = EventoReglaje.query.get_or_404(id)
    vehiculo = db.session.get(Vehiculo, request.form.get("vehiculo_id", type=int) or 0)
    nombre_sesion = _txt(request.form, "sesion", 80)
    if not vehiculo or not nombre_sesion:
        flash("Elige el coche e indica la sesión (ej. Entrenos 1, Manga 2).", "danger")
        return redirect(url_for("mecanica.reglajes_evento", id=evento.id))

    piloto_id = request.form.get("piloto_id", type=int)
    piloto = db.session.get(Piloto, piloto_id) if piloto_id else None
    if (SesionReglaje.query.filter_by(evento_id=evento.id, vehiculo_id=vehiculo.id, sesion=nombre_sesion).first()):
        flash(f"Ese coche ya tiene una sesión «{nombre_sesion}» en este evento.", "warning")
        return redirect(url_for("mecanica.reglajes_evento", id=evento.id))
    s = SesionReglaje(
        evento_id=evento.id, vehiculo_id=vehiculo.id, sesion=nombre_sesion,
        piloto_id=piloto.id if piloto else None,
        piloto_nombre="" if piloto else _txt(request.form, "piloto_nombre", 150),
        fecha_hora=_fecha_hora(request.form.get("fecha_hora")) or datetime.now().replace(second=0, microsecond=0),
    )
    # El coche sale con el setup con el que terminó su última sesión: se
    # copian los valores, no los "cambio siguiente salida" ya aplicados.
    anterior = (SesionReglaje.query.filter_by(vehiculo_id=vehiculo.id)
                .order_by(SesionReglaje.creado_en.desc()).first())
    if anterior and request.form.get("copiar_setup"):
        setup = anterior.setup
        for valores in setup.values():
            valores.pop("cambio", None)
        s.setup_json = json.dumps(setup)
        s.encargado_setup = anterior.encargado_setup
    if anterior and not s.piloto_id and not s.piloto_nombre:
        s.piloto_id, s.piloto_nombre = anterior.piloto_id, anterior.piloto_nombre
    # El tipo de cada curva es del circuito, no de la salida: se hereda de la
    # última sesión del evento que lo tenga apuntado.
    tipos = {}
    for previa in (SesionReglaje.query.filter_by(evento_id=evento.id)
                   .order_by(SesionReglaje.creado_en.desc()).limit(20)):
        for curva, datos in previa.curvas.items():
            if datos.get("tipo") and curva not in tipos:
                tipos[curva] = datos["tipo"]
    if tipos:
        s.curvas_json = json.dumps({c: {"tipo": t} for c, t in tipos.items()}, ensure_ascii=False)
    db.session.add(s)
    db.session.commit()
    registrar_log("crear", "sesion_reglaje", s.id, f"{evento.nombre}: {nombre_sesion} · {vehiculo.nombre_display}")
    return redirect(url_for("mecanica.reglajes_sesion_editar", sid=s.id))


def _fecha_hora(raw):
    try:
        return datetime.fromisoformat((raw or "").strip())
    except ValueError:
        return None


def _leer_setup(form):
    setup = {}
    for clave, _, _, modo, _ in PARAMETROS_SETUP:
        valores = {}
        if modo == "eje":
            for eje in ("del", "tras"):
                valores[eje] = _num(form.get(f"setup-{clave}-{eje}"))
        else:
            for rueda, _ in RUEDAS:
                if modo == "clicks":
                    valores[rueda] = _num(form.get(f"setup-{clave}-{rueda}"), int, 0, 99)
                else:
                    valores[rueda] = _num(form.get(f"setup-{clave}-{rueda}"), float, 0)
        valores["cambio"] = _txt(form, f"setup-{clave}-cambio", 200)
        setup[clave] = {k: v for k, v in valores.items() if v not in (None, "")}
    return {k: v for k, v in setup.items() if v}


def _leer_curvas(form, curvas):
    datos = {}
    problemas_validos = {k for k, _ in PROBLEMAS_CURVA}
    fases_validas = {k for k, _ in FASES_CURVA}
    for i, nombre in enumerate(curvas):
        c = {
            "tipo": _txt(form, f"curva-{i}-tipo", 150),
            "balance": _num(form.get(f"curva-{i}-balance"), int, -5, 5),
            "problemas": [p for p in form.getlist(f"curva-{i}-problemas") if p in problemas_validos],
            "comentario": _txt(form, f"curva-{i}-comentario", 300),
            "fases": [f for f in form.getlist(f"curva-{i}-fases") if f in fases_validas],
            "diagnostico": _txt(form, f"curva-{i}-diagnostico", 300),
        }
        c = {k: v for k, v in c.items() if v not in (None, "", [])}
        if c:
            datos[nombre] = c
    return datos


@mecanica_bp.route("/reglajes/sesiones/<int:sid>")
@login_required
def reglajes_sesion(sid):
    s = SesionReglaje.query.get_or_404(sid)
    return render_template("mecanica/reglajes/sesion.html", s=s, **_contexto_sesion(s))


def _contexto_sesion(s):
    ficha = s.vehiculo.ficha_suspension
    otras = (SesionReglaje.query.filter_by(evento_id=s.evento_id, vehiculo_id=s.vehiculo_id)
             .order_by(SesionReglaje.creado_en).all())
    idx = next((i for i, o in enumerate(otras) if o.id == s.id), 0)
    # Sesión previa del mismo coche (aunque sea de otro evento): de ahí salen
    # los valores "antes" y los cambios planeados para esta salida.
    previa = (SesionReglaje.query.filter(SesionReglaje.vehiculo_id == s.vehiculo_id,
                                         SesionReglaje.creado_en < s.creado_en)
              .order_by(SesionReglaje.creado_en.desc()).first())
    return dict(
        previa=previa,
        ficha=ficha, ruedas=RUEDAS, parametros=PARAMETROS_SETUP, problemas=PROBLEMAS_CURVA,
        fases=FASES_CURVA, sensaciones=SENSACIONES, resultados=RESULTADOS, decisiones=DECISIONES,
        anterior=otras[idx - 1] if idx > 0 else None,
        siguiente=otras[idx + 1] if idx + 1 < len(otras) else None,
        pilotos=Piloto.query.filter_by(activo=True).order_by(Piloto.nombre).all(),
    )


@mecanica_bp.route("/reglajes/sesiones/<int:sid>/editar", methods=["GET", "POST"])
@login_required
def reglajes_sesion_editar(sid):
    s = SesionReglaje.query.get_or_404(sid)
    if request.method == "POST":
        f = request.form
        s.sesion = _txt(f, "sesion", 80) or s.sesion
        piloto_id = f.get("piloto_id", type=int)
        s.piloto_id = piloto_id if piloto_id and db.session.get(Piloto, piloto_id) else None
        s.piloto_nombre = "" if s.piloto_id else _txt(f, "piloto_nombre", 150)
        s.fecha_hora = _fecha_hora(f.get("fecha_hora"))
        s.encargado_setup = _txt(f, "encargado_setup", 100)
        s.rellenado_por = _txt(f, "rellenado_por", 100)
        s.temp_aire = _num(f.get("temp_aire"))
        s.temp_pista = _num(f.get("temp_pista"))
        s.estado_pista = _txt(f, "estado_pista", 150)

        s.setup_json = json.dumps(_leer_setup(f))
        s.curvas_json = json.dumps(_leer_curvas(f, s.evento.curvas), ensure_ascii=False)
        validas = {k for k, _ in SENSACIONES}
        s.sensaciones_json = json.dumps([k for k in f.getlist("sensaciones") if k in validas])
        s.autoevaluacion = _txt(f, "autoevaluacion")
        s.lo_mas_importante = _txt(f, "lo_mas_importante")
        s.confianza_piloto = _num(f.get("confianza_piloto"), int, 1, 10)

        s.cambio_realizado = _txt(f, "cambio_realizado")
        s.mejor_vuelta_antes = _txt(f, "mejor_vuelta_antes", 20)
        s.mejor_vuelta_despues = _txt(f, "mejor_vuelta_despues", 20)
        s.confianza_antes = _num(f.get("confianza_antes"), int, 1, 10)
        s.confianza_despues = _num(f.get("confianza_despues"), int, 1, 10)
        s.resultado = f.get("resultado") if f.get("resultado") in dict(RESULTADOS) else ""
        s.decision = f.get("decision") if f.get("decision") in dict(DECISIONES) else ""
        s.plan_siguiente = _txt(f, "plan_siguiente")
        s.apuntes = _txt(f, "apuntes")
        db.session.commit()
        # El autoguardado llega cada pocos segundos: no se anota en el log de
        # actividad (lo inundaría); solo el guardado explícito.
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify(ok=True, guardado=datetime.now().strftime("%H:%M:%S"), progreso=s.progreso)
        registrar_log("editar", "sesion_reglaje", s.id, f"{s.evento.nombre}: {s.sesion} · {s.vehiculo.nombre_display}")
        flash("Hoja guardada.", "success")
        seccion = f.get("seguir")
        if seccion:
            ancla = seccion if seccion in SECCIONES_HOJA else "datos"
            return redirect(url_for("mecanica.reglajes_sesion_editar", sid=s.id) + "#" + ancla)
        return redirect(url_for("mecanica.reglajes_sesion", sid=s.id))
    return render_template("mecanica/reglajes/sesion_form.html", s=s, **_contexto_sesion(s))


@mecanica_bp.route("/reglajes/sesiones/<int:sid>/eliminar", methods=["POST"])
@login_required
def reglajes_sesion_eliminar(sid):
    s = SesionReglaje.query.get_or_404(sid)
    evento_id = s.evento_id
    db.session.delete(s)
    db.session.commit()
    flash("Sesión eliminada.", "success")
    return redirect(url_for("mecanica.reglajes_evento", id=evento_id))


# ── Ficha de suspensión del coche ─────────────────────────────────────────

@mecanica_bp.route("/vehiculos/<int:id>/suspension", methods=["GET", "POST"])
@login_required
def reglajes_ficha_suspension(id):
    vehiculo = Vehiculo.query.get_or_404(id)
    ficha = vehiculo.ficha_suspension
    if request.method == "POST":
        if ficha is None:
            ficha = FichaSuspension(vehiculo_id=vehiculo.id)
            db.session.add(ficha)
        ficha.amortiguador = _txt(request.form, "amortiguador", 150)
        ajustes = {}
        for clave, _ in AJUSTES_SUSPENSION:
            ajustes[clave] = {
                "tiene": bool(request.form.get(f"{clave}-tiene")),
                "max_del": _num(request.form.get(f"{clave}-max_del"), int, 1, 99),
                "max_tras": _num(request.form.get(f"{clave}-max_tras"), int, 1, 99),
            }
        ficha.ajustes_json = json.dumps(ajustes)
        db.session.commit()
        registrar_log("editar", "vehiculo", vehiculo.id, f"Ficha de suspensión: {vehiculo.nombre_display}")
        flash("Ficha de suspensión guardada.", "success")
        volver = safe_next_url(request.form.get("volver"))
        if volver:
            return redirect(volver)
        return redirect(url_for("mecanica.vehiculos_detalle", id=vehiculo.id) + "#suspension")
    return render_template("mecanica/reglajes/ficha_suspension.html", vehiculo=vehiculo, ficha=ficha,
                           ajustes=AJUSTES_SUSPENSION, volver=safe_next_url(request.args.get("volver")) or "")
