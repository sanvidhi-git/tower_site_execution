frappe.ui.form.on("Joint Measurement Record", {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && frm.doc.tower_site) {
			frm.add_custom_button(__("Get Executed BOQ Qty"), () =>
				frm.call("get_boq_items").then(() => frm.refresh_fields())
			);
		}
		if (frm.doc.docstatus === 1 && !frm.doc.sales_invoice) {
			frm.add_custom_button(__("Sales Invoice"), () =>
				frappe.model.open_mapped_doc({
					method: "tower_site_execution.tower_site_execution.doctype.joint_measurement_record.joint_measurement_record.make_sales_invoice",
					frm,
				})
			, __("Create"));
		}
	},
	tower_site(frm) {
		if (frm.doc.tower_site && !(frm.doc.items || []).length) {
			frm.call("get_boq_items").then(() => frm.refresh_fields());
		}
	},
});

frappe.ui.form.on("Joint Measurement Item", {
	measured_qty(frm, cdt, cdn) {
		const r = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(r.measured_qty) * flt(r.rate));
		frm.set_value("total_amount", (frm.doc.items || []).reduce((a, x) => a + flt(x.amount), 0));
	},
});
