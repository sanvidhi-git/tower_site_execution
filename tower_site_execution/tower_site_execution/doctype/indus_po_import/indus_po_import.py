# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from tower_site_execution.indus_parser import parse_allotment_email, parse_po_excel, parse_po_pdf
from tower_site_execution.utils import get_company, get_settings

# Indus UOM -> ERPNext UOM (created if missing)
UOM_MAP = {
	"each": "Nos",
	"meter": "Meter",
	"kilogram": "Kg",
	"cubic meter": "Cubic Meter",
	"sq. meter": "Square Meter",
	"lumpsum": "Lumpsum",
	"daily": "Day",
	"hour": "Hour",
}
WHOLE_NUMBER_OK = {"Nos"}


class IndusPOImport(Document):
	def validate(self):
		self.total_amount = sum(flt(r.amount) for r in self.items if not r.skip)

	def _path(self, url):
		return frappe.get_doc("File", {"file_url": url}).get_full_path()

	@frappe.whitelist()
	def parse_files(self):
		self.check_permission("write")
		if not (self.po_file or self.po_pdf or self.allotment_email):
			frappe.throw(_("Attach the PO Excel / PDF or paste the allotment email"))
		log = []
		hsn = {}
		if self.po_pdf:
			header, hsn = parse_po_pdf(self._path(self.po_pdf))
			for f in ("po_no", "po_date", "amendment_no", "gbpa_no", "buyer", "circle"):
				if header.get(f):
					self.set(f, header[f])
			self.indus_site_id = self.indus_site_id or header.get("site_id")
			self.reference_id = self.reference_id or header.get("reference_id")
			log.append(_("PDF: PO {0}, {1} HSN/SAC codes").format(header.get("po_no"), len(hsn)))
		if self.po_file:
			header, lines = parse_po_excel(self._path(self.po_file))
			if not lines:
				frappe.throw(_("No PO lines found. Is this the Indus PO line export?"))
			self.buyer = self.buyer or header.get("buyer")
			self.circle = self.circle or header.get("circle")
			self.reference_id = self.reference_id or header.get("reference_id") or lines[0]["reference_id"]
			self.indus_site_id = self.indus_site_id or lines[0]["site_id"]
			self.site_owner = lines[0]["site_owner"]
			if not self.po_date and header.get("order_date"):
				self.po_date = header["order_date"]
			self.set("items", [])
			for ln in lines:
				self.append("items", {
					"line_no": ln["line_no"], "item_code": ln["item_code"], "description": ln["description"],
					"task_name": ln["task_name"], "uom": ln["uom"], "qty": ln["qty"], "rate": ln["rate"],
					"amount": ln["amount"], "line_status": ln["line_status"], "need_by_date": ln["need_by_date"],
					"hsn_sac": hsn.get(ln["item_code"], ""),
					"skip": int(ln["qty"] <= 0 or ln["line_status"].lower() in ("closed", "cancelled")),
				})
			active = [r for r in self.items if not r.skip]
			log.append(_("Excel: {0} lines, {1} active, value {2}").format(
				len(lines), len(active), frappe.format(sum(r.amount for r in active), {"fieldtype": "Currency"})))
			if header.get("po_total") and abs(header["po_total"] - sum(r.amount for r in active)) > 1:
				log.append(_("WARNING: line total does not match PO total {0}").format(header["po_total"]))
		if self.allotment_email:
			site = parse_allotment_email(self.allotment_email)
			if site.get("indus_site_id"):
				if self.indus_site_id and self.indus_site_id != site["indus_site_id"]:
					log.append(_("WARNING: email is for site {0} but PO is for {1}").format(
						site["indus_site_id"], self.indus_site_id))
				self.indus_site_id = self.indus_site_id or site["indus_site_id"]
			log.append(_("Email: {0} site fields read").format(len(site)))
		self.status = "Parsed"
		self.import_log = "\n".join(log)
		self.save()
		return self.as_dict()

	@frappe.whitelist()
	def create_documents(self):
		self.check_permission("write")
		if self.status == "Imported":
			frappe.throw(_("Already imported into {0}").format(self.sales_order))
		if not self.indus_site_id:
			frappe.throw(_("Indus Site ID is required"))
		if not self.po_no:
			frappe.throw(_("Indus PO No is required (attach the PO PDF or type it in)"))
		rows = [r for r in self.items if not r.skip]
		if not rows:
			frappe.throw(_("No PO lines to import"))
		settings = get_settings()
		customer = settings.indus_customer
		if not customer:
			frappe.throw(_("Set Indus Towers Customer in Tower Site Settings"))
		existing = frappe.db.get_value(
			"Sales Order", {"po_no": self.po_no, "customer": customer, "docstatus": ["<", 2]}, "name")
		if existing:
			frappe.throw(_("Sales Order {0} already exists for Indus PO {1}. Cancel and amend it for PO amendments.").format(
				existing, self.po_no))

		site = self.get_or_create_site(customer)
		so = self.create_sales_order(site, rows, customer, settings)

		site.reload()
		site.sales_order = so.name
		site.po_no, site.po_date, site.gbpa_no = self.po_no, self.po_date, self.gbpa_no
		site.set("boq", [])
		for it in so.items:
			site.append("boq", {
				"line_no": it.indus_line_no, "item_code": it.item_code, "description": it.description,
				"task_name": it.indus_task_name, "uom": it.uom, "po_qty": it.qty, "rate": it.rate,
				"so_detail": it.name,
			})
		site.update_boq_progress()
		site.flags.ignore_permissions = True
		site.save()
		if site.project:
			frappe.db.set_value("Project", site.project, {"sales_order": so.name, "customer": customer})

		self.tower_site = site.name
		self.sales_order = so.name
		self.status = "Imported"
		self.import_log = (self.import_log or "") + "\n" + _("Created / updated Tower Site {0} and Sales Order {1}").format(
			site.name, so.name)
		self.save()
		return {"tower_site": site.name, "sales_order": so.name}

	def get_or_create_site(self, customer):
		data = parse_allotment_email(self.allotment_email) if self.allotment_email else {}
		data.pop("indus_site_id", None)
		if frappe.db.exists("Tower Site", self.indus_site_id):
			site = frappe.get_doc("Tower Site", self.indus_site_id)
		else:
			site = frappe.new_doc("Tower Site")
			site.indus_site_id = self.indus_site_id
			site.allocation_date = self.po_date or nowdate()
		for k, v in data.items():
			if v not in (None, "") and not site.get(k):
				site.set(k, v)
		site.reference_id = site.reference_id or self.reference_id
		site.circle = site.circle or self.circle
		site.site_owner_details = site.site_owner_details or self.site_owner
		site.customer = customer
		site.nominal_name = site.nominal_name or self.reference_id
		site.flags.ignore_permissions = True
		site.save()
		return site

	def create_sales_order(self, site, rows, customer, settings):
		po_date = getdate(self.po_date or nowdate())
		so = frappe.new_doc("Sales Order")
		so.company = get_company()
		so.customer = customer
		so.transaction_date = po_date
		so.po_no = self.po_no
		so.po_date = self.po_date
		so.tower_site = site.name
		so.gbpa_no = self.gbpa_no
		so.project = site.project
		so.order_type = "Sales"
		dates = []
		for r in rows:
			item_code = ensure_item(r, settings)
			d = max(getdate(r.need_by_date) if r.need_by_date else po_date, po_date)
			dates.append(d)
			so.append("items", {
				"item_code": item_code, "item_name": (r.description or item_code)[:140],
				"description": r.description, "qty": r.qty, "rate": r.rate, "uom": ensure_uom(r.uom),
				"delivery_date": d, "indus_task_name": r.task_name, "indus_line_no": r.line_no,
				"project": site.project,
			})
		so.delivery_date = max(dates)
		if settings.sales_taxes_and_charges_template:
			so.taxes_and_charges = settings.sales_taxes_and_charges_template
			so.set_taxes()
		so.flags.ignore_permissions = True
		so.insert()
		if settings.submit_sales_order:
			so.submit()
		return so


def ensure_uom(indus_uom):
	name = UOM_MAP.get((indus_uom or "").strip().lower()) or (indus_uom or "Nos").strip().title()
	if not frappe.db.exists("UOM", name):
		frappe.get_doc({"doctype": "UOM", "uom_name": name, "must_be_whole_number": 0}).insert(ignore_permissions=True)
	return name


def ensure_item(row, settings):
	code = row.item_code
	if frappe.db.exists("Item", code):
		return code
	item = frappe.new_doc("Item")
	item.item_code = code
	item.item_name = (row.description or code)[:140]
	item.description = row.description
	from tower_site_execution.install import ensure_item_group

	item.item_group = settings.boq_item_group or ensure_item_group()
	item.stock_uom = ensure_uom(row.uom)
	item.is_stock_item = 0
	item.is_sales_item = 1
	item.is_purchase_item = 0
	item.include_item_in_manufacturing = 0
	if row.hsn_sac and item.meta.has_field("gst_hsn_code"):
		if frappe.db.exists("GST HSN Code", row.hsn_sac):
			item.gst_hsn_code = row.hsn_sac
	item.flags.ignore_permissions = True
	item.insert()
	return code
