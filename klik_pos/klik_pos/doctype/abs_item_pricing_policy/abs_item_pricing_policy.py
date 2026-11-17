import frappe
from frappe import _
from frappe.model.document import Document


class ABSItemPricingPolicy(Document):
	def autoname(self):
		from klik_pos.api.item_pricing import policy_key
		self.name = policy_key(self.company, self.item, self.price_list, self.uom)

	def validate(self):
		from klik_pos.api.item_pricing import number
		number(self.markup_percentage,'Markup')
		number(self.manual_cost or 0,'Manual cost')
		self.company_currency = frappe.db.get_value('Company',self.company,'default_currency')
		item = frappe.get_doc('Item',self.item)
		if self.uom != item.stock_uom and not any(row.uom==self.uom for row in item.uoms):
			frappe.throw(_('Choose a UOM configured on this item.'))
