import frappe


def execute():
	"""Enable per-site warehouses and create them for open sites (added with Site Material Receipt)."""
	if not frappe.db.get_single_value("Tower Site Settings", "company"):
		return
	frappe.db.set_single_value("Tower Site Settings", "create_site_warehouse", 1)
	for name in frappe.get_all("Tower Site", filters={"status": ["not in", ["Closed", "Cancelled"]]}, pluck="name"):
		frappe.get_doc("Tower Site", name).ensure_site_warehouse()
