from app.extensions import db


class AutoclubInfo(db.Model):
    """Singleton — always id=1. Stores club-level data."""
    __tablename__ = "autoclub_info"

    id                  = db.Column(db.Integer, primary_key=True)
    nombre_escuderia    = db.Column(db.String(200), default="")
    cif                 = db.Column(db.String(20),  default="")
    licencia_escuderia  = db.Column(db.String(100), default="")
    email_contacto      = db.Column(db.String(200), default="")
    telefono            = db.Column(db.String(50),  default="")
    direccion           = db.Column(db.Text,        default="")
    notas               = db.Column(db.Text,        default="")
    firma_html          = db.Column(db.Text,        default="")

    @classmethod
    def get(cls):
        obj = cls.query.get(1)
        if obj is None:
            obj = cls(id=1)
            db.session.add(obj)
            db.session.commit()
        return obj


class AutoclubCredencial(db.Model):
    """Access credentials for external sites (federation portals, etc.)."""
    __tablename__ = "autoclub_credenciales"

    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(200), nullable=False)
    url         = db.Column(db.String(500), default="")
    usuario     = db.Column(db.String(200), default="")
    password    = db.Column(db.String(500), default="")
    notas       = db.Column(db.Text,        default="")
    creado_en   = db.Column(db.DateTime,    default=__import__("datetime").datetime.utcnow)
