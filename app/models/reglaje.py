"""
Reglajes de carcross por evento (Mecánica): basado en la "Hoja del
Ingeniero" y la "Ficha Feedback del Piloto" de Feeling Academy.

- FichaSuspension: una por coche, qué ajustes tienen sus amortiguadores y
  cuántos clicks máximos (criterio del equipo: 0 = cerrado del todo).
- EventoReglaje: una prueba o jornada (circuito, fechas, curvas a evaluar).
- SesionReglaje: cada salida (entrenos / manga) de un coche con su piloto:
  setup, curva a curva (feedback del piloto + diagnóstico del ingeniero),
  sensaciones, cierre y apuntes. Las partes tabulares se guardan en JSON.
"""
import json
from datetime import datetime

from app.extensions import db

CURVAS_POR_DEFECTO = "T1 (Frenada)\nT2\nT3\nT4\nT5\nT6\nT7\nT8\nT9\nT10 (Meta)\nJOKER LAP"

RUEDAS = [("di", "Del. Izq."), ("dd", "Del. Dcha."), ("ti", "Tras. Izq."), ("td", "Tras. Dcha.")]

# (clave, etiqueta, unidad, modo): "eje" = un valor delantero y uno trasero;
# "rueda" = un valor por rueda; "clicks" = clicks por rueda sobre el máximo
# del amortiguador (clave del ajuste en la ficha de suspensión).
PARAMETROS_SETUP = [
    ("altura", "Altura", "mm, por eje", "eje", None),
    ("presion_frio", "Presión en frío", "bar", "rueda", None),
    ("presion_caliente", "Presión en caliente", "bar", "rueda", None),
    ("convergencia", "Convergencia", "por eje · + cerrada · − abierta", "eje", None),
    ("rebote", "Rebote", "clicks / máx", "clicks", "rebote"),
    ("comp_unica", "Compresión", "clicks / máx · un solo ajuste", "clicks", "comp_unica"),
    ("comp_baja", "Compresión baja", "clicks / máx", "clicks", "comp_baja"),
    ("comp_alta", "Compresión alta", "clicks / máx", "clicks", "comp_alta"),
]

AJUSTES_SUSPENSION = [
    ("rebote", "Rebote (extensión)"),
    ("comp_unica", "Compresión (un solo ajuste)"),
    ("comp_baja", "Compresión BAJA velocidad"),
    ("comp_alta", "Compresión ALTA velocidad"),
]

PROBLEMAS_CURVA = [("bloquea", "Bloquea"), ("bota", "Bota"), ("patina", "Patina")]
FASES_CURVA = [("ent", "Ent"), ("med", "Med"), ("sal", "Sal")]

SENSACIONES = [
    ("rpm_bajas", "Bajas RPM: le cuesta salir (desarrollo largo)"),
    ("rpm_altas", "Altas RPM: corta muy rápido (desarrollo corto)"),
    ("cambio", "Cambio: entran mal las marchas / fallo embrague"),
    ("traccion_mala", "Tracción: patina mucho de atrás al dar gas"),
    ("traccion_buena", "Tracción: empuja bien, agarra perfecto"),
    ("freno_bueno", "Pedal freno: buen tacto y firmeza"),
    ("freno_blando", "Pedal freno: se hunde mucho / está blando"),
    ("reparto_delante", "Reparto: bloquea excesivo de DELANTE"),
    ("reparto_detras", "Reparto: bloquea excesivo de DETRÁS"),
    ("estabilidad", "Estabilidad: el coche culea mucho al frenar"),
]

RESULTADOS = [("mejor", "Mejor"), ("igual", "Igual"), ("peor", "Peor")]
DECISIONES = [("queda", "Se queda"), ("deshace", "Se deshace")]


def _cargar(raw, por_defecto):
    try:
        valor = json.loads(raw) if raw else por_defecto
    except (TypeError, ValueError):
        return por_defecto
    return valor if isinstance(valor, type(por_defecto)) else por_defecto


class FichaSuspension(db.Model):
    __tablename__ = "mecanica_fichas_suspension"

    id           = db.Column(db.Integer, primary_key=True)
    vehiculo_id  = db.Column(db.Integer, db.ForeignKey("vehiculos.id", ondelete="CASCADE"),
                             nullable=False, unique=True)
    amortiguador = db.Column(db.String(150), default="")
    # {"rebote": {"tiene": true, "max_del": 20, "max_tras": 20}, ...}
    ajustes_json = db.Column(db.Text, default="{}")
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehiculo = db.relationship("Vehiculo", backref=db.backref(
        "ficha_suspension", uselist=False, cascade="all, delete-orphan"))

    @property
    def ajustes(self):
        return _cargar(self.ajustes_json, {})

    def maximo(self, ajuste, eje):
        """Máx. clicks de un ajuste en un eje ('del' / 'tras'), o None."""
        datos = self.ajustes.get(ajuste) or {}
        if not datos.get("tiene"):
            return None
        return datos.get(f"max_{eje}")


class EventoReglaje(db.Model):
    __tablename__ = "mecanica_eventos"

    id           = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(150), nullable=False)
    circuito     = db.Column(db.String(150), default="")
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin    = db.Column(db.Date, nullable=True)
    curvas_texto = db.Column(db.Text, default=CURVAS_POR_DEFECTO)   # una curva por línea
    notas        = db.Column(db.Text, default="")
    creado_en    = db.Column(db.DateTime, default=datetime.utcnow)

    sesiones = db.relationship("SesionReglaje", backref="evento", cascade="all, delete-orphan",
                               order_by="SesionReglaje.creado_en")

    @property
    def curvas(self):
        return [c.strip() for c in (self.curvas_texto or "").splitlines() if c.strip()]


class SesionReglaje(db.Model):
    __tablename__ = "mecanica_sesiones"

    id             = db.Column(db.Integer, primary_key=True)
    evento_id      = db.Column(db.Integer, db.ForeignKey("mecanica_eventos.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    vehiculo_id    = db.Column(db.Integer, db.ForeignKey("vehiculos.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    piloto_id      = db.Column(db.Integer, db.ForeignKey("pilotos.id", ondelete="SET NULL"), nullable=True)
    piloto_nombre  = db.Column(db.String(150), default="")   # si no está dado de alta como piloto
    sesion         = db.Column(db.String(80), nullable=False)  # "Entrenos 1", "Manga 2"…
    fecha_hora     = db.Column(db.DateTime, nullable=True)
    encargado_setup = db.Column(db.String(100), default="")
    rellenado_por  = db.Column(db.String(100), default="")
    temp_aire      = db.Column(db.Float, nullable=True)
    temp_pista     = db.Column(db.Float, nullable=True)
    estado_pista   = db.Column(db.String(150), default="")

    setup_json      = db.Column(db.Text, default="{}")   # {param: {di,dd,ti,td,del,tras,cambio}}
    curvas_json     = db.Column(db.Text, default="{}")   # {curva: {tipo,balance,problemas[],comentario,fases[],diagnostico}}
    sensaciones_json = db.Column(db.Text, default="[]")  # claves de SENSACIONES marcadas
    autoevaluacion  = db.Column(db.Text, default="")
    lo_mas_importante = db.Column(db.Text, default="")
    confianza_piloto = db.Column(db.Integer, nullable=True)

    cambio_realizado = db.Column(db.Text, default="")
    mejor_vuelta_antes = db.Column(db.String(20), default="")
    mejor_vuelta_despues = db.Column(db.String(20), default="")
    confianza_antes  = db.Column(db.Integer, nullable=True)
    confianza_despues = db.Column(db.Integer, nullable=True)
    resultado        = db.Column(db.String(10), default="")
    decision         = db.Column(db.String(10), default="")
    plan_siguiente   = db.Column(db.Text, default="")
    apuntes          = db.Column(db.Text, default="")

    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vehiculo = db.relationship("Vehiculo", backref=db.backref(
        "sesiones_reglaje", cascade="all, delete-orphan", lazy="dynamic"))
    piloto = db.relationship("Piloto")

    @property
    def setup(self):
        return _cargar(self.setup_json, {})

    @property
    def curvas(self):
        return _cargar(self.curvas_json, {})

    @property
    def sensaciones(self):
        return _cargar(self.sensaciones_json, [])

    @property
    def piloto_display(self):
        if self.piloto:
            return self.piloto.nombre_completo
        return self.piloto_nombre or "—"

    @property
    def progreso(self):
        """Qué partes de la hoja tienen datos (para los indicadores)."""
        curvas = self.curvas.values()
        return {
            "setup": any(k != "cambio" for v in self.setup.values() for k in v),
            "piloto": bool(any("balance" in c or "problemas" in c for c in curvas)
                           or self.sensaciones or self.confianza_piloto or self.lo_mas_importante),
            "diagnostico": any("diagnostico" in c or "fases" in c for c in curvas),
            "cierre": bool(self.resultado or self.plan_siguiente or self.cambio_realizado
                           or self.mejor_vuelta_antes or self.mejor_vuelta_despues),
        }
