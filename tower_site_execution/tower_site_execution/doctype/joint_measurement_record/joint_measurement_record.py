# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from tower_site_execution.utils import refresh_site


class JointMeasurementRecord(Document):
	def validate(self):
		if not self.sales_order:
			self.sales_order = frappe.db.get_value("Tower Site", self.tower_site, "sales_order")
		if not self.sales_order:
			frappe.throw(_("Site {0} has no Sales Order. Import the Indus PO first.").format(self.tower_site))
		total = 0
		for row in self.items:
			row.amount = flt(row.measured_qty) * flt(row.rate)
			total += row.amount
			if flt(row.measured_qty) > flt(row.po_qty):
				frappe.msgprint(
					_("Row {0}: measured qty {1} exceeds PO qty {2} for {3}; only PO qty can be invoiced until Indus amends the PO").format(
						row.idx, row.measured_qty, row.po_qty, row.item_code),
					indicator="orange", alert=True)
		self.total_amount = total

	def on_submit(self):
		refresh_site(self.tower_site, costing=False)

	def on_cancel(self):
		refresh_site(self.tower_site, costing=False)

	@frappe.whitelist()
	def get_boq_items(self):
		self.check_permission("write")
		site = frappe.get_doc("Tower Site", self.tower_site)
		self.set("items", [])
		already = dict(frappe.db.sql(
			"""select ji.so_detail, sum(ji.measured_qty) from `tabJoint Measurement Item` ji
			join `tabJoint Measurement Record` j on j.name = ji.parent
			where j.tower_site = %s and j.docstatus = 1 and j.name != %s group by ji.so_detail""",
			(self.tower_site, self.name or "")))
		for r in site.boq:
			pending = flt(r.executed_qty) - flt(already.get(r.so_detail))
			if pending <= 0 and flt(r.executed_qty):
				continue
			self.append("items", {
				"item_code": r.item_code, "description": r.description, "task_name": r.task_name, "uom": r.uom,
				"po_qty": r.po_qty, "executed_qty": r.executed_qty,
				"measured_qty": pending if pending > 0 else 0,
				"rate": r.rate, "so_detail": r.so_detail,
			})
		self.validate()
		return self.as_dict()


@frappe.whitelist()
def make_sales_invoice(source_name):
	from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as so_to_si

	jmr = frappe.get_doc("Joint Measurement Record", source_name)
	jmr.check_permission("read")
	if jmr.docstatus != 1:
		frappe.throw(_("Submit the Joint Measurement Record first"))
	if jmr.sales_invoice and frappe.db.get_value("Sales Invoice", jmr.sales_invoice, "docstatus") < 2:
		frappe.throw(_("Sales Invoice {0} already created").format(jmr.sales_invoice))

	measured = {r.so_detail: flt(r.measured_qty) for r in jmr.items if flt(r.measured_qty) > 0}
	si = so_to_si(jmr.sales_order)
	keep = []
	for item in si.items:
		if item.so_detail in measured:
			item.qty = min(measured[item.so_detail], flt(item.qty))
			if item.qty > 0:
				keep.append(item)
	if not keep:
		frappe.throw(_("Nothing left to invoice against Sales Order {0}").format(jmr.sales_order))
	si.set("items", keep)
	si.tower_site = jmr.tower_site
	si.project = jmr.project
	si.joint_measurement_record = jmr.name
	si.remarks = _("Against Joint Measurement Record {0} dated {1}").format(jmr.name, jmr.jmr_date)
	si.run_method("set_missing_values")
	si.run_method("calculate_taxes_and_totals")
	return si
