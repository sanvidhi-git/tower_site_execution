# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, nowdate

from tower_site_execution.utils import (
	cancel_site_transactions,
	post_site_transactions,
	refresh_site,
	set_total_expense,
	validate_site_open,
)


class DailySiteReport(Document):
	def validate(self):
		validate_site_open(self.tower_site)
		if getdate(self.report_date) > getdate(nowdate()):
			frappe.throw(_("Report Date cannot be in the future"))
		if not self.project:
			self.project = frappe.db.get_value("Tower Site", self.tower_site, "project")
		if not self.supervisor:
			self.supervisor = frappe.db.get_value("Employee", {"user_id": frappe.session.user, "status": "Active"})
		set_total_expense(self)
		self.validate_work_items()
		self.warn_duplicate()

	def validate_work_items(self):
		boq = {
			r.item_code: r
			for r in frappe.get_all(
				"Tower Site BOQ",
				filters={"parent": self.tower_site, "parenttype": "Tower Site"},
				fields=["item_code", "po_qty", "executed_qty"],
			)
		}
		for row in self.work_items:
			if row.item_code not in boq:
				frappe.throw(_("Row {0}: {1} is not in the PO BOQ of site {2}").format(
					row.idx, row.item_code, self.tower_site))
			line = boq[row.item_code]
			if flt(line.executed_qty) + flt(row.qty_completed) > flt(line.po_qty) and self.docstatus == 0:
				frappe.msgprint(
					_("Row {0}: cumulative quantity for {1} will exceed PO quantity {2}. Raise an amendment with Indus.").format(
						row.idx, row.item_code, line.po_qty),
					indicator="orange", alert=True,
				)

	def warn_duplicate(self):
		if frappe.db.exists("Daily Site Report", {
			"tower_site": self.tower_site, "report_date": self.report_date, "supervisor": self.supervisor,
			"docstatus": ["<", 2], "name": ["!=", self.name]}):
			frappe.msgprint(_("A report for this site, date and supervisor already exists"), indicator="orange", alert=True)

	def on_submit(self):
		post_site_transactions(self, self.report_date, _("Daily Site Report"))
		site = frappe.get_doc("Tower Site", self.tower_site)
		if site.status == "Work Not Started":
			site.status = "Work In Progress"
		if not site.work_start_date or getdate(site.work_start_date) > getdate(self.report_date):
			site.work_start_date = self.report_date
		if self.milestone_achieved:
			for m in site.milestones:
				if m.milestone == self.milestone_achieved and not m.actual_date:
					m.actual_date = self.report_date
		site.update_boq_progress()
		site.calculate_costing()
		site.flags.ignore_permissions = True
		site.save()

	def on_cancel(self):
		cancel_site_transactions(self)
		refresh_site(self.tower_site)
