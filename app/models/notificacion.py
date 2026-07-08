from datetime import datetime
from app.extensions import db


class Notificacion(db.Model):
    __tablename__ = "notificaciones"

    id         = db.Column(db.Integer, primary_key=True)
    tipo       = db.Column(db.String(20), default="warning")  # info | warning | danger
    titulo     = db.Column(db.String(200), nullable=False)
    mensaje    = db.Column(db.Text, default="")
    url        = db.Column(db.String(500), default="")
    leida      = db.Column(db.Boolean, default=False, index=True)
    referencia = db.Column(db.String(100), default="", index=True)
    creado_en  = db.Column(db.DateTime, default=datetime.utcnow)
