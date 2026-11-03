"""Sample demo data for Tower Site Execution - for TEST sites only.

Command line (from the bench folder):

    bench --site <site> tower-demo                       # load demo data into the site's company
    bench --site <site> tower-demo --company "My Co"     # pick the company
    bench --site <site> tower-demo --files-dir /path     # also import a real Indus PO (.xlsx + .pdf)
    bench --site <site> tower-demo --sites 12            # fewer sites (default 30)
    bench --site <site> tower-demo --clear               # remove everything the demo created

or, without the CLI:

    bench --site <site> execute tower_site_execution.demo.make_demo --kwargs "{'company': 'My Co'}"
    bench --site <site> execute tower_site_execution.demo.clear_demo

or from the desk: Tower Site Settings -> "Load Demo Data" (System Manager, runs in the background).

What it creates (all tagged as demo data so --clear can remove it):
  masters  : Indus Towers customer, 4 suppliers, site expense accounts + site imprest, central store,
             stock and service items, opening stock, a demo BOQ (Indus-style), demo users/employees
             (1 Project Manager, 3 Site Supervisors; password Demo@1234)
  sites    : N Tower Sites in the dashboard mix (by default 5 RFI Done, 5 RFI Pending, 5 Work Completed,
             10 Work In Progress, 5 Work Not Started), each with Sales Order (= Indus PO), project, tasks,
             site warehouse, feasibility survey, daily site reports (material + expenses), JCB/RMC
             purchase invoices, vendor PO + material receipts (PO delivery, store transfer, Indus
             free-issue), JMR + Sales Invoice, support visit
A fresh site without a company: the setup wizard is completed for you ("Demo Towers Pvt Ltd").
"""

import os
import random

import frappe
from frappe.utils import add_days, add_years, cint, flt, getdate, nowdate

DEMO_TAG = "DEMO DATA - tower_site_execution.demo"
CUSTOMER = "Indus Towers Limited"
SUPPLIERS = ("Shree Ganesh Earthmovers", "Palghar RMC Suppliers", "Konkan Steel Traders", "Om Sai Electricals")
PASSWORD = "Demo@1234"
SITE_PREFIX = "IN-DM"

# Indus-style BOQ used when no real PO is imported: code, description, task, uom, qty, rate, hsn/sac
DEMO_BOQ = [
	("DM-25-EXCAV", "Excavation in all types of soils by mechanized methods", "Civil Work", "Cubic Meter", 74.8, 130, "995433"),
	("DM-15-TMT", "Reinforcement steel Fe-500 incl. cutting, bending, laying", "Civil Work", "Kg", 1624.2, 71, "72142090"),
	("DM-25-RCC", "Reinforced cement concrete M20 for tower foundation", "Civil Work", "Cubic Meter", 17.16, 8250, "995428"),
	("DM-25-PCC", "Plain cement concrete M10 below foundation", "Civil Work", "Cubic Meter", 2.1, 5726, "995428"),
	("DM-2D-SHUTTER", "Shuttering for Eco / Eco-lite sites, MS sheet / plywood", "Civil Work", "Square Meter", 26.5, 290, "995428"),
	("DM-25-BACKFILL", "Backfilling in layers with compaction", "Civil Work", "Cubic Meter", 57.21, 60, "995433"),
	("DM-25-CURING", "Curing services at site", "Civil Work", "Nos", 8, 500, "998732"),
	("DM-22-EARTH", "Earthing, GI strip 25x3 incl. laying and jointing", "Civil Work", "Meter", 120, 90, "998732"),
	("DM-22-CABLE70", "Supply and laying of cable 70 sq mm 1C copper", "Electrical Work", "Meter", 10, 1206, "998732"),
	("DM-27-SOLARCIV", "Civil works for solar power system 5.4 kWp", "Other Services &Lots", "Nos", 1, 41000, "998732"),
	("DM-27-SOLARIC", "Installation, testing and commissioning of solar 5.4 kWp", "Other Services &Lots", "Nos", 1, 15000, "998732"),
	("DM-21-SMPS", "Electrical works with 12 kW SMPS and MPPT", "SMPS", "Nos", 1, 12500, "998732"),
	("DM-2E-SECURITY", "Site security during construction, up to 2 months", "Other Services &Lots", "Nos", 1, 21600, "998525"),
	("DM-29-PMC", "Project management charges", "Civil Work", "Nos", 1, 25000, "998399"),
]

STOCK_ITEMS = [
	("MAT-TMT-FE500", "TMT Steel Bar Fe-500", "Kg", 62, "72142090"),
	("MAT-CEMENT-OPC53", "Cement OPC 53 Grade (50 kg bag)", "Bag", 380, "25232930"),
	("MAT-GI-STRIP-25X3", "GI Strip 25x3 mm", "Meter", 55, "72104900"),
	("MAT-CU-CABLE-70", "Copper Cable 70 sq mm 1C", "Meter", 980, "85444999"),
	("MAT-HDPE-PIPE-2IN", "HDPE Pipe 2 inch", "Meter", 70, "39172390"),
	("MAT-AGGREGATE-20MM", "Aggregate 20 mm", "Cubic Meter", 1500, "25171010"),
]
SERVICE_ITEMS = [
	("SRV-JCB-HIRE", "JCB Hire Charges", "Hour", "997313"),
	("SRV-RMC-M20", "RMC M20 delivered at site", "Cubic Meter", "995428"),
	("SRV-SUBCON-LABOUR", "Subcontract Labour (civil)", "Nos", "998519"),
]
PEOPLE = [("Rahul", "Patil", "Project Manager"), ("Santosh", "Jadhav", "Site Supervisor"),
	("Imran", "Shaikh", "Site Supervisor"), ("Ganesh", "Vartak", "Site Supervisor")]
WORK_TEXT = [
	"Excavation for tower foundation pits completed with JCB",
	"PCC laid for tower footing, shuttering fixed",
	"Reinforcement binding and CIP levelling done",
	"RCC pour for tower foundation with RMC, curing started",
	"OD BTS slab casting completed",
	"Earthing pits and GI strip laying done",
	"Solar foundation and cable trench work",
	"Electrical cabling, SMPS and DCDB installation",
	"Site cleaning and backfilling done",
]
ZONES = [("Vasai", "Palghar"), ("Boisar", "Palghar"), ("Dahanu", "Palghar"), ("Bhiwandi", "Thane"), ("Kalyan", "Thane")]
OPCOS = ["Airtel", "Jio", "Vodafone Idea"]
AGE = {"RFI Done": 110, "RFI Pending": 70, "Work Completed": 50, "Work In Progress": 25, "Work Not Started": 4}


class Ctx(frappe._dict):
	pass


def log(msg):
	print(f"[tower-demo] {msg}", flush=True)


# =========================================================================== entry points
@frappe.whitelist()
def enqueue_demo(company=None, sites=30):
	"""Desk button on Tower Site Settings."""
	frappe.only_for("System Manager")
	frappe.enqueue("tower_site_execution.demo.make_demo", queue="long", timeout=3600,
		company=company, sites=cint(sites))
	return "queued"


def make_demo(company=None, files_dir=None, sites=30, email_domain="towerdemo.local"):
	random.seed(42)
	frappe.flags.mute_emails = True
	frappe.flags.in_demo = True
	today = getdate(nowdate())

	c = Ctx(today=today, email_domain=email_domain)
	c.company = _resolve_company(company)
	c.abbr = frappe.get_cached_value("Company", c.company, "abbr")
	c.store = f"Central Store - {c.abbr}"
	log(f"company: {c.company}")
	_ensure_fiscal_years(c, add_days(today, -260))
	_ensure_india_compliance_masters(c)
	make_masters(c)
	frappe.db.commit()

	real_site = None
	if files_dir:
		real_site = import_real_po(c, files_dir)
		frappe.db.commit()

	plan = _plan(cint(sites))
	if real_site:
		plan[0] = None  # the imported PO site is driven as one of the RFI Done sites
	for n, target in enumerate(plan, start=1):
		if not target:
			continue
		site_id = f"{SITE_PREFIX}{n:04d}"
		if frappe.db.exists("Tower Site", site_id):
			continue
		log(f"{site_id} -> {target}")
		site = _new_site(c, n, site_id, target)
		_drive(c, site, target)
		frappe.db.commit()

	if real_site and frappe.db.get_value("Tower Site", real_site, "status") == "Work Not Started":
		site = frappe.get_doc("Tower Site", real_site)
		_assign_team(c, site, 1)
		site.save()
		_drive(c, site, "RFI Done")
		frappe.db.commit()

	from tower_site_execution.tower_site_execution.doctype.tower_site.tower_site import daily_site_refresh

	daily_site_refresh()
	frappe.db.commit()
	summary = frappe.get_all("Tower Site", filters={"allotment_remarks": DEMO_TAG},
		fields=["status", {"COUNT": "name", "as": "sites"}], group_by="status")
	log(f"done: {summary}")
	log(f"logins (password {PASSWORD}): " + ", ".join(f"{p[0].lower()}@{email_domain}" for p in PEOPLE))
	return summary


def _plan(n):
	base = ["RFI Done"] * 5 + ["RFI Pending"] * 5 + ["Work Completed"] * 5 + ["Work In Progress"] * 10 + ["Work Not Started"] * 5
	if n >= len(base):
		return base + ["Work In Progress"] * (n - len(base))
	# keep the same mix, scaled down
	order = ["RFI Done", "RFI Pending", "Work Completed", "Work In Progress", "Work In Progress", "Work Not Started"]
	return [order[i % len(order)] for i in range(n)]


# =========================================================================== company & setup
def _resolve_company(company):
	if company:
		if not frappe.db.exists("Company", company):
			frappe.throw(f"Company {company} not found")
		return company
	company = (frappe.db.get_single_value("Tower Site Settings", "company")
		or frappe.defaults.get_global_default("company")
		or frappe.db.get_value("Company", {}, "name"))
	if company:
		return company
	log("no company yet - completing the setup wizard with 'Demo Towers Pvt Ltd'")
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	today = getdate(nowdate())
	fy_start = getdate(f"{today.year if today.month >= 4 else today.year - 1}-04-01")
	setup_complete({
		"language": "English", "country": "India", "timezone": "Asia/Kolkata", "currency": "INR",
		"company_name": "Demo Towers Pvt Ltd", "company_abbr": "DTPL", "chart_of_accounts": "Standard",
		"fy_start_date": str(fy_start), "fy_end_date": str(add_days(add_years(fy_start, 1), -1)),
		"full_name": "Demo Admin", "email": "admin@towerdemo.local", "password": "admin", "setup_demo": 0,
	})
	frappe.db.commit()
	return "Demo Towers Pvt Ltd"


def _ensure_fiscal_years(c, from_date):
	"""Back-dated demo documents need fiscal years covering the last ~9 months."""
	from erpnext.accounts.utils import get_fiscal_year

	d = getdate(from_date)
	while d <= c.today:
		try:
			get_fiscal_year(d, company=c.company)
		except Exception:
			start = getdate(f"{d.year if d.month >= 4 else d.year - 1}-04-01")
			name = f"{start.year}-{start.year + 1}"
			if not frappe.db.exists("Fiscal Year", name):
				fy = frappe.get_doc({"doctype": "Fiscal Year", "year": name, "year_start_date": start,
					"year_end_date": add_days(add_years(start, 1), -1)})
				fy.append("companies", {"company": c.company})
				fy.insert(ignore_permissions=True)
				log(f"created fiscal year {name}")
		d = add_days(d, 30)


def _ensure_india_compliance_masters(c):
	"""With India Compliance installed, items need a valid HSN/SAC and parties a GST category."""
	c.has_hsn = frappe.get_meta("Item").has_field("gst_hsn_code")
	c.has_gst_cat = frappe.get_meta("Customer").has_field("gst_category")
	if not c.has_hsn or not frappe.db.exists("DocType", "GST HSN Code"):
		return
	codes = {r[6] for r in DEMO_BOQ} | {r[4] for r in STOCK_ITEMS} | {r[3] for r in SERVICE_ITEMS}
	for code in codes:
		if not frappe.db.exists("GST HSN Code", code):
			frappe.get_doc({"doctype": "GST HSN Code", "hsn_code": code, "description": "Demo"}).insert(ignore_permissions=True)


# =========================================================================== masters
def _get_or_insert(doctype, name, values):
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	doc = frappe.get_doc(dict(values, doctype=doctype))
	doc.flags.ignore_mandatory = doctype in ("Customer", "Supplier")
	doc.insert(ignore_permissions=True)
	return doc


def _group_account(c, names, root_type):
	for n in names:
		acc = frappe.db.get_value("Account", {"company": c.company, "is_group": 1, "account_name": n, "root_type": root_type})
		if acc:
			return acc
	return frappe.db.get_value("Account", {"company": c.company, "is_group": 1, "root_type": root_type,
		"parent_account": ["is", "set"]}, order_by="lft")


def _account(c, name, parent, account_type=None):
	full = f"{name} - {c.abbr}"
	if not frappe.db.exists("Account", full):
		frappe.get_doc({"doctype": "Account", "account_name": name, "parent_account": parent, "company": c.company,
			"account_type": account_type, "is_group": 0}).insert(ignore_permissions=True)
	return full


def _item(c, code, name, uom, group, is_stock, hsn, rate=None, sales=False):
	if frappe.db.exists("Item", code):
		return
	values = {"item_code": code, "item_name": name, "description": name, "item_group": group, "stock_uom": uom,
		"is_stock_item": is_stock, "is_sales_item": 1 if sales else 0, "is_purchase_item": 0 if sales else 1,
		"include_item_in_manufacturing": 0}
	if rate:
		values.update({"valuation_rate": rate, "standard_rate": rate})
	if c.has_hsn and hsn:
		values["gst_hsn_code"] = hsn
	frappe.get_doc(dict(values, doctype="Item")).insert(ignore_permissions=True)


def make_masters(c):
	gst = {"gst_category": "Unregistered"} if c.has_gst_cat else {}
	_get_or_insert("Customer", CUSTOMER, {"customer_name": CUSTOMER, "customer_type": "Company",
		"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}) or "All Customer Groups",
		"territory": frappe.db.get_value("Territory", {"is_group": 0}) or "All Territories", **gst})
	for s in SUPPLIERS:
		_get_or_insert("Supplier", s, {"supplier_name": s,
			"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}) or "All Supplier Groups", **gst})

	cash_parent = _group_account(c, ["Cash In Hand", "Cash"], "Asset")
	direct = _group_account(c, ["Direct Expenses", "Expenses"], "Expense")
	c.imprest = _account(c, "Site Imprest", cash_parent, "Cash")
	for et, acc in {
		"Labour Wages": "Site Labour Wages", "Earth Moving Equipment Hire": "Site Equipment Hire",
		"Diesel / Fuel": "Site Fuel", "Transport & Freight": "Site Transport", "Food & Lodging": "Site Food & Lodging",
		"Local Purchase": "Site Local Purchase", "Site Security": "Site Security Charges",
		"Water / Curing": "Site Water & Curing", "Repair & Maintenance": "Site Repair & Maintenance",
		"Miscellaneous": "Site Misc Expenses",
	}.items():
		if not frappe.db.exists("Site Expense Type", et):
			frappe.get_doc({"doctype": "Site Expense Type", "expense_type": et}).insert(ignore_permissions=True)
		if not frappe.db.get_value("Site Expense Type", et, "expense_account"):
			frappe.db.set_value("Site Expense Type", et, "expense_account", _account(c, acc, direct))

	if not frappe.db.exists("Warehouse", c.store):
		root = frappe.db.get_value("Warehouse", {"company": c.company, "is_group": 1, "parent_warehouse": ["in", ["", None]]})
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": "Central Store", "company": c.company,
			"parent_warehouse": root}).insert(ignore_permissions=True)

	for uom in ("Kg", "Meter", "Cubic Meter", "Square Meter", "Nos", "Hour", "Bag"):
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom, "must_be_whole_number": uom in ("Nos", "Bag")}).insert(
				ignore_permissions=True)
	from tower_site_execution.install import ensure_item_group

	boq_group = ensure_item_group()
	mat_group = frappe.db.get_value("Item Group", {"is_group": 0, "name": ["!=", boq_group]}) or "All Item Groups"
	for code, name, task, uom, qty, rate, hsn in DEMO_BOQ:
		_item(c, code, name, uom, boq_group, 0, hsn, sales=True)
	for code, name, uom, rate, hsn in STOCK_ITEMS:
		_item(c, code, name, uom, mat_group, 1, hsn, rate)
	for code, name, uom, hsn in SERVICE_ITEMS:
		_item(c, code, name, uom, mat_group, 0, hsn)

	s = frappe.get_single("Tower Site Settings")
	s.company = c.company
	s.indus_customer = CUSTOMER
	s.boq_item_group = boq_group
	s.default_site_warehouse = s.default_site_warehouse or c.store
	s.expense_credit_account = s.expense_credit_account or c.imprest
	s.default_cost_center = s.default_cost_center or frappe.get_cached_value("Company", c.company, "cost_center")
	s.support_months = s.support_months or 12
	s.submit_sales_order = 1
	s.create_site_warehouse = 1
	s.save(ignore_permissions=True)
	c.store = s.default_site_warehouse

	if not frappe.db.exists("Stock Entry", {"remarks": DEMO_TAG + " opening stock", "docstatus": 1, "company": c.company}):
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Receipt"
		se.purpose = "Material Receipt"
		se.company = c.company
		se.set_posting_time = 1
		se.posting_date = add_days(c.today, -250)
		se.remarks = DEMO_TAG + " opening stock"
		for code, _n, _u, rate, _h in STOCK_ITEMS:
			se.append("items", {"item_code": code, "qty": 20000, "t_warehouse": c.store, "basic_rate": rate})
		se.insert(ignore_permissions=True)
		se.submit()

	c.emps = {}
	for first, last, role in PEOPLE:
		email = f"{first.lower()}@{c.email_domain}"
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "last_name": last,
				"send_welcome_email": 0, "new_password": PASSWORD, "user_type": "System User",
				"bio": DEMO_TAG})
			u.insert(ignore_permissions=True)
			roles = ["Site Project Manager", "Projects User", "Sales User", "Purchase User", "Stock User",
				"Accounts User"] if role == "Project Manager" else ["Site Supervisor"]
			u.add_roles(*[r for r in roles + ["Employee"] if frappe.db.exists("Role", r)])
		emp = frappe.db.get_value("Employee", {"user_id": email})
		if not emp:
			e = frappe.get_doc({"doctype": "Employee", "first_name": first, "last_name": last, "gender": "Male",
				"date_of_birth": "1990-01-01", "date_of_joining": add_days(c.today, -400), "company": c.company,
				"user_id": email, "status": "Active", "cell_number": "98" + str(random.randint(10000000, 99999999))})
			e.insert(ignore_permissions=True)
			emp = e.name
		c.emps.setdefault(role, []).append(emp)
	c.pm = c.emps["Project Manager"][0]
	c.sups = c.emps["Site Supervisor"]



# =========================================================================== sites
def _assign_team(c, site, n):
	site.append("team", {"employee": c.pm, "role": "Project Manager"})
	site.append("team", {"employee": c.sups[n % len(c.sups)], "role": "Site Supervisor"})


def _new_site(c, n, site_id, target):
	zone, district = ZONES[n % len(ZONES)]
	alloc = add_days(c.today, -(AGE[target] + random.randint(0, 20)))
	site = frappe.get_doc({"doctype": "Tower Site", "indus_site_id": site_id,
		"reference_id": f"R/NN-10{random.randint(10000, 99999)}",
		"nominal_name": f"{zone}_{random.choice(['NB', 'RE', 'NB2'])}_{n:02d}",
		"principal_opco": random.choice(OPCOS), "category": random.choice(["New Build", "New Build", "Relocation"]),
		"product_type": "New Nominal Site Request",
		"tower_type": random.choice(["GBT", "RT Tower", "GBM"]), "tower_height": random.choice([15, 21, 30, 40]),
		"circle": "Maharashtra & Goa", "region": "Region 2", "zone": zone, "district": district,
		"latitude": round(19.2 + random.random() * 0.8, 6), "longitude": round(72.7 + random.random() * 0.4, 6),
		"site_address": f"Survey no. {random.randint(10, 400)}, near {zone} MIDC, {district}",
		"allocation_date": alloc, "customer": CUSTOMER, "zpm_name": "Prabhash Chandra",
		"de_name": "Ravi Singh", "fse_name": "Anil Ray", "tsp_team": "Demo TSP", "allotment_remarks": DEMO_TAG})
	_assign_team(c, site, n)
	site.insert(ignore_permissions=True)
	return _sales_order(c, site, random.uniform(0.7, 1.4))


def _sales_order(c, site, factor):
	so = frappe.new_doc("Sales Order")
	so.company = c.company
	so.customer = CUSTOMER
	so.transaction_date = site.allocation_date
	so.delivery_date = add_days(site.allocation_date, 45)
	so.po_no = f"DEMO-{site.name}"
	so.po_date = site.allocation_date
	so.tower_site = site.name
	so.project = site.project
	for i, (code, _name, task, uom, qty, rate, _h) in enumerate(DEMO_BOQ, start=1):
		q = qty * factor if uom not in ("Nos",) else qty
		q = round(q) if uom in ("Nos", "Bag") else round(q, 2)
		so.append("items", {"item_code": code, "qty": max(q, 1), "rate": rate, "uom": uom, "project": site.project,
			"delivery_date": so.delivery_date, "indus_task_name": task, "indus_line_no": i})
	so.insert(ignore_permissions=True)
	so.submit()
	site.reload()
	site.update({"sales_order": so.name, "po_no": so.po_no, "po_date": so.po_date})
	site.set("boq", [])
	for it in so.items:
		site.append("boq", {"line_no": it.indus_line_no, "item_code": it.item_code, "description": it.description,
			"task_name": it.indus_task_name, "uom": it.uom, "po_qty": it.qty, "rate": it.rate, "so_detail": it.name})
	site.save()
	frappe.db.set_value("Project", site.project, "sales_order", so.name)
	return site


def _attach(path, doc):
	with open(path, "rb") as f:
		fd = frappe.get_doc({"doctype": "File", "file_name": os.path.basename(path), "attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name, "content": f.read(), "is_private": 1})
		fd.insert(ignore_permissions=True)
	return fd.file_url


def import_real_po(c, files_dir):
	"""Imports a real Indus PO (the .xlsx line export and the PDF found in files_dir)."""
	existing = frappe.db.get_value("Indus PO Import", {"status": "Imported"}, "tower_site")
	if existing:
		return existing
	files = os.listdir(files_dir)
	xlsx = next((f for f in files if f.lower().endswith(".xlsx")), None)
	pdf = next((f for f in files if f.lower().endswith(".pdf")), None)
	if not xlsx:
		frappe.throw(f"No .xlsx PO export in {files_dir}")
	imp = frappe.get_doc({"doctype": "Indus PO Import"}).insert(ignore_permissions=True)
	imp.po_file = _attach(os.path.join(files_dir, xlsx), imp)
	if pdf:
		imp.po_pdf = _attach(os.path.join(files_dir, pdf), imp)
	imp.save()
	imp.parse_files()
	result = imp.create_documents()
	site = frappe.get_doc("Tower Site", result["tower_site"])
	site.allotment_remarks = DEMO_TAG
	site.save()
	log(f"imported real PO into {site.name}")
	return site.name


# =========================================================================== activity
def _dsr(c, site, day, sup, fraction, milestone=None, final=False):
	dsr = frappe.new_doc("Daily Site Report")
	dsr.tower_site = site.name
	dsr.report_date = day
	dsr.supervisor = sup
	dsr.labour_count = random.randint(4, 14)
	dsr.work_completed = random.choice(WORK_TEXT)
	dsr.milestone_achieved = milestone
	dsr.latitude, dsr.longitude = site.latitude, site.longitude
	for r in site.boq:
		remaining = flt(r.po_qty) - flt(r.executed_qty)
		if remaining <= 0:
			continue
		q = remaining if final else min(round(r.po_qty * fraction, 2), remaining)
		if r.uom in ("Nos", "Bag"):
			q = min(max(1, round(q)), remaining) if final or random.random() < fraction * 3 else 0
		if q > 0:
			dsr.append("work_items", {"item_code": r.item_code, "qty_completed": q, "uom": r.uom})
	dsr.append("materials", {"item_code": "MAT-TMT-FE500", "qty": random.randint(60, 200), "source_warehouse": c.store})
	dsr.append("materials", {"item_code": "MAT-CEMENT-OPC53", "qty": random.randint(5, 25), "source_warehouse": c.store})
	if random.random() < 0.5:
		dsr.append("materials", {"item_code": "MAT-GI-STRIP-25X3", "qty": random.randint(10, 40), "source_warehouse": c.store})
	dsr.append("expenses", {"expense_type": "Labour Wages", "amount": dsr.labour_count * 650, "paid_to": "Labour contractor"})
	dsr.append("expenses", {"expense_type": "Food & Lodging", "amount": random.randint(6, 18) * 100})
	if random.random() < 0.4:
		dsr.append("expenses", {"expense_type": "Diesel / Fuel", "amount": random.randint(15, 40) * 100, "paid_to": "Petrol pump"})
	dsr.pending_work = "" if final else "Continue as per plan"
	dsr.remarks = "Demo"
	dsr.insert(ignore_permissions=True)
	dsr.submit()
	site.reload()


def _purchase_invoice(c, site, day):
	pi = frappe.new_doc("Purchase Invoice")
	pi.company = c.company
	pi.supplier = "Shree Ganesh Earthmovers"
	pi.set_posting_time = 1
	pi.posting_date = day
	pi.bill_no = f"SGE/{site.name}/{random.randint(100, 999)}"
	pi.bill_date = day
	pi.project = site.project
	pi.remarks = DEMO_TAG
	pi.append("items", {"item_code": "SRV-JCB-HIRE", "qty": random.randint(8, 22), "rate": 950, "project": site.project})
	if random.random() < 0.6:
		pi.append("items", {"item_code": "SRV-RMC-M20", "qty": random.randint(8, 18), "rate": 5200, "project": site.project})
	pi.insert(ignore_permissions=True)
	pi.submit()


def _material_receipts(c, site, day, sup):
	"""Vendor PO delivered to site, a store transfer and Indus free-issue material, as reported from the app."""
	site_wh = frappe.db.get_value("Tower Site", site.name, "site_warehouse")
	po = frappe.get_doc({"doctype": "Purchase Order", "company": c.company, "supplier": "Konkan Steel Traders",
		"transaction_date": add_days(day, -3), "schedule_date": day, "tower_site": site.name, "project": site.project,
		"set_warehouse": site_wh or c.store,
		"items": [
			{"item_code": "MAT-TMT-FE500", "qty": 1200, "rate": 62, "schedule_date": day, "project": site.project},
			{"item_code": "MAT-CEMENT-OPC53", "qty": 100, "rate": 380, "schedule_date": day, "project": site.project}]})
	po.insert(ignore_permissions=True)
	po.submit()
	common = {"doctype": "Site Material Receipt", "tower_site": site.name, "receipt_date": day, "received_by": sup,
		"latitude": site.latitude, "longitude": site.longitude, "remarks": "Demo"}
	vendor = frappe.get_doc(dict(common, receipt_type="Vendor Delivery against PO", purchase_order=po.name,
		challan_no=f"KST/{random.randint(100, 999)}", vehicle_no=f"MH48 {random.choice('ABCDEFG')}{random.choice('JKLMN')} {random.randint(1000, 9999)}",
		items=[{"item_code": d.item_code, "purchase_order_item": d.name, "received_qty": d.qty - (5 if d.uom == "Bag" else 0),
			"rejected_qty": 5 if d.uom == "Bag" else 0} for d in po.items]))
	vendor.insert(ignore_permissions=True)
	vendor.submit()
	pr_name = frappe.db.get_value("Site Material Receipt", vendor.name, "purchase_receipt")
	if pr_name and frappe.db.get_value("Purchase Receipt", pr_name, "docstatus") == 0:
		pr = frappe.get_doc("Purchase Receipt", pr_name)
		pr.set_posting_time = 1
		pr.posting_date = day
		pr.submit()  # stores has checked it: the material now shows in the site warehouse
	if site_wh and site_wh != c.store:
		transfer = frappe.get_doc(dict(common, receipt_type="Transfer from Store", source_warehouse=c.store,
			challan_no=f"DC/{random.randint(100, 999)}", items=[{"item_code": "MAT-CU-CABLE-70", "received_qty": 30}]))
		transfer.insert(ignore_permissions=True)
		transfer.submit()
	indus = frappe.get_doc(dict(common, receipt_type="Indus Free-Issue Material", indus_warehouse="MAW - Pune Warehouse",
		challan_no=f"INDUS/DC/{random.randint(10000, 99999)}", items=[
			{"item_name": "SMPS 12kW with MPPT", "received_qty": 1, "uom": "Nos", "serial_nos": f"SMPS-{random.randint(10000, 99999)}"},
			{"item_name": "Li-ion Battery Bank 48V", "received_qty": 2, "uom": "Nos",
			 "serial_nos": f"BB-{random.randint(1000, 4999)}\nBB-{random.randint(5000, 9999)}"},
			{"item_name": "Solar panel 540 Wp", "received_qty": 10, "uom": "Nos"}]))
	indus.insert(ignore_permissions=True)
	indus.submit()
	# one receipt left for the PM to approve, as it would arrive from the app
	frappe.get_doc(dict(common, receipt_type="Indus Free-Issue Material", indus_warehouse="MAW - Pune Warehouse",
		challan_no=f"INDUS/DC/{random.randint(10000, 99999)}",
		items=[{"item_name": "Tower section kit 30m", "received_qty": 1, "uom": "Nos"}])).insert(ignore_permissions=True)


def _jmr_and_invoice(c, site, day):
	from tower_site_execution.tower_site_execution.doctype.joint_measurement_record.joint_measurement_record import (
		make_sales_invoice,
	)

	jmr = frappe.new_doc("Joint Measurement Record")
	jmr.update({"tower_site": site.name, "jmr_date": day, "indus_representative": "Indus FSE",
		"company_representative": c.pm, "remarks": "Demo"})
	jmr.get_boq_items()
	jmr.insert(ignore_permissions=True)
	jmr.submit()
	si = make_sales_invoice(jmr.name)
	si.set_posting_time = 1
	si.posting_date = day
	si.due_date = add_days(day, 30)
	si.remarks = DEMO_TAG
	si.insert(ignore_permissions=True)
	si.submit()


def _drive(c, site, target):
	"""Walk a site from allocation to the target status with back-dated documents."""
	sup = next(t.employee for t in site.team if t.role == "Site Supervisor")
	alloc = getdate(site.allocation_date)
	site.set_site_status("hoto", add_days(alloc, random.choice([1, 2, 3])))
	survey = frappe.get_doc({"doctype": "Site Feasibility Survey", "tower_site": site.name,
		"survey_date": add_days(alloc, 2), "surveyed_by": sup,
		"soil_type": random.choice(["Normal Soil", "Hard Soil", "Soft Rock"]),
		"site_accessible": "Vehicle up to site", "power_availability": random.choice(["EB available", "EB nearby"]),
		"findings": "<p>Site workable. Landlord cooperative.</p>", "landlord_cooperative": 1})
	survey.insert(ignore_permissions=True)
	survey.submit()
	if target == "Work Not Started":
		return
	survey.indus_decision = "Go Ahead"
	survey.decision_date = add_days(alloc, 3)
	survey.save()
	site.reload()

	start = add_days(alloc, random.choice([4, 5, 6]))
	plan = [(0, None), (5, "C1"), (9, "C2"), (11, "C3"), (14, "E1"), (15, "Solar I&C")]
	steps = random.randint(2, 4) if target == "Work In Progress" else len(plan)
	for i, (offset, ms) in enumerate(plan[:steps]):
		day = add_days(start, offset + random.choice([0, 0, 1, 2]))
		if getdate(day) > c.today:
			break
		final = target != "Work In Progress" and i == len(plan) - 1
		_dsr(c, site, day, sup, 0.18, milestone=ms, final=final)
		if i == 1:
			_purchase_invoice(c, site, day)
			_material_receipts(c, site, day, sup)
	site.reload()
	if target == "Work In Progress":
		return
	done = add_days(start, 17)
	site.set_site_status("complete", min(getdate(done), c.today))
	if target == "Work Completed":
		return
	site.reload()
	site.set_site_status("raise_rfi", min(getdate(add_days(done, 2)), c.today))
	site.reload()
	_jmr_and_invoice(c, site, min(getdate(add_days(done, 3)), c.today))
	if target == "RFI Pending":
		return
	site.reload()
	site.set_site_status("rfi_done", min(getdate(add_days(done, 6)), c.today))
	site.reload()
	visit = frappe.get_doc({"doctype": "Site Support Visit", "tower_site": site.name,
		"visit_date": min(getdate(add_days(done, 30)), c.today), "visit_type": "Routine Inspection", "engineer": sup,
		"observations": "Earthing resistance checked, foundation bolts tight, solar panels cleaned",
		"action_taken": "No issues", "next_visit_date": add_days(done, 120)})
	visit.append("expenses", {"expense_type": "Transport & Freight", "amount": 900})
	visit.insert(ignore_permissions=True)
	visit.submit()


# =========================================================================== clean-up
LEDGERS = ("GL Entry", "Stock Ledger Entry", "Payment Ledger Entry", "Repost Item Valuation")


class _InlineLinkCleanup:
	"""frappe.delete_doc queues one background job per deleted document to clean comments,
	versions etc. Hundreds of deletes would overflow the queue, so run those inline instead."""

	def __enter__(self):
		self._enqueue = frappe.enqueue

		def enqueue(method, *args, **kwargs):
			if method == "frappe.model.delete_doc.delete_dynamic_links":
				from frappe.model.delete_doc import delete_dynamic_links

				return delete_dynamic_links(kwargs["doctype"], kwargs["name"])
			return self._enqueue(method, *args, **kwargs)

		frappe.enqueue = enqueue
		return self

	def __exit__(self, *exc):
		frappe.enqueue = self._enqueue


def clear_demo(masters=False):
	"""Cancel and delete every document the demo created (sites tagged as demo data).
	masters=True also removes demo items, suppliers and users/employees."""
	with _InlineLinkCleanup():
		return _clear_demo(masters)


def _clear_demo(masters=False):
	frappe.flags.mute_emails = True
	sites = frappe.get_all("Tower Site", filters={"allotment_remarks": DEMO_TAG}, fields=["name", "project", "site_warehouse"])
	names = [s.name for s in sites]
	projects = [s.project for s in sites if s.project]
	log(f"removing {len(names)} demo sites")
	if not names:
		return "nothing to clear"

	def by_site(dt):
		return frappe.get_all(dt, filters={"tower_site": ["in", names]}, pluck="name")

	def by_project(dt, field="project"):
		return frappe.get_all(dt, filters={field: ["in", projects or [""]]}, pluck="name") if projects else []

	pr = frappe.get_all("Site Material Receipt", filters={"tower_site": ["in", names]}, pluck="purchase_receipt")
	stages = [
		("Site Support Visit", by_site("Site Support Visit")),
		("Sales Invoice", sorted(set(by_site("Sales Invoice") + by_project("Sales Invoice")))),
		("Joint Measurement Record", by_site("Joint Measurement Record")),
		("Site Material Receipt", by_site("Site Material Receipt")),
		("Purchase Receipt", [p for p in pr if p]),
		("Daily Site Report", by_site("Daily Site Report")),
		("Purchase Invoice", by_project("Purchase Invoice")),
		("Purchase Order", sorted(set(by_site("Purchase Order") + by_project("Purchase Order")))),
		("Stock Entry", by_project("Stock Entry")),
		("Journal Entry", list({r.parent for r in frappe.get_all("Journal Entry Account",
			filters={"project": ["in", projects or [""]]}, fields=["parent"])})),
		("Sales Order", by_site("Sales Order")),
		("Site Feasibility Survey", by_site("Site Feasibility Survey")),
		("Indus PO Import", by_site("Indus PO Import")),
	]
	removed = {}
	for dt, docs in stages:
		for name in docs:
			_cancel_and_delete(dt, name)
		removed[dt] = len(docs)
		frappe.db.commit()
	for name in names:
		frappe.db.set_value("Tower Site", name, {"project": None, "sales_order": None})
	for task in frappe.get_all("Task", filters={"project": ["in", projects or [""]]}, pluck="name"):
		frappe.delete_doc("Task", task, force=True, ignore_permissions=True)
	for p in projects:
		frappe.delete_doc("Project", p, force=True, ignore_permissions=True)
	for s in sites:
		frappe.delete_doc("Tower Site", s.name, force=True, ignore_permissions=True)
		if s.site_warehouse and not frappe.db.exists("Stock Ledger Entry", {"warehouse": s.site_warehouse, "is_cancelled": 0}):
			frappe.db.delete("Bin", {"warehouse": s.site_warehouse})
			frappe.delete_doc("Warehouse", s.site_warehouse, force=True, ignore_permissions=True)
	frappe.db.commit()

	if cint(masters):
		_clear_masters()
	log(f"removed: {removed}")
	return removed


def _cancel_and_delete(dt, name):
	if not frappe.db.exists(dt, name):
		return
	doc = frappe.get_doc(dt, name)
	doc.flags.ignore_permissions = True
	doc.flags.ignore_links = True
	if doc.docstatus == 1:
		doc.flags.ignore_links = True
		doc.ignore_linked_doctypes = (*LEDGERS, "Sales Invoice", "Purchase Receipt", "Payment Entry",
			"Site Material Receipt", "Joint Measurement Record", "Daily Site Report", "Stock Entry", "Journal Entry",
			"Purchase Invoice", "Purchase Order", "Sales Order", "Project", "Tower Site", "Indus PO Import")
		doc.cancel()
	for ledger in LEDGERS:
		field = "voucher_no" if ledger != "Repost Item Valuation" else "voucher_no"
		if frappe.db.has_column(ledger, field):
			frappe.db.delete(ledger, {"voucher_type": dt, field: name})
	frappe.delete_doc(dt, name, force=True, ignore_permissions=True, delete_permanently=True)


def _clear_masters():
	opening = frappe.get_all("Stock Entry", filters={"remarks": DEMO_TAG + " opening stock"}, pluck="name")
	for name in opening:
		_cancel_and_delete("Stock Entry", name)
	for code in [r[0] for r in DEMO_BOQ] + [r[0] for r in STOCK_ITEMS] + [r[0] for r in SERVICE_ITEMS]:
		if frappe.db.exists("Item", code):
			frappe.db.delete("Bin", {"item_code": code})
			frappe.delete_doc("Item", code, force=True, ignore_permissions=True)
	for s in SUPPLIERS:
		if frappe.db.exists("Supplier", s):
			frappe.delete_doc("Supplier", s, force=True, ignore_permissions=True)
	for user in frappe.get_all("User", filters={"bio": DEMO_TAG}, pluck="name"):
		for emp in frappe.get_all("Employee", filters={"user_id": user}, pluck="name"):
			frappe.delete_doc("Employee", emp, force=True, ignore_permissions=True)
		frappe.delete_doc("User", user, force=True, ignore_permissions=True)
	frappe.db.commit()
	log("demo masters removed (customer, accounts and warehouses kept)")
