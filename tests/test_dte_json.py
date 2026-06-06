import json
from unittest.mock import patch

from odoo.tests import tagged
from odoo.exceptions import UserError

from .common import L10nSvDteTestBase, TEST_NIT_DIGITS


@tagged('post_install', '-at_install', 'l10n_sv_dte', 'l10n_sv_dte_json')
class TestL10nSvDteJson(L10nSvDteTestBase):

    def test_01_fcf_v1_identificacion(self):
        invoice = self._create_invoice(tipo_dte='01')
        payload = invoice.action_generate_dte_json()
        ident = payload['identificacion']
        self.assertEqual(ident['version'], 1)
        self.assertEqual(ident['tipoDte'], '01')
        self.assertEqual(ident['ambiente'], '00')
        self.assertEqual(ident['tipoMoneda'], 'USD')
        self.assertIn('numeroControl', ident)
        self.assertIn('codigoGeneracion', ident)

    def test_02_ccf_v3_identificacion(self):
        invoice = self._create_invoice(tipo_dte='03', partner=self.partner)
        payload = invoice.action_generate_dte_json()
        ident = payload['identificacion']
        self.assertEqual(ident['version'], 3)
        self.assertEqual(ident['tipoDte'], '03')

    def test_03_emisor_strips_dashes_from_nit(self):
        self.company.write({'l10n_sv_nit': '0614-140610-001-2'})
        invoice = self._create_invoice()
        payload = invoice.action_generate_dte_json()
        self.assertEqual(payload['emisor']['nit'], TEST_NIT_DIGITS)

    def test_04_emisor_direccion_uses_municipio_code_2digits(self):
        invoice = self._create_invoice()
        payload = invoice.action_generate_dte_json()
        self.assertEqual(
            payload['emisor']['direccion']['municipio'],
            self.municipio.code[:2],
        )

    def test_05_cuerpo_documento_has_tributos_for_iva_line(self):
        if not self.iva_13:
            self.skipTest('No se encontró el impuesto IVA 13% mapeado a tributo 20.')
        invoice = self._create_invoice(cantidad=2, precio=100.0)
        payload = invoice.action_generate_dte_json()
        cuerpo = payload['cuerpoDocumento']
        self.assertEqual(len(cuerpo), 1)
        item = cuerpo[0]
        self.assertEqual(item['cantidad'], 2)
        self.assertEqual(item['ventaGravada'], 200.0)
        self.assertIn('tributos', item)
        iva_t = next((t for t in item['tributos'] if t['codigo'] == '20'), None)
        self.assertIsNotNone(iva_t, 'Debe existir tributo 20 (IVA)')
        self.assertAlmostEqual(iva_t['valor'], 26.0, places=2)

    def test_06_cuerpo_documento_v1_has_no_iva_item(self):
        invoice = self._create_invoice(tipo_dte='01')
        payload = invoice.action_generate_dte_json()
        item = payload['cuerpoDocumento'][0]
        self.assertNotIn('ivaItem', item, 'v1 no debe llevar ivaItem por línea')

    def test_07_cuerpo_documento_v3_has_iva_item(self):
        if not self.iva_13:
            self.skipTest('No se encontró el impuesto IVA 13% mapeado a tributo 20.')
        invoice = self._create_invoice(tipo_dte='03', partner=self.partner)
        payload = invoice.action_generate_dte_json()
        item = payload['cuerpoDocumento'][0]
        self.assertIn('ivaItem', item, 'v3 debe llevar ivaItem por línea')
        self.assertEqual(item['ivaItem']['codigo'], '20')

    def test_08_resumen_v1_uses_iva_perci_field(self):
        if not self.iva_13:
            self.skipTest('No se encontró el impuesto IVA 13% mapeado a tributo 20.')
        invoice = self._create_invoice(cantidad=1, precio=100.0)
        payload = invoice.action_generate_dte_json()
        resumen = payload['resumen']
        self.assertIn('ivaPerci1', resumen)
        self.assertIn('tributos', resumen)
        iva_t = next((t for t in resumen['tributos'] if t['codigo'] == '20'), None)
        self.assertIsNotNone(iva_t)

    def test_09_resumen_v3_uses_iva_array(self):
        if not self.iva_13:
            self.skipTest('No se encontró el impuesto IVA 13% mapeado a tributo 20.')
        invoice = self._create_invoice(tipo_dte='03', partner=self.partner)
        payload = invoice.action_generate_dte_json()
        resumen = payload['resumen']
        self.assertIn('iva', resumen)
        self.assertGreater(len(resumen['iva']), 0)
        iva_item = resumen['iva'][0]['ivaItem']
        self.assertEqual(iva_item['codigo'], '20')

    def test_10_resumen_pagos_contado(self):
        invoice = self._create_invoice(condicion='1', cantidad=1, precio=100.0)
        payload = invoice.action_generate_dte_json()
        resumen = payload['resumen']
        self.assertIn('pagos', resumen)
        self.assertEqual(len(resumen['pagos']), 1)
        self.assertEqual(resumen['pagos'][0]['montoPago'], 113.0)
        self.assertEqual(resumen['pagos'][0]['codigo'], '01')

    def test_11_resumen_total_letras(self):
        invoice = self._create_invoice(cantidad=1, precio=100.0)
        payload = invoice.action_generate_dte_json()
        resumen = payload['resumen']
        self.assertIn('totalLetras', resumen)
        self.assertIn('DÓLARES', resumen['totalLetras'])
        self.assertIn('USD', resumen['totalLetras'])

    def test_12_validate_rejects_ccf_without_nit(self):
        partner_sin_nit = self.env['res.partner'].create({
            'name': 'Sin NIT',
            'l10n_sv_municipio_id': self.municipio.id,
        })
        invoice = self._create_invoice(tipo_dte='03', partner=partner_sin_nit)
        with self.assertRaises(UserError):
            invoice.action_generate_dte_json()

    def test_13_validate_rejects_fcf_without_doc(self):
        partner_sin_doc = self.env['res.partner'].create({
            'name': 'Sin Doc',
            'l10n_sv_municipio_id': self.municipio.id,
        })
        invoice = self._create_invoice(tipo_dte='01', partner=partner_sin_doc)
        with self.assertRaises(UserError):
            invoice.action_generate_dte_json()

    def test_14_extension_added_when_observaciones_set(self):
        invoice = self._create_invoice()
        invoice.write({'l10n_sv_dte_observaciones': 'Cliente retira en tienda'})
        payload = invoice.action_generate_dte_json()
        self.assertIn('extension', payload)
        self.assertEqual(payload['extension']['observaciones'], 'Cliente retira en tienda')

    def test_15_extension_omitted_when_no_observaciones(self):
        invoice = self._create_invoice()
        payload = invoice.action_generate_dte_json()
        self.assertNotIn('extension', payload)

    def test_16_nc_includes_documento_relacionado(self):
        ref_invoice = self._create_invoice(tipo_dte='03', partner=self.partner)
        ref_invoice.action_post()
        ref_invoice._ensure_dte_identifiers()
        ref_invoice.action_generate_dte_json()
        nc = self.env['account.move'].create({
            'move_type': 'out_refund',
            'company_id': self.company.id,
            'partner_id': self.partner.id,
            'invoice_date': '2025-01-20',
            'currency_id': self.env.ref('base.USD').id,
            'reversed_entry_id': ref_invoice.id,
            'invoice_line_ids': [(0, 0, {
                'name': 'Devolución de mercadería',
                'quantity': 1,
                'price_unit': 50.0,
                'tax_ids': [(6, 0, [self.iva_13.id])] if self.iva_13 else [],
            })],
        })
        nc.write({
            'l10n_sv_dte_tipo_doc': '05',
            'l10n_sv_dte_condicion_operacion': '1',
        })
        payload = nc.action_generate_dte_json()
        self.assertIn('documentoRelacionado', payload)
        rel = payload['documentoRelacionado'][0]
        self.assertEqual(rel['numeroDocumento'], ref_invoice.l10n_sv_dte_numero_control)

    def test_17_fcf_does_not_include_documento_relacionado(self):
        invoice = self._create_invoice(tipo_dte='01')
        payload = invoice.action_generate_dte_json()
        self.assertNotIn('documentoRelacionado', payload)

    def test_18_dte_state_advances_to_json_generated(self):
        invoice = self._create_invoice()
        self.assertEqual(invoice.l10n_sv_dte_state, 'draft')
        invoice.action_generate_dte_json()
        self.assertEqual(invoice.l10n_sv_dte_state, 'json_generated')
        self.assertIsNotNone(invoice.l10n_sv_dte_json)

    def test_19_numero_pago_electronico_in_resumen(self):
        invoice = self._create_invoice()
        invoice.write({'l10n_sv_dte_num_pago_electronico': 'REF-12345'})
        payload = invoice.action_generate_dte_json()
        self.assertEqual(payload['resumen'].get('numPagoElectronico'), 'REF-12345')

    def test_20_credito_pagos_split_by_payment_term(self):
        term = self.env['account.payment.term'].create({
            'name': '30/60',
            'line_ids': [
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'days': 30, 'option': 'day_after_invoice_date'}),
                (0, 0, {'value': 'percent', 'value_amount': 50.0, 'days': 60, 'option': 'day_after_invoice_date'}),
            ],
        })
        invoice = self._create_invoice(condicion='2', cantidad=1, precio=100.0)
        invoice.write({'invoice_payment_term_id': term.id})
        payload = invoice.action_generate_dte_json()
        pagos = payload['resumen']['pagos']
        self.assertEqual(len(pagos), 2)
        total_pagos = sum(p['montoPago'] for p in pagos)
        self.assertAlmostEqual(total_pagos, 113.0, places=2)
