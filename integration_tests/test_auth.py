"""
Tests de autenticación contra el endpoint /seguridad/auth de MH.

Miden:
  - Que el endpoint responda (no esté caído)
  - Que el formato de respuesta sea el esperado
  - Que el token se reciba y tenga formato válido
  - Que credenciales inválidas devuelvan error estructurado
"""

import pytest


class TestAuth:
    """Pruebas de autenticación contra MH real."""

    def test_auth_returns_token(self, client):
        """El endpoint auth responde con un token JWT."""
        token = client.authenticate(force_refresh=True)
        assert token, 'No se obtuvo token'
        assert isinstance(token, str), 'Token debe ser string'
        assert len(token) > 20, 'Token muy corto'
        # Los tokens de MH suelen ser JWT (3 segmentos)
        # pero no todos lo son; validar longitud mínima

    def test_auth_token_cached(self, client):
        """La cache de token funciona (segunda llamada no hace HTTP)."""
        token1 = client.authenticate(force_refresh=True)
        assert client._is_token_valid(), 'Token debería ser válido tras autenticar'
        token2 = client.authenticate(force_refresh=False)
        assert token1 == token2, 'Debe retornar el mismo token cacheado'

    def test_auth_response_structure(self, client):
        """Valida que la respuesta JSON tenga la estructura que espera Odoo."""
        from mh_client import MHClient
        import requests

        mh = client
        url = mh._base_url + '/seguridad/auth'
        resp = requests.post(
            url,
            data={'user': mh.api_user, 'pwd': mh.api_password},
            timeout=mh.timeout,
        )
        assert resp.status_code == 200
        data = resp.json()

        # La estructura esperada por el módulo Odoo
        assert 'status' in data, 'Respuesta debe tener campo status'
        assert data['status'] == 'OK', f'Status debe ser OK, got {data["status"]}'
        assert 'body' in data, 'Respuesta debe tener campo body'
        assert isinstance(data['body'], dict), 'body debe ser dict'
        assert 'token' in data['body'], 'body debe tener token'

    def test_auth_invalid_credentials(self, config):
        """Credenciales inválidas devuelven error estructurado (no 500)."""
        from mh_client import MHClient
        import requests

        client = MHClient(
            ambiente=config['mh']['ambiente'],
            api_user='USUARIO_INVALIDO',
            api_password='PASS_INVALIDO',
        )
        url = client._base_url + '/seguridad/auth'
        resp = requests.post(
            url,
            data={'user': 'USUARIO_INVALIDO', 'pwd': 'PASS_INVALIDO'},
            timeout=30,
        )
        # Debe responder con error, no con timeout/500
        assert resp.status_code in (200, 401, 403, 422), (
            f'Código inesperado: {resp.status_code}'
        )
        data = resp.json()
        # Si responde 200, debe tener status ERROR
        if resp.status_code == 200:
            assert data.get('status') == 'ERROR' or 'error' in str(data).lower(), (
                f'Credenciales inválidas deberían reportar error: {data}'
            )

    def test_auth_endpoint_reachable(self, client):
        """Endpoint de autenticación está accesible (no timeout, no DNS error)."""
        import requests
        url = client._base_url + '/seguridad/auth'
        try:
            resp = requests.post(url, data={'user': '', 'pwd': ''}, timeout=10)
            # Nos importa que responda, no el código
            assert resp.status_code in (200, 401, 422, 400)
        except requests.ConnectionError:
            pytest.fail(f'No se puede conectar con {url} — ¿Hacienda está caído?')
        except requests.Timeout:
            pytest.fail(f'Timeout conectando con {url}')
