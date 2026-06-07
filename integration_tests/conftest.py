"""
Fixtures compartidos para tests de integración contra MH.

Soporta tres fuentes de configuración (por orden de precedencia):
  1. Variables de entorno (MH_*)
  2. Archivo .env (cargado con python-dotenv)
  3. Archivo config.yaml (YAML junto a este archivo)

Ver config.yaml.example para la lista completa de variables.
"""

import logging
import os
from pathlib import Path

import pytest

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)

ENV_PREFIX = 'MH_'


def _from_env_or_yaml(env_key, yaml_path, default=None):
    """Valor desde env var, o busca en dict YAML, o default."""
    val = os.environ.get(f'{ENV_PREFIX}{env_key}')
    if val is not None:
        return val
    # navegar el path YAML ej. "mh.api_user"
    node = _yaml_config()
    for key in yaml_path.split('.'):
        if isinstance(node, dict):
            node = node.get(key)
        else:
            return default
    return node if node is not None else default


_YAML_CACHE = None


def _yaml_config():
    global _YAML_CACHE
    if _YAML_CACHE is not None:
        return _YAML_CACHE
    path = Path(__file__).parent / 'config.yaml'
    if path.exists():
        import yaml
        with open(path) as f:
            _YAML_CACHE = yaml.safe_load(f) or {}
    else:
        _YAML_CACHE = {}
    return _YAML_CACHE


def _require(key, yaml_path, label):
    """Obtiene un valor obligatorio o salta el test."""
    val = _from_env_or_yaml(key, yaml_path)
    if val:
        return val
    pytest.skip(
        f'{label} no configurado. Define {ENV_PREFIX}{key}= en .env / entorno, '
        f'o config.yaml → {yaml_path}'
    )
    return None  # unreachable


def _load_dotenv():
    """Carga .env si existe y python-dotenv está disponible."""
    dotenv_path = Path(__file__).parent / '.env'
    if dotenv_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(dotenv_path, override=False)
            logging.getLogger(__name__).info('Cargado .env desde %s', dotenv_path)
        except ImportError:
            logging.getLogger(__name__).warning(
                '.env presente pero python-dotenv no instalado. '
                'pip install python-dotenv o carga las vars manualmente.'
            )


_load_dotenv()


@pytest.fixture(scope='session')
def config():
    """Dict con la configuración completa (simula estructura YAML)."""
    return {
        'mh': {
            'ambiente': _require('AMBIENTE', 'mh.ambiente', 'Ambiente MH'),
            'api_user': _require('API_USER', 'mh.api_user', 'Usuario API MH'),
            'api_password': _require('API_PASSWORD', 'mh.api_password',
                                     'Contraseña API MH'),
            'nit_emisor': _require('NIT_EMISOR', 'mh.nit_emisor', 'NIT emisor'),
            'cod_estable': _from_env_or_yaml('COD_ESTABLE',
                                             'mh.cod_estable', '0001'),
            'cod_punto_venta': _from_env_or_yaml('COD_PUNTO_VENTA',
                                                  'mh.cod_punto_venta', '0001'),
            'timeout': int(_from_env_or_yaml('TIMEOUT', 'mh.timeout', '60')),
        },
        'certificate': {
            'path': _require('CERT_PATH', 'certificate.path',
                             'Ruta al certificado MH'),
        },
        'dte_test': {
            'tipo_doc': _from_env_or_yaml('DTE_TIPO_DOC',
                                          'dte_test.tipo_doc', '01'),
            'cod_estable': _from_env_or_yaml('COD_ESTABLE',
                                             'dte_test.cod_estable', '0001'),
            'cod_punto_venta': _from_env_or_yaml('COD_PUNTO_VENTA',
                                                  'dte_test.cod_punto_venta', '0001'),
            'receptor_nombre': _from_env_or_yaml('RECEPTOR_NOMBRE',
                                                  'dte_test.receptor_nombre',
                                                  'Cliente Prueba S.A. de C.V.'),
            'receptor_nit': _from_env_or_yaml('RECEPTOR_NIT',
                                              'dte_test.receptor_nit',
                                              '06140101234567'),
            'receptor_nrc': _from_env_or_yaml('RECEPTOR_NRC',
                                              'dte_test.receptor_nrc', '7654321'),
            'receptor_giro': _from_env_or_yaml('RECEPTOR_GIRO',
                                               'dte_test.receptor_giro', 'Comercio'),
            'receptor_direccion': _from_env_or_yaml('RECEPTOR_DIRECCION',
                                                     'dte_test.receptor_direccion',
                                                     'Calle Cliente 456'),
        },
    }


@pytest.fixture(scope='session')
def cert_path(config):
    path = config['certificate']['path']
    p = Path(path)
    if not p.is_absolute():
        p = Path(__file__).parent / p
    if not p.exists():
        pytest.skip(f'Certificado no encontrado: {p}')
    return p


@pytest.fixture(scope='session')
def private_key(cert_path):
    """Carga la clave privada RSA desde el certificado XML MH."""
    from mh_client import parse_mh_certificate
    return parse_mh_certificate(cert_path.read_bytes())


@pytest.fixture(scope='session')
def client(config):
    """Cliente HTTP listo para llamar a la API de MH."""
    from mh_client import MHClient
    mh = config['mh']
    return MHClient(
        ambiente=mh['ambiente'],
        api_user=mh['api_user'],
        api_password=mh['api_password'],
        timeout=mh.get('timeout', 60),
    )


@pytest.fixture(scope='session')
def nit_emisor(config):
    return config['mh']['nit_emisor']
