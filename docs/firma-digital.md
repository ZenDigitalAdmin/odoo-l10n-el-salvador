# Firma Digital para DTE - Ministerio de Hacienda de El Salvador

Este documento describe el flujo de firma digital de los DTE (Documentos Tributarios
Electrónicos) para transmisión al Ministerio de Hacienda (MH) de El Salvador.

## Resumen del flujo

```
1. Construir el JSON del DTE (sin firmar)
2. Serializar a JSON canónico (sin espacios)
3. Codificar header y payload en base64url
4. Firmar con RS512 (RSA + SHA-512 + PKCS#1 v1.5)
5. Construir JWS compacto: header.payload.signature
6. POST a /seguridad/receptordte con Authorization: <token>
```

## Algoritmo

- **Algoritmo JWS**: `RS512` (RSASSA-PKCS1-v1_5 con SHA-512)
- **Header**:
  ```json
  {"alg": "RS512", "kid": "<NIT_EMISOR>"}
  ```
- **Payload**: el JSON completo del DTE, serializado canónicamente.
- **Firma**: el input `base64url(header).base64url(payload)` se firma con la
  clave privada RSA extraída del certificado.

## Certificado Digital

El Ministerio de Hacienda emite un **certificado de firma** como un archivo
XML con la clave privada embebida. Estructura esperada:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<certificate>
    <privateKey>
        <encodied>BASE64_DEL_PEM_DE_LA_CLAVE_PRIVADA</encodied>
    </privateKey>
    <publicKey>...</publicKey>
    ...
</certificate>
```

### Cómo obtener el certificado

1. Ingresar a [https://www.factura.gob.sv/](https://www.factura.gob.sv/) con
   sus credenciales del MH.
2. Solicitar el certificado de firma (si no lo ha hecho ya).
3. Descargar el archivo `.crt` (XML con clave privada).
4. **Importante**: este archivo es equivalente a una firma manuscrita
   legalmente vinculante. Protéjalo como cualquier documento confidencial.

### Cómo cargar el certificado en Odoo

1. Ir a **Configuración → Compañías → [Su empresa]**
2. Abrir la pestaña **Facturación Electrónica SV**
3. En el grupo **Certificado Digital**, suba el archivo `.crt` en el campo
   `Certificado Digital MH`.
4. El archivo se almacena en `ir.attachment` con permisos controlados.

> **Nunca** almacene el certificado en un repositorio de código abierto
> ni en un directorio público. La clave privada puede firmar facturas a
> su nombre.

## Credenciales de la API

Las credenciales del API del MH se configuran en **Parámetros del sistema**
(NO en la ficha de la compañía, para mayor seguridad y portabilidad):

1. Ir a **Configuración → Técnico → Parámetros del sistema**
2. Crear dos parámetros por cada compañía:

| Clave | Valor |
|-------|-------|
| `l10n_sv.api_user_<company_id>` | Usuario asignado por el MH |
| `l10n_sv.api_password_<company_id>` | Contraseña del API del MH |

Donde `<company_id>` es el ID de la compañía (típicamente `1` para la
compañía principal).

## Endpoints de la API del MH

| Ambiente | URL |
|----------|-----|
| Test (00) | `https://apitest.dtes.mh.gob.sv` |
| Producción (01) | `https://api.dtes.mh.gob.sv` |

| Acción | Endpoint | Método |
|--------|----------|--------|
| Autenticación | `/seguridad/auth` | POST |
| Recepción de DTE | `/seguridad/receptordte` | POST |
| Invalidación | `/seguridad/anulardte` | POST |
| Contingencia | `/seguridad/contingencia` | POST |

## Dependencias externas

- `requests` - cliente HTTP
- `cryptography` - firma RSA y manipulación de PEM

Para instalar:

```bash
pip install requests cryptography
```

## Ejemplo de JWS generado

```
eyJhbGciOiJSUzUxMiIsImtpZCI6IjA2MTQwMzcwMTI0In0.
eyJpZGVudGlmaWNhY2lvbiI6eyJ2ZXJzaW9uIjoxLCJhbWJpZW50ZSI6IjAw...
.MEUCIQDx7qKqL5cAxK1G3yZJ-vDH7V8B9jZP3OWHnAf8J2F4Q...
```

Los tres segmentos están separados por `.` y cada uno es base64url sin
padding (`=`).

## Pruebas

### 1. Probar conexión

Desde la ficha de la compañía, haga clic en **Probar Conexión MH**. Esto
intenta autenticarse con las credenciales configuradas y muestra un
mensaje de éxito o error.

### 2. Firmar y enviar un DTE de prueba

1. Cree una factura de cliente (`out_invoice`) en estado Borrador.
2. En la pestaña **Facturación Electrónica (DTE)**:
   - Seleccione tipo **01** (FCF) o **03** (CCF)
   - Condición de operación (Contado/Crédito)
3. Confirme la factura.
4. Use los botones del header en orden:
   1. **1. Generar JSON DTE**
   2. **2. Firmar JWS**
   3. **3. Enviar al MH**
5. Verifique el `selloRecepcion` en la pestaña DTE.

## Troubleshooting

| Problema | Solución |
|----------|----------|
| "No se pudo cargar la clave privada PEM" | El XML no tiene la clave privada o el formato Base64 está corrupto. Re-descargue el certificado del portal MH. |
| "Faltan credenciales API" | Configure los parámetros `l10n_sv.api_user_<id>` y `l10n_sv.api_password_<id>`. |
| "401 Unauthorized" | El token expiró (>1h). El módulo lo refresca automáticamente, pero verifique las credenciales. |
| "RECHAZADO por MH" | Revise la pestaña "Detalle técnico" (visible para grupo Admin) para ver la respuesta completa del MH. |

## Seguridad

- **No** commitee el certificado ni las credenciales al repositorio.
- Use `.gitignore` para excluir archivos `.crt` y `.key`.
- Configure permisos en `ir.attachment` y `ir.config_parameter` para
  restringir acceso a usuarios no autorizados.
- En producción, use HTTPS con certificados válidos para Odoo.
