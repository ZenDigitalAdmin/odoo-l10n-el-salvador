import logging

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class L10nSvDteSendWizard(models.TransientModel):
    _name = 'l10n_sv.dte.send.wizard'
    _description = 'Wizard de Envío Masivo DTE'

    move_ids = fields.Many2many(
        'account.move', string='Facturas a Procesar',
        required=True,
    )
    state = fields.Selection([
        ('draft', 'Pendiente'),
        ('done', 'Completado'),
    ], string='Estado', default='draft')
    total_count = fields.Integer(string='Total')
    success_count = fields.Integer(string='Procesados')
    failed_count = fields.Integer(string='Fallidos')
    line_ids = fields.One2many(
        'l10n_sv.dte.send.wizard.line', 'wizard_id',
        string='Detalle',
    )
    include_draft = fields.Boolean(
        string='Incluir Borradores (generar + firmar + enviar)',
        default=True,
        help='Si está activo, también procesa facturas en estado draft DTE. '
             'Si no, solo procesa las que ya están firmadas o enviadas.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'account.move' and self.env.context.get('active_ids'):
            res['move_ids'] = [(6, 0, self.env.context['active_ids'])]
        return res

    def _prepare_line(self, move, success, message):
        return {
            'move_id': move.id,
            'wizard_id': self.id,
            'name': move.name or '',
            'partner_id': move.partner_id.id,
            'state': move.l10n_sv_dte_state,
            'success': success,
            'message': message,
        }

    def action_send(self):
        self.ensure_one()
        if not self.move_ids:
            raise UserError('No se han seleccionado facturas para procesar.')
        success, failed = 0, 0
        lines = []
        for move in self.move_ids:
            if move.l10n_sv_dte_state == 'processed':
                lines.append(self._prepare_line(move, True, 'Ya estaba procesado por el MH.'))
                success += 1
                continue
            if move.l10n_sv_dte_state == 'invalidated':
                lines.append(self._prepare_line(move, False, 'DTE invalidado por el MH; no se puede reenviar.'))
                failed += 1
                continue
            if not self.include_draft and move.l10n_sv_dte_state not in ('json_generated', 'signed'):
                lines.append(self._prepare_line(move, False, 'Saltado: estado draft sin generar JSON.'))
                failed += 1
                continue
            try:
                move.action_send_dte()
                if move.l10n_sv_dte_state == 'processed':
                    lines.append(self._prepare_line(move, True, 'Procesado por el MH (sello asignado).'))
                    success += 1
                else:
                    lines.append(self._prepare_line(move, False, move.l10n_sv_dte_last_error or 'Sin confirmación del MH.'))
                    failed += 1
            except Exception as e:
                _logger.warning('Error enviando DTE %s: %s', move.name, e)
                lines.append(self._prepare_line(move, False, str(e)))
                failed += 1
        self.write({
            'state': 'done',
            'total_count': len(self.move_ids),
            'success_count': success,
            'failed_count': failed,
            'line_ids': [(0, 0, ln) for ln in lines],
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'l10n_sv.dte.send.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class L10nSvDteSendWizardLine(models.TransientModel):
    _name = 'l10n_sv.dte.send.wizard.line'
    _description = 'Línea de resultado del Wizard de Envío Masivo DTE'

    wizard_id = fields.Many2one('l10n_sv.dte.send.wizard', required=True, ondelete='cascade')
    move_id = fields.Many2one('account.move', string='Factura')
    name = fields.Char(string='Referencia')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    state = fields.Char(string='Estado DTE')
    success = fields.Boolean(string='Éxito')
    message = fields.Char(string='Mensaje')
