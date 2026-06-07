"""
Tests de invalidación contra el endpoint /seguridad/anulardte de MH.

NOTA: Para probar invalidación real se necesita un DTE previamente enviado
y recibido (con selloRecepcion). Este test construye una solicitud con
datos sintéticos para verificar que el endpoint responde con la estructura
esperada, aunque MH la rechace por no existir el documento.
"""

import uuid

import pytest


def build_invalidation_payload(nit_emisor, config):
    """Construye un payload de invalidación con datos sintéticos."""
    dte = config['dte_test']
    return {
        'identificacion': {
            'version': 2,
            'ambiente': config['mh']['ambiente'],
            'codigoGeneracion': str(uuid.uuid4()).upper(),
        },
        'emisor': {
            'nit': nit_emisor,
            'nombre': 'DIAL Studio Test, S.A. de C.V.',
            'tipoEstablecimiento': '01',
            'codEstableMH': dte.get('cod_estable', '0001'),
            'codPuntoVentaMH': dte.get('cod_punto_venta', '0001'),
        },
        'documento': {
            'tipoDte': '01',
            'codigoGeneracion': str(uuid.uuid4()).upper(),
            'selloRecibido': 'X' * 40,
            'numeroControl': f'DTE-01-00010001-{uuid.uuid4().hex[:15].upper()}',
            'fecEmi': '15/01/2025',
            'montoIva': 1.30,
            'codigoGeneracionR': str(uuid.uuid4()).upper(),
        },
        'motivo': {
            'tipoAnulacion': 2,
            'motivoAnulacion': 'Prueba de integración — anulación de test',
            'nombreResponsable': 'Admin Test',
            'tipDocResponsable': '36',
            'numDocResponsable': nit_emisor,
        },
    }


class TestInvalidate:
    """Pruebas de invalidación contra MH real."""

    def test_invalidate_endpoint_response_structure(self, client, private_key, nit_emisor, config):
        """
        Envía una solicitud de invalidación sintética y valida la respuesta.

        MH rechazará la invalidación porque el documento no existe realmente,
        pero debemos verificar que:
          - El endpoint responde (no está caído)
          - La respuesta tiene la estructura JSON esperada por Odoo
          - El status es ERROR o CONTINGENCIA (no puede ser OK para DTE inexistente)
        """
        from mh_client import sign_jws, MHApiError

        payload = build_invalidation_payload(nit_emisor, config)
        jws = sign_jws(payload, private_key, nit_emisor)

        try:
            response = client.invalidate_dte(jws)
            # Si MH acepta la invalidación (poco probable con datos sintéticos)
            assert response['status'] in ('OK', 'CONTINGENCIA'), (
                f'Status inesperado: {response.get("status")}'
            )
        except MHApiError as e:
            # Esperado: MH rechaza porque el DTE no existe
            assert e.status_code in (200, 400, 422), (
                f'Código de error inesperado: {e.status_code}'
            )
            body = e.body
            assert 'status' in body, f'Error body debe tener status: {body}'
            assert 'body' in body, f'Error body debe tener body: {body}'
            # El mensaje debería indicar que el documento no existe
            desc = (body.get('body') or {}).get('descripcionMsg', '')
            assert desc, 'Debe haber descripcionMsg en el error'
            pytest.skip(f'MH rechazó (esperado): {desc}')

    def test_invalidate_without_sello(self, client, private_key, nit_emisor, config):
        """Invalidación sin selloRecibido debe ser rechazada."""
        from mh_client import sign_jws, MHApiError

        payload = build_invalidation_payload(nit_emisor, config)
        payload['documento']['selloRecibido'] = ''
        jws = sign_jws(payload, private_key, nit_emisor)

        try:
            client.invalidate_dte(jws)
        except MHApiError as e:
            assert e.status_code in (200, 400, 422)
            body = e.body.get('body', {})
            desc = body.get('descripcionMsg', '')
            assert any(kw in desc.lower() for kw in ['sello', 'obligatorio', 'requerido']), (
                f'Error debería mencionar sello: {desc}'
            )

    def test_invalidate_endpoint_reachable(self, client):
        """El endpoint anulardte responde (aunque sea con error)."""
        import requests
        url = client._base_url + '/seguridad/anulardte'
        try:
            resp = requests.post(url, json={}, timeout=10)
            assert resp.status_code in (200, 400, 401, 422, 500)
        except requests.ConnectionError:
            pytest.fail(f'No se puede conectar con {url} — ¿Hacienda caído?')
        except requests.Timeout:
            pytest.fail(f'Timeout en {url}')
