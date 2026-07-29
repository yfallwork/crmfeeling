"""
Verifica la gestión de usuarios en Configuración: solo admin puede
crear/editar/eliminar cuentas, los permisos por módulo restringen el acceso
de los roles no-admin, y las salvaguardas (no auto-eliminarse, no dejar la
app sin ningún admin) funcionan.
"""
from app.extensions import db
from app.models.usuario import Usuario


def _crear_gestor_via_admin(auth_client, auth_csrf_token, modulos=None, autoclub_secciones=None,
                             nombre="QA Gestor", username="qa_gestor"):
    resp = auth_client.post(
        "/configuracion/usuarios/nuevo",
        data={
            "nombre": nombre,
            "username": username,
            "email": f"{username}@example.com",
            "password": "qa-password-123",
            "rol": "gestor",
            "activo": "on",
            "modulos": modulos or [],
            "autoclub_secciones": autoclub_secciones or [],
            "csrf_token": auth_csrf_token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with auth_client.application.app_context():
        return Usuario.query.filter_by(username=username).first().id


def _login(client, email, password, csrf_token):
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": csrf_token},
        follow_redirects=True,
    )


def test_admin_puede_crear_editar_y_eliminar_usuario(auth_client, auth_csrf_token, app):
    user_id = _crear_gestor_via_admin(auth_client, auth_csrf_token, modulos=["clientes"])

    resp = auth_client.get("/configuracion/usuarios")
    assert resp.status_code == 200
    assert b"QA Gestor" in resp.data

    # Editar: le quitamos el módulo y le añadimos reservas
    edit_page = auth_client.get(f"/configuracion/usuarios/{user_id}/editar")
    from tests.conftest import _extraer_csrf_token
    token = _extraer_csrf_token(edit_page.get_data(as_text=True))
    resp = auth_client.post(
        f"/configuracion/usuarios/{user_id}/editar",
        data={
            "nombre": "QA Gestor Editado",
            "username": "qa_gestor",
            "email": "qa_gestor@example.com",
            "password": "",
            "rol": "gestor",
            "activo": "on",
            "modulos": ["reservas"],
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        u = Usuario.query.get(user_id)
        assert u.nombre == "QA Gestor Editado"
        assert u.modulos_permitidos == ["reservas"]

    # Eliminar
    resp = auth_client.post(
        f"/configuracion/usuarios/{user_id}/eliminar",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        assert Usuario.query.get(user_id) is None


def test_no_admin_no_puede_acceder_a_gestion_usuarios(auth_client, auth_csrf_token, app):
    user_id = _crear_gestor_via_admin(auth_client, auth_csrf_token, modulos=["clientes"], username="qa_no_admin")

    client = app.test_client()  # sesión anónima nueva, independiente de auth_client
    login_page = client.get("/login")
    from tests.conftest import _extraer_csrf_token
    token = _extraer_csrf_token(login_page.get_data(as_text=True))
    _login(client, "qa_no_admin@example.com", "qa-password-123", token)

    resp = client.get("/configuracion/usuarios")
    assert resp.status_code == 403

    with app.app_context():
        db.session.delete(Usuario.query.get(user_id))
        db.session.commit()


def test_permisos_restringen_acceso_a_modulos(auth_client, auth_csrf_token, app):
    user_id = _crear_gestor_via_admin(auth_client, auth_csrf_token, modulos=["clientes"], username="qa_restringido")

    client = app.test_client()  # sesión anónima nueva, independiente de auth_client
    login_page = client.get("/login")
    from tests.conftest import _extraer_csrf_token
    token = _extraer_csrf_token(login_page.get_data(as_text=True))
    _login(client, "qa_restringido@example.com", "qa-password-123", token)

    # Tiene acceso a clientes (permitido)
    resp = client.get("/clientes/")
    assert resp.status_code == 200

    # No tiene acceso a reservas (no permitido) -> 403
    resp = client.get("/reservas/")
    assert resp.status_code == 403

    with app.app_context():
        db.session.delete(Usuario.query.get(user_id))
        db.session.commit()


def test_permisos_restringen_secciones_internas_de_autoclub(auth_client, auth_csrf_token, app):
    user_id = _crear_gestor_via_admin(
        auth_client, auth_csrf_token,
        modulos=["autoclub"], autoclub_secciones=["pilotos"],
        username="qa_autoclub",
    )

    client = app.test_client()
    login_page = client.get("/login")
    from tests.conftest import _extraer_csrf_token
    token = _extraer_csrf_token(login_page.get_data(as_text=True))
    _login(client, "qa_autoclub@example.com", "qa-password-123", token)

    # Tiene acceso al módulo autoclub y a la sección "pilotos"
    resp = client.get("/autoclub/")
    assert resp.status_code == 200
    resp = client.get("/autoclub/pilotos")
    assert resp.status_code == 200

    # No tiene acceso a la sección "vehiculos" dentro de autoclub -> 403
    resp = client.get("/autoclub/vehiculos")
    assert resp.status_code == 403

    with app.app_context():
        db.session.delete(Usuario.query.get(user_id))
        db.session.commit()


def test_admin_no_puede_quitarse_a_si_mismo_el_rol(auth_client, auth_csrf_token, app):
    from tests.conftest import ADMIN_EMAIL
    with app.app_context():
        admin = Usuario.query.filter_by(email=ADMIN_EMAIL).first()
        admin_id = admin.id

    resp = auth_client.post(
        f"/configuracion/usuarios/{admin_id}/editar",
        data={
            "nombre": "Admin",
            "username": "",
            "email": ADMIN_EMAIL,
            "password": "",
            "rol": "gestor",
            "activo": "on",
            "modulos": [],
            "csrf_token": auth_csrf_token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "quitarte a ti mismo".encode("utf-8") in resp.data
    with app.app_context():
        assert Usuario.query.get(admin_id).rol == "admin"


def test_no_se_puede_eliminar_el_ultimo_admin(auth_client, auth_csrf_token, app):
    from tests.conftest import ADMIN_EMAIL
    with app.app_context():
        admins = Usuario.query.filter_by(rol="admin").all()
        admin_ids = [a.id for a in admins]
        current_admin_id = Usuario.query.filter_by(email=ADMIN_EMAIL).first().id

    # Eliminamos a todos los demás admins salvo el que tiene la sesión actual
    otros = [i for i in admin_ids if i != current_admin_id]
    for oid in otros:
        auth_client.post(f"/configuracion/usuarios/{oid}/eliminar",
                          data={"csrf_token": auth_csrf_token}, follow_redirects=True)

    with app.app_context():
        assert Usuario.query.filter_by(rol="admin").count() == 1

    # Ahora sí queda uno solo: la propia sesión no puede eliminarse (auto-eliminación bloqueada primero)
    resp = auth_client.post(f"/configuracion/usuarios/{current_admin_id}/eliminar",
                             data={"csrf_token": auth_csrf_token}, follow_redirects=True)
    assert resp.status_code == 200
    assert "no puedes eliminar tu propia cuenta".encode("utf-8") in resp.data.lower()
    with app.app_context():
        assert Usuario.query.get(current_admin_id) is not None
