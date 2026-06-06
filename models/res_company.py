from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    # Datos básicos de Identificación Fiscal
    l10n_sv_nit = fields.Char(string='NIT')
    l10n_sv_nrc = fields.Char(string='NRC')
    l10n_sv_nombre_comercial = fields.Char(string='Nombre Comercial')
    l10n_sv_giro = fields.Char(string='Giro')
    
    # Campo para la ubicación homologada
    l10n_sv_municipio_id = fields.Many2one(
        'l10n_sv.municipio', 
        string='Municipio MH',
        help='Seleccione el municipio para la localización de El Salvador'
    )

    # Campos de configuración para la API de Hacienda
    l10n_sv_nit_emisor = fields.Char(string='NIT Emisor')
    l10n_sv_api_user = fields.Char(string='Usuario MH (API)')
    l10n_sv_api_password = fields.Char(string='Password MH (API)')