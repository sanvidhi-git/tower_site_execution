# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors

import frappe
from frappe import _

# dashboard rows in the order the client asked for
BUCKETS = [
	("Work not started", ["Work Not Started"]),
	("Work in progress", ["Work In Progress"]),
	("Work completed", ["Work Completed"]),
	("RFI pending", ["RFI Pending"]),
	("RFI done", ["RFI Done"]),
	("On hold", ["On Hold"]),
	("Closed (support over)", ["Closed"]),
]


def site_filters(filters):
	f = {"status": ["!=", "Cancelled"]}
	for key in ("circle", "zone", "principal_opco"):
		if filters.get(key):
			f[key] = filters[key]
	if filters.get("from_date"):
		f["allocation_date"] = [">=", filters["from_date"]]
	if filters.get("to_date"):
		f.setdefault("allocation_date", [">=", "2000-01-01"])
		f["allocation_date"] = ["between", [f["allocation_date"][1], filters["to_date"]]]
	return f


def get_counts(filters):
	rows = frappe.get_all("Tower Site", filters=site_filters(filters), fields=["status", {"COUNT": "name", "as": "n"}], group_by="status")
	by_status = {r.status: r.n for r in rows}
	out = [{"status": "Total allocated", "sites": sum(by_status.values()), "is_total": 1, "filter": ""}]
	for label, statuses in BUCKETS:
		n = sum(by_status.get(s, 0) for s in statuses)
		if n or label not in ("On hold", "Closed (support over)"):
			out.append({"status": label, "sites": n, "filter": statuses[0]})
	return out


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 220},
		{"fieldname": "sites", "label": _("Number of Sites"), "fieldtype": "Int", "width": 150},
		{"fieldname": "pct", "label": _("% of Allocated"), "fieldtype": "Percent", "width": 130},
	]
	data = get_counts(filters)
	total = data[0]["sites"] or 1
	for r in data:
		r["pct"] = r["sites"] / total * 100
	chart_rows = [r for r in data if not r.get("is_total")]
	chart = {
		"data": {
			"labels": [r["status"] for r in chart_rows],
			"datasets": [{"name": _("Sites"), "values": [r["sites"] for r in chart_rows]}],
		},
		"type": "bar",
		"colors": ["#1F6F5C"],
	}
	summary = [
		{"label": r["status"], "value": r["sites"], "indicator": "Blue" if r.get("is_total") else "Green", "datatype": "Int"}
		for r in data[:6]
	]
	return columns, data, None, chart, summary
