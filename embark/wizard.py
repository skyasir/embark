"""The setup wizard: one question at a time, each answer a field in ERPNext.

This is the implementation itself, asked as questions. Every task names the
record it produces — Company, System Settings, Fiscal Year, Warehouse — and
every question under it fills one field of that record. Answer a task and
Embark writes it, through the same change set everything else goes through, so
it is previewed before and reversible after.

Nothing here is a form that gets posted somewhere. A question knows which field
it fills, which means the wizard can say what it is about to do, show the record
once it exists, and never ask for the same thing twice.
"""

from __future__ import annotations

import frappe
from frappe import _

from embark.conditions import applies


def Q(
	key, task, label, description, *, field="", kind="Text", options="", example="", reqd=0, when="", seq=0
):
	return {
		"question_key": key,
		"task": task,
		"label": label,
		"description": description,
		"fieldname": field,
		"answer_type": kind,
		"options": options,
		"example": example,
		"is_required": reqd,
		"applies_when": when,
		"sequence": seq,
	}


TASKS = [
	{
		"task_name": "Create a company",
		"sequence": 10,
		"icon": "briefcase",
		"target_doctype": "Company",
		"description": "The business itself. Everything in ERPNext hangs off this record: your ledgers, your stock, your invoices.",
	},
	{
		"task_name": "Choose your modules",
		"sequence": 15,
		"icon": "grid",
		"description": "Which parts of ERPNext this business will run. Everything after this step is decided by the answer — a module you leave out is never mentioned again.",
	},
	{
		"task_name": "Set the system timezone",
		"sequence": 20,
		"icon": "globe",
		"target_doctype": "System Settings",
		"is_single": 1,
		"description": "Every document records when it was made. The timezone decides what time that is.",
	},
	{
		"task_name": "Set date and number format",
		"sequence": 30,
		"icon": "calendar",
		"target_doctype": "System Settings",
		"is_single": 1,
		"description": "How dates and amounts are written everywhere — on screen, on invoices, in exports.",
	},
	{
		"task_name": "Set currency and float precision",
		"sequence": 40,
		"icon": "hash",
		"target_doctype": "System Settings",
		"is_single": 1,
		"description": "How many decimal places money and quantities carry, and how the odd fraction is rounded.",
	},
	{
		"task_name": "Create a fiscal year",
		"sequence": 50,
		"icon": "calendar",
		"target_doctype": "Fiscal Year",
		"description": "The twelve months your books are kept in. Nothing can be posted outside one.",
	},
	{
		"task_name": "Set company default accounts",
		"sequence": 60,
		"icon": "book",
		"target_doctype": "Company",
		"description": "Which ledger each kind of entry lands in, so nobody has to pick one on every document.",
		"applies_when": "modules == accounts",
	},
	{
		"task_name": "Create an item group",
		"sequence": 70,
		"icon": "layers",
		"target_doctype": "Item Group",
		"description": "How your products and services are grouped. Reports, taxes and defaults all follow these.",
		"applies_when": "modules == stock,selling,buying,manufacturing",
	},
	{
		"task_name": "Create a customer group",
		"sequence": 80,
		"icon": "user-check",
		"target_doctype": "Customer Group",
		"description": "How your customers are grouped — wholesale, retail, government — for pricing and reporting.",
		"applies_when": "modules == selling,crm",
	},
	{
		"task_name": "Create a supplier group",
		"sequence": 90,
		"icon": "truck",
		"target_doctype": "Supplier Group",
		"description": "How your suppliers are grouped, for reporting and for default payment terms.",
		"applies_when": "modules == buying",
	},
	{
		"task_name": "Create a territory",
		"sequence": 100,
		"icon": "map-pin",
		"target_doctype": "Territory",
		"description": "The places you sell into. Sales can then be read by region, and prices can differ by one.",
		"applies_when": "modules == selling,crm",
	},
	{
		"task_name": "Create a parent warehouse",
		"sequence": 110,
		"icon": "archive",
		"target_doctype": "Warehouse",
		"description": "A group warehouse that holds other warehouses — a city, a site, a building. Nothing is stocked in it directly.",
		"applies_when": "modules == stock",
	},
	{
		"task_name": "Create a child warehouse",
		"sequence": 120,
		"icon": "archive",
		"target_doctype": "Warehouse",
		"description": "A place stock actually sits: a godown, a shop floor, a van.",
		"applies_when": "modules == stock",
	},
	{
		"task_name": "Create a unit of measure",
		"sequence": 130,
		"icon": "hash",
		"target_doctype": "UOM",
		"description": "A unit you buy, sell or stock in that ERPNext does not already know.",
		"applies_when": "modules == stock,manufacturing",
	},
]


QUESTIONS = [
	# ── Create a company ────────────────────────────────────────────────
	Q(
		"company_name",
		"Create a company",
		"What is the registered name of the company?",
		"The legal name on your invoices and filings, not a short name or a brand. It appears at the top of every document ERPNext prints.",
		field="company_name",
		example="Sunrise Traders Private Limited",
		reqd=1,
		seq=10,
	),
	Q(
		"company_abbr",
		"Create a company",
		"What short code should stand for the company?",
		"Two to five letters. ERPNext puts it at the end of every account and warehouse name so two companies on one site never collide — 'Stores - STPL'.",
		field="abbr",
		example="STPL",
		reqd=1,
		seq=20,
	),
	Q(
		"company_country",
		"Create a company",
		"Which country is the company registered in?",
		"This decides the chart of accounts ERPNext starts you with, the tax rules available, and the default currency.",
		field="country",
		kind="Link",
		options="Country",
		example="India",
		reqd=1,
		seq=30,
	),
	Q(
		"company_currency",
		"Create a company",
		"Which currency are the books kept in?",
		"The currency your accounts are reported in. You can still invoice in others — those are converted back to this one.",
		field="default_currency",
		kind="Link",
		options="Currency",
		example="INR",
		reqd=1,
		seq=40,
	),
	Q(
		"company_tax_id",
		"Create a company",
		"What is the company's tax registration number?",
		"Your GSTIN, VAT number or equivalent. It is printed on invoices and used by the tax reports. Leave blank if the business is not registered.",
		field="tax_id",
		example="27AAACS1234A1Z5",
		seq=50,
	),
	Q(
		"company_established",
		"Create a company",
		"When was the company established?",
		"Used on reports that run since inception. The exact day rarely matters; the year does.",
		field="date_of_establishment",
		kind="Date",
		example="2014-04-01",
		seq=60,
	),
	# ── Which modules ───────────────────────────────────────────────────
	Q(
		"modules",
		"Choose your modules",
		"Which parts of ERPNext will this business use?",
		"Pick everything they will actually run. Every question after this one follows from the answer: choose Stock and you are asked about warehouses, leave it out and warehouses are never mentioned. You can come back and add a module later.",
		kind="Multiple Choice",
		options="accounts | Accounting — invoices, payments, taxes\nselling | Selling — quotations, orders, customers\nbuying | Buying — purchase orders, suppliers, bills\nstock | Stock — items, warehouses, deliveries\nmanufacturing | Manufacturing — BOMs, work orders\ncrm | CRM — leads and deals\nprojects | Projects — tasks and timesheets\nhr | HR and Payroll — employees, leave, salary\nassets | Assets — what you own, and depreciation",
		example="Accounting, Selling, Buying, Stock",
		reqd=1,
		seq=10,
	),
	# ── Timezone ────────────────────────────────────────────────────────
	Q(
		"time_zone",
		"Set the system timezone",
		"Which timezone does the business run in?",
		"Every document records the moment it was made. Get this wrong and a day's sales can land on the wrong date.",
		field="time_zone",
		kind="Select",
		example="Asia/Kolkata",
		reqd=1,
		seq=10,
	),
	# ── Date and number format ──────────────────────────────────────────
	Q(
		"date_format",
		"Set date and number format",
		"How should dates be written?",
		"How every date appears on screen and on printed documents. Most of the world reads dd-mm-yyyy; the United States reads mm-dd-yyyy.",
		field="date_format",
		kind="Select",
		options="dd-mm-yyyy\nmm-dd-yyyy\ndd/mm/yyyy\nmm/dd/yyyy\nyyyy-mm-dd",
		example="dd-mm-yyyy",
		reqd=1,
		seq=10,
	),
	Q(
		"time_format",
		"Set date and number format",
		"Should times be shown on a 24-hour clock?",
		"24-hour avoids the am/pm mistakes that creep into delivery and attendance times.",
		field="time_format",
		kind="Select",
		options="HH:mm:ss\nHH:mm",
		example="HH:mm:ss",
		seq=20,
	),
	Q(
		"number_format",
		"Set date and number format",
		"How should numbers be grouped?",
		"Where the separators fall in a large amount. India groups in lakhs — 12,34,567.89 — while most other places group in thousands.",
		field="number_format",
		kind="Select",
		options="#,###.##\n#.###,##\n# ###.##\n#,##,###.##",
		example="#,##,###.##",
		reqd=1,
		seq=30,
	),
	Q(
		"first_day_of_week",
		"Set date and number format",
		"Which day does your week start on?",
		"Used by the calendar, by weekly reports and by attendance.",
		field="first_day_of_the_week",
		kind="Select",
		options="Sunday\nMonday\nTuesday\nWednesday\nThursday\nFriday\nSaturday",
		example="Monday",
		seq=40,
	),
	# ── Currency and float precision ────────────────────────────────────
	Q(
		"currency_precision",
		"Set currency and float precision",
		"How many decimal places should money carry?",
		"Controls rounding of every amount in invoices, reports and ledger balances. Two is normal — 1,250.75. Use three only if you genuinely price in fractions of a paisa.",
		field="currency_precision",
		kind="Select",
		options="2\n3\n4",
		example="2",
		reqd=1,
		seq=10,
	),
	Q(
		"float_precision",
		"Set currency and float precision",
		"How many decimal places should quantities carry?",
		"How finely you can count what you stock. Three suits weights and litres; use more only if you sell in very small fractions.",
		field="float_precision",
		kind="Select",
		options="2\n3\n4\n5\n6",
		example="3",
		reqd=1,
		seq=20,
	),
	Q(
		"rounding_method",
		"Set currency and float precision",
		"How should a half be rounded?",
		"Banker's rounding sends a .5 to the nearest even number, which keeps long columns from drifting upward. Commercial rounding always sends it up.",
		field="rounding_method",
		kind="Select",
		options="Banker's Rounding\nBanker's Rounding (legacy)\nCommercial Rounding",
		example="Banker's Rounding",
		seq=30,
	),
	# ── Fiscal year ─────────────────────────────────────────────────────
	Q(
		"fy_start",
		"Create a fiscal year",
		"What is the start date of the company's financial year?",
		"The financial year is the twelve months your books are kept in. In India it runs 1 April to 31 March; in much of Europe and the US it follows the calendar year.",
		field="year_start_date",
		kind="Date",
		example="2026-04-01",
		reqd=1,
		seq=10,
	),
	Q(
		"fy_end",
		"Create a fiscal year",
		"What is the end date of the company's financial year?",
		"Exactly twelve months after the start, less a day. ERPNext will not let anything be posted outside a fiscal year, so this has to cover the period you are moving.",
		field="year_end_date",
		kind="Date",
		example="2027-03-31",
		reqd=1,
		seq=20,
	),
	Q(
		"fy_name",
		"Create a fiscal year",
		"What should this financial year be called?",
		"The label you will pick in reports. Most people use the two years it spans.",
		field="year",
		example="2026-2027",
		reqd=1,
		seq=30,
	),
	# ── Company default accounts ────────────────────────────────────────
	Q(
		"default_cash",
		"Set company default accounts",
		"Which account is your cash?",
		"Where cash receipts and payments land. ERPNext made a standard chart of accounts when the company was created; this picks one from it.",
		field="default_cash_account",
		kind="Link",
		options="Account",
		example="Cash - STPL",
		seq=10,
	),
	Q(
		"default_receivable",
		"Set company default accounts",
		"Which account holds money customers owe you?",
		"Every sales invoice posts here until it is paid. On a standard chart it is Debtors.",
		field="default_receivable_account",
		kind="Link",
		options="Account",
		example="Debtors - STPL",
		seq=20,
	),
	Q(
		"default_payable",
		"Set company default accounts",
		"Which account holds money you owe suppliers?",
		"Every purchase invoice posts here until you pay it. On a standard chart it is Creditors.",
		field="default_payable_account",
		kind="Link",
		options="Account",
		example="Creditors - STPL",
		seq=30,
	),
	Q(
		"default_cost_center",
		"Set company default accounts",
		"Which cost center should entries default to?",
		"Cost centers split your profit and loss by branch, product line or team. If you do not split it, the company's main one is right.",
		field="cost_center",
		kind="Link",
		options="Cost Center",
		example="Main - STPL",
		seq=40,
	),
	# ── Groups and territory ────────────────────────────────────────────
	Q(
		"item_group_name",
		"Create an item group",
		"What is the item group called?",
		"A group of things you sell or stock — 'Spare Parts', 'Services', 'Raw Material'. Items inherit defaults and tax treatment from their group.",
		field="item_group_name",
		example="Spare Parts",
		reqd=1,
		seq=10,
	),
	Q(
		"item_group_parent",
		"Create an item group",
		"Which group does it sit under?",
		"Item groups form a tree. Unless you have a reason, hang new ones off 'All Item Groups'.",
		field="parent_item_group",
		kind="Link",
		options="Item Group",
		example="All Item Groups",
		seq=20,
	),
	Q(
		"customer_group_name",
		"Create a customer group",
		"What is the customer group called?",
		"How you divide your customers for pricing and reporting — 'Wholesale', 'Retail', 'Government'.",
		field="customer_group_name",
		example="Wholesale",
		reqd=1,
		seq=10,
	),
	Q(
		"customer_group_parent",
		"Create a customer group",
		"Which group does it sit under?",
		"Customer groups form a tree. 'All Customer Groups' is the root everything hangs from.",
		field="parent_customer_group",
		kind="Link",
		options="Customer Group",
		example="All Customer Groups",
		seq=20,
	),
	Q(
		"supplier_group_name",
		"Create a supplier group",
		"What is the supplier group called?",
		"How you divide your suppliers — 'Local', 'Imports', 'Services'. Useful for reporting and for default payment terms.",
		field="supplier_group_name",
		example="Local Suppliers",
		reqd=1,
		seq=10,
	),
	Q(
		"territory_name",
		"Create a territory",
		"What is the territory called?",
		"A place you sell into — a state, a city, a region. Sales can then be read by territory, and a price list can be tied to one.",
		field="territory_name",
		example="Maharashtra",
		reqd=1,
		seq=10,
	),
	Q(
		"territory_parent",
		"Create a territory",
		"Which territory does it sit under?",
		"Territories form a tree. 'All Territories' is the root.",
		field="parent_territory",
		kind="Link",
		options="Territory",
		example="All Territories",
		seq=20,
	),
	# ── Warehouses ──────────────────────────────────────────────────────
	Q(
		"parent_wh_name",
		"Create a parent warehouse",
		"What is the group warehouse called?",
		"A heading that holds other warehouses — a city, a site, a building. Stock is never placed in it directly.",
		field="warehouse_name",
		example="Pune",
		reqd=1,
		seq=10,
	),
	Q(
		"child_wh_name",
		"Create a child warehouse",
		"What is the warehouse called?",
		"A real place stock sits: a godown, a shop floor, a van. Every stock movement names one of these.",
		field="warehouse_name",
		example="Main Store",
		reqd=1,
		seq=10,
	),
	Q(
		"child_wh_parent",
		"Create a child warehouse",
		"Which group warehouse does it belong to?",
		"The heading it sits under, so stock reports can be read by site as well as by store.",
		field="parent_warehouse",
		kind="Link",
		options="Warehouse",
		example="Pune - STPL",
		seq=20,
	),
	# ── UOM ─────────────────────────────────────────────────────────────
	Q(
		"uom_name",
		"Create a unit of measure",
		"What is the unit called?",
		"ERPNext already knows 239 units — Nos, Kg, Litre, Box and the rest. Only add one it does not have, such as 'Bundle of 12'.",
		field="uom_name",
		example="Bundle",
		reqd=1,
		seq=10,
	),
	Q(
		"uom_whole",
		"Create a unit of measure",
		"Must this unit always be a whole number?",
		"On for things you cannot have half of, like a crate or a machine. Off for weights and volumes.",
		field="must_be_whole_number",
		kind="Yes / No",
		example="Yes",
		seq=20,
	),
]


# Fields a later version may add to a record seeded earlier. Only a blank is
# filled, so a consultant's own edit is never overwritten.
FILLED_IF_BLANK = ("applies_when", "description", "example", "options", "icon")


def seed():
	"""Put the wizard's tasks and questions on the site, without overwriting edits."""
	_seed("Embark Wizard Task", "task_name", TASKS)
	_seed("Embark Wizard Question", "question_key", QUESTIONS)


def _seed(doctype: str, key: str, rows: list[dict]) -> None:
	for row in rows:
		if not frappe.db.exists(doctype, row[key]):
			frappe.get_doc({"doctype": doctype, **row}).insert(ignore_permissions=True)
			continue

		doc = frappe.get_doc(doctype, row[key])
		changed = False
		for field in FILLED_IF_BLANK:
			if row.get(field) and not doc.get(field):
				doc.set(field, row[field])
				changed = True

		# What kind of answer a question takes, which field it fills and where it
		# sits are structural — they are the engine, not the wording, and a later
		# version that corrects them has to win or the wizard asks for a link
		# where ERPNext wants a choice. The words stay as the site has them.
		if doctype == "Embark Wizard Question":
			for field in ("answer_type", "fieldname", "sequence"):
				if row.get(field) is not None and doc.get(field) != row.get(field):
					doc.set(field, row[field])
					changed = True

		if changed:
			doc.save(ignore_permissions=True)


def board(doc) -> dict:
	"""The whole wizard: every task, its questions, and what has been answered.

	A task appears when the answers so far call for it. Those are the wizard's
	own answers — the modules chosen in step two — so the wizard explains itself
	without reaching into anything else.
	"""
	answers = {row.question: row.value for row in doc.wizard_answers}

	tasks, answered, total = [], 0, 0
	for task in frappe.get_all(
		"Embark Wizard Task",
		filters={"is_active": 1},
		fields=[
			"name",
			"task_name",
			"sequence",
			"icon",
			"target_doctype",
			"is_single",
			"description",
			"applies_when",
		],
		order_by="sequence asc",
	):
		if not applies(task.applies_when, answers):
			continue

		questions = []
		for q in frappe.get_all(
			"Embark Wizard Question",
			filters={"task": task.name, "is_active": 1},
			fields=[
				"name",
				"label",
				"description",
				"example",
				"fieldname",
				"answer_type",
				"options",
				"is_required",
				"applies_when",
			],
			order_by="sequence asc",
		):
			if not applies(q.applies_when, answers):
				continue
			questions.append(
				{
					"key": q.name,
					"label": q.label,
					"description": q.description,
					"example": q.example,
					"field": q.fieldname,
					"type": q.answer_type,
					"choices": choices(q, task.target_doctype),
					"link_doctype": _link_doctype(q, task.target_doctype),
					"required": bool(q.is_required),
					"answer": answers.get(q.name, ""),
				}
			)

		if not questions:
			continue
		done = sum(1 for q in questions if q["answer"])
		answered += done
		total += len(questions)
		tasks.append(
			{
				"task": task.name,
				"title": task.task_name,
				"icon": task.icon,
				"doctype": task.target_doctype,
				"is_single": bool(task.is_single),
				"description": task.description,
				"questions": questions,
				"answered": done,
				"total": len(questions),
				"state": _("Ready to apply")
				if done == len(questions)
				else (_("In progress") if done else _("Not started")),
			}
		)

	return {
		"tasks": tasks,
		"answered": answered,
		"total": total,
		"percent": round(100 * answered / total) if total else 0,
	}


def choices(question, target_doctype: str | None) -> list[dict]:
	"""What a question may be answered with, asked of ERPNext itself.

	A Select question fills a real field on a real doctype, and that field
	already lists its options — so they are read from there rather than copied
	into Embark, where they would quietly go stale the next time ERPNext adds
	one. Only a question with no field of its own carries its own list.
	"""
	if question.answer_type not in ("Select", "Multiple Choice"):
		return []

	if question.answer_type == "Select" and question.fieldname and target_doctype:
		field = frappe.get_meta(target_doctype).get_field(question.fieldname)
		# A few Selects are filled in by the browser rather than stored on the
		# field. The timezone list is the one that matters here, and frappe
		# keeps it; reading it is still reading ERPNext, not a copy.
		if field and field.fieldtype == "Select" and not field.options and question.fieldname == "time_zone":
			from frappe.utils.momentjs import get_all_timezones

			return [{"value": zone, "label": zone} for zone in get_all_timezones()]
		if field and field.fieldtype == "Select" and field.options:
			return [
				{"value": option.strip(), "label": option.strip()}
				for option in field.options.split("\n")
				if option.strip()
			]
		if field and field.fieldtype in ("Link", "Dynamic Link") and field.options:
			# The field turned out to be a link; the question follows it.
			return []

	out = []
	for line in (question.options or "").split("\n"):
		line = line.strip()
		if not line:
			continue
		value, _sep, label = line.partition("|")
		out.append({"value": value.strip(), "label": (label or value).strip()})
	return out


def _link_doctype(question, target_doctype: str | None) -> str | None:
	"""Which doctype a Link question offers, taken from the field where it can be."""
	if question.fieldname and target_doctype:
		field = frappe.get_meta(target_doctype).get_field(question.fieldname)
		if field and field.fieldtype == "Link" and field.options:
			return field.options
	return (question.options or "").strip() if question.answer_type == "Link" else None


def save_answer(doc, question: str, value: str) -> None:
	"""One answer, kept against the question it belongs to."""
	if not frappe.db.exists("Embark Wizard Question", question):
		frappe.throw(_("{0} is not one of the wizard's questions.").format(question))

	for row in doc.wizard_answers:
		if row.question == question:
			row.value = value
			break
	else:
		doc.append("wizard_answers", {"question": question, "value": value})
	doc.save(ignore_permissions=True)


def check(doc, task: str) -> dict:
	"""What applying this task would do to ERPNext, and whether that is safe."""
	plan = _record(doc, task)
	if not plan:
		return {"about_to": "", "safe_because": [], "fields": [], "ready": False}

	meta = frappe.get_meta(plan["doctype"])
	safe = [
		_("Every field below comes from an answer you gave — nothing is invented."),
		_("The record is written through a change set, copied first, so it can be put back."),
	]
	if meta.is_submittable:
		safe.append(
			_("{0} can be submitted. It is left as a draft for you to check.").format(plan["doctype"])
		)
	else:
		safe.append(
			_("{0} is not a document that gets submitted — it is a setting or a list.").format(
				plan["doctype"]
			)
		)

	return {
		"about_to": _("Embark is about to {0} {1} in ERPNext.").format(
			_("update") if plan["exists"] else _("create"), plan["doctype"]
		),
		"safe_because": safe,
		"fields": [
			{"field": _(meta.get_field(f).label) if meta.get_field(f) else f, "value": v}
			for f, v in plan["values"].items()
		],
		"ready": True,
	}


def apply(doc, task: str) -> dict:
	"""Write the task's record, and hand back what ERPNext now holds."""
	import json

	plan = _record(doc, task)
	if not plan:
		frappe.throw(_("Answer this step's questions first."))

	change_set = frappe.get_doc(
		{
			"doctype": "Embark Change Set",
			"title": _("Embark: {0}").format(task)[:140],
			"request": _("From the setup wizard of {0}.").format(doc.client_name),
			"changes": [
				{
					"action": "Update" if plan["exists"] else "Create",
					"ref_doctype": plan["doctype"],
					"ref_name": plan["name"],
					"summary": task,
					"payload": json.dumps(plan["values"], default=str),
				}
			],
		}
	).insert(ignore_permissions=True)
	change_set.apply()

	name = change_set.changes[0].ref_name
	return {"task": task, "change_set": change_set.name, "record": result(plan["doctype"], name)}


def result(doctype: str, name: str) -> dict:
	"""The record as ERPNext holds it now — the card shown once it exists."""
	record = frappe.get_doc(doctype, name)
	meta = frappe.get_meta(doctype)

	shown = []
	for field in meta.fields:
		if field.fieldtype in ("Section Break", "Column Break", "Table", "HTML", "Button"):
			continue
		value = record.get(field.fieldname)
		if value in (None, "", 0, []) or isinstance(value, list):
			continue
		shown.append({"field": _(field.label) if field.label else field.fieldname, "value": str(value)[:120]})
		if len(shown) >= 8:
			break

	return {
		"doctype": doctype,
		"name": name,
		"fields": shown,
		"url": f"/app/{frappe.scrub(doctype).replace('_', '-')}/{frappe.utils.quoted(name)}",
		"created": str(record.get("creation") or ""),
		"owner": record.get("owner"),
	}


def state(doc) -> dict:
	"""The implementation as ERPNext holds it: every task, and what it produced.

	Read back from the records themselves, not from what Embark remembers doing,
	so a record somebody changed by hand in the desk shows their change.
	"""
	made = {}
	for row in frappe.get_all(
		"Embark Change Set",
		filters={"status": "Applied"},
		fields=["name", "title", "applied_at"],
		order_by="applied_at asc",
	):
		for change in frappe.get_all(
			"Embark Change", filters={"parent": row.name}, fields=["ref_doctype", "ref_name", "summary"]
		):
			if change.ref_name and frappe.db.exists(change.ref_doctype, change.ref_name):
				made[change.summary] = (change.ref_doctype, change.ref_name)

	board_now = board(doc)
	tasks = []
	for task in board_now["tasks"]:
		built = made.get(task["task"])
		tasks.append(
			{
				**{k: task[k] for k in ("task", "title", "icon", "doctype", "answered", "total", "state")},
				"record": result(*built) if built else None,
			}
		)

	return {
		"tasks": tasks,
		"answered": board_now["answered"],
		"total": board_now["total"],
		"percent": board_now["percent"],
		"built": sum(1 for t in tasks if t["record"]),
	}


def _record(doc, task: str) -> dict | None:
	"""What this task's answers add up to: a doctype, a name, and the fields."""
	task_doc = frappe.get_cached_doc("Embark Wizard Task", task)
	if not task_doc.target_doctype:
		return None

	answers = {row.question: row.value for row in doc.wizard_answers}
	values, missing = {}, []
	for q in frappe.get_all(
		"Embark Wizard Question",
		filters={"task": task, "is_active": 1},
		fields=["name", "fieldname", "answer_type", "is_required"],
		order_by="sequence asc",
	):
		value = (answers.get(q.name) or "").strip()
		if not value:
			if q.is_required:
				missing.append(q.name)
			continue
		if q.fieldname:
			values[q.fieldname] = (
				1
				if q.answer_type == "Yes / No" and value.lower() in ("yes", "1", "true")
				else (0 if q.answer_type == "Yes / No" else value)
			)

	if missing or not values:
		return None

	doctype = task_doc.target_doctype
	if task_doc.is_single:
		return {"doctype": doctype, "name": doctype, "values": values, "exists": True}

	# A record that is already there is updated, not made twice.
	meta = frappe.get_meta(doctype)
	title_field = (
		meta.get_field(meta.autoname.split(":")[1]) if (meta.autoname or "").startswith("field:") else None
	)
	guess = values.get(title_field.fieldname) if title_field else None
	existing = guess if guess and frappe.db.exists(doctype, guess) else None

	# Company-scoped records need the company, and nobody should have to type it.
	company = doc.company_name or frappe.db.get_value("Company", {}, "name", order_by="creation asc")
	if company and meta.get_field("company") and "company" not in values:
		values["company"] = company

	return {"doctype": doctype, "name": existing, "values": values, "exists": bool(existing)}
