from datetime import datetime
from app.extensions import db

_EVENTOS = {
    # ── Etiquetas ────────────────────────────────────────────────────
    "tag_asignada":          ("Etiqueta asignada",          "bi-tag-fill",               "#10B981"),
    "tag_eliminada":         ("Etiqueta eliminada",         "bi-tag",                    "#EF4444"),
    "tag_trigger":           ("Trigger automático",         "bi-lightning-fill",         "#F59E0B"),
    # ── Acciones de normas ───────────────────────────────────────────
    "accion_email":          ("Email enviado",              "bi-envelope-fill",          "#6366F1"),
    "accion_whatsapp":       ("WhatsApp enviado",           "bi-whatsapp",               "#25D366"),
    "accion_notificacion":   ("Notif. interna generada",   "bi-bell-fill",              "#F59E0B"),
    "accion_error":          ("Acción fallida",             "bi-x-circle-fill",          "#EF4444"),
    # ── Normas ───────────────────────────────────────────────────────
    "norma_evaluada_ok":     ("Norma ejecutada",            "bi-diagram-3-fill",         "#6366F1"),
    "norma_evaluada_skip":   ("Norma sin coincidencia",     "bi-diagram-3",              "#9CA3AF"),
    "norma_activada":        ("Norma activada",             "bi-play-circle-fill",       "#10B981"),
    "norma_desactivada":     ("Norma desactivada",          "bi-pause-circle-fill",      "#6B7280"),
    # ── Campañas ─────────────────────────────────────────────────────
    "campana_programada":    ("Campaña programada",         "bi-send-check-fill",        "#8B5CF6"),
    "campana_enviada":       ("Campaña enviada",            "bi-megaphone-fill",         "#10B981"),
    "campana_error":         ("Campaña con errores",        "bi-megaphone",              "#EF4444"),
    "campana_email_ok":      ("Email campaña enviado",      "bi-envelope-check-fill",    "#6366F1"),
    "campana_email_error":   ("Email campaña fallido",      "bi-envelope-x-fill",        "#EF4444"),
    "campana_wa_ok":         ("WhatsApp campaña enviado",   "bi-whatsapp",               "#25D366"),
    # ── Notificaciones ───────────────────────────────────────────────
    "notificacion_creada":   ("Notificación creada",        "bi-bell-plus",              "#8B5CF6"),
    "notificacion_resuelta": ("Notificación resuelta",      "bi-check-circle-fill",      "#10B981"),
    # ── Webhooks / sistema ───────────────────────────────────────────
    "webhook_recibido":      ("Webhook recibido",           "bi-arrow-down-circle-fill", "#3B82F6"),
    "webhook_error":         ("Webhook con error",          "bi-exclamation-circle-fill","#EF4444"),
}

_RESULTADO = {
    "ok":    ("#10B981", "bi-check-circle-fill", "OK"),
    "error": ("#EF4444", "bi-x-circle-fill",     "Error"),
    "skip":  ("#9CA3AF", "bi-dash-circle",        "Omitido"),
}


class MarketingLog(db.Model):
    __tablename__ = "marketing_logs"

    id             = db.Column(db.Integer, primary_key=True)
    fecha          = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    evento         = db.Column(db.String(30), nullable=False, index=True)
    resultado      = db.Column(db.String(10), default="ok",     index=True)   # ok | error | skip

    # ── Contexto de norma ────────────────────────────────────────────
    rule_id        = db.Column(db.Integer,
                               db.ForeignKey("rules.id", ondelete="SET NULL"),
                               nullable=True, index=True)
    rule_nombre    = db.Column(db.String(150), default="")   # denorm. — sobrevive al borrado de la norma
    accion_tipo    = db.Column(db.String(20),  default="")   # email | whatsapp | notificacion

    # ── Contexto de campaña ──────────────────────────────────────────
    campana_id     = db.Column(db.Integer, nullable=True, index=True)   # sin FK: sobrevive al borrado
    campana_nombre = db.Column(db.String(200), default="")

    # ── Contexto de etiqueta ─────────────────────────────────────────
    tag_id         = db.Column(db.Integer,
                               db.ForeignKey("tags.id", ondelete="SET NULL"),
                               nullable=True)
    tag_nombre     = db.Column(db.String(100), default="")

    # ── Contexto de entidad (cliente / empresa) ───────────────────────
    entidad        = db.Column(db.String(20),  default="")   # cliente | empresa
    entidad_id     = db.Column(db.Integer,     nullable=True)
    entidad_nombre = db.Column(db.String(200), default="")

    # ── Metadata ─────────────────────────────────────────────────────
    detalle        = db.Column(db.Text, default="")
    origen         = db.Column(db.String(20), default="manual", index=True)  # manual|sistema|webhook|scheduler
    usuario_nombre = db.Column(db.String(100), default="Sistema")

    # ── Relaciones (nullable — sobreviven a borrados) ─────────────────
    rule = db.relationship("Rule")
    tag  = db.relationship("Tag")

    # ── Properties de presentación ───────────────────────────────────

    @property
    def evento_label(self):
        return _EVENTOS.get(self.evento, (self.evento, "bi-dot", "#9CA3AF"))[0]

    @property
    def evento_icono(self):
        return _EVENTOS.get(self.evento, (self.evento, "bi-dot", "#9CA3AF"))[1]

    @property
    def evento_color(self):
        return _EVENTOS.get(self.evento, (self.evento, "bi-dot", "#9CA3AF"))[2]

    @property
    def resultado_color(self):
        return _RESULTADO.get(self.resultado, ("#9CA3AF", "bi-dash-circle", "?"))[0]

    @property
    def resultado_icono(self):
        return _RESULTADO.get(self.resultado, ("#9CA3AF", "bi-dash-circle", "?"))[1]

    @property
    def resultado_label(self):
        return _RESULTADO.get(self.resultado, ("#9CA3AF", "bi-dash-circle", "?"))[2]

    @property
    def origen_label(self):
        return {
            "manual":    "Manual",
            "sistema":   "Sistema",
            "webhook":   "Webhook",
            "scheduler": "Programado",
        }.get(self.origen, self.origen)
