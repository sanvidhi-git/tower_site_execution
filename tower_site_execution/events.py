import frappe

from tower_site_execution.utils import refresh_site


def _site_from_project(project):
	return project and frappe.db.get_value("Project", project, "tower_site")


def sales_invoice_changed(doc, method=None):
	site = doc.get("tower_site") or _site_from_project(doc.get("project"))
	if doc.get("joint_measurement_record"):
		frappe.db.set_value(
			"Joint Measurement Record",
			doc.joint_measurement_record,
			"sales_invoice",
			doc.name if doc.docstatus == 1 else None,
		)
	if site:
		refresh_site(site)


def cost_document_changed(doc, method=None):
	"""Purchase Invoice / Journal Entry / Stock Entry tagged with a site project -> refresh costing."""
	projects = set()
	if doc.get("project"):
		projects.add(doc.project)
	for table in ("items", "accounts"):
		for row in doc.get(table) or []:
			if row.get("project"):
				projects.add(row.project)
	for project in projects:
		site = _site_from_project(project)
		if site:
			refresh_site(site)
