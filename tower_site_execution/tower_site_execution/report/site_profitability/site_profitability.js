frappe.query_reports["Site Profitability"] = {
	filters: [
		{ fieldname: "circle", label: __("Circle"), fieldtype: "Data" },
		{ fieldname: "zone", label: __("Zone"), fieldtype: "Data" },
		{ fieldname: "principal_opco", label: __("OPCO"), fieldtype: "Select", options: ["", "Airtel", "Jio", "Vodafone Idea", "BSNL", "Other"] },
		{ fieldname: "from_date", label: __("Allocated From"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("Allocated To"), fieldtype: "Date" },
		{ fieldname: "status", label: __("Status"), fieldtype: "Select",
		  options: ["", "Work Not Started", "Work In Progress", "Work Completed", "RFI Pending", "RFI Done", "Closed", "On Hold"] },
		{ fieldname: "refresh", label: __("Recalculate Costing Now"), fieldtype: "Check" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (["gross_margin", "margin_pct"].includes(column.fieldname) && data && data[column.fieldname] < 0) {
			value = `<span style="color:var(--red-600)">${value}</span>`;
		}
		return value;
	},
};
