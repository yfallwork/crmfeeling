from datetime import datetime
from app.extensions import db

# Catálogo de operaciones habituales de mantenimiento y reparación de un
# carcross (chasis tubular, motor de moto, transmisión por cadena),
# agrupadas por sistema. Las claves se guardan en BD: no renombrarlas, solo
# añadir nuevas.
CATALOGO_OPERACIONES = [
    ("Motor", [
        ("aceite_motor", "Cambio de aceite de motor"),
        ("filtro_aceite", "Cambio de filtro de aceite"),
        ("filtro_aire", "Limpieza / cambio de filtro de aire"),
        ("bujias", "Cambio de bujías"),
        ("valvulas", "Reglaje de válvulas"),
        ("distribucion", "Revisión de cadena y tensor de distribución"),
        ("compresion", "Prueba de compresión"),
        ("sincronizacion", "Sincronización de carburadores / cuerpos de inyección"),
        ("carburacion", "Limpieza de carburadores / inyectores"),
        ("refrigerante", "Cambio de líquido refrigerante"),
        ("radiador", "Revisión de radiador, manguitos y ventilador"),
        ("escape", "Revisión de escape / cambio de fibra del silencioso"),
        ("juntas_motor", "Cambio de juntas / retenes de motor"),
        ("anclajes_motor", "Revisión de soportes y anclajes de motor"),
        ("reconstruccion_motor", "Reconstrucción de motor (pistón, segmentos, cojinetes)"),
        ("cambio_motor", "Sustitución de motor completo"),
    ]),
    ("Embrague y caja de cambios", [
        ("discos_embrague", "Revisión / cambio de discos de embrague"),
        ("muelles_embrague", "Cambio de muelles de embrague"),
        ("ajuste_embrague", "Ajuste de cable / purgado del embrague hidráulico"),
        ("liquido_embrague", "Cambio de líquido de embrague"),
        ("caja_cambios", "Revisión de caja de cambios y selector"),
        ("palanca_cambio", "Revisión / ajuste de palanca de cambio secuencial"),
        ("marcha_atras", "Revisión de la marcha atrás"),
    ]),
    ("Transmisión", [
        ("cadena_engrase", "Limpieza, engrase y tensado de cadena"),
        ("cadena_cambio", "Cambio de cadena"),
        ("pinon_corona", "Cambio de piñón y corona"),
        ("eje_trasero", "Revisión de eje trasero y rodamientos"),
        ("palieres", "Revisión de palieres y homocinéticas"),
        ("diferencial", "Revisión del diferencial / autoblocante"),
        ("guia_cadena", "Cambio de patín / guía de cadena"),
    ]),
    ("Frenos", [
        ("pastillas_del", "Cambio de pastillas delanteras"),
        ("pastillas_tras", "Cambio de pastillas traseras"),
        ("discos_freno", "Cambio / rectificado de discos de freno"),
        ("liquido_frenos", "Purgado / cambio de líquido de frenos"),
        ("bombas_pinzas", "Revisión de bombas, pinzas y latiguillos"),
        ("freno_mano", "Revisión del freno de mano hidráulico"),
        ("repartidor", "Ajuste del repartidor de frenada"),
    ]),
    ("Suspensión y dirección", [
        ("amortiguadores_reglaje", "Revisión / reglaje de amortiguadores"),
        ("amortiguadores_servicio", "Mantenimiento de amortiguadores (aceite, retenes)"),
        ("muelles", "Cambio de muelles de suspensión"),
        ("rotulas", "Revisión / cambio de rótulas"),
        ("silentblocks", "Revisión / cambio de silentblocks y casquillos"),
        ("trapecios", "Revisión / cambio de trapecios"),
        ("direccion", "Revisión de dirección (cremallera, terminales, columna)"),
        ("volante", "Revisión de volante y piña de desmontaje rápido"),
        ("alineacion", "Alineación: convergencia, caída y avance"),
        ("bujes", "Revisión de bujes y rodamientos de rueda"),
    ]),
    ("Ruedas y neumáticos", [
        ("neumaticos_cambio", "Cambio de neumáticos"),
        ("neumaticos_presion", "Ajuste de presiones"),
        ("neumaticos_rotacion", "Rotación de neumáticos"),
        ("llantas", "Revisión / reparación de llantas"),
        ("tuercas_rueda", "Apriete de tuercas / espárragos de rueda"),
    ]),
    ("Chasis y carrocería", [
        ("chasis_revision", "Revisión de chasis y soldaduras"),
        ("chasis_reparacion", "Reparación de chasis tras golpe"),
        ("paneles", "Reparación / cambio de paneles y pontones"),
        ("aleron", "Revisión / reparación del alerón"),
        ("parachoques", "Revisión de defensas y paragolpes"),
        ("tornilleria", "Repaso general de tornillería"),
        ("lavado", "Lavado y limpieza general"),
    ]),
    ("Combustible", [
        ("deposito", "Revisión del depósito FT3 y respiradero"),
        ("conductos_gasolina", "Revisión de conductos y racores de combustible"),
        ("filtro_gasolina", "Cambio de filtro de gasolina"),
        ("bomba_gasolina", "Revisión de bomba de gasolina"),
    ]),
    ("Sistema eléctrico", [
        ("bateria", "Revisión / carga / cambio de batería"),
        ("cableado", "Revisión de cableado y conectores"),
        ("cortacorrientes", "Revisión del cortacorrientes"),
        ("motor_arranque", "Revisión de motor de arranque y regulador"),
        ("luz_lluvia", "Revisión de luz de lluvia / freno"),
        ("transponder", "Revisión / fijación del transponder"),
    ]),
    ("Seguridad", [
        ("arnes", "Revisión / cambio de arnés"),
        ("asiento", "Revisión del baquet y sus anclajes"),
        ("extincion", "Revisión / recarga del sistema de extinción"),
        ("redes", "Revisión / cambio de redes de ventanilla"),
        ("jaula", "Revisión de la estructura antivuelco"),
        ("espejos", "Revisión de espejos"),
    ]),
    ("Revisiones generales", [
        ("pre_carrera", "Revisión pre-carrera (check-list completo)"),
        ("post_carrera", "Revisión post-carrera"),
        ("verificaciones", "Preparación para verificaciones técnicas"),
        ("puesta_punto", "Puesta a punto / setup para circuito"),
        ("otro", "Otro (detallar en observaciones)"),
    ]),
]
OPERACIONES_LABELS = {k: label for _, ops in CATALOGO_OPERACIONES for k, label in ops}
OPERACIONES_CATEGORIA = {k: cat for cat, ops in CATALOGO_OPERACIONES for k, _ in ops}


class MantenimientoVehiculo(db.Model):
    # No "mantenimientos_vehiculo": ese nombre ya lo ocupa en algunas BBDD
    # locales una tabla huérfana de un prototipo anterior con otro esquema.
    __tablename__ = "mecanica_mantenimientos"

    id = db.Column(db.Integer, primary_key=True)
    vehiculo_id = db.Column(db.Integer, db.ForeignKey("vehiculos.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    fecha = db.Column(db.Date, nullable=False, index=True)
    # Claves de CATALOGO_OPERACIONES separadas por comas.
    operaciones = db.Column(db.Text, nullable=False, default="")
    titulo = db.Column(db.String(150), default="")
    descripcion = db.Column(db.Text, default="")
    piezas = db.Column(db.Text, default="")
    # Contador de vueltas del vehículo en el momento del mantenimiento.
    vueltas = db.Column(db.Integer, nullable=True)
    coste = db.Column(db.Float, nullable=True)
    realizado_por = db.Column(db.String(100), default="")
    proxima_fecha = db.Column(db.Date, nullable=True)
    proximas_vueltas = db.Column(db.Integer, nullable=True)
    creado_en = db.Column(db.DateTime, default=datetime.utcnow)
    creado_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)

    vehiculo = db.relationship(
        "Vehiculo",
        backref=db.backref("mantenimientos", cascade="all, delete-orphan", lazy="dynamic",
                           order_by="MantenimientoVehiculo.fecha.desc()"),
    )
    creado_por = db.relationship("Usuario", foreign_keys=[creado_por_id])

    @property
    def operaciones_lista(self):
        return [k for k in (self.operaciones or "").split(",") if k]

    @property
    def operaciones_labels(self):
        return [OPERACIONES_LABELS.get(k, k) for k in self.operaciones_lista]

    @property
    def titulo_display(self):
        if self.titulo:
            return self.titulo
        labels = self.operaciones_labels
        if not labels:
            return "Mantenimiento"
        return labels[0] if len(labels) == 1 else f"{labels[0]} y {len(labels) - 1} más"
