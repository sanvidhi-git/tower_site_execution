from frappe import _


def get_data():
	return {
		"fieldname": "tower_site",
		"non_standard_fieldnames": {},
		"transactions": [
			{"label": _("Execution"), "items": ["Site Feasibility Survey", "Daily Site Report", "Site Support Visit"]},
			{"label": _("Billing"), "items": ["Sales Order", "Joint Measurement Record", "Sales Invoice"]},
			{"label": _("Buying"), "items": ["Material Request", "Purchase Order"]},
			{"label": _("Project"), "items": ["Project", "Indus PO Import"]},
		],
	}
