# Catálogos MH (referencia rápida)

El módulo carga los siguientes catálogos oficiales del Ministerio de
Hacienda de El Salvador. Cada catálogo tiene un modelo
`l10n_sv.<catálogo>`, una vista (árbol + formulario) y un menú en
*Facturación SV → Catálogos MH*.

| Catálogo | Modelo | CSV | Descripción |
|----------|--------|-----|-------------|
| CAT-009  | `l10n_sv.tipo_establecimiento` | `l10n_sv.cat009.csv` | Tipo de establecimiento (Matriz, Sucursal, Bodega, etc.) |
| CAT-015  | `l10n_sv.tributo`            | `l10n_sv.cat015.csv` | Tributos que aplica el emisor (IVA, FOVIAL, retenciones, etc.) |
| CAT-016  | `l10n_sv.condicion_operacion` | `l10n_sv.cat016.csv` | Condición de la operación (Contado, Crédito) |
| CAT-017  | `l10n_sv.forma_pago`         | `l10n_sv.cat017.csv` | Forma de pago (Efectivo, Tarjeta, Transferencia, etc.) |
| CAT-019  | `l10n_sv.actividad_economica` | `l10n_sv.actividad_economica.csv` | 989 códigos CIIU Rev 4 (BCR) |
| CAT-022  | `l10n_sv.tipo_documento`     | `l10n_sv.cat022.csv` | Tipo de documento de identificación del cliente |

Adicionalmente:

- **Municipios**: `l10n_sv.municipio` + `l10n_sv.municipio.csv` (~262 municipios)
- **Departamentos**: `res.country.state` (incluido en `base`, cargado vía
  `data/res.country.state.csv`)

## CAT-009 — Tipo de Establecimiento

| Código | Descripción |
|--------|-------------|
| 01 | Matriz |
| 02 | Sucursal |
| 04 | Bodega |
| 07 | Expendio |
| 99 | Otro |

Se usa en `res.company.l10n_sv_tipo_establecimiento_id` y aparece en el
`emisor.tipoEstablecimiento` del JSON DTE.

## CAT-015 — Tributos

| Código | Descripción |
|--------|-------------|
| 20 | IVA 13% |
| C3 | IVA Percibido |
| C4 | Anticipo a cuenta del IVA 2% |
| C5 | Retención IVA 1% Bienes |
| C6 | Retención IVA 1% Servicios |
| C7 | Retención IVA Bienes 13% a Grandes Contribuyentes |
| C8 | Retención IVA Servicios 13% a Grandes Contribuyentes |
| 59 | FOVIAL |
| 71 | Turismo |
| D1 | Impuesto Municipal |
| D4 | Retención ISR 1% |
| D5 | Retención ISR 5% |
| 25 | Otros Impuestos |

Se vincula a `account.tax.l10n_sv_tributo_id` para que el módulo sepa a
qué tributo MH equivale cada impuesto. Aparece en:

- `cuerpoDocumento[].tributos[]` por línea
- `resumen.tributos[]` agregado

## CAT-016 — Condición de la Operación

| Código | Descripción |
|--------|-------------|
| 1 | Contado |
| 2 | Crédito |

Se usa en `account.move.l10n_sv_dte_condicion_operacion` y determina
`resumen.condicionOperacion` y la presencia de `pagos[]`.

## CAT-017 — Forma de Pago

| Código | Descripción |
|--------|-------------|
| 01 | Efectivo (Billetes y Monedas) |
| 02 | Tarjeta de Crédito |
| 03 | Tarjeta de Débito |
| 04 | Cheque |
| 05 | Transferencia Bancaria |
| 06 | Dinero Electrónico |
| 07 | Criptomonedas |
| 08 | Otros |
| 09 | Vale |
| 10 | Compensación de Deuda |
| 11 | Pago Móvil |
| 12 | Billetera Electrónica |
| 13 | Tarjeta de Regalo |
| 14 | Monedero Electrónico |
| 99 | Pago en Especie (No Gravado) |

Se usa en `account.move.l10n_sv_dte_forma_pago_id` y aparece en
`resumen.pagos[].codigo`.

## CAT-019 — Actividad Económica

989 códigos CIIU Rev 4 desde el BCR (Banco Central de Reserva de El
Salvador). Estructura: 5 dígitos (sección + división + grupo + clase).

Ejemplos:

| Código | Descripción |
|--------|-------------|
| 01111 | Cultivo de cereales |
| 47110 | Comercio al por menor en tiendas de abarrotes |
| 62010 | Programación informática |
| 69200 | Servicios de contabilidad, auditoría y asesoría fiscal |
| 96000 | Otras actividades de servicios personales |

Se usa en:

- `res.company.l10n_sv_cod_actividad_id` (en `emisor.codActividad`)
- `res.partner.l10n_sv_giro` (en `receptor.codActividad`)

> El campo del modelo es `description`, no `name`, para evitar conflictos
> con el campo `name` estándar de Odoo. El modelo es reutilizable en
> cualquier entidad (compañía, partner, etc.).

## CAT-022 — Tipo de Documento

| Código | Descripción |
|--------|-------------|
| 13 | DUI |
| 36 | NIT |
| 14 | NRC |
| 03 | Pasaporte |
| 02 | Carné de Extranjería |
| 99 | Otro |

Se usa en `res.partner.l10n_sv_tipo_documento_id` y aparece en
`receptor.tipoDocumento` (requerido para FCF cuando el cliente no tiene
NIT).

## Cómo agregar más catálogos

1. Crear el modelo en `models/l10n_sv_<nombre>.py` heredando `models.Model`
   con `_name = 'l10n_sv.<nombre>'` y los campos `code`, `name`, `active`.
2. Importarlo en `models/__init__.py`.
3. Agregar la fila ACL en `security/ir.model.access.csv`.
4. Cargar el CSV en `data/l10n_sv.cat<NNN>.csv` con el formato:

   ```csv
   id,code,name
   mi_prefijo_<code>,<code>,<descripcion>
   ```

5. Registrar el CSV en `__manifest__.py → data` (antes de las vistas).
6. Agregar vistas tree + form + search en `views/l10n_sv_catalog_views.xml`.
7. Agregar menú en `views/l10n_sv_catalog_views.xml` con el parent
   `menu_l10n_sv_catalogos`.

## Actualización de un catálogo

Si el MH publica una versión nueva de un catálogo:

1. Editar el CSV correspondiente en `data/`.
2. NO cambiar los `id` de filas existentes (son PKs externas estables).
3. Agregar las filas nuevas con un `id` que no exista aún (sufijo
   `_v2` o código nuevo).
4. Subir la versión del módulo (`__manifest__.py`).

Al actualizar el módulo en Odoo (`-u l10n_sv_dte`), las filas nuevas se
insertan y las existentes se actualizan si el código cambió (no se
eliminan las anteriores para preservar integridad referencial).
