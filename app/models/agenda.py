from datetime import datetime
from app.extensions import db

EMPRESAS = [
    ("autoclub", "Autoclub"),
    ("feeling",  "Feeling"),
    ("ambas",    "Ambas empresas"),
]

TIPOS = [
    ("rrss_carrera",      "RRSS · Carrera"),
    ("rrss_evento",       "RRSS · Evento"),
    ("rrss_promocion",    "RRSS · Promoción"),
    ("rrss_sorteo",       "RRSS · Sorteo"),
    ("rrss_noticia",      "RRSS · Noticia"),
    ("rrss_gift",         "RRSS · Gift / Regalo"),
    ("rrss_novedad",      "RRSS · Novedad"),
    ("rrss_inspiracional","RRSS · Inspiracional"),
    ("pista_abierta",     "Día de Pista Abierta"),
    ("actividad_circuito","Actividad en Circuito"),
    ("evento_especial",   "Evento Especial"),
    ("promocion_oferta",  "Promoción / Oferta"),
    ("otro",              "Otro"),
]

REDES = [
    ("instagram", "Instagram"),
    ("facebook",  "Facebook"),
    ("twitter",   "Twitter / X"),
    ("tiktok",    "TikTok"),
    ("todas",     "Todas las redes"),
]

ESTADOS = [
    ("planificado", "Planificado"),
    ("publicado",   "Publicado"),
    ("cancelado",   "Cancelado"),
]

EMPRESA_COLORES = {
    "autoclub": "#2563EB",
    "feeling":  "#AD1726",
    "ambas":    "#7C3AED",
}

TIPO_ICONOS = {
    "rrss_carrera":       "bi-flag",
    "rrss_evento":        "bi-calendar-event",
    "rrss_promocion":     "bi-tag",
    "rrss_sorteo":        "bi-gift",
    "rrss_noticia":       "bi-newspaper",
    "rrss_gift":          "bi-gift",
    "rrss_novedad":       "bi-stars",
    "rrss_inspiracional": "bi-sun",
    "pista_abierta":      "bi-flag-fill",
    "actividad_circuito": "bi-trophy",
    "evento_especial":    "bi-star",
    "promocion_oferta":   "bi-percent",
    "otro":               "bi-three-dots",
}

ESTADO_COLORES = {
    "planificado": "#F59E0B",
    "publicado":   "#10B981",
    "cancelado":   "#6B7280",
}

# Tabla de asociación many-to-many
entrada_tematica = db.Table(
    "entrada_tematica",
    db.Column("entrada_id",  db.Integer, db.ForeignKey("agenda_entradas.id"),  primary_key=True),
    db.Column("tematica_id", db.Integer, db.ForeignKey("agenda_tematicas.id"), primary_key=True),
)


class Tematica(db.Model):
    __tablename__ = "agenda_tematicas"

    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(120), nullable=False)
    descripcion = db.Column(db.Text, default="")
    empresa     = db.Column(db.String(20), default="ambas")
    tipo        = db.Column(db.String(40), default="otro")
    color       = db.Column(db.String(7),  default="#6B7280")
    activo      = db.Column(db.Boolean, default=True)
    creado_en   = db.Column(db.DateTime, default=datetime.utcnow)

    entradas = db.relationship(
        "EntradaAgenda", secondary=entrada_tematica, back_populates="tematicas"
    )

    @property
    def empresa_label(self):
        return dict(EMPRESAS).get(self.empresa, self.empresa)

    @property
    def tipo_label(self):
        return dict(TIPOS).get(self.tipo, self.tipo)

    def to_dict(self):
        return {
            "id":     self.id,
            "nombre": self.nombre,
            "color":  self.color,
            "empresa": self.empresa,
            "tipo":   self.tipo,
        }

    def __repr__(self):
        return f"<Tematica #{self.id} {self.nombre}>"


class EntradaAgenda(db.Model):
    __tablename__ = "agenda_entradas"

    id            = db.Column(db.Integer, primary_key=True)
    fecha         = db.Column(db.Date, nullable=False)
    empresa       = db.Column(db.String(20), nullable=False, default="ambas")
    tipo          = db.Column(db.String(40), nullable=False, default="otro")
    red_social    = db.Column(db.String(20), default="")
    titulo        = db.Column(db.String(200), nullable=False)
    descripcion   = db.Column(db.Text, default="")
    url           = db.Column(db.String(500), default="")
    estado        = db.Column(db.String(20), default="planificado")
    notas         = db.Column(db.Text, default="")
    creado_en     = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en= db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tematicas = db.relationship(
        "Tematica", secondary=entrada_tematica, back_populates="entradas"
    )

    @property
    def color(self):
        return EMPRESA_COLORES.get(self.empresa, "#6B7280")

    @property
    def estado_color(self):
        return ESTADO_COLORES.get(self.estado, "#6B7280")

    @property
    def empresa_label(self):
        return dict(EMPRESAS).get(self.empresa, self.empresa)

    @property
    def tipo_label(self):
        return dict(TIPOS).get(self.tipo, self.tipo)

    @property
    def red_social_label(self):
        return dict(REDES).get(self.red_social, self.red_social or "")

    @property
    def estado_label(self):
        return dict(ESTADOS).get(self.estado, self.estado)

    @property
    def icono(self):
        return TIPO_ICONOS.get(self.tipo, "bi-three-dots")

    def to_calendar_event(self):
        return {
            "id":    str(self.id),
            "title": self.titulo,
            "start": self.fecha.isoformat(),
            "allDay": True,
            "backgroundColor": self.color,
            "borderColor":     self.estado_color,
            "extendedProps": {
                "empresa":       self.empresa,
                "empresa_label": self.empresa_label,
                "tipo":          self.tipo,
                "tipo_label":    self.tipo_label,
                "red_social":    self.red_social or "",
                "red_social_label": self.red_social_label,
                "descripcion":   self.descripcion or "",
                "url":           self.url or "",
                "estado":        self.estado,
                "estado_label":  self.estado_label,
                "estado_color":  self.estado_color,
                "notas":         self.notas or "",
                "tematicas":     [t.to_dict() for t in self.tematicas],
                "icono":         self.icono,
            },
        }

    def __repr__(self):
        return f"<EntradaAgenda #{self.id} {self.fecha} {self.titulo}>"
