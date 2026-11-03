"""Shared helpers: settings access and the stock / expense postings made from
Daily Site Reports and Site Support Visits. Every posting carries the site's
Project, so ERPNext's project-wise GL and stock ledgers give per-site costing."""

import frappe
from frappe import _
from frappe.utils import flt, nowtime


def get_settings():
	return frappe.get_cached_doc("Tower Site Settings")


def get_company():
	company = get_settings().company or frappe.defaults.get_user_default("company")
	if not company:
		frappe.throw(_("Set Company in Tower Site Settings"))
	return company


def get_cost_center(company):
	return get_settings().default_cost_center or frappe.get_cached_value("Company", company, "cost_center")


def validate_site_open(site_name):
	status = frappe.db.get_value("Tower Site", site_name, "status")
	if status in ("Closed", "Cancelled"):
		frappe.throw(_("Tower Site {0} is {1}").format(frappe.bold(site_name), status))


def set_total_expense(doc):
	doc.total_expense = sum(flt(r.amount) for r in doc.get("expenses") or [])


def post_site_transactions(doc, posting_date, label):
	"""Create Material Issue + expense Journal Entry for a DSR / Support Visit."""
	settings = get_settings()
	company = get_company()
	cost_center = get_cost_center(company)
	remark = _("{0} {1} - Site {2}").format(label, doc.name, doc.tower_site)

	if doc.get("materials") and settings.auto_post_material_issue:
		site_wh = frappe.db.get_value("Tower Site", doc.tower_site, "site_warehouse")
		stock_rows = [m for m in doc.materials if frappe.get_cached_value("Item", m.item_code, "is_stock_item")]
		if stock_rows:
			se = frappe.new_doc("Stock Entry")
			se.stock_entry_type = "Material Issue"
			se.purpose = "Material Issue"
			se.company = company
			se.set_posting_time = 1
			se.posting_date = posting_date
			se.posting_time = nowtime()
			se.project = doc.project
			se.remarks = remark
			for m in stock_rows:
				warehouse = m.source_warehouse
				if not warehouse:
					# site stock first (material received at site), else the central store
					at_site = site_wh and flt(frappe.db.get_value(
						"Bin", {"item_code": m.item_code, "warehouse": site_wh}, "actual_qty")) >= flt(m.qty)
					warehouse = site_wh if at_site else settings.default_site_warehouse
				if not warehouse:
					frappe.throw(_("Row {0}: Source Warehouse is required for {1}").format(m.idx, m.item_code))
				se.append(
					"items",
					{
						"item_code": m.item_code,
						"qty": m.qty,
						"uom": m.uom or frappe.get_cached_value("Item", m.item_code, "stock_uom"),
						"s_warehouse": warehouse,
						"cost_center": cost_center,
						"project": doc.project,
					},
				)
			se.insert(ignore_permissions=True)
			se.submit()
			doc.db_set("stock_entry", se.name)

	if doc.get("expenses") and settings.auto_post_site_expenses:
		credit_account = settings.expense_credit_account
		if not credit_account:
			frappe.throw(_("Set Expense Credit Account in Tower Site Settings to post site expenses"))
		je = frappe.new_doc("Journal Entry")
		je.voucher_type = "Journal Entry"
		je.company = company
		je.posting_date = posting_date
		je.user_remark = remark
		total = 0
		for e in doc.expenses:
			account = frappe.get_cached_value("Site Expense Type", e.expense_type, "expense_account")
			if not account:
				frappe.throw(_("Set Expense Account on Site Expense Type {0}").format(frappe.bold(e.expense_type)))
			je.append(
				"accounts",
				{
					"account": account,
					"debit_in_account_currency": flt(e.amount),
					"cost_center": cost_center,
					"project": doc.project,
					"user_remark": " / ".join(x for x in (e.description, e.paid_to) if x),
				},
			)
			total += flt(e.amount)
		je.append(
			"accounts",
			{"account": credit_account, "credit_in_account_currency": total, "cost_center": cost_center},
		)
		je.insert(ignore_permissions=True)
		je.submit()
		doc.db_set("journal_entry", je.name)


def cancel_site_transactions(doc):
	for fieldname, doctype in (("stock_entry", "Stock Entry"), ("journal_entry", "Journal Entry")):
		name = doc.get(fieldname)
		if name and frappe.db.get_value(doctype, name, "docstatus") == 1:
			linked = frappe.get_doc(doctype, name)
			linked.flags.ignore_permissions = True
			linked.cancel()


def refresh_site(site_name, costing=True):
	"""Recompute BOQ progress (and costing) on a Tower Site."""
	if not site_name or not frappe.db.exists("Tower Site", site_name):
		return
	site = frappe.get_doc("Tower Site", site_name)
	site.update_boq_progress()
	if costing:
		site.calculate_costing()
	site.flags.ignore_permissions = True
	site.save()
