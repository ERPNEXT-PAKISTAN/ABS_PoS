"""Keep the ABS Item Type master aligned with pre-existing Item.custom_type values."""
import frappe


def sync_item_types():
	if not frappe.db.exists("DocType", "ABS Item Type") or not frappe.get_meta("Item").has_field("custom_type"):
		return
	values = frappe.db.sql(
		"""select distinct custom_type from `tabItem`
		where ifnull(custom_type, '') != '' order by custom_type""",
		pluck=True,
	)
	for value in values:
		if not frappe.db.exists("ABS Item Type", value):
			frappe.get_doc({"doctype": "ABS Item Type", "type_name": value}).insert(
				ignore_permissions=True
			)
