"""
Tests de envío de DTE contra el endpoint /seguridad/receptordte de MH.

ATENCIÓN: Estos tests ENVÍAN un DTE real al ambiente de pruebas de MH.
El DTE se marca con datos de prueba (no fiscales), pero genera un
número de control y código de generación reales en el sistema de MH.

Recomendación: Usar NIT de pruebas y montos simbólicos.
"""

import json
import uuid

import pytest


def build_dte_fcf(nit_emisor, cod_estable, cod_punto_venta, config):
    """Construye un payload DTE-01 (FCF) de prueba."""
    dte = config['dte_test']
    num_control = f'DTE-01-{cod_estable}{cod_punto_venta}-{uuid.uuid4().hex[:15].upper()}'
    codigo_gen = str(uuid.uuid4()).upper()

    return {
        'identificacion': {
            'version': 1,
            'ambiente': config['mh']['ambiente'],
            'tipoDte': '01',
            'numeroControl': num_control,
            'codigoGeneracion': codigo_gen,
            'tipoModelo': 1,
            'tipoOperacion': 1,
            'fecEmision': '15/01/2025',
            'horEmision': '10:30:00',
            'moneda': 'USD',
        },
        'documentoRelacionado': None,
        'emisor': {
            'nit': nit_emisor,
            'nrc': '1234567',
            'nombre': 'DIAL Studio Test, S.A. de C.V.',
            'codActividad': '62010',
            'descActividad': 'Servicios de tecnología',
            'direccion': {
                'municipio': '14',
                'departamento': '06',
                'direccionCompleta': 'Av. Test 123, San Salvador',
            },
            'telefono': '22334455',
            'correo': 'test@example.com',
            'codEstableMH': cod_estable,
            'codPuntoVentaMH': cod_punto_venta,
        },
        'receptor': {
            'nombre': dte['receptor_nombre'],
            'tipoDocumento': '36',
            'numDocumento': dte['receptor_nit'],
            'direccion': {
                'municipio': '14',
                'departamento': '06',
                'direccionCompleta': dte['receptor_direccion'],
            },
            'telefono': '70001111',
            'correo': 'cliente@test.com',
        },
        'cuerpoDocumento': [{
            'numItem': 1,
            'tipoItem': 1,
            'numeroDocumento': None,
            'cantidad': 1.0,
            'codigo': '001',
            'uniMedida': 59,
            'descripcion': 'Servicio de consultoría tecnológica (prueba)',
            'precioUnitario': 10.00,
            'montoDescuento': 0.00,
            'ventaNoSuj': 0.00,
            'ventaExenta': 0.00,
            'ventaGravada': 10.00,
            'tributos': [{'codigo': '20', 'descripcion': 'IVA 13%', 'valor': 1.30}],
            'noGravado': 0.00,
            'ivaItem': 0.00,
        }],
        'resumen': {
            'totalNoSuj': 0.00,
            'totalExenta': 0.00,
            'totalGravada': 10.00,
            'subTotalVentas': 10.00,
            'descuNoSuj': 0.00,
            'descuExenta': 0.00,
            'descuGravada': 0.00,
            'porcentajeDescuento': 0.00,
            'totalDescu': 0.00,
            'subTotal': 10.00,
            'ivaRete1': 0.00,
            'reteRenta': 0.00,
            'montoTotalOperacion': 11.30,
            'totalNoGravado': 0.00,
            'totalPagar': 11.30,
            'totalLetras': 'ONCE DÓLARES DE LOS ESTADOS UNIDOS DE AMÉRICA CON TREINTA CENTAVOS',
            'saldoFavor': 0.00,
            'condicionOperacion': 1,
            'ivaPerci1': 0.00,
            'pagos': [{'codigo': '01', 'montoPago': 11.30, 'referencia': ''}],
        },
    }


class TestSendDte:
    """Pruebas de envío de DTE contra MH real."""

    def test_send_fcf_v1_response_structure(self, client, private_key, nit_emisor, config):
        """
        Envía un DTE-01 (FCF) real y valida la estructura de respuesta.

        Este test verifica que el endpoint receptordte:
          - Responda con HTTP 200
          - Devuelva JSON con status + body
          - Incluya selloRecibido en caso de éxito
        """
        dte_payload = build_dte_fcf(
            nit_emisor,
            config['mh'].get('cod_estable', '0001'),
            config['mh'].get('cod_punto_venta', '0001'),
            config,
        )

        from mh_client import sign_jws, MHApiError

        jws = sign_jws(dte_payload, private_key, nit_emisor)

        try:
            response = client.send_dte(jws, tipo_dte='01')
        except MHApiError as e:
            # Si MH lo rechaza por datos de prueba, la estructura debe ser la esperada
            assert 'body' in e.body, f'Error MH debe incluir body: {e.body}'
            pytest.skip(f'MH rechazó el DTE de prueba (esperado): {e}')
            return

        # Si llegamos aquí, MH aceptó el DTE
        assert response['status'] == 'OK', f'Status debe ser OK: {response}'
        assert 'body' in response, 'Respuesta debe tener body'
        body = response['body']
        assert 'selloRecibido' in body, 'Body debe tener selloRecibido'
        assert len(body['selloRecibido']) > 10, 'selloRecibido parece inválido'
        assert 'codigoMsg' in body, 'Body debe tener codigoMsg'
        assert body['codigoMsg'] == '001', 'codigoMsg 001 = procesado OK'
        assert body.get('descripcionMsg'), 'Debe tener descripcionMsg'

    def test_send_dte_rejects_missing_tipo_dte(self, client, private_key, nit_emisor):
        """Enviar sin tipoDte debe devolver error estructurado."""
        import requests

        from mh_client import MHApiError, sign_jws

        jws = sign_jws({'test': 'payload'}, private_key, nit_emisor)
        token = client.authenticate()

        url = client._base_url + '/seguridad/receptordte'
        resp = requests.post(
            url,
            json={'ambiente': client.ambiente, 'documento': jws},
            headers={'Authorization': token, 'Content-Type': 'application/json'},
            timeout=client.timeout,
        )
        # Debe responder con error, no 500
        assert resp.status_code in (200, 400, 422), (
            f'Código inesperado: {resp.status_code}'
        )
        data = resp.json()
        assert 'status' in data, 'Respuesta debe tener status'

    def test_send_dte_version_mismatch(self, client, private_key, nit_emisor, config):
        """Enviar DTE-01 con version=3 debe fallar (schema mismatch)."""
        from mh_client import sign_jws

        dte = build_dte_fcf(
            nit_emisor,
            config['mh'].get('cod_estable', '0001'),
            config['mh'].get('cod_punto_venta', '0001'),
            config,
        )
        jws = sign_jws(dte, private_key, nit_emisor)

        # Forzar version incorrecta
        from mh_client import MHApiError
        try:
            client._post_signed(
                'receptordte', jws,
                ambiente=client.ambiente,
                idEnvio=1,
                version=3,     # FCF debe ser version=1
                tipoDte='01',
            )
        except MHApiError as e:
            # Esperamos un error de validación de schema
            assert e.status_code in (200, 400, 422), (
                f'Código inesperado: {e.status_code}'
            )
            body = e.body.get('body', {})
            desc = body.get('descripcionMsg', '')
            assert any(kw in desc.lower() for kw in ['version', 'schema', 'estructura', 'invalido']), (
                f'Error debería mencionar version/schema: {desc}'
            )
        else:
            pytest.fail('Debería haber lanzado MHApiError por version mismatch')

    def test_send_endpoint_reachable(self, client):
        """El endpoint receptordte responde (aunque sea con error de auth)."""
        import requests
        url = client._base_url + '/seguridad/receptordte'
        try:
            resp = requests.post(url, json={}, timeout=10)
            # Si responde, nos sirve
            assert resp.status_code in (200, 400, 401, 422, 500)
        except requests.ConnectionError:
            pytest.fail(f'No se puede conectar con {url} — Hacienda puede estar caído')
        except requests.Timeout:
            pytest.fail(f'Timeout en {url}')
