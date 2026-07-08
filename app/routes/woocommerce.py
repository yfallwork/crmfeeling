import hmac
import hashlib
import base64
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app
from flask_login import login_required
from app.services.woo_sync import sync_orders, fetch_orders
from app.models.reserva import Reserva
from app.models.experiencia import TipoExperiencia
from app.extensions import db, csrf

woo_bp = Blueprint("woocommerce", __name__)


@woo_bp.route("/")
@login_required
def index():
    ultima_sincronizacion = (
        Reserva.query
        .filter(Reserva.woo_order_id.isnot(None))
        .order_by(Reserva.actualizado_en.desc())
        .first()
    )
    total_woo = Reserva.query.filter(Reserva.woo_order_id.isnot(None)).count()
    tipos = TipoExperiencia.query.all()
    return render_template(
        "woocommerce/sync.html",
        ultima_sincronizacion=ultima_sincronizacion,
        total_woo=total_woo,
        tipos=tipos,
    )


@woo_bp.route("/sync", methods=["POST"])
@login_required
def sync():
    from app.services.log_service import registrar_log
    try:
        stats = sync_orders(max_pages=20)
        registrar_log("sync_woo", "sistema", detalle=(
            f"Sync manual: {stats['nuevas']} nuevas, "
            f"{stats['actualizadas']} actualizadas, {stats['errores']} errores"
        ), origen="woocommerce")
        flash(
            f"Sincronización completada: {stats['nuevas']} nuevas, "
            f"{stats['actualizadas']} actualizadas, {stats['errores']} errores.",
            "success" if stats["errores"] == 0 else "warning",
        )
    except Exception as e:
        flash(f"Error durante la sincronización: {e}", "danger")
    return redirect(url_for("woocommerce.index"))


@woo_bp.route("/test-conexion")
@login_required
def test_conexion():
    import requests as req
    from app.services.woo_sync import _woo_url, _woo_params_auth
    try:
        resp = req.get(
            _woo_url("orders"),
            params={**_woo_params_auth(), "per_page": 1},
            timeout=15,
        )
        if resp.status_code == 200:
            total = resp.headers.get("X-WP-Total", "?")
            return jsonify({"ok": True, "mensaje": f"Conexion exitosa. {total} pedidos en total."})
        data = resp.json()
        return jsonify({
            "ok": False,
            "mensaje": f"Error {resp.status_code}: {data.get('message', resp.text[:200])}",
        }), 200
    except Exception as e:
        return jsonify({"ok": False, "mensaje": str(e)}), 200


@woo_bp.route("/inspeccionar-pedido")
@login_required
def inspeccionar_pedido():
    """Muestra los metadatos reales de los últimos pedidos para identificar
    en qué campo guarda WooCommerce la fecha de la experiencia."""
    import requests as req
    from app.services.woo_sync import _woo_url, _woo_params_auth
    try:
        resp = req.get(
            _woo_url("orders"),
            params={**_woo_params_auth(), "per_page": 5, "orderby": "date", "order": "desc"},
            timeout=20,
        )
        orders = resp.json()
        resultado = []
        for o in orders:
            pedido = {
                "id": o["id"],
                "status": o["status"],
                "date_created": o["date_created"],
                "cliente": f"{o['billing'].get('first_name','')} {o['billing'].get('last_name','')}".strip(),
                "line_items": [],
            }
            for item in o.get("line_items", []):
                li = {
                    "nombre": item.get("name"),
                    "product_id": item.get("product_id"),
                    "meta_data": [
                        {"key": m["key"], "value": m["value"]}
                        for m in item.get("meta_data", [])
                    ],
                }
                pedido["line_items"].append(li)
            # También meta del pedido completo
            pedido["order_meta"] = [
                {"key": m["key"], "value": m["value"]}
                for m in o.get("meta_data", [])
                if not m["key"].startswith("_")  # omitir campos internos de WP
            ]
            resultado.append(pedido)
        return jsonify(resultado)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@woo_bp.route("/webhook", methods=["POST"])
@csrf.exempt
def webhook():
    """
    Endpoint para webhooks de WooCommerce.
    Configura en WooCommerce → Ajustes → Avanzado → Webhooks:
      - Tema: Pedido creado / Pedido actualizado
      - URL: https://tu-servidor.com/woocommerce/webhook
      - Secreto: el valor de WOO_WEBHOOK_SECRET en .env

    Exento de CSRF porque es una llamada servidor-a-servidor (WooCommerce),
    no una petición de navegador con sesión — la autenticidad se verifica
    con la firma HMAC de abajo, no con cookies de sesión.
    """
    secret = current_app.config.get("WOO_WEBHOOK_SECRET", "")
    if not secret:
        current_app.logger.error(
            "Webhook rechazado: WOO_WEBHOOK_SECRET no está configurado en el entorno."
        )
        return jsonify({"ok": False, "error": "Webhook no configurado"}), 503

    sig_header = request.headers.get("X-WC-Webhook-Signature", "")
    payload    = request.get_data()
    expected   = base64.b64encode(
        hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    ).decode()
    if not sig_header or not hmac.compare_digest(sig_header, expected):
        current_app.logger.warning("Webhook: firma inválida")
        return jsonify({"ok": False, "error": "Firma invalida"}), 401

    topic = request.headers.get("X-WC-Webhook-Topic", "")
    if not topic.startswith("order."):
        return jsonify({"ok": True, "skip": True})

    order = request.get_json(force=True, silent=True)
    if not order:
        return jsonify({"ok": False, "error": "Sin datos"}), 400

    stats = {"nuevas": 0, "actualizadas": 0, "errores": 0}
    try:
        from app.services.woo_sync import _process_order
        from app.services.log_service import registrar_log
        _process_order(order, stats)
        db.session.commit()
        registrar_log("webhook", "sistema",
                      detalle=f"Webhook {topic} pedido #{order.get('id')}: {stats['nuevas']} nuevas, {stats['actualizadas']} actualizadas",
                      origen="webhook")
        current_app.logger.info(f"Webhook {topic} pedido #{order.get('id')} → {stats}")
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

    return jsonify({"ok": True, "stats": stats})


@woo_bp.route("/experiencias", methods=["GET", "POST"])
@login_required
def experiencias():
    tipos = TipoExperiencia.query.all()

    if request.method == "POST":
        accion = request.form.get("accion")
        tipo_id = request.form.get("tipo_id", type=int)
        tipo = TipoExperiencia.query.get_or_404(tipo_id) if tipo_id else None

        if accion == "crear":
            nuevo = TipoExperiencia(
                nombre=request.form.get("nombre", "").strip(),
                descripcion=request.form.get("descripcion", "").strip(),
                duracion_minutos=int(request.form.get("duracion_minutos", 60) or 60),
                precio_base=float(request.form.get("precio_base", 0) or 0),
                color=request.form.get("color", "#2563EB"),
                woo_product_id=request.form.get("woo_product_id", type=int),
            )
            db.session.add(nuevo)
            db.session.commit()
            flash("Tipo de experiencia creado.", "success")

        elif accion == "eliminar" and tipo:
            db.session.delete(tipo)
            db.session.commit()
            flash("Tipo eliminado.", "info")

        return redirect(url_for("woocommerce.experiencias"))

    return render_template("woocommerce/experiencias.html", tipos=tipos)
