# odoo-l10n-el-salvador

Módulo de localización para Odoo 19: **Facturación Electrónica (DTE)**
conforme a los requerimientos del Ministerio de Hacienda de El Salvador.

## Características

- **Tipos de DTE soportados**: FCF-01, CCF-03, NC-05, ND-06, FSE-14
  (NR-04, FEX-11, retención-07, donación-15 extensibles).
- **Catálogos MH precargados** (CAT-009, 015, 016, 017, 019, 022) +
  municipios y actividad económica (CIIU Rev 4, 989 códigos).
- **Firma JWS RS512** con certificado del MH (XML embebido, sin
  dependencias de Java).
- **Envío automático** al MH con cache de token JWT (TTL 55 min) y
  selección de ambiente (test/producción).
- **Contingencia** y cron de reenvío automático cada 5 minutos.
- **Invalidación** de DTE ya procesados.
- **Bitácora completa** de cada intento (envío, invalidación, contingencia).
- **Wizard de envío masivo** para procesar lotes de facturas.
- **QR de verificación** generado con `qrcode` (formato SVG, sin
  Pillow).
- **Reporte QWeb de impresión** del DTE con todos los identificadores
  y el QR.
- **Suite de tests** (`tests/`) con 50+ tests cubriendo signer, JSON
  DTE, API, state machine y flujo end-to-end.

## Documentación

Toda la documentación funcional está en `docs/`:

| Documento | Tema |
|-----------|------|
| [`docs/instalacion.md`](docs/instalacion.md) | Instalación, requisitos, configuración inicial |
| [`docs/flujo-dte.md`](docs/flujo-dte.md) | Máquina de estados del DTE, cron, wizard, recetas |
| [`docs/api-mh.md`](docs/api-mh.md) | Endpoints REST del MH, auth, manejo de errores |
| [`docs/firma-digital.md`](docs/firma-digital.md) | JWS RS512, certificado XML, troubleshooting |
| [`docs/catalogos.md`](docs/catalogos.md) | Catálogos MH (CAT-009/015/016/017/019/022) y municipios |

## AGENTS.md (para OpenCode)

[`AGENTS.md`](AGENTS.md) contiene las convenciones y trampas conocidas
del módulo. Si trabajas con un agente, léeselo primero.

## Arquitectura rápida

```
l10n_sv_dte/
├── __manifest__.py          # versión 19.0.1.7.0
├── models/
│   ├── account_move.py      # generador JSON DTE + state machine
│   ├── account_tax.py       # M2O a l10n_sv.tributo
│   ├── res_company.py       # config MH de la compañía
│   ├── res_partner.py       # NIT, NRC, municipio del cliente
│   ├── l10n_sv_signer.py    # JWS RS512 + parser de cert MH
│   ├── l10n_sv_api.py       # cliente HTTP del MH (token cache)
│   ├── l10n_sv_dte_log.py   # bitácora de intentos
│   ├── l10n_sv_dte_send_wizard.py  # wizard de envío masivo
│   └── l10n_sv_*.py         # modelos de catálogos
├── data/                    # CSVs de catálogos + account.tax + ir.cron
├── views/                   # UI + reporte QWeb
├── security/ir.model.access.csv
├── docs/                    # documentación funcional
├── tests/                   # tests Odoo (TransactionCase)
└── graphify-out/            # [gitignored] output de la skill graphify
```

## Seguridad

- **No hay credenciales en el código**. Las credenciales de la API del
  MH viven en `ir.config_parameter`.
- **No hay certificados en el repositorio**. El `.crt` se sube vía UI
  como `ir.attachment`.
- Licencia **LGPL-3**.

## Estado del desarrollo

| Fase | Estado | Descripción |
|------|--------|-------------|
| 1 | ✅ | Bug fixes, fields, credential migration, UUID/numeroControl auto-gen |
| 2 | ✅ | Catálogos + 989 CIIU codes |
| 3 | ✅ | JWS signer, MH API client, contingency, invalidation |
| 4 | ✅ | JSON DTE completo (`resumen`, `documentoRelacionado`, `extension`, `pagos`) |
| 5 | ✅ | State machine polish + log + wizard + cron contingencia |
| 6 | ✅ | QR generation + QWeb DTE print report |
| 7 | ✅ | Test suite + per-topic docs |

## Licencia

LGPL-3. Ver [`LICENSE`](LICENSE).
