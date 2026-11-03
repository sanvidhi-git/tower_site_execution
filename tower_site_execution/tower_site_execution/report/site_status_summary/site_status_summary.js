frappe.query_reports["Site Status Summary"] = {
	filters: [
		{ fieldname: "circle", label: __("Circle"), fieldtype: "Data" },
		{ fieldname: "zone", label: __("Zone"), fieldtype: "Data" },
		{ fieldname: "principal_opco", label: __("OPCO"), fieldtype: "Select", options: ["", "Airtel", "Jio", "Vodafone Idea", "BSNL", "Other"] },
		{ fieldname: "from_date", label: __("Allocated From"), fieldtype: "Date" },
		{ fieldname: "to_date", label: __("Allocated To"), fieldtype: "Date" },
	],
	formatter(value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (data && data.is_total) value = `<b>${value}</b>`;
		if (column.fieldname === "sites" && data && data.filter) {
			value = `<a href="/app/tower-site?status=${encodeURIComponent(data.filter)}">${value}</a>`;
		}
		return value;
	},
};
