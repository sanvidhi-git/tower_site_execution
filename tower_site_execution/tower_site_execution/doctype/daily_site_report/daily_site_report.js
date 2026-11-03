// Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors

frappe.ui.form.on("Daily Site Report", {
	setup(frm) {
		frm.set_query("tower_site", () => ({ filters: { status: ["not in", ["Closed", "Cancelled"]] } }));
		frm.set_query("item_code", "work_items", () => ({
			query: "tower_site_execution.api.boq_item_query",
			filters: { tower_site: frm.doc.tower_site },
		}));
		frm.set_query("item_code", "materials", () => ({ filters: { is_stock_item: 1, disabled: 0 } }));
		frm.set_query("supervisor", () => ({ filters: { status: "Active" } }));
	},
	onload(frm) {
		if (frm.is_new()) {
			if (!frm.doc.supervisor) {
				frappe.db.get_value("Employee", { user_id: frappe.session.user, status: "Active" }, "name")
					.then((r) => r.message && r.message.name && frm.set_value("supervisor", r.message.name));
			}
			frm.trigger("capture_location");
		}
	},
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Capture GPS"), () => frm.trigger("capture_location"));
		}
		if (frm.doc.latitude) {
			frm.add_custom_button(__("Open in Maps"), () =>
				window.open(`https://maps.google.com/?q=${frm.doc.latitude},${frm.doc.longitude}`)
			);
		}
	},
	capture_location(frm) {
		if (!navigator.geolocation) return;
		navigator.geolocation.getCurrentPosition(
			(p) => {
				frm.set_value("latitude", p.coords.latitude);
				frm.set_value("longitude", p.coords.longitude);
			},
			() => frappe.show_alert({ message: __("Location permission denied"), indicator: "orange" }),
			{ enableHighAccuracy: true, timeout: 15000 }
		);
	},
});

frappe.ui.form.on("Site Expense", {
	amount: (frm) => frm.set_value("total_expense", (frm.doc.expenses || []).reduce((a, r) => a + flt(r.amount), 0)),
	expenses_remove: (frm) => frm.set_value("total_expense", (frm.doc.expenses || []).reduce((a, r) => a + flt(r.amount), 0)),
});
