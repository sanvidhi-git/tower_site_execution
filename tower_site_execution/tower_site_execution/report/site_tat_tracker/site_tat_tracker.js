frappe.query_reports["Site TAT Tracker"] = {
	filters: [
		{ fieldname: "tower_site", label: __("Site"), fieldtype: "Link", options: "Tower Site" },
		{ fieldname: "zone", label: __("Zone"), fieldtype: "Data" },
		{ fieldname: "milestone_status", label: __("Milestone Status"), fieldtype: "Select", options: ["", "Pending", "Overdue", "Done"] },
		{ fieldname: "only_delayed", label: __("Only Delayed"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (column.fieldname === "status" && data) {
			const c = { Overdue: "red", Done: "green", Pending: "orange" }[data.status];
			value = `<span class="indicator-pill ${c}">${value}</span>`;
		}
		return value;
	},
};
