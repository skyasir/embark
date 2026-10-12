"""Configure ERPNext from the plan, instead of printing the plan.

Embark works out what a standard implementation needs switched on. Until now it
wrote that down and a person went and did it by hand in the desk, which is the
opposite of what this tool is for: the point is that a standard implementation
runs itself.

Each recipe below belongs to one line of the plan, keyed by the setup task it
implements. A recipe says nothing about *whether* the line applies — the
interview already decided that — only what writing it means in ERPNext.

Three rules:

* **It is the same machinery Studio uses.** Every recipe produces rows for an
  Embark Change Set, so each change is snapshotted before it is written, shown
  before and after, and can be put back.
* **Nothing is guessed.** A recipe only writes fields that exist on this site,
  and only values the interview actually supports. A line with no recipe stays a
  line for a person to do, and says so.
* **Settings only.** These are the switches that decide how ERPNext behaves.
  Master data is the data steps' job, and the customer's own numbers — tax
  rates, opening balances — are nobody's to invent.
"""

from __future__ import annotations

import json

import frappe
from frappe import _


def _update(doctype: str, values: dict, summary: str) -> dict:
	"""One change row: a settings record brought to what the plan says."""
	return {
		"action": "Update",
		"ref_doctype": doctype,
		"ref_name": doctype,  # these are all Singles
		"summary": summary,
		"payload": json.dumps(values),
	}


# ── The recipes ───────────────────────────────────────────────────────────────
# Keyed by Embark Setup Task.task_key. Each takes the onboarding and returns the
# changes that line means, or [] when there is nothing left to do.


def _sales_flow(doc) -> list[dict]:
	return [
		_update(
			"Selling Settings",
			{"so_required": "Yes"},
			_("Selling runs through a Sales Order before an invoice"),
		)
	]


def _partial_delivery(doc) -> list[dict]:
	return [
		_update(
			"Selling Settings",
			{"dn_required": "Yes"},
			_("An invoice follows a Delivery Note, so part deliveries are tracked"),
		)
	]


def _purchase_flow(doc) -> list[dict]:
	return [
		_update(
			"Buying Settings",
			{"po_required": "Yes"},
			_("Buying runs through a Purchase Order before a bill"),
		)
	]


def _partial_receipt(doc) -> list[dict]:
	return [
		_update(
			"Buying Settings",
			{"pr_required": "Yes", "maintain_same_rate": 1},
			_("A bill follows a Purchase Receipt, at the rate that was ordered"),
		)
	]


def _batch_or_serial(doc) -> list[dict]:
	# One switch serves both; v16 ships it off, and every Serial and Batch
	# Bundle fails until it is on.
	return [
		_update(
			"Stock Settings",
			{"enable_serial_and_batch_no_for_item": 1},
			_("Serial and batch tracking is available on items"),
		)
	]


def _manufacturing(doc) -> list[dict]:
	return [
		_update(
			"Manufacturing Settings",
			{"update_bom_costs_automatically": 1, "backflush_raw_materials_based_on": "BOM"},
			_("BOM costs stay current, and materials are consumed as the BOM says"),
		)
	]


def _multi_currency(doc) -> list[dict]:
	return [
		_update(
			"Accounts Settings",
			{"allow_stale": 0},
			_("A stale exchange rate is refused rather than quietly used"),
		)
	]


def _price_lists(doc) -> list[dict]:
	"""The price lists the customer's own sheet names, created if missing.

	Their rates are their business; the lists those rates live on are
	configuration, and an Item Price cannot be imported without them.
	"""
	from embark.engine import build_columns

	wanted: list[str] = []
	for row in doc.areas:
		if row.data_area != "Item Prices":
			continue
		name = frappe.db.get_value(
			"Embark Upload", {"onboarding": doc.name, "data_area": row.data_area}, "name"
		)
		if not name:
			continue
		upload = frappe.get_doc("Embark Upload", name)
		area = frappe.get_cached_doc("Embark Data Area", row.data_area)
		build_columns(area, doc.answer_map())
		for line in upload.evaluate().result.rows:
			value = (line.get("price_list") or "").strip()
			if value and value not in wanted:
				wanted.append(value)

	return [
		{
			"action": "Create",
			"ref_doctype": "Price List",
			"ref_name": None,
			"summary": _("Price list {0}").format(value),
			"payload": json.dumps(
				{
					"price_list_name": value,
					"enabled": 1,
					"selling": 1,
					"currency": doc.default_currency or "INR",
				}
			),
		}
		for value in wanted
		if not frappe.db.exists("Price List", value)
	]


def _tax_setup(doc) -> list[dict]:
	"""Tax accounts and ready-made templates, one set per rate they charge.

	A standard implementation stands or falls on this: without templates nobody
	can raise a correct invoice, and ERPNext ships none. The rates come from the
	interview, and nothing else is invented — the accounts hang under the chart
	of accounts' own "Duties and Taxes" group, and the rate on each template is
	the rate they said.
	"""
	rates = [r for r in (answers(doc).get("tax_rates") or "").split(",") if r.strip()]
	company = _company_of(doc)
	if not (rates and company):
		return []

	parent = frappe.db.get_value(
		"Account", {"company": company, "account_name": "Duties and Taxes", "is_group": 1}, "name"
	)
	if not parent:
		return []

	abbr = frappe.db.get_value("Company", company, "abbr")
	changes = []
	for rate in rates:
		rate = rate.strip()
		heads = {}
		for side, word in (("Output", _("charged on what you sell")), ("Input", _("paid on what you buy"))):
			account_name = f"{side} Tax {rate}%"
			heads[side] = f"{account_name} - {abbr}"
			if not frappe.db.exists("Account", heads[side]):
				changes.append(
					{
						"action": "Create",
						"ref_doctype": "Account",
						"ref_name": None,
						"summary": _("Account {0} — tax {1}").format(account_name, word),
						"payload": json.dumps(
							{
								"account_name": account_name,
								"parent_account": parent,
								"company": company,
								"account_type": "Tax",
								"is_group": 0,
								"tax_rate": float(rate),
							}
						),
					}
				)

		title = f"Tax {rate}%"
		for doctype, head, label in (
			("Sales Taxes and Charges Template", heads["Output"], _("on sales")),
			("Purchase Taxes and Charges Template", heads["Input"], _("on purchases")),
		):
			if frappe.db.exists(doctype, {"title": title, "company": company}):
				continue
			changes.append(
				{
					"action": "Create",
					"ref_doctype": doctype,
					"ref_name": None,
					"summary": _("{0}% {1}, ready to pick on a document").format(rate, label),
					"payload": json.dumps(
						{
							"title": title,
							"company": company,
							"taxes": [
								{
									"charge_type": "On Net Total",
									"account_head": head,
									"description": title,
									"rate": float(rate),
								}
							],
						}
					),
				}
			)

		if not frappe.db.exists("Item Tax Template", {"title": title, "company": company}):
			changes.append(
				{
					"action": "Create",
					"ref_doctype": "Item Tax Template",
					"ref_name": None,
					"summary": _("Item tax group {0}, to put on the items it applies to").format(title),
					"payload": json.dumps(
						{
							"title": title,
							"company": company,
							"taxes": [
								{"tax_type": heads["Output"], "tax_rate": float(rate)},
								{"tax_type": heads["Input"], "tax_rate": float(rate)},
							],
						}
					),
				}
			)

	return changes


def answers(doc) -> dict[str, str]:
	"""The answers that still count.

	An answer stays on the record after its question stops being asked — say
	the customer answers a tax rate and then tells us they are not registered.
	The plan already ignores those: a condition on a question outside the
	interview reads false. A recipe has to read them the same way, or it
	configures a site from something nobody is being asked any more.
	"""
	from embark.engine import asked_keys

	given = doc.answer_map()
	asked = asked_keys(given)
	return {key: value for key, value in given.items() if key in asked}


def _company_of(doc) -> str | None:
	if doc.company_name and frappe.db.exists("Company", doc.company_name):
		return doc.company_name
	return frappe.db.get_value("Company", {}, "name", order_by="creation asc")


RECIPES = {
	"tax_setup": _tax_setup,
	"sales_flow": _sales_flow,
	"partial_delivery": _partial_delivery,
	"purchase_flow": _purchase_flow,
	"partial_receipt": _partial_receipt,
	"batches": _batch_or_serial,
	"serials": _batch_or_serial,
	"manufacturing": _manufacturing,
	"multi_currency": _multi_currency,
	"price_lists": _price_lists,
}


def can_apply(task_key: str) -> bool:
	"""Is this a line Embark can do itself?"""
	return task_key in RECIPES


def plan_changes(doc, task_key: str) -> list[dict]:
	"""What this line means in ERPNext, as change rows — nothing written yet."""
	recipe = RECIPES.get(task_key)
	if not recipe:
		return []
	return [row for row in recipe(doc) if _still_needed(row)]


def _still_needed(row: dict) -> bool:
	"""Drop a change the site has already made, so applying twice is a no-op."""
	payload = frappe.parse_json(row["payload"]) or {}
	if row["action"] == "Create":
		return True
	if not frappe.db.exists(row["ref_doctype"], row["ref_name"]):
		return False
	current = frappe.get_cached_doc(row["ref_doctype"], row["ref_name"])
	return any(str(current.get(field)) != str(value) for field, value in payload.items())


def preview(doc, task_key: str) -> list[dict]:
	"""Before and after for every field this line would write."""
	out = []
	for row in plan_changes(doc, task_key):
		payload = frappe.parse_json(row["payload"]) or {}
		existing = (
			frappe.get_cached_doc(row["ref_doctype"], row["ref_name"])
			if row["ref_name"] and frappe.db.exists(row["ref_doctype"], row["ref_name"])
			else None
		)
		out.append(
			{
				"summary": row["summary"],
				"doctype": row["ref_doctype"],
				"action": row["action"],
				"lines": [
					{
						"field": _label(row["ref_doctype"], field),
						"before": _shown(existing.get(field)) if existing else "",
						"after": _shown(value),
					}
					for field, value in payload.items()
				],
			}
		)
	return out


def apply(doc, task_key: str) -> dict:
	"""Write this line to the site, and remember that it was Embark that did it."""
	changes = plan_changes(doc, task_key)
	row = next((r for r in doc.tasks if r.setup_task == task_key), None)
	if not row:
		frappe.throw(_("{0} is not on this plan.").format(task_key))

	if not changes:
		# Already true on this site. Saying so is more use than doing nothing.
		row.db_set("status", "Done")
		return {"task": task_key, "already": True, "changes": [], "change_set": None}

	title = _("Embark: {0}").format(row.title)
	change_set = frappe.get_doc(
		{
			"doctype": "Embark Change Set",
			"title": title[:140],
			"request": _("Configured from the onboarding plan of {0}.").format(doc.client_name),
			"changes": changes,
		}
	).insert(ignore_permissions=True)
	change_set.apply()

	row.db_set("status", "Done")
	row.db_set("notes", _("Configured by Embark · {0}").format(change_set.name))
	return {
		"task": task_key,
		"already": False,
		"changes": [c["summary"] for c in changes],
		"change_set": change_set.name,
	}


def _label(doctype: str, fieldname: str) -> str:
	field = frappe.get_meta(doctype).get_field(fieldname)
	return _(field.label) if field and field.label else fieldname


def _shown(value) -> str:
	if value in (None, "", []):
		return ""
	if value is True or value == 1:
		return _("Yes")
	if value is False or value == 0:
		return _("No")
	return str(value)[:140]
