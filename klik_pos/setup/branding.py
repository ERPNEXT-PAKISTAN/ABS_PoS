"""Update the site's existing launcher without changing its roles or visibility."""
import frappe


def sync_site_branding():
	from klik_pos.api.setup import get_branding
	branding = get_branding()
	logo = branding['logo'] or '/assets/klik_pos/klik_spa/abs-logo.svg'
	if frappe.db.exists('DocType', 'Desktop Icon'):
		names = frappe.get_all('Desktop Icon', filters={'app': 'klik_pos', 'icon_type': 'App'}, pluck='name')
		docs = [frappe.get_doc('Desktop Icon', name) for name in names]
		if not docs:
			docs = [frappe.get_doc({'doctype': 'Desktop Icon', 'app': 'klik_pos', 'icon_type': 'App', 'standard': 0})]
		for doc in docs:
			if not doc.is_new() and doc.name != branding['business_name']:
				frappe.rename_doc('Desktop Icon', doc.name, branding['business_name'], force=True)
				doc = frappe.get_doc('Desktop Icon', branding['business_name'])
			doc.label = branding['business_name']
			doc.link_type = 'External'
			doc.link_to = None
			doc.link = '/abs_pos/pos'
			doc.logo_url = logo
			doc.icon_image = logo
			doc.save(ignore_permissions=True)
	if (frappe.flags.in_install or frappe.flags.in_migrate) and frappe.db.exists('Workspace', 'Klik POS'):
		doc = frappe.get_doc('Workspace', 'Klik POS')
		if frappe.get_meta('Workspace').has_field('type') and not doc.get('type'):
			doc.type = 'Workspace'
		doc.label = 'ABS PoS'
		doc.title = 'ABS PoS'
		doc.content = (doc.content or '').replace('Klik POS', 'ABS PoS')
		for shortcut in doc.shortcuts:
			if (shortcut.url or '').rstrip('/') == '/klik_pos':
				shortcut.url = '/abs_pos/pos'
				shortcut.label = 'ABS PoS'
		doc.save(ignore_permissions=True)
