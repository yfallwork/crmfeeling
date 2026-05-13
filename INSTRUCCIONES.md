# CRM Regaloexperiencias

## Inicio rápido (Windows)

```bash
cd crm_experiencias

# 1. Crear entorno virtual
python -m venv venv
venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env
# Edita .env con tus credenciales de WooCommerce, email, etc.

# 4. Inicializar base de datos con datos de ejemplo
python init_db.py

# 5. Arrancar el servidor
python run.py
```

Accede en: http://localhost:5000

**Credenciales por defecto:**
- Admin: `admin@crm.local` / `admin123`

---

## Configurar WooCommerce

1. En WordPress: **WooCommerce → Ajustes → Avanzado → API REST**
2. Crear nueva clave con permisos de **Lectura**
3. Copiar `Consumer Key` y `Consumer Secret` en `.env`

```
WOO_BASE_URL=https://www.regaloexperiencias.com
WOO_CONSUMER_KEY=ck_...
WOO_CONSUMER_SECRET=cs_...
```

4. En el CRM: **WooCommerce → Probar conexión → Sincronizar**

---

## Despliegue en PythonAnywhere

1. Subir archivos al directorio del proyecto
2. En la consola de PythonAnywhere:
```bash
pip install -r requirements.txt --user
python init_db.py
```
3. En **Web → WSGI configuration file**, apuntar a `run.py`
4. Configurar variables de entorno en el panel de PythonAnywhere

---

## Estructura del proyecto

```
crm_experiencias/
├── run.py                  # Punto de entrada
├── config.py               # Configuración por entorno
├── init_db.py              # Inicializar BD con datos de ejemplo
├── requirements.txt
├── .env                    # Variables de entorno (no subir a git)
└── app/
    ├── __init__.py         # App factory
    ├── extensions.py       # SQLAlchemy, Login, Mail
    ├── models/
    │   ├── usuario.py      # Usuarios del CRM
    │   ├── cliente.py      # Clientes
    │   ├── experiencia.py  # Tipos de experiencia
    │   └── reserva.py      # Reservas (modelo principal)
    ├── routes/
    │   ├── auth.py         # Login/logout
    │   ├── dashboard.py    # Panel principal
    │   ├── clientes.py     # CRUD clientes
    │   ├── reservas.py     # CRUD reservas
    │   ├── calendario.py   # Calendario + API drag&drop
    │   ├── woocommerce.py  # Sync WooCommerce
    │   └── api.py          # API interna (notificaciones, stats)
    ├── services/
    │   ├── woo_sync.py     # Lógica de sincronización WooCommerce
    │   ├── email_service.py# Envío de emails
    │   └── whatsapp_service.py # WhatsApp vía Twilio
    └── templates/
        ├── base.html       # Layout con sidebar
        ├── auth/login.html
        ├── dashboard/index.html
        ├── clientes/{lista,detalle,form}.html
        ├── reservas/{lista,detalle,form}.html
        ├── calendario/index.html
        └── woocommerce/sync.html
```

---

## API interna (para integrar con WordPress)

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/clientes` | GET | Buscar clientes (`?q=nombre`) |
| `/api/reservas` | GET | Listar reservas (`?estado=pendiente`) |
| `/api/reservas/<id>/fecha` | PATCH | Actualizar fecha de disfrute |
| `/api/reservas/<id>/notificar` | POST | Enviar email/WhatsApp |
| `/api/stats/dashboard` | GET | Estadísticas resumen |

---

## Migrar a PostgreSQL

Cambiar en `.env`:
```
DATABASE_URL=postgresql://usuario:password@host/nombre_bd
```
Y añadir `psycopg2-binary` a `requirements.txt`. El resto del código no cambia (SQLAlchemy abstrae el motor).
