import re
import uuid

from odoo.tests import tagged

from .common import L10nSvDteTestBase, TEST_COD_ESTABLE, TEST_COD_PUNTO_VENTA


@tagged('post_install', '-at_install', 'l10n_sv_dte', 'l10n_sv_dte_ids')
class TestL10nSvNumeroControl(L10nSvDteTestBase):

    def test_01_codigo_generacion_is_valid_uuid(self):
        invoice = self._create_invoice()
        invoice._ensure_dte_identifiers()
        uuid_value = invoice.l10n_sv_dte_codigo_generacion
        self.assertIsNotNone(uuid_value)
        parsed = uuid.UUID(uuid_value)
        self.assertEqual(str(parsed), uuid_value)

    def test_02_codigo_generacion_is_unique(self):
        inv1 = self._create_invoice()
        inv2 = self._create_invoice()
        inv1._ensure_dte_identifiers()
        inv2._ensure_dte_identifiers()
        self.assertNotEqual(
            inv1.l10n_sv_dte_codigo_generacion,
            inv2.l10n_sv_dte_codigo_generacion,
        )

    def test_03_codigo_generacion_is_stable_across_calls(self):
        invoice = self._create_invoice()
        invoice._ensure_dte_identifiers()
        original = invoice.l10n_sv_dte_codigo_generacion
        invoice._ensure_dte_identifiers()
        self.assertEqual(invoice.l10n_sv_dte_codigo_generacion, original)

    def test_04_numero_control_format_fcf(self):
        invoice = self._create_invoice(tipo_dte='01')
        invoice._ensure_dte_identifiers()
        nc = invoice.l10n_sv_dte_numero_control
        self.assertTrue(nc.startswith('DTE-01-'), 'NC debe iniciar con DTE-01-')
        self.assertIn(TEST_COD_ESTABLE + TEST_COD_PUNTO_VENTA, nc)
        pattern = r'^DTE-01-\d{8}-[A-Z0-9]{17}$'
        self.assertRegex(nc, pattern, 'NC debe coincidir con el formato esperado: %s' % pattern)

    def test_05_numero_control_format_ccf(self):
        invoice = self._create_invoice(tipo_dte='03', partner=self.partner)
        invoice._ensure_dte_identifiers()
        nc = invoice.l10n_sv_dte_numero_control
        self.assertTrue(nc.startswith('DTE-03-'))
        pattern = r'^DTE-03-\d{8}-[A-Z0-9]{17}$'
        self.assertRegex(nc, pattern)

    def test_06_numero_control_uses_company_cod_estable(self):
        self.company.write({'l10n_sv_cod_estable_mh': '0002', 'l10n_sv_cod_punto_venta_mh': '0005'})
        invoice = self._create_invoice()
        invoice._ensure_dte_identifiers()
        self.assertIn('00020005', invoice.l10n_sv_dte_numero_control)

    def test_07_numero_control_uses_defaults_when_company_blank(self):
        self.company.write({'l10n_sv_cod_estable_mh': False, 'l10n_sv_cod_punto_venta_mh': False})
        invoice = self._create_invoice()
        invoice._ensure_dte_identifiers()
        self.assertIn('00010001', invoice.l10n_sv_dte_numero_control)

    def test_08_generate_codigo_generacion_uppercase(self):
        for _ in range(20):
            code = self.env['account.move']._generate_codigo_generacion()
            self.assertEqual(code, code.upper())

    def test_09_generate_numero_control_returns_string(self):
        nc = self.env['account.move']._generate_numero_control('01')
        self.assertIsInstance(nc, str)
        self.assertTrue(re.match(r'^DTE-01-\d{8}-[A-Z0-9]{17}$', nc))
