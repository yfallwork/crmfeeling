import json
from datetime import datetime
from app.extensions import db

# (clave, grupo, pregunta) — el orden es el orden de la especificación.
# La clave es la que se usa como llave dentro de notas_json.
BLOQUE_1_FAMILIA = [
    ("b1_1", "Compromiso y logística", "Este proceso puede exigir bastante tiempo y desplazamientos. ¿Tenéis disponibilidad real como familia para acompañarla si es necesario?"),
    ("b1_2", "Compromiso y logística", "¿Hay algún condicionante (estudios, salud, otras actividades) que debamos tener en cuenta a la hora de planificar su participación?"),
    ("b1_3", "Apoyo y expectativas familiares", "¿Qué os motivó como familia a apoyar esta candidatura?"),
    ("b1_4", "Apoyo y expectativas familiares", "¿Cómo os tomaríais que, tras todo el proceso, no resulte seleccionada?"),
    ("b1_5", "Apoyo y expectativas familiares", "¿Qué papel creéis que debe tener la familia en el desarrollo deportivo de vuestra hija?"),
    ("b1_6", "Apoyo y expectativas familiares", "¿Hay experiencia previa en el entorno familiar con el mundo del motor o el deporte de competición?"),
    ("b1_7", "Seguridad y madurez percibida", "¿Hay algo que consideréis relevante que debamos saber para acompañarla mejor durante el proceso (salud, carácter, situación personal)?"),
]
BLOQUE_2_CANDIDATA = [
    ("b2_8", "Motivación personal", "¿Por qué has decidido apuntarte a este proceso de selección?"),
    ("b2_9", "Motivación personal", "¿Cuándo sentiste por primera vez interés por el mundo del motor?"),
    ("b2_10", "Motivación personal", "¿Qué esperas conseguir tú, a nivel personal, más allá de ganar?"),
    ("b2_11", "Compromiso", "Cuéntame una vez en la que te comprometiste con algo difícil y no lo abandonaste, aunque te costara."),
    ("b2_12", "Gestión emocional y de la presión", "Cuéntame una situación en la que sentiste mucha presión. ¿Cómo la gestionaste?"),
    ("b2_13", "Gestión emocional y de la presión", "Si cometes un error delante de mucha gente, ¿cómo sueles recuperarte?"),
    ("b2_14", "Valores personales", "¿Qué significa para ti el «juego limpio» en el deporte?"),
    ("b2_15", "Proyección y aprendizaje", "¿Qué crees que puedes aportar tú que otras candidatas quizá no?"),
]
TODAS_LAS_PREGUNTAS = BLOQUE_1_FAMILIA + BLOQUE_2_CANDIDATA
CLAVES_PREGUNTAS = [p[0] for p in TODAS_LAS_PREGUNTAS]


class EntrevistaPiloto(db.Model):
    """Notas de entrevista de una candidata — visibles solo para el staff
    del CRM (esta tabla nunca se expone en ninguna ruta pública). Un único
    registro por candidata; las notas de cada pregunta viven en notas_json
    para poder autoguardar todo el formulario de una vez sin necesidad de
    una columna por pregunta."""
    __tablename__ = "entrevistas_piloto"

    id                = db.Column(db.Integer, primary_key=True)
    preinscripcion_id = db.Column(db.Integer, db.ForeignKey("preinscripciones_carcross.id", ondelete="CASCADE"),
                                   nullable=False, unique=True, index=True)

    notas_json         = db.Column(db.Text, default="{}")
    valoracion_bloque1  = db.Column(db.String(20), default="")
    valoracion_bloque2  = db.Column(db.String(20), default="")

    fecha_entrevista   = db.Column(db.DateTime, nullable=True)
    realizada_por_id   = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    creado_en      = db.Column(db.DateTime, default=datetime.utcnow)
    actualizado_en = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    preinscripcion = db.relationship("PreinscripcionCarcross", backref=db.backref(
        "entrevista", uselist=False, cascade="all, delete-orphan",
    ))
    realizada_por = db.relationship("Usuario", foreign_keys=[realizada_por_id])

    @property
    def notas(self):
        try:
            return json.loads(self.notas_json or "{}")
        except (ValueError, TypeError):
            return {}

    def nota(self, clave):
        return self.notas.get(clave, "")
