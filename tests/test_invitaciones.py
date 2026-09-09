"""
Verifica el módulo de Invitaciones: creación individual (token → pedido
WooCommerce → QR → email), reenvío, detección de duplicados, carga por
lote vía CSV (validación completa antes de procesar, previsualización,
fallos parciales) y que el QR generado sea escaneable por el mecanismo de
verificación ya existente en Eventos sin lógica nueva.
"""
import io
import json
import os
from unittest.mock import patch, MagicMock

from app.extensions import db
from app.models.evento import Evento, EntradaEvento
from app.models.invitacion import Invitacion


def _woo_config(app):
    app.config["EVENTOS_WOO_BASE_URL"] = "https://entradas.example.com"
    app.config["EVENTOS_WOO_CONSUMER_KEY"] = "ck_test"
    app.config["EVENTOS_WOO_CONSUMER_SECRET"] = "cs_test"
    app.config["WOO_PRODUCT_ID_INVITACION"] = "999000"
    app.config["MAIL_PRENSA_USERNAME"] = "escuderia@autoclubladehesa.com"
    app.config["MAIL_PRENSA_PASSWORD"] = "fake-pass"
    app.config["MAIL_PRENSA_SENDER"] = "escuderia@autoclubladehesa.com"


def _limpiar(app):
    with app.app_context():
        Invitacion.query.delete()
        EntradaEvento.query.delete()
        Evento.query.delete()
        db.session.commit()


def _crear_evento_activo(app, nombre="Evento Invitaciones"):
    with app.app_context():
        Evento.query.filter_by(activo=True).update({"activo": False})
        db.session.commit()
        e = Evento(nombre=nombre, slug=nombre.lower().replace(" ", "-"), activo=True)
        db.session.add(e)
        db.session.commit()
        return e.id


def _mock_woo_post(order_id=5001):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"id": order_id})
    return mock_resp


# ── Creación individual ─────────────────────────────────────────────────

def test_crear_invitacion_individual_ok(auth_client, auth_csrf_token, app):
    _woo_config(app)
    evento_id = _crear_evento_activo(app)
    try:
        with patch("app.services.invitacion_service.requests.post", return_value=_mock_woo_post(6001)) as mock_post, \
             patch("app.services.invitacion_service.enviar_smtp_prensa") as mock_smtp:
            resp = auth_client.post(
                "/autoclub/eventos/invitaciones",
                data={
                    "csrf_token": auth_csrf_token,
                    "nombre": "Ayuntamiento de Prueba",
                    "email": "ayto@example.com",
                    "tipo": "institucion",
                    "notas": "Contacto: concejalía",
                },
                follow_redirects=True,
            )
        assert resp.status_code == 200
        assert mock_post.called
        body = mock_post.call_args[1]["json"]
        assert body["status"] == "completed"
        assert body["line_items"] == [{"product_id": 999000, "quantity": 1}]
        assert {"key": "tipo_invitacion", "value": "institucion"} in body["meta_data"]
        assert mock_smtp.called

        with app.app_context():
            inv = Invitacion.query.filter_by(email="ayto@example.com").first()
            assert inv is not None
            assert inv.woo_order_id == 6001
            assert inv.token
            assert inv.qr_path and inv.qr_path.endswith(f"{inv.token}.png")
            qr_file = os.path.join(app.root_path, "static", inv.qr_path)
            assert os.path.isfile(qr_file)
            os.remove(qr_file)

            evento = Evento.query.get(evento_id)
            assert "999000" in evento.producto_ids_lista
    finally:
        _limpiar(app)


def test_fallo_woocommerce_no_deja_registro_a_medias(auth_client, auth_csrf_token, app):
    _woo_config(app)
    _crear_evento_activo(app)
    try:
        import requests
        with patch("app.services.invitacion_service.requests.post", side_effect=requests.RequestException("boom")):
            resp = auth_client.post(
                "/autoclub/eventos/invitaciones",
                data={
                    "csrf_token": auth_csrf_token,
                    "nombre": "Fallará",
                    "email": "fallara@example.com",
                    "tipo": "vip",
                    "notas": "",
                },
                follow_redirects=True,
            )
        assert resp.status_code == 200
        with app.app_context():
            assert Invitacion.query.filter_by(email="fallara@example.com").first() is None
    finally:
        _limpiar(app)


def test_duplicado_email_avisa_y_no_crea_otra(auth_client, auth_csrf_token, app):
    _woo_config(app)
    _crear_evento_activo(app)
    try:
        with patch("app.services.invitacion_service.requests.post", return_value=_mock_woo_post(6002)), \
             patch("app.services.invitacion_service.enviar_smtp_prensa"):
            auth_client.post(
                "/autoclub/eventos/invitaciones",
                data={"csrf_token": auth_csrf_token, "nombre": "Primera", "email": "dup@example.com",
                      "tipo": "vip", "notas": ""},
                follow_redirects=True,
            )
            with patch("app.services.invitacion_service.requests.post") as mock_post_2:
                resp = auth_client.post(
                    "/autoclub/eventos/invitaciones",
                    data={"csrf_token": auth_csrf_token, "nombre": "Segunda", "email": "dup@example.com",
                          "tipo": "vip", "notas": ""},
                    follow_redirects=True,
                )
            assert resp.status_code == 200
            assert not mock_post_2.called
            assert "Ya existe una invitación" in resp.get_data(as_text=True)

        with app.app_context():
            assert Invitacion.query.filter_by(email="dup@example.com").count() == 1
    finally:
        _limpiar(app)


def test_reenviar_no_crea_pedido_nuevo(auth_client, auth_csrf_token, app):
    _woo_config(app)
    _crear_evento_activo(app)
    try:
        with patch("app.services.invitacion_service.requests.post", return_value=_mock_woo_post(6003)), \
             patch("app.services.invitacion_service.enviar_smtp_prensa"):
            auth_client.post(
                "/autoclub/eventos/invitaciones",
                data={"csrf_token": auth_csrf_token, "nombre": "Reenvíame", "email": "reenvio@example.com",
                      "tipo": "otro", "notas": ""},
                follow_redirects=True,
            )
        with app.app_context():
            inv_id = Invitacion.query.filter_by(email="reenvio@example.com").first().id

        with patch("app.services.invitacion_service.requests.post") as mock_post_reenvio, \
             patch("app.services.invitacion_service.enviar_smtp_prensa") as mock_smtp_reenvio:
            resp = auth_client.post(
                f"/autoclub/eventos/invitaciones/{inv_id}/reenviar",
                data={"csrf_token": auth_csrf_token},
                follow_redirects=True,
            )
        assert resp.status_code == 200
        assert not mock_post_reenvio.called
        assert mock_smtp_reenvio.called
        with app.app_context():
            inv = Invitacion.query.get(inv_id)
            assert inv.woo_order_id == 6003
    finally:
        _limpiar(app)


# ── QR compatible con el escáner de Eventos sin lógica nueva ────────────

def test_qr_de_invitacion_es_escaneable_por_el_flujo_existente(auth_client, auth_csrf_token, app):
    _woo_config(app)
    evento_id = _crear_evento_activo(app)
    try:
        with patch("app.services.invitacion_service.requests.post", return_value=_mock_woo_post(6004)), \
             patch("app.services.invitacion_service.enviar_smtp_prensa"):
            auth_client.post(
                "/autoclub/eventos/invitaciones",
                data={"csrf_token": auth_csrf_token, "nombre": "Invitada VIP", "email": "vip@example.com",
                      "tipo": "vip", "notas": ""},
                follow_redirects=True,
            )
        with app.app_context():
            inv = Invitacion.query.filter_by(email="vip@example.com").first()
            token = inv.token
            # Simula lo que haría el webhook al recibir el pedido ya creado
            # en WooCommerce (mismo mecanismo que prensa/institucional/general).
            entrada = EntradaEvento(
                evento_id=evento_id, woo_order_id=6004, estado_pedido="completed",
                token_pase=token, nombre_cliente="Invitada VIP", email_cliente="vip@example.com",
                tipo_pase="Invitación",
            )
            db.session.add(entrada)
            db.session.commit()

        resp = auth_client.post(
            f"/autoclub/eventos/{evento_id}/escanear/validar",
            data=json.dumps({"token": token}),
            content_type="application/json",
            headers={"X-CSRFToken": auth_csrf_token},
        )
        assert resp.status_code == 200
        payload = resp.get_json()
        assert payload["resultado"] == "valida"

        with app.app_context():
            assert Invitacion.query.filter_by(email="vip@example.com").first().usado is True
    finally:
        _limpiar(app)


# ── CSV ──────────────────────────────────────────────────────────────────

def test_plantilla_csv_descarga_con_cabeceras_correctas(auth_client):
    resp = auth_client.get("/autoclub/eventos/invitaciones/plantilla-csv")
    assert resp.status_code == 200
    texto = resp.get_data(as_text=True).lstrip("﻿")
    assert texto.splitlines()[0].strip() == "nombre,email,tipo,notas"


def test_csv_con_cabeceras_incorrectas_no_procesa_nada(auth_client, auth_csrf_token, app):
    _woo_config(app)
    try:
        csv_malo = "nombre,correo,tipo\nFulano,fulano@example.com,vip\n"
        data = {"csrf_token": auth_csrf_token, "archivo_csv": (io.BytesIO(csv_malo.encode()), "malo.csv")}
        resp = auth_client.post(
            "/autoclub/eventos/invitaciones/lote/previsualizar",
            data=data, content_type="multipart/form-data", follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "cabeceras" in resp.get_data(as_text=True).lower()
        with app.app_context():
            assert Invitacion.query.count() == 0
    finally:
        _limpiar(app)


def test_csv_con_fila_invalida_reporta_error_sin_procesar_nada(auth_client, auth_csrf_token, app):
    _woo_config(app)
    try:
        csv_malo = "nombre,email,tipo,notas\nFulano,no-es-email,vip,\nMengana,mengana@example.com,tipo-raro,\n"
        data = {"csrf_token": auth_csrf_token, "archivo_csv": (io.BytesIO(csv_malo.encode()), "malo.csv")}
        with patch("app.services.invitacion_service.requests.post") as mock_post:
            resp = auth_client.post(
                "/autoclub/eventos/invitaciones/lote/previsualizar",
                data=data, content_type="multipart/form-data", follow_redirects=True,
            )
        assert resp.status_code == 200
        assert not mock_post.called
        with app.app_context():
            assert Invitacion.query.count() == 0
    finally:
        _limpiar(app)


def test_csv_valido_previsualiza_y_confirmar_crea_invitaciones(auth_client, auth_csrf_token, app):
    _woo_config(app)
    _crear_evento_activo(app)
    try:
        csv_bueno = (
            "nombre,email,tipo,notas\n"
            "Patrocinador Uno,patro1@example.com,patrocinador,\n"
            "Patrocinador Dos,patro2@example.com,patrocinador,nota\n"
        )
        data = {"csrf_token": auth_csrf_token, "archivo_csv": (io.BytesIO(csv_bueno.encode()), "bueno.csv")}
        resp = auth_client.post(
            "/autoclub/eventos/invitaciones/lote/previsualizar",
            data=data, content_type="multipart/form-data", follow_redirects=True,
        )
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Confirmar y enviar 2 invitaciones" in html

        m = __import__("re").search(r"name=\"filas_json\" value='(.*?)'", html)
        assert m, "No se encontró el campo oculto filas_json en la previsualización"
        import html as _html_mod
        filas_json = _html_mod.unescape(m.group(1))

        with patch("app.services.invitacion_service.requests.post", side_effect=[_mock_woo_post(7001), _mock_woo_post(7002)]), \
             patch("app.services.invitacion_service.enviar_smtp_prensa"):
            resp2 = auth_client.post(
                "/autoclub/eventos/invitaciones/lote/confirmar",
                data={"csrf_token": auth_csrf_token, "filas_json": filas_json},
                follow_redirects=True,
            )
        assert resp2.status_code == 200
        with app.app_context():
            invs = Invitacion.query.order_by(Invitacion.email).all()
            assert [i.email for i in invs] == ["patro1@example.com", "patro2@example.com"]
            for inv in invs:
                if inv.qr_path:
                    qr_file = os.path.join(app.root_path, "static", inv.qr_path)
                    if os.path.isfile(qr_file):
                        os.remove(qr_file)
    finally:
        _limpiar(app)


def test_csv_fallo_parcial_no_aborta_el_resto_del_lote(auth_client, auth_csrf_token, app):
    _woo_config(app)
    _crear_evento_activo(app)
    try:
        csv_bueno = (
            "nombre,email,tipo,notas\n"
            "Falla,falla@example.com,otro,\n"
            "OK,ok@example.com,otro,\n"
        )
        data = {"csrf_token": auth_csrf_token, "archivo_csv": (io.BytesIO(csv_bueno.encode()), "mixto.csv")}
        resp = auth_client.post(
            "/autoclub/eventos/invitaciones/lote/previsualizar",
            data=data, content_type="multipart/form-data", follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        m = __import__("re").search(r"name=\"filas_json\" value='(.*?)'", html)
        import html as _html_mod
        filas_json = _html_mod.unescape(m.group(1))

        import requests as _requests

        def _post_side_effect(*args, **kwargs):
            if kwargs.get("json", {}).get("billing", {}).get("email") == "falla@example.com":
                raise _requests.RequestException("fallo de red simulado")
            return _mock_woo_post(7100)

        with patch("app.services.invitacion_service.requests.post", side_effect=_post_side_effect), \
             patch("app.services.invitacion_service.enviar_smtp_prensa"):
            resp2 = auth_client.post(
                "/autoclub/eventos/invitaciones/lote/confirmar",
                data={"csrf_token": auth_csrf_token, "filas_json": filas_json},
                follow_redirects=True,
            )
        assert resp2.status_code == 200
        with app.app_context():
            assert Invitacion.query.filter_by(email="ok@example.com").first() is not None
            assert Invitacion.query.filter_by(email="falla@example.com").first() is None
    finally:
        _limpiar(app)


def test_csv_marca_duplicados_y_los_excluye_por_defecto(auth_client, auth_csrf_token, app):
    _woo_config(app)
    _crear_evento_activo(app)
    try:
        with patch("app.services.invitacion_service.requests.post", return_value=_mock_woo_post(6005)), \
             patch("app.services.invitacion_service.enviar_smtp_prensa"):
            auth_client.post(
                "/autoclub/eventos/invitaciones",
                data={"csrf_token": auth_csrf_token, "nombre": "Ya invitado", "email": "yainvitado@example.com",
                      "tipo": "vip", "notas": ""},
                follow_redirects=True,
            )

        csv_con_dup = (
            "nombre,email,tipo,notas\n"
            "Ya invitado,yainvitado@example.com,vip,\n"
            "Nuevo,nuevo@example.com,vip,\n"
        )
        data = {"csrf_token": auth_csrf_token, "archivo_csv": (io.BytesIO(csv_con_dup.encode()), "dup.csv")}
        resp = auth_client.post(
            "/autoclub/eventos/invitaciones/lote/previsualizar",
            data=data, content_type="multipart/form-data", follow_redirects=True,
        )
        html = resp.get_data(as_text=True)
        assert "Confirmar y enviar 1 invitaciones" in html
        assert "Ya invitado" in html
    finally:
        _limpiar(app)
