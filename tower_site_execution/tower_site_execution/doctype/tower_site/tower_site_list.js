frappe.listview_settings["Tower Site"] = {
	add_fields: ["status", "overall_progress"],
	get_indicator(doc) {
		const c = {
			"Work Not Started": "gray", "Work In Progress": "orange", "Work Completed": "blue",
			"RFI Pending": "yellow", "RFI Done": "green", "Closed": "darkgrey", "On Hold": "red", "Cancelled": "red",
		};
		return [__(doc.status), c[doc.status] || "gray", "status,=," + doc.status];
	},
};
