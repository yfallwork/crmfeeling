"""
Calendario de publicaciones en redes (Instagram @feelingexperiences):
cada publicación tiene fecha, categoría, tipo, indicaciones de producción y
el texto a publicar, y se le pueden adjuntar los vídeos/fotos finales. Las
campañas agrupan publicaciones en un rango de fechas (ej. Navidad).
"""
from datetime import date, datetime
from app.extensions import db

# clave: (etiqueta, color texto, color fondo) — mismos colores que el PDF
CATEGORIAS_RRSS = {
    "ventas":        ("Ventas",                         "#DC2626", "#FEE2E2"),
    "fechas":        ("Fechas",                         "#C2410C", "#FFEDD5"),
    "navidad":       ("Navidad · Rivales y Fin de Semana", "#854D0E", "#FEF3C7"),
    "team_building": ("Team Building",                  "#374151", "#E5E7EB"),
    "opiniones":     ("Opiniones",                      "#0F766E", "#CCFBF1"),
    "academy":       ("Academy",                        "#6D28D9", "#EDE9FE"),
    "competicion":   ("Competición",                    "#1D4ED8", "#DBEAFE"),
}

TIPOS_RRSS = {
    "post":      ("Post",          "bi-square-fill"),
    "historias": ("Historias",     "bi-circle-fill"),
    "evento":    ("Evento",        "bi-diamond-fill"),
    "anuncio":   ("Anuncio Meta",  "bi-badge-ad"),
    "tarea":     ("Tarea",         "bi-check2-square"),
}

PRODUCCION_RRSS = {
    "":                 "—",
    "sin_editar":       "Sin editar",
    "canva":            "Canva",
    "ya_montado":       "Ya montado",
    "video_por_editar": "Vídeo por editar",
}

# pendiente → falta subir el contenido; listo → contenido subido;
# publicado → ya está en redes (o la tarea está hecha).
ESTADOS_RRSS = {
    "pendiente": ("Pendiente",        "#B45309", "#FEF3C7"),
    "listo":     ("Contenido listo",  "#1D4ED8", "#DBEAFE"),
    "publicado": ("Publicado / hecho", "#15803D", "#DCFCE7"),
}


class CampanaRRSS(db.Model):
    __tablename__ = "campanas_rrss"

    id           = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(150), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin    = db.Column(db.Date, nullable=False)
    color        = db.Column(db.String(7), default="#854D0E")
    descripcion  = db.Column(db.Text, default="")
    creado_en    = db.Column(db.DateTime, default=datetime.utcnow)

    def incluye(self, dia):
        return self.fecha_inicio <= dia <= self.fecha_fin


class PublicacionRRSS(db.Model):
    __tablename__ = "publicaciones_rrss"

    id            = db.Column(db.Integer, primary_key=True)
    fecha         = db.Column(db.Date, nullable=False, index=True)
    titulo        = db.Column(db.String(200), nullable=False)
    categoria     = db.Column(db.String(20), nullable=False, default="ventas")
    tipo          = db.Column(db.String(20), nullable=False, default="post")
    formato       = db.Column(db.String(150), default="")
    produccion    = db.Column(db.String(20), default="")
    indicaciones  = db.Column(db.Text, default="")
    descripcion   = db.Column(db.Text, default="")   # texto/caption a publicar
    estado        = db.Column(db.String(20), nullable=False, default="pendiente", index=True)
    # Se graba y publica el mismo día (historias en directo, reels del
    # momento): no hay que subir nada antes, así que no genera avisos previos.
    en_directo    = db.Column(db.Boolean, nullable=False, default=False)
    campana_id    = db.Column(db.Integer, db.ForeignKey("campanas_rrss.id", ondelete="SET NULL"), nullable=True)
    ultimo_aviso_en = db.Column(db.DateTime, nullable=True)
    creado_en     = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    campana  = db.relationship("CampanaRRSS", backref=db.backref("publicaciones", lazy="dynamic"))
    archivos = db.relationship("ArchivoPublicacion", backref="publicacion",
                               cascade="all, delete-orphan", order_by="ArchivoPublicacion.subido_en")

    @property
    def categoria_info(self):
        return CATEGORIAS_RRSS.get(self.categoria, (self.categoria, "#374151", "#E5E7EB"))

    @property
    def tipo_info(self):
        return TIPOS_RRSS.get(self.tipo, (self.tipo, "bi-dot"))

    @property
    def estado_info(self):
        return ESTADOS_RRSS.get(self.estado, (self.estado, "#374151", "#E5E7EB"))

    @property
    def produccion_label(self):
        return PRODUCCION_RRSS.get(self.produccion or "", self.produccion)

    @property
    def atrasada(self):
        return self.estado == "pendiente" and self.fecha < date.today()

    @property
    def requiere_subida(self):
        """Hay que subir el contenido antes de su fecha (lo que se avisa)."""
        return self.estado == "pendiente" and not self.en_directo


class ArchivoPublicacion(db.Model):
    __tablename__ = "archivos_publicacion"

    id              = db.Column(db.Integer, primary_key=True)
    publicacion_id  = db.Column(db.Integer, db.ForeignKey("publicaciones_rrss.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    nombre_archivo  = db.Column(db.String(200), nullable=False)   # nombre en disco
    nombre_original = db.Column(db.String(255), nullable=False)
    mimetype        = db.Column(db.String(100), default="")
    tamano          = db.Column(db.Integer, default=0)
    subido_en       = db.Column(db.DateTime, default=datetime.utcnow)
    subido_por_id   = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    subido_por = db.relationship("Usuario", foreign_keys=[subido_por_id])

    @property
    def es_video(self):
        return (self.mimetype or "").startswith("video/")

    @property
    def es_imagen(self):
        return (self.mimetype or "").startswith("image/")

    @property
    def tamano_legible(self):
        n = self.tamano or 0
        for unidad in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {unidad}" if unidad == "B" else f"{n:.1f} {unidad}"
            n /= 1024
        return f"{n:.1f} TB"


class DestinatarioAvisoRRSS(db.Model):
    """Correos que reciben el aviso de contenido pendiente de subir."""
    __tablename__ = "destinatarios_aviso_rrss"

    id        = db.Column(db.Integer, primary_key=True)
    email     = db.Column(db.String(150), nullable=False, unique=True)
    nombre    = db.Column(db.String(100), default="")
    activo    = db.Column(db.Boolean, default=True, nullable=False)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
