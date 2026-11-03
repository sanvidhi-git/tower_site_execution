"""Demo data for a Crystal Interiors walkthrough.

    bench --site <site> execute tower_site_execution.demo.setup_company      # fresh site only
    bench --site <site> execute tower_site_execution.demo.make_demo --kwargs "{'files_dir': '/path/to/indus/files'}"

Creates masters, imports the real Indus PO (IN-3613941) through Indus PO Import and
creates 30 sites in the status mix of the client's dashboard (5/10/5/5/5) with daily
reports, expenses, material issues, purchases, JMRs and invoices so every report has data.
Everything except the imported PO is synthetic demo data.
"""

import os
import random

import frappe
from frappe.utils import add_days, getdate, nowdate

COMPANY = "Crystal Interiors"
ABBR = "CI"
CUSTOMER = "Indus Towers Limited"
WAREHOUSE = f"Palghar Site Store - {ABBR}"
TODAY = getdate(nowdate())


def setup_company():
	from frappe.desk.page.setup_wizard.setup_wizard import setup_complete

	if frappe.db.exists("Company", COMPANY):
		return "exists"
	setup_complete(
		{
			"language": "English",
			"country": "India",
			"timezone": "Asia/Kolkata",
			"currency": "INR",
			"company_name": COMPANY,
			"company_abbr": ABBR,
			"chart_of_accounts": "Standard",
			"fy_start_date": "2026-04-01",
			"fy_end_date": "2027-03-31",
			"full_name": "Demo Admin",
			"email": "admin@crystal.local",
			"password": "admin",
			"setup_demo": 0,
		}
	)
	frappe.db.commit()
	return "done"


# --------------------------------------------------------------------------- helpers
def _get_or_insert(doctype, name, values):
	if frappe.db.exists(doctype, name):
		return frappe.get_doc(doctype, name)
	doc = frappe.get_doc(dict(values, doctype=doctype))
	doc.insert(ignore_permissions=True)
	return doc


def _account(name, parent, account_type=None, root=None):
	full = f"{name} - {ABBR}"
	if not frappe.db.exists("Account", full):
		frappe.get_doc(
			{
				"doctype": "Account",
				"account_name": name,
				"parent_account": parent,
				"company": COMPANY,
				"account_type": account_type,
				"is_group": 0,
			}
		).insert(ignore_permissions=True)
	return full


def _parent(account_name_like, root_type):
	return frappe.db.get_value(
		"Account", {"company": COMPANY, "is_group": 1, "account_name": account_name_like, "root_type": root_type}
	)


def make_masters():
	_get_or_insert("Customer", CUSTOMER, {"customer_name": CUSTOMER, "customer_type": "Company",
		"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}) or "All Customer Groups",
		"territory": "India" if frappe.db.exists("Territory", "India") else "All Territories"})
	for s in ("Shree Ganesh Earthmovers", "Palghar RMC Suppliers", "Konkan Steel Traders", "Om Sai Electricals"):
		_get_or_insert("Supplier", s, {"supplier_name": s, "supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0})})

	cash_parent = _parent("Cash In Hand", "Asset")
	direct = _parent("Direct Expenses", "Expense") or _parent("Expenses", "Expense")
	imprest = _account("Site Imprest", cash_parent, "Cash")
	acc = {
		"Labour Wages": _account("Site Labour Wages", direct),
		"Earth Moving Equipment Hire": _account("Site Equipment Hire", direct),
		"Diesel / Fuel": _account("Site Fuel", direct),
		"Transport & Freight": _account("Site Transport", direct),
		"Food & Lodging": _account("Site Food & Lodging", direct),
		"Local Purchase": _account("Site Local Purchase", direct),
		"Site Security": _account("Site Security Charges", direct),
		"Water / Curing": _account("Site Water & Curing", direct),
		"Repair & Maintenance": _account("Site Repair & Maintenance", direct),
		"Miscellaneous": _account("Site Misc Expenses", direct),
	}
	for et, account in acc.items():
		frappe.db.set_value("Site Expense Type", et, "expense_account", account)

	if not frappe.db.exists("Warehouse", WAREHOUSE):
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": "Palghar Site Store", "company": COMPANY,
			"parent_warehouse": f"All Warehouses - {ABBR}"}).insert(ignore_permissions=True)

	for uom in ("Kg", "Meter", "Cubic Meter", "Nos", "Hour", "Bag"):
		if not frappe.db.exists("UOM", uom):
			frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)
	group = frappe.db.get_value("Item Group", {"is_group": 0, "name": ["!=", "Indus BOQ Items"]}) or "All Item Groups"
	stock_items = [
		("MAT-TMT-FE500", "TMT Steel Bar Fe-500", "Kg", 62),
		("MAT-CEMENT-OPC53", "Cement OPC 53 Grade (50 kg bag)", "Bag", 380),
		("MAT-GI-STRIP-25X3", "GI Strip 25x3 mm", "Meter", 55),
		("MAT-CU-CABLE-70", "Copper Cable 70 sq mm 1C", "Meter", 980),
		("MAT-HDPE-PIPE-2IN", "HDPE Pipe 2 inch", "Meter", 70),
		("MAT-AGGREGATE-20MM", "Aggregate 20 mm", "Cubic Meter", 1500),
	]
	for code, name, uom, rate in stock_items:
		_get_or_insert("Item", code, {"item_code": code, "item_name": name, "item_group": group, "stock_uom": uom,
			"is_stock_item": 1, "valuation_rate": rate, "standard_rate": rate})
	for code, name, uom in (("SRV-JCB-HIRE", "JCB Hire Charges", "Hour"), ("SRV-RMC-M20", "RMC M20 delivered at site", "Cubic Meter"),
			("SRV-SUBCON-LABOUR", "Subcontract Labour (civil)", "Nos")):
		_get_or_insert("Item", code, {"item_code": code, "item_name": name, "item_group": group, "stock_uom": uom,
			"is_stock_item": 0, "is_purchase_item": 1})

	if not frappe.db.exists("Stock Entry", {"remarks": "Demo opening stock", "docstatus": 1}):
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Receipt"
		se.company = COMPANY
		se.set_posting_time = 1
		se.posting_date = "2026-04-01"
		se.remarks = "Demo opening stock"
		for code, _n, _u, rate in stock_items:
			se.append("items", {"item_code": code, "qty": 20000, "t_warehouse": WAREHOUSE, "basic_rate": rate})
		se.insert(ignore_permissions=True)
		se.submit()

	people = [("Rahul", "Patil", "Project Manager"), ("Santosh", "Jadhav", "Site Supervisor"),
		("Imran", "Shaikh", "Site Supervisor"), ("Ganesh", "Vartak", "Site Supervisor"), ("Vikas", "More", "Electrician")]
	emps = {}
	for first, last, role in people:
		email = f"{first.lower()}@crystal.local"
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "last_name": last,
				"send_welcome_email": 0, "new_password": "Crystal@123", "user_type": "System User"})
			u.insert(ignore_permissions=True)
			u.add_roles("Site Project Manager" if role == "Project Manager" else "Site Supervisor", "Employee")
			if role == "Project Manager":
				u.add_roles("Projects User", "Sales User", "Purchase User", "Stock User", "Accounts User")
		emp = frappe.db.get_value("Employee", {"user_id": email})
		if not emp:
			e = frappe.get_doc({"doctype": "Employee", "first_name": first, "last_name": last, "gender": "Male",
				"date_of_birth": "1990-01-01", "date_of_joining": "2024-04-01", "company": COMPANY,
				"user_id": email, "status": "Active", "cell_number": "98" + str(random.randint(10000000, 99999999))})
			e.insert(ignore_permissions=True)
			emp = e.name
		emps[role if role != "Site Supervisor" else f"Supervisor {first}"] = emp

	s = frappe.get_single("Tower Site Settings")
	s.company = COMPANY
	s.indus_customer = CUSTOMER
	s.boq_item_group = "Indus BOQ Items"
	s.default_site_warehouse = WAREHOUSE
	s.expense_credit_account = imprest
	s.default_cost_center = frappe.get_cached_value("Company", COMPANY, "cost_center")
	s.support_months = 12
	s.submit_sales_order = 1
	s.save(ignore_permissions=True)
	frappe.db.commit()
	return emps


# ------------------------------------------------------------------------ flows
def _attach(path, doc):
	with open(path, "rb") as f:
		fd = frappe.get_doc({"doctype": "File", "file_name": os.path.basename(path), "attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name, "content": f.read(), "is_private": 1})
		fd.insert(ignore_permissions=True)
	return fd.file_url


def import_real_po(files_dir):
	existing = frappe.db.get_value("Indus PO Import", {"status": "Imported"})
	if existing:
		return frappe.db.get_value("Indus PO Import", existing, "tower_site")
	xlsx = next(f for f in os.listdir(files_dir) if f.lower().endswith(".xlsx"))
	pdf = next(f for f in os.listdir(files_dir) if f.lower().endswith(".pdf"))
	imp = frappe.get_doc({"doctype": "Indus PO Import"}).insert(ignore_permissions=True)
	imp.po_file = _attach(os.path.join(files_dir, xlsx), imp)
	imp.po_pdf = _attach(os.path.join(files_dir, pdf), imp)
	imp.save()
	imp.parse_files()
	result = imp.create_documents()
	site = frappe.get_doc("Tower Site", result["tower_site"])
	site.update({"nominal_name": "Malyan_Dhanu_NB", "principal_opco": "Airtel", "category": "New Build",
		"tower_type": "GBT", "tower_height": 30, "zone": "Vasai", "district": "Palghar", "area_name": "Dahanu",
		"region": "Region 2", "latitude": 19.9682, "longitude": 72.7307, "allocation_date": "2026-07-22"})
	site.save()
	return site.name


def _so_for_site(site, template_rows, factor):
	so = frappe.new_doc("Sales Order")
	so.company = COMPANY
	so.customer = CUSTOMER
	so.transaction_date = site.allocation_date
	so.delivery_date = add_days(site.allocation_date, 45)
	so.po_no = str(19030480100 + int(site.name[-5:]))
	so.po_date = site.allocation_date
	so.tower_site = site.name
	so.project = site.project
	for r in template_rows:
		qty = round(max(r.po_qty * factor, 1 if r.uom == "Nos" else 0.5), 2 if r.uom != "Nos" else 0)
		so.append("items", {"item_code": r.item_code, "qty": qty, "rate": r.rate, "uom": r.uom,
			"delivery_date": so.delivery_date, "indus_task_name": r.task_name, "indus_line_no": r.line_no,
			"project": site.project})
	so.insert(ignore_permissions=True)
	so.submit()
	site.reload()
	site.sales_order = so.name
	site.po_no = so.po_no
	site.po_date = so.po_date
	site.set("boq", [])
	for it in so.items:
		site.append("boq", {"line_no": it.indus_line_no, "item_code": it.item_code, "description": it.description,
			"task_name": it.indus_task_name, "uom": it.uom, "po_qty": it.qty, "rate": it.rate, "so_detail": it.name})
	site.save()
	frappe.db.set_value("Project", site.project, "sales_order", so.name)
	return site


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


def _dsr(site, day, supervisor, fraction, milestone=None, final=False):
	dsr = frappe.new_doc("Daily Site Report")
	dsr.tower_site = site.name
	dsr.report_date = day
	dsr.supervisor = supervisor
	dsr.labour_count = random.randint(4, 14)
	dsr.work_completed = random.choice(WORK_TEXT)
	dsr.milestone_achieved = milestone
	dsr.latitude = site.latitude
	dsr.longitude = site.longitude
	for r in site.boq:
		remaining = r.po_qty - r.executed_qty
		if remaining <= 0:
			continue
		q = remaining if final else round(r.po_qty * fraction, 2)
		q = min(q, remaining)
		if r.uom == "Nos":
			q = max(1, round(q)) if final or random.random() < fraction * 3 else 0
			q = min(q, remaining)
		if q > 0:
			dsr.append("work_items", {"item_code": r.item_code, "qty_completed": q, "uom": r.uom})
	dsr.append("materials", {"item_code": "MAT-TMT-FE500", "qty": random.randint(60, 200), "source_warehouse": WAREHOUSE})
	dsr.append("materials", {"item_code": "MAT-CEMENT-OPC53", "qty": random.randint(5, 25), "source_warehouse": WAREHOUSE})
	if random.random() < 0.5:
		dsr.append("materials", {"item_code": "MAT-GI-STRIP-25X3", "qty": random.randint(10, 40), "source_warehouse": WAREHOUSE})
	dsr.append("expenses", {"expense_type": "Labour Wages", "amount": dsr.labour_count * 650, "paid_to": "Labour contractor"})
	dsr.append("expenses", {"expense_type": "Food & Lodging", "amount": random.randint(6, 18) * 100})
	if random.random() < 0.4:
		dsr.append("expenses", {"expense_type": "Diesel / Fuel", "amount": random.randint(15, 40) * 100, "paid_to": "Petrol pump"})
	dsr.pending_work = "" if final else "Continue as per plan"
	dsr.insert(ignore_permissions=True)
	dsr.submit()
	site.reload()
	return dsr


def _purchase(site, day):
	pi = frappe.new_doc("Purchase Invoice")
	pi.company = COMPANY
	pi.supplier = "Shree Ganesh Earthmovers"
	pi.set_posting_time = 1
	pi.posting_date = day
	pi.bill_no = f"SGE/{random.randint(100, 999)}"
	pi.bill_date = day
	pi.project = site.project
	pi.append("items", {"item_code": "SRV-JCB-HIRE", "qty": random.randint(8, 22), "rate": 950, "project": site.project})
	if random.random() < 0.6:
		pi.append("items", {"item_code": "SRV-RMC-M20", "qty": random.randint(8, 18), "rate": 5200, "project": site.project})
	pi.insert(ignore_permissions=True)
	pi.submit()


def _jmr_and_invoice(site, day, rep):
	from tower_site_execution.tower_site_execution.doctype.joint_measurement_record.joint_measurement_record import (
		make_sales_invoice,
	)

	jmr = frappe.new_doc("Joint Measurement Record")
	jmr.tower_site = site.name
	jmr.jmr_date = day
	jmr.indus_representative = "Indus FSE"
	jmr.company_representative = rep
	jmr.get_boq_items()
	jmr.insert(ignore_permissions=True)
	jmr.submit()
	si = make_sales_invoice(jmr.name)
	si.set_posting_time = 1
	si.posting_date = day
	si.due_date = add_days(day, 30)
	si.insert(ignore_permissions=True)
	si.submit()
	return si


def _drive(site, target, sup, pm):
	"""Walk a site from allocation to the target status with backdated documents."""
	alloc = getdate(site.allocation_date)
	site.set_site_status("hoto", add_days(alloc, random.choice([1, 2, 3])))
	survey = frappe.get_doc({"doctype": "Site Feasibility Survey", "tower_site": site.name,
		"survey_date": add_days(alloc, 2), "surveyed_by": sup, "soil_type": random.choice(["Normal Soil", "Hard Soil", "Soft Rock"]),
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
	steps = 2 if target == "Work In Progress" else len(plan)
	if target == "Work In Progress":
		steps = random.randint(2, 4)
	for i, (offset, ms) in enumerate(plan[:steps]):
		day = add_days(start, offset + random.choice([0, 0, 1, 2]))
		if getdate(day) > TODAY:
			break
		final = target != "Work In Progress" and i == len(plan) - 1
		_dsr(site, day, sup, 0.18, milestone=ms, final=final)
		if i == 1:
			_purchase(site, day)
	site.reload()
	if target == "Work In Progress":
		return
	done = add_days(start, 17)
	site.set_site_status("complete", min(getdate(done), TODAY))
	if target == "Work Completed":
		return
	site.reload()
	site.set_site_status("raise_rfi", min(getdate(add_days(done, 2)), TODAY))
	site.reload()
	_jmr_and_invoice(site, min(getdate(add_days(done, 3)), TODAY), pm)
	if target == "RFI Pending":
		return
	site.reload()
	site.set_site_status("rfi_done", min(getdate(add_days(done, 6)), TODAY))
	site.reload()
	visit = frappe.get_doc({"doctype": "Site Support Visit", "tower_site": site.name,
		"visit_date": min(getdate(add_days(done, 30)), TODAY), "visit_type": "Routine Inspection", "engineer": sup,
		"observations": "Earthing resistance checked, foundation bolts tight, solar panels cleaned",
		"action_taken": "No issues", "next_visit_date": add_days(done, 120)})
	visit.append("expenses", {"expense_type": "Transport & Freight", "amount": 900})
	visit.insert(ignore_permissions=True)
	visit.submit()


ZONES = [("Vasai", "Palghar"), ("Boisar", "Palghar"), ("Dahanu", "Palghar"), ("Bhiwandi", "Thane"), ("Kalyan", "Thane")]
OPCOS = ["Airtel", "Jio", "Vodafone Idea"]


def make_demo(files_dir=None):
	random.seed(42)
	frappe.flags.mute_emails = True
	emps = make_masters()
	sups = [v for k, v in emps.items() if k.startswith("Supervisor")]
	pm = emps["Project Manager"]

	real_site = None
	if files_dir:
		real_site = import_real_po(files_dir)
		frappe.db.commit()
	template = frappe.get_doc("Tower Site", real_site).boq if real_site else []
	template = [r for r in template if r.rate * r.po_qty > 1000][:14]

	plan = ["RFI Done"] * 5 + ["RFI Pending"] * 5 + ["Work Completed"] * 5 + ["Work In Progress"] * 10 + ["Work Not Started"] * 5
	if real_site:
		plan[0] = None  # real site is driven separately as one of the RFI Done sites
	for n, target in enumerate(plan, start=1):
		site_id = f"IN-37{n:05d}"
		if frappe.db.exists("Tower Site", site_id):
			continue
		zone, district = ZONES[n % len(ZONES)]
		age = {"RFI Done": 110, "RFI Pending": 70, "Work Completed": 50, "Work In Progress": 25, "Work Not Started": 4}
		if target is None:
			continue
		alloc = add_days(TODAY, -(age[target] + random.randint(0, 20)))
		site = frappe.get_doc({"doctype": "Tower Site", "indus_site_id": site_id,
			"reference_id": f"R/NN-10{random.randint(10000, 99999)}", "nominal_name": f"{zone}_{random.choice(['NB', 'RE', 'NB2'])}_{n:02d}",
			"principal_opco": random.choice(OPCOS), "category": random.choice(["New Build", "New Build", "Relocation"]),
			"tower_type": random.choice(["GBT", "RT Tower", "GBM"]), "tower_height": random.choice([15, 21, 30, 40]),
			"circle": "Maharashtra & Goa", "region": "Region 2", "zone": zone, "district": district,
			"latitude": 19.2 + random.random() * 0.8, "longitude": 72.7 + random.random() * 0.4,
			"allocation_date": alloc, "customer": CUSTOMER, "zpm_name": "Prabhash Chandra", "tsp_team": "Crystal"})
		site.append("team", {"employee": pm, "role": "Project Manager"})
		sup = sups[n % len(sups)]
		site.append("team", {"employee": sup, "role": "Site Supervisor"})
		site.insert(ignore_permissions=True)
		if template:
			site = _so_for_site(site, template, random.uniform(0.7, 1.4))
		_drive(site, target, sup, pm)
		frappe.db.commit()

	if real_site and frappe.db.get_value("Tower Site", real_site, "status") == "Work Not Started":
		site = frappe.get_doc("Tower Site", real_site)
		site.append("team", {"employee": pm, "role": "Project Manager"})
		site.append("team", {"employee": sups[0], "role": "Site Supervisor"})
		site.save()
		_drive(site, "RFI Done", sups[0], pm)
		frappe.db.commit()

	from tower_site_execution.tower_site_execution.doctype.tower_site.tower_site import daily_site_refresh

	daily_site_refresh()
	frappe.db.commit()
	return frappe.get_all("Tower Site", fields=["status", {"COUNT": "name", "as": "n"}], group_by="status")
