from odoo import models, fields


class L10nSvCondicionOperacion(models.Model):
    _name = 'l10n_sv.condicion_operacion'
    _description = 'Condiciones de Operación MH (CAT-016)'
    _order = 'code'

    code = fields.Char(string='Código', size=1, required=True, index=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)
