"""
Tests de firma JWS RS512 usando el certificado MH real.

Se ejecutan SIN llamar a la API de MH — solo validan que
el certificado se parsea correctamente y la firma es válida.
"""

import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa


class TestSigner:
    """Pruebas de firma JWS con certificado real de MH."""

    def test_parse_certificate_returns_rsa_key(self, private_key):
        """El certificado XML se parsea y produce una clave RSA."""
        assert isinstance(private_key, rsa.RSAPrivateKey)
        # Una clave RSA 2048 bits tiene tamaño de clave específico
        assert private_key.key_size == 2048, (
            f'MH requiere RSA 2048 bits, tiene {private_key.key_size}'
        )

    def test_sign_jws_produces_compact_format(self, private_key, nit_emisor):
        """La firma produce JWS de 3 segmentos con cabecera correcta."""
        from mh_client import sign_jws, b64url_decode

        payload = {'test': 'data', 'version': 1}
        jws = sign_jws(payload, private_key, nit_emisor)
        parts = jws.split('.')
        assert len(parts) == 3, f'JWS debe tener 3 segmentos, tiene {len(parts)}'

        header = json.loads(b64url_decode(parts[0]))
        assert header['alg'] == 'RS512'
        assert header['kid'] == nit_emisor

        decoded_payload = json.loads(b64url_decode(parts[1]))
        assert decoded_payload == payload

    def test_signature_verifies_with_public_key(self, private_key, nit_emisor):
        """La firma se verifica correctamente con la clave pública."""
        from mh_client import sign_jws, verify_jws

        payload = {'numeroControl': 'DTE-01-0001-12345', 'monto': 100.50}
        jws = sign_jws(payload, private_key, nit_emisor)
        decoded = verify_jws(jws, private_key.public_key())
        assert decoded == payload

    def test_tampered_jws_fails_verification(self, private_key, nit_emisor):
        """Un JWS manipulado debe fallar verificación."""
        from mh_client import sign_jws, verify_jws

        payload = {'monto': 100}
        jws = sign_jws(payload, private_key, nit_emisor)
        parts = jws.split('.')
        # Manipular el payload
        tampered = f'{parts[0]}.{parts[1]}x.{parts[2]}'
        with pytest.raises(Exception):
            verify_jws(tampered, private_key.public_key())

    def test_sign_full_dte_payload(self, private_key, nit_emisor):
        """Firma un payload de DTE realista (identificacion + emisor + resumen)."""
        from mh_client import sign_jws, verify_jws

        dte_payload = {
            'identificacion': {
                'version': 1,
                'ambiente': '00',
                'tipoDte': '01',
                'numeroControl': 'DTE-01-0001-20250115-123456789012345',
                'codigoGeneracion': 'A1B2C3D4-E5F6-7890-ABCD-EF1234567890',
                'tipoModelo': 1,
                'tipoOperacion': 1,
                'fecEmision': '15/01/2025',
                'horEmision': '10:30:00',
                'moneda': 'USD',
            },
            'emisor': {
                'nit': '06141406100012',
                'nrc': '1234567',
                'nombre': 'DIAL Studio Test, S.A. de C.V.',
                'codActividad': '62010',
                'descActividad': 'Servicios de tecnología',
                'codEstableMH': '0001',
                'codPuntoVentaMH': '0001',
                'correo': 'test@example.com',
                'telefono': '22334455',
            },
            'receptor': {
                'nit': '06140101234567',
                'nrc': '7654321',
                'nombre': 'Cliente Test, S.A. de C.V.',
                'direccion': {'municipio': '01', 'departamento': '06'},
            },
            'cuerpoDocumento': [{
                'numItem': 1,
                'tipoItem': 1,
                'cantidad': 1.0,
                'codigo': '001',
                'descripcion': 'Servicio de consultoría',
                'precioUnitario': 100.0,
                'montoDescuento': 0.0,
                'ventaNoSuj': 0.0,
                'ventaExenta': 0.0,
                'ventaGravada': 100.0,
            }],
            'resumen': {
                'totalNoSuj': 0.0,
                'totalExenta': 0.0,
                'totalGravada': 100.0,
                'subTotalVentas': 100.0,
                'descuNoSuj': 0.0,
                'descuExenta': 0.0,
                'descuGravada': 0.0,
                'porcentajeDescuento': 0.0,
                'totalDescu': 0.0,
                'subTotal': 100.0,
                'ivaPerci1': 0.0,
                'ivaRete1': 0.0,
                'reteRenta': 0.0,
                'montoTotalOperacion': 113.0,
                'totalNoGravado': 0.0,
                'totalPagar': 113.0,
                'totalLetras': 'CIENTO TRECE DÓLARES DE LOS ESTADOS UNIDOS DE AMÉRICA',
                'saldoFavor': 0.0,
                'condicionOperacion': 1,
                'pagos': [{'codigo': '01', 'montoPago': 113.0}],
            },
        }
        jws = sign_jws(dte_payload, private_key, nit_emisor)
        decoded = verify_jws(jws, private_key.public_key())
        assert decoded['identificacion']['tipoDte'] == '01'
        assert decoded['resumen']['totalPagar'] == 113.0

    def test_parse_certificate_rejects_non_xml(self):
        """Bytes no-XML lanzan ValueError."""
        from mh_client import parse_mh_certificate
        with pytest.raises(ValueError, match='XML'):
            parse_mh_certificate(b'esto no es xml')

    def test_parse_certificate_rejects_missing_key(self):
        """XML sin <encodied> lanza ValueError."""
        from mh_client import parse_mh_certificate
        with pytest.raises(ValueError, match='encodied'):
            parse_mh_certificate(b'<?xml version="1.0"?><root><foo/></root>')
