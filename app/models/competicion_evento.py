from datetime import datetime
from app.extensions import db


class CompeticionEvento(db.Model):
    __tablename__ = "competicion_eventos"

    id          = db.Column(db.Integer, primary_key=True)
    titulo      = db.Column(db.String(200), nullable=False)
    descripcion = db.Column(db.Text, default="")
    fecha       = db.Column(db.Date, nullable=False)
    fecha_plazo = db.Column(db.Date, nullable=True)
    creado_en   = db.Column(db.DateTime, default=datetime.utcnow)
