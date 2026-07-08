from datetime import datetime
from app.extensions import db


class AutoclubNota(db.Model):
    __tablename__ = "autoclub_notas"

    id             = db.Column(db.Integer, primary_key=True)
    entidad        = db.Column(db.String(20), nullable=False, index=True)  # socio | patrocinador
    entidad_id     = db.Column(db.Integer, nullable=False, index=True)
    entidad_nombre = db.Column(db.String(150), default="")
    contenido      = db.Column(db.Text, nullable=False)
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    usuario_nombre = db.Column(db.String(100), default="")
