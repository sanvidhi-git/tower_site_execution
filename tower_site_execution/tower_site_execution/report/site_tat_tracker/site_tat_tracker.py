# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = [
		{"fieldname": "tower_site", "label": _("Site ID"), "fieldtype": "Link", "options": "Tower Site", "width": 120},
		{"fieldname": "nominal_name", "label": _("Nominal Name"), "fieldtype": "Data", "width": 140},
		{"fieldname": "site_status", "label": _("Site Status"), "fieldtype": "Data", "width": 120},
		{"fieldname": "milestone", "label": _("Milestone"), "fieldtype": "Link", "options": "Site Milestone Template", "width": 120},
		{"fieldname": "tat_days", "label": _("TAT"), "fieldtype": "Int", "width": 60},
		{"fieldname": "planned_date", "label": _("Planned"), "fieldtype": "Date", "width": 100},
		{"fieldname": "actual_date", "label": _("Actual"), "fieldtype": "Date", "width": 100},
		{"fieldname": "hold_days", "label": _("Hold Days"), "fieldtype": "Int", "width": 80},
		{"fieldname": "delay_days", "label": _("Delay Days"), "fieldtype": "Int", "width": 90},
		{"fieldname": "penalty_amount", "label": _("Penalty"), "fieldtype": "Currency", "width": 110},
		{"fieldname": "status", "label": _("Milestone Status"), "fieldtype": "Data", "width": 110},
	]
	cond = ["s.status not in ('Cancelled')"]
	if filters.tower_site:
		cond.append("s.name = %(tower_site)s")
	if filters.only_delayed:
		cond.append("m.delay_days > 0")
	if filters.milestone_status:
		cond.append("m.status = %(milestone_status)s")
	if filters.zone:
		cond.append("s.zone = %(zone)s")
	data = frappe.db.sql(
		f"""select s.name as tower_site, s.nominal_name, s.status as site_status, m.milestone, m.tat_days,
			m.planned_date, m.actual_date, m.hold_days, m.delay_days, m.penalty_amount, m.status
		from `tabTower Site Milestone` m join `tabTower Site` s on s.name = m.parent
		where m.parenttype = 'Tower Site' and {' and '.join(cond)}
		order by s.allocation_date desc, s.name, m.idx""",
		filters,
		as_dict=True,
	)
	return columns, data
