"""The customer journey end to end, run as a real Website User.

bench --site <site> run-tests --module embark.tests.test_onboarding
"""

import io
import json
import zipfile

import frappe
from openpyxl import Workbook, load_workbook

from embark import api, assistant
from embark.conditions import applies
from embark.engine import Column, build_columns, coerce, match_columns, split_header

try:  # v16
	from frappe.tests import IntegrationTestCase as TestCase
except ImportError:  # v15
	from frappe.tests.utils import FrappeTestCase as TestCase


def xlsx(rows) -> bytes:
	wb = Workbook()
	for r in rows:
		wb.active.append(r)
	out = io.BytesIO()
	wb.save(out)
	return out.getvalue()


class TestEngine(TestCase):
	def test_header_below_a_title_row(self):
		headers, rows = split_header(
			[["Customer List"], [], ["Name", "GSTIN"], ["Sunrise", "27AAA"], [None, None]]
		)
		self.assertEqual(headers, ["Name", "GSTIN"])
		self.assertEqual(rows, [(4, ["Sunrise", "27AAA"])])

	def test_columns_match_by_alias_and_fuzzy(self):
		cols = [
			Column("customer_name", "Customer Name", "Data", aliases=["Party Name"]),
			Column("tax_id", "Tax ID", "Data", aliases=["GSTIN"]),
			Column("customer_group", "Customer Group", "Link"),
		]
		self.assertEqual(
			match_columns(["Party Name", "GSTIN No.", "Customer Grp", "Notes"], cols),
			{"Party Name": "customer_name", "GSTIN No.": "tax_id", "Customer Grp": "customer_group"},
		)
		self.assertEqual(match_columns(["GSTIN", "Notes"], cols), {"GSTIN": "tax_id"})

	def test_coercion(self):
		check = Column("x", "X", "Check")
		self.assertEqual(coerce(check, "yes")[:2], (1, None))
		self.assertEqual(coerce(check, "maybe")[1], "BAD_YESNO")
		num = Column("x", "X", "Float")
		self.assertEqual(coerce(num, "₹1,250.50")[:2], (1250.5, None))
		phone = Column("x", "X", "Phone")
		self.assertEqual(coerce(phone, 9876543210.0)[:2], ("9876543210", None))
		choice = Column("x", "X", "Select", choices=["Company", "Individual"])
		self.assertEqual(coerce(choice, "individual")[:2], ("Individual", None))
		date = Column("x", "X", "Date")
		self.assertEqual(coerce(date, "03/04/2026")[0], "2026-04-03")
		required = Column("x", "X", "Data", required=True)
		self.assertEqual(coerce(required, "  ")[1], "REQUIRED_MISSING")
		defaulted = Column("x", "X", "Check", default="Yes")
		self.assertEqual(coerce(defaulted, None)[:2], (1, None))


class TestConditions(TestCase):
	def test_conditions(self):
		answers = {
			"keeps_stock": "yes",
			"business_type": "trading,manufacturing",
			"tracks_batches": "no",
			"unsure": "not_sure",
		}
		self.assertTrue(applies("", answers))
		self.assertTrue(applies("keeps_stock == yes", answers))
		self.assertFalse(applies("keeps_stock == no", answers))
		self.assertTrue(applies("business_type == manufacturing", answers))  # one of several
		self.assertTrue(applies("tracks_batches != yes", answers))
		self.assertTrue(applies("tracks_batches == yes or keeps_stock == yes", answers))
		self.assertFalse(applies("tracks_batches == yes and keeps_stock == yes", answers))
		# Unanswered, "not sure" and nonsense all leave the step visible.
		self.assertTrue(applies("never_asked == yes", answers))
		self.assertTrue(applies("unsure == yes", answers))
		self.assertTrue(applies("!!!", answers))


class TestOnboardingFlow(TestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.delete("Embark Upload")
		frappe.db.delete("Embark Onboarding")
		self.onboarding = frappe.get_doc(
			{"doctype": "Embark Onboarding", "client_name": "Sunrise Traders", "consultant": "Administrator"}
		).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def answer_interview(self, **answers):
		"""Answer every question that gets asked, following the branches."""
		while True:
			questions = api.get_interview(self.onboarding.name)["questions"]
			todo = {
				q["key"]: answers.get(q["key"], self.default_answer(q)) for q in questions if not q["answer"]
			}
			if not todo:
				return
			api.save_answers(self.onboarding.name, todo)

	@staticmethod
	def default_answer(question):
		if question["type"] == "Number":
			return "1"
		if question["type"] == "Yes / No":
			return "yes"
		return question["choices"][0]["value"]

	def upload(self, area, rows, name=None):
		"""Upload a sheet the way the portal does: a private File on the onboarding."""
		f = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": name or f"{area}.xlsx",
				"content": xlsx(rows),
				"is_private": 1,
				"attached_to_doctype": "Embark Onboarding",
				"attached_to_name": self.onboarding.name,
			}
		).insert()
		return api.attach_file(self.onboarding.name, area, f.file_url)

	def test_customer_journey(self):
		overview = api.get_overview()
		self.assertEqual(overview["name"], self.onboarding.name)
		# The company is only asked for when ERPNext has not been set up yet.
		self.assertEqual(overview["company_complete"], api.setup_done())
		self.assertEqual(overview["readiness"], 50 if api.setup_done() else 0)
		# Nothing is asked for until the interview has been answered.
		self.assertEqual(overview["steps"], [])

		# A trader, so the plan holds no workstations or operations.
		self.answer_interview(manufactures="no", subcontracts="no")
		overview = api.get_overview(self.onboarding.name)
		self.assertTrue(overview["interview"]["done"])
		self.assertEqual([s["area"] for s in overview["steps"]][:2], ["Users", "Item Groups"])

		overview = api.save_company_details(
			self.onboarding.name,
			{
				"company_name": "Sunrise Traders",
				"country": "India",
				"default_currency": "INR",
				"fiscal_year_start": "2026-04-01",
			},
		)
		self.assertTrue(overview["company_complete"])
		self.assertEqual(overview["status"], "In Progress")

		# Items first: their group is not uploaded yet, so it cannot be found.
		area = self.upload(
			"Items",
			[
				["Product List"],
				["SKU", "Product Name", "Category", "UOM", "Maintain Stock", "MRP"],
				["FG-1", "Rack", "Finished Goods", "nos", "Yes", "2,500"],
				["FG-1", "Rack copy", "Products", "Nos", "Yes", "10"],
				["RM-1", "Steel", "Products", "Kilo", "maybe", "abc"],
			],
		)
		up = area["upload"]
		mapped = {h["header"]: h["fieldname"] for h in up["headers"]}
		self.assertEqual(mapped["SKU"], "item_code")
		self.assertEqual(mapped["Category"], "item_group")
		self.assertEqual(mapped["UOM"], "stock_uom")
		codes = {(i["code"], i["fieldname"]) for i in up["issues"]}
		self.assertIn(("NOT_FOUND", "item_group"), codes)  # Finished Goods
		self.assertIn(("DUPLICATE", "item_code"), codes)
		self.assertIn(("NOT_FOUND", "stock_uom"), codes)  # Kilo
		kilo = next(i for i in up["issues"] if i["code"] == "NOT_FOUND" and i["fieldname"] == "stock_uom")
		self.assertEqual(kilo["suggestions"], ["Kg"])
		group = next(i for i in up["issues"] if i["code"] == "NOT_FOUND" and i["fieldname"] == "item_group")
		self.assertIn("Item Groups step", group["hint"])
		self.assertIn(("BAD_YESNO", "is_stock_item"), codes)
		self.assertIn(("BAD_NUMBER", "standard_rate"), codes)
		# 'nos' is the standard unit Nos, written in lower case: fixed silently.
		self.assertEqual(up["preview"]["rows"][0]["stock_uom"], "Nos")
		self.assertEqual(up["preview"]["rows"][0]["standard_rate"], 2500)

		# Uploading Item Groups re-checks Items: Finished Goods is now known.
		self.upload("Item Groups", [["Item Group", "Belongs To"], ["Finished Goods", ""]])
		up = api.get_area(self.onboarding.name, "Items")["upload"]
		self.assertNotIn(("NOT_FOUND", "item_group"), {(i["code"], i["fieldname"]) for i in up["issues"]})

		# Fix on screen: one value everywhere, and single rows.
		api.fix_value(self.onboarding.name, "Items", "stock_uom", "Kg", old_value="Kilo")
		api.fix_value(self.onboarding.name, "Items", "item_code", "FG-2", row=4)
		api.fix_value(self.onboarding.name, "Items", "is_stock_item", "Yes", row=5)
		up = api.fix_value(self.onboarding.name, "Items", "standard_rate", "90", row=5)["upload"]
		self.assertEqual(up["errors"], 0, up["issues"])

		# The file itself is untouched; fixes live beside it.
		stored = frappe.get_doc("Embark Upload", {"onboarding": self.onboarding.name, "data_area": "Items"})
		self.assertEqual(json.loads(stored.overrides)["*"]["stock_uom"], {"Kilo": "Kg"})

		self.upload("Users", [["Name", "Email"], ["Asha", "asha@sunrise.com"]])
		self.upload("Warehouses", [["Godown"], ["Main Store"], ["Shop"]])
		self.upload("Customers", [["Party Name", "GSTIN", "Mobile"], ["Acme", "27AAACS1234A1Z5", 9876543210]])

		# A column the customer's file lacks can be chosen by hand.
		area = self.upload("Suppliers", [["Vendor", "Branch Office"], ["Apex Steel", "Pune"]])
		self.assertEqual(
			{h["header"]: h["fieldname"] for h in area["upload"]["headers"]}["Branch Office"], None
		)
		area = api.set_column(self.onboarding.name, "Suppliers", "Branch Office", "address_city")
		self.assertEqual(area["upload"]["preview"]["rows"][0]["address_city"], "Pune")

		overview = api.get_overview(self.onboarding.name)
		self.assertEqual(overview["readiness"], 100, overview["steps"])
		self.assertTrue(overview["can_submit"])

		overview = api.submit_for_review(self.onboarding.name)
		self.assertEqual(overview["status"], "Submitted")
		self.assertTrue(overview["locked"])
		self.assertRaises(frappe.ValidationError, self.upload, "Users", [["Email"], ["x@y.com"]])
		api.review(self.onboarding.name, "Returned", "One more thing")
		self.upload("Users", [["Name", "Email"], ["Asha", "asha@sunrise.com"]])  # open again

		# The consultant gets ERPNext-shaped files.
		frappe.set_user("Administrator")
		api.download_prepared_data(self.onboarding.name)
		zf = zipfile.ZipFile(io.BytesIO(frappe.response.filecontent))
		items = next(n for n in zf.namelist() if n.endswith("Items.xlsx"))
		sheet = load_workbook(io.BytesIO(zf.read(items))).active
		header = [c.value for c in sheet[1]]
		self.assertIn("Item Code", header)
		self.assertEqual(sheet.max_row, 4)
		warehouses = next(n for n in zf.namelist() if n.endswith("Warehouses.xlsx"))
		self.assertEqual(load_workbook(io.BytesIO(zf.read(warehouses))).active["A2"].value, "Sunrise Traders")

		self.assertEqual(
			api.review(self.onboarding.name, "Returned", "Add your price list")["status"], "Returned"
		)
		self.assertEqual(api.get_overview()["review_notes"], "Add your price list")

	def test_remove_file(self):
		self.answer_interview()
		self.upload("Units of Measure", [["Unit"], ["Carton"]])
		self.assertEqual(self.step("Units of Measure")["status"], "Ready")
		area = api.remove_file(self.onboarding.name, "Units of Measure")
		self.assertIsNone(area["upload"])
		self.assertEqual(self.step("Units of Measure")["status"], "Not Started")
		self.assertFalse(frappe.db.exists("Embark Upload", {"onboarding": self.onboarding.name}))

		# Once sent for review, the customer can't remove files either.
		self.upload("Units of Measure", [["Unit"], ["Carton"]])
		frappe.db.set_value("Embark Onboarding", self.onboarding.name, "status", "Submitted")
		self.assertRaises(frappe.ValidationError, api.remove_file, self.onboarding.name, "Units of Measure")

	def step(self, area):
		return next(s for s in api.get_overview(self.onboarding.name)["steps"] if s["area"] == area)

	def test_file_must_belong_to_the_onboarding(self):
		other = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "elsewhere.xlsx",
				"content": xlsx([["Email"], ["a@b.com"]]),
				"is_private": 1,
				"attached_to_doctype": "User",
				"attached_to_name": "Administrator",
			}
		).insert()
		self.assertRaises(
			frappe.ValidationError, api.attach_file, self.onboarding.name, "Users", other.file_url
		)

	def test_start_onboarding(self):
		"""One site, one onboarding, started by a System Manager."""
		frappe.db.delete("Embark Upload")
		frappe.db.delete("Embark Onboarding")
		self.assertTrue(api.get_overview()["needs_start"])

		overview = api.start_onboarding("Yasir Traders")["overview"]
		self.assertEqual(overview["client_name"], "Yasir Traders")
		self.assertEqual(api.get_overview()["name"], overview["name"])
		# A new onboarding starts with the interview and nothing else: the steps
		# are built from the answers.
		self.assertEqual(overview["steps"], [])
		self.assertRaises(frappe.ValidationError, api.start_onboarding, "Someone Else")

	def test_standard_values_before_setup(self):
		from unittest.mock import patch

		from embark.embark.doctype.embark_upload import embark_upload
		from embark.presets import standard_values

		self.assertIn("Nos", standard_values("UOM"))
		self.assertIn("Commercial", standard_values("Customer Group", "India"))
		self.assertIn("Products", standard_values("Item Group", "India"))
		self.assertIn("India", standard_values("Territory", "India"))

		# On a site whose setup wizard has not run, those tables are empty.
		real_get_all = frappe.get_all

		def empty_masters(doctype, *args, **kwargs):
			if doctype in ("UOM", "Item Group", "Customer Group", "Supplier Group", "Territory"):
				return []
			return real_get_all(doctype, *args, **kwargs)

		columns = build_columns(frappe.get_doc("Embark Data Area", "Items"))
		with patch.object(embark_upload.frappe, "get_all", side_effect=empty_masters):
			known = embark_upload.known_values(self.onboarding.name, columns)
		self.assertEqual(known["UOM"].get("nos"), "Nos")
		self.assertEqual(known["Item Group"].get("products"), "Products")

	def test_tally_answer_offers_the_migrator(self):
		self.assertIsNone(api.get_overview(self.onboarding.name)["tally"])

		overview = api.save_answers(self.onboarding.name, {"current_system": "tally"})
		self.assertEqual(overview["tally"]["route"], "/app/tally-migrator")
		self.assertEqual(overview["tally"]["installed"], "tally_migrator" in frappe.get_installed_apps())

		# Anyone else is left alone.
		self.assertIsNone(api.save_answers(self.onboarding.name, {"current_system": "paper"})["tally"])

	def test_no_checklist_until_the_interview_is_answered(self):

		def steps():
			return [s["area"] for s in api.get_overview(self.onboarding.name)["steps"]]

		# The checklist is built from the answers, not trimmed from a standard
		# list, so a customer who has answered nothing is asked for nothing.
		self.assertEqual(steps(), [])
		self.assertRaises(frappe.DoesNotExistError, api.get_area, self.onboarding.name, "Items")

		# Half an interview is still no checklist.
		api.save_answers(self.onboarding.name, {"keeps_stock": "yes"})
		self.assertEqual(steps(), [])

		self.answer_interview()
		self.assertIn("Items", steps())

	def test_assistant_is_off_until_a_provider_is_configured(self):
		self.assertFalse(assistant.is_on())
		self.assertFalse(api.get_overview(self.onboarding.name)["assistant"])
		self.assertRaises(frappe.ValidationError, api.ask, "hello", self.onboarding.name)

	def test_a_tool_call_written_as_text_is_still_a_tool_call(self):
		"""A small model often types the call instead of making it."""
		from embark import llm

		written = '{"name": "save_answers", "parameters": {"answers": {"keeps_stock": "no"}}}'
		self.assertEqual(
			llm.recovered_calls(written),
			[{"id": "recovered-save_answers", "name": "save_answers", "arguments": {"answers": {"keeps_stock": "no"}}}],
		)
		# Fenced, and with a sentence around it, is the same call.
		self.assertTrue(llm.recovered_calls(f"Sure:\n```json\n{written}\n```"))
		# Plain talk is left alone.
		self.assertEqual(llm.recovered_calls("What do you sell?"), [])
		self.assertFalse(llm.looks_like_plumbing("What do you sell?"))
		self.assertTrue(llm.looks_like_plumbing(written))

	def test_the_assistant_acts_on_a_written_tool_call(self):
		from unittest.mock import patch

		frappe.db.set_single_value(
			"Embark Settings",
			{"assistant_enabled": 1, "provider": "OpenAI compatible", "model": "stub", "base_url": "http://stub.invalid/v1"},
		)
		frappe.clear_cache(doctype="Embark Settings")

		turns = [
			{
				"text": '{"name": "save_answers", "parameters": {"answers": {"keeps_stock": "no"}}}',
				"raw": {"role": "assistant"},
				"tool_calls": [],
			},
			{"text": "Noted, no stock.", "raw": {"role": "assistant"}, "tool_calls": []},
		]
		with patch.object(assistant, "_complete", side_effect=turns):
			result = api.ask("we hold no stock", self.onboarding.name)

		self.assertEqual(result["used"], ["save_answers"])
		self.assertEqual(result["reply"], "Noted, no stock.")
		doc = frappe.get_doc("Embark Onboarding", self.onboarding.name)
		self.assertEqual(doc.answer_map()["keeps_stock"], "no")

	def test_assistant_answers_the_interview_and_nothing_else(self):
		from unittest.mock import patch

		frappe.db.set_single_value(
			"Embark Settings",
			{
				"assistant_enabled": 1,
				"provider": "OpenAI compatible",
				"model": "stub",
				"base_url": "http://stub.invalid/v1",
			},
		)
		frappe.clear_cache(doctype="Embark Settings")
		self.assertTrue(assistant.is_on())

		# The model looks at what is open, saves what the customer described,
		# then answers in words.
		turns = [
			{
				"text": "",
				"raw": {"role": "assistant"},
				"tool_calls": [{"id": "1", "name": "open_questions", "arguments": {}}],
			},
			{
				"text": "",
				"raw": {"role": "assistant"},
				"tool_calls": [
					{
						"id": "2",
						"name": "save_answers",
						"arguments": {"answers": {"keeps_stock": "no", "business_type": "services"}},
					}
				],
			},
			{"text": "Noted: services, no stock.", "raw": {"role": "assistant"}, "tool_calls": []},
		]
		with patch.object(assistant, "_complete", side_effect=turns):
			result = api.ask("We're a services firm, we hold no stock.", self.onboarding.name)

		self.assertEqual(result["reply"], "Noted: services, no stock.")
		self.assertEqual(result["used"], ["open_questions", "save_answers"])
		doc = frappe.get_doc("Embark Onboarding", self.onboarding.name)
		self.assertEqual(doc.answer_map()["keeps_stock"], "no")
		# It went through save_answers, so the same validation applies to it.
		self.assertEqual(
			assistant._run_tool(self.onboarding.name, "save_answers", {"answers": {"nope": "yes"}}).get(
				"error"
			)
			is not None,
			True,
		)

	def test_the_plan_is_generated_from_the_answers(self):

		def plan():
			return {line["key"]: line for line in api.get_overview(self.onboarding.name)["plan"]}

		# No interview, no plan — the settings and training are not a standard list.
		self.assertEqual(plan(), {})

		self.answer_interview(keeps_stock="no", manufactures="no", tax_registered="no")
		lines = plan()
		self.assertNotIn("batches", lines)
		self.assertNotIn("costing_method", lines)
		self.assertNotIn("training_stock", lines)
		self.assertNotIn("tax_setup", lines)
		self.assertIn("training_selling", lines)

		# Keeping stock brings the stock side of the plan with it, and says why.
		api.save_answers(
			self.onboarding.name,
			{"keeps_stock": "yes", "tracks_batches": "yes", "tax_registered": "yes"},
		)
		self.answer_interview()
		lines = plan()
		self.assertEqual(lines["batches"]["kind"], "Setting")
		self.assertEqual(lines["batches"]["because"], "you track batches or expiry dates")
		self.assertEqual(lines["costing_method"]["kind"], "Decision")
		self.assertIn("training_stock", lines)
		self.assertIn("tax_setup", lines)

		# A line the consultant has settled survives a change of mind.
		doc = frappe.get_doc("Embark Onboarding", self.onboarding.name)
		for row in doc.tasks:
			if row.setup_task == "batches":
				row.status = "Done"
		doc.save()
		api.save_answers(self.onboarding.name, {"tracks_batches": "no"})
		self.assertEqual(plan()["batches"]["status"], "Done")

	def test_interview_shapes_the_onboarding(self):

		def steps():
			return [s["area"] for s in api.get_overview(self.onboarding.name)["steps"]]

		def item_columns():
			return {c["fieldname"] for c in api.get_area(self.onboarding.name, "Items")["columns"]}

		# A business with no stock is not asked for warehouses or stock columns.
		self.answer_interview(keeps_stock="no", business_type="services")
		overview = api.get_overview(self.onboarding.name)
		self.assertNotIn("Warehouses", steps())
		self.assertEqual(item_columns() & {"has_batch_no", "has_serial_no", "is_stock_item"}, set())
		self.assertTrue(overview["interview"]["done"])
		# The stock questions are no longer asked, so they are not counted either.
		asked = [q["key"] for q in api.get_interview(self.onboarding.name)["questions"]]
		self.assertNotIn("tracks_batches", asked)

		# The template follows the same columns.
		api.download_template("Items", self.onboarding.name)
		headers = [c.value for c in load_workbook(io.BytesIO(frappe.response.filecontent)).active[1]]
		self.assertNotIn("Batch Tracked", headers)

		# Saying yes again brings the step and its questions back.
		api.save_answers(self.onboarding.name, {"keeps_stock": "yes"})
		self.assertIn("Warehouses", steps())
		self.assertIn(
			"tracks_batches", [q["key"] for q in api.get_interview(self.onboarding.name)["questions"]]
		)

		# A step that already holds an upload is never taken away.
		self.upload("Warehouses", [["Godown"], ["Main Store"]])
		api.save_answers(self.onboarding.name, {"keeps_stock": "no"})
		self.assertIn("Warehouses", steps())

		self.assertRaises(
			frappe.ValidationError, api.save_answers, self.onboarding.name, {"keeps_stock": "maybe"}
		)
		self.assertRaises(frappe.ValidationError, api.save_answers, self.onboarding.name, {"nope": "yes"})

	def test_template_download(self):
		self.answer_interview()
		api.download_template("Customers", self.onboarding.name)
		wb = load_workbook(io.BytesIO(frappe.response.filecontent))
		self.assertEqual(wb.sheetnames[1], "How to fill")
		self.assertEqual(wb.active["A1"].value, "Customer Name *")
