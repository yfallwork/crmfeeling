from datetime import datetime
from app.extensions import db


class Inscripcion(db.Model):
    __tablename__ = "inscripciones"
    id = db.Column(db.Integer, primary_key=True)
    nombre_prueba = db.Column(db.String(200), nullable=False)
    fecha_prueba = db.Column(db.Date)
    campeonato = db.Column(db.String(50))
    piloto_id = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=True, index=True)
    concursante = db.Column(db.String(200))
    fecha_plazo = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(20), default="pendiente")
    justificante_filename = db.Column(db.String(200))
    notas = db.Column(db.Text)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    piloto = db.relationship("Piloto", backref=db.backref("inscripciones", lazy="dynamic"))
    vehiculo = db.relationship("Vehiculo", backref=db.backref("inscripciones", lazy="dynamic"))
