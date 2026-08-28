import json
from datetime import datetime
import requests
from flask import current_app
from app.extensions import db
from app.models.evento import Evento, EntradaEvento

# Claves de meta_data que WooCommerce añade al pedido/pase y que promovemos
# a columnas propias en EntradaEvento (el resto del meta_data se guarda
# igualmente completo en meta_data_json por si hace falta consultarlo).
_META_FIELDS = {
    "token_pase":         "token_pase",
    # Prensa
    "dni_prensa":         "dni_prensa",
    "medio_comunicacion": "medio_comunicacion",
    "cargo_prensa":       "cargo_prensa",
    "carne_prensa":       "carne_prensa",
    "portfolio_redes":    "portfolio_redes",
    # Institucional
    "cargo_institucional": "cargo_institucional",
    "institucion":         "institucion",
    "cif_institucion":     "cif_institucion",
    "num_acompanantes":    "num_acompanantes",
}
# Campos numéricos: se guardan con int() en vez de como texto tal cual.
_META_FIELDS_NUMERICOS = {"num_acompanantes"}

# Los tipos de entrada cuyo nombre de producto contiene alguna de estas
# palabras requieren revisión manual antes de aprobarse (prensa/institución
# necesitan comprobar credenciales). Todo lo demás (entrada general) se
# considera automáticamente aprobable en cuanto el pago está confirmado.
_PALABRAS_REQUIEREN_APROBACION_MANUAL = ("prensa", "instituci")


def requiere_aprobacion_manual(tipo_pase):
    t = (tipo_pase or "").lower()
    return any(p in t for p in _PALABRAS_REQUIEREN_APROBACION_MANUAL)


def _parsear_fecha_woo(valor):
    """WooCommerce manda date_created como '2026-08-24T13:29:44' (hora del
    sitio, sin zona horaria)."""
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except (ValueError, TypeError):
        return None


def _evento_destino(order_data):
    """Decide a qué Evento pertenece un pedido:
    1. Si algún evento tiene woo_producto_ids configurado: el pedido solo
       se asigna si alguna de sus líneas tiene un product_id que coincida
       con alguno de esos eventos — así conviven varias ediciones
       vendiéndose a la vez sin mezclarse. Si no coincide con ninguno (o
       el pedido no trae product_id útil, ej. producto ya borrado en
       WooCommerce → product_id 0), se ignora: NO cae al evento activo
       por defecto, precisamente para no colar pedidos de otra cosa.
    2. Solo si NINGÚN evento tiene productos configurados todavía se usa
       el único evento marcado como activo (modo simple, un evento).
    """
    eventos_con_filtro = Evento.query.filter(Evento.woo_producto_ids.isnot(None), Evento.woo_producto_ids != "").all()
    if eventos_con_filtro:
        product_ids_pedido = {
            str(li.get("product_id")) for li in order_data.get("line_items", []) if li.get("product_id")
        }
        for evento in eventos_con_filtro:
            if product_ids_pedido & set(evento.producto_ids_lista):
                return evento
        return None

    return Evento.query.filter_by(activo=True).order_by(Evento.id.desc()).first()


def procesar_pedido_evento(order_data):
    """Crea o actualiza la EntradaEvento correspondiente a un pedido de
    WooCommerce. Devuelve None si el pedido no pertenece a ningún evento
    conocido (ver _evento_destino)."""
    evento = _evento_destino(order_data)
    if not evento:
        return None

    order_id = order_data.get("id")
    meta = {m.get("key"): m.get("value") for m in order_data.get("meta_data", []) if m.get("key")}
    billing = order_data.get("billing", {}) or {}
    line_items = order_data.get("line_items", []) or []
    tipo_pase = line_items[0].get("name", "") if line_items else ""

    entrada = EntradaEvento.query.filter_by(woo_order_id=order_id).first()
    if not entrada:
        entrada = EntradaEvento(evento_id=evento.id, woo_order_id=order_id)
        db.session.add(entrada)

    entrada.woo_order_numero = str(order_data.get("number", order_id))
    entrada.estado_pedido = order_data.get("status", "pending")
    entrada.fecha_pedido = _parsear_fecha_woo(order_data.get("date_created"))
    entrada.nombre_cliente = f"{billing.get('first_name', '')} {billing.get('last_name', '')}".strip()
    entrada.email_cliente = billing.get("email", "")
    entrada.telefono_cliente = billing.get("phone", "")
    entrada.tipo_pase = tipo_pase

    for meta_key, attr in _META_FIELDS.items():
        valor = meta.get(meta_key)
        if valor in (None, ""):
            continue
        if meta_key in _META_FIELDS_NUMERICOS:
            try:
                setattr(entrada, attr, int(valor))
            except (TypeError, ValueError):
                pass
        else:
            setattr(entrada, attr, str(valor)[:300])

    entrada.meta_data_json = json.dumps(order_data.get("meta_data", []), ensure_ascii=False)

    # Entrada general en "processing" (pago ya confirmado por WooCommerce,
    # solo pendiente de la confirmación manual que aquí no hace falta) →
    # se aprueba sola. Prensa/institucional NUNCA se auto-aprueban: exigen
    # revisión humana de las credenciales antes de dar acceso.
    if entrada.estado_pedido == "processing" and not requiere_aprobacion_manual(entrada.tipo_pase):
        try:
            aprobar_pedido_woo(entrada)
        except requests.RequestException as e:
            current_app.logger.error(
                f"Auto-aprobación fallida para el pedido {entrada.woo_order_id}: {e}"
            )

    return entrada


def aprobar_pedido_woo(entrada):
    """Llama a la API REST de WooCommerce para marcar el pedido como
    'completed'. WordPress se encarga de generar el token/QR y avisar al
    cliente por email — el CRM no replica esa lógica, solo dispara el
    cambio de estado. Devuelve True si se aprobó, False si falta
    configuración o el pedido no tiene woo_order_id."""
    base = current_app.config.get("EVENTOS_WOO_BASE_URL", "")
    ck = current_app.config.get("EVENTOS_WOO_CONSUMER_KEY", "")
    cs = current_app.config.get("EVENTOS_WOO_CONSUMER_SECRET", "")
    if not (base and ck and cs and entrada.woo_order_id):
        return False

    url = f"{base.rstrip('/')}/wp-json/wc/v3/orders/{entrada.woo_order_id}"
    resp = requests.put(url, json={"status": "completed"}, auth=(ck, cs), timeout=20)
    resp.raise_for_status()
    entrada.estado_pedido = "completed"
    return True


def _woo_eventos_url(endpoint):
    base = current_app.config["EVENTOS_WOO_BASE_URL"].rstrip("/")
    return f"{base}/wp-json/wc/v3/{endpoint.lstrip('/')}"


def _woo_eventos_auth():
    return (
        current_app.config["EVENTOS_WOO_CONSUMER_KEY"],
        current_app.config["EVENTOS_WOO_CONSUMER_SECRET"],
    )


def fetch_orders_evento(page=1, per_page=100):
    resp = requests.get(
        _woo_eventos_url("orders"),
        params={"page": page, "per_page": per_page, "orderby": "date", "order": "desc"},
        auth=_woo_eventos_auth(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json(), int(resp.headers.get("X-WP-TotalPages", 1))


def sync_pedidos_evento(max_pages=10):
    """Trae pedidos de WooCommerce y los procesa igual que el webhook — red
    de seguridad para pedidos que llegaron antes de configurar el webhook,
    o si algún envío puntual se perdió. Usado tanto por el botón manual
    como por el job periódico del scheduler."""
    stats = {"nuevas": 0, "actualizadas": 0, "ignoradas": 0, "errores": 0}
    if not (current_app.config.get("EVENTOS_WOO_BASE_URL")
            and current_app.config.get("EVENTOS_WOO_CONSUMER_KEY")
            and current_app.config.get("EVENTOS_WOO_CONSUMER_SECRET")):
        return stats

    for page in range(1, max_pages + 1):
        try:
            orders, total_pages = fetch_orders_evento(page=page)
        except requests.RequestException as e:
            current_app.logger.error(f"Error sincronizando pedidos de eventos: {e}")
            stats["errores"] += 1
            break
        if not orders:
            break

        for order in orders:
            try:
                existia = EntradaEvento.query.filter_by(woo_order_id=order.get("id")).first() is not None
                entrada = procesar_pedido_evento(order)
                if entrada is None:
                    stats["ignoradas"] += 1
                elif existia:
                    stats["actualizadas"] += 1
                else:
                    stats["nuevas"] += 1
            except Exception as e:
                current_app.logger.error(f"Error procesando pedido {order.get('id')} en sync eventos: {e}")
                stats["errores"] += 1

        db.session.commit()
        if page >= total_pages:
            break

    return stats
