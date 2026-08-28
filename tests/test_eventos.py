"""
Verifica el módulo de Eventos: creación/gestión desde AutoClub, el webhook de
WooCommerce (firma HMAC, mapeo de meta_data a EntradaEvento) y el flujo de
escaneo de QR el día del evento (válida / ya escaneada / no válida / no
reconocida).
"""
import hashlib
import hmac
import base64
import json
from datetime import datetime
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models.evento import Evento, EntradaEvento

WEBHOOK_SECRET = "secreto-de-prueba-para-tests"


def _borrar_evento(app, evento_id):
    with app.app_context():
        EntradaEvento.query.filter_by(evento_id=evento_id).delete()
        Evento.query.filter_by(id=evento_id).delete()
        db.session.commit()


def _crear_evento_activo(app, nombre="Evento de prueba"):
    with app.app_context():
        Evento.query.filter_by(activo=True).update({"activo": False})
        db.session.commit()
        e = Evento(nombre=nombre, slug=nombre.lower().replace(" ", "-"), activo=True)
        db.session.add(e)
        db.session.commit()
        return e.id


def _firmar(app, payload_bytes):
    app.config["EVENTOS_WOO_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    digest = hmac.new(WEBHOOK_SECRET.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _pedido_woo(order_id=555, status="completed", token="tok-abc123", email="prensa@example.com",
                 product_id=None, date_created="2026-08-20T10:00:00"):
    return {
        "id": order_id,
        "number": str(order_id),
        "status": status,
        "date_created": date_created,
        "billing": {"first_name": "Ana", "last_name": "Reportera", "email": email, "phone": "600111222"},
        "line_items": [{"name": "Pase de prensa", "product_id": product_id}],
        "meta_data": [
            {"key": "token_pase", "value": token},
            {"key": "dni_prensa", "value": "12345678A"},
            {"key": "medio_comunicacion", "value": "Radio Guadalajara"},
            {"key": "cargo_prensa", "value": "Redactora"},
        ],
    }


# ── Webhook ──────────────────────────────────────────────────────────

def test_webhook_rechaza_sin_secreto_configurado(client, app):
    app.config["EVENTOS_WOO_WEBHOOK_SECRET"] = ""
    resp = client.post(
        "/woocommerce/webhook-eventos",
        data=json.dumps(_pedido_woo()),
        headers={"X-WC-Webhook-Topic": "order.created", "Content-Type": "application/json"},
    )
    assert resp.status_code == 503


def test_webhook_rechaza_firma_invalida(client, app):
    app.config["EVENTOS_WOO_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    resp = client.post(
        "/woocommerce/webhook-eventos",
        data=json.dumps(_pedido_woo()),
        headers={
            "X-WC-Webhook-Topic": "order.created",
            "X-WC-Webhook-Signature": "firma-falsa",
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 401


def test_webhook_crea_entrada_con_firma_valida(client, app):
    evento_id = _crear_evento_activo(app, "Webhook Crea Entrada")
    try:
        payload = json.dumps(_pedido_woo(order_id=9001, token="tok-webhook-1")).encode()
        firma = _firmar(app, payload)
        resp = client.post(
            "/woocommerce/webhook-eventos",
            data=payload,
            headers={
                "X-WC-Webhook-Topic": "order.created",
                "X-WC-Webhook-Signature": firma,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        with app.app_context():
            entrada = EntradaEvento.query.filter_by(woo_order_id=9001).first()
            assert entrada is not None
            assert entrada.evento_id == evento_id
            assert entrada.estado_pedido == "completed"
            assert entrada.token_pase == "tok-webhook-1"
            assert entrada.nombre_cliente == "Ana Reportera"
            assert entrada.medio_comunicacion == "Radio Guadalajara"
            assert entrada.fecha_pedido is not None
            assert entrada.fecha_pedido.isoformat() == "2026-08-20T10:00:00"
    finally:
        _borrar_evento(app, evento_id)


def test_webhook_ignora_topics_que_no_son_pedidos(client, app):
    app.config["EVENTOS_WOO_WEBHOOK_SECRET"] = WEBHOOK_SECRET
    payload = json.dumps({"algo": "irrelevante"}).encode()
    firma = _firmar(app, payload)
    resp = client.post(
        "/woocommerce/webhook-eventos",
        data=payload,
        headers={
            "X-WC-Webhook-Topic": "customer.created",
            "X-WC-Webhook-Signature": firma,
            "Content-Type": "application/json",
        },
    )
    assert resp.status_code == 200
    assert resp.get_json().get("skip") is True


# ── Panel admin ──────────────────────────────────────────────────────

def test_eventos_requiere_login(client):
    resp = client.get("/autoclub/eventos")
    assert resp.status_code in (302, 401, 403)


def test_crear_evento_y_verlo_en_listado(auth_client, auth_csrf_token, app):
    resp = auth_client.post(
        "/autoclub/eventos/nuevo",
        data={
            "nombre": "V Autocross La Dehesa",
            "fecha": "",
            "lugar": "Circuito La Dehesa",
            "activo": "1",
            "csrf_token": auth_csrf_token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        evento = Evento.query.filter_by(nombre="V Autocross La Dehesa").first()
        assert evento is not None
        assert evento.activo is True
        eid = evento.id
    try:
        resp = auth_client.get("/autoclub/eventos")
        assert resp.status_code == 200
        assert b"V Autocross La Dehesa" in resp.data
    finally:
        _borrar_evento(app, eid)


# ── Aprobar entrada (PUT a WooCommerce) ─────────────────────────────

def test_aprobar_entrada_llama_a_woocommerce_y_actualiza_estado(auth_client, auth_csrf_token, app):
    evento_id = _crear_evento_activo(app, "Evento Aprobar")
    app.config["EVENTOS_WOO_BASE_URL"] = "https://entradas.example.com"
    app.config["EVENTOS_WOO_CONSUMER_KEY"] = "ck_test"
    app.config["EVENTOS_WOO_CONSUMER_SECRET"] = "cs_test"
    with app.app_context():
        entrada = EntradaEvento(evento_id=evento_id, woo_order_id=777, estado_pedido="pending")
        db.session.add(entrada)
        db.session.commit()
        eid = entrada.id
    try:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        with patch("app.services.evento_sync.requests.put", return_value=mock_resp) as mock_put:
            resp = auth_client.post(
                f"/autoclub/eventos/{evento_id}/entradas/{eid}/aprobar",
                data={"csrf_token": auth_csrf_token},
                follow_redirects=True,
            )
        assert resp.status_code == 200
        assert mock_put.called
        call_args = mock_put.call_args
        assert "orders/777" in call_args[0][0]
        assert call_args[1]["json"] == {"status": "completed"}
        assert call_args[1]["auth"] == ("ck_test", "cs_test")
        with app.app_context():
            assert EntradaEvento.query.get(eid).estado_pedido == "completed"
    finally:
        _borrar_evento(app, evento_id)


# ── Escaneo de QR ────────────────────────────────────────────────────

def test_escanear_no_reconocida(auth_client, auth_csrf_token, app):
    evento_id = _crear_evento_activo(app, "Evento Escaneo A")
    try:
        resp = auth_client.post(
            f"/autoclub/eventos/{evento_id}/escanear/validar",
            data=json.dumps({"token": "no-existe"}),
            content_type="application/json",
            headers={"X-CSRFToken": auth_csrf_token},
        )
        assert resp.status_code == 200
        assert resp.get_json()["resultado"] == "no_encontrada"
    finally:
        _borrar_evento(app, evento_id)


def test_escanear_valida_y_luego_ya_escaneada(auth_client, auth_csrf_token, app):
    evento_id = _crear_evento_activo(app, "Evento Escaneo B")
    with app.app_context():
        entrada = EntradaEvento(
            evento_id=evento_id, woo_order_id=888, estado_pedido="completed",
            token_pase="tok-valido-1", nombre_cliente="Piloto Uno",
        )
        db.session.add(entrada)
        db.session.commit()
    try:
        resp = auth_client.post(
            f"/autoclub/eventos/{evento_id}/escanear/validar",
            data=json.dumps({"token": "tok-valido-1"}),
            content_type="application/json",
            headers={"X-CSRFToken": auth_csrf_token},
        )
        payload = resp.get_json()
        assert resp.status_code == 200
        assert payload["resultado"] == "valida"
        assert payload["entrada"]["nombre_cliente"] == "Piloto Uno"

        # Segundo escaneo del mismo token: ya escaneada
        resp2 = auth_client.post(
            f"/autoclub/eventos/{evento_id}/escanear/validar",
            data=json.dumps({"token": "tok-valido-1"}),
            content_type="application/json",
            headers={"X-CSRFToken": auth_csrf_token},
        )
        payload2 = resp2.get_json()
        assert payload2["resultado"] == "ya_escaneada"
    finally:
        _borrar_evento(app, evento_id)


def test_escanear_pedido_no_aprobado(auth_client, auth_csrf_token, app):
    evento_id = _crear_evento_activo(app, "Evento Escaneo C")
    with app.app_context():
        entrada = EntradaEvento(
            evento_id=evento_id, woo_order_id=999, estado_pedido="pending",
            token_pase="tok-pendiente",
        )
        db.session.add(entrada)
        db.session.commit()
    try:
        resp = auth_client.post(
            f"/autoclub/eventos/{evento_id}/escanear/validar",
            data=json.dumps({"token": "tok-pendiente"}),
            content_type="application/json",
            headers={"X-CSRFToken": auth_csrf_token},
        )
        assert resp.get_json()["resultado"] == "no_valida"
    finally:
        _borrar_evento(app, evento_id)


# ── Filtro por producto (varios eventos vendiéndose a la vez) ───────

def test_pedido_se_asigna_al_evento_de_su_producto_no_al_activo(app):
    from app.services.evento_sync import procesar_pedido_evento

    with app.app_context():
        Evento.query.filter_by(activo=True).update({"activo": False})
        db.session.commit()
        evento_v = Evento(nombre="V Autocross", slug="v-autocross", woo_producto_ids="111,222", activo=True)
        evento_iv = Evento(nombre="IV Autocross (cerrado)", slug="iv-autocross", woo_producto_ids="999", activo=False)
        db.session.add_all([evento_v, evento_iv])
        db.session.commit()
        v_id, iv_id = evento_v.id, evento_iv.id

    try:
        with app.app_context():
            # Pedido de un producto del IV (no del evento activo) -> va al IV, no al V.
            pedido = _pedido_woo(order_id=7001, product_id=999, token="tok-iv")
            entrada = procesar_pedido_evento(pedido)
            db.session.commit()
            assert entrada is not None
            assert entrada.evento_id == iv_id

            # Pedido de un producto del V -> va al V.
            pedido2 = _pedido_woo(order_id=7002, product_id=222, token="tok-v")
            entrada2 = procesar_pedido_evento(pedido2)
            db.session.commit()
            assert entrada2.evento_id == v_id

            # Pedido de un producto que no pertenece a ningún evento con
            # filtro configurado -> se ignora (no se cuela en el activo).
            pedido3 = _pedido_woo(order_id=7003, product_id=555, token="tok-otro")
            entrada3 = procesar_pedido_evento(pedido3)
            assert entrada3 is None
    finally:
        _borrar_evento(app, v_id)
        _borrar_evento(app, iv_id)


# ── Sincronización manual/automática ────────────────────────────────

def test_sync_pedidos_evento_sin_config_no_hace_nada(app):
    app.config["EVENTOS_WOO_BASE_URL"] = ""
    app.config["EVENTOS_WOO_CONSUMER_KEY"] = ""
    app.config["EVENTOS_WOO_CONSUMER_SECRET"] = ""
    from app.services.evento_sync import sync_pedidos_evento
    with app.app_context():
        stats = sync_pedidos_evento()
    assert stats == {"nuevas": 0, "actualizadas": 0, "ignoradas": 0, "errores": 0}


def test_sync_pedidos_evento_crea_y_actualiza(app):
    evento_id = _crear_evento_activo(app, "Evento Sync")
    app.config["EVENTOS_WOO_BASE_URL"] = "https://entradas.example.com"
    app.config["EVENTOS_WOO_CONSUMER_KEY"] = "ck_test"
    app.config["EVENTOS_WOO_CONSUMER_SECRET"] = "cs_test"
    try:
        pagina_1 = [_pedido_woo(order_id=8001, token="tok-sync-1"), _pedido_woo(order_id=8002, token="tok-sync-2")]

        mock_resp = MagicMock()
        mock_resp.json.return_value = pagina_1
        mock_resp.headers = {"X-WP-TotalPages": "1"}
        mock_resp.raise_for_status = MagicMock()

        from app.services.evento_sync import sync_pedidos_evento
        with app.app_context():
            with patch("app.services.evento_sync.requests.get", return_value=mock_resp):
                stats = sync_pedidos_evento(max_pages=5)
            assert stats["nuevas"] == 2
            assert EntradaEvento.query.filter_by(evento_id=evento_id).count() == 2

            # Segunda pasada con los mismos pedidos: deben actualizarse, no duplicarse.
            with patch("app.services.evento_sync.requests.get", return_value=mock_resp):
                stats2 = sync_pedidos_evento(max_pages=5)
            assert stats2["actualizadas"] == 2
            assert EntradaEvento.query.filter_by(evento_id=evento_id).count() == 2
    finally:
        _borrar_evento(app, evento_id)


def test_boton_sincronizar_requiere_login(client):
    # Sin login (y sin token CSRF): CSRFProtect corta la petición con 400
    # antes incluso de llegar al login_required, lo cual también bloquea
    # correctamente el acceso no autenticado.
    resp = client.post("/autoclub/eventos/1/sincronizar")
    assert resp.status_code in (302, 400, 401, 403, 404)


# ── Orden por fecha del pedido ───────────────────────────────────────

def test_entradas_se_muestran_por_fecha_de_pedido_mas_reciente_primero(auth_client, app):
    evento_id = _crear_evento_activo(app, "Evento Orden")
    with app.app_context():
        vieja = EntradaEvento(
            evento_id=evento_id, woo_order_id=101, estado_pedido="completed",
            nombre_cliente="Pedido Antiguo", fecha_pedido=datetime(2026, 1, 1, 10, 0),
        )
        reciente = EntradaEvento(
            evento_id=evento_id, woo_order_id=102, estado_pedido="completed",
            nombre_cliente="Pedido Reciente", fecha_pedido=datetime(2026, 8, 20, 10, 0),
        )
        sin_fecha = EntradaEvento(
            evento_id=evento_id, woo_order_id=103, estado_pedido="pending",
            nombre_cliente="Pedido Sin Fecha",
        )
        db.session.add_all([vieja, reciente, sin_fecha])
        db.session.commit()
    try:
        resp = auth_client.get(f"/autoclub/eventos/{evento_id}")
        html = resp.get_data(as_text=True)
        pos_reciente = html.index("Pedido Reciente")
        pos_antiguo = html.index("Pedido Antiguo")
        assert pos_reciente < pos_antiguo, "el pedido más reciente debe aparecer antes que el antiguo"
    finally:
        _borrar_evento(app, evento_id)


# ── Filtro por tipo de entrada ───────────────────────────────────────

def test_filtro_por_tipo_de_entrada(auth_client, app):
    evento_id = _crear_evento_activo(app, "Evento Tipo")
    with app.app_context():
        prensa = EntradaEvento(
            evento_id=evento_id, woo_order_id=201, estado_pedido="completed",
            nombre_cliente="Cliente Prensa", tipo_pase="Entradas Prensa V Autocross",
        )
        publico = EntradaEvento(
            evento_id=evento_id, woo_order_id=202, estado_pedido="completed",
            nombre_cliente="Cliente Público", tipo_pase="Entradas V Autocross",
        )
        db.session.add_all([prensa, publico])
        db.session.commit()
    try:
        resp = auth_client.get(f"/autoclub/eventos/{evento_id}?tipo=Entradas+Prensa+V+Autocross")
        html = resp.get_data(as_text=True)
        assert "Cliente Prensa" in html
        assert "Cliente Público" not in html
    finally:
        _borrar_evento(app, evento_id)


# ── Auto-aprobación de entrada general en "processing" ──────────────

def test_entrada_general_en_processing_se_autoaprueba(app):
    from app.services.evento_sync import procesar_pedido_evento
    evento_id = _crear_evento_activo(app, "Evento AutoAprobar General")
    app.config["EVENTOS_WOO_BASE_URL"] = "https://entradas.example.com"
    app.config["EVENTOS_WOO_CONSUMER_KEY"] = "ck_test"
    app.config["EVENTOS_WOO_CONSUMER_SECRET"] = "cs_test"
    try:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        pedido = _pedido_woo(order_id=6001, status="processing", token="tok-general")
        pedido["line_items"] = [{"name": "Entradas V Autocross Feeling Academy Guadalajara", "product_id": 1}]
        with app.app_context():
            with patch("app.services.evento_sync.requests.put", return_value=mock_resp) as mock_put:
                entrada = procesar_pedido_evento(pedido)
                db.session.commit()
            assert mock_put.called
            assert entrada.estado_pedido == "completed"
    finally:
        _borrar_evento(app, evento_id)


def test_entrada_prensa_en_processing_no_se_autoaprueba(app):
    from app.services.evento_sync import procesar_pedido_evento
    evento_id = _crear_evento_activo(app, "Evento NoAutoAprobar Prensa")
    app.config["EVENTOS_WOO_BASE_URL"] = "https://entradas.example.com"
    app.config["EVENTOS_WOO_CONSUMER_KEY"] = "ck_test"
    app.config["EVENTOS_WOO_CONSUMER_SECRET"] = "cs_test"
    try:
        pedido = _pedido_woo(order_id=6002, status="processing", token="tok-prensa-pend")
        pedido["line_items"] = [{"name": "Entradas Prensa V Autocross Feeling Academy Guadalajara", "product_id": 2}]
        with app.app_context():
            with patch("app.services.evento_sync.requests.put") as mock_put:
                entrada = procesar_pedido_evento(pedido)
                db.session.commit()
            assert not mock_put.called
            assert entrada.estado_pedido == "processing"
    finally:
        _borrar_evento(app, evento_id)


def test_entrada_institucional_en_processing_no_se_autoaprueba(app):
    from app.services.evento_sync import procesar_pedido_evento
    evento_id = _crear_evento_activo(app, "Evento NoAutoAprobar Institucional")
    app.config["EVENTOS_WOO_BASE_URL"] = "https://entradas.example.com"
    app.config["EVENTOS_WOO_CONSUMER_KEY"] = "ck_test"
    app.config["EVENTOS_WOO_CONSUMER_SECRET"] = "cs_test"
    try:
        pedido = _pedido_woo(order_id=6003, status="processing", token="tok-inst-pend")
        pedido["line_items"] = [{"name": "Entradas Instituciones V Autocross Feeling Academy Guadalajara", "product_id": 3}]
        with app.app_context():
            with patch("app.services.evento_sync.requests.put") as mock_put:
                entrada = procesar_pedido_evento(pedido)
                db.session.commit()
            assert not mock_put.called
            assert entrada.estado_pedido == "processing"
    finally:
        _borrar_evento(app, evento_id)


# ── Vista de detalle de una entrada ──────────────────────────────────

def test_entrada_detalle_requiere_login(client):
    resp = client.get("/autoclub/eventos/1/entradas/1")
    assert resp.status_code in (302, 401, 403, 404)


def test_entrada_detalle_muestra_datos_de_prensa_y_boton_aprobar(auth_client, app):
    evento_id = _crear_evento_activo(app, "Evento Detalle Entrada")
    with app.app_context():
        entrada = EntradaEvento(
            evento_id=evento_id, woo_order_id=333, estado_pedido="processing",
            nombre_cliente="Periodista Ejemplo", email_cliente="p@example.com",
            tipo_pase="Entradas Prensa V Autocross", dni_prensa="11111111H",
            medio_comunicacion="Canal QA", cargo_prensa="Redactor Jefe",
        )
        db.session.add(entrada)
        db.session.commit()
        eid = entrada.id
    try:
        resp = auth_client.get(f"/autoclub/eventos/{evento_id}/entradas/{eid}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Periodista Ejemplo" in html
        assert "Canal QA" in html
        assert "Redactor Jefe" in html
        assert "Requiere aprobación manual" in html
        assert "Aprobar" in html
    finally:
        _borrar_evento(app, evento_id)


def test_meta_data_institucional_se_mapea_correctamente(app):
    from app.services.evento_sync import procesar_pedido_evento, requiere_aprobacion_manual
    evento_id = _crear_evento_activo(app, "Evento Institucional QA")
    try:
        pedido = {
            "id": 888888, "number": "888888", "status": "on-hold",
            "date_created": "2026-08-25T13:00:00",
            "billing": {"first_name": "Maria", "last_name": "Lopez", "email": "maria@example.com", "phone": "600"},
            "line_items": [{"name": "Entradas Instituciones V Autocross Feeling Academy Guadalajara"}],
            "meta_data": [
                {"id": 1, "key": "cargo_institucional", "value": "Concejala de Deportes"},
                {"id": 2, "key": "institucion", "value": "Ayuntamiento de Guadalajara"},
                {"id": 3, "key": "cif_institucion", "value": "P1900000A"},
                {"id": 4, "key": "num_acompanantes", "value": "3"},
            ],
        }
        with app.app_context():
            entrada = procesar_pedido_evento(pedido)
            db.session.commit()
            assert entrada.cargo_institucional == "Concejala de Deportes"
            assert entrada.institucion == "Ayuntamiento de Guadalajara"
            assert entrada.cif_institucion == "P1900000A"
            assert entrada.num_acompanantes == 3
            assert requiere_aprobacion_manual(entrada.tipo_pase) is True
    finally:
        _borrar_evento(app, evento_id)


def test_entrada_detalle_muestra_datos_institucionales(auth_client, app):
    evento_id = _crear_evento_activo(app, "Evento Detalle Institucional")
    with app.app_context():
        entrada = EntradaEvento(
            evento_id=evento_id, woo_order_id=444, estado_pedido="on-hold",
            nombre_cliente="Institucion Ejemplo", tipo_pase="Entradas Instituciones V Autocross",
            institucion="Diputación de Guadalajara", cif_institucion="P1900000B",
            cargo_institucional="Delegado", num_acompanantes=5,
        )
        db.session.add(entrada)
        db.session.commit()
        eid = entrada.id
    try:
        resp = auth_client.get(f"/autoclub/eventos/{evento_id}/entradas/{eid}")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Diputación de Guadalajara" in html
        assert "P1900000B" in html
        assert "Delegado" in html
    finally:
        _borrar_evento(app, evento_id)
