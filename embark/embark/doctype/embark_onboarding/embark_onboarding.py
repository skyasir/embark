# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from embark.conditions import applies
from embark.engine import asked_keys

# What the customer must answer before the company can be created. The rest of
# the company section is useful but never blocks readiness.
COMPANY_FIELDS = ("company_name", "country", "default_currency", "fiscal_year_start")

# Once handed over, the customer's data is frozen until the consultant returns it.
LOCKED_STATUSES = ("Submitted", "Approved")


class EmbarkOnboarding(Document):
	def validate(self):
		self.guard_locked()
		self.sync_areas()
		self.sync_tasks()
		self.set_abbr()
		self.refresh_areas()
		self.advance_status()

	def guard_locked(self):
		"""Once sent for review the data is read-only; returning it opens it again."""
		before = self.get_doc_before_save()
		if before and before.status in LOCKED_STATUSES and self.status == before.status:
			frappe.throw(
				_("This onboarding has been sent for review. Return it first to make changes."),
				title=_("Sent for review"),
			)

	def answer_map(self) -> dict[str, str]:
		return {row.question: row.answer for row in self.answers if row.answer not in (None, "")}

	def sync_areas(self):
		"""The answers decide which steps this customer is asked for.

		There is no checklist until the interview has been answered: the steps are
		built from the answers, not trimmed from a standard list. A step the
		customer has already uploaded to is kept even if their answers later say it
		does not apply, so nothing they did quietly disappears.
		"""
		answers = self.answer_map()
		asked = asked_keys(answers)
		existing = {row.data_area: row for row in self.areas}
		# Once the checklist exists it keeps up with the answers; before that it
		# takes a finished interview to build one, so a half-answered interview
		# never shows a standard list of steps.
		planned = bool(self.areas) or self.interview()["done"]
		wanted = []
		for area in frappe.get_all(
			"Embark Data Area", fields=["name", "required", "applies_when"], order_by="sequence asc"
		):
			kept = existing.get(area.name)
			if (planned and applies(area.applies_when, answers, asked)) or (kept and kept.upload):
				wanted.append(area)

		self.set("areas", [])
		for area in wanted:
			old = existing.get(area.name)
			self.append(
				"areas",
				{
					"data_area": area.name,
					"required": area.required,
					"status": old.status if old else "Not Started",
					"rows": old.rows if old else 0,
					"errors": old.errors if old else 0,
					"warnings": old.warnings if old else 0,
					"upload": old.upload if old else None,
				},
			)

	def sync_tasks(self):
		"""The rest of the plan: what we switch on, decide and train, from the answers.

		Built by the same rules as the data steps, so the whole plan is the
		interview's doing. A line the consultant has already dealt with is kept,
		whatever the answers say now.
		"""
		answers = self.answer_map()
		asked = asked_keys(answers)
		existing = {row.setup_task: row for row in self.tasks}
		planned = bool(self.areas or self.tasks) or self.interview()["done"]
		wanted = []
		for task in frappe.get_all(
			"Embark Setup Task",
			filters={"is_active": 1},
			fields=["name", "title", "kind", "applies_when", "because"],
			order_by="sequence asc",
		):
			kept = existing.get(task.name)
			settled = kept and kept.status != "Planned"
			if (planned and applies(task.applies_when, answers, asked)) or settled:
				wanted.append(task)

		self.set("tasks", [])
		for task in wanted:
			old = existing.get(task.name)
			self.append(
				"tasks",
				{
					"setup_task": task.name,
					"title": task.title,
					"kind": task.kind,
					"because": task.because,
					"status": old.status if old else "Planned",
					"notes": old.notes if old else None,
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

	def advance_status(self):
		"""Draft until someone starts filling it in."""
		if self.status == "Draft" and (self.answers or self.readiness):
			self.status = "In Progress"

	def company_complete(self) -> bool:
		return all(self.get(f) for f in COMPANY_FIELDS)
