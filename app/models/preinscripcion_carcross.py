from datetime import datetime
from app.extensions import db

# Proyecto puntual "Selección Femenina de Pilotos de Carcross" (JCCM / Autoclub
# La Dehesa / Motorsport Ibérica / Feeling Experience). Landing pública +
# preinscripción sin login — ver app/routes/seleccion_femenina.py.
EXPERIENCIA_PREVIA_OPCIONES = [
    ("ninguna", "Ninguna"),
    ("conduccion_embrague", "Algo de conducción con embrague"),
    ("amateur_sin_resultados", "Amateur, sin resultados destacados"),
]
EXPERIENCIA_PREVIA_KEYS = [k for k, _ in EXPERIENCIA_PREVIA_OPCIONES]

ESTADOS_PREINSCRIPCION = ["pendiente", "contactada", "descartada", "seleccionada"]


class PreinscripcionCarcross(db.Model):
    __tablename__ = "preinscripciones_carcross"

    id                 = db.Column(db.Integer, primary_key=True)
    nombre_completo    = db.Column(db.String(200), nullable=False)
    fecha_nacimiento   = db.Column(db.Date, nullable=False)
    localidad          = db.Column(db.String(150), default="")
    email              = db.Column(db.String(150), nullable=False)
    telefono           = db.Column(db.String(30), nullable=False)
    experiencia_previa = db.Column(db.String(40), default="ninguna")
    motivacion         = db.Column(db.Text, default="")
    acepta_privacidad  = db.Column(db.Boolean, default=False, nullable=False)
    estado             = db.Column(db.String(20), default="pendiente")
    notas_internas     = db.Column(db.Text, default="")
    ip                 = db.Column(db.String(45), default="")
    creado_en          = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def edad(self):
        if not self.fecha_nacimiento:
            return None
        hoy = datetime.utcnow().date()
        cumplidos = hoy.year - self.fecha_nacimiento.year
        if (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day):
            cumplidos -= 1
        return cumplidos

    @property
    def experiencia_previa_label(self):
        return dict(EXPERIENCIA_PREVIA_OPCIONES).get(self.experiencia_previa, self.experiencia_previa)
