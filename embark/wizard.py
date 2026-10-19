"""The setup wizard: one question at a time, each answer a field in ERPNext.

This is the implementation itself, asked as questions. Every question names the
record it belongs to — Company, System Settings, Fiscal Year, Warehouse — and
the field of it that the answer fills; a question that says nothing takes the
task's own record, which is the usual case. A step asked as one topic may well
touch several records: credit terms are a Payment Term, a default on the
Company and a role in Accounts Settings. Answer a task and Embark writes each
of them, through the same change set everything else goes through, so it is
previewed before and reversible after.

Nothing here is a form that gets posted somewhere. A question knows which field
it fills, which means the wizard can say what it is about to do, show the record
once it exists, and never ask for the same thing twice.
"""

from __future__ import annotations

import json
import pathlib

import frappe
from frappe import _

from embark.conditions import applies


def Q(
	key,
	task,
	label,
	description,
	*,
	field="",
	kind="Text",
	options="",
	example="",
	reqd=0,
	when="",
	seq=0,
	doctype="",
	single=0,
):
	return {
		"question_key": key,
		"task": task,
		"label": label,
		"description": description,
		"target_doctype": doctype,
		"is_single": single,
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
		"stage": "Company",
		"icon": "briefcase",
		"target_doctype": "Company",
		"description": "The business itself. Everything in ERPNext hangs off this record: your ledgers, your stock, your invoices.",
	},
	{
		"task_name": "Choose your modules",
		"sequence": 15,
		"stage": "Modules",
		"icon": "grid",
		"description": "Which parts of ERPNext this business will run. Everything after this step is decided by the answer — a module you leave out is never mentioned again.",
	},
	{
		"task_name": "Set the system timezone",
		"sequence": 20,
		"stage": "Setup",
		"icon": "globe",
		"target_doctype": "System Settings",
		"is_single": 1,
		"description": "Every document records when it was made. The timezone decides what time that is.",
	},
	{
		"task_name": "Set date and number format",
		"sequence": 30,
		"stage": "Setup",
		"icon": "calendar",
		"target_doctype": "System Settings",
		"is_single": 1,
		"description": "How dates and amounts are written everywhere — on screen, on invoices, in exports.",
	},
	{
		"task_name": "Set currency and float precision",
		"sequence": 40,
		"stage": "Setup",
		"icon": "hash",
		"target_doctype": "System Settings",
		"is_single": 1,
		"description": "How many decimal places money and quantities carry, and how the odd fraction is rounded.",
	},
	{
		"task_name": "Create a fiscal year",
		"sequence": 50,
		"stage": "Setup",
		"icon": "calendar",
		"target_doctype": "Fiscal Year",
		"description": "The twelve months your books are kept in. Nothing can be posted outside one.",
	},
	{
		"task_name": "Set company default accounts",
		"sequence": 60,
		"stage": "Setup",
		"icon": "book",
		"target_doctype": "Company",
		"description": "Which ledger each kind of entry lands in, so nobody has to pick one on every document.",
		"applies_when": "modules == accounts",
	},
	{
		"task_name": "Create an item group",
		"sequence": 70,
		"stage": "Setup",
		"icon": "layers",
		"target_doctype": "Item Group",
		"description": "How your products and services are grouped. Reports, taxes and defaults all follow these.",
		"applies_when": "modules == stock,selling,buying,manufacturing",
	},
	{
		"task_name": "Create a customer group",
		"sequence": 80,
		"stage": "Setup",
		"icon": "user-check",
		"target_doctype": "Customer Group",
		"description": "How your customers are grouped — wholesale, retail, government — for pricing and reporting.",
		"applies_when": "modules == selling,crm",
	},
	{
		"task_name": "Create a supplier group",
		"sequence": 90,
		"stage": "Setup",
		"icon": "truck",
		"target_doctype": "Supplier Group",
		"description": "How your suppliers are grouped, for reporting and for default payment terms.",
		"applies_when": "modules == buying",
	},
	{
		"task_name": "Create a territory",
		"sequence": 100,
		"stage": "Setup",
		"icon": "map-pin",
		"target_doctype": "Territory",
		"description": "The places you sell into. Sales can then be read by region, and prices can differ by one.",
		"applies_when": "modules == selling,crm",
	},
	{
		"task_name": "Create a parent warehouse",
		"sequence": 110,
		"stage": "Setup",
		"icon": "archive",
		"target_doctype": "Warehouse",
		"description": "A group warehouse that holds other warehouses — a city, a site, a building. Nothing is stocked in it directly.",
		"applies_when": "modules == stock",
	},
	{
		"task_name": "Create a child warehouse",
		"sequence": 120,
		"stage": "Setup",
		"icon": "archive",
		"target_doctype": "Warehouse",
		"description": "A place stock actually sits: a godown, a shop floor, a van.",
		"applies_when": "modules == stock",
	},
	{
		"task_name": "Create a unit of measure",
		"sequence": 130,
		"stage": "Setup",
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


# ── The authored question bank ────────────────────────────────────────────────
#
# The wording lives in embark/data/wizard_questions.json, not in this file: it
# is content, written and rewritten by whoever knows the business, and it has
# no business being a Python literal. This end only decides what each row
# means — which stage it belongs to, which module has to be chosen for it to
# be asked, and what it writes.

CONTENT = pathlib.Path(__file__).parent / "data" / "wizard_questions.json"

# An authored module, and the choice in step two that has to include it.
MODULE_GATES = {
	"Company Setup": "",
	"Accounting": "modules == accounts",
	"Stock": "modules == stock",
	"Selling": "modules == selling,crm",
	"Buying": "modules == buying",
	"CRM": "modules == crm",
	"Manufacturing": "modules == manufacturing",
	"Projects": "modules == projects",
	"HR": "modules == hr",
	"Assets": "modules == assets",
}

# The company's own identity is stage one. Everything else it owns — its
# address, the days it is closed — is setup like any other.
COMPANY_STAGE = ("Create a company",)

# A question that only decides, and the questions that decision opens up.
# The file does not say this, because a list of questions cannot: it is the
# sense of the two sitting next to each other.
GATED_BY = {
	"additional_warehouse_name": "has_multiple_stock_locations == yes",
	"rejected_warehouse_name": "does_quality_inspection == yes",
	"cost_center_name": "uses_branch_cost_centres == yes",
	"quality_inspection_template_name": "does_quality_inspection == yes",
	"action_if_qi_not_submitted": "does_quality_inspection == yes",
	"price_list_name": "uses_multiple_price_lists == yes",
	"backflush_based_on": "does_manufacturing == yes",
	"material_consumption": "does_manufacturing == yes",
	"overproduction_for_sales_order": "does_manufacturing == yes",
	"overproduction_for_work_order": "does_manufacturing == yes",
	"make_serial_batch_from_work_order": "does_manufacturing == yes",
	"update_bom_costs_automatically": "does_manufacturing == yes",
	"fetch_timesheet_in_invoice": "runs_projects == yes",
	"ignore_employee_time_overlap": "runs_projects == yes",
	"activity_type": "runs_projects == yes",
	"activity_billing_rate": "runs_projects == yes",
	"activity_costing_rate": "runs_projects == yes",
	"tax_category_title": "is_gst_registered == yes",
	"asset_category_name": "tracks_fixed_assets == yes",
	"enable_cwip_accounting": "tracks_fixed_assets == yes",
	"depreciation_method": "tracks_fixed_assets == yes",
	"total_number_of_depreciations": "tracks_fixed_assets == yes",
	"frequency_of_depreciation": "tracks_fixed_assets == yes",
	"book_depreciation_automatically": "tracks_fixed_assets == yes",
	"asset_location_name": "tracks_fixed_assets == yes",
	"opening_trial_balance": "needs_opening_balances == yes",
	"opening_receivables": "needs_opening_balances == yes",
	"opening_payables": "needs_opening_balances == yes",
	"discount_approval_above": "needs_approvals == yes",
	"purchase_approval_above": "needs_approvals == yes",
	"approver_role": "needs_approvals == yes",
	"volume_discounts": "gives_discounts == yes",
	"landed_cost_from_invoice": "adds_landed_cost == yes",
	"uses_job_cards": "tracks_operations == yes",
	"job_card_excess_transfer": "tracks_operations == yes",
	"paid_leave_days": "works_shifts == yes or attendance_capture == Biometric machine",
	"terms_text": "",
}

# Work, not questions.
#
# A question is something only this business can answer, and answering it
# configures ERPNext — a field is set or a record is made. Everything else
# that has to happen is work: somebody collects a trial balance, somebody
# sets up the approval rules, somebody trains the people who will use it.
#
# Dressing work up as a question produces the worst of both. "Do your closing
# balances need to be brought in?" has one answer for every business moving
# off an old system, teaches nobody anything, configures nothing, and leaves
# the actual job — getting the balances in — unlisted and undone.
#
# So work is a step of its own: it says what has to happen and who prepares
# what, and it is ticked off rather than answered.
WORK = (
	{
		"task_name": "Switch on batch and serial tracking",
		"applies_when": "needs_batch_tracking == yes or needs_serial_tracking == yes",
		"icon": "hash",
		"description": "Turning tracking on for the items that need it, and no others.",
		"work_note": (
			"We switch tracking on in Stock Settings and set it per item — only the ones you traced "
			"before. It cannot be turned off for an item once it has stock, so we go through your "
			"list with you rather than guessing, and agree how the numbers are formed."
		),
	},
	{
		"task_name": "Set up your prices and discounts",
		"applies_when": "customer_specific_prices == yes or volume_discounts == yes",
		"icon": "tag",
		"description": "The rates and slabs that fill themselves in, instead of being remembered.",
		"work_note": (
			"Send us the rates you have agreed with particular customers, and any slab pricing. We "
			"build them as rules, then raise one order per rule with you watching, so you can see "
			"the right rate appear before anyone relies on it."
		),
	},
	{
		"task_name": "Set up tax deducted at source",
		"applies_when": "deducts_tds == yes",
		"icon": "percent",
		"description": "The categories, rates and thresholds for the tax you deduct when paying.",
		"work_note": (
			"We set up a category per section you deduct under, with its rate and threshold, and "
			"attach them to the suppliers they apply to. Give us the sections you use and the rates "
			"your auditor expects. Short deductions are interest and a mismatched return."
		),
	},
	{
		"task_name": "Set up trading in other currencies",
		"applies_when": "trades_in_foreign_currency == yes",
		"icon": "globe",
		"description": "Exchange rates, and where the gain or loss on them is posted.",
		"work_note": (
			"We switch on the currencies you trade in, decide whether rates come in automatically or "
			"are entered by hand, and set the account that exchange differences post to. Without "
			"that account, the difference sits unexplained in your books."
		),
	},
	{
		"task_name": "Set up subcontracting",
		"applies_when": "does_subcontracting == yes",
		"icon": "truck",
		"description": "Material sent out to a job worker, and goods coming back.",
		"work_note": (
			"We set up the flow that keeps material at your job workers visible as your stock, with "
			"the warehouse that represents each one. Tell us who you send to and what they do. "
			"Without it, material at the job worker disappears from your records."
		),
	},
	{
		"task_name": "Set up enquiry and quotation tracking",
		"applies_when": "tracks_leads == yes",
		"icon": "phone",
		"description": "Where enquiries come from, and how they become quotations and orders.",
		"work_note": (
			"Leads and opportunities live in Frappe CRM in this version, so we install and connect "
			"it, bring your sources across, and agree the stages your pipeline uses. Then we walk "
			"one enquiry through to an order with your sales people watching."
		),
	},
	{
		"task_name": "Plan your stock counts",
		"applies_when": "does_stock_takes == Yearly,Quarterly,Monthly,Weekly",
		"icon": "clipboard",
		"description": "How a physical count becomes a correction in the books.",
		"work_note": (
			"We agree who counts, on what day, and who signs off a difference, then run one count "
			"with you so the first real one is not also the first attempt. Counts that are never "
			"reconciled leave your stock figure as good as the entries behind it, and no better."
		),
	},
	{
		"task_name": "Set up barcode scanning",
		"applies_when": "uses_barcodes == yes",
		"icon": "maximize",
		"description": "Items carrying their barcode, so receiving and dispatch is scanned.",
		"work_note": (
			"Every item needs its barcode recorded before this is worth anything, so we agree who "
			"collects them and by when, then test a receipt and a dispatch with your own scanner."
		),
	},
	{
		"task_name": "Set up the quote-to-order flow",
		"applies_when": "takes_supplier_quotes == yes",
		"icon": "file-text",
		"description": "Asking several suppliers, comparing what comes back, ordering from it.",
		"work_note": (
			"We set up the request that goes out to your suppliers and the comparison that brings "
			"their quotes together, then run one real purchase through it end to end. Tell us which "
			"suppliers you normally ask."
		),
	},
	{
		"task_name": "Set up returns and credit notes",
		"applies_when": "handles_returns == yes",
		"icon": "corner-up-left",
		"description": "Goods coming back, and the credit that goes with them.",
		"work_note": (
			"We agree what happens when goods come back — whether they go into saleable stock or a "
			"rejected store, and who authorises the credit — and run one return through so your "
			"sales figures and your stock both end up right."
		),
	},
	{
		"task_name": "Set up job cards on the floor",
		"applies_when": "uses_job_cards == yes",
		"icon": "tool",
		"description": "Operators starting and finishing their stages as the work happens.",
		"work_note": (
			"We set up the cards for your operations and decide where the floor sees them — a shared "
			"screen or a tablet at the machine. Then we run one job through with a supervisor, "
			"because this is the part that only works if the floor is willing."
		),
	},
	{
		"task_name": "Add your other weekly offs",
		"applies_when": "has_second_weekly_off == Yes",
		"icon": "calendar",
		"description": "The alternate Saturdays and other days your weekly off does not cover.",
		"work_note": (
			"Tell us which Saturdays you close — second and fourth is the usual — and we add them to "
			"the holiday list for the year. Left out, they count as absences in attendance and come "
			"off people's pay."
		),
	},
	{
		"task_name": "Bring in your opening balances",
		"applies_when": "modules == accounts",
		"icon": "download",
		"description": "What you owe, what you are owed, your bank and your stock, as at the day before you start.",
		"work_note": (
			"Your accountant gives us a trial balance as at the day before go-live, a list of the "
			"invoices your customers have not paid, and a list of the bills you have not paid — each "
			"with its own date, so the ageing is right from the first day. Stock comes in as a count "
			"with its value. We post it; you check the trial balance matches your old system to the "
			"rupee before anything else is entered."
		),
	},
	{
		"task_name": "Set up who approves what",
		"applies_when": "modules == accounts,selling,buying",
		"icon": "shield",
		"description": "The limits above which a discount, an order or a payment waits for somebody.",
		"work_note": (
			"Tell us the figures — the discount percentage above which a sale needs releasing, the "
			"order value above which a purchase does — and who releases them. We set the rules up "
			"and test them with one of your own orders, so the first time somebody hits the limit is "
			"not the day you go live."
		),
	},
	{
		"task_name": "Set up your people and what they can see",
		"applies_when": "",
		"icon": "users",
		"description": "The accounts your staff log in with, and what each of them is allowed to reach.",
		"work_note": (
			"We create a login for each person, give them the roles their job needs and no more, and "
			"where you work across sites, restrict each person to their own branch, warehouse or "
			"territory. Send us the list of names, emails and what each one does."
		),
	},
	{
		"task_name": "Plan the switch over",
		"applies_when": "",
		"icon": "flag",
		"description": "The day you start, who is trained first, and how long the old system runs alongside.",
		"work_note": (
			"We agree the date you stop entering in the old system, train the two or three people who "
			"will answer everyone else's questions in week one, and decide whether both systems run "
			"together for a month. Nothing here is a setting; it is the part that decides whether "
			"go-live is calm."
		),
	},
)


# The order an implementation actually happens in, which is not the order the
# question bank happens to be written in. Who the company is, then where it
# is, then when its books start — and only then the accounts those books post
# to. Stock before the things that move it; selling and buying before the
# enquiries that feed them; people and assets last.
#
# A step not named here keeps its own sequence and falls in after these.
STEP_ORDER = (
	"Choose your modules",
	# The company itself
	"Create a company",
	"Add your company address",
	"Set your go-live dates",
	"Set up your printed documents",
	# Its books
	"Set company default accounts",
	"Keep the books straight",
	"Set up taxes",
	"Set up cost centres",
	"Set up your bank account",
	"Set up credit terms",
	"Set accounting rules",
	"Set up who approves what",
	# How it runs
	"Set up holidays",
	"Set up warehouses",
	"Set stock rules",
	"Count and control stock",
	"Organise your products",
	"Set up quality checks",
	"Organise customers and sales team",
	"Set selling rules",
	"Set your pricing and discount policy",
	"Set buying rules",
	"Set your buying process",
	"Set up enquiry tracking",
	"Set production rules",
	"Plan machine time",
	"Track the shop floor",
	"Set up projects",
	# Its people and what it owns
	"Set up your organisation",
	"Set employee rules",
	"Decide how attendance and leave work",
	"Set payroll rules",
	"Set up fixed assets",
	# The work, once the questions that shape it are answered.
	"Switch on batch and serial tracking",
	"Set up your prices and discounts",
	"Set up tax deducted at source",
	"Set up trading in other currencies",
	"Set up subcontracting",
	"Set up enquiry and quotation tracking",
	"Plan your stock counts",
	"Set up barcode scanning",
	"Set up the quote-to-order flow",
	"Set up returns and credit notes",
	"Set up job cards on the floor",
	"Add your other weekly offs",
	"Bring in your opening balances",
	"Set up your people and what they can see",
	"Plan the switch over",
)


# Steps that asked the customer what ERPNext decides for itself. A new site
# arrives with 239 units of measure, and its timezone, date format and number
# format set from the country it was made in. Asking for them again is asking
# somebody to do the computer's work and then checking their answer with it.
ALREADY_DECIDED = (
	# Replaced by the work steps of the same name, which say what has to
	# happen instead of asking whether it does.
	"Decide who approves what",
	"Decide who uses ERPNext",
	"Create a unit of measure",
	"Set the system timezone",
	"Set date and number format",
	"Set currency and float precision",
)

# A step the question bank now covers in its own words. Switched off rather
# than deleted, so a site that has answered one keeps the answer.
SUPERSEDED = (
	"Create a fiscal year",
	"Create an item group",
	"Create a customer group",
	"Create a supplier group",
	"Create a territory",
	"Create a parent warehouse",
	"Create a child warehouse",
)

ICONS = {
	"Create a company": "briefcase",
	"Add your company address": "map-pin",
	"Set up holidays": "calendar",
	"Set your go-live dates": "calendar",
	"Set up your bank account": "credit-card",
	"Set up credit terms": "clock",
	"Set accounting rules": "book",
	"Set up cost centres": "git-branch",
	"Set up taxes": "percent",
	"Set up warehouses": "archive",
	"Set stock rules": "layers",
	"Set up quality checks": "shield",
	"Organise your products": "tag",
	"Organise customers and sales team": "users",
	"Set selling rules": "shopping-cart",
	"Set buying rules": "truck",
	"Set up enquiry tracking": "phone",
	"Set production rules": "tool",
	"Plan machine time": "clock",
	"Set up projects": "clipboard",
	"Set up your organisation": "users",
	"Set employee rules": "user-check",
	"Set payroll rules": "credit-card",
	"Set up fixed assets": "box",
	"Set up your printed documents": "file-text",
	"Decide who uses ERPNext": "users",
	"Plan the switch over": "flag",
	"Bring in your opening balances": "download",
	"Keep the books straight": "book",
	"Decide who approves what": "shield",
	"Set your pricing and discount policy": "tag",
	"Set your buying process": "truck",
	"Count and control stock": "clipboard",
	"Track the shop floor": "tool",
	"Decide how attendance and leave work": "calendar",
}


def _is_single(doctype: str) -> int:
	"""Whether this record is a Settings record ERPNext already holds."""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return 0
	return 1 if frappe.get_meta(doctype).issingle else 0


def authored() -> tuple[list[dict], list[dict]]:
	"""The question bank, read as tasks and questions.

	A task is a topic the bank groups under one heading. It takes its place in
	the order from its module, and the module decides whether it is asked at
	all.
	"""
	rows = json.loads(CONTENT.read_text())
	order = list(MODULE_GATES)

	tasks, questions, seen = [], [], {}
	for row in rows:
		module, task = row["module"], row["task"]
		# A question about a record this site does not have is not seeded at
		# all. HR Settings and Payroll Settings arrive with Frappe HR, so those
		# questions appear on the migrate after it is installed, not before.
		if row["target_doctype"] and not frappe.db.exists("DocType", row["target_doctype"]):
			continue
		if task not in seen:
			seen[task] = True
			tasks.append(
				{
					"task_name": task,
					"sequence": 1000 + order.index(module) * 100 + len(seen),
					"stage": "Company" if task in COMPANY_STAGE else "Setup",
					"icon": ICONS.get(task, "circle"),
					"applies_when": MODULE_GATES.get(module, ""),
					"description": _("The answers below set this up in ERPNext."),
				}
			)
		questions.append(
			{
				"is_single": _is_single(row["target_doctype"]),
				"question_key": row["question_key"],
				"task": task,
				"label": row["label"],
				"description": row["description"],
				"target_doctype": row["target_doctype"],
				"fieldname": row["fieldname"],
				"answer_type": row["answer_type"],
				"options": row["options"],
				"example": row["example"],
				"is_required": row["is_required"],
				"applies_when": GATED_BY.get(row["question_key"], ""),
				"sequence": row["sequence"],
			}
		)
	# A step whose every question needed an app that is not here is not a step.
	asked = {q["task"] for q in questions}
	return [t for t in tasks if t["task_name"] in asked], questions


# Fields a later version may add to a record seeded earlier. Only a blank is
# filled, so a consultant's own edit is never overwritten.
FILLED_IF_BLANK = ("description", "example", "options", "icon")


def seed():
	"""Put the wizard's tasks and questions on the site, without overwriting edits.

	Two sources, in order: the steps this app has always asked, then the
	question bank, which is the one people actually write. Where both ask the
	same thing the bank wins, because it is the version somebody maintains.
	"""
	_seed("Embark Wizard Task", "task_name", TASKS)
	_seed("Embark Wizard Question", "question_key", QUESTIONS)

	for work in WORK:
		if frappe.db.exists("Embark Wizard Task", work["task_name"]):
			doc = frappe.get_doc("Embark Wizard Task", work["task_name"])
		else:
			doc = frappe.get_doc({"doctype": "Embark Wizard Task", **work})
		existed = bool(doc.get("__islocal") is None and doc.name and frappe.db.exists("Embark Wizard Task", doc.name))
		doc.update({**work, "kind": "Work", "stage": "Setup", "is_active": 1})
		doc.save(ignore_permissions=True) if existed else doc.insert(ignore_permissions=True)

	bank_tasks, bank_questions = authored()
	_seed("Embark Wizard Task", "task_name", bank_tasks, wording=True)
	_seed("Embark Wizard Question", "question_key", bank_questions, wording=True)

	# The order is decided here, in one place, whichever source a step came
	# from. Without it a step seeded by this app sorts before a step from the
	# bank, and the customer is asked for the company's default accounts
	# before the company exists.
	for n, task in enumerate(STEP_ORDER, start=1):
		if frappe.db.exists("Embark Wizard Task", task):
			frappe.db.set_value("Embark Wizard Task", task, "sequence", n * 10, update_modified=False)

	# A question the bank no longer carries stops being asked. Without this,
	# taking one out of the file leaves it on every site that already has it,
	# which is how four questions about work nobody could act on survived
	# being deleted.
	from_app = {q["question_key"] for q in QUESTIONS}
	from_bank = {q["question_key"] for q in bank_questions}
	for stale in frappe.get_all(
		"Embark Wizard Question", filters={"is_active": 1}, pluck="name"
	):
		if stale not in from_app and stale not in from_bank:
			frappe.db.set_value("Embark Wizard Question", stale, "is_active", 0, update_modified=False)

	# A step the bank now covers in its own words is switched off, not deleted,
	# along with any question still sitting on it. A question the bank took
	# over has already moved, so what is left here is what it did not want.
	for task in SUPERSEDED + ALREADY_DECIDED:
		if not frappe.db.exists("Embark Wizard Task", task):
			continue
		frappe.db.set_value("Embark Wizard Task", task, "is_active", 0)
		for name in frappe.get_all("Embark Wizard Question", filters={"task": task}, pluck="name"):
			frappe.db.set_value("Embark Wizard Question", name, "is_active", 0)


def _seed(doctype: str, key: str, rows: list[dict], wording: bool = False) -> None:
	"""Put rows on the site. `wording` marks a source that owns its own words."""
	for row in rows:
		if not frappe.db.exists(doctype, row[key]):
			frappe.get_doc({"doctype": doctype, **row}).insert(ignore_permissions=True)
			continue

		doc = frappe.get_doc(doctype, row[key])
		changed = False
		for field in FILLED_IF_BLANK:
			# The question bank is written to be read, so its wording replaces
			# whatever was there. Everything else only fills a blank.
			if row.get(field) and (wording or not doc.get(field)) and doc.get(field) != row[field]:
				doc.set(field, row[field])
				changed = True
		if wording and row.get("label") and doc.get("label") != row["label"]:
			doc.set("label", row["label"])
			changed = True
		if wording and not doc.is_active:
			doc.is_active = 1
			changed = True

		# What kind of answer a question takes, which field it fills, where it
		# sits and when it is asked at all are structural — they are the engine,
		# not the wording, and a later version that corrects them has to win or
		# the wizard asks for a link where ERPNext wants a choice, or gates a
		# step on a question that no longer exists. The words stay as the site
		# has them.
		structural = {
			"Embark Wizard Question": (
				"answer_type",
				"fieldname",
				"sequence",
				"applies_when",
				"target_doctype",
				# Which step asks it is structural: when the question bank
				# regroups a question under a new heading, it has to move, or
				# it is left behind on a step nobody sees any more.
				"task",
				"is_single",
			),
			"Embark Wizard Task": ("sequence", "stage", "applies_when"),
		}.get(doctype, ())
		for field in structural:
			if row.get(field) is not None and doc.get(field) != row.get(field):
				doc.set(field, row[field])
				changed = True

		if changed:
			doc.save(ignore_permissions=True)


def adopt(doc) -> dict:
	"""Take what the site already holds as the answers to the questions about it.

	A question like "which timezone does the business run in?" has an answer
	sitting in ERPNext already, put there when the site was made. Asking it
	again is asking somebody to tell the computer what the computer told them.

	So any question still open whose field already has a value is answered from
	the site and marked as such. The customer sees what it says and changes it
	if it is wrong, instead of typing it out to be checked.

	Only settings and the company are read this way. "What is one of your
	warehouses?" is a question about a record to make, not a field to read.
	"""
	answered = {row.question for row in doc.wizard_answers}
	# company_name is what the customer is called, which is not always the name
	# of a Company record — reading fields off it then quietly finds nothing.
	company = doc.company_name if frappe.db.exists("Company", doc.company_name) else None
	company = company or frappe.db.get_value("Company", {}, "name", order_by="creation asc")

	taken = {}
	for q in frappe.get_all(
		"Embark Wizard Question",
		filters={"is_active": 1},
		fields=["name", "fieldname", "target_doctype", "answer_type"],
	):
		if q.name in answered or not q.fieldname or not q.target_doctype:
			continue
		if not frappe.db.exists("DocType", q.target_doctype):
			continue
		meta = frappe.get_meta(q.target_doctype)
		if meta.issingle:
			value = frappe.db.get_single_value(q.target_doctype, q.fieldname)
		elif q.target_doctype == "Company" and company:
			value = frappe.db.get_value("Company", company, q.fieldname)
		else:
			continue
		if value in (None, "", 0):
			continue
		# A checkbox reads back as 1, and the question offers Yes and No, so
		# the answer box showed nothing at all for anything adopted this way.
		if q.answer_type == "Yes / No":
			value = "Yes" if frappe.utils.cint(value) else "No"
		taken[q.name] = str(value)

	for question, value in taken.items():
		doc.append("wizard_answers", {"question": question, "value": value, "source": "From the site"})
	if taken:
		doc.save(ignore_permissions=True)
	return taken


def board(doc) -> dict:
	"""The whole wizard: every task, its questions, and what has been answered.

	A task appears when the answers so far call for it. Those are the wizard's
	own answers — the modules chosen in step two — so the wizard explains itself
	without reaching into anything else.
	"""
	answers = {row.question: row.value for row in doc.wizard_answers}
	sources = {row.question: row.get("source") for row in doc.wizard_answers}

	tasks, answered, total = [], 0, 0
	for task in frappe.get_all(
		"Embark Wizard Task",
		filters={"is_active": 1},
		fields=[
			"name",
			"task_name",
			"sequence",
			"stage",
			"kind",
			"work_note",
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
				"target_doctype",
			],
			order_by="sequence asc",
		):
			if not applies(q.applies_when, answers):
				continue
			# Its own record if it names one, otherwise the task's.
			target = q.target_doctype or task.target_doctype
			if target and not frappe.db.exists("DocType", target):
				continue
			questions.append(
				{
					"key": q.name,
					"label": q.label,
					"description": q.description,
					"example": q.example,
					"field": q.fieldname,
					"doctype": target,
					"type": q.answer_type,
					"choices": choices(q, target),
					"link_doctype": _link_doctype(q, target),
					"required": bool(q.is_required),
					"answer": answers.get(q.name, ""),
					"from_site": sources.get(q.name) == "From the site",
				}
			)

		# A work step has nothing to answer. It is still a step.
		if not questions and task.kind != "Work":
			continue
		done = sum(1 for q in questions if q["answer"])
		answered += done
		total += len(questions)
		tasks.append(
			{
				"task": task.name,
				"title": task.task_name,
				"stage": task.stage or "Setup",
				"kind": task.kind or "Questions",
				"work_note": task.work_note,
				"sequence": task.sequence or 0,
				"icon": task.icon,
				"doctype": task.target_doctype,
				"is_single": bool(task.is_single),
				"description": task.description,
				"questions": questions,
				"answered": done,
				"total": len(questions),
				"state": _("To do")
				if task.kind == "Work"
				else (
					_("Ready to apply")
					if done == len(questions)
					else (_("In progress") if done else _("Not started"))
				),
			}
		)

	return {
		"tasks": tasks,
		"stages": _stages(tasks),
		"answered": answered,
		"total": total,
		"percent": round(100 * answered / total) if total else 0,
	}


# Onboarding in three stages: who the company is, which parts of ERPNext it
# runs, and then only the setup those parts call for. The third stage is
# shorter for having asked the second, which is the point of the order.
STAGES = (
	("Company", _("Company details"), _("Who the business is, as it is registered.")),
	("Modules", _("Modules"), _("Which parts of ERPNext this business will run.")),
	("Setup", _("Setup questions"), _("Only what the modules you chose actually need.")),
)


def _stages(tasks: list[dict]) -> list[dict]:
	"""Each stage, with how much of it is answered.

	A stage with no task of its own is left out rather than shown empty — the
	wizard is configuration, and a site may have been given its own.
	"""
	out = []
	for key, title, description in STAGES:
		mine = [task for task in tasks if task["stage"] == key]
		if not mine:
			continue
		answered = sum(task["answered"] for task in mine)
		total = sum(task["total"] for task in mine)
		out.append(
			{
				"key": key,
				"title": title,
				"description": description,
				"tasks": len(mine),
				"answered": answered,
				"total": total,
				"done": bool(total) and answered == total,
			}
		)
	return out


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


def save_answers(doc, answers: dict) -> None:
	"""Several answers at once, saved in one write.

	The company's own details are a form, not an interview — a name, a country,
	a currency — so they arrive together and are kept together.
	"""
	known = set(
		frappe.get_all("Embark Wizard Question", filters={"name": ("in", list(answers))}, pluck="name")
	)
	unknown = set(answers) - known
	if unknown:
		frappe.throw(_("{0} is not one of the wizard's questions.").format(sorted(unknown)[0]))

	rows = {row.question: row for row in doc.wizard_answers}
	for question, value in answers.items():
		if question in rows:
			rows[question].value = value
		else:
			doc.append("wizard_answers", {"question": question, "value": value})
	doc.save(ignore_permissions=True)


def check(doc, task: str) -> dict:
	"""What applying this task would do to ERPNext, and whether that is safe."""
	plans = _records(doc, task)
	if not plans:
		return {"about_to": "", "safe_because": [], "fields": [], "records": [], "ready": False}

	safe = [
		_("Every field below comes from an answer you gave — nothing is invented."),
		_("The record is written through a change set, copied first, so it can be put back."),
	]
	for plan in plans:
		meta = frappe.get_meta(plan["doctype"])
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

	records, fields = [], []
	for plan in plans:
		meta = frappe.get_meta(plan["doctype"])
		shown = [
			{"field": _(meta.get_field(f).label) if meta.get_field(f) else f, "value": v}
			for f, v in plan["values"].items()
		]
		records.append(
			{
				"doctype": plan["doctype"],
				"action": _("update") if plan["exists"] else _("create"),
				"fields": shown,
			}
		)
		fields.extend(shown)

	# "create a Payment Term and update Company", in the order they are written.
	doing = _(", ").join(f"{r['action']} {r['doctype']}" for r in records)
	return {
		"about_to": _("Embark is about to {0} in ERPNext.").format(doing),
		"safe_because": safe,
		"records": records,
		"fields": fields,
		"ready": True,
	}


def apply(doc, task: str) -> dict:
	"""Write the task's records, and hand back what ERPNext now holds."""
	import json

	plans = _records(doc, task)
	if not plans:
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
				for plan in plans
			],
		}
	).insert(ignore_permissions=True)
	change_set.apply()

	made = [result(change.ref_doctype, change.ref_name) for change in change_set.changes if change.ref_name]
	return {
		"task": task,
		"change_set": change_set.name,
		# The first is what the screen shows; a step that wrote several hands
		# back all of them.
		"record": made[0] if made else None,
		"records": made,
	}


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
	made: dict[str, list] = {}
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
				here = made.setdefault(change.summary, [])
				if (change.ref_doctype, change.ref_name) not in here:
					here.append((change.ref_doctype, change.ref_name))

	board_now = board(doc)
	tasks = []
	for task in board_now["tasks"]:
		built = made.get(task["task"]) or []
		tasks.append(
			{
				**{k: task[k] for k in ("task", "title", "icon", "doctype", "answered", "total", "state")},
				"record": result(*built[0]) if built else None,
				"records": [result(*one) for one in built],
			}
		)

	return {
		"tasks": tasks,
		"answered": board_now["answered"],
		"total": board_now["total"],
		"percent": board_now["percent"],
		"built": sum(1 for t in tasks if t["record"]),
	}


def _records(doc, task: str) -> list[dict]:
	"""What this task's answers add up to: a record per doctype they fill.

	A step is a topic, and a topic can reach more than one record — credit
	terms are a Payment Term, a default on the Company and a role in Accounts
	Settings. Each answer says which record it belongs to, so they are grouped
	by that and written together.
	"""
	task_doc = frappe.get_cached_doc("Embark Wizard Task", task)
	answers = {row.question: row.value for row in doc.wizard_answers}

	# Doctype -> {field: value}, in the order the questions ask for them.
	wanted: dict[tuple[str, bool], dict] = {}
	missing = []
	for q in frappe.get_all(
		"Embark Wizard Question",
		filters={"task": task, "is_active": 1},
		fields=["name", "fieldname", "answer_type", "is_required", "target_doctype", "is_single", "applies_when"],
		order_by="sequence asc",
	):
		if not applies(q.applies_when, answers):
			continue
		value = (answers.get(q.name) or "").strip()
		if not value:
			if q.is_required:
				missing.append(q.name)
			continue
		# A question with no field of its own decides whether later questions
		# are asked. It is an answer, not a value to write.
		if not q.fieldname:
			continue
		doctype = q.target_doctype or task_doc.target_doctype
		if not doctype or not frappe.db.exists("DocType", doctype):
			continue
		single = bool(q.is_single if q.target_doctype else task_doc.is_single)
		# Two questions filling the same field of the same doctype are asking
		# for two records, not overwriting one: "your other stock location"
		# and "where rejected goods go" are both a warehouse_name, and only
		# one warehouse was ever made.
		key = (doctype, single)
		while key in wanted and q.fieldname in wanted[key] and not single:
			key = (*key, q.name)
		values = wanted.setdefault(key, {})
		values[q.fieldname] = (
			1
			if q.answer_type == "Yes / No" and value.lower() in ("yes", "1", "true")
			else (0 if q.answer_type == "Yes / No" else value)
		)

	if missing:
		return []

	rows = _child_rows(wanted)
	plans = [_plan(doc, key[0], key[1], values) for key, values in wanted.items() if values]
	_link_siblings(plans)
	for plan in plans:
		for field, row in rows.get(plan["doctype"], {}).items():
			plan["values"][field] = [row]
	return plans


def _link_siblings(plans: list[dict]) -> None:
	"""Point the records a step makes at each other.

	A bank account belongs to a bank, and a step that asks for both makes
	both — but the account was planned without knowing the bank's name, so
	ERPNext refused it. The records are written in order, so by the time the
	second one lands the first exists.
	"""
	named = {}
	for plan in plans:
		meta = frappe.get_meta(plan["doctype"])
		title = meta.autoname.split(":")[1] if (meta.autoname or "").startswith("field:") else None
		known = plan["name"] or (plan["values"].get(title) if title else None)
		if known:
			named[plan["doctype"]] = known

	for plan in plans:
		meta = frappe.get_meta(plan["doctype"])
		for field in meta.fields:
			# Only a link the record cannot do without. A territory has a
			# manager field and a step that also names a salesperson does not
			# thereby make them the manager — that is a relationship nobody
			# stated, and inventing one is worse than leaving it empty.
			if field.fieldtype != "Link" or not field.reqd or plan["values"].get(field.fieldname):
				continue
			if field.options in named and field.options != plan["doctype"]:
				plan["values"][field.fieldname] = named[field.options]

	# And written in that order, so the record being pointed at exists first.
	plans.sort(key=lambda plan: any(
		field.fieldtype == "Link" and field.reqd and field.options in named and field.options != plan["doctype"]
		for field in frappe.get_meta(plan["doctype"]).fields
	))


def _child_rows(wanted: dict) -> dict:
	"""Lift a child table's answers onto the record that holds it.

	Some of what a step asks belongs in a row of another record it is already
	making: how an Asset Category depreciates is a row on that category, not a
	record of its own. The questions name the child doctype, and the parent is
	whichever record in the same step has a table of them.
	"""
	parents = [key[0] for key in wanted if not frappe.get_meta(key[0]).istable]
	out: dict[str, dict] = {}
	for key in list(wanted):
		doctype = key[0]
		if not frappe.get_meta(doctype).istable:
			continue
		row = wanted.pop(key)
		for parent in parents:
			field = next(
				(f for f in frappe.get_meta(parent).get_table_fields() if f.options == doctype), None
			)
			if field:
				out.setdefault(parent, {})[field.fieldname] = row
				break
	return out


def _plan(doc, doctype: str, single: bool, values: dict) -> dict:
	"""One record: where it goes, whether it is already there, and its fields."""
	if single:
		return {"doctype": doctype, "name": doctype, "values": values, "exists": True}

	meta = frappe.get_meta(doctype)
	company = the_company(doc)

	# A step that sets the company's defaults is editing the company, not
	# making another one. It never asks for the company's name, so there is
	# nothing to recognise it by — and a create then fails on the fields it
	# was never going to ask for, or worse, succeeds and the site has two
	# companies and two charts of accounts.
	if doctype == "Company" and company and not values.get("company_name"):
		return {"doctype": doctype, "name": company, "values": values, "exists": True}

	# Company-scoped records need the company, and nobody should have to type it.
	if company and meta.get_field("company") and "company" not in values:
		values["company"] = company

	# What the record must have is worked out first, because some of it is
	# what identifies the record: a fiscal year is named after its own dates,
	# and ERPNext already made the one the customer is about to go live in.
	_fill_required(doctype, meta, values, company)

	# A record that is already there is updated, not made twice.
	title_field = (
		meta.get_field(meta.autoname.split(":")[1]) if (meta.autoname or "").startswith("field:") else None
	)
	guess = values.get(title_field.fieldname) if title_field else None
	existing = guess if guess and frappe.db.exists(doctype, guess) else None

	return {"doctype": doctype, "name": existing, "values": values, "exists": bool(existing)}


def the_company(doc) -> str:
	"""The company this onboarding is for, as ERPNext knows it."""
	if doc.company_name and frappe.db.exists("Company", doc.company_name):
		return doc.company_name
	return frappe.db.get_value("Company", {}, "name", order_by="creation asc") or ""


def _fill_required(doctype: str, meta, values: dict, company: str) -> None:
	"""Fill what a new record must have and nobody should be asked for.

	A customer answering "which day are you closed?" has told us everything
	about their holidays that matters. ERPNext also wants the list to have a
	name and a start and end date, which follow from the year, not from them.
	Without these the step is planned happily and refused on the way in.
	"""
	defaults = _REQUIRED_DEFAULTS.get(doctype)
	if not defaults:
		return
	for field, make in defaults.items():
		if values.get(field) or not meta.get_field(field):
			continue
		value = make(values, company)
		if value:
			values[field] = value


def _year_of(values: dict) -> str:
	start = values.get("year_start_date") or frappe.utils.nowdate()
	end = frappe.utils.add_days(frappe.utils.add_years(frappe.utils.getdate(start), 1), -1)
	return frappe.utils.formatdate(start, "yyyy") + "-" + frappe.utils.formatdate(end, "yyyy")


_REQUIRED_DEFAULTS = {
	"Fiscal Year": {
		"year": lambda values, company: _year_of(values),
		"year_end_date": lambda values, company: frappe.utils.add_days(
			frappe.utils.add_years(frappe.utils.getdate(values.get("year_start_date")), 1), -1
		)
		if values.get("year_start_date")
		else None,
	},
	"Holiday List": {
		"holiday_list_name": lambda values, company: f"{company} Holidays" if company else "Holidays",
		"from_date": lambda values, company: frappe.utils.get_year_start(frappe.utils.nowdate()),
		"to_date": lambda values, company: frappe.utils.get_year_ending(frappe.utils.nowdate()),
	},
	"Address": {
		"address_title": lambda values, company: company or "Head Office",
		"address_type": lambda values, company: "Billing",
		"country": lambda values, company: frappe.db.get_value("Company", company, "country")
		if company
		else None,
	},
	"Cost Center": {
		"parent_cost_center": lambda values, company: frappe.db.get_value(
			"Cost Center", {"company": company, "is_group": 1}, "name"
		)
		if company
		else None,
	},
	"Bank Account": {
		"account_name": lambda values, company: values.get("bank_account_no") or company or "Current Account",
		"bank": lambda values, company: frappe.db.get_value("Bank", {}, "name", order_by="creation desc"),
	},
	"Price List": {
		"currency": lambda values, company: frappe.db.get_value("Company", company, "default_currency")
		if company
		else None,
		"selling": lambda values, company: 1,
	},
	"Warehouse": {
		"parent_warehouse": lambda values, company: frappe.db.get_value(
			"Warehouse", {"company": company, "is_group": 1}, "name"
		)
		if company
		else None,
	},
}
