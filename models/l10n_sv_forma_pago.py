from odoo import models, fields


class L10nSvFormaPago(models.Model):
    _name = 'l10n_sv.forma_pago'
    _description = 'Forma de Pago MH (CAT-017)'
    _order = 'code'

    code = fields.Char(string='Código', size=2, required=True, index=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)
