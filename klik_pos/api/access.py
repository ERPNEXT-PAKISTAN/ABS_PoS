"""Server-side boundaries shared by ABS checkout and profile operations."""
import frappe
from frappe import _
from frappe.utils import flt
import math


def require_user():
	if frappe.session.user == 'Guest':
		frappe.throw(_('Please sign in to use ABS POS.'), frappe.PermissionError)


def is_manager():
	return frappe.session.user == 'Administrator' or 'System Manager' in frappe.get_roles()


def require_profile(name):
	require_user()
	profile = frappe.get_doc('POS Profile', name)
	profile.check_permission('read')
	if profile.disabled:
		frappe.throw(_('This POS Profile is disabled.'))
	if not is_manager():
		if not any(row.user == frappe.session.user for row in profile.applicable_for_users):
			frappe.throw(_('This POS Profile is not assigned to you.'), frappe.PermissionError)
		allowed = frappe.get_all('User Permission', filters={'user': frappe.session.user, 'allow': 'POS Profile'}, pluck='for_value')
		if allowed and name not in allowed:
			frappe.throw(_('This POS Profile is not permitted.'), frappe.PermissionError)
	for doctype, value in [('Company', profile.company), ('Warehouse', profile.warehouse)]:
		if value:
			frappe.get_doc(doctype, value).check_permission('read')
	return profile


def require_invoice(doc, permission='read'):
	require_user()
	doc.check_permission(permission)
	if not doc.pos_profile:
		frappe.throw(_('This invoice does not belong to a POS Profile.'), frappe.PermissionError)
	profile = require_profile(doc.pos_profile)
	if profile.company != doc.company:
		frappe.throw(_('Invoice company does not match its POS Profile.'), frappe.PermissionError)
	if not is_manager() and doc.owner != frappe.session.user:
		frappe.throw(_('You can only access your own POS invoices.'), frappe.PermissionError)
	return profile


def validate_checkout(data, profile):
	"""Do not trust client-selected business mode, payment modes or discounts."""
	require_profile(profile.name)
	if profile.get('custom_business_type') not in ('B2C', 'B2B', 'B2B & B2C'):
		frappe.throw(_('Configure the Business Type in this POS Profile before checkout.'))
	if not frappe.has_permission('Sales Invoice', 'create'):
		frappe.throw(_('You cannot create Sales Invoices.'), frappe.PermissionError)
	from klik_pos.api.sales_invoice import get_current_pos_opening_entry
	opening = get_current_pos_opening_entry()
	if not opening or frappe.db.get_value('POS Opening Entry', opening, 'pos_profile') != profile.name:
		frappe.throw(_('Open a shift for this POS Profile before checkout.'))
	if not isinstance(data.get('items'), list) or not 1 <= len(data['items']) <= 200:
		frappe.throw(_('Checkout requires between 1 and 200 item rows.'))
	allowed_modes = {p.mode_of_payment for p in profile.payments}
	for payment in data.get('paymentMethods') or []:
		mode = payment.get('method') or payment.get('mode_of_payment') or payment.get('name') or payment.get('id')
		if not math.isfinite(flt(payment.get('amount'))) or flt(payment.get('amount')) < 0:
			frappe.throw(_('Payment amounts must be finite and non-negative.'))
		if mode not in allowed_modes:
			frappe.throw(_('Payment method is not enabled in this POS Profile.'))
	for item in data.get('items') or []:
		for field in ('price', 'discountPercentage', 'discountAmount'):
			if not math.isfinite(flt(item.get(field))) or flt(item.get(field)) < 0:
				frappe.throw(_('Prices and discounts must be finite and non-negative.'))
		if flt(item.get('discountPercentage')) > 100:
			frappe.throw(_('Discount percentage cannot exceed 100.'))
		if not math.isfinite(flt(item.get('quantity'))) or flt(item.get('quantity')) <= 0:
			frappe.throw(_('Sale quantities must be positive. Use the return workflow for refunds.'))
		if not profile.allow_discount_change and (flt(item.get('discountPercentage')) or flt(item.get('discountAmount'))):
			frappe.throw(_('Manual discounts are disabled in this POS Profile.'))
	if not profile.allow_discount_change and data.get('appliedCoupons'):
		frappe.throw(_('Manual coupons are disabled in this POS Profile.'))
	invoice_discount = flt(data.get('invoiceDiscount'))
	if not math.isfinite(invoice_discount) or invoice_discount < 0:
		frappe.throw(_('Invoice discount must be finite and non-negative.'))
	if invoice_discount and not profile.allow_discount_change:
		frappe.throw(_('Invoice discounts are disabled in this POS Profile.'), frappe.PermissionError)
	if not math.isfinite(flt(data.get('amountPaid'))) or flt(data.get('amountPaid')) < 0:
		frappe.throw(_('Payment amount must be finite and non-negative.'))
	if abs(flt(data.get('roundOffAmount'))) > flt(profile.write_off_limit):
		frappe.throw(_('Write-off exceeds the POS Profile limit.'))
	if flt(data.get('roundOffAmount')) and not profile.get('custom_allow_write_off'):
		frappe.throw(_('Write-off is disabled in this POS Profile.'))
