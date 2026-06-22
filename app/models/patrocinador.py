from datetime import datetime
from app.extensions import db


class Patrocinador(db.Model):
    __tablename__ = "patrocinadores"

    id = db.Column(db.Integer, primary_key=True)

    # Datos corporativos
    nombre           = db.Column(db.String(150), nullable=False)
    sector           = db.Column(db.String(100), default="")
    persona_contacto = db.Column(db.String(150), default="")
    email            = db.Column(db.String(150), default="")
    telefono         = db.Column(db.String(20),  default="")
    web              = db.Column(db.String(300),  default="")

    # Redes sociales (URL completa)
    instagram = db.Column(db.String(300), default="")
    facebook  = db.Column(db.String(300), default="")
    twitter   = db.Column(db.String(300), default="")
    linkedin  = db.Column(db.String(300), default="")
    tiktok    = db.Column(db.String(300), default="")
    youtube   = db.Column(db.String(300), default="")

    # Logos corporativos — guardados en uploads/autoclub/patrocinadores/
    # logo_positivo: versión para fondo blanco/claro (logotipo en color o negro)
    # logo_negativo: versión para fondo oscuro/negro (logotipo en blanco o color claro)
    # logo_banner:   versión horizontal/apaisada para banners y cabeceras
    logo_positivo_filename = db.Column(db.String(255), default="")
    logo_negativo_filename = db.Column(db.String(255), default="")
    logo_banner_filename   = db.Column(db.String(255), default="")

    activo         = db.Column(db.Boolean, default=True, nullable=False)
    notas          = db.Column(db.Text, default="")
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def redes_activas(self):
        redes = {
            "instagram": self.instagram,
            "facebook":  self.facebook,
            "twitter":   self.twitter,
            "linkedin":  self.linkedin,
            "tiktok":    self.tiktok,
            "youtube":   self.youtube,
        }
        return {k: v for k, v in redes.items() if v and v.strip()}

    @property
    def logo_principal(self):
        """Logo más apropiado para mostrar sobre fondo claro (orden de preferencia)."""
        return self.logo_positivo_filename or self.logo_banner_filename or self.logo_negativo_filename or ""

    @property
    def tiene_logo(self):
        return bool(self.logo_positivo_filename or self.logo_negativo_filename or self.logo_banner_filename)

    def __repr__(self):
        return f"<Patrocinador {self.nombre}>"
