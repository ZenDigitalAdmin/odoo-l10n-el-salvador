from odoo import models, fields


class L10nSvTipoDocumento(models.Model):
    _name = 'l10n_sv.tipo_documento'
    _description = 'Tipos de Documento de Identificación MH (CAT-022)'
    _order = 'code'

    code = fields.Char(string='Código', size=2, required=True, index=True)
    name = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)
