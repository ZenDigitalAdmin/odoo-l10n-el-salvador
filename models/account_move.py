import json
import logging
import uuid
import re
import secrets
import string
from datetime import datetime

from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CONDICION_CONTADO = '1'
CONDICION_CREDITO = '2'
CONDICION_ANTICIPO = '3'

DTE_VERSION_MAP = {
    '01': 1,
    '03': 3,
    '04': 3,
    '05': 3,
    '06': 3,
    '07': 1,
    '08': 1,
    '09': 1,
    '11': 1,
    '14': 1,
    '15': 1,
}


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
    ], string='Condición de la Operación', default=CONDICION_CONTADO)

    l10n_sv_dte_codigo_generacion = fields.Char(
        string='Código de Generación (UUID)',
        readonly=True, copy=False, size=36,
    )
    l10n_sv_dte_numero_control = fields.Char(
        string='Número de Control',
        readonly=True, copy=False, size=31,
    )
    l10n_sv_dte_sello_recepcion = fields.Char(
        string='Sello de Recepción MH',
        readonly=True, copy=False, size=40,
    )

    l10n_sv_dte_state = fields.Selection([
        ('draft', 'Borrador'),
        ('json_generated', 'JSON Generado'),
        ('signed', 'Firmado'),
        ('sent', 'Enviado'),
        ('processed', 'Procesado por MH'),
        ('rejected', 'Rechazado por MH'),
        ('contingencia', 'En Contingencia'),
        ('invalidating', 'Invalidando'),
        ('invalidated', 'Invalidado por MH'),
    ], string='Estado DTE', default='draft', readonly=True, copy=False,
        tracking=True)

    l10n_sv_dte_json = fields.Text(
        string='JSON DTE (crudo)',
        readonly=True, copy=False,
        help='JSON del DTE generado, antes de firmar. Se usa para re-firma y auditoría.',
    )
    l10n_sv_dte_signed = fields.Text(
        string='JWS Firmado',
        readonly=True, copy=False,
        help='JWS en formato compacto enviado al MH (header.payload.signature).',
    )
    l10n_sv_dte_response = fields.Text(
        string='Respuesta MH',
        readonly=True, copy=False,
        help='Última respuesta JSON del Ministerio de Hacienda.',
    )
    l10n_sv_dte_contingencia = fields.Boolean(
        string='Marcar para contingencia',
        help='Si está activo, el DTE se almacena localmente y se transmite cuando el servicio del MH esté disponible.',
    )
    l10n_sv_dte_tipo_contingencia = fields.Selection([
        ('1', 'Falla de internet'),
        ('2', 'Servicio del MH no disponible'),
        ('3', 'MH rechaza transmisión'),
        ('4', 'Falla del sistema del emisor'),
        ('5', 'Otra'),
    ], string='Tipo de Contingencia')

    l10n_sv_dte_documento_relacionado_ids = fields.One2many(
        'account.move', 'reversed_entry_id',
        string='Documentos Relacionados',
    )

    l10n_sv_dte_observaciones = fields.Text(
        string='Observaciones DTE',
        help='Observaciones que se incluirán en la sección extension del DTE.',
    )
    l10n_sv_dte_forma_pago_id = fields.Many2one(
        'l10n_sv.forma_pago',
        string='Forma de Pago (CAT-017)',
        default=lambda self: self._default_forma_pago(),
        help='Forma de pago predominante para esta operación (CAT-017).',
    )
    l10n_sv_dte_num_pago_electronico = fields.Char(
        string='Número de Pago Electrónico',
        size=100,
        help='Código de pago electrónico generado por la plataforma de pagos (opcional).',
    )

    l10n_sv_dte_send_attempts = fields.Integer(
        string='Intentos de Envío',
        default=0, copy=False, readonly=True,
        help='Número de veces que se ha intentado enviar este DTE al MH.',
    )
    l10n_sv_dte_last_attempt_at = fields.Datetime(
        string='Último Intento',
        copy=False, readonly=True,
    )
    l10n_sv_dte_last_error = fields.Text(
        string='Último Error',
        copy=False, readonly=True,
        help='Mensaje del último error de envío o invalidación.',
    )
    l10n_sv_dte_state_changed_at = fields.Datetime(
        string='Último Cambio de Estado',
        copy=False, readonly=True,
    )
    l10n_sv_dte_invalidated_at = fields.Datetime(
        string='Fecha de Invalidación',
        copy=False, readonly=True,
    )
    l10n_sv_dte_log_ids = fields.One2many(
        'l10n_sv.dte.log', 'move_id',
        string='Bitácora DTE',
        readonly=True,
    )
    l10n_sv_dte_log_count = fields.Integer(
        string='# Bitácora', compute='_compute_l10n_sv_dte_log_count',
    )

    l10n_sv_dte_qr_url = fields.Char(
        string='URL del Código QR',
        readonly=True, copy=False,
    )
    l10n_sv_dte_qr_image = fields.Text(
        string='SVG del Código QR',
        readonly=True, copy=False,
        help='Código QR en formato SVG generado al procesarse el DTE. '
             'Se incrusta en el reporte QWeb del DTE.',
    )

    @api.depends('l10n_sv_dte_log_ids')
    def _compute_l10n_sv_dte_log_count(self):
        for move in self:
            move.l10n_sv_dte_log_count = len(move.l10n_sv_dte_log_ids)

    @api.model
    def _generate_codigo_generacion(self):
        return str(uuid.uuid4()).upper()

    @api.model
    def _generate_numero_control(self, tipo_dte, cod_estable='0001', cod_punto_venta='0001'):
        seed = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
        correlativo = ''.join(secrets.choice(string.digits) for _ in range(15))
        return 'DTE-%s-%s%s-%s' % (tipo_dte, cod_estable, cod_punto_venta, '%s%s' % (seed[:2], correlativo))

    def _ensure_dte_identifiers(self):
        self.ensure_one()
        if not self.l10n_sv_dte_tipo_doc:
            return False
        if not self.l10n_sv_dte_codigo_generacion:
            self.l10n_sv_dte_codigo_generacion = self._generate_codigo_generacion()
        if not self.l10n_sv_dte_numero_control:
            company = self.company_id
            cod_estable = company.l10n_sv_cod_estable_mh or '0001'
            cod_punto_venta = company.l10n_sv_cod_punto_venta_mh or '0001'
            self.l10n_sv_dte_numero_control = self._generate_numero_control(
                self.l10n_sv_dte_tipo_doc, cod_estable, cod_punto_venta,
            )
        return True

    def _validate_dte_basic(self):
        self.ensure_one()
        if not self.l10n_sv_dte_tipo_doc:
            raise UserError('Debe seleccionar el Tipo de Documento DTE antes de generar el JSON.')
        if not self.partner_id.l10n_sv_municipio_id:
            raise UserError('El cliente no tiene asignado un Municipio homologado por el MH.')
        if not self.company_id.l10n_sv_municipio_id:
            raise UserError('Tu empresa no tiene asignado un Municipio homologado por el MH.')
        tipo = self.l10n_sv_dte_tipo_doc
        if tipo in ('03', '05', '06'):
            if not self.partner_id.l10n_sv_nit or not self.partner_id.l10n_sv_nrc:
                raise UserError(
                    'Para DTE tipo %s (CCF/NC/ND) el cliente debe tener NIT y NRC configurados.'
                    % tipo
                )
        if tipo == '01' and not self.partner_id.l10n_sv_nit and not self.partner_id.l10n_sv_num_documento:
            raise UserError(
                'Para Factura de Consumidor Final (01) el cliente debe tener NIT o un número de documento (DUI/Pasaporte).'
            )

    @api.model
    def _default_forma_pago(self):
        forma = self.env['l10n_sv.forma_pago'].search([('code', '=', '01')], limit=1)
        return forma.id if forma else False

    def _get_dte_line_tributos(self, line):
        tributos = []
        for tax in line.tax_ids:
            tributo = tax.l10n_sv_tributo_id
            if not tributo:
                continue
            if tax.amount_type == 'percent':
                valor = round(line.price_subtotal * (tax.amount / 100.0), 2)
            else:
                tax_data = tax.compute_all(
                    line.price_unit, currency=line.currency_id, quantity=line.quantity,
                    product=line.product_id, partner=line.partner_id,
                )
                if tax_data['taxes']:
                    valor = round(abs(tax_data['taxes'][0]['amount']), 2)
                else:
                    valor = 0.0
            tributos.append({
                'codigo': tributo.code,
                'descripcion': tributo.name,
                'valor': abs(valor),
            })
        return tributos

    def _get_dte_line_iva_item(self, line):
        for tax in line.tax_ids:
            tributo = tax.l10n_sv_tributo_id
            if tributo and tributo.code == '20':
                if tax.amount_type == 'percent':
                    monto = round(line.price_subtotal * (tax.amount / 100.0), 2)
                else:
                    tax_data = tax.compute_all(
                        line.price_unit, currency=line.currency_id, quantity=line.quantity,
                        product=line.product_id, partner=line.partner_id,
                    )
                    monto = round(abs(tax_data['taxes'][0]['amount']), 2) if tax_data['taxes'] else 0.0
                return {'codigo': '20', 'monto': abs(monto)}
        return None

    def _build_cuerpo_documento(self):
        version = DTE_VERSION_MAP.get(self.l10n_sv_dte_tipo_doc, 1)
        cuerpo = []
        resumen = {
            'totalNoSuj': 0.0,
            'totalExenta': 0.0,
            'totalGravada': 0.0,
            'totalNoGravado': 0.0,
            'descuNoSuj': 0.0,
            'descuExenta': 0.0,
            'descuGravada': 0.0,
            'montoTotalOperacion': 0.0,
            'tributos': {},
            'iva_items': {},
        }
        for idx, line in enumerate(self.invoice_line_ids.filtered(lambda l: not l.display_type), start=1):
            price_unit = round(line.price_unit, 2)
            discount_pct = line.discount or 0.0
            descuento = round(price_unit * line.quantity * (discount_pct / 100.0), 2)
            gravada = round(line.price_subtotal, 2)
            item = {
                'numItem': idx,
                'tipoItem': 1,
                'cantidad': line.quantity,
                'codigo': line.product_id.default_code or 'SERV',
                'descripcion': line.name,
                'precioUni': price_unit,
                'montoDescu': descuento,
                'ventaNoSuj': 0.0,
                'ventaExenta': 0.0,
                'ventaGravada': gravada,
                'noGravado': 0.0,
                'psv': round(line.price_total, 2),
            }
            tributos = self._get_dte_line_tributos(line)
            if tributos:
                item['tributos'] = tributos
                item['codTributo'] = tributos[0]['codigo']
            if version >= 3:
                iva = self._get_dte_line_iva_item(line)
                if iva:
                    item['ivaItem'] = iva
            cuerpo.append(item)
            resumen['totalGravada'] += gravada
            resumen['descuGravada'] += descuento
            resumen['montoTotalOperacion'] += line.price_total
            for tr in tributos:
                agg = resumen['tributos'].setdefault(
                    tr['codigo'], {'codigo': tr['codigo'], 'descripcion': tr['descripcion'], 'valor': 0.0},
                )
                agg['valor'] += tr['valor']
            if version >= 3 and 'ivaItem' in item:
                cod = item['ivaItem']['codigo']
                iva_agg = resumen['iva_items'].setdefault(cod, {'codigo': cod, 'monto': 0.0})
                iva_agg['monto'] += item['ivaItem']['monto']
        return cuerpo, resumen

    def _build_pagos(self):
        condicion = self.l10n_sv_dte_condicion_operacion or CONDICION_CONTADO
        forma_codigo = self.l10n_sv_dte_forma_pago_id.code if self.l10n_sv_dte_forma_pago_id else '01'
        total = round(self.amount_total, 2)
        if condicion == CONDICION_CONTADO:
            return [{
                'codigo': forma_codigo,
                'montoPago': total,
                'referencia': self.l10n_sv_dte_num_pago_electronico or '',
            }]
        term = self.invoice_payment_term_id
        if not term or not term.line_ids:
            return [{
                'codigo': forma_codigo,
                'plazo': '01',
                'montoPago': total,
                'referencia': self.l10n_sv_dte_num_pago_electronico or '',
            }]
        pagos = []
        for term_line in term.line_ids:
            monto = round(total * (term_line.value_amount / 100.0), 2)
            pagos.append({
                'codigo': forma_codigo,
                'plazo': '%02d' % (term_line.days or 0),
                'referencia': self.l10n_sv_dte_num_pago_electronico or '',
                'periodo': {
                    'plazo': '%02d' % (term_line.days or 0),
                },
                'montoPago': monto,
            })
        if pagos and abs(sum(p['montoPago'] for p in pagos) - total) > 0.01:
            pagos[-1]['montoPago'] = round(total - sum(p['montoPago'] for p in pagos[:-1]), 2)
        return pagos

    def _build_resumen(self, resumen):
        version = DTE_VERSION_MAP.get(self.l10n_sv_dte_tipo_doc, 1)
        condicion = int(self.l10n_sv_dte_condicion_operacion or CONDICION_CONTADO)
        total_gravada = round(resumen['totalGravada'], 2)
        total_exenta = round(resumen['totalExenta'], 2)
        total_no_suj = round(resumen['totalNoSuj'], 2)
        total_no_gravado = round(resumen['totalNoGravado'], 2)
        descu_gravada = round(resumen['descuGravada'], 2)
        descu_exenta = round(resumen['descuExenta'], 2)
        descu_no_suj = round(resumen['descuNoSuj'], 2)
        sub_total_ventas = round(total_gravada + total_exenta + total_no_suj, 2)
        total_descu = round(descu_gravada + descu_exenta + descu_no_suj, 2)
        porcentaje = round((total_descu / sub_total_ventas * 100.0) if sub_total_ventas else 0.0, 2)
        sub_total = round(sub_total_ventas - total_descu, 2)
        iva_13 = resumen['iva_items'].get('20', {}).get('monto', 0.0) if version >= 3 else 0.0
        if version < 3:
            iva_13 = round(total_gravada * 0.13, 2)
        monto_total_operacion = round(resumen['montoTotalOperacion'], 2)
        total_pagar = round(monto_total_operacion, 2)
        resumen_out = {
            'totalNoSuj': total_no_suj,
            'totalExenta': total_exenta,
            'totalGravada': total_gravada,
            'subTotalVentas': sub_total_ventas,
            'descuNoSuj': descu_no_suj,
            'descuExenta': descu_exenta,
            'descuGravada': descu_gravada,
            'porcentajeDescuento': porcentaje,
            'totalDescu': total_descu,
            'subTotal': sub_total,
            'montoTotalOperacion': monto_total_operacion,
            'totalNoGravado': total_no_gravado,
            'totalPagar': total_pagar,
            'totalLetras': self._num_to_words_es(total_pagar),
            'saldoFavor': 0.0,
            'condicionOperacion': condicion,
        }
        if version >= 3:
            resumen_out['ivaRete1'] = 0.0
            resumen_out['reteRenta'] = 0.0
        else:
            resumen_out['ivaPerci1'] = 0.0
            resumen_out['ivaRete1'] = 0.0
            resumen_out['reteRenta'] = 0.0
        tributos_out = [
            {'codigo': t['codigo'], 'descripcion': t['descripcion'], 'valor': round(t['valor'], 2)}
            for t in resumen['tributos'].values()
        ]
        if tributos_out:
            resumen_out['tributos'] = tributos_out
        if version >= 3 and resumen['iva_items']:
            resumen_out['iva'] = [
                {'ivaItem': {'codigo': i['codigo'], 'monto': round(i['monto'], 2)}}
                for i in resumen['iva_items'].values()
            ]
        return resumen_out

    def _build_documento_relacionado(self):
        if self.l10n_sv_dte_tipo_doc not in ('05', '06'):
            return None
        if not self.reversed_entry_id:
            return None
        ref = self.reversed_entry_id
        return [{
            'tipoDocumento': 'DTE-%s' % (ref.l10n_sv_dte_tipo_doc or '03'),
            'tipoGeneracion': 1,
            'numeroDocumento': ref.l10n_sv_dte_numero_control or '',
            'fechaEmision': fields.Date.to_string(ref.invoice_date) if ref.invoice_date else '',
        }]

    def _build_extension(self):
        if not self.l10n_sv_dte_observaciones:
            return None
        return {
            'nombEntrega': self.partner_id.name or '',
            'docuEntrega': re.sub(r'[^0-9]', '', self.partner_id.l10n_sv_nit or ''),
            'nombRecibe': self.partner_id.name or '',
            'docuRecibe': re.sub(r'[^0-9]', '', self.partner_id.l10n_sv_nit or ''),
            'observaciones': self.l10n_sv_dte_observaciones,
        }

    def _num_to_words_es(self, amount):
        if amount is None:
            return 'CERO DÓLARES CON CERO CENTAVOS'
        try:
            amount = round(float(amount), 2)
        except (TypeError, ValueError):
            return 'CERO DÓLARES CON CERO CENTAVOS'
        entero, centavos = int(amount), int(round((amount - int(amount)) * 100))
        return '%s DÓLARES CON %02d/100 USD' % (self._int_to_words_es(entero).upper(), centavos)

    def _int_to_words_es(self, n):
        if n == 0:
            return 'cero'
        if n == 100:
            return 'cien'
        unidades = ['', 'uno', 'dos', 'tres', 'cuatro', 'cinco', 'seis', 'siete', 'ocho', 'nueve']
        teens = ['diez', 'once', 'doce', 'trece', 'catorce', 'quince', 'dieciséis',
                 'diecisiete', 'dieciocho', 'diecinueve']
        decenas = ['', '', 'veinte', 'treinta', 'cuarenta', 'cincuenta',
                   'sesenta', 'setenta', 'ochenta', 'noventa']
        cientos = ['', 'ciento', 'doscientos', 'trescientos', 'cuatrocientos',
                   'quinientos', 'seiscientos', 'setecientos', 'ochocientos', 'novecientos']

        def under1000(x):
            if x == 0:
                return ''
            if x < 10:
                return unidades[x]
            if x < 20:
                return teens[x - 10]
            if x < 100:
                d, u = divmod(x, 10)
                if d == 2 and u:
                    return 'venti' + unidades[u]
                return decenas[d] + ('' if u == 0 else ' y ' + unidades[u])
            c, r = divmod(x, 100)
            base = 'ciento' if c == 1 else cientos[c]
            return base + ('' if r == 0 else ' ' + under1000(r))

        if n < 1000:
            return under1000(n)
        if n < 1_000_000:
            miles, r = divmod(n, 1000)
            head = 'mil' if miles == 1 else under1000(miles) + ' mil'
            return head + ('' if r == 0 else ' ' + under1000(r))
        millones, r = divmod(n, 1_000_000)
        head = 'un millón' if millones == 1 else under1000(millones) + ' millones'
        return head + ('' if r == 0 else ' ' + self._int_to_words_es(r))

    def action_generate_dte_json(self):
        self.ensure_one()
        self._validate_dte_basic()
        self._ensure_dte_identifiers()

        identificacion = {
            'version': DTE_VERSION_MAP.get(self.l10n_sv_dte_tipo_doc, 1),
            'ambiente': self.company_id.l10n_sv_ambiente or '00',
            'tipoDte': self.l10n_sv_dte_tipo_doc,
            'numeroControl': self.l10n_sv_dte_numero_control,
            'codigoGeneracion': self.l10n_sv_dte_codigo_generacion,
            'tipoModelo': 1,
            'tipoOperacion': 1,
            'fecEmi': fields.Date.to_string(self.invoice_date) if self.invoice_date else fields.Date.to_string(fields.Date.today()),
            'horEmi': datetime.now().strftime('%H:%M:%S'),
            'tipoMoneda': self.currency_id.name or 'USD',
        }

        emisor = {
            'nit': re.sub(r'[^0-9]', '', self.company_id.l10n_sv_nit or ''),
            'nrc': re.sub(r'[^0-9]', '', self.company_id.l10n_sv_nrc or ''),
            'nombre': self.company_id.name,
            'nombreComercial': self.company_id.l10n_sv_nombre_comercial or '',
            'codActividad': self.company_id.l10n_sv_cod_actividad_id.code or '',
            'descActividad': self.company_id.l10n_sv_desc_actividad or self.company_id.l10n_sv_cod_actividad_id.description or '',
            'tipoEstablecimiento': self.company_id.l10n_sv_tipo_establecimiento_id.code or '01',
            'direccion': {
                'departamento': self.company_id.state_id.l10n_sv_code or '',
                'municipio': self.company_id.l10n_sv_municipio_id.code[:2] if self.company_id.l10n_sv_municipio_id else '',
                'complemento': self.company_id.street or 'San Salvador',
            },
        }
        if self.company_id.l10n_sv_telefono:
            emisor['telefono'] = self.company_id.l10n_sv_telefono
        if self.company_id.l10n_sv_correo:
            emisor['correo'] = self.company_id.l10n_sv_correo
        if self.company_id.l10n_sv_cod_estable_mh:
            emisor['codEstableMH'] = self.company_id.l10n_sv_cod_estable_mh
        if self.company_id.l10n_sv_cod_punto_venta_mh:
            emisor['codPuntoVentaMH'] = self.company_id.l10n_sv_cod_punto_venta_mh

        receptor = {
            'nit': re.sub(r'[^0-9]', '', self.partner_id.l10n_sv_nit or ''),
            'nrc': re.sub(r'[^0-9]', '', self.partner_id.l10n_sv_nrc or ''),
            'nombre': self.partner_id.name,
            'codActividad': self.partner_id.l10n_sv_giro or '',
            'direccion': {
                'departamento': self.partner_id.state_id.l10n_sv_code or '',
                'municipio': self.partner_id.l10n_sv_municipio_id.code[:2] if self.partner_id.l10n_sv_municipio_id else '',
                'complemento': self.partner_id.street or 'Dirección Cliente',
            },
        }
        if self.l10n_sv_dte_tipo_doc == '01':
            tipo_doc = self.partner_id.l10n_sv_tipo_documento_id
            if tipo_doc and not self.partner_id.l10n_sv_nit:
                receptor['tipoDocumento'] = tipo_doc.code
                receptor['numDocumento'] = self.partner_id.l10n_sv_num_documento or ''

        cuerpo_documento, resumen = self._build_cuerpo_documento()
        resumen_out = self._build_resumen(resumen)
        pagos = self._build_pagos()
        if pagos:
            resumen_out['pagos'] = pagos
        if self.l10n_sv_dte_num_pago_electronico:
            resumen_out['numPagoElectronico'] = self.l10n_sv_dte_num_pago_electronico

        dte_payload = {
            'identificacion': identificacion,
            'emisor': emisor,
            'receptor': receptor,
            'cuerpoDocumento': cuerpo_documento,
            'resumen': resumen_out,
        }

        doc_rel = self._build_documento_relacionado()
        if doc_rel:
            dte_payload['documentoRelacionado'] = doc_rel

        extension = self._build_extension()
        if extension:
            dte_payload['extension'] = extension

        _logger.info('====== DTE PAYLOAD GENERADO PARA EL MH ======')
        _logger.info(dte_payload)
        _logger.info('=============================================')

        import json
        self.write({
            'l10n_sv_dte_state': 'json_generated',
            'l10n_sv_dte_json': json.dumps(dte_payload, ensure_ascii=False, indent=2),
        })

        return dte_payload

    def action_sign_dte(self):
        self.ensure_one()
        if not self.l10n_sv_dte_json:
            payload = self.action_generate_dte_json()
        else:
            import json
            payload = json.loads(self.l10n_sv_dte_json)

        signer = self.env['l10n_sv.signer'].sudo()
        jws = signer.sign_and_store(self, payload)

        self.write({
            'l10n_sv_dte_signed': jws,
            'l10n_sv_dte_state': 'signed',
        })
        _logger.info('DTE firmado: %s', self.l10n_sv_dte_numero_control)
        return True

    def _write_dte_state(self, new_state, extra=None):
        self.ensure_one()
        vals = {
            'l10n_sv_dte_state': new_state,
            'l10n_sv_dte_state_changed_at': fields.Datetime.now(),
        }
        if extra:
            vals.update(extra)
        self.write(vals)
        return True

    def _log_dte_attempt(self, operation, success, response=None, error_message=None,
                         status_code=None, response_code=None, sello_recepcion=None,
                         is_automatic=False, response_body=None):
        self.ensure_one()
        self.env['l10n_sv.dte.log'].sudo().create({
            'move_id': self.id,
            'operation': operation,
            'attempt_number': self.l10n_sv_dte_send_attempts + (0 if operation == 'invalidate' else 1),
            'success': bool(success),
            'status_code': status_code or '',
            'response_code': response_code or '',
            'sello_recepcion': sello_recepcion or '',
            'response_body': response_body or (json.dumps(response, ensure_ascii=False, indent=2) if response else ''),
            'error_message': error_message or '',
            'is_automatic': is_automatic,
        })

    def _compute_qr_url(self):
        self.ensure_one()
        nit = re.sub(r'[^0-9]', '', self.company_id.l10n_sv_nit or '')
        fecha = fields.Date.to_string(self.invoice_date) if self.invoice_date else fields.Date.to_string(fields.Date.today())
        total = round(self.amount_total, 2)
        cuerpo, resumen_agg = self._build_cuerpo_documento()
        iva_monto = 0.0
        for iva in resumen_agg.get('iva_items', {}).values():
            iva_monto += iva.get('monto', 0.0)
        iva_monto = round(iva_monto, 2)
        if not iva_monto:
            iva_monto = round(total - self.amount_untaxed, 2)
        from urllib.parse import urlencode
        params = urlencode({
            'nit': nit,
            'codigoGeneracion': self.l10n_sv_dte_codigo_generacion or '',
            'fechaEmision': fecha,
            'montoTotalOperacion': '%0.2f' % total,
            'montoIVA': '%0.2f' % iva_monto,
            'numeroControl': self.l10n_sv_dte_numero_control or '',
            'selloRecibido': self.l10n_sv_dte_sello_recepcion or '',
        })
        return 'https://portaldgii.mh.gob.sv/consulta/QR?%s' % params

    def _generate_qr_image(self):
        self.ensure_one()
        try:
            import qrcode
            from qrcode.image.svg import SvgPathImage
        except ImportError:
            _logger.warning(
                'No se pudo generar el QR: la librería "qrcode" no está instalada '
                '(pip install qrcode). DTE=%s',
                self.l10n_sv_dte_numero_control,
            )
            return None
        url = self._compute_qr_url()
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(image_factory=SvgPathImage)
        svg_bytes = img.to_string(encoding='utf-8')
        return url, svg_bytes

    def action_regenerate_qr(self):
        self.ensure_one()
        if self.l10n_sv_dte_state != 'processed':
            raise UserError(
                'Solo se puede generar el QR para DTEs en estado "Procesado por MH". '
                'Estado actual: %s' % self.l10n_sv_dte_state,
            )
        result = self._generate_qr_image()
        if not result:
            raise UserError(
                'No se pudo generar el QR. Verifique que la librería "qrcode" esté '
                'instalada en el entorno de Odoo (pip install qrcode).'
            )
        url, svg_bytes = result
        self.write({
            'l10n_sv_dte_qr_url': url,
            'l10n_sv_dte_qr_image': svg_bytes,
        })
        _logger.info('QR regenerado para DTE %s', self.l10n_sv_dte_numero_control)
        return True

    def get_qr_data_url(self):
        self.ensure_one()
        if not self.l10n_sv_dte_qr_image:
            return ''
        import base64
        b64 = base64.b64encode(self.l10n_sv_dte_qr_image.encode('utf-8')).decode('ascii')
        return 'data:image/svg+xml;base64,%s' % b64

    def action_send_dte(self, is_automatic=False):
        self.ensure_one()
        if not self.l10n_sv_dte_signed:
            self.action_sign_dte()
        if self.l10n_sv_dte_state == 'processed':
            raise UserError('Este DTE ya fue procesado por el MH (sello: %s).' % self.l10n_sv_dte_sello_recepcion)
        if self.l10n_sv_dte_state == 'invalidated':
            raise UserError('Este DTE ya fue invalidado por el MH.')
        if not self.l10n_sv_dte_contingencia:
            self._write_dte_state('sent', {
                'l10n_sv_dte_send_attempts': self.l10n_sv_dte_send_attempts + 1,
                'l10n_sv_dte_last_attempt_at': fields.Datetime.now(),
            })
            api = self.env['l10n_sv.api'].sudo()
            try:
                response = api.send_dte(
                    signed_jws=self.l10n_sv_dte_signed,
                    tipo_dte=self.l10n_sv_dte_tipo_doc,
                )
            except Exception as e:
                self._log_dte_attempt(
                    operation='send' if not is_automatic else 'contingencia',
                    success=False,
                    error_message=str(e),
                    is_automatic=is_automatic,
                )
                self.write({
                    'l10n_sv_dte_state': 'rejected',
                    'l10n_sv_dte_last_error': str(e),
                    'l10n_sv_dte_state_changed_at': fields.Datetime.now(),
                })
                raise
            body = (response or {}).get('body') if isinstance(response, dict) else None
            sello = (body or {}).get('selloRecibido') or (body or {}).get('selloRecepcion') if isinstance(body, dict) else None
            response_code = (body or {}).get('codigoMsg') or (body or {}).get('codigo') if isinstance(body, dict) else None
            status = (response or {}).get('status') if isinstance(response, dict) else None
            if status == 'OK' and sello:
                self._log_dte_attempt(
                    operation='send',
                    success=True,
                    response=response,
                    status_code=str(response.get('statusCode')) if isinstance(response, dict) else '',
                    response_code=response_code or '',
                    sello_recepcion=sello,
                    is_automatic=is_automatic,
                )
                self._write_dte_state('processed', {
                    'l10n_sv_dte_sello_recepcion': sello,
                    'l10n_sv_dte_last_error': False,
                })
                qr_result = self._generate_qr_image()
                if qr_result:
                    url, svg_bytes = qr_result
                    self.write({
                        'l10n_sv_dte_qr_url': url,
                        'l10n_sv_dte_qr_image': svg_bytes,
                    })
                _logger.info('DTE PROCESADO por MH: %s (sello=%s)', self.l10n_sv_dte_numero_control, sello)
            else:
                error_msg = (body or {}).get('descripcionMsg') or (body or {}).get('observaciones') if isinstance(body, dict) else None
                self._log_dte_attempt(
                    operation='send',
                    success=False,
                    response=response,
                    error_message=error_msg or 'Rechazado por el MH',
                    status_code=str(response.get('statusCode')) if isinstance(response, dict) else '',
                    response_code=response_code or '',
                    is_automatic=is_automatic,
                )
                self._write_dte_state('rejected', {'l10n_sv_dte_last_error': error_msg or 'Rechazado por el MH'})
                _logger.warning('DTE RECHAZADO por MH: %s - %s', self.l10n_sv_dte_numero_control, response)
        else:
            self._log_dte_attempt(
                operation='contingencia',
                success=True,
                error_message='Marcado para contingencia; el cron reintentará cuando haya servicio del MH.',
                is_automatic=False,
            )
            self._write_dte_state('contingencia')
            _logger.info('DTE marcado para contingencia: %s', self.l10n_sv_dte_numero_control)
        return True

    def action_resend_dte(self):
        self.ensure_one()
        if self.l10n_sv_dte_state not in ('rejected', 'contingencia'):
            raise UserError(
                'Solo se pueden reenviar DTEs en estado Rechazado o Contingencia. '
                'Estado actual: %s' % self.l10n_sv_dte_state,
            )
        if self.l10n_sv_dte_send_attempts >= 5:
            raise UserError(
                'Este DTE ya alcanzó el máximo de 5 intentos de envío al MH. '
                'Revise la configuración o contacte a soporte antes de reintentar.',
            )
        if self.l10n_sv_dte_state == 'contingencia':
            self.write({'l10n_sv_dte_contingencia': False})
        return self.action_send_dte()

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.l10n_sv_dte_state == 'processed':
            raise UserError(
                'No se puede reiniciar un DTE ya procesado por el MH. '
                'Si necesita corregirlo, invalídelo primero y luego emita uno nuevo.',
            )
        if self.l10n_sv_dte_state == 'invalidated':
            raise UserError('Este DTE ya fue invalidado por el MH y no puede reiniciarse.')
        return self.write({
            'l10n_sv_dte_state': 'draft',
            'l10n_sv_dte_state_changed_at': fields.Datetime.now(),
            'l10n_sv_dte_json': False,
            'l10n_sv_dte_signed': False,
            'l10n_sv_dte_response': False,
            'l10n_sv_dte_last_error': False,
            'l10n_sv_dte_contingencia': False,
            'l10n_sv_dte_tipo_contingencia': False,
        })

    def action_invalidate_dte(self):
        self.ensure_one()
        if not self.l10n_sv_dte_sello_recepcion:
            raise UserError('Solo se pueden invalidar DTEs que ya fueron procesados por el MH (con sello de recepción).')
        if not self.l10n_sv_dte_codigo_generacion:
            raise UserError('El DTE no tiene código de generación. No se puede invalidar.')
        if not self.company_id.l10n_sv_certificate_id:
            raise UserError('La compañía no tiene un certificado digital MH configurado.')

        self._write_dte_state('invalidating')

        invalidacion = {
            'identificacion': {
                'version': 2,
                'ambiente': self.company_id.l10n_sv_ambiente or '00',
                'codigoGeneracion': self.l10n_sv_dte_codigo_generacion,
                'fecAnula': fields.Date.to_string(fields.Date.today()),
                'horAnula': datetime.now().strftime('%H:%M:%S'),
            },
            'emisor': {
                'nit': re.sub(r'[^0-9]', '', self.company_id.l10n_sv_nit or ''),
                'nombre': self.company_id.name,
                'tipoEstablecimiento': self.company_id.l10n_sv_tipo_establecimiento_id.code or '01',
                'codEstableMH': self.company_id.l10n_sv_cod_estable_mh or '',
                'codPuntoVentaMH': self.company_id.l10n_sv_cod_punto_venta_mh or '',
            },
            'documento': {
                'tipoDte': self.l10n_sv_dte_tipo_doc,
                'codigoGeneracion': self.l10n_sv_dte_codigo_generacion,
                'selloRecibido': self.l10n_sv_dte_sello_recepcion,
                'numeroControl': self.l10n_sv_dte_numero_control,
                'fecEmi': fields.Date.to_string(self.invoice_date) if self.invoice_date else '',
                'montoIva': 0.0,
                'codigoGeneracionR': None,
            },
            'motivo': {
                'tipoAnulacion': 2,
                'motivoAnulacion': 'Anulación solicitada por el emisor',
                'nombreResponsable': self.company_id.l10n_sv_nombre_comercial or self.company_id.name,
                'tipDocResponsable': '36',
                'numDocResponsable': re.sub(r'[^0-9]', '', self.company_id.l10n_sv_nit or ''),
            },
        }

        signer = self.env['l10n_sv.signer'].sudo()
        nit = self.company_id.l10n_sv_nit_emisor or self.company_id.l10n_sv_nit or ''
        cert_bytes = self.company_id.l10n_sv_certificate_id.raw
        private_key = signer.parse_mh_certificate(cert_bytes)
        jws = signer.sign_dte(invalidacion, private_key, nit)

        api = self.env['l10n_sv.api'].sudo()
        try:
            response = api.invalidate_dte(signed_jws=jws)
        except Exception as e:
            self._log_dte_attempt(
                operation='invalidate',
                success=False,
                error_message=str(e),
            )
            self._write_dte_state('rejected', {'l10n_sv_dte_last_error': str(e)})
            raise

        body = (response or {}).get('body') if isinstance(response, dict) else None
        status = (response or {}).get('status') if isinstance(response, dict) else None
        if status == 'OK':
            self._log_dte_attempt(
                operation='invalidate',
                success=True,
                response=response,
                status_code=str(response.get('statusCode')) if isinstance(response, dict) else '',
            )
            self._write_dte_state('invalidated', {
                'l10n_sv_dte_invalidated_at': fields.Datetime.now(),
            })
            _logger.info('DTE INVALIDADO por MH: %s', self.l10n_sv_dte_numero_control)
        else:
            error_msg = (body or {}).get('descripcionMsg') if isinstance(body, dict) else 'Rechazo de invalidación'
            self._log_dte_attempt(
                operation='invalidate',
                success=False,
                response=response,
                error_message=error_msg,
                status_code=str(response.get('statusCode')) if isinstance(response, dict) else '',
            )
            self._write_dte_state('rejected', {'l10n_sv_dte_last_error': error_msg})
        return True
