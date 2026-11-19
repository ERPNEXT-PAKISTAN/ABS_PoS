"""Markup, normalization and guarded native-price writes. No business prices changed."""
import unittest
from types import SimpleNamespace
from decimal import Decimal
from unittest.mock import Mock, patch
import frappe
from klik_pos.api.item_pricing import calculate_price, summarize_purchases, number, preview_item_price, save_item_price, context


class TestItemPricing(unittest.TestCase):
	def test_thirty_percent_is_markup_not_margin(self):
		q=calculate_price('100','30')
		self.assertEqual(q['net_selling_price'],'130')
		self.assertAlmostEqual(float(q['gross_margin_percentage']),23.076923,places=5)

	def test_inclusive_vat_uses_rounded_gross_price(self):
		q=calculate_price('100','30',inclusive_rate='15')
		self.assertEqual(q['net_selling_price'],'130.43')
		self.assertEqual(q['selling_price'],'150')
		self.assertEqual(q['tax_amount'],'19.57')

	def test_pack_conversion_is_applied_before_markup(self):
		q=calculate_price('10','30',factor='12')
		self.assertEqual(q['unit_cost'],'120')
		self.assertEqual(q['net_selling_price'],'156')

	def test_currency_rounding_is_decimal_half_up(self):
		self.assertEqual(calculate_price('1.5',0)['net_selling_price'],'2')

	def test_effective_margin_reflects_rounded_price(self):
		q=calculate_price('1.2','30')
		self.assertEqual(q['net_selling_price'],'2')
		self.assertEqual(Decimal(q['gross_margin_percentage']),Decimal('40'))

	def test_invalid_values_are_rejected(self):
		for value in ['-1','NaN','Infinity','text','']:
			with self.subTest(value=value),self.assertRaises(frappe.ValidationError):number(value)

	def test_weighted_average_uses_base_amounts_and_stock_quantities(self):
		latest=SimpleNamespace(name='NEW',modified='m1',posting_date='2026-11-16',items=[frappe._dict(item_code='ITEM',stock_qty=10,base_net_amount=200,rate=999,currency='USD')])
		older=SimpleNamespace(name='OLD',modified='m2',posting_date='2026-11-15',items=[frappe._dict(item_code='ITEM',stock_qty=20,base_net_amount=200)])
		r=summarize_purchases([latest,older],'ITEM')
		self.assertEqual(Decimal(r['latest']['cost']),20)
		self.assertEqual(Decimal(r['weighted_average']),Decimal(400)/30)
		self.assertEqual(r['stock_quantity'],'30')

	def test_latest_invoice_combines_matching_lines_without_mixing_items(self):
		doc=SimpleNamespace(name='NEW',modified='m1',posting_date='2026-11-16',items=[frappe._dict(item_code='ITEM',stock_qty=12,base_net_amount=120),frappe._dict(item_code='ITEM',stock_qty=2,base_net_amount=40),frappe._dict(item_code='OTHER',stock_qty=1000,base_net_amount=99999),frappe._dict(item_code='ITEM',stock_qty=-1,base_net_amount=-999)])
		r=summarize_purchases([doc],'ITEM')
		self.assertEqual(Decimal(r['latest']['cost']),Decimal(160)/14)
		self.assertEqual(r['invoice_count'],1)

	def test_no_purchase_cost_is_not_invented(self):
		r=summarize_purchases([],'ITEM');self.assertIsNone(r['latest']);self.assertIsNone(r['weighted_average'])

	def test_no_purchase_permission_stops_cost_lookup(self):
		with patch('klik_pos.api.item_pricing.require_user'),patch('klik_pos.api.item_pricing.can_view',return_value=False),patch.object(frappe,'get_list') as query:
			with self.assertRaises(frappe.PermissionError):context('ITEM')
			# frappe.throw() may load translations through frappe.get_list; no cost query may run.
			self.assertFalse(any(call.args and call.args[0] == 'Purchase Invoice' for call in query.call_args_list))

	def test_manual_quote_is_recomputed_on_server(self):
		c={'factor':'1','profile':'P','currency':'SAR','uom':'Nos','price_list':'PL','current_price':None,'purchases':{'versions':[]},'tax':{'inclusive':False,'supported':True,'rate':None},'policy':None,'can_save':True,'blockers':[]}
		with patch('klik_pos.api.item_pricing.context',return_value=c):
			r=preview_item_price('ITEM',cost_basis='Manual',manual_cost='100',markup_percentage='30')
			self.assertEqual(r['quote']['selling_price'],'130');self.assertTrue(r['quote']['snapshot'])

	def test_non_manager_cannot_save(self):
		with patch('klik_pos.api.item_pricing.require_user'),patch('klik_pos.api.item_pricing.is_manager',return_value=False),patch('klik_pos.api.item_pricing.context') as lookup:
			with self.assertRaises(frappe.PermissionError):save_item_price('ITEM','token')
			lookup.assert_not_called()

	def test_stale_quote_does_not_write_any_price(self):
		c={'can_save':True,'price_list':'PL','current_price':None,'quote':{'snapshot':'NEW'}}
		with patch('klik_pos.api.item_pricing.require_user'),patch('klik_pos.api.item_pricing.is_manager',return_value=True),patch('klik_pos.api.item_pricing.context',return_value=c),patch('klik_pos.api.item_pricing.preview_item_price',return_value=c),patch.object(frappe.db,'sql'),patch.object(frappe,'get_doc') as docs:
			with self.assertRaises(frappe.ValidationError):save_item_price('ITEM','OLD')
			docs.assert_not_called()

	def test_saving_uses_native_price_and_policy_permissions(self):
		c={'can_save':True,'price_list':'PL','current_price':{'name':'PRICE'},'quote':{'snapshot':'TOKEN','selling_price':'130.00'},'company':'COMPANY','currency':'SAR','uom':'Nos','policy_key':'POLICY'}
		price=Mock();price.name='PRICE';policy=Mock();policy.is_new.return_value=False
		with patch('klik_pos.api.item_pricing.require_user'),patch('klik_pos.api.item_pricing.is_manager',return_value=True),patch('klik_pos.api.item_pricing.context',return_value=c),patch('klik_pos.api.item_pricing.preview_item_price',return_value=c),patch.object(frappe.db,'sql'),patch.object(frappe.db,'exists',return_value=True),patch.object(frappe,'get_doc',side_effect=lambda dt,name: price if dt=='Item Price' else policy):
			r=save_item_price('ITEM','TOKEN')
			self.assertEqual(price.price_list_rate,'130.00');price.check_permission.assert_called_with('write');price.save.assert_called_once_with();policy.save.assert_called_once_with();self.assertEqual(r['item_price'],'PRICE')

	def test_cost_query_is_company_scoped_non_return_distinct_and_limited(self):
		profile=frappe._dict(name='POS',company='COMPANY',selling_price_list=None,taxes_and_charges=None)
		item=Mock();item.name='ITEM';item.item_name='Item';item.stock_uom='Nos';item.uoms=[];item.has_variants=0
		with patch('klik_pos.api.item_pricing.require_user'),patch('klik_pos.api.item_pricing.can_view',return_value=True),patch('klik_pos.api.item_pricing.get_permitted_fields',return_value=['item_code','stock_qty','base_net_amount']),patch('klik_pos.api.sales_invoice._get_active_pos_profile',return_value=profile),patch.object(frappe,'get_doc',return_value=item),patch.object(frappe.db,'get_value',return_value='SAR'),patch.object(frappe,'has_permission',return_value=False),patch.object(frappe,'get_list',return_value=[]) as query:
			r=context('ITEM')
			filters=query.call_args.kwargs['filters']
			self.assertIn(['Purchase Invoice','company','=','COMPANY'],filters)
			self.assertIn(['Purchase Invoice','docstatus','=',1],filters)
			self.assertIn(['Purchase Invoice','is_return','=',0],filters)
			self.assertIn(['Purchase Invoice Item','stock_qty','>',0],filters)
			self.assertEqual(query.call_args.kwargs['limit_page_length'],8)
			self.assertTrue(query.call_args.kwargs['distinct']);self.assertIsNone(r['purchases']['weighted_average'])

	def test_hidden_purchase_cost_fields_cannot_be_derived(self):
		with patch('klik_pos.api.item_pricing.require_user'),patch('klik_pos.api.item_pricing.can_view',return_value=True),patch('klik_pos.api.item_pricing.get_permitted_fields',return_value=['stock_qty']),patch.object(frappe,'get_list') as query:
			with self.assertRaises(frappe.PermissionError):context('ITEM')
			query.assert_not_called()

	def test_new_price_creation_and_policy_use_native_insert(self):
		c={'can_save':True,'price_list':'PL','current_price':None,'quote':{'snapshot':'TOKEN','selling_price':'130.00'},'company':'COMPANY','currency':'SAR','uom':'Box','policy_key':'POLICY'}
		price=Mock();price.name='NEW PRICE';policy=Mock();policy.is_new.return_value=True
		with patch('klik_pos.api.item_pricing.require_user'),patch('klik_pos.api.item_pricing.is_manager',return_value=True),patch('klik_pos.api.item_pricing.context',return_value=c),patch('klik_pos.api.item_pricing.preview_item_price',return_value=c),patch.object(frappe.db,'sql'),patch.object(frappe.db,'exists',return_value=False),patch.object(frappe,'new_doc',side_effect=lambda dt: price if dt=='Item Price' else policy):
			save_item_price('ITEM','TOKEN')
			self.assertEqual(price.item_code,'ITEM');self.assertEqual(price.uom,'Box');self.assertEqual(price.price_list,'PL')
			price.save.assert_called_once_with();policy.insert.assert_called_once_with(set_name='POLICY')

	def test_single_inclusive_tax_is_detected(self):
		from klik_pos.api.item_pricing import tax_context
		template=Mock();template.company='C';template.get.return_value=False
		template.taxes=[frappe._dict(included_in_print_rate=1,charge_type='On Net Total',rate=15)]
		item=Mock();item.get.return_value=[]
		with patch.object(frappe,'get_doc',return_value=template):
			r=tax_context(frappe._dict(taxes_and_charges='TAX',company='C'),item)
			self.assertTrue(r['supported']);self.assertTrue(r['inclusive']);self.assertEqual(r['rate'],'15')

	def test_item_specific_inclusive_tax_requires_native_review(self):
		from klik_pos.api.item_pricing import tax_context
		template=Mock();template.company='C';template.get.return_value=False
		template.taxes=[frappe._dict(included_in_print_rate=1,charge_type='On Net Total',rate=15)]
		item=Mock();item.get.return_value=['ITEM TAX']
		with patch.object(frappe,'get_doc',return_value=template):
			self.assertFalse(tax_context(frappe._dict(taxes_and_charges='TAX',company='C'),item)['supported'])

	def test_compound_inclusive_tax_requires_native_review(self):
		from klik_pos.api.item_pricing import tax_context
		template=Mock();template.company='C';template.get.return_value=False
		template.taxes=[frappe._dict(included_in_print_rate=1,charge_type='On Net Total',rate=15),frappe._dict(included_in_print_rate=0,charge_type='Actual',rate=0)]
		item=Mock();item.get.return_value=[]
		with patch.object(frappe,'get_doc',return_value=template):
			self.assertFalse(tax_context(frappe._dict(taxes_and_charges='TAX',company='C'),item)['supported'])
