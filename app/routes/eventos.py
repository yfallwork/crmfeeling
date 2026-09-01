"""
EVENTOS — gestión de entradas (WooCommerce) y control de acceso por QR el
día del evento, e INVITACIONES — invitar directamente a entidades/personas
(patrocinadores, ayuntamiento, VIPs) sin pasar por el checkout público.

Unificadas en un solo apartado del CRM (una entrada en el menú lateral,
sección de permisos "eventos"): las invitaciones son, en el fondo, otra
forma de generar entradas para el mismo evento — comparten modelo de
validación de QR (EntradaEvento por token_pase) y el mismo escáner de
acceso, así que viven bajo /autoclub/eventos/... para heredar sus permisos
sin lógica adicional (ver _restrict_modulos en app/__init__.py).

Las rutas se registran sobre autoclub_bp (definido en app/routes/autoclub.py)
en vez de un blueprint propio — es requisito para que el control de acceso
por sección de AutoClub las reconozca (solo actúa cuando
request.blueprint == "autoclub").

Los pedidos de entradas normales llegan solos vía webhook
(app/routes/woocommerce.py:webhook_eventos); esto es la gestión y el
escáner para el staff, más el alta manual de invitaciones.
"""
import json
import re
from datetime import datetime

import requests
from flask import (render_template, request, redirect, url_for, flash,
                    Response, current_app, jsonify)
from flask_login import login_required, current_user

from app.extensions import db
from app.models.evento import Evento, EntradaEvento
from app.models.invitacion import Invitacion, TIPOS_INVITACION, TIPOS_INVITACION_KEYS
from app.services.log_service import registrar_log
from app.routes.autoclub import autoclub_bp


def _slug(texto):
    s = texto.strip().lower()
    s = (s.replace("á", "a").replace("é", "e").replace("í", "i")
          .replace("ó", "o").replace("ú", "u").replace("ñ", "n"))
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "evento"


def _normalizar_producto_ids(texto):
    """'354857, 354863,354864' -> '354857,354863,354864'"""
    ids = re.findall(r"\d+", texto or "")
    return ",".join(dict.fromkeys(ids))  # sin duplicados, conserva orden


# ══════════════════════════════════════════════════════════════════════════
# ENTRADAS DE EVENTOS
# ══════════════════════════════════════════════════════════════════════════

@autoclub_bp.route("/eventos")
@login_required
def eventos_lista():
    eventos = Evento.query.order_by(Evento.creado_en.desc()).all()
    return render_template("autoclub/eventos/lista.html", eventos=eventos)


@autoclub_bp.route("/eventos/nuevo", methods=["GET", "POST"])
@login_required
def eventos_nuevo():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("Indica un nombre para el evento.", "danger")
            return redirect(url_for("autoclub.eventos_nuevo"))

        fecha_str = request.form.get("fecha", "").strip()
        fecha = None
        if fecha_str:
            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        slug_base = _slug(nombre)
        slug = slug_base
        n = 2
        while Evento.query.filter_by(slug=slug).first():
            slug = f"{slug_base}-{n}"
            n += 1

        activo = bool(request.form.get("activo"))
        if activo:
            # Solo un evento activo a la vez: los pedidos del webhook se
            # asignan al que esté marcado como tal (ver evento_sync.py).
            Evento.query.filter_by(activo=True).update({"activo": False})

        evento = Evento(
            nombre=nombre, slug=slug, fecha=fecha,
            lugar=request.form.get("lugar", "").strip(),
            woo_producto_ids=_normalizar_producto_ids(request.form.get("woo_producto_ids", "")),
            activo=activo,
        )
        db.session.add(evento)
        db.session.commit()
        registrar_log("crear", "evento", evento.id, f"Evento creado: {nombre}")
        flash("Evento creado.", "success")
        return redirect(url_for("autoclub.eventos_detalle", id=evento.id))

    return render_template("autoclub/eventos/form.html", evento=None)


@autoclub_bp.route("/eventos/<int:id>/editar", methods=["GET", "POST"])
@login_required
def eventos_editar(id):
    evento = Evento.query.get_or_404(id)
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if not nombre:
            flash("Indica un nombre para el evento.", "danger")
            return redirect(url_for("autoclub.eventos_editar", id=id))

        fecha_str = request.form.get("fecha", "").strip()
        fecha = None
        if fecha_str:
            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                pass

        activo = bool(request.form.get("activo"))
        if activo and not evento.activo:
            Evento.query.filter_by(activo=True).update({"activo": False})

        evento.nombre = nombre
        evento.fecha = fecha
        evento.lugar = request.form.get("lugar", "").strip()
        evento.woo_producto_ids = _normalizar_producto_ids(request.form.get("woo_producto_ids", ""))
        evento.activo = activo
        db.session.commit()
        registrar_log("editar", "evento", evento.id, f"Evento editado: {nombre}")
        flash("Evento actualizado.", "success")
        return redirect(url_for("autoclub.eventos_detalle", id=id))

    return render_template("autoclub/eventos/form.html", evento=evento)


@autoclub_bp.route("/eventos/<int:id>")
@login_required
def eventos_detalle(id):
    from app.models.evento import ESTADOS_PEDIDO_VALIDOS, ESTADO_PEDIDO_LABELS
    evento = Evento.query.get_or_404(id)
    estado = request.args.get("estado", "")
    tipo = request.args.get("tipo", "")
    validas = request.args.get("validas", "")
    escaneadas = request.args.get("escaneadas", "")
    q = request.args.get("q", "").strip()

    query = evento.entradas
    if validas:
        # Vista rápida: solo las entradas aprobadas (completed/processing),
        # que son las que ya tienen QR y hay que leer en el acceso.
        query = query.filter(EntradaEvento.estado_pedido.in_(ESTADOS_PEDIDO_VALIDOS))
    elif estado:
        query = query.filter(EntradaEvento.estado_pedido == estado)
    if tipo:
        query = query.filter(EntradaEvento.tipo_pase == tipo)
    if escaneadas == "1":
        query = query.filter(EntradaEvento.escaneada.is_(True))
    elif escaneadas == "0":
        query = query.filter(EntradaEvento.escaneada.is_(False))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(
            EntradaEvento.nombre_cliente.ilike(like),
            EntradaEvento.email_cliente.ilike(like),
            EntradaEvento.woo_order_numero.ilike(like),
        ))
    entradas = query.order_by(EntradaEvento.fecha_pedido.desc().nullslast(), EntradaEvento.creado_en.desc()).all()

    estados_presentes = sorted({e.estado_pedido for e in evento.entradas})
    tipos_presentes = sorted({e.tipo_pase for e in evento.entradas if e.tipo_pase})
    woo_configurado = bool(
        current_app.config.get("EVENTOS_WOO_BASE_URL")
        and current_app.config.get("EVENTOS_WOO_CONSUMER_KEY")
        and current_app.config.get("EVENTOS_WOO_CONSUMER_SECRET")
    )
    return render_template(
        "autoclub/eventos/detalle.html",
        evento=evento, entradas=entradas, estado=estado, tipo=tipo, validas=validas,
        escaneadas=escaneadas, q=q,
        estados_presentes=estados_presentes, tipos_presentes=tipos_presentes, woo_configurado=woo_configurado,
        estado_labels=ESTADO_PEDIDO_LABELS,
    )


@autoclub_bp.route("/eventos/<int:id>/activar", methods=["POST"])
@login_required
def eventos_activar(id):
    evento = Evento.query.get_or_404(id)
    Evento.query.filter_by(activo=True).update({"activo": False})
    evento.activo = True
    db.session.commit()
    registrar_log("cambiar_estado", "evento", evento.id, f"Marcado como evento activo: {evento.nombre}")
    flash(f"«{evento.nombre}» es ahora el evento activo (recibirá los próximos pedidos del webhook).", "success")
    return redirect(url_for("autoclub.eventos_detalle", id=id))


@autoclub_bp.route("/eventos/<int:id>/eliminar", methods=["POST"])
@login_required
def eventos_eliminar(id):
    evento = Evento.query.get_or_404(id)
    nombre = evento.nombre
    db.session.delete(evento)
    db.session.commit()
    registrar_log("eliminar", "evento", id, f"Evento eliminado: {nombre}")
    flash("Evento y sus entradas eliminados.", "info")
    return redirect(url_for("autoclub.eventos_lista"))


@autoclub_bp.route("/eventos/<int:id>/sincronizar", methods=["POST"])
@login_required
def eventos_sincronizar(id):
    evento = Evento.query.get_or_404(id)
    from app.services.evento_sync import sync_pedidos_evento
    if not (current_app.config.get("EVENTOS_WOO_BASE_URL")
            and current_app.config.get("EVENTOS_WOO_CONSUMER_KEY")
            and current_app.config.get("EVENTOS_WOO_CONSUMER_SECRET")):
        flash("Falta configurar la conexión con el WooCommerce de entradas.", "danger")
        return redirect(url_for("autoclub.eventos_detalle", id=id))

    stats = sync_pedidos_evento(max_pages=20)
    registrar_log("sync_woo", "evento", evento.id, (
        f"Sync manual eventos: {stats['nuevas']} nuevas, "
        f"{stats['actualizadas']} actualizadas, {stats['errores']} errores"
    ))
    flash(
        f"Sincronización completada: {stats['nuevas']} nuevas, "
        f"{stats['actualizadas']} actualizadas, {stats['errores']} errores.",
        "success" if stats["errores"] == 0 else "warning",
    )
    return redirect(url_for("autoclub.eventos_detalle", id=id))


@autoclub_bp.route("/eventos/<int:id>/entradas/<int:eid>")
@login_required
def eventos_entrada_detalle(id, eid):
    from app.services.evento_sync import requiere_aprobacion_manual
    evento = Evento.query.get_or_404(id)
    entrada = EntradaEvento.query.filter_by(id=eid, evento_id=evento.id).first_or_404()
    woo_configurado = bool(
        current_app.config.get("EVENTOS_WOO_BASE_URL")
        and current_app.config.get("EVENTOS_WOO_CONSUMER_KEY")
        and current_app.config.get("EVENTOS_WOO_CONSUMER_SECRET")
    )
    meta_data = []
    if entrada.meta_data_json:
        try:
            meta_data = [
                m for m in json.loads(entrada.meta_data_json)
                if not str(m.get("key", "")).startswith("_")
            ]
        except (ValueError, TypeError):
            pass
    return render_template(
        "autoclub/eventos/entrada_detalle.html",
        evento=evento, entrada=entrada, meta_data=meta_data,
        woo_configurado=woo_configurado,
        requiere_aprobacion_manual=requiere_aprobacion_manual(entrada.tipo_pase),
    )


@autoclub_bp.route("/eventos/<int:id>/entradas/<int:eid>/aprobar", methods=["POST"])
@login_required
def eventos_entrada_aprobar(id, eid):
    from app.services.evento_sync import aprobar_pedido_woo
    evento = Evento.query.get_or_404(id)
    entrada = EntradaEvento.query.filter_by(id=eid, evento_id=evento.id).first_or_404()

    try:
        if not aprobar_pedido_woo(entrada):
            flash("Falta configurar la conexión con el WooCommerce de entradas (o el pedido no tiene ID de WooCommerce).", "danger")
        else:
            db.session.commit()
            registrar_log("cambiar_estado", "entrada_evento", entrada.id,
                          f"Aprobada en WooCommerce: pedido #{entrada.woo_order_numero or entrada.woo_order_id}")
            flash("Entrada aprobada. WooCommerce generará el QR y avisará al cliente por email.", "success")
    except requests.RequestException as e:
        flash(f"Error al aprobar en WooCommerce: {e}", "danger")
    return redirect(url_for("autoclub.eventos_entrada_detalle", id=id, eid=eid))


@autoclub_bp.route("/eventos/<int:id>/escanear")
@login_required
def eventos_escanear(id):
    evento = Evento.query.get_or_404(id)
    return render_template("autoclub/eventos/escanear.html", evento=evento)


@autoclub_bp.route("/eventos/<int:id>/escanear/validar", methods=["POST"])
@login_required
def eventos_escanear_validar(id):
    evento = Evento.query.get_or_404(id)
    data = request.get_json(force=True, silent=True) or {}
    token = (data.get("token") or "").strip()
    if not token:
        return jsonify({"ok": False, "resultado": "error", "mensaje": "Código vacío."}), 400

    entrada = EntradaEvento.query.filter_by(evento_id=evento.id, token_pase=token).first()
    if not entrada:
        return jsonify({"ok": True, "resultado": "no_encontrada", "mensaje": "Entrada no reconocida para este evento."})

    if not entrada.es_valida:
        return jsonify({
            "ok": True, "resultado": "no_valida",
            "mensaje": f"Pedido en estado «{entrada.estado_label}», no aprobado todavía.",
            "entrada": entrada.to_dict(),
        })

    if entrada.escaneada:
        return jsonify({
            "ok": True, "resultado": "ya_escaneada",
            "mensaje": "Esta entrada ya se escaneó antes.",
            "entrada": entrada.to_dict(),
        })

    entrada.escaneada = True
    entrada.escaneada_en = datetime.utcnow()
    entrada.escaneada_por_id = current_user.id
    db.session.commit()
    registrar_log("cambiar_estado", "entrada_evento", entrada.id,
                  f"Escaneada en acceso: {entrada.nombre_cliente or entrada.email_cliente}")

    return jsonify({
        "ok": True, "resultado": "valida",
        "mensaje": "Entrada válida. Acceso permitido.",
        "entrada": entrada.to_dict(),
    })


# ══════════════════════════════════════════════════════════════════════════
# INVITACIONES — invitar directamente a entidades/personas (patrocinadores,
# ayuntamiento, VIPs) sin pasar por el checkout público de WooCommerce.
# Viven bajo /eventos/invitaciones (no /invitaciones) para heredar el mismo
# permiso de sección "eventos" — es la misma gestión de entradas del mismo
# evento, solo que dadas de alta a mano en vez de por checkout.
# ══════════════════════════════════════════════════════════════════════════

@autoclub_bp.route("/eventos/invitaciones")
@login_required
def invitaciones_lista():
    invitaciones = Invitacion.query.order_by(Invitacion.creado_en.desc()).all()
    return render_template(
        "autoclub/invitaciones/lista.html",
        invitaciones=invitaciones, tipos=TIPOS_INVITACION,
        datos=None, duplicado_existente=None,
        preview_filas=None, preview_errores=None,
    )


@autoclub_bp.route("/eventos/invitaciones", methods=["POST"])
@login_required
def invitaciones_crear():
    from app.services.invitacion_service import crear_invitacion

    nombre = request.form.get("nombre", "").strip()
    email = request.form.get("email", "").strip()
    tipo = request.form.get("tipo", "").strip()
    notas = request.form.get("notas", "").strip()
    forzar = bool(request.form.get("forzar"))

    errores = {}
    if not nombre:
        errores["nombre"] = "Indica el nombre."
    if not email:
        errores["email"] = "Indica el email."
    if tipo not in TIPOS_INVITACION_KEYS:
        errores["tipo"] = "Selecciona un tipo válido."

    if errores:
        flash("Revisa los datos marcados: hay campos obligatorios sin rellenar.", "danger")
        invitaciones = Invitacion.query.order_by(Invitacion.creado_en.desc()).all()
        return render_template(
            "autoclub/invitaciones/lista.html",
            invitaciones=invitaciones, tipos=TIPOS_INVITACION,
            datos=request.form, duplicado_existente=None,
            preview_filas=None, preview_errores=None,
        ), 400

    existente = None if forzar else Invitacion.query.filter_by(email=email).order_by(Invitacion.creado_en.desc()).first()
    if existente:
        invitaciones = Invitacion.query.order_by(Invitacion.creado_en.desc()).all()
        return render_template(
            "autoclub/invitaciones/lista.html",
            invitaciones=invitaciones, tipos=TIPOS_INVITACION,
            datos=request.form, duplicado_existente=existente,
            preview_filas=None, preview_errores=None,
        )

    try:
        crear_invitacion(nombre, email, tipo, notas, current_user.id)
    except requests.RequestException as e:
        flash(f"Error al crear el pedido en WooCommerce: {e}. No se ha guardado ninguna invitación.", "danger")
        return redirect(url_for("autoclub.invitaciones_lista"))
    except Exception as e:
        flash(f"Error al crear la invitación: {e}", "danger")
        return redirect(url_for("autoclub.invitaciones_lista"))

    registrar_log("crear", "invitacion", None, f"Invitación creada para {nombre} ({email})")
    flash(f"Invitación enviada a «{nombre}».", "success")
    return redirect(url_for("autoclub.invitaciones_lista"))


@autoclub_bp.route("/eventos/invitaciones/<int:id>/reenviar", methods=["POST"])
@login_required
def invitaciones_reenviar(id):
    from app.services.invitacion_service import enviar_email_invitacion
    invitacion = Invitacion.query.get_or_404(id)
    if enviar_email_invitacion(invitacion):
        registrar_log("cambiar_estado", "invitacion", invitacion.id, f"Invitación reenviada a {invitacion.email}")
        flash(f"Invitación reenviada a «{invitacion.nombre}».", "success")
    else:
        flash(f"No se pudo reenviar el email: {invitacion.email_error or 'error desconocido'}.", "danger")
    return redirect(url_for("autoclub.invitaciones_lista"))


@autoclub_bp.route("/eventos/invitaciones/plantilla-csv")
@login_required
def invitaciones_plantilla_csv():
    from app.services.invitacion_service import plantilla_csv_bytes
    return Response(
        plantilla_csv_bytes(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=plantilla_invitaciones.csv"},
    )


@autoclub_bp.route("/eventos/invitaciones/lote/previsualizar", methods=["POST"])
@login_required
def invitaciones_lote_previsualizar():
    from app.services.invitacion_service import parsear_csv_invitaciones

    archivo = request.files.get("archivo_csv")
    if not archivo or not archivo.filename:
        flash("Selecciona un archivo CSV.", "danger")
        return redirect(url_for("autoclub.invitaciones_lista"))
    if not archivo.filename.lower().endswith(".csv"):
        flash("El archivo debe tener extensión .csv.", "danger")
        return redirect(url_for("autoclub.invitaciones_lista"))

    filas, errores = parsear_csv_invitaciones(archivo.stream)
    invitaciones = Invitacion.query.order_by(Invitacion.creado_en.desc()).all()
    return render_template(
        "autoclub/invitaciones/lista.html",
        invitaciones=invitaciones, tipos=TIPOS_INVITACION,
        datos=None, duplicado_existente=None,
        preview_filas=filas, preview_errores=errores,
        preview_filas_json=json.dumps(filas, ensure_ascii=False) if filas else "",
    )


@autoclub_bp.route("/eventos/invitaciones/lote/confirmar", methods=["POST"])
@login_required
def invitaciones_lote_confirmar():
    from app.services.invitacion_service import procesar_lote

    try:
        filas = json.loads(request.form.get("filas_json", "[]"))
    except (ValueError, TypeError):
        flash("No se pudo leer el lote a procesar. Vuelve a subir el CSV.", "danger")
        return redirect(url_for("autoclub.invitaciones_lista"))

    a_procesar = []
    excluidas = 0
    for f in filas:
        if not isinstance(f, dict):
            continue
        # Defensa en profundidad: revalidar aunque ya se validó al previsualizar.
        if not f.get("nombre") or not f.get("email") or f.get("tipo") not in TIPOS_INVITACION_KEYS:
            continue
        if f.get("ya_invitado") and not request.form.get(f"incluir_{f.get('fila')}"):
            excluidas += 1
            continue
        a_procesar.append(f)

    if not a_procesar:
        flash("No había ninguna invitación que procesar (todas excluidas o el lote estaba vacío).", "warning")
        return redirect(url_for("autoclub.invitaciones_lista"))

    resultado = procesar_lote(a_procesar, current_user.id)
    # El botón "reintentar fallidas" reenvía este mismo listado tal cual —
    # se quita el flag de duplicado para que el reintento no vuelva a
    # excluirlas silenciosamente (ya se decidió incluirlas la primera vez).
    for f in resultado["fallidas"]:
        f.pop("ya_invitado", None)
    registrar_log("crear", "invitacion", None,
                  f"Lote de invitaciones: {len(resultado['ok'])} creadas, {len(resultado['fallidas'])} fallidas")

    if resultado["fallidas"]:
        flash(
            f"{len(resultado['ok'])} invitaciones enviadas. {len(resultado['fallidas'])} fallaron "
            f"(revisa el detalle abajo para reintentarlas).", "warning",
        )
    else:
        flash(f"{len(resultado['ok'])} invitaciones enviadas correctamente.", "success")
    if excluidas:
        flash(f"{excluidas} fila(s) excluidas por ser emails ya invitados.", "info")

    invitaciones = Invitacion.query.order_by(Invitacion.creado_en.desc()).all()
    return render_template(
        "autoclub/invitaciones/lista.html",
        invitaciones=invitaciones, tipos=TIPOS_INVITACION,
        datos=None, duplicado_existente=None,
        preview_filas=None, preview_errores=None,
        lote_resultado=resultado,
    )
