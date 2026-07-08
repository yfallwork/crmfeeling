from datetime import datetime
from app.extensions import db


class MedioContacto(db.Model):
    __tablename__ = "medios_contacto"

    id        = db.Column(db.Integer, primary_key=True)
    nombre    = db.Column(db.String(200), nullable=False)
    medio     = db.Column(db.String(200), default="")   # outlet / publication
    email     = db.Column(db.String(200), nullable=False)
    notas     = db.Column(db.Text,        default="")
    activo    = db.Column(db.Boolean,     default=True)
    creado_en = db.Column(db.DateTime,    default=datetime.utcnow)


class CronicaEnviada(db.Model):
    __tablename__ = "cronicas_enviadas"

    id             = db.Column(db.Integer,  primary_key=True)
    asunto         = db.Column(db.String(500), nullable=False)
    cuerpo_html    = db.Column(db.Text,        default="")
    destinatarios  = db.Column(db.Text,        default="")  # JSON: [{"nombre":…,"email":…}]
    total_enviados = db.Column(db.Integer,     default=0)
    total_errores  = db.Column(db.Integer,     default=0)
    enviado_por    = db.Column(db.String(100), default="")
    enviado_en     = db.Column(db.DateTime,    default=datetime.utcnow)
