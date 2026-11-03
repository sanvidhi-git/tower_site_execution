"""Parsers for Indus Towers documents (no Frappe dependency, unit-testable).

* parse_po_excel  - Oracle iSupplier "PO line" export (.xlsx) - one row per PO line
                    followed by a "Milestone" row holding the Need-By date
* parse_po_pdf    - Indus PO PDF: header (PO No, date, GBPA, amendment, buyer, circle)
                    and HSN / SAC per item code
* parse_allotment_email - the site allotment mail (Reference ID, OPCO, lat/long, Indus contacts...)
"""

import re
from datetime import date, datetime


def _num(v):
	if v in (None, ""):
		return 0.0
	if isinstance(v, (int, float)):
		return float(v)
	try:
		return float(str(v).replace(",", "").strip())
	except ValueError:
		return 0.0


def _date(v):
	if isinstance(v, datetime):
		return v.date()
	if isinstance(v, date):
		return v
	if not v:
		return None
	s = str(v).strip()
	for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%b-%Y %H:%M:%S", "%d-%b-%Y", "%d-%b-%y", "%d/%m/%Y"):
		try:
			return datetime.strptime(s.title() if "%b" in fmt else s, fmt).date()
		except ValueError:
			continue
	return None


def parse_po_excel(path):
	import openpyxl

	wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
	ws = wb.worksheets[0]
	rows = [list(r) for r in ws.iter_rows(values_only=True)]

	header = {}
	lines = []
	col = None
	for i, row in enumerate(rows):
		cells = [str(c).strip() if c is not None else "" for c in row]
		# PO header block: "Total | Supplier | ... | Buyer | Order Date | Description ..."
		if not header and "Supplier" in cells and "Buyer" in cells and i + 1 < len(rows):
			vals = rows[i + 1]
			hmap = {}
			for j, name in enumerate(cells):
				if name and name not in hmap:
					hmap[name] = vals[j] if j < len(vals) else None
			header = {
				"supplier": hmap.get("Supplier"),
				"buyer": hmap.get("Buyer"),
				"order_date": _date(hmap.get("Order Date")),
				"description": hmap.get("Description"),
				"circle": hmap.get("Operating Unit"),
				"po_total": _num(hmap.get("Total")),
			}
			m = re.search(r"(R/[A-Z]+-\d+)", str(hmap.get("Description") or ""))
			if m:
				header["reference_id"] = m.group(1)
			continue
		if col is None and cells and cells[0] == "Line" and "Item Num" in cells:
			col = {}
			for j, name in enumerate(cells):
				if name and name not in col:
					col[name] = j
			continue
		if col is None or not cells or not cells[0]:
			continue

		def g(name, r=row):
			j = col.get(name)
			return r[j] if j is not None and j < len(r) else None

		try:
			line_no = int(float(cells[0]))
		except ValueError:
			continue
		is_milestone = "Milestone" in cells
		if not is_milestone and g("Qty") is not None:
			lines.append(
				{
					"line_no": line_no,
					"item_code": str(g("Item Num") or "").strip(),
					"description": str(g("Description") or "").strip(),
					"uom": str(g("UOM") or "").strip(),
					"qty": _num(g("Qty")),
					"rate": _num(g("Price")),
					"amount": _num(g("Amount")),
					"line_status": str(g("Status") or "").strip(),
					"site_id": str(g("Site ID") or "").strip(),
					"site_owner": str(g("Site Address") or "").strip(),
					"reference_id": str(g("Project Name") or "").strip(),
					"task_name": str(g("Task Name") or "").strip(),
					"need_by_date": None,
				}
			)
		elif is_milestone and lines and lines[-1]["line_no"] == line_no:
			nb = col.get("Need-By Date")
			if nb is not None and nb < len(row):
				lines[-1]["need_by_date"] = _date(row[nb])
	return header, lines


HEADER_LABELS = [
	("Document Type", "document_type"),
	("P.O No", "po_no"),
	("Date", "po_date"),
	("Amendment No", "amendment_no"),
	("Amendment Date", "amendment_date"),
	("Po Subtype", "po_subtype"),
	("GBPA No.", "gbpa_no"),
	("GBPA Valid from", "gbpa_valid_from"),
	("GBPA Valid up to", "gbpa_valid_upto"),
	("Buyer", "buyer"),
]


def parse_po_pdf_text(text):
	lines = [ln.rstrip() for ln in text.splitlines()]
	header = {}

	# header: labels are printed in one block, values (": xxx") in the next block, same order
	try:
		start = next(i for i, ln in enumerate(lines) if ln.strip() == "Document Type")
		labels = []
		i = start
		while i < len(lines) and not lines[i].strip().startswith(":"):
			labels.append(lines[i].strip())
			i += 1
		values = []
		while i < len(lines) and lines[i].strip().startswith(":") and len(values) < len(labels):
			values.append(lines[i].strip()[1:].strip())
			i += 1
		label_map = dict(HEADER_LABELS)
		for lab, val in zip(labels, values):
			if lab in label_map:
				header[label_map[lab]] = val
	except StopIteration:
		pass
	# fall back to inline "Label : value" style
	for lab, key in HEADER_LABELS:
		if key not in header:
			m = re.search(rf"^{re.escape(lab)}\s*:\s*(.+)$", text, re.M)
			if m:
				header[key] = m.group(1).strip()
	for key in ("po_date", "amendment_date", "gbpa_valid_from", "gbpa_valid_upto"):
		if header.get(key):
			header[key] = _date(header[key].split()[0])
	for lab, key in (("Circle", "circle"), ("Indus ID", "site_id"), ("Project No", "reference_id"), ("GSTIN", "supplier_gstin")):
		m = re.search(rf"^{lab}\s*:\s*(\S[^\n]*?)(?:\s{{2,}}|\s+Warehouse-Code|$)", text, re.M)
		if m:
			header[key] = m.group(1).strip()

	# HSN / SAC per item: "<sr> <item-code-part>" [continuation] "HSN No : x" "SAC No : y"
	hsn = {}
	code_buf = None
	for ln in lines:
		s = ln.strip()
		m = re.match(r"^(\d{1,3})\s+([0-9A-Z]{2}-[0-9A-Z-]*)$", s)
		if m:
			code_buf = m.group(2)
			continue
		if code_buf is not None:
			if s.startswith("HSN No"):
				hsn_val = s.split(":", 1)[1].strip() if ":" in s else ""
				hsn[code_buf] = {"hsn": hsn_val}
				continue
			if s.startswith("SAC No"):
				sac_val = s.split(":", 1)[1].strip() if ":" in s else ""
				hsn.setdefault(code_buf, {})["sac"] = sac_val
				code_buf = None
				continue
			if re.match(r"^[0-9A-Z]+$", s) and code_buf.endswith("-"):
				code_buf += s
				continue
	return header, {k: (v.get("hsn") or v.get("sac") or "") for k, v in hsn.items()}


def parse_po_pdf(path):
	from pypdf import PdfReader

	reader = PdfReader(path)
	text = "\n".join((p.extract_text() or "") for p in reader.pages)
	return parse_po_pdf_text(text)


EMAIL_LABELS = {
	"Reference ID": "reference_id",
	"Principle OPCO": "principal_opco",
	"Principal OPCO": "principal_opco",
	"Category": "category",
	"Indus Site ID": "indus_site_id",
	"Opco ID": "opco_id",
	"Nominal Name": "nominal_name",
	"Product Type": "product_type",
	"Owner Details": "site_owner_details",
	"Site Details": "site_address",
	"Lat": "latitude",
	"Long": "longitude",
	"Tower Type": "tower_type",
	"Tower Height": "tower_height",
	"District": "district",
	"Area Name": "area_name",
	"Zone": "zone",
	"ZPM Name": "zpm_name",
	"DE Name": "de_name",
	"ACQ": "acq_name",
	"Acquisition TL Name": "acq_tl_name",
	"Region": "region",
	"PM": "pm_name",
	"AOM Name": "aom_name",
	"FSE": "fse_name",
	"TSP Team": "tsp_team",
	"Remark": "allotment_remarks",
}
_ORDERED = sorted(EMAIL_LABELS, key=len, reverse=True)
_STOP = re.compile(r"^(Milestones|Allocation to HOTO|TAT )", re.I)


def parse_allotment_email(text):
	out = {}
	if not text:
		return out
	raw = [ln.strip().strip("|").strip() for ln in text.replace("\r", "").split("\n")]
	raw = [ln for ln in raw if ln and not set(ln) <= set("-=| ")]
	i = 0
	current = None
	while i < len(raw):
		ln = raw[i]
		if _STOP.match(ln):
			break
		matched = None
		for lab in _ORDERED:
			if ln.lower() == lab.lower() or re.match(rf"^{re.escape(lab)}(\s*[:|\t]\s*|\s{{2,}}|\s+)(.+)$", ln, re.I):
				matched = lab
				break
		if matched:
			key = EMAIL_LABELS[matched]
			rest = ln[len(matched):].strip(" :|\t")
			if not rest and i + 1 < len(raw):
				nxt = raw[i + 1]
				if not any(nxt.lower() == lab.lower() or nxt.lower().startswith(lab.lower() + " ") for lab in _ORDERED):
					rest = nxt
					i += 1
			out[key] = rest
			current = key
		elif current in ("site_owner_details", "site_address", "allotment_remarks") and current in out:
			out[current] = (out[current] + " " + ln).strip()  # wrapped table cell
		i += 1
	if "category" in out:
		cat = out["category"].strip().lower()
		mapping = {"relocation": "Relocation", "new build": "New Build", "upgrade": "Upgrade", "strengthening": "Strengthening"}
		out["category"] = mapping.get(cat, "Other")
	for k in ("latitude", "longitude", "tower_height"):
		if k in out:
			m = re.search(r"-?\d+(\.\d+)?", out[k])
			out[k] = float(m.group(0)) if m else None
	if "principal_opco" in out:
		op = out["principal_opco"].lower()
		out["principal_opco"] = next(
			(v for k, v in (("airtel", "Airtel"), ("jio", "Jio"), ("voda", "Vodafone Idea"), ("vi", "Vodafone Idea"), ("bsnl", "BSNL")) if op.startswith(k)),
			"Other",
		)
	return out
