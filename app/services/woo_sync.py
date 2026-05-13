import requests
from datetime import datetime
from flask import current_app
from app.extensions import db
from app.models.cliente import Cliente
from app.models.experiencia import TipoExperiencia
from app.models.reserva import Reserva

# Meses en español → número
MESES_ES = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# Valores de pa_fechas que indican fecha abierta (regalo/voucher)
FECHA_ABIERTA_KEYWORDS = ("abierta", "regalo", "open", "voucher", "gift")


def _woo_params_auth():
    return {
        "consumer_key": current_app.config["WOO_CONSUMER_KEY"],
        "consumer_secret": current_app.config["WOO_CONSUMER_SECRET"],
    }


def _woo_url(endpoint):
    base = current_app.config["WOO_BASE_URL"].rstrip("/")
    return f"{base}/wp-json/wc/v3/{endpoint.lstrip('/')}"


def fetch_orders(page=1, per_page=100, after=None):
    params = {
        **_woo_params_auth(),
        "page": page,
        "per_page": per_page,
        "orderby": "date",
        "order": "desc",
    }
    if after:
        params["after"] = after
    try:
        resp = requests.get(_woo_url("orders"), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json(), int(resp.headers.get("X-WP-TotalPages", 1))
    except requests.RequestException as e:
        current_app.logger.error(f"WooCommerce API error: {e}")
        return [], 0


def _parse_fecha_woo(pa_fechas, horario=""):
    """
    Convierte 'mayo-16-2026' + '10:00-12:00'  →  datetime(2026, 5, 16, 10, 0)
    Si es fecha abierta (regalo) o no parseable  →  None
    """
    v = (pa_fechas or "").lower().strip()

    if not v or any(k in v for k in FECHA_ABIERTA_KEYWORDS):
        return None

    # Formato esperado: "mes-dia-año" ej. "mayo-16-2026"
    parts = v.split("-")
    if len(parts) < 3:
        return None

    mes = MESES_ES.get(parts[0])
    if not mes:
        return None

    try:
        dia = int(parts[1])
        anio = int(parts[2])
    except (ValueError, IndexError):
        return None

    # Hora de inicio del horario "10:00-12:00" → 10:00
    hora, minuto = 10, 0
    if horario:
        hora_inicio = horario.split("-")[0].strip()
        try:
            h, m = hora_inicio.split(":")
            hora, minuto = int(h), int(m)
        except (ValueError, AttributeError):
            pass

    try:
        return datetime(anio, mes, dia, hora, minuto)
    except ValueError:
        return None


def _extract_item_meta(item):
    """Extrae los meta relevantes de un line_item en un dict limpio."""
    meta = {}
    for m in item.get("meta_data", []):
        key = m.get("key", "")
        val = m.get("value", "")
        # Ignorar campos internos de WooCommerce
        if key.startswith("_"):
            continue
        # Si el valor es un dict (ej. _woo_vou_recipient_name), coger .value
        if isinstance(val, dict):
            val = val.get("value", "")
        meta[key] = str(val)
    return meta


def _parse_date(date_str):
    if not date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _get_or_create_cliente(billing, order_meta, woo_customer_id):
    email = billing.get("email", "").strip().lower()
    if not email:
        return None

    # Teléfono: primero billing.phone, luego order_meta billing_phone
    telefono = billing.get("phone", "").strip()
    if not telefono:
        telefono = next(
            (m["value"] for m in order_meta if m.get("key") == "billing_phone"), ""
        )

    cliente = Cliente.query.filter_by(email=email).first()
    if not cliente:
        cliente = Cliente(
            nombre=billing.get("first_name", "").strip(),
            apellido=billing.get("last_name", "").strip(),
            email=email,
            telefono=telefono,
            fuente="woocommerce",
            woo_customer_id=woo_customer_id or None,
        )
        db.session.add(cliente)
    else:
        if not cliente.telefono and telefono:
            cliente.telefono = telefono
        if woo_customer_id and not cliente.woo_customer_id:
            cliente.woo_customer_id = woo_customer_id
    return cliente


def _get_or_create_tipo(product_name, product_id, precio):
    tipo = TipoExperiencia.query.filter_by(woo_product_id=product_id).first()
    if not tipo:
        tipo = TipoExperiencia.query.filter(
            TipoExperiencia.nombre.ilike(f"%{product_name[:40]}%")
        ).first()
    if not tipo:
        tipo = TipoExperiencia(
            nombre=product_name,
            precio_base=float(precio or 0),
            woo_product_id=product_id,
            color="#AD1726",
        )
        db.session.add(tipo)
    return tipo


def _map_woo_status(woo_status):
    mapping = {
        "pending":    "pendiente",
        "processing": "pendiente",
        "on-hold":    "pendiente",
        "completed":  "disfrutado",
        "cancelled":  "cancelado",
        "refunded":   "cancelado",
        "failed":     "cancelado",
    }
    return mapping.get(woo_status, "pendiente")


def sync_orders(max_pages=10):
    stats = {"nuevas": 0, "actualizadas": 0, "errores": 0}

    for page in range(1, max_pages + 1):
        orders, total_pages = fetch_orders(page=page)
        if not orders:
            break

        for order in orders:
            try:
                _process_order(order, stats)
            except Exception as e:
                current_app.logger.error(
                    f"Error procesando pedido {order.get('id')}: {e}"
                )
                stats["errores"] += 1

        db.session.commit()

        if page >= total_pages:
            break

    return stats


def _process_order(order, stats):
    woo_order_id   = order["id"]
    billing        = order.get("billing", {})
    order_meta_raw = order.get("meta_data", [])
    woo_customer_id= order.get("customer_id")
    fecha_compra   = _parse_date(order.get("date_created"))
    woo_status     = order.get("status", "")

    cliente = _get_or_create_cliente(billing, order_meta_raw, woo_customer_id)
    if not cliente:
        stats["errores"] += 1
        return

    for item in order.get("line_items", []):
        product_name = item.get("name", "Experiencia")
        product_id   = item.get("product_id")
        precio       = item.get("total", 0)

        meta         = _extract_item_meta(item)
        pa_fechas    = meta.get("pa_fechas", "")
        horario      = meta.get("horario", "")
        variante     = meta.get("pa_escoge-tu-experiencia", "")

        fecha_disfrute = _parse_fecha_woo(pa_fechas, horario)

        # Estado: si tiene fecha específica y el pedido está activo → reservado
        estado_crm = _map_woo_status(woo_status)
        if fecha_disfrute and estado_crm == "pendiente":
            estado_crm = "reservado"

        tipo = _get_or_create_tipo(product_name, product_id, precio)
        db.session.flush()

        reserva = Reserva.query.filter_by(woo_order_id=woo_order_id).first()
        if reserva:
            # Actualizar datos que pueden haber cambiado
            reserva.woo_order_status = woo_status
            reserva.estado           = estado_crm
            # Solo actualizar fecha si antes era None y ahora tenemos una
            if not reserva.fecha_disfrute and fecha_disfrute:
                reserva.fecha_disfrute = fecha_disfrute
            if not reserva.horario and horario:
                reserva.horario = horario
            if not reserva.variante and variante:
                reserva.variante = variante
            stats["actualizadas"] += 1
        else:
            reserva = Reserva(
                cliente=cliente,
                tipo_experiencia=tipo,
                fecha_compra=fecha_compra,
                fecha_disfrute=fecha_disfrute,
                estado=estado_crm,
                precio=float(precio or 0),
                horario=horario,
                variante=variante,
                woo_order_id=woo_order_id,
                woo_order_status=woo_status,
            )
            db.session.add(reserva)
            stats["nuevas"] += 1
