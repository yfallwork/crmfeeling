"""
Carga inicial del calendario de publicaciones octubre 2026 – enero 2027
(calendario_feeling_v6.pdf, actualizado el 3 nov 2026). Solo se ejecuta si
no hay ni publicaciones ni campañas de redes todavía.
"""
from datetime import date

CAMPANAS = {
    "navidad": ("Campaña de Navidad · Pack Rivales y Pack Fin de Semana", date(2026, 11, 23), date(2027, 1, 5), "#A16207",
                "Pack Rivales (2 pilotos · 325 €) del 23 nov al 5 ene y Pack Fin de Semana (carcross + cena + noche en Las Horneras de Cobeta) desde el 3 dic."),
    "meta1": ("Anuncio Meta · Pack Rivales", date(2026, 11, 23), date(2026, 12, 1), "#0369A1",
              "9 días · 50 $ · objetivo Mensajes. Provincias de Madrid, Guadalajara y Zaragoza, 25–55 años."),
    "meta2": ("Segundo anuncio Meta · Regalo de última hora", date(2026, 12, 14), date(2026, 12, 22), "#0369A1",
              "Solo si el primer anuncio vendió al menos 1 pack (decisión el 2 dic)."),
}

JEREZ = "Jerez de los Caballeros · Javi Mimbrera y José Ángel Moratilla"
CERX = "CERX · MotorLand Aragón · Sara Espada, Fabiola y Javi Mimbrera"

# (fecha, categoria, tipo, titulo, formato, produccion, indicaciones, estado, campana)
PUBLICACIONES = [
    (date(2026, 10, 17), "academy", "post", "¿Y si el que derrapa la próxima vez eres tú?", "Post", "", "", "publicado", None),
    (date(2026, 10, 19), "competicion", "historias", "Pilotos que van a Jerez de los Caballeros", "Historia con foto de cada piloto + cuenta atrás", "",
     "Una historia por piloto: foto con el casco o el mono, nombre y categoría [por confirmar]. Última historia: cuenta atrás al viernes 23. Etiquetad a cada piloto para que la compartan.", "publicado", None),
    (date(2026, 10, 20), "opiniones", "post", "Así se vivió el sábado 17 en Feeling Academy", "Reel", "",
     "Publicado el 20 oct (38 me gusta). Llamada: EXPERIENCIA por DM.", "publicado", None),
    (date(2026, 10, 21), "opiniones", "historias", "FAQ: ¿Y si llueve?", "3 historias", "",
     "Pregunta, respuesta («Se cambia la fecha sin coste») y enlace. Añadidlas a la destacada FAQ.", "publicado", None),
    (date(2026, 10, 23), "competicion", "evento", JEREZ, "Historias en directo", "", "Los dos terminan 7º, remontando desde el último puesto en la final.", "publicado", None),
    (date(2026, 10, 24), "competicion", "evento", JEREZ, "Historias en directo", "", "Los dos terminan 7º, remontando desde el último puesto en la final.", "publicado", None),
    (date(2026, 10, 25), "competicion", "evento", JEREZ, "Historias en directo", "", "Los dos terminan 7º, remontando desde el último puesto en la final.", "publicado", None),
    (date(2026, 10, 27), "competicion", "post", "Resumen de Jerez de los Caballeros: dos remontadas hasta el 7º", "Carrusel en colaboración con @autoclub_ladehesa_132", "",
     "Publicado el 27 oct (75 me gusta). Queda sin responder el comentario de duende_lew: contestadle.", "publicado", None),
    (date(2026, 10, 28), "opiniones", "historias", "FAQ: ¿Puedo ir con mi hijo?", "3 historias", "",
     "Respuesta: sí, no hay edad mínima. Fondo: 08_para_todos.mp4. A la destacada FAQ.", "publicado", None),
    (date(2026, 10, 29), "competicion", "post", "Último reto de la temporada… y ya pensando en 2027", "Reel en colaboración con @autoclub_ladehesa_132", "",
     "Publicado el 29 oct: Sara Espada, Fabiola y Javi Mimbrera rumbo a MotorLand, y búsqueda de pilotos, mecánicos y equipo para 2027.", "publicado", None),
    (date(2026, 11, 2), "academy", "post", "Primeros contactos de Fabiola con su nueva montura", "Reel", "", "Publicado el 2 nov (38 me gusta).", "publicado", None),
    (date(2026, 11, 2), "academy", "post", "Últimos entrenamientos antes de la gran cita", "Reel en colaboración con @autoclub_ladehesa_132", "",
     "Publicado el 2 nov: el mejor resultado hasta ahora (74 me gusta y comentarios de otras pilotos).", "publicado", None),
    (date(2026, 11, 3), "academy", "historias", "Carteles: pilotos que van al CERX MotorLand", "Una historia por piloto", "",
     "Sara Espada, Fabiola y Javi Mimbrera. Subidas el 3 nov. Guardadlas en la destacada RACING TEAM.", "publicado", None),
    (date(2026, 11, 4), "competicion", "historias", "Así fue Jerez + cuenta atrás a MotorLand", "Historias", "ya_montado",
     "Vuestro vídeo corto de Jerez como historia y, detrás, la cuenta atrás al sábado 7.", "pendiente", None),
    (date(2026, 11, 5), "ventas", "historias", "Ven tú también a sentirte como un piloto", "3 historias con enlace", "ya_montado",
     "Engancha con el CERX del fin de semana. 1) 07_a_fondo.mp4: «Este finde, nuestros pilotos en MotorLand». 2) 05_casco_y_equipo.mp4: «Ven tú también a sentirte como un piloto · sin carnet, desde 169 €». 3) 02_donde.mp4: «Próxima fecha: sábado 21 de noviembre» + sticker de enlace a la web. Fondos en videos/destacada_como_es/.", "pendiente", None),
    (date(2026, 11, 6), "academy", "historias", "Rumbo a MotorLand", "Historias", "sin_editar", "Carga del remolque, viaje y llegada al paddock.", "pendiente", None),
    (date(2026, 11, 7), "academy", "evento", CERX, "Historias en directo", "sin_editar",
     "Última prueba de la temporada. Paddock, casco puesto, salida y primeras palabras al bajar del coche. Fotos para el carrusel del martes.", "pendiente", None),
    (date(2026, 11, 8), "academy", "evento", CERX, "Historias en directo", "sin_editar",
     "Última prueba de la temporada. Paddock, casco puesto, salida y primeras palabras al bajar del coche. Fotos para el carrusel del martes.", "pendiente", None),
    (date(2026, 11, 9), "competicion", "historias", "Pilotos que van al Regional de Aragón en Aguaviva", "Historia con foto de cada piloto + cuenta atrás", "sin_editar",
     "Una historia por piloto con nombre y foto, etiquetados. Última: cuenta atrás al sábado 14.", "pendiente", None),
    (date(2026, 11, 10), "academy", "post", "Así fue el CERX en MotorLand", "Carrusel de fotos en colaboración con @autoclub_ladehesa_132", "sin_editar",
     "Resultados de Sara, Fabiola y Javi: [por confirmar]. Etiquetad a pilotos, patrocinadores y @cerx_rfeda. Llamada: «¿Quieres ser piloto en 2027? ACADEMIA por DM».", "pendiente", None),
    (date(2026, 11, 11), "competicion", "historias", "Este sábado, Regional de Aragón en Aguaviva", "Historia con cuenta atrás", "sin_editar",
     "Recordatorio a mitad de semana: foto del coche preparado y cuenta atrás al sábado 14.", "pendiente", None),
    (date(2026, 11, 12), "fechas", "historias", "Últimas plazas: sábado 21", "Historia con la plantilla Calendario", "canva",
     "Una sola fecha en grande y enlace. «Reserva antes del jueves 19».", "pendiente", None),
    (date(2026, 11, 13), "opiniones", "post", "«Experiencia de 10», en palabras de David Lara", "Reel", "ya_montado",
     "Vuestro vídeo ya preparado. Llamada: «Últimas plazas para el sábado 21. Reserva en la bio».", "pendiente", None),
    (date(2026, 11, 14), "competicion", "evento", "Regional de Aragón · Aguaviva", "Historias en directo", "sin_editar",
     "Paddock, salida y resultado. Guardad fotos para el carrusel del lunes.", "pendiente", None),
    (date(2026, 11, 15), "competicion", "historias", "Así fue Aguaviva", "Historias", "sin_editar", "Resultado y fotos del sábado. Etiquetad a la organización.", "pendiente", None),
    (date(2026, 11, 16), "ventas", "historias", "Encuesta: ¿Con quién te picarías en la pista?", "Historia con encuesta", "sin_editar",
     "Opciones: Mi pareja / Mi hermano / Un amigo. Calienta la campaña Pack Rivales sin anunciarla todavía.", "pendiente", None),
    (date(2026, 11, 17), "competicion", "post", "Resumen de la temporada [CEAX] 2026", "Reel", "video_por_editar",
     "Lo mejor de todas las pruebas del año y los resultados de cada piloto [por confirmar]. Hacen falta los clips de cada carrera. Cierre: «2027 ya está en marcha: ¿pilotos, mecánicos o equipo? Escríbenos».", "pendiente", None),
    (date(2026, 11, 18), "fechas", "historias", "Quedan [X] plazas para el sábado", "Historia con cuenta atrás", "sin_editar", "Siempre con el número real de plazas.", "pendiente", None),
    (date(2026, 11, 19), "ventas", "post", "El regalo que no acaba en un cajón", "Reel", "ya_montado",
     "Vuestro vídeo ya preparado. Calienta la campaña: el Pack Rivales sale el lunes 23. Llamada: «Regálalo desde la bio».", "pendiente", None),
    (date(2026, 11, 20), "navidad", "tarea", "Preparar el anuncio de Meta", "Tarea", "video_por_editar",
     "Elegir el reel con más guardados y compartidos y añadirle un final «Pack Rivales · 2 pilotos · 325 €». Crear el código RIVALESIG y comprobar que el Pack Rivales ya se puede comprar en la web.", "pendiente", "meta1"),
    (date(2026, 11, 21), "fechas", "evento", "Experiencia carcross · La Dehesa", "Historias en directo", "sin_editar",
     "Seguid la lista de tomas. Al acabar, pedid a cada cliente una reseña en Google y un vídeo de 10 s respondiendo «¿qué tal?».", "pendiente", None),
    (date(2026, 11, 22), "opiniones", "post", "Así fue el sábado en La Dehesa", "Carrusel de 8 fotos", "sin_editar",
     "Caras con el casco en la mano, grupo y derrapes. Etiquetad a quien lo acepte.", "pendiente", None),
    (date(2026, 11, 23), "navidad", "anuncio", "Anuncio Meta: arranca (9 días · 50 $)", "Anuncio · objetivo Mensajes", "sin_editar",
     "Administrador de anuncios → objetivo «Mensajes» (WhatsApp o DM), no el botón «Promocionar». ~5 €/día del 23 nov al 1 dic. Anuncio: reel con final «Pack Rivales · 325 €». Provincias de Madrid, Guadalajara y Zaragoza, 25–55 años.", "pendiente", "meta1"),
    (date(2026, 11, 23), "navidad", "post", "Este año, regálale un rival: Pack Rivales", "Plantilla Canva + historia", "canva",
     "Lanzamiento: 2 pilotos, 3 vueltas cada uno, 325 € (162,50 € por piloto). Fecha abierta 1 año. Publicadlo como colaboración con @autoclub_ladehesa_132. El Pack Fin de Semana sale el 3 de diciembre: este día, un solo mensaje.", "pendiente", "navidad"),
    (date(2026, 11, 25), "navidad", "historias", "Etiqueta a tu rival", "Historia con caja de preguntas", "sin_editar",
     "«¿A quién retarías? Etiquétalo en tu historia y menciónanos». Compartid las que os lleguen.", "pendiente", "navidad"),
    (date(2026, 11, 27), "navidad", "tarea", "Anuncio: revisión a mitad de campaña", "Tarea · 10 min", "sin_editar",
     "Mirar coste por conversación y mensajes recibidos. Si un anuncio va claramente peor, pausarlo. Responder todos los mensajes el mismo día.", "pendiente", "meta1"),
    (date(2026, 11, 27), "navidad", "post", "Black Friday: dos amigos, un circuito, un ganador", "Reel", "video_por_editar",
     "Clips del 21 de noviembre con dos pilotos picándose y cierre «Pack Rivales · 325 €». Historias de viernes a domingo.", "pendiente", "navidad"),
    (date(2026, 11, 28), "navidad", "historias", "Black Friday: Pack Rivales", "3 historias con enlace", "sin_editar",
     "Repetid el post, el «¿quién ganaría?» y el enlace.", "pendiente", "navidad"),
    (date(2026, 12, 1), "navidad", "anuncio", "Anuncio: último día", "Anuncio", "sin_editar", "Termina la campaña de 9 días.", "pendiente", "meta1"),
    (date(2026, 12, 1), "team_building", "post", "Así cambia un equipo cuando le das un casco y 125 CV", "Reel", "video_por_editar",
     "El reel de Hankook recortado a 20 s, con los textos «Hankook trajo a su equipo»… Llamada: «¿Evento de empresa en enero? Escríbenos EMPRESA». Une el caso Hankook con el regalo de empresa: Pack Rivales para empleados o clientes.", "pendiente", None),
    (date(2026, 12, 2), "navidad", "tarea", "Anuncio: resultados y decisión", "Tarea · 15 min", "sin_editar",
     "Contar conversaciones, Packs Rivales vendidos con el código RIVALESIG y euros gastados. Si se vendió al menos 1 pack, repetir del 14 al 22 de diciembre con «Regalo de última hora».", "pendiente", "meta1"),
    (date(2026, 12, 2), "navidad", "historias", "Repost: quién ha regalado un Pack Rivales", "Historias", "sin_editar",
     "Compartid las historias de quien os etiquete con su rival. Si no hay, encuesta «¿Quién ganaría?».", "pendiente", "navidad"),
    (date(2026, 12, 3), "navidad", "post", "Pack Fin de Semana: derrapa, cena y quédate a dormir", "Carrusel de 5 · plantilla Canva", "canva",
     "Lanzamiento del segundo pack: carcross en La Dehesa + cena en el restaurante de horno de leña de Las Horneras de Cobeta + noche en un apartamento con chimenea. Precio: [por confirmar]. Fotos de la carpeta LAS HORNERAS de HiDrive. Publicadlo como colaboración con la cuenta de Las Horneras [usuario por confirmar].", "pendiente", "navidad"),
    (date(2026, 12, 5), "navidad", "historias", "Así es Las Horneras de Cobeta", "4 historias", "sin_editar",
     "El apartamento, la chimenea, el horno de leña y el pueblo. Enlace al Pack Fin de Semana. Añadidlas a la destacada PRECIOS.", "pendiente", "navidad"),
    (date(2026, 12, 8), "academy", "post", "¿Quieres ser piloto en 2027?", "Reel", "video_por_editar",
     "Con clips de MotorLand y de los entrenamientos. Continúa el post del 29 oct: pilotos, mecánicos y equipo. Llamada: «ACADEMIA por DM».", "pendiente", None),
    (date(2026, 12, 10), "navidad", "historias", "Encuesta: ¿Rivales o Fin de Semana?", "Historia con encuesta", "sin_editar",
     "«¿Qué regalarías: un rival (Pack Rivales) o una escapada (Pack Fin de Semana)?». El resultado decide el anuncio del 14.", "pendiente", "navidad"),
    (date(2026, 12, 11), "fechas", "post", "Mañana, última experiencia del año", "Plantilla Calendario", "canva",
     "«Sábado 12 de diciembre» y debajo «Siguiente: sábado 16 de enero» + «Regálalo: Pack Rivales, 325 €».", "pendiente", None),
    (date(2026, 12, 12), "fechas", "evento", "Experiencia carcross · La Dehesa", "Historias en directo", "sin_editar",
     "Misma lista de tomas que el 21 de noviembre.", "pendiente", None),
    (date(2026, 12, 14), "navidad", "anuncio", "Segundo anuncio: Pack Fin de Semana para parejas (si el primero funcionó)", "Anuncio · objetivo Mensajes", "sin_editar",
     "Del 14 al 22 de diciembre, objetivo «Mensajes», con el carrusel o un reel del Pack Fin de Semana. Si la encuesta del 10 la gana Rivales, anunciad Rivales. Con un ticket más alto, una sola venta cubre el anuncio varias veces.", "pendiente", "meta2"),
    (date(2026, 12, 15), "opiniones", "post", "¿Qué tal? Los pilotos del sábado", "Reel", "video_por_editar",
     "Los vídeos de 10 s de los clientes del 12, uno detrás de otro.", "pendiente", None),
    (date(2026, 12, 16), "navidad", "historias", "Encuesta: ¿Quién gana, tú o tu rival?", "Historia con encuesta", "sin_editar",
     "Encuesta sobre un clip de dos coches en paralelo. Debajo, enlace al Pack Rivales.", "pendiente", "navidad"),
    (date(2026, 12, 18), "navidad", "post", "Regalo de última hora: Pack Rivales o Pack Fin de Semana, al momento", "Plantilla Canva", "canva",
     "Los dos packs, bono digital + tarjeta para imprimir. Confirmad cómo y cuándo llega el bono. Llamada: «Cómpralo hoy y regálalo en Nochebuena o en Reyes».", "pendiente", "navidad"),
    (date(2026, 12, 21), "navidad", "historias", "¿Llegas a Reyes? Te llega al momento", "Historias", "sin_editar",
     "La campaña sigue hasta el 5 de enero: en España muchos regalos se hacen en Reyes.", "pendiente", "navidad"),
    (date(2026, 12, 22), "opiniones", "post", "Lo que dicen quienes ya lo han probado", "Carrusel de reseñas", "canva",
     "5–7 reseñas reales con permiso. Cierre: «Pack Rivales y Pack Fin de Semana: hasta Reyes».", "pendiente", "navidad"),
    (date(2026, 12, 24), "ventas", "historias", "Felicitación del equipo", "Historia", "sin_editar", "Vídeo del equipo en el circuito. Sin venta.", "pendiente", None),
    (date(2026, 12, 26), "ventas", "historias", "¿Te lo han regalado? Así se canjea", "3 historias", "sin_editar",
     "1. Elige fecha. 2. Escríbenos por WhatsApp o en la web. 3. Ven a pilotar.", "pendiente", None),
    (date(2026, 12, 28), "navidad", "historias", "Aún llegas a Reyes: Pack Rivales", "Historias con enlace", "sin_editar",
     "Los dos packs: bono digital al momento + tarjeta para imprimir. La campaña acaba el 5 de enero.", "pendiente", "navidad"),
    (date(2026, 12, 29), "ventas", "post", "2026 en La Dehesa", "Reel resumen", "video_por_editar",
     "Lo mejor del año: CEAX, Aguaviva, CERX y las experiencias. Cifras reales: [nº de pilotos].", "pendiente", None),
    (date(2027, 1, 2), "fechas", "post", "¿Te lo han regalado? Elige fecha: 16 de enero", "Plantilla Calendario", "canva",
     "Y las fechas de febrero y marzo [por confirmar]. Para el Pack Fin de Semana: noche en Las Horneras el viernes 15 o el sábado 16.", "pendiente", None),
    (date(2027, 1, 4), "navidad", "historias", "Último día para regalarlo en Reyes", "Historias con cuenta atrás", "sin_editar",
     "Cuenta atrás al 5 de enero a las 23:59.", "pendiente", "navidad"),
    (date(2027, 1, 5), "navidad", "post", "Mañana es Reyes: Pack Rivales o Pack Fin de Semana, al momento", "Post o historia · plantilla", "canva",
     "Último post de la campaña. Llamada: «Cómpralo hoy y te llega por email». Después, el Pack Fin de Semana puede seguir hasta San Valentín.", "pendiente", "navidad"),
    (date(2027, 1, 16), "fechas", "evento", "Experiencia carcross · La Dehesa", "Historias en directo", "sin_editar",
     "Primera fecha de 2027: canje de los bonos de Navidad.", "pendiente", None),
]


def migrar_en_directo():
    """Añade la columna en_directo a BBDD existentes y, solo en ese momento,
    marca como "en el momento" las historias en directo de los días de
    evento ya cargadas (no se tocan después: lo que cambie el usuario se
    respeta)."""
    from sqlalchemy import inspect, text
    from app.extensions import db

    columnas = {c["name"] for c in inspect(db.engine).get_columns("publicaciones_rrss")}
    if "en_directo" in columnas:
        return
    with db.engine.begin() as conn:
        conn.execute(text("ALTER TABLE publicaciones_rrss ADD COLUMN en_directo BOOLEAN NOT NULL DEFAULT 0"))
        conn.execute(text("UPDATE publicaciones_rrss SET en_directo = 1 WHERE tipo = 'evento'"))


def seed_publicaciones():
    from app.extensions import db
    from app.models.publicacion_rrss import CampanaRRSS, PublicacionRRSS

    migrar_en_directo()
    if CampanaRRSS.query.count() or PublicacionRRSS.query.count():
        return
    campanas = {}
    for clave, (nombre, ini, fin, color, desc) in CAMPANAS.items():
        c = CampanaRRSS(nombre=nombre, fecha_inicio=ini, fecha_fin=fin, color=color, descripcion=desc)
        db.session.add(c)
        campanas[clave] = c
    db.session.flush()
    for fecha, cat, tipo, titulo, formato, prod, indic, estado, camp in PUBLICACIONES:
        db.session.add(PublicacionRRSS(
            fecha=fecha, categoria=cat, tipo=tipo, titulo=titulo, formato=formato,
            produccion=prod, indicaciones=indic, estado=estado, en_directo=(tipo == "evento"),
            campana_id=campanas[camp].id if camp else None,
        ))
    db.session.commit()
