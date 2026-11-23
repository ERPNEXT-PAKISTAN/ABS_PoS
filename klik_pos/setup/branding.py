"""Keep the shared POS launcher and saved desktop layouts in sync."""
import json

import frappe
from frappe.model.rename_doc import rename_doc


LAYOUT_ICON_FIELDS = (
	'name', 'label', 'app', 'icon_type', 'link_type', 'link', 'link_to', 'logo_url', 'icon_image', 'standard',
)
CHILD_ICON_FIELDS = (*LAYOUT_ICON_FIELDS, 'parent_icon', 'hidden')


def sync_desktop_layouts(icon, *children):
	if not frappe.db.exists('DocType', 'Desktop Layout'):
		return

	for name in frappe.get_all('Desktop Layout', pluck='name'):
		saved_layout = frappe.db.get_value('Desktop Layout', name, 'layout', for_update=True)
		try:
			layout = json.loads(saved_layout or '[]')
		except ValueError:
			continue
		if not isinstance(layout, list) or not layout or not all(isinstance(entry, dict) for entry in layout):
			continue

		by_name = {entry.get('name'): entry for entry in layout}
		parent = by_name.get(icon.name)
		if parent is None:
			parent = next((
				entry for entry in layout
				if entry.get('icon_type') == 'App' and entry.get('name') != 'Open POS'
				and (entry.get('app') == 'klik_pos' or entry.get('link') in ('/klik_pos', '/abs_pos/pos'))
			), None)
		changed = sync_layout_entry(layout, parent, icon, LAYOUT_ICON_FIELDS)
		for child in children:
			changed |= sync_layout_entry(layout, by_name.get(child.name), child, CHILD_ICON_FIELDS)

		if changed:
			frappe.db.set_value('Desktop Layout', name, 'layout', json.dumps(layout), update_modified=False)


def sync_layout_entry(layout, entry, icon, fields):
	values = {field: icon.get(field) for field in fields}
	if entry is None:
		layout.append({
			'idx': max(entry.get('idx') or 0 for entry in layout) + 1,
			'hidden': icon.hidden,
			'parent_icon': icon.parent_icon,
			**values,
		})
		return True
	if any(entry.get(key) != value for key, value in values.items()):
		entry.update(values)
		return True
	return False


def sync_site_branding():
	launcher_icon = '/assets/klik_pos/icons/desktop_icons/subtle/pos.svg'
	if frappe.db.exists('DocType', 'Desktop Icon'):
		names = frappe.get_all('Desktop Icon', filters={
			'app': 'klik_pos', 'icon_type': 'App', 'name': ['!=', 'Open POS'],
		}, pluck='name')
		docs = [frappe.get_doc('Desktop Icon', name) for name in names]
		if not docs:
			doc = frappe.new_doc('Desktop Icon')
			doc.app = 'klik_pos'
			doc.icon_type = 'App'
			docs = [doc]
		for index, doc in enumerate(docs):
			is_new = doc.is_new()
			if not is_new and doc.name != 'POS' and not frappe.db.exists('Desktop Icon', 'POS'):
				rename_doc('Desktop Icon', doc.name, 'POS', ignore_permissions=True)
				doc = frappe.get_doc('Desktop Icon', 'POS')
			doc.label = 'POS'
			doc.standard = 1
			doc.link_type = 'External'
			doc.link_to = None
			doc.link = '/abs_pos/pos'
			doc.logo_url = launcher_icon
			doc.icon_image = launcher_icon
			if is_new and frappe.db.exists('Desktop Icon', doc.label):
				doc.insert(ignore_permissions=True, set_name='ABS POS Launcher')
			else:
				doc.save(ignore_permissions=True)
			# Frappe syncs the label to the document name on save.
			if doc.label != 'POS':
				doc.db_set('label', 'POS', update_modified=False)
			if index == 0:
				children = frappe.get_all(
					'Desktop Icon',
					filters={'app': 'klik_pos', 'parent_icon': doc.name},
					fields=list(CHILD_ICON_FIELDS),
					order_by='idx asc',
				)
				sync_desktop_layouts(doc, *children)
	if not (frappe.flags.in_install or frappe.flags.in_migrate):
		return

	business_name = frappe.db.get_single_value('ABS POS Settings', 'business_name')
	if business_name in ('ABS PoS', 'KLiK PoS', 'Klik POS', 'KLIK POS'):
		frappe.db.set_single_value('ABS POS Settings', 'business_name', 'ABS POS')

	if frappe.db.exists('Workspace', 'Klik POS'):
		doc = frappe.get_doc('Workspace', 'Klik POS')
		if frappe.get_meta('Workspace').has_field('type') and not doc.get('type'):
			doc.type = 'Workspace'
		doc.title = 'ABS POS'
		doc.content = (doc.content or '').replace('Klik POS', 'ABS POS').replace('ABS PoS', 'ABS POS')
		for shortcut in doc.shortcuts:
			if (shortcut.url or '').rstrip('/') == '/klik_pos':
				shortcut.url = '/abs_pos/pos'
			if (shortcut.url or '').rstrip('/') == '/abs_pos/pos':
				shortcut.label = 'ABS POS'
		doc.save(ignore_permissions=True)
		if doc.label != 'ABS POS':
			doc.db_set('label', 'ABS POS', update_modified=False)
