import requests
import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

class L10nSvApi(models.Model):
    _name = 'l10n_sv.api'
    _description = 'Conector API Ministerio de Hacienda'

    @api.model
    def authenticate(self):
        # Obtenemos la compañía activa
        company = self.env.company
        
        # URL de pruebas del Ministerio de Hacienda (Sandbox)
        url = "https://apitest.dtes.mh.gob.sv/seguridad/auth"
        
        payload = {
            "user": company.l10n_sv_api_user,
            "pwd": company.l10n_sv_api_password,
            "nit": company.l10n_sv_nit_emisor
        }
        
        try:
            _logger.info("Intentando conectar con Hacienda...")
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                token = data.get('body', {}).get('token')
                _logger.info("¡Conexión exitosa! Token obtenido.")
                return token
            else:
                _logger.error(f"Error MH {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            _logger.error(f"Error de red al conectar con MH: {e}")
            return None