"""REST API for the "Sanvidhi Site" Android app.

Auth: `login` returns an API token ("api_key:api_secret"); the app then sends
`Authorization: token <api_key>:<api_secret>` on every call, so all methods run with
the user's own permissions.

Submissions carry a client-generated `mobile_ref`; re-sending the same payload (offline
outbox retry) returns the document already created instead of creating a duplicate.
"""

import base64
import json

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from tower_site_execution import __version__

MANAGER_ROLES = {"Site Project Manager", "System Manager"}
OPEN = ["not in", ["Closed", "Cancelled"]]


# --------------------------------------------------------------------------- auth
@frappe.whitelist(allow_guest=True)
def ping():
	return {"app": "tower_site_execution", "version": __version__, "site": frappe.local.site}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def login(usr, pwd):
	from frappe.auth import LoginManager

	lm = LoginManager()
	lm.authenticate(user=usr, pwd=pwd)
	lm.post_login()
	user = frappe.get_doc("User", frappe.session.user)
	secret = None
	if user.api_key:
		try:
			secret = user.get_password("api_secret")
		except Exception:
			secret = None
	if not user.api_key or not secret:
		user.api_key = user.api_key or frappe.generate_hash(length=15)
		secret = frappe.generate_hash(length=15)
		user.api_secret = secret
		user.flags.ignore_permissions = True
		user.save()
		frappe.db.commit()
	frappe.local.login_manager = lm
	return {"api_key": user.api_key, "api_secret": secret, "user": user.name, "full_name": user.full_name,
		"bootstrap": bootstrap()}


# ------------------------------------------------------------------------ helpers
def _me():
	roles = set(frappe.get_roles())
	employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user, "status": "Active"}, ["name", "employee_name"], as_dict=True)
	return roles, employee


def _my_site_names():
	roles, employee = _me()
	if roles & MANAGER_ROLES:
		return None  # all open sites
	if not employee:
		return []
	return frappe.get_all(
		"Tower Site Team Member", filters={"parenttype": "Tower Site", "employee": employee.name},
		pluck="parent", distinct=True)


def _check_site(site):
	names = _my_site_names()
	if names is not None and site not in names:
		frappe.throw(_("You are not assigned to site {0}").format(site), frappe.PermissionError)
	return frappe.get_doc("Tower Site", site)


def _load(payload):
	return frappe._dict(json.loads(payload) if isinstance(payload, str) else payload)


def _save_image(b64, doc, idx, prefix):
	if not b64:
		return None
	if "," in b64[:80]:
		b64 = b64.split(",", 1)[1]
	f = frappe.get_doc({
		"doctype": "File",
		"file_name": f"{doc.name}-{idx}.jpg",
		"attached_to_doctype": doc.doctype,
		"attached_to_name": doc.name,
		"content": base64.b64decode(b64),
		"is_private": 1,
	})
	f.flags.ignore_permissions = True
	f.insert()
	return f.file_url


def _existing(doctype, ref):
	return ref and frappe.db.get_value(doctype, {"mobile_ref": ref}, ["name", "docstatus"], as_dict=True)


def _result(doc):
	return {"name": doc.name, "docstatus": doc.docstatus,
		"status": {0: "Pending approval", 1: "Approved", 2: "Cancelled"}[doc.docstatus]}


# ------------------------------------------------------------------------- read
@frappe.whitelist()
def bootstrap():
	roles, employee = _me()
	names = _my_site_names()
	filters = {"status": OPEN}
	if names is not None:
		filters["name"] = ["in", names or [""]]
	sites = frappe.get_all(
		"Tower Site", filters=filters,
		fields=["name", "nominal_name", "status", "overall_progress", "zone", "district", "latitude", "longitude",
			"allocation_date", "principal_opco", "tower_type", "project", "site_warehouse"],
		order_by="allocation_date desc")
	company = frappe.db.get_single_value("Tower Site Settings", "company")
	return {
		"user": frappe.session.user,
		"full_name": frappe.utils.get_fullname(frappe.session.user),
		"employee": employee,
		"is_manager": bool(roles & MANAGER_ROLES),
		"company": company,
		"sites": sites,
		"expense_types": frappe.get_all("Site Expense Type", pluck="name", order_by="name"),
		"milestones": frappe.get_all("Site Milestone Template", filters={"is_active": 1},
			fields=["name", "description"], order_by="sequence"),
		"warehouses": frappe.get_all("Warehouse", filters={"company": company, "is_group": 0, "disabled": 0},
			pluck="name", order_by="name"),
		"central_store": frappe.db.get_single_value("Tower Site Settings", "default_site_warehouse"),
		"server_version": __version__,
	}


@frappe.whitelist()
def site_detail(site):
	doc = _check_site(site)
	return {
		"site": {k: doc.get(k) for k in ("name", "nominal_name", "status", "overall_progress", "zone", "district",
			"latitude", "longitude", "allocation_date", "tower_type", "tower_height", "principal_opco",
			"site_address", "site_warehouse", "zpm_name", "de_name", "fse_name")},
		"boq": [{"item_code": r.item_code, "description": r.description, "task_name": r.task_name, "uom": r.uom,
			"po_qty": r.po_qty, "executed_qty": r.executed_qty, "progress": r.progress} for r in doc.boq],
		"milestones": [{"milestone": m.milestone, "planned_date": m.planned_date, "actual_date": m.actual_date,
			"status": m.status, "delay_days": m.delay_days} for m in doc.milestones],
		"open_pos": open_purchase_orders(site),
		"recent": _submissions({"tower_site": site}, 10),
	}


@frappe.whitelist()
def open_purchase_orders(site):
	doc = frappe.get_doc("Tower Site", site)
	pos = frappe.db.sql(
		"""select distinct po.name, po.supplier, po.supplier_name, po.transaction_date, po.per_received
		from `tabPurchase Order` po join `tabPurchase Order Item` poi on poi.parent = po.name
		where po.docstatus = 1 and po.per_received < 100 and po.status not in ('Closed', 'On Hold')
		and (po.tower_site = %(site)s or poi.project = %(project)s or po.project = %(project)s)
		order by po.transaction_date desc limit 30""",
		{"site": site, "project": doc.project or ""}, as_dict=True)
	return pos


@frappe.whitelist()
def get_po_pending_items(purchase_order):
	names = _my_site_names()
	if names is not None and not frappe.has_permission("Purchase Order", "read", purchase_order):
		# site staff usually have no buying access: allow POs that belong to one of their sites
		po_sites = {frappe.db.get_value("Purchase Order", purchase_order, "tower_site")}
		for project in frappe.get_all("Purchase Order Item", filters={"parent": purchase_order}, pluck="project"):
			if project:
				po_sites.add(frappe.db.get_value("Project", project, "tower_site"))
		if not po_sites & set(names):
			frappe.throw(_("Not permitted"), frappe.PermissionError)
	rows = frappe.get_all("Purchase Order Item", filters={"parent": purchase_order},
		fields=["name", "item_code", "item_name", "uom", "qty", "received_qty"], order_by="idx")
	for r in rows:
		r.pending_qty = max(flt(r.qty) - flt(r.received_qty), 0)
	return [r for r in rows if r.pending_qty > 0]


@frappe.whitelist()
def search_items(txt="", stock_only=1, limit=20):
	filters = {"disabled": 0, "item_group": ["!=", "Indus BOQ Items"]}
	if cint(stock_only):
		filters["is_stock_item"] = 1
	or_filters = {"item_code": ["like", f"%{txt}%"], "item_name": ["like", f"%{txt}%"]} if txt else None
	return frappe.get_all("Item", filters=filters, or_filters=or_filters,
		fields=["name as item_code", "item_name", "stock_uom as uom"], limit=cint(limit), order_by="item_name")


def _submissions(filters, limit):
	out = []
	for dt, date_field, kind in (("Daily Site Report", "report_date", "Daily Report"),
			("Site Material Receipt", "receipt_date", "Material Receipt")):
		f = dict(filters)
		f["docstatus"] = ["<", 2]
		extra = "receipt_type" if dt == "Site Material Receipt" else "work_completed"
		for d in frappe.get_all(dt, filters=f, fields=["name", "tower_site", date_field + " as date", "docstatus",
				extra + " as summary", "modified"], order_by="modified desc", limit=limit):
			d.kind = kind
			d.status = "Approved" if d.docstatus == 1 else "Pending approval"
			out.append(d)
	out.sort(key=lambda d: d.modified, reverse=True)
	return out[:limit]


@frappe.whitelist()
def my_submissions(limit=40):
	return _submissions({"owner": frappe.session.user}, cint(limit))


# ------------------------------------------------------------------------ write
@frappe.whitelist(methods=["POST"])
def submit_daily_report(payload):
	data = _load(payload)
	done = _existing("Daily Site Report", data.mobile_ref)
	if done:
		return dict(done, duplicate=1, status="Already received")
	_check_site(data.tower_site)
	if getdate(data.report_date or nowdate()) > getdate(nowdate()):
		frappe.throw(_("Report date cannot be in the future"))

	dsr = frappe.new_doc("Daily Site Report")
	dsr.update({
		"tower_site": data.tower_site, "report_date": data.report_date or nowdate(),
		"labour_count": cint(data.labour_count), "milestone_achieved": data.milestone_achieved or None,
		"work_completed": data.work_completed, "pending_work": data.pending_work, "remarks": data.remarks,
		"latitude": flt(data.latitude), "longitude": flt(data.longitude), "source": "Mobile App",
		"mobile_ref": data.mobile_ref,
	})
	for r in data.work_items or []:
		if flt(r.get("qty_completed")):
			dsr.append("work_items", {"item_code": r["item_code"], "qty_completed": flt(r["qty_completed"]),
				"remarks": r.get("remarks")})
	for r in data.materials or []:
		if flt(r.get("qty")):
			dsr.append("materials", {"item_code": r["item_code"], "qty": flt(r["qty"]),
				"source_warehouse": r.get("source_warehouse") or None})
	for r in data.expenses or []:
		if flt(r.get("amount")):
			dsr.append("expenses", {"expense_type": r["expense_type"], "amount": flt(r["amount"]),
				"description": r.get("description"), "paid_to": r.get("paid_to")})
	dsr.insert()

	changed = False
	for i, (row, src) in enumerate(zip(dsr.expenses, [r for r in data.expenses or [] if flt(r.get("amount"))])):
		url = _save_image(src.get("bill_image"), dsr, f"bill{i + 1}", "DSR")
		if url:
			row.bill = url
			changed = True
	for i, p in enumerate(data.photos or []):
		url = _save_image(p.get("image"), dsr, i + 1, "DSR")
		if url:
			dsr.append("photos", {"image": url, "caption": p.get("caption")})
			changed = True
	if changed:
		dsr.save()
	return _result(dsr)


@frappe.whitelist(methods=["POST"])
def submit_material_receipt(payload):
	data = _load(payload)
	done = _existing("Site Material Receipt", data.mobile_ref)
	if done:
		return dict(done, duplicate=1, status="Already received")
	_check_site(data.tower_site)

	smr = frappe.new_doc("Site Material Receipt")
	smr.update({
		"tower_site": data.tower_site, "receipt_type": data.receipt_type,
		"receipt_date": data.receipt_date or nowdate(), "purchase_order": data.purchase_order or None,
		"source_warehouse": data.source_warehouse or None, "indus_warehouse": data.indus_warehouse,
		"challan_no": data.challan_no, "vehicle_no": data.vehicle_no, "remarks": data.remarks,
		"latitude": flt(data.latitude), "longitude": flt(data.longitude), "source": "Mobile App",
		"mobile_ref": data.mobile_ref,
	})
	for r in data.get("items") or []:
		smr.append("items", {
			"item_code": r.get("item_code") or None, "item_name": r.get("item_name"),
			"received_qty": flt(r.get("received_qty")), "rejected_qty": flt(r.get("rejected_qty")),
			"uom": r.get("uom") or None, "serial_nos": r.get("serial_nos"),
			"purchase_order_item": r.get("purchase_order_item"), "remarks": r.get("remarks"),
		})
	if smr.receipt_type == "Indus Free-Issue Material":
		for row in smr.items:
			if row.uom and not frappe.db.exists("UOM", row.uom):
				row.uom = None
	smr.insert()
	changed = False
	for i, p in enumerate(data.photos or []):
		url = _save_image(p.get("image"), smr, i + 1, "SMR")
		if url:
			smr.append("photos", {"image": url, "caption": p.get("caption")})
			changed = True
	if changed:
		smr.save()
	return _result(smr)
