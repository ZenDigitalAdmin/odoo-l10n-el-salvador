from odoo import models, fields


class L10nSvDteLog(models.Model):
    _name = 'l10n_sv.dte.log'
    _description = 'Bitácora de intentos DTE (envío / invalidación / contingencia)'
    _order = 'attempt_at desc, id desc'
    _rec_name = 'attempt_at'

    move_id = fields.Many2one(
        'account.move', string='Factura',
        required=True, ondelete='cascade', index=True,
    )
    company_id = fields.Many2one(
        'res.company', related='move_id.company_id', store=True,
    )
    operation = fields.Selection([
        ('send', 'Envío al MH'),
        ('invalidate', 'Invalidación'),
        ('contingencia', 'Reenvío contingencia'),
    ], string='Operación', required=True)
    attempt_number = fields.Integer(string='# Intento', default=1)
    attempt_at = fields.Datetime(string='Fecha/Hora', default=fields.Datetime.now, required=True)
    success = fields.Boolean(string='Éxito')
    status_code = fields.Char(string='HTTP Status', size=10)
    response_code = fields.Char(string='Código MH', size=20)
    sello_recepcion = fields.Char(string='Sello MH', size=40)
    response_body = fields.Text(string='Respuesta MH (cruda)')
    error_message = fields.Text(string='Mensaje de Error')
    is_automatic = fields.Boolean(
        string='Automático',
        help='Marcado cuando el intento fue disparado por el cron de contingencia.',
    )
