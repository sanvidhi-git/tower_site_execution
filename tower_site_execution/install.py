import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

ROLES = ("Site Project Manager", "Site Supervisor")

# Indus Towers New-Build TAT matrix (from the site allotment email)
MILESTONES = [
	# name, description, seq, tat, penalty/day, exceptions, wef, site date field
	("HOTO", "Allocation to HOTO", 1, 2, 500, "Nil", "Fresh allocation", "hoto_date"),
	("Work Start", "HOTO to Work start", 2, 3, 500, "SBC / Drawing / Site not workable", "Fresh allocation", "work_start_date"),
	("C1", "Work start to C1 (Tower Footing, OD BTS Footing)", 3, 7, 1500, "Environment Hold", "Fresh allocation", ""),
	("C2", "C1 to C2 (Tower Foundation, OD BTS Slab, Solar Foundation)", 4, 4, 1500,
	 "Environment Hold / Non availability of CIP", "Immediate Effect", ""),
	("C3", "C2 to C3 (Earthing)", 5, 2, 500, "Environment Hold", "Immediate Effect", ""),
	("E1", "T1 to E1 (Solar, Ladder & Railing)", 6, 2, 5000, "Environment Hold", "Immediate Effect", ""),
	("Solar I&C", "Solar Installation & Commissioning", 7, 1, 1000, "Environment Hold", "Immediate Effect", ""),
	("Ladder & Railing", "Ladder & Railing (part of E1)", 8, 0, 0, "Environment Hold", "Immediate Effect",
	 "work_completion_date"),
]

EXPENSE_TYPES = [
	"Labour Wages",
	"Earth Moving Equipment Hire",
	"Diesel / Fuel",
	"Transport & Freight",
	"Food & Lodging",
	"Local Purchase",
	"Site Security",
	"Water / Curing",
	"Repair & Maintenance",
	"Miscellaneous",
]


def after_install():
	make_roles()
	make_custom_fields()
	make_masters()
	set_default_settings()
	frappe.db.commit()


def after_migrate():
	make_roles()
	make_custom_fields()
	if ensure_item_group():
		set_default_settings()


def make_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def make_custom_fields():
	site = {
		"fieldname": "tower_site",
		"label": "Tower Site",
		"fieldtype": "Link",
		"options": "Tower Site",
		"in_standard_filter": 1,
	}
	create_custom_fields(
		{
			"Project": [dict(site, insert_after="project_name", read_only=1)],
			"Sales Order": [
				dict(site, insert_after="po_date"),
				{"fieldname": "gbpa_no", "label": "GBPA No", "fieldtype": "Data", "insert_after": "tower_site"},
			],
			"Sales Order Item": [
				{"fieldname": "indus_task_name", "label": "Indus Task", "fieldtype": "Data",
				 "insert_after": "item_name", "read_only": 1},
				{"fieldname": "indus_line_no", "label": "Indus PO Line", "fieldtype": "Int",
				 "insert_after": "indus_task_name", "read_only": 1},
			],
			"Sales Invoice": [
				dict(site, insert_after="customer_name"),
				{"fieldname": "joint_measurement_record", "label": "Joint Measurement Record",
				 "fieldtype": "Link", "options": "Joint Measurement Record", "insert_after": "tower_site",
				 "read_only": 1, "no_copy": 1},
			],
			"Material Request": [dict(site, insert_after="material_request_type")],
			"Purchase Order": [dict(site, insert_after="supplier_name")],
		},
		ignore_validate=True,
	)


def make_masters():
	for name, desc, seq, tat, pen, exc, wef, field in MILESTONES:
		if frappe.db.exists("Site Milestone Template", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Site Milestone Template",
				"milestone_name": name,
				"description": desc,
				"sequence": seq,
				"tat_days": tat,
				"penalty_per_day": pen,
				"exceptions_allowed": exc,
				"applicable_wef": wef,
				"site_date_field": field,
				"is_active": 1,
			}
		).insert(ignore_permissions=True)

	for et in EXPENSE_TYPES:
		if not frappe.db.exists("Site Expense Type", et):
			frappe.get_doc({"doctype": "Site Expense Type", "expense_type": et}).insert(ignore_permissions=True)

	ensure_item_group()


def ensure_item_group():
	"""Item group for Indus BOQ items; needs the ERPNext root group (exists after the setup wizard)."""
	if frappe.db.exists("Item Group", "Indus BOQ Items"):
		return "Indus BOQ Items"
	parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ["in", ["", None]]})
	if not parent:
		return None
	frappe.get_doc(
		{"doctype": "Item Group", "item_group_name": "Indus BOQ Items", "parent_item_group": parent, "is_group": 0}
	).insert(ignore_permissions=True)
	return "Indus BOQ Items"


def set_default_settings():
	settings = frappe.get_single("Tower Site Settings")
	company = frappe.defaults.get_global_default("company") or frappe.db.get_value("Company", {}, "name")
	if company and not settings.company:
		settings.company = company
	if not settings.boq_item_group and frappe.db.exists("Item Group", "Indus BOQ Items"):
		settings.boq_item_group = "Indus BOQ Items"
	if not settings.support_months:
		settings.support_months = 12
	settings.flags.ignore_mandatory = True
	settings.save(ignore_permissions=True)
