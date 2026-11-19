"""Purchase-cost markup calculator. Only explicit, authorized POSTs save prices."""
import hashlib
import json
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.utils import getdate, today
from klik_pos.api.access import require_user, is_manager
from klik_pos.api.item_history import can_view

BASES = ('Latest purchase', 'Weighted average', 'Manual')


def number(value, label='Value'):
	try:
		result = Decimal(str(value))
		if not result.is_finite() or result < 0 or result > Decimal('1000000000000'):
			raise ValueError()
		return result
	except (InvalidOperation, ValueError, TypeError):
		frappe.throw(_('{0} must be a finite, non-negative number.').format(label))


def calculate_price(cost, percentage, factor=1, inclusive_rate=None):
	cost, percentage, factor = number(cost, 'Cost'), number(percentage, 'Markup'), number(factor, 'UOM factor')
	if factor <= 0:
		frappe.throw(_('UOM conversion factor must be positive.'))
	net_cost = cost * factor
	raw_net_price = net_cost * (1 + percentage / 100)
	if raw_net_price >= Decimal('1000000000000'):
		frappe.throw(_('Calculated selling price is too large.'))
	rate = number(inclusive_rate or 0, 'Tax rate')
	raw_stored = raw_net_price * (1 + rate / 100)
	if raw_stored >= Decimal('1000000000000'):
		frappe.throw(_('Calculated selling price is too large.'))
	stored = raw_stored.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
	# For tax-inclusive prices, derive the net value from the actual rounded price.
	net_price = (stored / (1 + rate / 100)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP) if rate else stored
	if stored >= Decimal('1000000000000'):
		frappe.throw(_('Calculated selling price is too large.'))
	return {'unit_cost': str(net_cost), 'net_selling_price': str(net_price), 'tax_amount': str(stored-net_price),
		'selling_price': str(stored), 'markup_amount': str(net_price-net_cost),
		'gross_margin_percentage': str((net_price-net_cost) / net_price * 100 if net_price else Decimal(0))}


def summarize_purchases(invoices, item_code):
	"""Historical base net amounts / positive stock quantities; never mix pack sizes or FX."""
	total_amount = Decimal(0)
	total_qty = Decimal(0)
	latest = None
	versions = []
	count = 0
	for doc in invoices:
		amount = Decimal(0)
		quantity = Decimal(0)
		for row in doc.items:
			if row.item_code != item_code or Decimal(str(row.stock_qty or 0)) <= 0:
				continue
			amount += number(row.base_net_amount, 'Purchase net amount')
			quantity += number(row.stock_qty, 'Purchase stock quantity')
		if not quantity:
			continue
		count += 1
		versions.append([doc.name, str(doc.modified)])
		if latest is None:
			latest = {'cost': str(amount / quantity), 'invoice': doc.name, 'date': str(doc.posting_date)}
		total_amount += amount
		total_qty += quantity
	return {'latest': latest, 'weighted_average': str(total_amount / total_qty) if total_qty else None,
		'invoice_count': count, 'stock_quantity': str(total_qty), 'versions': versions}


def tax_context(profile, item):
	if not profile.taxes_and_charges:
		return {'inclusive': False, 'rate': None, 'supported': True, 'message': ''}
	template = frappe.get_doc('Sales Taxes and Charges Template', profile.taxes_and_charges)
	template.check_permission('read')
	if template.get('disabled') or template.company != profile.company:
		return {'inclusive': False, 'rate': None, 'supported': False, 'message': _('Review the disabled or mismatched tax template on this POS Profile before saving a price.')}
	included = [row for row in template.taxes if row.included_in_print_rate]
	if not included:
		return {'inclusive': False, 'rate': None, 'supported': True, 'message': ''}
	if len(template.taxes) == 1 and included[0].charge_type == 'On Net Total' and not item.get('taxes'):
		return {'inclusive': True, 'rate': str(included[0].rate), 'supported': True, 'message': ''}
	return {'inclusive': True, 'rate': None, 'supported': False,
		'message': _('This counter uses compound or item-specific inclusive tax. Preview the net target here and set its final price using the native Item Price form.')}


def policy_key(company, item, price_list, uom):
	return hashlib.sha256('\0'.join([company, item, price_list or '', uom]).encode()).hexdigest()


def context(item_code, uom=None):
	require_user()
	if not isinstance(item_code,str) or not item_code.strip() or len(item_code)>140:
		frappe.throw(_('A valid item code is required.'))
	if uom and (not isinstance(uom,str) or len(uom)>140):
		frappe.throw(_('A valid UOM is required.'))
	if not can_view('Purchase Invoice'):
		frappe.throw(_('Purchase Invoice read and report permissions are required for purchase-based pricing.'), frappe.PermissionError)
	needed = {'stock_qty', 'base_net_amount', 'item_code'}
	if not needed.issubset(set(get_permitted_fields('Purchase Invoice Item', parenttype='Purchase Invoice', permission_type='read'))):
		frappe.throw(_('You do not have access to purchase cost fields.'), frappe.PermissionError)
	from klik_pos.api.sales_invoice import _get_active_pos_profile
	profile = _get_active_pos_profile()
	item = frappe.get_doc('Item', item_code)
	item.check_permission('read')
	currency = frappe.db.get_value('Company', profile.company, 'default_currency')
	uoms = {item.stock_uom: Decimal(1)}
	for row in item.uoms:
		if row.uom != item.stock_uom and row.conversion_factor and Decimal(str(row.conversion_factor)) > 0:
			uoms[row.uom] = Decimal(str(row.conversion_factor))
	uom = uom or item.stock_uom
	if uom not in uoms:
		frappe.throw(_('Choose a UOM configured on this item.'))
	invoices = frappe.get_list('Purchase Invoice',
		filters=[['Purchase Invoice','company','=',profile.company],['Purchase Invoice','docstatus','=',1],['Purchase Invoice','is_return','=',0],['Purchase Invoice Item','item_code','=',item_code],['Purchase Invoice Item','stock_qty','>',0]],
		fields=['name','posting_date','posting_time','creation'], distinct=True,
		order_by='posting_date desc, posting_time desc, creation desc, name desc', limit_page_length=8)
	docs = []
	for row in invoices:
		doc = frappe.get_doc('Purchase Invoice', row.name)
		doc.check_permission('read')
		docs.append(doc)
	purchases = summarize_purchases(docs, item_code)
	blockers = []
	if item.has_variants:
		blockers.append(_('Choose an item variant rather than its template before saving a price.'))
	price_list = profile.selling_price_list
	price_list_currency = None
	current_price = None
	if not price_list:
		blockers.append(_('Configure a selling price list in the POS Profile.'))
	else:
		pl = frappe.get_doc('Price List', price_list)
		pl.check_permission('read')
		price_list_currency = pl.currency
		if not pl.enabled or not pl.selling or pl.buying:
			blockers.append(_('Saving requires an enabled, selling-only price list.'))
		if pl.currency != currency:
			blockers.append(_('The selling price list currency differs from the company currency. Currency conversion must be reviewed in the native Item Price form.'))
		price_fields = {'customer','supplier','batch_no','uom','packing_unit','price_list_rate','currency','valid_from','valid_upto','modified'}
		if not frappe.has_permission('Item Price','read') or not price_fields.issubset(set(get_permitted_fields('Item Price', permission_type='read'))):
			blockers.append(_('Item Price read permission is required to save a price.'))
		else:
			prices = frappe.get_list('Item Price', filters={'item_code':item_code,'price_list':price_list},
				fields=['name','uom','customer','supplier','batch_no','packing_unit','price_list_rate','currency','valid_from','valid_upto','modified'], limit_page_length=201)
			generic = [p for p in prices if not p.customer and not p.supplier and not p.batch_no and p.uom == uom and p.packing_unit in (None,0,1)]
			date = getdate(today())
			active = [p for p in generic if (not p.valid_from or getdate(p.valid_from)<=date) and (not p.valid_upto or getdate(p.valid_upto)>=date)]
			if len(prices)>200 or len(active)>1:
				blockers.append(_('Multiple or excessive price variants exist. Resolve them in Item Price before saving here.'))
			elif active:
				current_price = dict(active[0])
			elif any(p.valid_from and getdate(p.valid_from)>date for p in generic):
				blockers.append(_('A future-dated price exists. Review its effective dates in Item Price.'))
			elif uom == item.stock_uom and any(not p.uom and not p.customer and not p.supplier and not p.batch_no for p in prices):
				blockers.append(_('An existing generic price has no UOM. Set its UOM in Item Price before saving here.'))
	tax = tax_context(profile, item)
	if not tax['supported']:
		blockers.append(tax['message'])
	key = policy_key(profile.company, item_code, price_list, uom)
	policy = None
	if frappe.has_permission('ABS Item Pricing Policy','read') and frappe.db.exists('ABS Item Pricing Policy',key):
		p = frappe.get_doc('ABS Item Pricing Policy',key);p.check_permission('read')
		policy = {k:p.get(k) for k in ['markup_percentage','cost_basis','manual_cost','modified']}
	item_price_permission = 'write' if current_price else 'create'
	can_save = bool(is_manager() and frappe.has_permission('ABS Item Pricing Policy','write') and frappe.has_permission('ABS Item Pricing Policy','create') and frappe.has_permission('Item Price',item_price_permission) and not blockers)
	return {'item_code':item.name,'item_name':item.item_name,'company':profile.company,'profile':profile.name,'currency':currency,'stock_uom':item.stock_uom,
		'uoms':[{'uom':name,'factor':str(factor)} for name,factor in uoms.items()], 'uom':uom,'factor':str(uoms[uom]),
		'purchases':purchases,'price_list':price_list,'price_list_currency':price_list_currency,'current_price':current_price,
		'tax':tax,'policy':policy,'can_save':can_save,'blockers':blockers,'policy_key':key}


@frappe.whitelist()
def get_item_pricing(item_code, uom=None):
	return context(item_code, uom)


@frappe.whitelist()
def preview_item_price(item_code, uom=None, cost_basis='Latest purchase', markup_percentage=30, manual_cost=0):
	if cost_basis not in BASES:
		frappe.throw(_('Choose a valid purchase cost basis.'))
	c = context(item_code,uom)
	percentage = number(markup_percentage, 'Markup')
	manual = number(manual_cost,'Manual cost')
	cost = manual if cost_basis=='Manual' else c['purchases']['weighted_average'] if cost_basis=='Weighted average' else (c['purchases']['latest'] or {}).get('cost')
	if cost is None:
		c['quote'] = None
		return c
	quote = calculate_price(cost,percentage,c['factor'],c['tax']['rate'] if c['tax']['inclusive'] and c['tax']['supported'] else None)
	snapshot = {'profile':c['profile'],'currency':c['currency'],'uom':c['uom'],'factor':c['factor'],'price_list':c['price_list'],
		'current_price':c['current_price'],'purchase_versions':c['purchases']['versions'],'cost':str(cost),'basis':cost_basis,
		'percentage':str(percentage),'manual_cost':str(manual),'tax':c['tax'],'policy':c['policy']}
	quote['snapshot'] = hashlib.sha256(json.dumps(snapshot,sort_keys=True,default=str).encode()).hexdigest()
	if number(quote['selling_price'])<=0:
		c['can_save'] = False;c['blockers'].append(_('A positive cost and selling price are required to save.'))
	c['quote'] = quote
	return c


@frappe.whitelist(methods=['POST'])
def save_item_price(item_code, snapshot, uom=None, cost_basis='Latest purchase', markup_percentage=30, manual_cost=0):
	require_user()
	if not is_manager():
		frappe.throw(_('Only a System Manager can save purchase-based selling prices.'),frappe.PermissionError)
	c = context(item_code,uom)
	if not c['can_save']:
		frappe.throw(_('Price cannot be saved: {0}').format('; '.join(c['blockers']) or _('check Item Price and pricing policy permissions.')))
	# Serialize calculator updates, including the first price for an item/UOM.
	frappe.db.sql('SELECT name FROM `tabPrice List` WHERE name=%s FOR UPDATE',c['price_list'])
	if c['current_price']:
		frappe.db.sql('SELECT name FROM `tabItem Price` WHERE name=%s FOR UPDATE',c['current_price']['name'])
	c = preview_item_price(item_code,uom,cost_basis,markup_percentage,manual_cost)
	if not c['can_save'] or not c['quote'] or snapshot != c['quote']['snapshot']:
		frappe.throw(_('Pricing or purchase costs changed. Refresh the calculator and review the new price before saving.'))
	if c['current_price']:
		doc = frappe.get_doc('Item Price',c['current_price']['name'])
		doc.check_permission('write')
	else:
		doc = frappe.new_doc('Item Price')
		doc.item_code = item_code;doc.price_list = c['price_list'];doc.uom = c['uom'];doc.valid_from = today()
	doc.price_list_rate = c['quote']['selling_price']
	doc.save()
	p = frappe.get_doc('ABS Item Pricing Policy',c['policy_key']) if frappe.db.exists('ABS Item Pricing Policy',c['policy_key']) else frappe.new_doc('ABS Item Pricing Policy')
	p.update({'company':c['company'],'item':item_code,'price_list':c['price_list'],'uom':c['uom'],
		'markup_percentage':number(markup_percentage),'cost_basis':cost_basis,'manual_cost':number(manual_cost),
		'company_currency':c['currency'],'saved_price':c['quote']['selling_price'],'item_price':doc.name})
	if p.is_new():p.insert(set_name=c['policy_key'])
	else:p.save()
	return {'item_price':doc.name,'price_list':c['price_list'],'uom':c['uom'],'currency':c['currency'],'selling_price':c['quote']['selling_price'],'pricing':preview_item_price(item_code,uom,cost_basis,markup_percentage,manual_cost)}
