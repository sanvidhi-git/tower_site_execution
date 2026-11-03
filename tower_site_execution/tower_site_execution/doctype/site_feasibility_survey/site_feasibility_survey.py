# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate

STATUS_MAP = {"Pending": "Submitted", "Go Ahead": "Go Ahead", "Revision Required": "Revision Required", "Rejected": "Rejected"}


class SiteFeasibilitySurvey(Document):
	def on_submit(self):
		if not self.submitted_to_indus_on:
			self.db_set("submitted_to_indus_on", nowdate())
		self.update_site()

	def on_update_after_submit(self):
		if self.indus_decision != "Pending" and not self.decision_date:
			self.db_set("decision_date", nowdate())
		self.update_site()

	def on_cancel(self):
		frappe.db.set_value("Tower Site", self.tower_site, "feasibility_status", "Pending")

	def update_site(self):
		site = frappe.get_doc("Tower Site", self.tower_site)
		site.feasibility_status = STATUS_MAP[self.indus_decision]
		if self.indus_decision == "Go Ahead":
			site.go_ahead_date = self.decision_date or nowdate()
		site.flags.ignore_permissions = True
		site.save()
