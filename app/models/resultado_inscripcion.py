from datetime import datetime
from app.extensions import db


class ResultadoInscripcion(db.Model):
    __tablename__ = "resultados_inscripcion"

    id                  = db.Column(db.Integer, primary_key=True)
    inscripcion_id      = db.Column(db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    posicion_salida     = db.Column(db.Integer)
    posicion_final      = db.Column(db.Integer)
    mejor_vuelta        = db.Column(db.String(20))   # ej. "1:42.350"
    tiempo_total        = db.Column(db.String(30))   # ej. "32:15.820"
    vueltas_completadas = db.Column(db.Integer)
    puntos              = db.Column(db.Float)
    abandono            = db.Column(db.Boolean, default=False)
    motivo_abandono     = db.Column(db.String(200))
    observaciones       = db.Column(db.Text)
    creado_en           = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    inscripcion = db.relationship(
        "Inscripcion",
        backref=db.backref("resultado", uselist=False, cascade="all, delete-orphan"),
    )
