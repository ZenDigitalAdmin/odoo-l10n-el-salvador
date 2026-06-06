from odoo import models, fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    l10n_sv_tributo_id = fields.Many2one(
        'l10n_sv.tributo',
        string='Tributo MH (CAT-015)',
        help='Tributo del Ministerio de Hacienda al que equivale este impuesto '
             '(IVA 13% = 20, FOVIAL = 59, etc.). Se usa para mapear el impuesto '
             'a la sección tributos del DTE.',
    )
