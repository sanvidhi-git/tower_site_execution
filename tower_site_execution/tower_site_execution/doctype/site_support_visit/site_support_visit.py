# Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate

from tower_site_execution.utils import (
	cancel_site_transactions,
	post_site_transactions,
	refresh_site,
	set_total_expense,
)


class SiteSupportVisit(Document):
	def validate(self):
		site = frappe.db.get_value(
			"Tower Site", self.tower_site, ["status", "rfi_done_date", "support_end_date", "project"], as_dict=True)
		if site.status not in ("RFI Done", "Closed"):
			frappe.throw(_("Support visits can be booked only after RFI is done (site is {0})").format(site.status))
		self.project = self.project or site.project
		self.within_support_period = int(bool(
			site.rfi_done_date and site.support_end_date
			and getdate(site.rfi_done_date) <= getdate(self.visit_date) <= getdate(site.support_end_date)))
		if not self.within_support_period:
			frappe.msgprint(_("Visit date is outside the 1-year support period"), indicator="orange", alert=True)
		set_total_expense(self)

	def on_submit(self):
		post_site_transactions(self, self.visit_date, _("Site Support Visit"))
		refresh_site(self.tower_site)

	def on_cancel(self):
		cancel_site_transactions(self)
		refresh_site(self.tower_site)
