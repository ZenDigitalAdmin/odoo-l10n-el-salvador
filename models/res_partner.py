from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Para clientes, el NIT también puede ser el DUI en caso de consumidor final
    l10n_sv_nit = fields.Char(string='NIT / DUI', help='Número de Identificación Tributaria o DUI')
    l10n_sv_nrc = fields.Char(string='NRC', help='Número de Registro de Contribuyente')
    l10n_sv_nombre_comercial = fields.Char(string='Nombre Comercial')
    l10n_sv_giro = fields.Char(string='Giro / Actividad Económica')
    l10n_sv_municipio_id = fields.Many2one('l10n_sv.municipio', string='Municipio MH', domain="[('state_id', '=', state_id)]")
    
    l10n_sv_tipo_contribuyente = fields.Selection([
        ('grande', 'Grande Contribuyente'),
        ('mediano', 'Mediano Contribuyente'),
        ('otros', 'Otros / Pequeño'),
    ], string='Tipo de Contribuyente', default='otros')