from odoo import models, fields


class L10nSvTipoEstablecimiento(models.Model):
    _name = 'l10n_sv.tipo_establecimiento'
    _description = 'Tipos de Establecimiento MH (CAT-009)'
    _order = 'code'

    code = fields.Char(string='Código', size=2, required=True, index=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)
