"""Optional integration discovery and native ERPNext setup readiness."""
import frappe
from frappe import _
from klik_pos.api.access import require_user, require_profile, is_manager


def zatca_state(company):
	installed = 'zatca_integration' in frappe.get_installed_apps()
	enabled = bool(frappe.db.get_value('Company', company, 'custom_enable_zatca_e_invoicing')) if frappe.get_meta('Company').has_field('custom_enable_zatca_e_invoicing') else False
	if enabled and not installed:
		state = 'Unavailable'
	elif enabled:
		state = 'Enabled'
	elif installed:
		state = 'Disabled'
	else:
		state = 'Not installed'
	return {'installed': installed, 'enabled': enabled, 'state': state}


@frappe.whitelist(allow_guest=True)
def get_branding():
	# Only non-sensitive display settings; no company, account or cashier details.
	doc = frappe.get_single('ABS POS Settings')
	return {'business_name': doc.business_name or 'ABS POS', 'logo': doc.logo or '', 'support_email': doc.support_email or '', 'receipt_footer': doc.receipt_footer or ''}


@frappe.whitelist()
def get_setup():
	require_user()
	from klik_pos.api.pos_profile import get_pos_profiles_for_user
	profiles = frappe.get_list('POS Profile', filters={'disabled': 0}, pluck='name') if is_manager() else [p['name'] for p in get_pos_profiles_for_user()]
	result = []
	for name in profiles:
		p = require_profile(name)
		checks = {'warehouse': bool(p.warehouse), 'currency': bool(p.currency), 'payments': bool(p.payments), 'cashiers': bool(p.applicable_for_users), 'business_type': bool(p.get('custom_business_type')), 'print_format': bool(p.get('custom_pos_printformat'))}
		result.append({'name': p.name, 'company': p.company, 'warehouse': p.warehouse, 'currency': p.currency, 'checks': checks, 'zatca': zatca_state(p.company)})
	return {'branding': get_branding(), 'can_manage': is_manager(), 'profiles': result}


@frappe.whitelist(methods=['POST'])
def save_branding(settings):
	require_user()
	if not is_manager():
		frappe.throw(_('Only a System Manager can change POS setup.'), frappe.PermissionError)
	if isinstance(settings, str):
		settings = frappe.parse_json(settings)
	doc = frappe.get_single('ABS POS Settings')
	doc.check_permission('write')
	for field in ['business_name', 'logo', 'support_email', 'receipt_footer']:
		value = str(settings.get(field) or '').strip()
		if len(value) > (500 if field == 'receipt_footer' else 140):
			frappe.throw(_('Setting is too long: {0}').format(field))
		if field == 'logo' and value and not value.startswith(('/files/', '/private/files/', '/assets/')):
			frappe.throw(_('Choose a logo uploaded to this site.'))
		doc.set(field, value)
	if not doc.business_name:
		frappe.throw(_('POS Name is required.'))
	doc.save()
	from klik_pos.setup.branding import sync_site_branding
	sync_site_branding()
	return get_branding()


@frappe.whitelist()
def get_session_context():
	"""Refresh the in-memory CSRF token after SPA sign-in; never persist it in cart storage."""
	require_user()
	from frappe.sessions import get_csrf_token
	return {'user': frappe.session.user, 'csrf_token': get_csrf_token()}
