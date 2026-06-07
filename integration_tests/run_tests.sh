#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=========================================="
echo "  Tests de integración MH  (l10n_sv_dte)"
echo "=========================================="
echo ""
echo "Ambiente: $(grep -A2 'mh:' "$ROOT/config.yaml" 2>/dev/null | grep ambiente | head -1 || echo '?')"
echo ""

# Verificar que existe config.yaml
if [ ! -f "$ROOT/config.yaml" ]; then
    echo "ERROR: No existe config.yaml"
    echo "  Copia config.yaml.example → config.yaml y rellena credenciales"
    exit 1
fi

# Verificar que existe el certificado
CERT_PATH=$(grep 'path:' "$ROOT/config.yaml" | head -1 | awk '{print $2}')
if [ ! -f "$ROOT/$CERT_PATH" ] && [ ! -f "$CERT_PATH" ]; then
    echo "ERROR: Certificado no encontrado: $CERT_PATH"
    echo "  Verifica certificate.path en config.yaml"
    exit 1
fi

# Verificar/instalar dependencias
if ! python3 -c "import requests, cryptography, yaml" 2>/dev/null; then
    echo "Instalando dependencias..."
    pip install -r "$ROOT/requirements.txt"
fi

echo ""
echo "Ejecutando tests..."
echo ""

cd "$ROOT"
python3 -m pytest "$@" -v
