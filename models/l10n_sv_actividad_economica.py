from odoo import models, fields

class L10nSvActividadEconomica(models.Model):
    _name = 'l10n_sv.actividad_economica'
    _description = 'Actividades Económicas del Catálogo CAT019 MH'
    _order = 'code'

    code = fields.Char(string='Código Actividad', size=10, required=True, index=True)
    description = fields.Char(string='Descripción', required=True)
    active = fields.Boolean(string='Activo', default=True)