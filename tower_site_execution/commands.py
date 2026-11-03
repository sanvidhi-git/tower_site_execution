import click
from frappe.commands import get_site, pass_context


@click.command("tower-demo")
@click.option("--company", help="Company to load the demo into (default: Tower Site Settings / default company)")
@click.option("--files-dir", help="Folder with a real Indus PO export (.xlsx) and PO PDF to import as one of the sites")
@click.option("--sites", default=30, type=int, show_default=True, help="Number of demo sites")
@click.option("--email-domain", default="towerdemo.local", show_default=True, help="Domain for demo user logins")
@click.option("--clear", is_flag=True, help="Remove the demo data instead of creating it")
@click.option("--clear-masters", is_flag=True, help="With --clear: also remove demo items, suppliers and users")
@pass_context
def tower_demo(context, company=None, files_dir=None, sites=30, email_domain=None, clear=False, clear_masters=False):
	"""Load (or --clear) sample demo data for Tower Site Execution. TEST SITES ONLY."""
	import frappe

	from tower_site_execution import demo

	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	try:
		if clear:
			demo.clear_demo(masters=clear_masters)
		else:
			demo.make_demo(company=company, files_dir=files_dir, sites=sites, email_domain=email_domain)
		frappe.db.commit()
	finally:
		frappe.destroy()


commands = [tower_demo]
