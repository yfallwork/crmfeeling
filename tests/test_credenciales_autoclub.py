"""Credenciales de acceso del Autoclub (Información): editar y eliminar."""
import re

from app.extensions import db
from app.models.autoclub_info import AutoclubCredencial


def _csrf(client, url):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'csrf_token" value="([^"]+)"', html) or re.search(r'name="csrf-token" content="([^"]+)"', html)
    return m.group(1)


def test_editar_y_eliminar_credencial(app, auth_client):
    with app.app_context():
        c = AutoclubCredencial(nombre='Portal "QA" d\'Aragón', url="https://x.example", usuario="u", password='p"<x', notas="n")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    html = auth_client.get("/autoclub/informacion").get_data(as_text=True)
    # El botón Editar lleva los datos en atributos escapados (comillas incluidas)
    assert 'data-nombre="Portal &#34;QA&#34; d&#39;Aragón"' in html
    assert 'onclick="abrirEditarCred' not in html
    token = _csrf(auth_client, "/autoclub/informacion")

    resp = auth_client.post(f"/autoclub/informacion/credencial/{cid}/editar", data={
        "csrf_token": token, "nombre": "Portal QA 2", "usuario": "u2", "password": "", "notas": ""})
    assert resp.status_code == 302
    with app.app_context():
        c = db.session.get(AutoclubCredencial, cid)
        assert c.nombre == "Portal QA 2" and c.usuario == "u2"

    resp = auth_client.post(f"/autoclub/informacion/credencial/{cid}/eliminar", data={"csrf_token": token})
    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(AutoclubCredencial, cid) is None


def test_token_caducado_vuelve_a_la_pagina_con_aviso(app, auth_client):
    with app.app_context():
        c = AutoclubCredencial(nombre="QA caducado")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    resp = auth_client.post(f"/autoclub/informacion/credencial/{cid}/eliminar",
                            data={"csrf_token": "caducado"},
                            headers={"Referer": "http://localhost/autoclub/informacion"})
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/autoclub/informacion")
    html = auth_client.get("/autoclub/informacion").get_data(as_text=True)
    assert "ha caducado" in html
    with app.app_context():
        assert db.session.get(AutoclubCredencial, cid) is not None  # no se borró
        db.session.delete(db.session.get(AutoclubCredencial, cid))
        db.session.commit()
    # Referer externo: no se redirige fuera
    resp = auth_client.post("/autoclub/informacion/credencial/999999/eliminar",
                            data={"csrf_token": "x"}, headers={"Referer": "https://evil.example.com/a"})
    assert "evil.example.com" not in resp.headers["Location"]
