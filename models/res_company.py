from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_sv_nit = fields.Char(string='NIT')
    l10n_sv_nrc = fields.Char(string='NRC')
    l10n_sv_nombre_comercial = fields.Char(string='Nombre Comercial')
    l10n_sv_giro = fields.Char(string='Giro')
    l10n_sv_telefono = fields.Char(string='Teléfono', help='Teléfono de contacto para el DTE')
    l10n_sv_correo = fields.Char(string='Correo Electrónico', help='Correo de contacto para el DTE')

    l10n_sv_municipio_id = fields.Many2one(
        'l10n_sv.municipio',
        string='Municipio MH',
        help='Seleccione el municipio para la localización de El Salvador'
    )

    l10n_sv_cod_actividad_id = fields.Many2one(
        'l10n_sv.actividad_economica',
        string='Actividad Económica (CAT-019)',
        help='Actividad económica del emisor según catálogo del MH'
    )
    l10n_sv_desc_actividad = fields.Char(
        string='Descripción de Actividad',
        help='Descripción complementaria de la actividad económica'
    )
    l10n_sv_tipo_establecimiento_id = fields.Many2one(
        'l10n_sv.tipo_establecimiento',
        string='Tipo de Establecimiento (CAT-009)',
        help='Tipo de establecimiento del emisor (Matriz, Sucursal, etc.)'
    )
    l10n_sv_cod_estable_mh = fields.Char(
        string='Código Establecimiento MH',
        size=4,
        help='Código del establecimiento asignado por el MH (4 dígitos). Requerido para CCF.'
    )
    l10n_sv_cod_punto_venta_mh = fields.Char(
        string='Código Punto de Venta MH',
        size=4,
        help='Código del punto de venta asignado por el MH (4 dígitos). Requerido para CCF.'
    )

    l10n_sv_ambiente = fields.Selection([
        ('00', 'Pruebas (Test)'),
        ('01', 'Producción (Certificación)'),
    ], string='Ambiente MH', default='00', required=True,
        help='Ambiente de la API del Ministerio de Hacienda. Use 00 para pruebas y 01 para producción.')

    l10n_sv_certificate_id = fields.Many2one(
        'ir.attachment',
        string='Certificado Digital MH',
        help='Certificado digital (.crt XML) emitido por el Ministerio de Hacienda para firma de DTE',
        domain=[('mimetype', 'in', ['application/xml', 'text/xml'])],
    )

    l10n_sv_nit_emisor = fields.Char(string='NIT Emisor (para autenticación)')

    @api.model
    def get_l10n_sv_api_config(self):
        """
        Retorna la configuración de la API del MH.
        Las credenciales sensibles se almacenan en ir.config_parameter.
        """
        self.ensure_one()
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'ambiente': self.l10n_sv_ambiente or '00',
            'base_url': 'https://apitest.dtes.mh.gob.sv' if self.l10n_sv_ambiente == '00' else 'https://api.dtes.mh.gob.sv',
            'api_user': ICP.get_param('l10n_sv.api_user_%s' % self.id, default=''),
            'api_password': ICP.get_param('l10n_sv.api_password_%s' % self.id, default=''),
            'nit_emisor': self.l10n_sv_nit_emisor or self.l10n_sv_nit or '',
        }

    def action_open_credentials_help(self):
        return {
            'type': 'ir.actions.act_url',
            'url': 'https://www.factura.gob.sv/',
            'target': 'new',
        }

    def action_open_certificate_wizard(self):
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/binary/download_document?model=ir.attachment&id=%s' % (self.l10n_sv_certificate_id.id or 0),
            'target': 'self',
        }
