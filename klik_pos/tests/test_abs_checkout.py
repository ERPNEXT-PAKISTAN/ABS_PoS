"""Run inside a connected Frappe test site; no invoices or payments are created."""
import unittest
from unittest.mock import Mock, patch
import frappe
from klik_pos.api.checkout import run_checkout
from klik_pos.api.access import require_user, require_profile, validate_checkout
from klik_pos.api.setup import zatca_state


class TestABSCheckout(unittest.TestCase):
	def setUp(self):
		frappe.set_user('Administrator')
		self.profile = frappe._dict(name='ABS Test Counter', company='ABS Test Company', custom_business_type='B2C')
		self.data = {'checkoutRequestId': 'abs-test-request-0001', 'items': [{'id': 'TEST', 'quantity': 1}]}

	def tearDown(self):
		frappe.db.rollback()
		frappe.set_user('Administrator')

	def test_repeated_request_returns_original_response(self):
		create = Mock(return_value={'success': True, 'invoice_name': 'TEST-ONLY'})
		first = run_checkout(self.data, self.profile, create)
		second = run_checkout(dict(self.data), self.profile, create)
		self.assertEqual(first, second)
		create.assert_called_once()

	def test_same_request_cannot_change_cart(self):
		run_checkout(self.data, self.profile, Mock(return_value={'success': True}))
		with self.assertRaises(frappe.ValidationError):
			run_checkout({**self.data, 'amountPaid': 999}, self.profile, Mock())

	def test_failed_request_can_be_retried(self):
		create = Mock(side_effect=[{'success': False}, {'success': True}])
		self.assertFalse(run_checkout(self.data, self.profile, create)['success'])
		self.assertTrue(run_checkout(self.data, self.profile, create)['success'])
		self.assertEqual(create.call_count, 2)

	def test_missing_id_does_not_run_checkout(self):
		create = Mock()
		with self.assertRaises(frappe.ValidationError):
			run_checkout({}, self.profile, create)
		create.assert_not_called()

	def test_guest_cannot_access_pos(self):
		frappe.set_user('Guest')
		with self.assertRaises(frappe.PermissionError):
			require_user()

	def test_unassigned_profile_is_denied(self):
		profile = Mock(disabled=0, applicable_for_users=[])
		with patch('klik_pos.api.access.require_user'), patch('klik_pos.api.access.is_manager', return_value=False), patch.object(frappe, 'get_doc', return_value=profile):
			with self.assertRaises(frappe.PermissionError):
				require_profile('UNASSIGNED')

	def test_zatca_not_installed_is_supported(self):
		with patch.object(frappe, 'get_installed_apps', return_value=['frappe', 'erpnext', 'klik_pos']), patch.object(frappe, 'get_meta', return_value=Mock(has_field=Mock(return_value=False))):
			self.assertEqual(zatca_state('Company')['state'], 'Not installed')

	def test_stale_enabled_flag_is_not_silently_disabled(self):
		with patch.object(frappe, 'get_installed_apps', return_value=['frappe', 'erpnext']), patch.object(frappe, 'get_meta', return_value=Mock(has_field=Mock(return_value=True))), patch.object(frappe.db, 'get_value', return_value=1):
			self.assertEqual(zatca_state('Company')['state'], 'Unavailable')

	def test_installed_disabled_and_enabled_states(self):
		with patch.object(frappe, 'get_installed_apps', return_value=['frappe', 'erpnext', 'zatca_integration']), patch.object(frappe, 'get_meta', return_value=Mock(has_field=Mock(return_value=True))), patch.object(frappe.db, 'get_value', return_value=0):
			self.assertEqual(zatca_state('Company')['state'], 'Disabled')
		with patch.object(frappe, 'get_installed_apps', return_value=['zatca_integration']), patch.object(frappe, 'get_meta', return_value=Mock(has_field=Mock(return_value=True))), patch.object(frappe.db, 'get_value', return_value=1):
			self.assertEqual(zatca_state('Company')['state'], 'Enabled')

	def test_item_lookup_binds_untrusted_codes(self):
		from klik_pos.api.sales_invoice import _batch_fetch_item_data
		code = "quote' OR 1=1 --"
		with patch.object(frappe.db, 'sql', return_value=[]) as sql:
			_batch_fetch_item_data([code])
			query, values = sql.call_args.args
			self.assertNotIn(code, query)
			self.assertEqual(values, (code,))

	def test_checkout_rejects_unconfigured_payment_mode(self):
		profile = frappe._dict(name='Counter', custom_business_type='B2C', payments=[frappe._dict(mode_of_payment='Cash')], allow_discount_change=0, write_off_limit=0)
		with patch('klik_pos.api.access.require_profile'), patch.object(frappe, 'has_permission', return_value=True), patch('klik_pos.api.sales_invoice.get_current_pos_opening_entry', return_value='OPEN'), patch.object(frappe.db, 'get_value', return_value='Counter'):
			with self.assertRaises(frappe.ValidationError):
				validate_checkout({'items': [{'quantity': 1}], 'paymentMethods': [{'method': 'Unapproved', 'amount': 10}]}, profile)

	def test_checkout_rejects_disabled_manual_discount(self):
		profile = frappe._dict(name='Counter', custom_business_type='B2C', payments=[], allow_discount_change=0, write_off_limit=0)
		with patch('klik_pos.api.access.require_profile'), patch.object(frappe, 'has_permission', return_value=True), patch('klik_pos.api.sales_invoice.get_current_pos_opening_entry', return_value='OPEN'), patch.object(frappe.db, 'get_value', return_value='Counter'):
			with self.assertRaises(frappe.ValidationError):
				validate_checkout({'items': [{'quantity': 1, 'discountPercentage': 10}]}, profile)

	def test_checkout_rejects_missing_shift(self):
		with patch('klik_pos.api.access.require_profile'), patch.object(frappe, 'has_permission', return_value=True), patch('klik_pos.api.sales_invoice.get_current_pos_opening_entry', return_value=None):
			with self.assertRaises(frappe.ValidationError):
				validate_checkout({'items': [{'quantity': 1}]}, self.profile)

	def test_business_mode_is_server_controlled(self):
		from klik_pos.api.sales_invoice import parse_invoice_data
		profile = frappe._dict(taxes_and_charges='TAX', custom_business_type='B2C')
		with patch('klik_pos.api.sales_invoice._get_active_pos_profile', return_value=profile):
			parsed = parse_invoice_data({'customer': {'id': 'TEST'}, 'items': [{'quantity': 1}], 'businessType': 'B2B'})
			self.assertEqual(parsed[5], 'B2C')

	def test_collected_amount_is_derived_from_payment_rows(self):
		from klik_pos.api.sales_invoice import parse_invoice_data
		profile = frappe._dict(taxes_and_charges='TAX', custom_business_type='B2C')
		with patch('klik_pos.api.sales_invoice._get_active_pos_profile', return_value=profile):
			parsed = parse_invoice_data({'customer': {'id': 'TEST'}, 'items': [{'quantity': 1}], 'amountPaid': 999, 'paymentMethods': [{'method': 'Cash', 'amount': 12}]})
			self.assertEqual(parsed[2], 12)

	def test_counter_switch_cannot_retarget_pending_checkout(self):
		from klik_pos.api.sales_invoice import create_and_submit_invoice
		with patch('klik_pos.api.sales_invoice._get_active_pos_profile', return_value=self.profile), patch('klik_pos.api.checkout.run_checkout', side_effect=lambda data, profile, create: create(data)), patch('klik_pos.api.sales_invoice._create_and_submit_invoice') as create:
			with self.assertRaises(frappe.ValidationError):
				create_and_submit_invoice({'checkoutProfile': 'Another Counter'})
			create.assert_not_called()
