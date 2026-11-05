"""
Reglajes por evento (Mecánica): evento con curvas, ficha de suspensión del
coche, hoja de sesión (setup + curva a curva + cierre) y que la siguiente
sesión del mismo coche parta del setup anterior.
"""
import re

import pytest

from app.extensions import db
from app.models.vehiculo import Vehiculo
from app.models.reglaje import EventoReglaje, SesionReglaje


def _csrf(client, url):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'csrf_token" value="([^"]+)"', html) or re.search(r'name="csrf-token" content="([^"]+)"', html)
    return m.group(1)


@pytest.fixture()
def coche(app):
    with app.app_context():
        v = Vehiculo(tipo_vehiculo="car_cross", cc_chasis_marca="Yacar", cc_chasis_modelo="MT-07 QA", dorsal="77")
        db.session.add(v)
        db.session.commit()
        vid = v.id
    yield vid
    with app.app_context():
        v = db.session.get(Vehiculo, vid)
        if v:
            db.session.delete(v)
        EventoReglaje.query.filter(EventoReglaje.nombre.like("QA %")).delete(synchronize_session=False)
        db.session.commit()


def test_flujo_completo_de_reglajes(app, auth_client, coche):
    token = _csrf(auth_client, "/mecanica/reglajes")
    resp = auth_client.post("/mecanica/reglajes/eventos/nuevo", data={
        "csrf_token": token, "nombre": "QA MotorLand", "circuito": "MotorLand Aragón",
        "fecha_inicio": "2026-11-07", "curvas_texto": "T1 (Frenada)\nT2\n\nJOKER LAP",
    })
    assert resp.status_code == 302
    with app.app_context():
        evento = EventoReglaje.query.filter_by(nombre="QA MotorLand").first()
        assert evento.curvas == ["T1 (Frenada)", "T2", "JOKER LAP"]
        eid = evento.id

    # Ficha de suspensión del coche
    auth_client.post(f"/mecanica/vehiculos/{coche}/suspension", data={
        "csrf_token": token, "amortiguador": "Öhlins TTX",
        "rebote-tiene": "1", "rebote-max_del": "20", "rebote-max_tras": "18",
    })
    with app.app_context():
        ficha = db.session.get(Vehiculo, coche).ficha_suspension
        assert ficha.maximo("rebote", "tras") == 18
        assert ficha.maximo("comp_baja", "del") is None

    # Primera sesión y su hoja
    auth_client.post(f"/mecanica/reglajes/eventos/{eid}/sesiones/nueva", data={
        "csrf_token": token, "vehiculo_id": coche, "sesion": "Entrenos 1", "piloto_nombre": "Piloto QA",
    })
    with app.app_context():
        sid = SesionReglaje.query.filter_by(evento_id=eid).first().id
    form = _csrf(auth_client, f"/mecanica/reglajes/sesiones/{sid}/editar")
    html = auth_client.get(f"/mecanica/reglajes/sesiones/{sid}/editar").get_data(as_text=True)
    assert "/18" in html  # máx. clicks del eje trasero en la hoja
    resp = auth_client.post(f"/mecanica/reglajes/sesiones/{sid}/editar", data={
        "csrf_token": form, "sesion": "Entrenos 1", "piloto_nombre": "Piloto QA",
        "setup-presion_frio-di": "1,2", "setup-rebote-ti": "8", "setup-rebote-cambio": "Rebote tras. 8/18 → 6/18",
        "setup-altura-del": "210",
        "curva-0-balance": "-3", "curva-0-problemas": ["bloquea", "inventado"], "curva-0-fases": ["ent"],
        "curva-0-diagnostico": "Más freno detrás", "curva-2-balance": "9",
        "sensaciones": ["freno_blando", "otra"], "confianza_piloto": "7",
        "resultado": "mejor", "decision": "queda", "mejor_vuelta_antes": "1:05.2",
    })
    assert resp.status_code == 302
    with app.app_context():
        s = db.session.get(SesionReglaje, sid)
        assert s.setup["presion_frio"]["di"] == 1.2
        assert s.setup["rebote"] == {"ti": 8, "cambio": "Rebote tras. 8/18 → 6/18"}
        assert s.setup["altura"]["del"] == 210
        assert s.curvas["T1 (Frenada)"] == {"balance": -3, "problemas": ["bloquea"], "fases": ["ent"], "diagnostico": "Más freno detrás"}
        assert "JOKER LAP" not in s.curvas  # balance fuera de -5..5 descartado
        assert s.sensaciones == ["freno_blando"]
        assert (s.resultado, s.decision, s.confianza_piloto) == ("mejor", "queda", 7)

    vista = auth_client.get(f"/mecanica/reglajes/sesiones/{sid}").get_data(as_text=True)
    assert "Más freno detrás" in vista and "Rebote tras. 8/18" in vista

    # La siguiente sesión parte del setup anterior, sin los "cambio siguiente salida"
    auth_client.post(f"/mecanica/reglajes/eventos/{eid}/sesiones/nueva", data={
        "csrf_token": form, "vehiculo_id": coche, "sesion": "Manga 1", "copiar_setup": "1",
    })
    with app.app_context():
        s2 = SesionReglaje.query.filter_by(evento_id=eid, sesion="Manga 1").first()
        assert s2.setup["rebote"] == {"ti": 8}
        assert s2.piloto_nombre == "Piloto QA"
        sid2 = s2.id
    assert auth_client.get(f"/mecanica/reglajes/sesiones/{sid2}").status_code == 200
    assert auth_client.get(f"/mecanica/reglajes/eventos/{eid}").status_code == 200
    assert auth_client.get(f"/mecanica/vehiculos/{coche}").status_code == 200


def test_seguir_editando_no_acepta_anclas_arbitrarias(app, auth_client, coche):
    with app.app_context():
        e = EventoReglaje(nombre="QA ancla", fecha_inicio=__import__("datetime").date(2026, 1, 1))
        db.session.add(e)
        db.session.flush()
        s = SesionReglaje(evento_id=e.id, vehiculo_id=coche, sesion="Manga")
        db.session.add(s)
        db.session.commit()
        sid = s.id
    token = _csrf(auth_client, f"/mecanica/reglajes/sesiones/{sid}/editar")
    resp = auth_client.post(f"/mecanica/reglajes/sesiones/{sid}/editar",
                            data={"csrf_token": token, "sesion": "Manga", "seguir": "x\"><script>"})
    assert resp.headers["Location"].endswith("#datos")


def test_ficha_suspension_volver_externo_se_ignora(app, auth_client, coche):
    token = _csrf(auth_client, f"/mecanica/vehiculos/{coche}/suspension")
    resp = auth_client.post(f"/mecanica/vehiculos/{coche}/suspension",
                            data={"csrf_token": token, "volver": "//evil.example.com"})
    assert "evil.example.com" not in resp.headers["Location"]


def test_autoguardado_y_valores_heredados(app, auth_client, coche):
    import json
    from datetime import date
    with app.app_context():
        e = EventoReglaje(nombre="QA autoguardado", fecha_inicio=date(2026, 2, 1), curvas_texto="T1\nT2")
        db.session.add(e)
        db.session.flush()
        s = SesionReglaje(evento_id=e.id, vehiculo_id=coche, sesion="Entrenos 1", piloto_nombre="Ana QA")
        db.session.add(s)
        db.session.commit()
        eid, sid = e.id, s.id
    url = f"/mecanica/reglajes/sesiones/{sid}/editar"
    token = _csrf(auth_client, url)

    # El autoguardado recibe JSON con el progreso por sección
    resp = auth_client.post(url, headers={"X-Requested-With": "fetch"}, data={
        "csrf_token": token, "sesion": "Entrenos 1", "piloto_nombre": "Ana QA",
        "setup-presion_frio-di": "1.15", "curva-0-tipo": "Horquilla lenta en tierra", "curva-1-balance": "2",
        "setup-presion_frio-cambio": "Bajar 0.05",
    })
    assert resp.status_code == 200 and resp.is_json
    assert resp.json["progreso"] == {"setup": True, "piloto": True, "diagnostico": False, "cierre": False}

    # La siguiente salida hereda piloto, setup (sin cambios planeados) y tipos de curva
    auth_client.post(f"/mecanica/reglajes/eventos/{eid}/sesiones/nueva",
                     data={"csrf_token": token, "vehiculo_id": coche, "sesion": "Entrenos 2", "copiar_setup": "1"})
    with app.app_context():
        s2 = SesionReglaje.query.filter_by(evento_id=eid, sesion="Entrenos 2").first()
        assert s2.piloto_nombre == "Ana QA"
        assert s2.setup == {"presion_frio": {"di": 1.15}}
        assert s2.curvas == {"T1": {"tipo": "Horquilla lenta en tierra"}}
        assert s2.fecha_hora is not None
        sid2 = s2.id
    html = auth_client.get(f"/mecanica/reglajes/sesiones/{sid2}/editar").get_data(as_text=True)
    assert "Planeado en «Entrenos 1»" in html and "Bajar 0.05" in html

    # No se puede repetir el mismo nombre de salida para el mismo coche
    auth_client.post(f"/mecanica/reglajes/eventos/{eid}/sesiones/nueva",
                     data={"csrf_token": token, "vehiculo_id": coche, "sesion": "Entrenos 2"})
    with app.app_context():
        assert SesionReglaje.query.filter_by(evento_id=eid, sesion="Entrenos 2").count() == 1

    # La página del evento propone la siguiente salida
    assert 'value="Entrenos 3"' in auth_client.get(f"/mecanica/reglajes/eventos/{eid}").get_data(as_text=True)
