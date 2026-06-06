import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_sv_dte_tipo_doc = fields.Selection([
        ('01', 'Factura de Consumidor Final (FCF)'),
        ('03', 'Comprobante de Crédito Fiscal (CCF)'),
        ('05', 'Nota de Crédito (NC)'),
        ('06', 'Nota de Débito (ND)'),
        ('14', 'Factura de Sujeto Excluido (FSE)'),
    ], string='Tipo de Documento DTE', help='Tipo de documento electrónico homologado por el MH')

    l10n_sv_dte_condicion_operacion = fields.Selection([
        ('1', 'Contado'),
        ('2', 'Crédito'),
    ], string='Condición de la Operación', default='1')

    l10n_sv_dte_codigo_generacion = fields.Char(string='Código de Generación (UUID)', readonly=True, copy=False)
    l10n_sv_dte_numero_control = fields.Char(string='Número de Control', readonly=True, copy=False)
    l10n_sv_dte_sello_recepcion = fields.Char(string='Sello de Recepción MH', readonly=True, copy=False)

    def action_generate_dte_json(self):
        """
        Método para compilar los datos de Odoo y estructurar el JSON crudo para el Ministerio de Hacienda.
        """
        self.ensure_one()
        
        # Validaciones iniciales básicas antes de armar el JSON
        if not self.l10n_sv_dte_tipo_doc:
            raise UserError("Debe seleccionar el Tipo de Documento DTE antes de generar el JSON.")
        if not self.partner_id.l10n_sv_municipio_id:
            raise UserError("El cliente no tiene asignado un Municipio homologado por el MH.")
        if not self.company_id.l10n_sv_municipio_id:
            raise UserError("Tu empresa no tiene asignado un Municipio homologado por el MH.")

        # 1. Nodo de Identificación del DTE
        identificacion = {
            "version": 1,
            "tipoDte": self.l10n_sv_dte_tipo_doc,
            "condicionOperacion": int(self.l10n_sv_dte_condicion_operacion),
            "tipoMoneda": self.currency_id.name or "USD"
        }

        # 2. Nodo del Emisor (Tu empresa: DIAL Studio)
        emisor = {
            "nit": self.company_id.l10n_sv_nit or "",
            "nrc": self.company_id.l10n_sv_nrc or "",
            "nombre": self.company_id.name,
            "nombreComercial": self.company_id.l10n_sv_nombre_comercial or "",
            "codGiro": self.company_id.l10n_sv_giro or "",
            "direccion": {
                "departamento": self.company_id.state_id.l10n_sv_code or "",
                "municipio": self.company_id.l10n_sv_municipio_id.code or "",
                "complemento": self.company_id.street or "San Salvador"
            }
        }

        # 3. Nodo del Receptor (Tu Cliente)
        receptor = {
            "nit": self.partner_id.l10n_sv_nit or "",
            "nrc": self.partner_id.l10n_sv_nrc or "",
            "nombre": self.partner_id.name,
            "codGiro": self.partner_id.l10n_sv_giro or "",
            "direccion": {
                "departamento": self.partner_id.state_id.l10n_sv_code or "",
                "municipio": self.partner_id.l10n_sv_municipio_id.code or "",
                "complemento": self.partner_id.street or "Dirección Cliente"
            }
        }

        # 4. Cuerpo del Documento (Líneas de la Factura)
        cuerpo_documento = []
        num_item = 1
        for line in self.invoice_line_ids.filtered(lambda l: not l.display_type):
            item = {
                "numItem": num_item,
                "cantidad": line.quantity,
                "codigo": line.product_id.default_code or "SERV",
                "descripcion": line.name,
                "precioUni": line.price_unit,
                "montoDescu": 0.0,
                "ventaNoSuj": 0.0,
                "ventaExenta": 0.0,
                "ventaGravada": line.price_subtotal
            }
            cuerpo_documento.append(item)
            num_item += 1

        # Ensamblar el JSON Completo del DTE
        dte_payload = {
            "identificacion": identificacion,
            "emisor": emisor,
            "receptor": receptor,
            "cuerpoDocumento": cuerpo_documento
        }

        # Imprimir el resultado estructurado en los logs del contenedor para inspeccionarlo
        _logger.info("====== DTE PAYLOAD GENERADO PARA EL MH ======")
        _logger.info(dte_payload)
        _logger.info("=============================================")

        # Probar autenticación
        token = self.env['l10n_sv.api'].authenticate()
        
        if token:
            _logger.info("Autenticación exitosa, estamos listos para enviar.")
            # Aquí próximamente llamaremos al método de envío (POST)
        else:
            _logger.warning("Fallo en la autenticación. Revisa tus credenciales.")
        
        return True