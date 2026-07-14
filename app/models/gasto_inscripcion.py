from datetime import datetime
from app.extensions import db


CATEGORIAS_GASTO = [
    "Inscripción",
    "Combustible",
    "Alojamiento",
    "Dietas",
    "Transporte",
    "Repuestos",
    "Neumáticos",
    "Equipación",
    "Otros",
]


class GastoInscripcion(db.Model):
    __tablename__ = "gastos_inscripcion"

    id              = db.Column(db.Integer, primary_key=True)
    inscripcion_id  = db.Column(db.Integer, db.ForeignKey("inscripciones.id", ondelete="CASCADE"), nullable=False, index=True)
    concepto        = db.Column(db.String(200), nullable=False)
    importe         = db.Column(db.Float, nullable=False, default=0.0)
    categoria       = db.Column(db.String(50), default="Otros")
    fecha               = db.Column(db.Date)
    documento_filename  = db.Column(db.String(255))  # comprobante (recibo/ticket), se sube al crear el gasto
    factura_filename    = db.Column(db.String(255))  # factura oficial, normalmente llega mas tarde
    creado_en           = db.Column(db.DateTime, default=datetime.utcnow)

    inscripcion = db.relationship(
        "Inscripcion",
        backref=db.backref("gastos", cascade="all, delete-orphan", lazy="dynamic"),
    )
