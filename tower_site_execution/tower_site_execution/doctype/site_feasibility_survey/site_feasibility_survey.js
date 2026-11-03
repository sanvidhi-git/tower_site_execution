frappe.ui.form.on("Site Feasibility Survey", {
	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.indus_decision === "Pending") {
			frm.add_custom_button(__("Record Indus Go-Ahead"), () => {
				frm.set_value("indus_decision", "Go Ahead");
				frm.set_value("decision_date", frappe.datetime.get_today());
				frm.save("Update");
			});
		}
	},
});
