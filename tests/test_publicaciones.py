"""
Calendario de publicaciones en redes (Marketing): carga inicial del PDF,
vista mensual, subida de vídeo/foto y descripción, y avisos por email del
contenido pendiente de subir.
"""
import io
import re
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.configuracion import Configuracion
from app.models.publicacion_rrss import PublicacionRRSS, ArchivoPublicacion, DestinatarioAvisoRRSS


def _csrf(client, url):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'csrf_token" value="([^"]+)"', html) or re.search(r'name="csrf-token" content="([^"]+)"', html)
    return m.group(1)


@pytest.fixture()
def carpeta_tmp(app, tmp_path):
    original = app.instance_path
    app.instance_path = str(tmp_path)
    yield tmp_path
    app.instance_path = original


def _nueva(app, **kw):
    with app.app_context():
        datos = dict(fecha=date.today(), titulo="QA publicación", categoria="ventas", tipo="post", estado="pendiente")
        datos.update(kw)
        p = PublicacionRRSS(**datos)
        db.session.add(p)
        db.session.commit()
        return p.id


def _borrar(app, *ids):
    with app.app_context():
        for i in ids:
            p = db.session.get(PublicacionRRSS, i)
            if p:
                db.session.delete(p)
        db.session.commit()


def test_calendario_carga_el_plan_del_pdf(auth_client):
    resp = auth_client.get("/marketing/publicaciones?mes=2026-11")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Así fue el CERX en MotorLand" in html
    assert "Campaña de Navidad" in html
    assert "Noviembre 2026" in html


def test_calendario_requiere_login(client):
    assert client.get("/marketing/publicaciones").status_code in (302, 401)


def test_subir_video_y_descripcion(app, auth_client, carpeta_tmp):
    pid = _nueva(app)
    url = f"/marketing/publicaciones/{pid}"
    try:
        token = _csrf(auth_client, url)
        resp = auth_client.post(f"{url}/archivos", data={
            "csrf_token": token,
            "archivos": [(io.BytesIO(b"\x00\x00\x00\x18ftypmp42" + b"0" * 1000), "reel final.mp4"),
                         (io.BytesIO(b"MZ"), "virus.exe")],
        }, content_type="multipart/form-data", follow_redirects=True)
        html = resp.get_data(as_text=True)
        assert "1 archivo subido" in html
        assert "No se admiten" in html
        with app.app_context():
            p = db.session.get(PublicacionRRSS, pid)
            assert p.estado == "listo"
            assert len(p.archivos) == 1
            a = p.archivos[0]
            aid = a.id
            assert a.es_video
            assert (carpeta_tmp / "uploads" / "publicaciones" / a.nombre_archivo).exists()

        assert auth_client.get(f"/marketing/publicaciones/archivos/{aid}").status_code == 200

        auth_client.post(f"{url}/descripcion", data={"csrf_token": token, "descripcion": "¡Ven a derrapar! #carcross"})
        with app.app_context():
            assert db.session.get(PublicacionRRSS, pid).descripcion == "¡Ven a derrapar! #carcross"

        auth_client.post(f"/marketing/publicaciones/archivos/{aid}/eliminar", data={"csrf_token": token})
        with app.app_context():
            p = db.session.get(PublicacionRRSS, pid)
            assert not p.archivos
            assert p.estado == "pendiente"
    finally:
        _borrar(app, pid)


def test_limite_de_subida_ampliado_solo_para_archivos(app):
    with app.test_request_context("/marketing/publicaciones/1/archivos", method="POST"):
        from flask import request
        assert request.max_content_length > app.config["MAX_CONTENT_LENGTH"]
    with app.test_request_context("/clientes/nuevo", method="POST"):
        from flask import request
        assert request.max_content_length == app.config["MAX_CONTENT_LENGTH"]


def test_resumen_avisa_solo_lo_pendiente_y_una_vez_al_dia(app):
    from app.services import publicaciones_aviso
    hoy = date(2030, 5, 10)
    ids = [
        _nueva(app, fecha=hoy, titulo="QA pendiente hoy"),
        _nueva(app, fecha=hoy + timedelta(days=1), titulo="QA pendiente mañana"),
        _nueva(app, fecha=hoy, titulo="QA ya subida", estado="listo"),
        _nueva(app, fecha=hoy + timedelta(days=5), titulo="QA demasiado lejos"),
    ]
    with app.app_context():
        db.session.add(DestinatarioAvisoRRSS(email="qa.redes@example.com"))
        config = Configuracion.get()
        config.rrss_aviso_activo, config.rrss_aviso_dias, config.rrss_ultimo_resumen = True, 1, None
        db.session.commit()
    try:
        with app.test_request_context(), patch.object(publicaciones_aviso, "_enviar") as enviar:
            n, nd, error = publicaciones_aviso.enviar_resumen(hoy=hoy)
            assert (n, nd, error) == (2, 1, None)
            destinatarios, asunto, html = enviar.call_args.args
            assert destinatarios == ["qa.redes@example.com"]
            assert "QA pendiente hoy" in html and "QA pendiente mañana" in html
            assert "QA ya subida" not in html and "QA demasiado lejos" not in html

            enviar.reset_mock()
            assert publicaciones_aviso.enviar_resumen(hoy=hoy)[0] == 0
            enviar.assert_not_called()
            assert publicaciones_aviso.enviar_resumen(forzar=True, hoy=hoy)[0] == 2
    finally:
        _borrar(app, *ids)
        with app.app_context():
            DestinatarioAvisoRRSS.query.filter_by(email="qa.redes@example.com").delete()
            db.session.commit()


def test_resumen_sin_destinatarios_no_envia(app):
    from app.services import publicaciones_aviso
    with app.test_request_context(), patch.object(publicaciones_aviso, "_enviar") as enviar:
        n, nd, error = publicaciones_aviso.enviar_resumen(forzar=True)
        assert n == 0 and nd == 0 and error
        enviar.assert_not_called()


def test_gestion_de_destinatarios(app, auth_client):
    token = _csrf(auth_client, "/marketing/publicaciones/avisos")
    auth_client.post("/marketing/publicaciones/avisos", data={"csrf_token": token, "accion": "anadir", "email": "QA.Dest@Example.com"})
    auth_client.post("/marketing/publicaciones/avisos", data={"csrf_token": token, "accion": "anadir", "email": "no-es-email"})
    with app.app_context():
        d = DestinatarioAvisoRRSS.query.filter_by(email="qa.dest@example.com").first()
        assert d is not None
        assert DestinatarioAvisoRRSS.query.filter_by(email="no-es-email").first() is None
        did = d.id
    auth_client.post("/marketing/publicaciones/avisos", data={"csrf_token": token, "accion": "quitar", "id": did})
    with app.app_context():
        assert db.session.get(DestinatarioAvisoRRSS, did) is None


def test_en_el_momento_no_avisa_antes_solo_su_mismo_dia(app, auth_client):
    from app.services import publicaciones_aviso
    hoy = date(2030, 6, 10)
    manana = _nueva(app, fecha=hoy + timedelta(days=1), titulo="QA directo mañana", en_directo=True)
    hoy_id = _nueva(app, fecha=hoy, titulo="QA directo hoy", en_directo=True)
    with app.app_context():
        db.session.add(DestinatarioAvisoRRSS(email="qa.directo@example.com"))
        config = Configuracion.get()
        config.rrss_aviso_activo, config.rrss_aviso_dias = True, 1
        db.session.commit()
    try:
        with app.test_request_context(), patch.object(publicaciones_aviso, "_enviar") as enviar:
            assert [p.titulo for p in publicaciones_aviso.pendientes_para_aviso(1, hoy)
                    if p.titulo.startswith("QA directo")] == []
            n, _, error = publicaciones_aviso.enviar_resumen(forzar=True, hoy=hoy)
            assert error is None and n == 1
            _, asunto, html = enviar.call_args.args
            assert "para grabar y publicar hoy" in asunto
            assert "QA directo hoy" in html and "QA directo mañana" not in html

        # El interruptor de la ficha lo activa y desactiva
        token = _csrf(auth_client, f"/marketing/publicaciones/{manana}")
        auth_client.post(f"/marketing/publicaciones/{manana}/en-directo", data={"csrf_token": token})
        with app.app_context():
            assert db.session.get(PublicacionRRSS, manana).en_directo is False
    finally:
        _borrar(app, manana, hoy_id)
        with app.app_context():
            DestinatarioAvisoRRSS.query.filter_by(email="qa.directo@example.com").delete()
            db.session.commit()
