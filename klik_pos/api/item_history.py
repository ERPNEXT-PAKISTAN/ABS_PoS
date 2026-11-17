"""Read-only invoice history, scoped to the active POS company and native permissions."""
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
	if view not in (*SOURCES, 'access'):
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
	result = {'item_code': item.name, 'item_name': item.item_name, 'company': profile.company, 'permissions': permissions, 'limit': LIMIT, 'transactions': []}
	if view == 'access':
		return result
	if not permissions[view]:
		frappe.throw(_('You do not have permission to read this invoice history report.'), frappe.PermissionError)
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
