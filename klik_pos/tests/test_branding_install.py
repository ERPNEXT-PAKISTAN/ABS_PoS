"""Exercise launcher setup without changing the site's desktop icons."""
import json
import unittest
from unittest.mock import MagicMock, patch

import frappe

from klik_pos.setup.branding import sync_desktop_layouts, sync_site_branding


class TestBrandingInstall(unittest.TestCase):
	def setUp(self):
		frappe_patch = patch('klik_pos.setup.branding.frappe')
		self.frappe = frappe_patch.start()
		self.addCleanup(frappe_patch.stop)
		rename_patch = patch('klik_pos.setup.branding.rename_doc')
		self.rename_doc = rename_patch.start()
		self.addCleanup(rename_patch.stop)
		self.frappe.flags.in_install = False
		self.frappe.flags.in_migrate = False
		self.frappe.db.exists.side_effect = lambda doctype, name: doctype == 'DocType' and name == 'Desktop Icon'

	def test_fresh_install_uses_new_document_without_rename(self):
		doc = MagicMock()
		doc.is_new.return_value = True
		self.frappe.get_all.return_value = []
		self.frappe.new_doc.return_value = doc
		sync_site_branding()
		self.frappe.new_doc.assert_called_once_with('Desktop Icon')
		self.rename_doc.assert_not_called()
		self.assertEqual(doc.label, 'POS')
		self.assertEqual(doc.link, '/abs_pos/pos')
		doc.save.assert_called_once_with(ignore_permissions=True)

	def test_existing_icon_is_renamed_through_frappe(self):
		doc = MagicMock()
		doc.is_new.return_value = False
		doc.name = 'Existing Icon'
		renamed = MagicMock()
		renamed.name = 'POS'
		self.frappe.get_all.return_value = ['Existing Icon']
		self.frappe.get_doc.side_effect = [doc, renamed]
		sync_site_branding()
		self.rename_doc.assert_called_once_with(
			'Desktop Icon', 'Existing Icon', 'POS', ignore_permissions=True
		)
		self.assertEqual(renamed.label, 'POS')
		renamed.save.assert_called_once_with(ignore_permissions=True)

	def test_new_icon_retains_pos_label_when_docname_is_taken(self):
		doc = MagicMock()
		doc.is_new.return_value = True
		self.frappe.db.exists.side_effect = lambda doctype, name: (doctype, name) in {
			('DocType', 'Desktop Icon'), ('Desktop Icon', 'POS')
		}
		self.frappe.get_all.return_value = []
		self.frappe.new_doc.return_value = doc

		sync_site_branding()

		self.assertEqual(doc.label, 'POS')
		doc.insert.assert_called_once_with(ignore_permissions=True, set_name='ABS POS Launcher')

	def test_saved_layout_updates_launcher_in_place(self):
		icon = frappe._dict(name='POS', label='POS', app='klik_pos', icon_type='App', standard=1)
		folder = {'name': 'My folder', 'icon_type': 'Folder', 'idx': 2}
		old_launcher = {'name': 'ABS PoS', 'app': 'klik_pos', 'icon_type': 'App', 'idx': 3, 'parent_icon': 'My folder'}
		self.frappe.db.exists.side_effect = None
		self.frappe.db.exists.return_value = True
		self.frappe.get_all.return_value = ['Saved Layout']
		self.frappe.db.get_value.return_value = json.dumps([folder, old_launcher])

		sync_desktop_layouts(icon)

		saved = self.frappe.db.set_value.call_args.args[3]
		layout = json.loads(saved)
		self.assertEqual(len(layout), 2)
		self.assertEqual(layout[0], folder)
		self.assertEqual((layout[1]['name'], layout[1]['idx'], layout[1]['parent_icon']), ('POS', 3, 'My folder'))
		self.frappe.db.set_value.reset_mock()
		self.frappe.db.get_value.return_value = saved
		sync_desktop_layouts(icon)
		self.frappe.db.set_value.assert_not_called()
