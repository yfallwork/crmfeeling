# Marketing Automation — Etiquetas y Reglas

Documento de referencia para el sistema de etiquetas de marketing del CRM Feeling Experience.

---

## Conceptos clave

| Término | Descripción |
|---|---|
| **Etiqueta (Tag)** | Identificador que se aplica a un cliente o empresa para segmentarlos |
| **Sistemática** | Se asigna automáticamente cuando ocurre un evento (WooCommerce webhook o acción del CRM) |
| **Dinámica** | Se calcula periódicamente mediante una query SQL sobre los datos actuales |
| **Segmento B2C** | Aplica a clientes particulares |
| **Segmento B2B** | Aplica a empresas del módulo Team Building |
| **Trigger** | Evento que dispara la asignación de una etiqueta sistemática |
| **Origen** | Cómo se asignó la etiqueta: `manual`, `sistema`, `webhook` |

---

## Etiquetas B2C — Particulares

### Sistemáticas (auto-trigger)

Estas etiquetas se asignan automáticamente cuando WooCommerce envía un webhook al CRM o cuando el CRM registra un evento interno.

| Slug | Nombre | Trigger | Descripción |
|---|---|---|---|
| `lead_particular_nuevo` | Lead particular nuevo | `woo.order.created` | Se activa cuando WooCommerce crea un nuevo pedido de un cliente particular. Es el primer punto de contacto del cliente con la plataforma. |
| `carrito_abandonado` | Carrito abandonado | `woo.cart.abandoned` | El cliente inició el proceso de checkout pero no completó el pago. WooCommerce necesita el plugin de abandoned cart para enviar este webhook. |
| `experiencia_reservada` | Experiencia reservada | `woo.order.completed` | El pedido en WooCommerce pasó a estado `completed`, lo que indica que el pago fue procesado y la reserva está confirmada. |
| `experiencia_realizada` | Experiencia realizada | `crm.reserva.disfrutada` | El equipo del CRM marca la reserva como `disfrutado`. Dispara el webhook interno `crm.reserva.disfrutada`. |
| `compro_para_regalo` | Compró para regalo | `woo.order.gift` | El cliente marcó el pedido como regalo en el checkout de WooCommerce. Requiere campo de metadato `_is_gift = yes` en el pedido. |

**Implementación WooCommerce:**
- Configurar WooCommerce → Ajustes → Avanzado → Webhooks
- URL del endpoint: `https://tudominio.com/woocommerce/webhook`
- Eventos a suscribir: `order.created`, `order.updated`, `order.completed`
- Para `cart.abandoned` se requiere un plugin de terceros (e.g., CartFlows, Abandoned Cart Lite)

---

### Dinámicas (filtros SQL periódicos)

Estas etiquetas se recalculan periódicamente (recomendado: cada noche a las 02:00) mediante queries SQL.

| Slug | Nombre | Criterio | Query base |
|---|---|---|---|
| `cliente_dormido_particular` | Cliente dormido | Sin reservas en los últimos 180 días, habiendo tenido al menos 1 histórica | `SELECT c.id FROM clientes c WHERE EXISTS (SELECT 1 FROM reservas r WHERE r.cliente_id = c.id AND r.estado = 'disfrutado') AND NOT EXISTS (SELECT 1 FROM reservas r WHERE r.cliente_id = c.id AND r.fecha_disfrute >= date('now', '-180 days'))` |
| `cliente_vip_particular` | Cliente VIP | 3+ experiencias realizadas o gasto acumulado ≥ 500 € | `SELECT cliente_id FROM reservas WHERE estado = 'disfrutado' GROUP BY cliente_id HAVING COUNT(*) >= 3 OR SUM(precio) >= 500` |
| `local_madrid` | Local Madrid | Código postal Comunidad de Madrid (28xxx, 45xxx, 19xxx) | `SELECT id FROM clientes WHERE codigo_postal LIKE '28%' OR codigo_postal LIKE '45%' OR codigo_postal LIKE '19%'` |
| `cumpleanos_mes` | Cumpleaños este mes | El campo `fecha_nacimiento` cae en el mes actual | `SELECT id FROM clientes WHERE strftime('%m', fecha_nacimiento) = strftime('%m', 'now')` |

**Nota:** Las queries dinámicas deben ejecutarse en el Scheduler del CRM (`app/scheduler.py`). El resultado debe compararse con las asignaciones actuales para añadir nuevas y eliminar las que ya no cumplen el criterio.

---

## Etiquetas B2B — Empresas Team Building

### Sistemáticas (auto-trigger)

| Slug | Nombre | Trigger | Descripción |
|---|---|---|---|
| `lead_empresa_nuevo` | Lead empresa nuevo | `crm.empresa.creada` | Se dispara cuando se crea una nueva empresa en el módulo Team Building. |
| `descargo_dossier` | Descargó dossier | `crm.empresa.dossier_descargado` | La empresa descargó el dossier corporativo de actividades TB. Requiere botón de descarga con tracking en la web. |
| `identificado_como_empresa` | Identificado como empresa | `crm.empresa.cualificada` | El equipo comercial marca el contacto como empresa B2B cualificada. Acción manual desde el CRM. |
| `presupuesto_solicitado` | Presupuesto solicitado | `crm.empresa.presupuesto_solicitado` | La empresa solicita un presupuesto de evento TB. Puede venir de formulario web o acción del CRM. |
| `evento_empresa_realizado` | Evento empresa realizado | `crm.reserva.disfrutada` | Se reutiliza el mismo trigger que B2C pero aplicado a reservas con `empresa_id` no nulo. |

---

### Dinámicas (filtros SQL periódicos)

| Slug | Nombre | Criterio | Query base |
|---|---|---|---|
| `gran_cuenta_b2b` | Gran cuenta B2B | ≥50 participantes históricos acumulados o ≥3 eventos realizados | `SELECT empresa_id FROM reservas WHERE estado = 'disfrutado' AND empresa_id IS NOT NULL GROUP BY empresa_id HAVING SUM(num_participantes) >= 50 OR COUNT(*) >= 3` |
| `b2b_sin_contacto_3meses` | B2B sin contacto 3 meses | Sin reservas ni actividad en los últimos 90 días | `SELECT e.id FROM empresas_tb e WHERE NOT EXISTS (SELECT 1 FROM reservas r WHERE r.empresa_id = e.id AND r.fecha_compra >= date('now', '-90 days'))` |
| `recurrente_anual_b2b` | Recurrente anual B2B | Eventos realizados en 2+ años distintos | `SELECT empresa_id FROM reservas WHERE estado = 'disfrutado' AND empresa_id IS NOT NULL GROUP BY empresa_id HAVING COUNT(DISTINCT strftime('%Y', fecha_disfrute)) >= 2` |
| `interesado_navidad_b2b` | Interesado navidad B2B | Al menos 1 evento realizado en Q4 (Oct, Nov, Dic) | `SELECT DISTINCT empresa_id FROM reservas WHERE empresa_id IS NOT NULL AND strftime('%m', fecha_disfrute) IN ('10','11','12')` |

---

## Flujo de asignación

```
WooCommerce Webhook
        │
        ▼
 /woocommerce/webhook  ──► Detecta evento (order.created, etc.)
        │
        ▼
 Busca Tags con trigger_evento = evento recibido
        │
        ▼
 Para cada Tag encontrada:
   - Busca o crea ClienteTag / EmpresaTag
   - origen = "webhook"
   - asignado_en = datetime.utcnow()
        │
        ▼
 registrar_log("webhook", "tag", tag_id, detalle)
```

```
Scheduler nocturno (02:00 UTC)
        │
        ▼
 Para cada Tag dinámica activa:
   - Ejecuta la query SQL del filtro
   - Obtiene set de IDs que cumplen el criterio
   - Compara con asignaciones actuales
        │
        ├── IDs nuevos → INSERT ClienteTag / EmpresaTag (origen="sistema")
        └── IDs que ya no cumplen → DELETE ClienteTag / EmpresaTag
```

---

## Futuras reglas de automatización

Las **reglas** (Rules) son la siguiente capa sobre las etiquetas. Una regla define:
- **Condición (IF):** una o más etiquetas activas en un cliente/empresa
- **Acción (THEN):** qué ocurre automáticamente

### Reglas planificadas

| Prioridad | Nombre | Condición | Acción |
|---|---|---|---|
| Alta | Bienvenida lead particular | `lead_particular_nuevo` | Enviar email de bienvenida con catálogo de experiencias |
| Alta | Recuperar carrito abandonado | `carrito_abandonado` | Enviar email a las 24h con enlace al carrito + descuento 5% |
| Alta | Post-experiencia B2C | `experiencia_realizada` | Enviar email de valoración + oferta próxima experiencia |
| Media | Reactivar cliente dormido | `cliente_dormido_particular` | Enviar email mensual con novedades y oferta especial |
| Media | Felicitación cumpleaños | `cumpleanos_mes` | Enviar email el día del cumpleaños con código descuento 10% |
| Media | VIP upgrade | `cliente_vip_particular` | Notificación interna + email personalizado de agradecimiento |
| Alta | Bienvenida empresa B2B | `lead_empresa_nuevo` | Enviar dossier corporativo por email automáticamente |
| Alta | Follow-up presupuesto | `presupuesto_solicitado` | Recordatorio interno a los 3 días si no hay respuesta |
| Media | Campaña navidad B2B | `interesado_navidad_b2b` | Enviar propuesta Q4 en septiembre |
| Media | Reactivar B2B dormida | `b2b_sin_contacto_3meses` | Crear tarea de seguimiento para el equipo comercial |

### Estructura de datos de una regla (futuro)

```python
class Rule(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    nombre       = db.Column(db.String(150))
    descripcion  = db.Column(db.Text)
    activo       = db.Column(db.Boolean, default=True)
    # Condición: lista de tag slugs que deben estar presentes (AND)
    tags_requeridas = db.Column(db.Text)  # JSON: ["lead_empresa_nuevo"]
    # Acción
    accion_tipo  = db.Column(db.String(50))   # "email" | "webhook" | "tarea" | "notificacion"
    accion_config = db.Column(db.Text)        # JSON con parámetros de la acción
    delay_horas  = db.Column(db.Integer, default=0)  # Retraso antes de ejecutar
    una_vez      = db.Column(db.Boolean, default=True)  # No repetir si ya se ejecutó
```

---

## Colores de referencia por categoría

| Color | Hex | Uso sugerido |
|---|---|---|
| Azul | `#3B82F6` | Leads nuevos, primeros contactos |
| Verde | `#10B981` | Conversiones, experiencias realizadas |
| Morado | `#8B5CF6` | VIP, B2B, alto valor |
| Amarillo | `#F59E0B` | Atención requerida, seguimiento pendiente |
| Rojo | `#EF4444` | Riesgo, abandonos, sin contacto |
| Rosa | `#EC4899` | Campañas especiales (cumpleaños, regalo) |
| Gris | `#6B7280` | Clientes dormidos, inactivos |
| Índigo | `#6366F1` | Integraciones externas (WooCommerce, webhooks) |

---

## Notas de implementación

1. **Idempotencia:** Antes de asignar una etiqueta, siempre verificar si ya existe (`ClienteTag.query.filter_by(cliente_id=x, tag_id=y).first()`). Nunca crear duplicados.

2. **Cascada al eliminar:** Los modelos `ClienteTag` y `EmpresaTag` usan `ondelete="CASCADE"`, así que eliminar un cliente o empresa borra sus asignaciones automáticamente.

3. **Tags dinámicas y el scheduler:** El recálculo nocturno no debe eliminar etiquetas asignadas con `origen="manual"`. Solo gestionar las de `origen="sistema"`.

4. **Auditoría:** Toda asignación y desasignación debe registrarse en `logs` con `accion="webhook"` u `accion="sistema"` y `entidad="tag"`.

5. **WooCommerce metadatos clave:**
   - `_billing_first_name`, `_billing_last_name`, `_billing_email` → identificar cliente
   - `_billing_postcode` → etiqueta `local_madrid`
   - `_is_gift` o meta personalizado → etiqueta `compro_para_regalo`
   - `line_items[].name` → mapear a `TipoExperiencia.nombre`
