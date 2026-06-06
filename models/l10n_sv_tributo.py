from odoo import models, fields


class L10nSvTributo(models.Model):
    _name = 'l10n_sv.tributo'
    _description = 'Tributos MH (CAT-015)'
    _order = 'code'

    code = fields.Char(string='Código', size=4, required=True, index=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)
