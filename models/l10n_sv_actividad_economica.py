from odoo import models, fields, api


class L10nSvActividadEconomica(models.Model):
    _name = 'l10n_sv.actividad_economica'
    _description = 'Actividades Económicas del Catálogo CAT019 MH'
    _order = 'code'
    _rec_name = 'description'

    code = fields.Char(string='Código Actividad', size=10, required=True, index=True)
    description = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)

    @api.depends('code', 'description')
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"{record.code} - {record.description}"