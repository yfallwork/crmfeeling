from datetime import datetime
from app.extensions import db


class Piloto(db.Model):
    __tablename__ = "pilotos"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(150), nullable=False)
    dni = db.Column(db.String(20))
    dni_doc_filename = db.Column(db.String(200))
    fecha_nacimiento = db.Column(db.Date)
    nacionalidad = db.Column(db.String(80))
    calle = db.Column(db.String(200))
    cp = db.Column(db.String(10))
    localidad = db.Column(db.String(100))
    provincia = db.Column(db.String(100))
    telefono = db.Column(db.String(20))
    telefono_asistencia = db.Column(db.String(20))
    email = db.Column(db.String(150))
    num_licencia = db.Column(db.String(50))
    tipo_licencia = db.Column(db.String(30))
    federacion = db.Column(db.String(50))
    num_licencia_concursante = db.Column(db.String(50))
    nombre_concursante = db.Column(db.String(150))
    grupo_sanguineo = db.Column(db.String(10))
    alergias = db.Column(db.Text)
    contacto_emergencia_nombre = db.Column(db.String(150))
    contacto_emergencia_parentesco = db.Column(db.String(50))
    contacto_emergencia_telefono = db.Column(db.String(20))
    tutor_nombre = db.Column(db.String(150))
    tutor_dni = db.Column(db.String(20))
    tutor_doc_filename = db.Column(db.String(200))
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}".strip()

    @property
    def es_menor(self):
        if not self.fecha_nacimiento:
            return False
        from datetime import date
        today = date.today()
        age = today.year - self.fecha_nacimiento.year - (
            (today.month, today.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
        )
        return age < 18
