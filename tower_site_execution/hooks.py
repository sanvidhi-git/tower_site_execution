app_name = "tower_site_execution"
app_title = "Tower Site Execution"
app_publisher = "Sanvidhi Tech Pvt. Ltd."
app_description = "Site-wise execution, TAT, DSR, JMR and costing for telecom tower subcontractors on ERPNext"
app_email = "info@sanvidhitech.com"
app_license = "mit"
required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "tower_site_execution",
		"logo": "/assets/tower_site_execution/tower.svg",
		"title": "Site Execution",
		"route": "/app/site-execution",
	}
]

after_install = "tower_site_execution.install.after_install"
after_migrate = "tower_site_execution.install.after_migrate"

doctype_js = {"Project": "public/js/project.js"}

doc_events = {
	"Sales Invoice": {
		"on_submit": "tower_site_execution.events.sales_invoice_changed",
		"on_cancel": "tower_site_execution.events.sales_invoice_changed",
	},
	"Purchase Invoice": {
		"on_submit": "tower_site_execution.events.cost_document_changed",
		"on_cancel": "tower_site_execution.events.cost_document_changed",
	},
	"Journal Entry": {
		"on_submit": "tower_site_execution.events.cost_document_changed",
		"on_cancel": "tower_site_execution.events.cost_document_changed",
	},
	"Stock Entry": {
		"on_submit": "tower_site_execution.events.cost_document_changed",
		"on_cancel": "tower_site_execution.events.cost_document_changed",
	},
}

scheduler_events = {
	"daily": [
		"tower_site_execution.tower_site_execution.doctype.tower_site.tower_site.daily_site_refresh",
	],
}
