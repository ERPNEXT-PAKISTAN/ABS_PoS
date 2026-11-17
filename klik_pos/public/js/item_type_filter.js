/* Shared desk filter for Item rows. The selected type is only a picking aid; it never changes document data. */
(function () {
	function setup(frm) {
		frm.set_query("item_code", "items", function () {
			return frm.doc.custom_type_filter ? { filters: { custom_type: frm.doc.custom_type_filter } } : {};
		});
		if (frm.__abs_item_type_button) return;
		frm.__abs_item_type_button = true;
		frm.add_custom_button(__("Item Type"), function () {
			const dialog = new frappe.ui.Dialog({
				title: __("Filter Items by Type"),
				fields: [{ fieldname: "custom_type", label: __("Custom Type"), fieldtype: "Link", options: "ABS Item Type", get_query: () => ({ filters: { disabled: 0 } }) }],
				primary_action_label: __("Apply"),
				primary_action(values) { frm.set_value("custom_type_filter", values.custom_type || ""); dialog.hide(); }
			});
			dialog.add_secondary_action(__("Clear Filter"), function () { frm.set_value("custom_type_filter", ""); dialog.hide(); });
			dialog.set_value("custom_type", frm.doc.custom_type_filter || "");
			dialog.show();
		}, __("Get Items From"));
	}
	["Sales Invoice", "Purchase Invoice", "POS Invoice"].forEach(function (doctype) {
		frappe.ui.form.on(doctype, { setup, refresh: setup, custom_type_filter: setup });
	});
})();
