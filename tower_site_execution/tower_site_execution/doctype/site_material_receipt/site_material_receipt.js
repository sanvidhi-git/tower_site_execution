frappe.ui.form.on("Site Material Receipt", {
	setup(frm) {
		frm.set_query("purchase_order", () => ({
			filters: { docstatus: 1, per_received: ["<", 100], status: ["not in", ["Closed", "On Hold"]] },
		}));
		frm.set_query("tower_site", () => ({ filters: { status: ["not in", ["Closed", "Cancelled"]] } }));
	},
	refresh(frm) {
		frm.set_intro(frm.doc.receipt_type === "Indus Free-Issue Material"
			? __("Indus-owned equipment: recorded against the site only, no stock posting.") : "");
		if (frm.doc.purchase_receipt) {
			frm.add_custom_button(__("Purchase Receipt"), () => frappe.set_route("Form", "Purchase Receipt", frm.doc.purchase_receipt), __("View"));
		}
		if (frm.doc.stock_entry) {
			frm.add_custom_button(__("Stock Entry"), () => frappe.set_route("Form", "Stock Entry", frm.doc.stock_entry), __("View"));
		}
	},
	purchase_order(frm) {
		if (!frm.doc.purchase_order) return;
		frappe.call("tower_site_execution.mobile_api.get_po_pending_items", { purchase_order: frm.doc.purchase_order }).then((r) => {
			frm.clear_table("items");
			(r.message || []).forEach((d) => frm.add_child("items", {
				item_code: d.item_code, item_name: d.item_name, uom: d.uom, ordered_qty: d.pending_qty,
				received_qty: d.pending_qty, purchase_order_item: d.name,
			}));
			frm.refresh_field("items");
		});
	},
});
