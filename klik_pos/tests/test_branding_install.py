"""Exercise launcher setup without changing the site's desktop icons."""
import unittest
from unittest.mock import MagicMock, patch

from klik_pos.setup.branding import sync_site_branding


class TestBrandingInstall(unittest.TestCase):
	def test_fresh_install_uses_new_document_without_rename(self):
		doc = MagicMock()
		doc.is_new.return_value = True
		with patch('klik_pos.api.setup.get_branding', return_value={'business_name': 'ABS PoS', 'logo': ''}), \
			patch('frappe.db.exists', side_effect=lambda doctype, name: doctype == 'DocType' and name == 'Desktop Icon'), \
			patch('frappe.get_all', return_value=[]), patch('frappe.new_doc', return_value=doc) as new_doc, \
			patch('frappe.rename_doc') as rename:
			sync_site_branding()
		new_doc.assert_called_once_with('Desktop Icon')
		rename.assert_not_called()
		self.assertEqual(doc.label, 'ABS PoS')
		self.assertEqual(doc.link, '/abs_pos/pos')
		doc.save.assert_called_once_with(ignore_permissions=True)

	def test_existing_icon_keeps_identity(self):
		doc = MagicMock()
		doc.is_new.return_value = False
		with patch('klik_pos.api.setup.get_branding', return_value={'business_name': 'ABS PoS', 'logo': ''}), \
			patch('frappe.db.exists', side_effect=lambda doctype, name: doctype == 'DocType' and name == 'Desktop Icon'), \
			patch('frappe.get_all', return_value=['Existing Icon']), patch('frappe.get_doc', return_value=doc), \
			patch('frappe.rename_doc') as rename:
			sync_site_branding()
		rename.assert_not_called()
		self.assertEqual(doc.label, 'ABS PoS')
		doc.save.assert_called_once_with(ignore_permissions=True)
