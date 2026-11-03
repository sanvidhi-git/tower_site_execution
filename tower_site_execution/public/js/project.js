frappe.ui.form.on("Project", {
	refresh(frm) {
		if (frm.doc.tower_site) {
			frm.add_custom_button(__("Tower Site {0}", [frm.doc.tower_site]), () =>
				frappe.set_route("Form", "Tower Site", frm.doc.tower_site)
			);
		}
	},
});
