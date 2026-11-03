# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

"""Material received at a tower site, reported by site staff (usually from the mobile app)
and verified (submitted) by the Project Manager / stores:

* Vendor Delivery against PO  -> Purchase Receipt into the site warehouse (draft or submitted)
* Transfer from Store         -> Stock Entry (Material Transfer) store -> site warehouse
* Indus Free-Issue Material   -> logged only; Indus-owned equipment is not Crystal stock
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowtime

from tower_site_execution.utils import get_company, get_cost_center, get_settings, validate_site_open


def get_site_warehouse(site_name):
	return frappe.db.get_value("Tower Site", site_name, "site_warehouse") or get_settings().default_site_warehouse


def get_rejected_warehouse(company, near_warehouse):
	"""Damaged / short-supplied qty is parked in a company-level 'Rejected Material' warehouse."""
	abbr = frappe.get_cached_value("Company", company, "abbr")
	name = f"Rejected Material - {abbr}"
	if not frappe.db.exists("Warehouse", name):
		parent = frappe.db.get_value("Warehouse", near_warehouse, "parent_warehouse")
		frappe.get_doc({"doctype": "Warehouse", "warehouse_name": "Rejected Material", "company": company,
			"parent_warehouse": parent, "is_group": 0}).insert(ignore_permissions=True)
	return name


class SiteMaterialReceipt(Document):
	def validate(self):
		validate_site_open(self.tower_site)
		if not self.project:
			self.project = frappe.db.get_value("Tower Site", self.tower_site, "project")
		if not self.received_by:
			self.received_by = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"})
		self.target_warehouse = get_site_warehouse(self.tower_site)
		self.items = [r for r in self.items if flt(r.received_qty) or flt(r.rejected_qty)]
		if not self.items:
			frappe.throw(_("Enter at least one received item"))
		getattr(self, "validate_" + frappe.scrub(self.receipt_type).split("_")[0])()

	def validate_vendor(self):
		if not self.purchase_order:
			frappe.throw(_("Select the Purchase Order"))
		po = frappe.get_doc("Purchase Order", self.purchase_order)
		if po.docstatus != 1:
			frappe.throw(_("Purchase Order {0} is not submitted").format(po.name))
		self.supplier = po.supplier
		po_items = {d.name: d for d in po.items}
		for r in self.items:
			line = po_items.get(r.purchase_order_item) or next(
				(d for d in po.items if d.item_code == r.item_code), None)
			if not line:
				frappe.throw(_("Row {0}: {1} is not on Purchase Order {2}").format(r.idx, r.item_code, po.name))
			r.purchase_order_item = line.name
			r.item_code = line.item_code
			r.item_name = r.item_name or line.item_name
			r.uom = r.uom or line.uom
			r.ordered_qty = flt(line.qty) - flt(line.received_qty)
			if flt(r.received_qty) > r.ordered_qty and self.docstatus == 0:
				frappe.msgprint(_("Row {0}: received {1} is more than pending PO qty {2}").format(
					r.idx, r.received_qty, r.ordered_qty), indicator="orange", alert=True)

	def validate_transfer(self):
		if not self.source_warehouse:
			frappe.throw(_("Select the warehouse the material was dispatched from"))
		if self.source_warehouse == self.target_warehouse:
			frappe.throw(_("Site {0} has no warehouse of its own. Set Site Warehouse on the Tower Site.").format(self.tower_site))
		for r in self.items:
			if not r.item_code:
				frappe.throw(_("Row {0}: select the item").format(r.idx))
			r.uom = r.uom or frappe.get_cached_value("Item", r.item_code, "stock_uom")
			r.item_name = r.item_name or frappe.get_cached_value("Item", r.item_code, "item_name")

	def validate_indus(self):
		for r in self.items:
			if not (r.item_code or r.item_name):
				frappe.throw(_("Row {0}: enter the material description").format(r.idx))

	def on_submit(self):
		if self.receipt_type == "Vendor Delivery against PO":
			self.make_purchase_receipt()
		elif self.receipt_type == "Transfer from Store":
			self.make_transfer()

	def on_cancel(self):
		for field, doctype in (("purchase_receipt", "Purchase Receipt"), ("stock_entry", "Stock Entry")):
			name = self.get(field)
			if not name:
				continue
			status = frappe.db.get_value(doctype, name, "docstatus")
			if status == 1:
				d = frappe.get_doc(doctype, name)
				d.flags.ignore_permissions = True
				d.cancel()
			elif status == 0:
				self.db_set(field, None)  # unlink first, else the delete is blocked by this link
				frappe.delete_doc(doctype, name, ignore_permissions=True)

	def make_purchase_receipt(self):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

		pr = make_purchase_receipt(self.purchase_order)
		qty = {r.purchase_order_item: r for r in self.items}
		keep = []
		for d in pr.items:
			r = qty.get(d.purchase_order_item)
			if not r:
				continue
			d.qty = flt(r.received_qty)
			d.received_qty = flt(r.received_qty) + flt(r.rejected_qty)
			d.rejected_qty = flt(r.rejected_qty)
			if d.rejected_qty:
				d.rejected_warehouse = get_rejected_warehouse(pr.company, self.target_warehouse)
			d.warehouse = self.target_warehouse
			d.project = self.project
			if r.serial_nos and frappe.get_cached_value("Item", d.item_code, "has_serial_no"):
				d.serial_no = r.serial_nos
			keep.append(d)
		pr.set("items", keep)
		pr.set_warehouse = self.target_warehouse
		pr.set_posting_time = 1
		pr.posting_date = self.receipt_date
		pr.project = self.project
		if pr.meta.has_field("tower_site"):
			pr.tower_site = self.tower_site
		pr.supplier_delivery_note = self.challan_no
		pr.lr_no = self.vehicle_no
		pr.remarks = _("Site Material Receipt {0} - site {1}").format(self.name, self.tower_site)
		pr.flags.ignore_permissions = True
		pr.insert()
		if get_settings().submit_purchase_receipt:
			pr.submit()
		self.db_set("purchase_receipt", pr.name)

	def make_transfer(self):
		se = frappe.new_doc("Stock Entry")
		se.stock_entry_type = "Material Transfer"
		se.purpose = "Material Transfer"
		se.company = get_company()
		se.set_posting_time = 1
		se.posting_date = self.receipt_date
		se.posting_time = nowtime()
		se.project = self.project
		se.remarks = _("Site Material Receipt {0} - site {1}").format(self.name, self.tower_site)
		for r in self.items:
			se.append("items", {
				"item_code": r.item_code, "qty": flt(r.received_qty), "uom": r.uom,
				"s_warehouse": self.source_warehouse, "t_warehouse": self.target_warehouse,
				"cost_center": get_cost_center(se.company), "project": self.project,
			})
		se.flags.ignore_permissions = True
		se.insert()
		se.submit()
		self.db_set("stock_entry", se.name)
