from datetime import datetime
from app.extensions import db


class InscripcionPiloto(db.Model):
    """Pilotos adicionales inscritos en la misma prueba (además del piloto
    principal de Inscripcion.piloto). Todos comparten la misma inscripción,
    la misma prueba y los mismos gastos, ya que van juntos al evento."""
    __tablename__ = "inscripcion_pilotos"

    id             = db.Column(db.Integer, primary_key=True)
    inscripcion_id = db.Column(db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=False, index=True)
    piloto_id      = db.Column(db.Integer, db.ForeignKey("pilotos.id"), nullable=False, index=True)
    vehiculo_id    = db.Column(db.Integer, db.ForeignKey("vehiculos.id"), nullable=True)
    concursante    = db.Column(db.String(200), default="")
    estado         = db.Column(db.String(20), default="pendiente")  # pendiente | enviada | aceptada | rechazada
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)

    inscripcion = db.relationship(
        "Inscripcion",
        backref=db.backref("participantes", cascade="all, delete-orphan", lazy="dynamic"),
    )
    piloto   = db.relationship("Piloto")
    vehiculo = db.relationship("Vehiculo")
