from odoo import models, fields

class ResCountryState(models.Model):
    _inherit = 'res.country.state'

    # Código de 2 dígitos del MH (ej: '05')
    l10n_sv_code = fields.Char(string='Código Departamento MH', size=2)

class L10nSvMunicipio(models.Model):
    _name = 'l10n_sv.municipio'
    _description = 'Municipios de El Salvador (MH)'
    _order = 'code'

    name = fields.Char(string='Nombre Municipio', required=True)
    code = fields.Char(string='Código Municipio MH', size=4, required=True)
    state_id = fields.Many2one(
        'res.country.state', 
        string='Departamento', 
        domain="[('country_id.code', '=', 'SV')]", 
        required=True
    )