# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, add_months, date_diff, flt, getdate, now_datetime, nowdate

from tower_site_execution.utils import get_company, get_settings

# action -> (allowed from statuses, new status, date field to stamp)
TRANSITIONS = {
	"complete": (("Work In Progress",), "Work Completed", "work_completion_date"),
	"raise_rfi": (("Work Completed",), "RFI Pending", "rfi_raised_date"),
	"rfi_done": (("RFI Pending",), "RFI Done", "rfi_done_date"),
	"close": (("RFI Done",), "Closed", "closed_date"),
	"start": (("Work Not Started",), "Work In Progress", "work_start_date"),
	"reopen": (("Work Completed", "RFI Pending"), "Work In Progress", None),
}


class TowerSite(Document):
	def before_insert(self):
		if not self.milestones:
			self.load_milestones_from_template()

	def validate(self):
		self.indus_site_id = (self.indus_site_id or "").strip().upper()
		self.set_location()
		self.calculate_milestones()
		self.calculate_boq_totals()
		if self.rfi_done_date and not self.support_end_date:
			self.support_end_date = add_months(self.rfi_done_date, get_settings().support_months or 12)

	def after_insert(self):
		if not self.project:
			self.create_project()

	def on_update(self):
		self.sync_tasks()

	# ------------------------------------------------------------------ setup
	def load_milestones_from_template(self):
		for t in frappe.get_all(
			"Site Milestone Template",
			filters={"is_active": 1},
			fields=["name", "tat_days", "penalty_per_day"],
			order_by="sequence asc",
		):
			self.append("milestones", {"milestone": t.name, "tat_days": t.tat_days, "penalty_per_day": t.penalty_per_day})

	def set_location(self):
		if self.latitude and self.longitude and not self.location:
			self.location = json.dumps(
				{
					"type": "FeatureCollection",
					"features": [
						{
							"type": "Feature",
							"properties": {},
							"geometry": {"type": "Point", "coordinates": [flt(self.longitude), flt(self.latitude)]},
						}
					],
				}
			)

	def create_project(self):
		project = frappe.new_doc("Project")
		project.project_name = f"{self.indus_site_id} - {self.nominal_name or self.reference_id or ''}".strip(" -")
		project.tower_site = self.name
		project.company = get_company()
		project.customer = self.customer or get_settings().indus_customer
		project.sales_order = self.sales_order
		project.expected_start_date = self.allocation_date
		last = self.milestones[-1].planned_date if self.milestones else None
		project.expected_end_date = last or add_days(self.allocation_date, 30)
		project.percent_complete_method = "Task Completion"
		project.notes = _("Auto-created for Indus site {0}").format(self.name)
		project.flags.ignore_permissions = True
		project.insert()
		self.db_set("project", project.name)
		self.project = project.name
		self.sync_tasks()

	def sync_tasks(self):
		"""One Task per TAT milestone so the Project Gantt shows the site plan."""
		if not self.project or not get_settings().create_project_tasks:
			return
		# delays push milestones out: keep the project window wide enough for its tasks
		ends = [getdate(d) for m in self.milestones for d in (m.planned_date, m.actual_date) if d]
		if ends:
			start, end = frappe.db.get_value("Project", self.project, ["expected_start_date", "expected_end_date"])
			new_start = min(getdate(self.allocation_date), getdate(start or self.allocation_date))
			new_end = max(max(ends), getdate(end or max(ends)))
			if (start, end) != (new_start, new_end):
				frappe.db.set_value("Project", self.project, {"expected_start_date": new_start, "expected_end_date": new_end})
		prev_end = self.allocation_date
		for m in self.milestones:
			start = prev_end
			end = m.planned_date or start
			if getdate(end) < getdate(start):
				end = start
			status = "Completed" if m.actual_date else ("Overdue" if m.status == "Overdue" else "Open")
			values = {
				"subject": f"{m.milestone} - {self.name}",
				"project": self.project,
				"exp_start_date": start,
				"exp_end_date": end,
				"status": status,
				"completed_on": m.actual_date if m.actual_date else None,
				"description": frappe.db.get_value("Site Milestone Template", m.milestone, "description"),
			}
			if m.task and frappe.db.exists("Task", m.task):
				task = frappe.get_doc("Task", m.task)
				changed = any(str(task.get(k) or "") != str(v or "") for k, v in values.items() if k != "description")
				if changed:
					task.update(values)
					task.flags.ignore_permissions = True
					task.save()
			else:
				task = frappe.get_doc(dict(values, doctype="Task"))
				task.flags.ignore_permissions = True
				task.insert()
				m.db_set("task", task.name)
			prev_end = m.actual_date or end

	# ------------------------------------------------------------- TAT engine
	def calculate_milestones(self):
		today = getdate(nowdate())
		templates = {
			t.name: t
			for t in frappe.get_all("Site Milestone Template", fields=["name", "site_date_field", "penalty_per_day"])
		}
		reference = getdate(self.allocation_date or today)
		total_delay = total_penalty = 0
		for m in self.milestones:
			tpl = templates.get(m.milestone)
			if tpl and tpl.site_date_field and self.get(tpl.site_date_field):
				m.actual_date = self.get(tpl.site_date_field)
			if m.penalty_per_day is None and tpl:
				m.penalty_per_day = tpl.penalty_per_day
			m.planned_date = add_days(reference, (m.tat_days or 0) + (m.hold_days or 0))
			if m.actual_date:
				m.delay_days = max(0, date_diff(m.actual_date, m.planned_date))
				m.status = "Done"
				reference = getdate(m.actual_date)
			else:
				m.delay_days = max(0, date_diff(today, m.planned_date))
				m.status = "Overdue" if m.delay_days else "Pending"
				reference = getdate(m.planned_date)
			if self.status in ("On Hold", "Cancelled") and not m.actual_date:
				m.delay_days = 0
				m.status = "Pending"
			m.penalty_amount = flt(m.delay_days) * flt(m.penalty_per_day)
			total_delay += m.delay_days
			total_penalty += m.penalty_amount
		self.total_delay_days = total_delay
		self.total_penalty = total_penalty

	# ----------------------------------------------------------- BOQ progress
	def calculate_boq_totals(self):
		po_value = done_value = 0
		for row in self.boq:
			row.po_amount = flt(row.po_qty) * flt(row.rate)
			row.progress = min(100, flt(row.executed_qty) / flt(row.po_qty) * 100) if flt(row.po_qty) else 0
			po_value += row.po_amount
			done_value += min(flt(row.executed_qty), flt(row.po_qty)) * flt(row.rate)
		self.po_value = po_value
		self.overall_progress = (done_value / po_value * 100) if po_value else 0

	def update_boq_progress(self):
		executed = dict(
			frappe.db.sql(
				"""select wi.item_code, sum(wi.qty_completed)
				from `tabSite Work Item` wi join `tabDaily Site Report` d on d.name = wi.parent
				where d.tower_site = %s and d.docstatus = 1 and wi.parenttype = 'Daily Site Report'
				group by wi.item_code""",
				self.name,
			)
		)
		measured = dict(
			frappe.db.sql(
				"""select ji.so_detail, sum(ji.measured_qty)
				from `tabJoint Measurement Item` ji join `tabJoint Measurement Record` j on j.name = ji.parent
				where j.tower_site = %s and j.docstatus = 1 group by ji.so_detail""",
				self.name,
			)
		)
		billed = {}
		if self.sales_order:
			billed = dict(
				frappe.db.sql(
					"""select so_detail, sum(qty) from `tabSales Invoice Item`
					where sales_order = %s and docstatus = 1 group by so_detail""",
					self.sales_order,
				)
			)
		for row in self.boq:
			row.executed_qty = flt(executed.get(row.item_code))
			row.measured_qty = flt(measured.get(row.so_detail))
			row.billed_qty = flt(billed.get(row.so_detail))
		self.calculate_boq_totals()

	# ---------------------------------------------------------------- costing
	def calculate_costing(self):
		project = self.project
		if not project:
			return
		self.billed_amount = flt(
			frappe.db.sql(
				"""select sum(base_net_total) from `tabSales Invoice`
				where docstatus = 1 and (tower_site = %s or project = %s)""",
				(self.name, project),
			)[0][0]
		)
		self.material_cost = flt(
			frappe.db.sql(
				"""select sum(sed.amount) from `tabStock Entry Detail` sed
				join `tabStock Entry` se on se.name = sed.parent
				where se.docstatus = 1 and se.purpose = 'Material Issue'
				and ifnull(sed.project, se.project) = %s""",
				project,
			)[0][0]
		)
		self.expense_cost = flt(
			frappe.db.sql(
				"""select sum(jea.debit - jea.credit) from `tabJournal Entry Account` jea
				join `tabJournal Entry` je on je.name = jea.parent
				join `tabAccount` acc on acc.name = jea.account
				where je.docstatus = 1 and jea.project = %s and acc.root_type = 'Expense'""",
				project,
			)[0][0]
		)
		# non-stock purchases (equipment hire, RMC delivered to site, subcontract labour);
		# stock purchases are counted when issued to the site via Material Issue
		self.purchase_cost = flt(
			frappe.db.sql(
				"""select sum(pii.base_net_amount) from `tabPurchase Invoice Item` pii
				join `tabPurchase Invoice` pi on pi.name = pii.parent
				join `tabItem` it on it.name = pii.item_code
				where pi.docstatus = 1 and ifnull(pii.project, pi.project) = %s
				and it.is_stock_item = 0 and ifnull(pii.is_fixed_asset, 0) = 0""",
				project,
			)[0][0]
		)
		self.total_cost = self.material_cost + self.expense_cost + self.purchase_cost
		self.gross_margin = flt(self.po_value) - self.total_cost
		self.margin_pct = (self.gross_margin / flt(self.po_value) * 100) if flt(self.po_value) else 0
		self.costing_updated_on = now_datetime()

	# -------------------------------------------------------------- API
	@frappe.whitelist()
	def refresh_progress_and_costing(self):
		self.check_permission("write")
		self.update_boq_progress()
		self.calculate_costing()
		self.save()
		return self.as_dict()

	@frappe.whitelist()
	def set_site_status(self, action, on_date=None, reason=None):
		self.check_permission("write")
		on_date = on_date or nowdate()
		if action == "hold":
			self.db_set({"status": "On Hold", "on_hold_reason": reason})
		elif action == "resume":
			if self.status != "On Hold":
				frappe.throw(_("Site is not On Hold"))
			self.status = "Work In Progress" if self.work_start_date else "Work Not Started"
		elif action == "hoto":
			self.hoto_date = on_date
		else:
			if action not in TRANSITIONS:
				frappe.throw(_("Unknown action {0}").format(action))
			allowed, new_status, date_field = TRANSITIONS[action]
			if self.status not in allowed:
				frappe.throw(
					_("Cannot move site from {0} to {1}").format(frappe.bold(self.status), frappe.bold(new_status))
				)
			self.status = new_status
			if date_field:
				self.set(date_field, on_date)
			if action == "rfi_done":
				self.support_end_date = add_months(on_date, get_settings().support_months or 12)
		self.save()
		return self.status


def daily_site_refresh():
	"""Nightly: roll TAT delays forward and refresh costing for open sites."""
	for name in frappe.get_all(
		"Tower Site", filters={"status": ["not in", ["Closed", "Cancelled"]]}, pluck="name"
	):
		try:
			site = frappe.get_doc("Tower Site", name)
			site.update_boq_progress()
			site.calculate_costing()
			site.flags.ignore_permissions = True
			site.save()
			frappe.db.commit()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(title=f"Tower Site refresh failed: {name}")
