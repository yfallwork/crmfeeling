"""
Verifica la landing pública (sin login) y el formulario de preinscripción
del proyecto "Selección Femenina de Pilotos de Carcross": validaciones
(rango de edad, campos obligatorios, checkbox de privacidad), guardado
correcto, aislamiento de la ruta pública (no requiere sesión), y el panel
admin dentro de AutoClub para gestionar lo recibido.
"""
import re

from app.extensions import db
from app.models.preinscripcion_carcross import PreinscripcionCarcross


def _extraer_csrf(html):
    m = re.search(r'csrf_token" value="([^"]+)"', html)
    assert m, "No se encontró csrf_token en la landing pública"
    return m.group(1)


def _borrar(app, id_):
    with app.app_context():
        PreinscripcionCarcross.query.filter_by(id=id_).delete()
        db.session.commit()


def test_landing_publica_accesible_sin_login(app):
    client = app.test_client()
    resp = client.get("/seleccion-femenina/")
    assert resp.status_code == 200
    assert "Selección Femenina".encode("utf-8") in resp.data
    assert b'action="/seleccion-femenina/preinscripcion"' in resp.data


def test_preinscripcion_exitosa_sin_login(app):
    client = app.test_client()
    token = _extraer_csrf(client.get("/seleccion-femenina/").get_data(as_text=True))

    resp = client.post(
        "/seleccion-femenina/preinscripcion",
        data={
            "nombre_completo": "Lucía QA Pérez",
            "fecha_nacimiento": "2010-01-15",  # ~16 años
            "localidad": "Guadalajara",
            "email": "lucia.qa@example.com",
            "telefono": "600111222",
            "experiencia_previa": "conduccion_embrague",
            "motivacion": "Quiero ser piloto",
            "acepta_privacidad": "1",
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Preinscripción recibida".encode("utf-8") in resp.data

    with app.app_context():
        p = PreinscripcionCarcross.query.filter_by(email="lucia.qa@example.com").first()
        assert p is not None
        assert p.nombre_completo == "Lucía QA Pérez"
        assert p.acepta_privacidad is True
        assert 14 <= p.edad <= 18
        pid = p.id
    _borrar(app, pid)


def test_preinscripcion_rechaza_fuera_de_rango_de_edad(app):
    client = app.test_client()
    token = _extraer_csrf(client.get("/seleccion-femenina/").get_data(as_text=True))

    resp = client.post(
        "/seleccion-femenina/preinscripcion",
        data={
            "nombre_completo": "QA Mayor De Edad",
            "fecha_nacimiento": "1990-01-01",  # demasiado mayor
            "email": "qa.mayor@example.com",
            "telefono": "600111222",
            "acepta_privacidad": "1",
            "csrf_token": token,
        },
    )
    assert resp.status_code == 400
    assert "14 a 18".encode("utf-8") in resp.data
    with app.app_context():
        assert PreinscripcionCarcross.query.filter_by(email="qa.mayor@example.com").first() is None


def test_preinscripcion_exige_privacidad_y_campos_obligatorios(app):
    client = app.test_client()
    token = _extraer_csrf(client.get("/seleccion-femenina/").get_data(as_text=True))

    resp = client.post(
        "/seleccion-femenina/preinscripcion",
        data={"nombre_completo": "QA Incompleta", "csrf_token": token},
    )
    assert resp.status_code == 400
    with app.app_context():
        assert PreinscripcionCarcross.query.filter_by(nombre_completo="QA Incompleta").first() is None


def test_panel_admin_requiere_login_y_permite_gestionar(auth_client, auth_csrf_token, app):
    # Sin login: la lista admin no es accesible
    anon = app.test_client()
    resp = anon.get("/autoclub/seleccion-femenina")
    assert resp.status_code in (302, 401, 403)

    # Crear una preinscripción real vía la ruta pública
    token = _extraer_csrf(anon.get("/seleccion-femenina/").get_data(as_text=True))
    anon.post(
        "/seleccion-femenina/preinscripcion",
        data={
            "nombre_completo": "QA Panel Admin",
            "fecha_nacimiento": "2009-06-01",
            "email": "qa.paneladmin@example.com",
            "telefono": "600333444",
            "acepta_privacidad": "1",
            "csrf_token": token,
        },
    )
    with app.app_context():
        p = PreinscripcionCarcross.query.filter_by(email="qa.paneladmin@example.com").first()
        assert p is not None
        pid = p.id

    try:
        # El admin (ya logueado en el CRM) sí la ve
        resp = auth_client.get("/autoclub/seleccion-femenina")
        assert resp.status_code == 200
        assert b"QA Panel Admin" in resp.data

        # Puede cambiar su estado
        resp = auth_client.post(
            f"/autoclub/seleccion-femenina/{pid}/estado",
            data={"estado": "contactada", "csrf_token": auth_csrf_token},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        with app.app_context():
            assert PreinscripcionCarcross.query.get(pid).estado == "contactada"

        # Exportar CSV incluye la fila
        resp = auth_client.get("/autoclub/seleccion-femenina/exportar")
        assert resp.status_code == 200
        assert b"QA Panel Admin" in resp.data
    finally:
        _borrar(app, pid)
