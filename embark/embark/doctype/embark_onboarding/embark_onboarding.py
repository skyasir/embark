# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from embark.conditions import applies
from embark.permissions import is_staff

# What the customer must answer before the company can be created. The rest of
# the company section is useful but never blocks readiness.
COMPANY_FIELDS = ("company_name", "country", "default_currency", "fiscal_year_start")

# Once handed over, the customer's data is frozen until the consultant returns it.
LOCKED_STATUSES = ("Submitted", "Approved")


class EmbarkOnboarding(Document):
	def validate(self):
		self.guard_locked()
		self.sync_areas()
		self.set_abbr()
		self.refresh_areas()
		self.guard_status()

	def guard_locked(self):
		before = self.get_doc_before_save()
		if before and before.status in LOCKED_STATUSES and not is_staff():
			frappe.throw(
				_(
					"Your data has been sent for review, so it can't be changed now. Ask your consultant to return it if something needs fixing."
				),
				title=_("Sent for review"),
			)

	def answer_map(self) -> dict[str, str]:
		return {row.question: row.answer for row in self.answers if row.answer not in (None, "")}

	def sync_areas(self):
		"""The package sets what is in scope; the answers decide what of it is asked for.

		A step the customer has already uploaded to is kept even if their answers
		later say it does not apply, so nothing they did quietly disappears.
		"""
		package = frappe.get_cached_doc("Embark Package", self.package)
		answers = self.answer_map()
		existing = {row.data_area: row for row in self.areas}
		wanted = []
		for row in package.areas:
			area = frappe.get_cached_doc("Embark Data Area", row.data_area)
			kept = existing.get(row.data_area)
			if applies(area.applies_when, answers) or (kept and kept.upload):
				wanted.append((row.data_area, row.required))

		self.set("areas", [])
		for data_area, required in wanted:
			old = existing.get(data_area)
			self.append(
				"areas",
				{
					"data_area": data_area,
					"required": required,
					"status": old.status if old else "Not Started",
					"rows": old.rows if old else 0,
					"errors": old.errors if old else 0,
					"warnings": old.warnings if old else 0,
					"upload": old.upload if old else None,
				},
			)

	def interview(self) -> dict:
		"""How far the interview has got, counting only the questions being asked."""
		answers = self.answer_map()
		asked = [
			q
			for q in frappe.get_all(
				"Embark Question",
				filters={"is_active": 1},
				fields=["name", "applies_when"],
				order_by="sequence asc",
			)
			if applies(q.applies_when, answers)
		]
		answered = sum(1 for q in asked if answers.get(q.name))
		return {"answered": answered, "total": len(asked), "done": bool(asked) and answered == len(asked)}

	def set_abbr(self):
		# The same rule as ERPNext's setup wizard: initials of the company name.
		if self.company_name and not self.abbr:
			self.abbr = "".join(w[0] for w in self.company_name.split() if w[0].isalnum()).upper()[:5]

	def refresh_areas(self):
		"""Recompute each area's status and the readiness figure from the uploads.

		Always derived, never trusted from the client: a save from the portal
		cannot claim an area is ready.
		"""
		uploads = {}
		if not self.is_new():
			for u in frappe.get_all(
				"Embark Upload",
				filters={"onboarding": self.name},
				fields=["name", "data_area", "rows", "errors", "warnings"],
			):
				uploads[u.data_area] = u

		for row in self.areas:
			u = uploads.get(row.data_area)
			row.upload = u.name if u else None
			row.rows = u.rows if u else 0
			row.errors = u.errors if u else 0
			row.warnings = u.warnings if u else 0
			if not u:
				row.status = "Not Started"
			elif u.errors or not u.rows:
				row.status = "Needs Attention"
			else:
				row.status = "Ready"

		required = [row for row in self.areas if row.required]
		done = (
			int(self.interview()["done"])
			+ int(self.company_complete())
			+ sum(1 for row in required if row.status == "Ready")
		)
		self.readiness = round(100 * done / (2 + len(required)))

	def company_complete(self) -> bool:
		return all(self.get(f) for f in COMPANY_FIELDS)

	def guard_status(self):
		before = self.get_doc_before_save()
		old = before.status if before else "Draft"
		if is_staff():
			return

		# Any change the customer makes means the work is under way.
		if self.status == old and old in ("Draft", "Returned"):
			self.status = "In Progress"
			return
		if self.status == old:
			return

		if self.status == "Submitted" and cint(self.readiness) == 100:
			return
		if self.status == "In Progress" and old in ("Draft", "Returned"):
			return
		frappe.throw(_("You can't change the status of this onboarding."))
