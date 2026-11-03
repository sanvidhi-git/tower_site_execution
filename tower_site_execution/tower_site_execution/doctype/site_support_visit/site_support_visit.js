frappe.ui.form.on("Site Support Visit", {
	setup(frm) {
		frm.set_query("tower_site", () => ({ filters: { status: ["in", ["RFI Done", "Closed"]] } }));
		frm.set_query("item_code", "materials", () => ({ filters: { is_stock_item: 1, disabled: 0 } }));
	},
});
