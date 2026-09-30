"""Create the collected data in ERPNext.

The last step of an onboarding: everything the customer gave us, checked and
fixed, becomes real records. Until now Embark prepared a spreadsheet and
somebody imported it by hand.

Three rules make this safe to press twice:

* **Order.** Item groups before items, warehouses before stock, workstations
  before the operations that name them. The steps carry a sequence already, and
  that is the order used.
* **Skip what exists.** A record whose key is already there is left alone and
  counted as skipped, so a second run creates nothing and changes nothing.
* **One row, one failure.** A row that ERPNext refuses is recorded with its
  reason and the rest carry on — an import is never half a row.

Nothing here invents values. What goes in is what the check screen showed, and
a step with errors is not imported at all.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import strip_html

from embark.engine import build_columns

# Fields ERPNext insists on that are not the customer's to give: their company,
# and the flags a new record needs to be usable.
COMPANY_FIELDS_CACHE: dict[str, list[str]] = {}

DEFAULTS = {
	"User": {"send_welcome_email": 0, "enabled": 1, "user_type": "System User"},
	"Item": {"is_stock_item": 1},
	"Warehouse": {"is_group": 0},
	"Customer": {},
	"Supplier": {},
}


def company_fields(doctype: str) -> list[str]:
	"""The required Company links on a doctype, which the onboarding answers."""
	if doctype not in COMPANY_FIELDS_CACHE:
		meta = frappe.get_meta(doctype)
		COMPANY_FIELDS_CACHE[doctype] = [
			df.fieldname
			for df in meta.fields
			if df.fieldtype == "Link" and df.options == "Company" and df.reqd
		]
	return COMPANY_FIELDS_CACHE[doctype]


def import_all(onboarding) -> dict:
	"""Create every ready step's rows, in the order the steps are asked for."""
	company = _company(onboarding)
	steps = []
	for row in sorted(onboarding.areas, key=lambda r: _sequence(r.data_area)):
		steps.append(import_area(onboarding, row.data_area, company))

	return {
		"company": company,
		"created": sum(s["created"] for s in steps),
		"skipped": sum(s["skipped"] for s in steps),
		"failed": sum(len(s["failures"]) for s in steps),
		"steps": steps,
	}


def import_area(onboarding, area: str, company: str | None = None) -> dict:
	"""One step: its checked rows become records, or the reason they could not."""
	out = {"area": area, "created": 0, "skipped": 0, "failures": [], "reason": ""}
	name = frappe.db.get_value("Embark Upload", {"onboarding": onboarding.name, "data_area": area}, "name")
	if not name:
		out["reason"] = _("Nothing was uploaded for this step.")
		return out

	upload = frappe.get_doc("Embark Upload", name)
	evaluated = upload.evaluate()
	if evaluated.result.errors:
		out["reason"] = _("{0} still has {1} to fix.").format(area, evaluated.result.errors)
		return out

	area_doc = frappe.get_cached_doc("Embark Data Area", area)
	doctype = area_doc.target_doctype
	columns = build_columns(area_doc, onboarding.answer_map())
	fields = {c.fieldname for c in columns if not c.is_extra}
	key = area_doc.key_field
	company = company or _company(onboarding)

	for row in evaluated.result.rows:
		values = {f: row.get(f) for f in fields if row.get(f) not in (None, "")}
		# Some records are named by the thing itself — an Operation called
		# "Cutting" has no operation_name field, the name *is* "Cutting".
		named = row.get(key) if key else None
		if not values and not named:
			continue
		if key and _exists(doctype, key, named, company):
			out["skipped"] += 1
			continue
		try:
			_create(doctype, values, company, named)
			out["created"] += 1
		except Exception as e:
			frappe.db.rollback(save_point="embark_row")
			out["failures"].append({"row": row.get("_row"), "why": _why(e)})
			# The reason belongs in the summary, not in a popup on top of it.
			frappe.clear_messages()

	return out


def _why(e: Exception) -> str:
	"""ERPNext's own reason, in plain text: its messages are written for people."""
	return " ".join(strip_html(str(e)).split())[:200] or _("ERPNext refused this row.")


def _create(doctype: str, values: dict, company: str | None, named: str | None = None) -> None:
	"""One record, inside a save point so a refusal costs only that row."""
	frappe.db.savepoint("embark_row")
	doc = frappe.new_doc(doctype)
	doc.update(DEFAULTS.get(doctype, {}))
	doc.update(values)
	for field in company_fields(doctype):
		if company and not doc.get(field):
			doc.set(field, company)
	if named and _named_by_hand(doctype):
		doc.name = named
	doc.insert(ignore_permissions=True)


def _named_by_hand(doctype: str) -> bool:
	"""Does ERPNext expect whoever creates this to supply the name?"""
	return (frappe.get_meta(doctype).autoname or "").lower() == "prompt"


def _exists(doctype: str, key: str, value, company: str | None) -> bool:
	"""Is this record already in ERPNext? Then leave it alone.

	Looked up by the step's key — the field a human would call the record by.
	Where records belong to a company, only that company's are counted, so a
	second company's warehouse of the same name is still created.
	"""
	if value in (None, ""):
		return False
	meta = frappe.get_meta(doctype)
	# The key is either the record's own name or a field to look it up by.
	if not meta.has_field(key) or (meta.autoname or "").startswith(f"field:{key}"):
		return bool(frappe.db.exists(doctype, value))
	filters = {key: value}
	scope = company_fields(doctype) or [f for f in ("company",) if meta.has_field(f)]
	if company and scope:
		filters[scope[0]] = company
	return bool(frappe.db.exists(doctype, filters) or frappe.db.exists(doctype, value))


def _company(onboarding) -> str | None:
	"""The company these records belong to: the one named in the onboarding."""
	if onboarding.company_name and frappe.db.exists("Company", onboarding.company_name):
		return onboarding.company_name
	return frappe.db.get_value("Company", {}, "name", order_by="creation asc")


def _sequence(area: str) -> int:
	return frappe.get_cached_value("Embark Data Area", area, "sequence") or 0
