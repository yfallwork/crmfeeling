from datetime import datetime
from app.extensions import db


class EmpresaNota(db.Model):
    __tablename__ = "empresa_notas"

    id             = db.Column(db.Integer, primary_key=True)
    empresa_id     = db.Column(db.Integer,
                               db.ForeignKey("empresas_tb.id", ondelete="CASCADE"),
                               nullable=False, index=True)
    contenido      = db.Column(db.Text, nullable=False)
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    usuario_nombre = db.Column(db.String(100), default="")

    empresa = db.relationship("Empresa", backref=db.backref("notas_historial",
                               cascade="all, delete-orphan"))
