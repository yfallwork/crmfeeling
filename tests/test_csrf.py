"""
Verifica que la protección CSRF global (S1) esté realmente activa:
  - Las rutas POST principales rechazan peticiones sin token.
  - Con un token válido, la petición pasa el filtro CSRF (aunque falle después
    por otra razón de negocio, como credenciales incorrectas).
  - El webhook de WooCommerce sigue exento (se autentica por HMAC, no por sesión).
"""
from datetime import datetime, timedelta

from app.extensions import db
from app.models.cliente import Cliente
from app.models.empresa import Empresa
from app.models.experiencia import TipoExperiencia
from app.models.reserva import Reserva


def test_login_post_sin_csrf_token_es_rechazado(client):
    resp = client.post("/login", data={"email": "admin@crm.local", "password": "cualquiera"})
    assert resp.status_code == 400
    assert b"CSRF" in resp.data


def test_login_post_con_csrf_token_no_es_bloqueado_por_csrf(client, csrf_token):
    # Password incorrecta a propósito: debe fallar por credenciales (200 + flash),
    # nunca por CSRF (400).
    resp = client.post(
        "/login",
        data={"email": "admin@crm.local", "password": "password-incorrecta", "csrf_token": csrf_token},
    )
    assert resp.status_code == 200
    assert b"CSRF" not in resp.data
    assert "incorrectos".encode("utf-8") in resp.data


def test_ruta_autenticada_post_sin_csrf_es_rechazada(auth_client):
    resp = auth_client.post("/clientes/nuevo", data={
        "nombre": "Sin", "apellido": "Token", "email": "sin.token@example.com",
    })
    assert resp.status_code == 400
    assert b"CSRF" in resp.data


def test_ruta_autenticada_post_con_csrf_valido_es_aceptada(auth_client, auth_csrf_token):
    resp = auth_client.post(
        "/clientes/nuevo",
        data={
            "nombre": "Con", "apellido": "Token", "email": "con.token.csrf@example.com",
            "csrf_token": auth_csrf_token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"CSRF" not in resp.data

    # limpieza
    with auth_client.application.app_context():
        Cliente.query.filter_by(email="con.token.csrf@example.com").delete()
        db.session.commit()


def test_cambiar_estado_reserva_sin_csrf_es_rechazado(auth_client, app):
    with app.app_context():
        tipo = TipoExperiencia(nombre="QA Experiencia CSRF")
        cliente = Cliente(nombre="QA", apellido="CSRF", email="qa.csrf.estado@example.com")
        db.session.add_all([tipo, cliente])
        db.session.flush()
        reserva = Reserva(cliente_id=cliente.id, tipo_experiencia_id=tipo.id, estado="pendiente")
        db.session.add(reserva)
        db.session.commit()
        reserva_id = reserva.id

    resp = auth_client.post(f"/reservas/{reserva_id}/estado", data={"estado": "reservado"})
    assert resp.status_code == 400
    assert b"CSRF" in resp.data

    with app.app_context():
        Reserva.query.filter_by(id=reserva_id).delete()
        Cliente.query.filter_by(email="qa.csrf.estado@example.com").delete()
        TipoExperiencia.query.filter_by(nombre="QA Experiencia CSRF").delete()
        db.session.commit()


def test_woocommerce_sync_sin_csrf_es_rechazado(auth_client):
    resp = auth_client.post("/woocommerce/sync")
    assert resp.status_code == 400
    assert b"CSRF" in resp.data


def test_webhook_woocommerce_sigue_exento_de_csrf(client):
    """El webhook se autentica por firma HMAC (S4), no por sesión de navegador,
    así que debe seguir siendo llamable sin token CSRF. Al no enviar una firma
    válida, debe fallar por firma inválida (401) y no por CSRF (400)."""
    resp = client.post(
        "/woocommerce/webhook",
        json={"id": 1},
        headers={"X-WC-Webhook-Topic": "order.created"},
    )
    assert resp.status_code in (401, 503)
    assert b"CSRF" not in resp.data
