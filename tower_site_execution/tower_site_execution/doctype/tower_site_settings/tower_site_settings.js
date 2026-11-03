frappe.ui.form.on("Tower Site Settings", {
	refresh(frm) {
		if (!frappe.user.has_role("System Manager")) return;
		frm.add_custom_button(__("Load Demo Data"), () => {
			frappe.confirm(
				__("Create about 30 demo Tower Sites with orders, daily reports, receipts, invoices and postings? Use on a TEST site only."),
				() => frappe.call("tower_site_execution.demo.enqueue_demo", { company: frm.doc.company })
					.then(() => frappe.show_alert({ message: __("Demo data is being created in the background (a few minutes)"), indicator: "blue" }))
			);
		}, __("Demo"));
	},
});
