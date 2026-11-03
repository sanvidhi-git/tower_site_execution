# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors

import frappe
from frappe import _

from tower_site_execution.tower_site_execution.report.site_status_summary.site_status_summary import site_filters


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if filters.get("refresh"):
		from tower_site_execution.utils import refresh_site

		for name in frappe.get_all("Tower Site", filters=site_filters(filters), pluck="name"):
			refresh_site(name)
	f = site_filters(filters)
	if filters.get("status"):
		f["status"] = filters.status
	cur = {"fieldtype": "Currency", "width": 120}
	columns = [
		{"fieldname": "name", "label": _("Site ID"), "fieldtype": "Link", "options": "Tower Site", "width": 120},
		{"fieldname": "nominal_name", "label": _("Nominal Name"), "fieldtype": "Data", "width": 150},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "overall_progress", "label": _("Progress"), "fieldtype": "Percent", "width": 90},
		dict(cur, fieldname="po_value", label=_("PO Value")),
		dict(cur, fieldname="billed_amount", label=_("Billed")),
		dict(cur, fieldname="material_cost", label=_("Material")),
		dict(cur, fieldname="expense_cost", label=_("Site Expenses")),
		dict(cur, fieldname="purchase_cost", label=_("Purchases / Hire")),
		dict(cur, fieldname="total_cost", label=_("Total Cost")),
		dict(cur, fieldname="gross_margin", label=_("Margin")),
		{"fieldname": "margin_pct", "label": _("Margin %"), "fieldtype": "Percent", "width": 90},
		dict(cur, fieldname="total_penalty", label=_("TAT Penalty Exposure")),
	]
	data = frappe.get_all(
		"Tower Site", filters=f, fields=[c["fieldname"] for c in columns], order_by="allocation_date desc")
	chart = {
		"data": {
			"labels": [d.name for d in data[:15]],
			"datasets": [
				{"name": _("PO Value"), "values": [d.po_value for d in data[:15]]},
				{"name": _("Total Cost"), "values": [d.total_cost for d in data[:15]]},
			],
		},
		"type": "bar",
	}
	return columns, data, None, chart
