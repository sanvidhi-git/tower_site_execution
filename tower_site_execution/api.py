import frappe


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def boq_item_query(doctype, txt, searchfield, start, page_len, filters):
	"""Only items on the site's Indus PO BOQ."""
	site = (filters or {}).get("tower_site")
	if not site:
		return []
	return frappe.db.sql(
		"""select b.item_code, concat(ifnull(b.task_name, ''), ' | PO ', b.po_qty, ' ', ifnull(b.uom, ''),
			' | done ', b.executed_qty), left(b.description, 80)
		from `tabTower Site BOQ` b
		where b.parent = %(site)s and b.parenttype = 'Tower Site'
		and (b.item_code like %(txt)s or b.description like %(txt)s or b.task_name like %(txt)s)
		order by b.line_no limit %(start)s, %(page_len)s""",
		{"site": site, "txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def site_status_counts(filters=None):
	"""Numbers for the main dashboard table."""
	from tower_site_execution.tower_site_execution.report.site_status_summary.site_status_summary import get_counts

	return get_counts(frappe.parse_json(filters) if filters else {})
