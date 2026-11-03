frappe.ui.form.on("Indus PO Import", {
	refresh(frm) {
		if (frm.is_new()) {
			frm.set_intro(__("Attach the Indus PO line export (Excel), optionally the PO PDF and the allotment email, save, then click Parse."));
			return;
		}
		if (frm.doc.status !== "Imported") {
			frm.add_custom_button(__("Parse Files"), () =>
				frm.call({ method: "parse_files", doc: frm.doc, freeze: true, freeze_message: __("Reading Indus PO...") })
					.then(() => frm.reload_doc())
			).addClass("btn-primary");
		}
		if (frm.doc.status === "Parsed") {
			frm.add_custom_button(__("Create Site, Project & Sales Order"), () =>
				frm.call({ method: "create_documents", doc: frm.doc, freeze: true, freeze_message: __("Creating documents...") })
					.then((r) => {
						frm.reload_doc();
						frappe.show_alert({ message: __("Site {0} / Sales Order {1} created", [r.message.tower_site, r.message.sales_order]), indicator: "green" });
					})
			).addClass("btn-primary");
		}
		if (frm.doc.tower_site) {
			frm.add_custom_button(__("Open Tower Site"), () => frappe.set_route("Form", "Tower Site", frm.doc.tower_site));
		}
	},
});
