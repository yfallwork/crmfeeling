from datetime import datetime
from app.extensions import db


class PlantillaEmail(db.Model):
    __tablename__ = "plantillas_email"

    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(150), nullable=False)
    asunto      = db.Column(db.String(250), nullable=False)
    cuerpo_html = db.Column(db.Text, default="")
    segmento    = db.Column(db.String(10), default="ambos")
    descripcion = db.Column(db.Text, default="")
    activo      = db.Column(db.Boolean, default=True)
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # RuleAccion → PlantillaEmail (a plantilla can appear in many acciones)
    acciones_uso = db.relationship("RuleAccion", back_populates="plantilla", lazy="dynamic")

    @property
    def normas_count(self):
        """How many distinct rules use this template."""
        from sqlalchemy import func
        return (db.session.query(func.count(func.distinct(RuleAccion.rule_id)))
                .filter(RuleAccion.plantilla_id == self.id).scalar() or 0)


class RuleTag(db.Model):
    __tablename__ = "rule_tags"

    rule_id = db.Column(db.Integer, db.ForeignKey("rules.id",  ondelete="CASCADE"), primary_key=True)
    tag_id  = db.Column(db.Integer, db.ForeignKey("tags.id",   ondelete="CASCADE"), primary_key=True)
    tipo    = db.Column(db.String(10), default="requerida")  # requerida | excluida

    rule = db.relationship("Rule", back_populates="rule_tags")
    tag  = db.relationship("Tag")


class RuleAccion(db.Model):
    """One row per action inside a Rule. A Rule can have 1-N actions."""
    __tablename__ = "rule_acciones"

    id      = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("rules.id", ondelete="CASCADE"), nullable=False)
    tipo    = db.Column(db.String(20), nullable=False)   # email | whatsapp | notificacion
    plantilla_id         = db.Column(db.Integer, db.ForeignKey("plantillas_email.id", ondelete="SET NULL"), nullable=True)
    mensaje_whatsapp     = db.Column(db.Text, default="")
    mensaje_notificacion = db.Column(db.Text, default="")
    orden   = db.Column(db.Integer, default=0)

    rule      = db.relationship("Rule", back_populates="acciones")
    plantilla = db.relationship("PlantillaEmail", back_populates="acciones_uso",
                                foreign_keys=[plantilla_id])

    _META = {
        "email":        ("Email",               "bi-envelope-fill",  "#6366F1"),
        "whatsapp":     ("WhatsApp",             "bi-whatsapp",       "#25D366"),
        "notificacion": ("Notificación interna", "bi-bell-fill",      "#F59E0B"),
    }

    @property
    def tipo_label(self):
        return self._META.get(self.tipo, (self.tipo, "bi-play-fill", "#6B7280"))[0]

    @property
    def tipo_icono(self):
        return self._META.get(self.tipo, (self.tipo, "bi-play-fill", "#6B7280"))[1]

    @property
    def tipo_color(self):
        return self._META.get(self.tipo, (self.tipo, "bi-play-fill", "#6B7280"))[2]


class Rule(db.Model):
    __tablename__ = "rules"

    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, default="")
    activo      = db.Column(db.Boolean, default=True)
    segmento    = db.Column(db.String(10), default="b2c")
    entidad     = db.Column(db.String(10), default="cliente")
    delay_horas = db.Column(db.Integer, default=0)
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    acciones  = db.relationship("RuleAccion", back_populates="rule",
                                cascade="all, delete-orphan",
                                order_by="RuleAccion.orden")
    rule_tags = db.relationship("RuleTag", back_populates="rule", cascade="all, delete-orphan")

    @property
    def tags_requeridas(self):
        return [rt.tag for rt in self.rule_tags if rt.tipo == "requerida"]

    @property
    def tags_excluidas(self):
        return [rt.tag for rt in self.rule_tags if rt.tipo == "excluida"]

    @property
    def delay_label(self):
        h = self.delay_horas
        if h == 0:   return "Inmediato"
        if h < 24:   return f"{h}h"
        if h < 168:  return f"{h // 24}d"
        return f"{h // 168}sem"


class Notificacion(db.Model):
    __tablename__ = "notificaciones_marketing"

    id             = db.Column(db.Integer, primary_key=True)
    titulo         = db.Column(db.String(200), nullable=False)
    mensaje        = db.Column(db.Text, default="")
    tipo           = db.Column(db.String(20), default="llamada")   # llamada | recordatorio | alerta
    prioridad      = db.Column(db.String(10), default="media")     # alta | media | baja
    entidad        = db.Column(db.String(20), default="cliente")   # cliente | empresa
    entidad_id     = db.Column(db.Integer, nullable=True)
    entidad_nombre = db.Column(db.String(200), default="")
    rule_id        = db.Column(db.Integer, db.ForeignKey("rules.id", ondelete="SET NULL"), nullable=True)
    resuelta       = db.Column(db.Boolean, default=False)
    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    resuelta_en    = db.Column(db.DateTime, nullable=True)

    rule = db.relationship("Rule")

    _PRIORIDAD = {
        "alta":  ("#EF4444", "bi-exclamation-circle-fill"),
        "media": ("#F59E0B", "bi-dash-circle-fill"),
        "baja":  ("#10B981", "bi-info-circle-fill"),
    }
    _TIPO = {
        "llamada":      ("#3B82F6", "bi-telephone-fill"),
        "recordatorio": ("#8B5CF6", "bi-clock-fill"),
        "alerta":       ("#EF4444", "bi-exclamation-triangle-fill"),
    }

    @property
    def prioridad_color(self):  return self._PRIORIDAD.get(self.prioridad, ("#6B7280","bi-dot"))[0]
    @property
    def prioridad_icono(self):  return self._PRIORIDAD.get(self.prioridad, ("#6B7280","bi-dot"))[1]
    @property
    def tipo_color(self):       return self._TIPO.get(self.tipo, ("#6B7280","bi-bell-fill"))[0]
    @property
    def tipo_icono(self):       return self._TIPO.get(self.tipo, ("#6B7280","bi-bell-fill"))[1]
    @property
    def tipo_label(self):
        return {"llamada":"Llamada","recordatorio":"Recordatorio","alerta":"Alerta"}.get(self.tipo, self.tipo)
