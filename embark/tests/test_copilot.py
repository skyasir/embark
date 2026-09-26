# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from embark import copilot

# Custom fields commit as they are written, so a test that dies mid-way can
# leave one behind. Each test starts by clearing its own.
SCRATCH_FIELDS = ("Item-po_number", "Item-shelf_code")
SCRATCH_WORKFLOW = "Copilot Item Approval"


class TestCopilot(FrappeTestCase):
	def setUp(self):
		for name in SCRATCH_FIELDS:
			if frappe.db.exists("Custom Field", name):
				frappe.delete_doc("Custom Field", name, force=True, ignore_permissions=True)
		if frappe.db.exists("Workflow", SCRATCH_WORKFLOW):
			frappe.delete_doc("Workflow", SCRATCH_WORKFLOW, force=True, ignore_permissions=True)
		frappe.db.commit()
		frappe.clear_cache(doctype="Item")

	def tearDown(self):
		frappe.db.rollback()

	def test_a_field_is_added_and_can_be_taken_back(self):
		change = copilot.add_field("Item", "PO Number", "Data", insert_after="item_name")
		plan = copilot.propose("Add PO Number to Item", "add a PO number to items", [change])
		self.assertEqual(plan["status"], "Draft")
		# Nothing has happened to the site yet.
		self.assertIsNone(frappe.get_meta("Item").get_field("po_number"))

		applied = copilot.apply(plan["name"])
		self.assertEqual(applied["status"], "Applied")
		frappe.clear_cache(doctype="Item")
		self.assertIsNotNone(frappe.get_meta("Item").get_field("po_number"))

		undone = copilot.undo(plan["name"])
		self.assertEqual(undone["status"], "Undone")
		frappe.clear_cache(doctype="Item")
		self.assertIsNone(frappe.get_meta("Item").get_field("po_number"))

	def test_a_property_goes_back_to_what_it_was(self):
		before = frappe.get_meta("Item").get_field("item_name").label
		change = copilot.set_property("Item", "item_name", "label", "Product Name")
		plan = copilot.propose("Rename Item Name", "call it Product Name", [change])
		copilot.apply(plan["name"])
		frappe.clear_cache(doctype="Item")
		self.assertEqual(frappe.get_meta("Item").get_field("item_name").label, "Product Name")

		copilot.undo(plan["name"])
		frappe.clear_cache(doctype="Item")
		self.assertEqual(frappe.get_meta("Item").get_field("item_name").label, before)

	def test_a_workflow_is_built_and_taken_back(self):
		rows = copilot.create_workflow(
			"Item",
			"Copilot Item Approval",
			states=[
				{"state": "Draft", "role": "System Manager"},
				{"state": "Approved", "role": "System Manager"},
			],
			transitions=[
				{"state": "Draft", "action": "Approve", "next_state": "Approved", "role": "System Manager"}
			],
		)
		plan = copilot.propose("Item approval", "items should be approved", rows)
		copilot.apply(plan["name"])
		self.assertTrue(frappe.db.exists("Workflow", "Copilot Item Approval"))

		copilot.undo(plan["name"])
		self.assertFalse(frappe.db.exists("Workflow", "Copilot Item Approval"))

	def test_a_client_script_needs_somewhere_to_run(self):
		self.assertRaises(frappe.ValidationError, copilot.create_client_script, "Item", "")
		self.assertRaises(
			frappe.ValidationError, copilot.create_client_script, "Item", "console.log(1)", "Kanban"
		)
		change = copilot.create_client_script("Item", "frappe.ui.form.on('Item', {});")
		self.assertEqual(change["ref_doctype"], "Client Script")

	def test_an_image_has_to_be_an_image(self):
		from embark import copilot_chat

		png = "data:image/png;base64,iVBORw0KGgo="
		self.assertEqual(copilot_chat._check_images([png]), [png])
		self.assertEqual(copilot_chat._check_images(None), [])
		self.assertRaises(frappe.ValidationError, copilot_chat._check_images, ["https://example.com/a.png"])
		self.assertRaises(frappe.ValidationError, copilot_chat._check_images, ["data:text/html;base64,PGI+"])
		self.assertRaises(frappe.ValidationError, copilot_chat._check_images, [png] * 5)

		# Each provider wants them in its own shape.
		message = copilot_chat._user_message("look at this", [png])
		self.assertEqual(message["content"][0], {"type": "text", "text": "look at this"})
		self.assertIn(message["content"][1]["type"], ("image_url", "image"))
		self.assertEqual(copilot_chat._user_message("no images", [])["content"], "no images")

	def test_it_refuses_what_it_should_not_touch(self):
		# Business data is out of reach, whatever the model asks for.
		self.assertRaises(
			frappe.ValidationError,
			copilot.propose,
			"Delete an invoice",
			"remove that invoice",
			[{"action": "Delete", "ref_doctype": "Sales Invoice", "ref_name": "SINV-0001"}],
		)
		# So is a field on a doctype that does not exist, or of a type it cannot add.
		self.assertRaises(frappe.ValidationError, copilot.add_field, "Not A Doctype", "X")
		self.assertRaises(frappe.ValidationError, copilot.add_field, "Item", "X", "Table")
		# A report is a SELECT and nothing else.
		self.assertRaises(frappe.ValidationError, copilot.create_report, "Bad", "Item", "delete from tabItem")

	def test_a_failed_change_set_leaves_nothing_behind(self):
		good = copilot.add_field("Item", "Shelf Code", "Data")
		bad = {
			"action": "Update",
			"ref_doctype": "Property Setter",
			"ref_name": "does-not-exist",
			"summary": "nonsense",
			"payload": "{}",
		}
		plan = copilot.propose("Half broken", "two changes, one impossible", [good, bad])
		self.assertRaises(frappe.DoesNotExistError, copilot.apply, plan["name"])

		frappe.clear_cache(doctype="Item")
		self.assertIsNone(frappe.get_meta("Item").get_field("shelf_code"))
		self.assertEqual(frappe.db.get_value("Embark Change Set", plan["name"], "status"), "Failed")
