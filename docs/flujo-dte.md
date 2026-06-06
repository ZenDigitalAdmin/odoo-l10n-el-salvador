# Flujo DTE — l10n_sv_dte

Este documento describe la **máquina de estados completa** del DTE
(generación → firma → envío → invalidación) y los componentes automáticos
del módulo.

## Estados del DTE

Definidos en `account.move.l10n_sv_dte_state`. El cambio de estado
siempre se hace a través del helper `_write_dte_state`, que también
actualiza `l10n_sv_dte_state_changed_at`.

| Estado | Significado | Cómo llegar | Cómo salir |
|--------|-------------|-------------|------------|
| `draft` | Borrador (no se ha generado JSON) | acción inicial | `action_generate_dte_json` |
| `json_generated` | JSON del DTE armado, sin firmar | `action_generate_dte_json` | `action_sign_dte` |
| `signed` | JWS RS512 generado | `action_sign_dte` | `action_send_dte` o `action_reset_to_draft` |
| `sent` | Enviado al MH, esperando respuesta | `action_send_dte` (transitorio) | éxito → `processed`, fallo → `rejected` |
| `processed` | MH devolvió sello de recepción | `action_send_dte` con respuesta `OK` | `action_invalidate_dte` |
| `rejected` | MH rechazó el DTE o falló la conexión | `action_send_dte` con respuesta != OK | `action_resend_dte` |
| `contingencia` | Marcado para reenvío automático (cron) | `action_send_dte` con `l10n_sv_dte_contingencia = True` | cron o `action_resend_dte` |
| `invalidating` | Solicitud de invalidación enviada | `action_invalidate_dte` (entrada) | éxito → `invalidated`, fallo → `rejected` |
| `invalidated` | MH confirmó la invalidación | `action_invalidate_dte` con respuesta `OK` | (terminal) |

## Acciones de usuario

| Botón en factura | Método | Estados permitidos |
|------------------|--------|--------------------|
| `1. Generar JSON DTE` | `action_generate_dte_json` | `draft` |
| `2. Firmar JWS` | `action_sign_dte` | `json_generated` |
| `3. Enviar al MH` | `action_send_dte` | `signed` |
| `Reenviar DTE` | `action_resend_dte` | `rejected`, `contingencia` |
| `Invalidar DTE` | `action_invalidate_dte` | `processed` |
| `Reiniciar a Borrador` | `action_reset_to_draft` | `json_generated`, `signed`, `sent`, `rejected`, `contingencia` |

## Límites y protecciones

- **Máximo de intentos de envío**: 5 (campo `l10n_sv_dte_send_attempts`).
  `action_resend_dte` rechaza el reenvío si se llegó al tope. Configurar el
  certificado, ambiente o el código del DTE antes de reintentar.
- **No se puede invalidar un DTE sin sello de recepción** (`action_invalidate_dte`).
- **No se puede reiniciar un DTE `processed` o `invalidated`**: para corregirlo,
  invalidarlo primero y luego emitir uno nuevo.
- **Envío de un DTE `processed` o `invalidated`**: `action_send_dte` lanza
  `UserError`.

## Componentes automáticos

### Cron: `DTE SV: Reenviar contingencia`

Definido en `data/ir_cron_data.xml` (`ir_cron_l10n_sv_dte_contingencia`).

- **Modelo**: `l10n_sv.api`
- **Método**: `cron_process_contingencia`
- **Intervalo**: cada 5 minutos
- **Búsqueda**: `account.move` con `l10n_sv_dte_state = 'contingencia'`
  y menos de 5 intentos previos
- **Acción**: limpia el flag de contingencia, llama `action_send_dte(is_automatic=True)`
  - si responde `OK` y devuelve sello → estado `processed`
  - si falla, registra el error en `l10n_sv.dte.log` con `is_automatic=True`
    y restaura el estado a `contingencia` para el próximo intento
  - el log se puede ver desde el menú *Facturación SV → Bitácora DTE* o desde
    la pestaña *Facturación Electrónica (DTE)* de la factura con el botón
    *Ver bitácora*

Para pausar el cron, desactivar el registro en
*Ajustes → Técnico → Automatización → Acciones planificadas*.

### Bitácora DTE

Modelo `l10n_sv.dte.log` (visible en el menú *Facturación SV → Bitácora DTE*).

Cada intento de envío o invalidación genera un registro con:

- `operation`: `send` / `invalidate` / `contingencia`
- `success`: True/False
- `status_code`, `response_code`, `sello_recepcion`: extraídos de la respuesta
- `response_body`: el JSON completo del MH
- `error_message`: descripción del error si falló
- `is_automatic`: True si fue disparado por el cron

### Wizard de envío masivo

Modelo `l10n_sv.dte.send.wizard` (menú *Facturación SV → Envío Masivo DTE*).

- Selecciona un lote de facturas (también se puede lanzar desde una lista de
  facturas con la acción contextual → *Acciones → Envío Masivo DTE*).
- Marca `include_draft` para incluir facturas en `draft` (las genera, firma y
  envía en una sola pasada).
- Al ejecutar, abre una pantalla de resultados con conteo de
  `Total / Procesados / Fallidos` y una tabla con el detalle por factura.

## Diagrama textual de transiciones

```
                                       ┌──────────────────────┐
                                       │                      │
                              ┌───────►│  processed (con sello)│
                              │        │                      │
       draft                  │        └──────────┬───────────┘
         │                    │                   │
         │ action_generate     │ action_send_dte   │ action_invalidate
         ▼                    │  (OK + sello)     │ (entrada)
   json_generated             │                   ▼
         │                    │           invalidating
         │ action_sign_dte    │                   │
         ▼                    │            action_invalidate
       signed ──────────────► sent               │ (OK)
         │                    │                   ▼
         │ action_send_dte    │             invalidated (terminal)
         │ (contingencia=True)│
         ▼                    │
     contingencia ────────────► (cron reintenta cada 5 min)
         │                    │
         │ cron o resend      │ action_send_dte (no OK)
         ▼                    ▼
       signed / sent       rejected
         ▲                    │
         │ action_resend_dte │
         └────────────────────┘
```

## Campos clave en `account.move`

- `l10n_sv_dte_state` (Selection) — estado actual
- `l10n_sv_dte_state_changed_at` (Datetime) — última vez que cambió el estado
- `l10n_sv_dte_send_attempts` (Integer) — total de intentos de envío
- `l10n_sv_dte_last_attempt_at` (Datetime) — fecha del último intento
- `l10n_sv_dte_last_error` (Text) — mensaje del último error
- `l10n_sv_dte_invalidated_at` (Datetime) — cuándo fue invalidado
- `l10n_sv_dte_log_ids` (One2many → `l10n_sv.dte.log`) — bitácora completa
- `l10n_sv_dte_log_count` (Integer, computed) — atajo para smart button

## Recetas de uso

### "El MH rechazó el DTE por error de NIT del cliente"

1. Corregir el NIT del cliente en la ficha de contacto.
2. Abrir la factura → botón **Reenviar DTE** (estado `rejected`).
3. Si el MH lo acepta, pasa a `processed`. Si sigue rechazando, revisar
   la pestaña *Facturación Electrónica (DTE)* → *Detalle técnico* o la
   *Bitácora DTE*.

### "El servicio del MH estuvo caído toda la tarde"

1. Marcar todas las facturas pendientes con `l10n_sv_dte_contingencia = True`.
2. Al volver el servicio, el cron las reenvía automáticamente cada 5 minutos.
3. También se puede usar el menú *Envío Masivo DTE* para procesarlas de una vez.

### "Necesito corregir una factura ya procesada"

1. Botón **Invalidar DTE** en la factura (estado `processed`).
2. Crear una nueva factura con los datos correctos, firmarla y enviarla.

## Código QR de verificación

Cuando un DTE pasa a `processed`, el módulo genera automáticamente un
código QR que se incrusta en el reporte PDF y se almacena en dos campos
de `account.move`:

- `l10n_sv_dte_qr_url` (Char) — URL codificada en el QR.
  Apunta al portal del MH:
  `https://portaldgii.mh.gob.sv/consulta/QR?nit=…&codigoGeneracion=…&fechaEmision=…&montoTotalOperacion=…&montoIVA=…&numeroControl=…&selloRecibido=…`
- `l10n_sv_dte_qr_image` (Text) — SVG del QR, incrustado en el reporte.

**Librería requerida**: `qrcode` (incluida en `external_dependencies` del
manifest). Se usa el factory `qrcode.image.svg.SvgPathImage` que **no
requiere** Pillow ni otras dependencias de imagen. Si la librería no está
instalada, el módulo registra un warning y deja los campos del QR vacíos;
el DTE no se ve afectado.

Para regenerar manualmente (por ejemplo, si la URL del portal del MH
cambia), usar el botón **Regenerar QR** en la factura (visible para
`processed`).

## Reporte de impresión

Reporte QWeb `l10n_sv_dte.report_l10n_sv_dte_invoice` (menú *Imprimir →
DTE SV (PDF)* o desde la lista de facturas con el botón *Imprimir*).

- **Tipo**: `qweb-pdf` (usa `wkhtmltopdf`).
- **Secciones**:
  1. Cabecera con datos del emisor + tipo de DTE + QR.
  2. Identificadores MH (número de control, código de generación, sello, fecha, hora, moneda).
  3. Datos del cliente (NIT/NRC, dirección, giro).
  4. Cuerpo del documento (tabla con #, cantidad, código, descripción, precio, descuento, gravada, IVA).
  5. Tributos aplicados (tabla `codigo / descripcion / valor`).
  6. Forma de pago y total a pagar.
  7. Observaciones (si existen).
  8. Pie con sello de recepción y URL de verificación.

Si `wkhtmltopdf` no está instalado en el servidor, el reporte
seguirá disponible como **HTML** desde el menú contextual *Imprimir*.
