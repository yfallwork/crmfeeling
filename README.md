<div align="center">
  <img src="app/static/img/feeling_experience/logo_completo.png" alt="Feeling Experience" height="60" />
  <h1>CRM Feeling Experience</h1>
  <p><strong>Sistema de gestión integral para experiencias B2C y Team Building B2B</strong></p>

  ![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
  ![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask&logoColor=white)
  ![SQLite](https://img.shields.io/badge/SQLite-SQLAlchemy-003B57?style=flat-square&logo=sqlite&logoColor=white)
  ![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?style=flat-square&logo=bootstrap&logoColor=white)
  ![APScheduler](https://img.shields.io/badge/APScheduler-3.10-FF6B35?style=flat-square)
</div>

---

## ¿Qué es esto?

CRM privado construido a medida para **Feeling Experience**, empresa de experiencias gastronómicas y de ocio. Gestiona clientes particulares (B2C), empresas de Team Building (B2B), reservas, marketing automatizado y el módulo AutoClub de socios.

No es un CRM genérico — cada módulo está diseñado alrededor del negocio real de Feeling Experience.

---

## Módulos

### 🏠 Dashboard
Panel de control con KPIs en tiempo real: reservas del mes, ingresos, nuevos clientes, tasa de conversión y actividad reciente. Vista rápida de próximas reservas y últimos logs del sistema.

### 👥 Clientes (B2C)
Ficha completa por cliente: datos personales, historial de reservas, etiquetas de marketing asignadas, comunicaciones enviadas y log de actividad. Sincronización bidireccional con WooCommerce vía webhook.

### 🏢 Reservas
Gestión completa del ciclo de reserva: creación, edición, estados (`pendiente → reservado → realizado → cancelado`), precio, participantes y notas internas. Soporte para reservas B2C (cliente) y B2B (empresa). Recordatorios automáticos por email 48h antes.

### 📅 Calendario
Vista mensual de reservas con FullCalendar 6. Responsive completo con FAB y bottom-sheet en móvil.

### 📊 Estadísticas
Gráficas de ingresos por mes, distribución por tipo de experiencia, fuente de captación y tasa de cancelación.

### 🎯 Marketing
Módulo completo de automatización de marketing:

| Sección | Descripción |
|---|---|
| **Dashboard** | Stats globales de etiquetas, normas, campañas y notificaciones |
| **Etiquetas** | Sistema de tags B2C/B2B con colores, segmentos y triggers automáticos |
| **Plantillas Email** | Editor de plantillas con variables dinámicas y vista previa |
| **Plantillas WhatsApp** | Mensajes WA con chips de variables (`{{nombre}}`, `{{empresa}}`…) y preview en burbuja |
| **Normas** | Motor de automatización: trigger → condiciones → acciones (email, WA, notificación) |
| **Campañas** | Envíos masivos segmentados por etiquetas, programables con APScheduler |
| **Calendario** | Vista de campañas programadas; click en día crea campaña pre-fechada |
| **Trazabilidad** | Ficha individual por cliente/empresa: timeline, campañas recibidas, historial de tags |
| **Logs** | Registro completo de todas las acciones automáticas con resultado y origen |

**Triggers automáticos incluidos:**
- 🏆 **VIP** — cliente con ≥3 reservas o gasto acumulado alto
- 🎂 **Aniversario** — reserva cumple 1 año
- ⏰ **Temporales** — tags con fecha de caducidad (ej. oferta de verano)
- 🏗️ **Gran Cuenta** — empresa con ≥5 reservas o volumen B2B alto
- 🛒 **Carrito abandonado** — checkout sin completar (vía webhook WooCommerce)

### 🏗️ Team Building (B2B)
Gestión de empresas clientes B2B: datos corporativos, logos, redes sociales, sector, persona de contacto y estado activo/inactivo. Sistema de notas internas por empresa (historial de llamadas, seguimientos, presupuestos).

### 🛡️ AutoClub
Módulo de gestión de socios del club privado: alta, renovación, seguimiento de cuotas, patrocinadores y dashboard propio.

### 🔗 WooCommerce
Sincronización de pedidos y clientes desde la tienda online. Webhook para eventos en tiempo real (nuevo pedido, checkout abandonado).

### 📅 Agenda Social
Calendario de eventos de agenda corporativa con temáticas, empresas asociadas y vistas por filtro.

---

## Stack técnico

```
Backend      Flask 3.0 + SQLAlchemy + Flask-Login
Base de datos  SQLite (dev) / PostgreSQL-ready (prod)
Scheduler    APScheduler 3.10 — tareas cada 5 min (campañas) y diarias (triggers)
Email        Flask-Mail + SMTP (DonDominio / cualquier proveedor)
WhatsApp     Twilio API (sandbox o número verificado)
Frontend     Bootstrap 5.3 + Bootstrap Icons + FullCalendar 6
CSS          Sistema de diseño propio (variables CSS, paleta #AD1726)
```

---

## Estructura del proyecto

```
crmfeeling/
├── app/
│   ├── models/          # SQLAlchemy models
│   │   ├── cliente.py
│   │   ├── empresa.py
│   │   ├── empresa_nota.py
│   │   ├── reserva.py
│   │   ├── tag.py
│   │   ├── rule.py          # Normas de automatización
│   │   ├── campana.py       # Campañas + PlantillaWA
│   │   ├── marketing_log.py
│   │   └── ...
│   ├── routes/          # Blueprints Flask
│   │   ├── clientes.py
│   │   ├── reservas.py
│   │   ├── marketing.py
│   │   ├── teambuilding.py
│   │   ├── autoclub.py
│   │   └── ...
│   ├── services/        # Lógica de negocio
│   │   ├── campana_service.py
│   │   ├── trigger_engine.py
│   │   ├── vip_criterio.py
│   │   ├── temporal_tags.py
│   │   └── ...
│   ├── templates/       # Jinja2 templates
│   ├── static/          # CSS, JS, imágenes
│   ├── scheduler.py     # APScheduler jobs
│   └── __init__.py      # create_app() + seeds
├── config.py
├── requirements.txt
└── run.py
```

---

## Instalación y arranque

### Requisitos
- Python 3.11+
- pip

### Setup

```bash
# 1. Clonar el repositorio
git clone https://github.com/yfallwork/crmfeeling.git
cd crmfeeling

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 5. Arrancar la app
python run.py
```

La app arranca en `http://localhost:5000`. La primera vez crea la base de datos y siembra datos de ejemplo automáticamente.

**Usuario por defecto:** `admin` / `admin123`

---

## Variables de entorno

```env
SECRET_KEY=tu-clave-secreta

# Base de datos (por defecto SQLite local)
DATABASE_URL=sqlite:///crm.db

# WooCommerce
WOO_BASE_URL=https://tu-tienda.com
WOO_CONSUMER_KEY=ck_...
WOO_CONSUMER_SECRET=cs_...
WOO_WEBHOOK_SECRET=tu-webhook-secret

# Email (SMTP)
MAIL_SERVER=smtp.tuproveedor.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=tu@email.com
MAIL_PASSWORD=tu-password
MAIL_DEFAULT_SENDER=tu@email.com

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
```

---

## Datos de ejemplo

Al arrancar por primera vez se crean automáticamente:
- 4 empresas B2B con reservas
- Clientes B2C de ejemplo
- Etiquetas de segmentación
- Plantillas de email y WhatsApp
- 3 campañas (borrador, programada, enviada)
- Normas de automatización
- Logs de marketing
- 9 notas internas de empresa
- Socios y patrocinadores AutoClub

---

## Roadmap

- [ ] Mejorar módulo de notas de empresas (menciones, adjuntos, recordatorios)
- [ ] Panel de estadísticas de marketing (open rate, conversión por campaña)
- [ ] Exportación de clientes y campañas a CSV/Excel
- [ ] Integración real de envío WhatsApp (número Twilio verificado)
- [ ] App móvil PWA
- [ ] Multi-tenant (varias empresas en la misma instancia)

---

<div align="center">
  <sub>Desarrollado a medida para <strong>Feeling Experience</strong> · Sistema interno · No es software open source</sub>
</div>
