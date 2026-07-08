from datetime import datetime
from app.extensions import db


class FechaApertura(db.Model):
    __tablename__ = "fechas_apertura"

    id                  = db.Column(db.Integer, primary_key=True)
    fecha               = db.Column(db.Date, nullable=False, index=True)
    tipo_experiencia_id = db.Column(db.Integer, db.ForeignKey("tipos_experiencia.id"), nullable=True)
    capacidad_ideal     = db.Column(db.Integer, nullable=True)  # nº de reservas objetivo para ese día
    notas               = db.Column(db.Text, default="")
    creado_en           = db.Column(db.DateTime, default=datetime.utcnow)

    tipo_experiencia = db.relationship(
        "TipoExperiencia",
        backref=db.backref("aperturas", lazy="dynamic"),
    )
