from datetime import datetime
from app.extensions import db


class Configuracion(db.Model):
    """Singleton — siempre id=1. Ajustes generales de la aplicación."""
    __tablename__ = "configuracion"

    id               = db.Column(db.Integer, primary_key=True)
    marketing_activo = db.Column(db.Boolean, default=True, nullable=False)
    campanas_activo  = db.Column(db.Boolean, default=True, nullable=False)
    # Recordatorio automático por email para que el cliente rellene los
    # datos de seguro, enviado X días antes de la fecha de disfrute si
    # todavía no los ha rellenado.
    seguro_recordatorio_activo = db.Column(db.Boolean, default=True, nullable=False)
    seguro_recordatorio_dias   = db.Column(db.Integer, default=7, nullable=False)
    actualizado_en   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get(cls):
        obj = cls.query.get(1)
        if obj is None:
            obj = cls(id=1)
            db.session.add(obj)
            db.session.commit()
        return obj
