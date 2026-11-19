"""Read-only invoice history, scoped to the active POS company and native permissions."""
import math
import frappe
from frappe import _
from frappe.model import get_permitted_fields
from klik_pos.api.access import require_user

SOURCES = {
	'sales': ('Sales Invoice', 'Sales Invoice Item', 'customer', 'customer_name', 'sales-invoice'),
	'purchases': ('Purchase Invoice', 'Purchase Invoice Item', 'supplier', 'supplier_name', 'purchase-invoice'),
	'customer_sales': ('Sales Invoice', 'Sales Invoice Item', 'customer', 'customer_name', 'sales-invoice'),
}
LIMIT = 8


def can_view(doctype):
	return bool(frappe.has_permission(doctype, 'read') and frappe.has_permission(doctype, 'report'))


@frappe.whitelist()
def get_item_history(item_code, view='sales', customer=None):
	require_user()
	if view not in (*SOURCES, 'stock', 'access'):
		frappe.throw(_('Invalid item history view.'))
	if not isinstance(item_code, str) or not item_code.strip() or len(item_code) > 140:
		frappe.throw(_('A valid item code is required.'))
	from klik_pos.api.sales_invoice import _get_active_pos_profile
	profile = _get_active_pos_profile()
	item = frappe.get_doc('Item', item_code)
	item.check_permission('read')
	permissions = {'sales': can_view('Sales Invoice'), 'purchases': can_view('Purchase Invoice')}
	permissions['customer_sales'] = permissions['sales']
	permissions['pricing'] = permissions['purchases']
	permissions['stock'] = can_view('Stock Ledger Entry') and bool(frappe.has_permission('Warehouse', 'read'))
	permissions['transfer'] = permissions['stock'] and bool(frappe.has_permission('Stock Entry', 'create') and frappe.has_permission('Stock Entry', 'submit'))
	result = {'item_code': item.name, 'item_name': item.item_name, 'company': profile.company, 'permissions': permissions, 'limit': LIMIT, 'transactions': []}
	if view == 'access':
		return result
	if not permissions[view]:
		frappe.throw(_('You do not have permission to view this report.'), frappe.PermissionError)
	if view == 'stock':
		warehouses = frappe.get_list('Warehouse', filters={'company': profile.company, 'is_group': 0, 'disabled': 0},
			fields=['name', 'warehouse_name'], order_by='warehouse_name asc', page_length=0)
		warehouse_names = [warehouse.name for warehouse in warehouses]
		bins = frappe.get_all('Bin', filters={'item_code': item.name, 'warehouse': ['in', warehouse_names]},
			fields=['warehouse', 'actual_qty'], limit_page_length=0) if warehouse_names else []
		quantities = {entry.warehouse: entry.actual_qty for entry in bins}
		result.update({'view': 'stock', 'stock_uom': item.stock_uom, 'is_stock_item': bool(item.is_stock_item), 'user': frappe.session.user,
			'has_batch_no': bool(item.has_batch_no), 'has_serial_no': bool(item.has_serial_no),
			'warehouses': [{'warehouse': warehouse.name, 'warehouse_name': warehouse.warehouse_name,
				'actual_qty': quantities.get(warehouse.name, 0)} for warehouse in warehouses]})
		return result
	doctype, childtype, partyfield, partyname, route = SOURCES[view]
	filters = [[doctype, 'docstatus', '=', 1], [doctype, 'company', '=', profile.company], [childtype, 'item_code', '=', item_code]]
	if view == 'customer_sales':
		if not customer or not isinstance(customer, str):
			frappe.throw(_('Select a customer in the POS before viewing customer sales history.'))
		frappe.get_doc('Customer', customer).check_permission('read')
		filters.append([doctype, 'customer', '=', customer])
	# DISTINCT limits documents rather than item rows: one invoice may contain
	# the same item more than once with different UOMs, prices or batches.
	invoices = frappe.get_list(doctype, filters=filters,
		fields=['name', 'posting_date', 'posting_time', 'creation', partyfield, partyname, 'currency', 'is_return'],
		distinct=True, order_by='posting_date desc, posting_time desc, creation desc, name desc', limit_page_length=LIMIT)
	allowed = set(get_permitted_fields(childtype, parenttype=doctype, permission_type='read'))
	for invoice in invoices:
		doc = frappe.get_doc(doctype, invoice.name)
		doc.check_permission('read')
		lines = []
		for row in doc.items:
			if row.item_code != item_code:
				continue
			lines.append({field: row.get(field) if field in allowed else None for field in ['qty', 'uom', 'net_rate', 'net_amount']})
		result['transactions'].append({'name': invoice.name, 'doctype': doctype, 'route': route,
			'posting_date': invoice.get('posting_date'), 'posting_time': invoice.get('posting_time'),
			'party': invoice.get(partyfield), 'party_name': invoice.get(partyname), 'currency': invoice.get('currency'),
			'is_return': bool(invoice.get('is_return')), 'lines': lines})
	result['view'] = view
	result['customer'] = customer if view == 'customer_sales' else None
	return result


@frappe.whitelist(methods=['POST'])
def transfer_stock(item_code, source_warehouse, target_warehouse, qty, request_id, batch_no=None, serial_no=None, remarks=None):
	"""Create and submit one native ERPNext material transfer with safe retries."""
	require_user()
	from klik_pos.api.sales_invoice import _get_active_pos_profile
	from klik_pos.api.checkout import run_checkout
	profile = _get_active_pos_profile()
	if not (can_view('Stock Ledger Entry') and frappe.has_permission('Warehouse', 'read')
		and frappe.has_permission('Stock Entry', 'create') and frappe.has_permission('Stock Entry', 'submit')):
		frappe.throw(_('Stock Entry create and submit, stock report and warehouse read permissions are required.'), frappe.PermissionError)
	item = frappe.get_doc('Item', item_code)
	item.check_permission('read')
	if not item.is_stock_item or item.disabled:
		frappe.throw(_('Select an enabled stock item.'))
	if not source_warehouse or not target_warehouse or source_warehouse == target_warehouse:
		frappe.throw(_('Choose two different warehouses.'))
	for name in (source_warehouse, target_warehouse):
		warehouse = frappe.get_doc('Warehouse', name)
		warehouse.check_permission('read')
		if warehouse.company != profile.company or warehouse.is_group or warehouse.disabled:
			frappe.throw(_('Both warehouses must be active warehouses in the POS company.'))
	try:
		quantity = float(qty)
	except (ValueError, TypeError):
		frappe.throw(_('Enter a valid quantity.'))
	if not math.isfinite(quantity) or quantity <= 0:
		frappe.throw(_('Quantity must be greater than zero.'))
	batch_no = (batch_no or '').strip()
	serial_no = (serial_no or '').strip()
	if remarks is not None and (not isinstance(remarks, str) or len(remarks) > 2000):
		frappe.throw(_('Remarks must be text of at most 2,000 characters.'))
	remarks = (remarks or '').strip()
	if item.has_batch_no and not batch_no:
		frappe.throw(_('A batch number is required for this item.'))
	if item.has_serial_no and not serial_no:
		frappe.throw(_('Serial numbers are required for this item.'))
	payload = {'checkoutRequestId': 'transfer_' + (request_id or ''), 'item_code': item.name,
		'source': source_warehouse, 'target': target_warehouse, 'qty': quantity, 'batch': batch_no, 'serial': serial_no}
	if remarks:
		payload['remarks'] = remarks
	def create(_data):
		doc = frappe.new_doc('Stock Entry')
		doc.company = profile.company
		doc.purpose = 'Material Transfer'
		doc.set_stock_entry_type()
		doc.from_warehouse = source_warehouse
		doc.to_warehouse = target_warehouse
		if remarks:
			doc.remarks = remarks
		row = {'item_code': item.name, 'qty': quantity, 'uom': item.stock_uom, 'stock_uom': item.stock_uom,
			'conversion_factor': 1, 's_warehouse': source_warehouse, 't_warehouse': target_warehouse}
		if item.has_batch_no or item.has_serial_no:
			row.update({'use_serial_batch_fields': 1, 'batch_no': batch_no or None, 'serial_no': serial_no or None})
		doc.append('items', row)
		doc.check_permission('create')
		doc.insert()
		doc.check_permission('submit')
		doc.submit()
		return {'success': True, 'name': doc.name}
	return run_checkout(payload, profile, create)
