"""
Cliente standalone de la API del Ministerio de Hacienda de El Salvador.

Réplica del código Odoo (models/l10n_sv_api.py + models/l10n_sv_signer.py)
pero sin dependencia de Odoo. Usa requests + cryptography directamente.

Útil para:
  - Tests de integración rápidos (sin levantar Odoo)
  - Detectar cambios en la API de Hacienda
  - Depurar problemas de conexión/autenticación
"""

import base64
import json
import logging
import time
import xml.etree.ElementTree as ET

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

logger = logging.getLogger(__name__)

ENDPOINTS = {
    'auth': '/seguridad/auth',
    'receptordte': '/seguridad/receptordte',
    'anulardte': '/seguridad/anulardte',
    'contingencia': '/seguridad/contingencia',
}

DTE_VERSION_V3_TYPES = ('03', '04', '05', '06')
DEFAULT_TIMEOUT = 60
TOKEN_TTL_SECONDS = 55 * 60


# ─── Base64url helpers ──────────────────────────────────────────────

def b64url_encode(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def b64url_decode(s):
    padding = 4 - (len(s) % 4)
    if padding != 4:
        s = s + ('=' * padding)
    return base64.urlsafe_b64decode(s)


# ─── Certificado MH / JWS Signer ────────────────────────────────────

def parse_mh_certificate(cert_xml_bytes):
    """Extrae la clave privada RSA del XML de certificado MH."""
    try:
        root = ET.fromstring(cert_xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f'El certificado no es XML válido: {e}')

    embodied = None
    for elem in root.iter():
        tag_lower = elem.tag.lower()
        if tag_lower.endswith('encodied') and elem.text:
            for p in root.iter():
                if elem in list(p):
                    if 'private' in p.tag.lower():
                        embodied = elem.text
                        break
        if embodied:
            break

    if not embodied:
        for elem in root.iter():
            if elem.tag.lower().endswith('encodied') and elem.text:
                embodied = elem.text
                break

    if not embodied:
        raise ValueError('No se encontró <encodied> con la clave privada en el certificado.')

    try:
        pem_bytes = base64.b64decode(embodied)
    except Exception as e:
        raise ValueError(f'El contenido del certificado no es Base64 válido: {e}')

    try:
        private_key = serialization.load_pem_private_key(pem_bytes, password=None)
    except Exception as e:
        raise ValueError(f'No se pudo cargar la clave privada PEM: {e}')

    return private_key


def sign_jws(payload_dict, private_key, kid):
    """Firma un payload como JWS compacto RS512."""
    header = {'alg': 'RS512', 'kid': kid}
    header_b64 = b64url_encode(json.dumps(header, separators=(',', ':')))
    payload_b64 = b64url_encode(
        json.dumps(payload_dict, separators=(',', ':'), ensure_ascii=False)
    )
    signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA512())
    sig_b64 = b64url_encode(signature)
    return f'{header_b64}.{payload_b64}.{sig_b64}'


def verify_jws(jws, public_key):
    """Verifica un JWS RS512 con la clave pública."""
    parts = jws.split('.')
    if len(parts) != 3:
        raise ValueError('JWS debe tener 3 segmentos')
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f'{header_b64}.{payload_b64}'.encode('ascii')
    signature = b64url_decode(sig_b64)
    public_key.verify(signature, signing_input, padding.PKCS1v15(), hashes.SHA512())
    return json.loads(b64url_decode(payload_b64))


# ─── API Client ──────────────────────────────────────────────────────

class MHClient:
    """Cliente HTTP para la API del MH con cache de token en memoria."""

    def __init__(self, ambiente, api_user, api_password, timeout=DEFAULT_TIMEOUT):
        self.ambiente = ambiente
        self.api_user = api_user
        self.api_password = api_password
        self.timeout = timeout
        self._base_url = 'https://api.dtes.mh.gob.sv' if ambiente == '01' else 'https://apitest.dtes.mh.gob.sv'
        self._token = None
        self._token_expires_at = 0

    def _is_token_valid(self):
        return self._token is not None and int(time.time()) < self._token_expires_at - 300

    def authenticate(self, force_refresh=False):
        if not force_refresh and self._is_token_valid():
            return self._token

        url = self._base_url + ENDPOINTS['auth']
        logger.info('MH auth: POST %s (user=%s)', url, self.api_user)
        try:
            resp = requests.post(
                url,
                data={'user': self.api_user, 'pwd': self.api_password},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise ConnectionError(f'Error de red al autenticar: {e}')

        if resp.status_code != 200:
            raise ConnectionError(f'Auth MH falló: HTTP {resp.status_code} {resp.text[:300]}')

        try:
            data = resp.json()
        except ValueError as e:
            raise ValueError(f'Respuesta auth MH no es JSON: {e}')

        token = (data.get('body') or {}).get('token') or data.get('token')
        if not token:
            raise ValueError(f'Respuesta auth OK pero sin token: {data}')

        self._token = token
        self._token_expires_at = int(time.time()) + TOKEN_TTL_SECONDS
        return token

    def _post_signed(self, endpoint_key, signed_jws, ambiente=None, **body_extra):
        token = self.authenticate()
        url = self._base_url + ENDPOINTS[endpoint_key]
        body = {'ambiente': ambiente or self.ambiente, 'documento': signed_jws}
        body.update(body_extra)

        logger.info('MH POST %s (ambiente=%s)', url, body.get('ambiente'))
        try:
            resp = requests.post(
                url, json=body,
                headers={'Authorization': token, 'Content-Type': 'application/json'},
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            raise ConnectionError(f'Error de red en {endpoint_key}: {e}')

        try:
            payload = resp.json()
        except ValueError as e:
            raise ValueError(f'Respuesta MH no es JSON (HTTP {resp.status_code}): {e}')

        if resp.status_code >= 400 or (isinstance(payload, dict) and payload.get('status') == 'ERROR'):
            self._token = None
            raise MHApiError(resp.status_code, payload)

        return payload

    def get_dte_version(self, tipo_dte):
        """Retorna versión de schema según tipo de DTE."""
        return 3 if tipo_dte in DTE_VERSION_V3_TYPES else 1

    def send_dte(self, signed_jws, tipo_dte, id_envio=1, ambiente=None):
        ambiente = ambiente or self.ambiente
        return self._post_signed(
            'receptordte', signed_jws,
            ambiente=ambiente,
            idEnvio=id_envio,
            version=self.get_dte_version(tipo_dte),
            tipoDte=tipo_dte,
        )

    def invalidate_dte(self, signed_jws, id_envio=1, ambiente=None):
        ambiente = ambiente or self.ambiente
        return self._post_signed(
            'anulardte', signed_jws,
            ambiente=ambiente,
            idEnvio=id_envio,
            version=2,
        )

    def send_contingencia(self, signed_jws, id_envio=1, ambiente=None):
        ambiente = ambiente or self.ambiente
        return self._post_signed(
            'contingencia', signed_jws,
            ambiente=ambiente,
            idEnvio=id_envio,
            version=3,
        )


class MHApiError(Exception):
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body
        desc = (body.get('body') or {}).get('descripcionMsg') or body.get('body', str(body))
        super().__init__(f'MH error HTTP {status_code}: {desc}')
