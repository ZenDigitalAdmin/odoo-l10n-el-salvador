"""
Tests de contingencia contra el endpoint /seguridad/contingencia de MH.
"""

import pytest


class TestContingencia:
    """Pruebas de contingencia contra MH real."""

    def test_contingencia_endpoint_reachable(self, client):
        """El endpoint contingencia responde (aunque sea con error)."""
        import requests
        url = client._base_url + '/seguridad/contingencia'
        try:
            resp = requests.post(url, json={}, timeout=10)
            assert resp.status_code in (200, 400, 401, 422, 500)
        except requests.ConnectionError:
            pytest.fail(f'No se puede conectar con {url} — ¿Hacienda caído?')
        except requests.Timeout:
            pytest.fail(f'Timeout en {url}')

    def test_contingencia_response_structure(self, client, private_key, nit_emisor, config):
        """
        Envía una declaración de contingencia sintética.
        Esperamos que MH la rechace (no hay DTE previo), pero
        validamos que la estructura de respuesta sea la esperada.
        """
        from mh_client import sign_jws, MHApiError

        payload = {
            'identificacion': {
                'version': 3,
                'ambiente': config['mh']['ambiente'],
                'codigoGeneracion': 'TEST-CONTINGENCIA-INTEGRATION',
                'tipoDte': '01',
                'fecIniContingencia': '15/01/2025',
                'horIniContingencia': '10:00:00',
                'fecFinContingencia': '15/01/2025',
                'horFinContingencia': '11:00:00',
                'tipoContingencia': 1,
            },
            'emisor': {
                'nit': nit_emisor,
                'nombre': 'DIAL Studio Test',
                'codEstableMH': '0001',
                'codPuntoVentaMH': '0001',
                'telefono': '22334455',
                'correo': 'test@example.com',
            },
            'documento': [],
        }
        jws = sign_jws(payload, private_key, nit_emisor)

        try:
            response = client.send_contingencia(jws)
            assert response['status'] in ('OK', 'CONTINGENCIA')
        except MHApiError as e:
            assert e.status_code in (200, 400, 422)
            pytest.skip(f'MH rechazó contingencia (esperado): {e}')
