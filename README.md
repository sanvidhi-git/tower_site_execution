# Tower Site Execution

A Frappe / ERPNext v16 app for telecom tower subcontractors (Indus Towers TSPs). Each Indus site is run as its own project, with its own TAT tracking, daily supervisor reports, joint measurement, billing and per-site profit and loss.

Built by **Sanvidhi Tech Pvt. Ltd.** as a working demo for Crystal Interiors.

## How the business flow maps to ERPNext

| # | Crystal Interiors flow | In the system |
|---|---|---|
| 1 | PO with BOQ received from Indus | **Indus PO Import**: upload the Oracle PO-line Excel (plus the PO PDF and allotment email if you have them). The import creates the BOQ items, a **Sales Order** with every PO line (Indus task, line no., need-by date, HSN/SAC), the **Tower Site** and the **Project** |
| 2 | Internal project created | Auto-created **Project** (one per site). It has one **Task** per Indus TAT milestone, so the Gantt chart shows the site plan |
| 3 | Project team assigned | *Project Team* table on Tower Site (PM, supervisor, engineers) |
| 4 | Feasibility survey → Indus go-ahead | **Site Feasibility Survey** (soil, access, power, photos), followed by *Record Indus Go-Ahead* |
| 5 | Excavation: earth-moving vendor | Standard **Material Request → RFQ → Supplier Quotation → Purchase Order / Invoice**, tagged to the site project |
| 6 | RMC & steel procurement (advance or credit) | Same RFQ flow. Advance payments go through **Payment Entry** against the PO |
| 7–9 | Civil, tower support, electrical | **Daily Site Report** from each supervisor (mobile), with milestones C1, C2, C3, E1 and Solar I&C |
| 10 | Clearing site | Last DSR, then *Status → Mark Work Completed* |
| 11 | Joint measurement | **Joint Measurement Record**, with quantities pulled from the BOQ executed so far |
| 12 | Invoice | *JMR → Create → Sales Invoice*: invoices only the measured qty against the Indus SO lines |
| 13 | Payment | Standard **Payment Entry** (TDS handled through India Compliance) |
| 14 | 1-year site support | *RFI Accepted* starts the support period. **Site Support Visit** records inspection, maintenance and repair, and books its material and expenses to the same site project |

## Daily supervisor update (mobile)

The supervisor opens `https://<your-site>/daily-site-report` on a phone (a login-protected web form) or uses the desk form, and enters:

Site ID · Date · Work completed · Quantity completed (only items on that site's PO BOQ can be picked) · Labour count · Material used · Expenses with bill photos · Site photos · Pending work · Remarks. The phone's GPS location is captured automatically.

When the Project Manager submits a report:
* **Material used** posts a *Material Issue* Stock Entry from the site store, tagged to the site project.
* **Expenses** post a *Journal Entry*: each expense type debits its own expense account, and the site imprest/petty-cash account is credited.
* BOQ executed qty and % progress update on the site, the site moves to *Work In Progress*, and the selected TAT milestone is marked done.

## Mobile app: Sanvidhi Site

Site staff use the **Sanvidhi Site** Android app ([sanvidhi-git/tower_site_app](https://github.com/sanvidhi-git/tower_site_app)) for daily reports and material receipts, including when offline. The app talks to `tower_site_execution.mobile_api` (token login, sites assigned through the Tower Site *Project Team*, idempotent submissions using `mobile_ref`, photos stored as private files).

**Site Material Receipt** records what reached a site. The Project Manager or stores verifies it by submitting:
* *Vendor Delivery against PO*: creates a Purchase Receipt into the site warehouse (a draft by default, or auto-submitted per settings). Damaged quantity goes to *Rejected Material*.
* *Transfer from Store*: creates a Stock Entry (Material Transfer) from the store to the site warehouse
* *Indus Free-Issue Material*: logged with serial numbers. Indus-owned equipment is never counted as company stock.

Each Tower Site gets its own warehouse under *Tower Sites* (Tower Site Settings → *Auto-create a Warehouse per Tower Site*). Daily Site Report material is issued from the site warehouse when it has enough stock, and otherwise from the central store.

## Main dashboard

The **Site Execution** workspace has number cards for **Total allocated · Work not started · Work in progress · Work completed · RFI pending · RFI done**. Below them are charts by status, by zone, daily report activity and expenses booked. The **Site Status Summary** report shows the same table with drill-down.

Reports:
* **Site Status Summary**: the dashboard table, filterable by circle, zone, OPCO and allocation date
* **Site Profitability**: per site PO value, billed, material, site expenses, hire/purchases, cost, margin and TAT penalty exposure
* **Site TAT Tracker**: each Indus milestone planned vs actual, hold/curing days, delay and penalty (₹/day from the allotment terms)

## TAT engine

The milestone TATs and penalties are seeded from the Indus allotment email: HOTO 2 days (₹500/day) → Work start 3 → C1 7 (₹1,500/day) → C2 4 → C3 2 → E1 2 (₹5,000/day) → Solar I&C 1 → Ladder & Railing. Each milestone's planned date rolls forward from the previous one's actual (or planned) date. Hold/curing days extend that milestone's TAT. Delay and penalty are recalculated every night. All of these values can be edited in **Site Milestone Template**.

## Costing per site

Every cost document carries the site's Project, so ERPNext's project dimension gives a true site P&L:
* Material issued (Stock Entry, Material Issue)
* Site expenses (Journal Entries from DSR / Support Visit)
* Non-stock purchases: equipment hire, RMC delivered to site, subcontract labour (Purchase Invoice)

*View → Site P&L* on a Tower Site opens the General Ledger filtered to that project.

## Install

```bash
bench get-app https://github.com/<org>/tower_site_execution
bench --site <site> install-app tower_site_execution
```

Then open **Tower Site Settings** and set the company, the Indus Towers customer, the site store warehouse and the site imprest account. Map an expense account on each **Site Expense Type**.

### Sample demo data (test sites only)

```bash
bench --site <site> tower-demo                          # 30 demo sites in the site's company
bench --site <site> tower-demo --company "My Company"    # choose the company
bench --site <site> tower-demo --sites 12               # fewer sites
bench --site <site> tower-demo --files-dir /path/po     # also import a real Indus PO (.xlsx + .pdf)
bench --site <site> tower-demo --clear                  # remove all demo transactions and sites
bench --site <site> tower-demo --clear --clear-masters  # ...and the demo items, suppliers, users
```

No shell access (e.g. Frappe Cloud): **Tower Site Settings → Demo → Load Demo Data** (System Manager). This runs as a background job.

The demo creates:
* **Masters:** customer "Indus Towers Limited", 4 suppliers, site expense accounts and site imprest, a central store with opening stock, a 14-line demo BOQ, stock and service items, and 4 demo logins: rahul (Project Manager) plus santosh, imran and ganesh (supervisors) `@towerdemo.local`, password `Demo@1234`.
* **Sites:** 30 sites (5 RFI Done, 5 RFI Pending, 5 Work Completed, 10 Work In Progress, 5 Work Not Started). Each has a Sales Order, a project with milestone tasks, a site warehouse and a survey. Depending on its status it also gets daily site reports (material and expenses), JCB/RMC purchase invoices, a vendor PO with material receipts (PO delivery, store transfer, Indus free-issue, plus one left for PM approval), JMR and invoice, and a support visit.
* **Dates:** documents are back-dated over the last ~5 months, and missing fiscal years are created. Works with or without India Compliance (HSN/SAC codes and GST categories are set). Running it again skips sites that already exist. Every demo site is tagged, so `--clear` removes only demo data.

## Other modules (standard ERPNext / Frappe HR)

Accounting, Buying (RFQ / supplier comparison), Stock, HRMS (payroll, leave, expense claims) and GST via India Compliance are used as shipped. Attendance and live tracking can use Frappe HR check-ins with geolocation, or the Sanvidhi ESS Android app (selfie + geo attendance, travel tracking).

## Roles

* **Site Supervisor**: creates Daily Site Reports, Feasibility Surveys and Support Visits; reads Tower Sites
* **Site Project Manager**: everything on sites; submits/approves DSRs, which posts stock and expenses; JMR and invoicing

License: MIT
