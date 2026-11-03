// Copyright (c) 2026, Sanvidhi Tech Pvt. Ltd. and contributors

const SITE_STATUS_COLORS = {
	"Work Not Started": "gray",
	"Work In Progress": "orange",
	"Work Completed": "blue",
	"RFI Pending": "yellow",
	"RFI Done": "green",
	"Closed": "darkgrey",
	"On Hold": "red",
	"Cancelled": "red",
};

frappe.ui.form.on("Tower Site", {
	refresh(frm) {
		if (frm.is_new()) return;
		frm.page.set_indicator(__(frm.doc.status), SITE_STATUS_COLORS[frm.doc.status] || "gray");
		frm.trigger("add_status_buttons");
		frm.trigger("add_create_buttons");
		frm.add_custom_button(__("Refresh Progress & Costing"), () =>
			frm.call("refresh_progress_and_costing").then(() => frm.reload_doc())
		);
		if (frm.doc.project) {
			frm.add_custom_button(__("Project Gantt"), () =>
				frappe.set_route("List", "Task", "Gantt", { project: frm.doc.project })
			, __("View"));
			frm.add_custom_button(__("Project"), () => frappe.set_route("Form", "Project", frm.doc.project), __("View"));
			frm.add_custom_button(__("Site P&L (General Ledger)"), () =>
				frappe.set_route("query-report", "General Ledger", {
					company: frappe.defaults.get_user_default("company"),
					project: [frm.doc.project],
					group_by: "Group by Voucher (Consolidated)",
				})
			, __("View"));
		}
		frm.trigger("render_summary");
	},

	add_status_buttons(frm) {
		const act = (label, action, confirm) =>
			frm.add_custom_button(__(label), () => {
				const run = () => frm.call("set_site_status", { action }).then(() => frm.reload_doc());
				confirm ? frappe.confirm(__(confirm), run) : run();
			}, __("Status"));
		const s = frm.doc.status;
		if (!frm.doc.hoto_date) act("Mark HOTO Done", "hoto");
		if (s === "Work Not Started") act("Start Work", "start");
		if (s === "Work In Progress") act("Mark Work Completed", "complete", "Mark all site work as completed?");
		if (s === "Work Completed") act("Raise RFI", "raise_rfi");
		if (s === "RFI Pending") act("RFI Accepted by Indus", "rfi_done", "Mark RFI as accepted? The 1-year support period starts today.");
		if (["Work Completed", "RFI Pending"].includes(s)) act("Reopen Work", "reopen");
		if (s === "RFI Done") act("Close Site", "close", "Close this site? No further reports can be booked.");
		if (s === "On Hold") act("Resume", "resume");
		else if (!["Closed", "Cancelled"].includes(s)) {
			frm.add_custom_button(__("Put On Hold"), () => {
				frappe.prompt({ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 }, (v) =>
					frm.call("set_site_status", { action: "hold", reason: v.reason }).then(() => frm.reload_doc())
				, __("Put Site On Hold"));
			}, __("Status"));
		}
	},

	add_create_buttons(frm) {
		const mk = (doctype) => frm.add_custom_button(__(doctype), () =>
			frappe.new_doc(doctype, { tower_site: frm.doc.name })
		, __("Create"));
		if (["Closed", "Cancelled"].includes(frm.doc.status)) return;
		if (frm.doc.feasibility_status !== "Go Ahead") mk("Site Feasibility Survey");
		mk("Daily Site Report");
		if (frm.doc.sales_order) mk("Joint Measurement Record");
		if (frm.doc.status === "RFI Done") mk("Site Support Visit");
		mk("Material Request");
	},

	render_summary(frm) {
		const fmt = (v) => format_currency(v || 0, frappe.defaults.get_default("currency"));
		const overdue = (frm.doc.milestones || []).filter((m) => m.status === "Overdue").length;
		const cards = [
			[__("Work Progress"), `${flt(frm.doc.overall_progress, 1)}%`],
			[__("PO Value"), fmt(frm.doc.po_value)],
			[__("Cost Booked"), fmt(frm.doc.total_cost)],
			[__("Margin"), `${fmt(frm.doc.gross_margin)} (${flt(frm.doc.margin_pct, 1)}%)`],
			[__("Overdue Milestones"), overdue],
			[__("Penalty Exposure"), fmt(frm.doc.total_penalty)],
		];
		frm.dashboard.clear_headline();
		frm.dashboard.set_headline_alert(
			`<div class="row">${cards
				.map(([l, v]) => `<div class="col-sm-2 col-xs-6"><div class="text-muted small">${l}</div><div class="bold">${v}</div></div>`)
				.join("")}</div>`
		);
	},

	latitude: (frm) => frm.set_value("location", ""),
	longitude: (frm) => frm.set_value("location", ""),
});

frappe.ui.form.on("Tower Site Milestone", {
	actual_date: (frm) => frm.dirty(),
	hold_days: (frm) => frm.dirty(),
});
