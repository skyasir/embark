"""A set of changes to this site, applied together and undoable together.

Embark Studio can change a site — add a field, rename a label, make a report. Doing
that from a chat is only safe if every change is written down first, applied in
one transaction, and can be put back exactly as it was. That is what this
record is: the request, the changes it produced, and how each record looked
before.

Two rules keep it honest:

* Only the doctypes in ``allowed_doctypes()`` can be touched: the list below —
  fields, properties, scripts, reports, workflows — and the settings that decide
  how ERPNext behaves, which is what Embark configures from the plan. Never a
  customer's invoices, stock or ledgers.
* Nothing is applied twice, and nothing is undone twice: the status says which
  state the set is in, and the undo restores from the snapshot taken at apply
  time, not from whatever the model thinks it did.
"""

import json

import frappe
from frappe import _
from frappe.model.document import Document

# How the site is set up, and nothing else. Business data is never in reach.
#
# Two kinds of record qualify. The customisation layer is what Studio composes.
# The settings singles are what a standard implementation *is* — Embark works
# out which ones the business needs from the interview, and writing them is the
# whole point of the plan. A Price List is here because an item price cannot be
# imported onto a list that does not exist; the rates on it stay the customer's.
ALLOWED = (
	# The settings a standard implementation configures
	"Account",
	"Sales Taxes and Charges Template",
	"Purchase Taxes and Charges Template",
	"Item Tax Template",
	"Tax Category",
	"Payment Terms Template",
	"Selling Settings",
	"Buying Settings",
	"Stock Settings",
	"Manufacturing Settings",
	"Accounts Settings",
	"Price List",
	# The customisation layer
	"Custom Field",
	"Property Setter",
	"Client Script",
	"Server Script",
	"Report",
	"Workflow",
	"Workflow State",
	"Workflow Action Master",
	"Notification",
	"Print Format",
	"Dashboard Chart",
	"Number Card",
	"Translation",
)


# A snapshot is a whole record. These columns belong to the row, not to what
# the change did, and writing them back breaks the save.
SNAPSHOT_SKIP = ("name", "doctype", "creation", "owner", "modified", "modified_by", "idx")


def allowed_doctypes() -> set[str]:
	"""What Embark may write: the list above, plus whatever the wizard asks for.

	The setup wizard's questions each name the record they fill — a Company, a
	Warehouse, a Payment Term — and those are the records a standard
	implementation is made of. Keeping a second copy of that list here would
	mean a question added to the bank could not be applied until somebody
	remembered to come back and allow it, which is exactly the kind of gap
	nobody finds until a customer presses the button.

	It stays bounded: the bank is a file in this app, every doctype in it is a
	master or a settings record, and nothing a question does not name can be
	touched.
	"""
	# Only a question that fills a field writes anything. A question like "do
	# your customers return goods?" names Sales Invoice to say what it is
	# about, and must not thereby hand Embark the right to write invoices.
	asked = frappe.get_all(
		"Embark Wizard Question",
		filters={"is_active": 1, "target_doctype": ("is", "set"), "fieldname": ("is", "set")},
		pluck="target_doctype",
	)
	tasks = frappe.get_all(
		"Embark Wizard Task",
		filters={"is_active": 1, "target_doctype": ("is", "set")},
		pluck="target_doctype",
	)
	return set(ALLOWED) | set(asked) | set(tasks)


class EmbarkChangeSet(Document):
	def validate(self):
		allowed = allowed_doctypes()
		for row in self.changes:
			if row.ref_doctype not in allowed:
				frappe.throw(
					_("Embark does not change {0}. It only changes how the site is set up.").format(
						frappe.bold(row.ref_doctype)
					)
				)
			if row.action in ("Update", "Delete") and not row.ref_name:
				frappe.throw(_("A change that edits or removes a record needs its name."))

	@frappe.whitelist()
	def apply(self) -> dict:
		"""Write every change, remembering how each record looked first."""
		if self.status == "Applied":
			frappe.throw(_("This change set has already been applied."))

		# Writing a Custom Field commits, so a database rollback cannot take the
		# earlier changes back. The snapshots can: undo what was done, in reverse.
		done = []
		try:
			for row in self.changes:
				row.before = json.dumps(_snapshot(row), default=str)
				_write(row)
				done.append(row)
		except Exception as e:
			for row in reversed(done):
				try:
					_restore(row)
				except Exception:
					frappe.log_error(
						f"{self.name}: could not undo {row.ref_doctype} {row.ref_name}",
						"Embark Studio change set",
					)
			self.reload()
			self.db_set({"status": "Failed", "error": str(e)[:1000]})
			raise

		self.db_set(
			{
				"status": "Applied",
				"error": None,
				"applied_at": frappe.utils.now(),
				"applied_by": frappe.session.user,
			}
		)
		for row in self.changes:
			row.db_update()
		frappe.clear_cache()
		return {"status": self.status, "changes": len(self.changes)}

	@frappe.whitelist()
	def undo(self) -> dict:
		"""Put every record back the way the snapshot says it was."""
		if self.status != "Applied":
			frappe.throw(_("Only an applied change set can be undone."))

		try:
			# Backwards: a later change may depend on an earlier one.
			for row in reversed(self.changes):
				_restore(row)
		except Exception as e:
			self.reload()
			self.db_set({"status": "Failed", "error": str(e)[:1000]})
			raise

		self.db_set({"status": "Undone", "error": None})
		frappe.clear_cache()
		return {"status": self.status}


def _snapshot(row) -> dict | None:
	"""The record as it is now, or None when it does not exist yet."""
	if row.action == "Create":
		return None
	if not frappe.db.exists(row.ref_doctype, row.ref_name):
		return None
	return frappe.get_doc(row.ref_doctype, row.ref_name).as_dict(no_nulls=True)


def _write(row) -> None:
	payload = frappe.parse_json(row.payload) or {}
	if row.action == "Create":
		doc = frappe.get_doc({"doctype": row.ref_doctype, **payload})
		doc.insert(ignore_permissions=True)
		# The name is only known once it is inserted, and the undo needs it.
		row.ref_name = doc.name
		return

	# Two lines of a plan can land on the same settings record, and the first
	# write leaves a stale copy in the document cache. Loading that copy and
	# saving it is a timestamp clash, so the cache is dropped first.
	frappe.clear_document_cache(row.ref_doctype, row.ref_name)
	doc = frappe.get_doc(row.ref_doctype, row.ref_name)
	if row.action == "Delete":
		doc.delete(ignore_permissions=True)
		return

	doc.update(payload)
	doc.save(ignore_permissions=True)


def _restore(row) -> None:
	before = frappe.parse_json(row.before)
	exists = row.ref_name and frappe.db.exists(row.ref_doctype, row.ref_name)

	if before is None:
		# It did not exist before this change set, so it should not exist now.
		if exists:
			frappe.delete_doc(row.ref_doctype, row.ref_name, ignore_permissions=True, force=True)
		return

	if not exists:
		frappe.get_doc(before).insert(ignore_permissions=True, set_name=row.ref_name)
		return

	frappe.clear_document_cache(row.ref_doctype, row.ref_name)
	doc = frappe.get_doc(row.ref_doctype, row.ref_name)
	# Everything the snapshot holds except its identity and its own bookkeeping:
	# putting the old `modified` back makes the save look stale to Frappe and it
	# refuses the write.
	doc.update({k: v for k, v in before.items() if k not in SNAPSHOT_SKIP})
	doc.save(ignore_permissions=True)
