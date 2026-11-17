/* Add the same Custom Type filter to ERPNext's Point of Sale page. */
(function () {
	let initialized = false;
	function init() {
		const selector = window.cur_pos && window.cur_pos.item_selector;
		if (!selector || initialized || !selector.$component) return;
		initialized = true;
		selector.custom_type = "";
		const original = selector.get_items.bind(selector);
		selector.get_items = function (args) {
			if (!this.custom_type) return original(args);
			const doc = this.events.get_frm().doc;
			return frappe.call({ method: "klik_pos.api.item.get_native_pos_items_by_custom_type", freeze: true,
				args: { start: args.start || 0, page_length: args.page_length || 40, price_list: (doc && doc.selling_price_list) || this.price_list, item_group: this.item_group, pos_profile: this.pos_profile, search_term: args.search_term || "", custom_type: this.custom_type } });
		};
		const $holder = $('<div class="abs-item-type-pos-filter" style="min-width:180px;margin-left:8px"></div>');
		selector.$component.find('.filter-section').append($holder);
		const control = frappe.ui.form.make_control({ parent: $holder, df: { fieldname: 'custom_type', label: __('Item Type'), fieldtype: 'Link', options: 'ABS Item Type', get_query: () => ({ filters: { disabled: 0 } }), change() { selector.custom_type = control.get_value() || ''; selector.search_index = {}; selector.filter_items(); } }, render_input: true });
		control.refresh();
	}
	$(document).on('page-change', function () { initialized = false; setTimeout(init, 300); });
	setInterval(init, 1000);
})();
