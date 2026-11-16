"""Read-only history contract tests; no invoice, payment or stock documents created."""
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
import frappe
from klik_pos.api.item_history import get_item_history, can_view


class TestItemHistory(unittest.TestCase):
	def setUp(self):
		self.stack = ExitStack()
		self.addCleanup(self.stack.close)
		self.stack.enter_context(patch('klik_pos.api.item_history.require_user'))
		self.stack.enter_context(patch('klik_pos.api.sales_invoice._get_active_pos_profile', return_value=frappe._dict(name='COUNTER', company='COMPANY A')))
		self.permissions = self.stack.enter_context(patch('klik_pos.api.item_history.can_view', return_value=True))
		self.fields = self.stack.enter_context(patch('klik_pos.api.item_history.get_permitted_fields', return_value=['qty', 'uom', 'net_rate', 'net_amount']))
		self.query = self.stack.enter_context(patch.object(frappe, 'get_list', return_value=[]))
		self.item = Mock(name='Item'); self.item.name = "ITEM'QUOTED";self.item.item_name='Item'
		self.invoice = Mock();self.invoice.items=[]
		self.docs = self.stack.enter_context(patch.object(frappe,'get_doc',side_effect=lambda dt,name: self.item if dt=='Item' else self.invoice))

	def test_limit_and_scope_are_enforced_by_parent_query(self):
		get_item_history(self.item.name)
		args = self.query.call_args
		self.assertEqual(args.args[0], 'Sales Invoice')
		self.assertEqual(args.kwargs['limit_page_length'],8)
		self.assertTrue(args.kwargs['distinct'])
		self.assertIn(['Sales Invoice','company','=','COMPANY A'],args.kwargs['filters'])
		self.assertIn(['Sales Invoice','docstatus','=',1],args.kwargs['filters'])
		self.assertIn(['Sales Invoice Item','item_code','=',self.item.name],args.kwargs['filters'])
		self.assertEqual(args.kwargs['order_by'],'posting_date desc, posting_time desc, creation desc, name desc')

	def test_purchase_uses_purchase_documents(self):
		get_item_history(self.item.name,'purchases')
		self.assertEqual(self.query.call_args.args[0],'Purchase Invoice')
		self.assertIn(['Purchase Invoice Item','item_code','=',self.item.name], self.query.call_args.kwargs['filters'])

	def test_customer_filter_is_explicit(self):
		get_item_history(self.item.name,'customer_sales','CUSTOMER A')
		self.assertIn(['Sales Invoice','customer','=','CUSTOMER A'],self.query.call_args.kwargs['filters'])
		self.docs.assert_any_call('Customer','CUSTOMER A')

	def test_missing_customer_does_not_fall_back_to_all_sales(self):
		with self.assertRaises(frappe.ValidationError):get_item_history(self.item.name,'customer_sales')
		self.query.assert_not_called()

	def test_denied_purchase_does_not_query_costs(self):
		self.permissions.side_effect=lambda dt:dt!='Purchase Invoice'
		with self.assertRaises(frappe.PermissionError):get_item_history(self.item.name,'purchases')
		self.query.assert_not_called()

	def test_access_check_does_not_load_invoices(self):
		r=get_item_history(self.item.name,'access')
		self.assertTrue(r['permissions']['sales']);self.query.assert_not_called()

	def test_invalid_view_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):get_item_history(self.item.name,'arbitrary table')
		self.query.assert_not_called()

	def test_repeated_item_lines_and_returns_are_preserved(self):
		self.query.return_value=[frappe._dict(name='INV',posting_date='2026-11-16',posting_time='12:00:00',currency='SAR',is_return=1,customer='CUSTOMER A',customer_name='Customer')]
		self.invoice.items=[frappe._dict(item_code=self.item.name,qty=-1,uom='Box',net_rate=20,net_amount=-20),frappe._dict(item_code=self.item.name,qty=-2,uom='Nos',net_rate=3,net_amount=-6),frappe._dict(item_code='OTHER',qty=999)]
		r=get_item_history(self.item.name)
		self.assertEqual(len(r['transactions']),1)
		tx=r['transactions'][0];self.assertTrue(tx['is_return'])
		self.assertEqual([line['uom'] for line in tx['lines']],['Box','Nos'])
		self.assertEqual([line['net_amount'] for line in tx['lines']],[-20,-6])
		self.invoice.check_permission.assert_called_with('read')

	def test_restricted_price_fields_are_redacted(self):
		self.fields.return_value=['qty','uom']
		self.query.return_value=[frappe._dict(name='INV')]
		self.invoice.items=[frappe._dict(item_code=self.item.name,qty=1,uom='Nos',net_rate=99,net_amount=99)]
		line=get_item_history(self.item.name)['transactions'][0]['lines'][0]
		self.assertEqual(line['qty'],1);self.assertIsNone(line['net_rate']);self.assertIsNone(line['net_amount'])

	def test_report_permission_is_required_as_well_as_read(self):
		# Test the real permission helper outside the patched get_item_history dependency.
		with patch.object(frappe,'has_permission',side_effect=lambda dt,ptype:ptype=='read'):
			self.assertFalse(can_view('Purchase Invoice'))
