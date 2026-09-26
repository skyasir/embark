# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document

from embark.embark.doctype.embark_onboarding.embark_onboarding import (
	LOCKED_STATUSES,
)
from embark.engine import (
	MAX_STORED_ISSUES,
	REFERENCE_DOCTYPES,
	build_columns,
	check,
	match_columns,
	read_file,
)
from embark.permissions import is_staff
from embark.presets import standard_values


class EmbarkUpload(Document):
	def validate(self):
		onboarding = frappe.get_doc("Embark Onboarding", self.onboarding)
		ensure_editable(onboarding.status)
		if self.data_area not in {row.data_area for row in onboarding.areas}:
			frappe.throw(_("{0} is not part of this onboarding's package.").format(self.data_area))
		if frappe.db.exists(
			"Embark Upload",
			{"onboarding": self.onboarding, "data_area": self.data_area, "name": ("!=", self.name)},
		):
			frappe.throw(
				_("There is already an upload for {0}; replace its file instead.").format(self.data_area)
			)

		self.evaluate(store=True)

	def on_update(self):
		before = self.get_doc_before_save()
		if not self.flags.skip_dependents and (not before or before.key_values != self.key_values):
			self.recheck_dependents()
		if not self.flags.skip_parent_refresh:
			frappe.get_doc("Embark Onboarding", self.onboarding).save()

	def on_trash(self):
		ensure_editable(frappe.db.get_value("Embark Onboarding", self.onboarding, "status"))
		# The onboarding's step table links here; Frappe refuses the delete until it is unlinked.
		frappe.db.set_value(
			"Embark Onboarding Area", {"upload": self.name}, "upload", None, update_modified=False
		)

	def after_delete(self):
		self.recheck_dependents()
		if frappe.db.exists("Embark Onboarding", self.onboarding):
			frappe.get_doc("Embark Onboarding", self.onboarding).save()

	def get_file(self):
		"""The upload's File, but only one that belongs to this onboarding.

		Without this a customer could point file_url at another customer's
		private file and read it back through the check results.
		"""
		name = frappe.db.get_value(
			"File",
			{
				"file_url": self.file_url,
				"attached_to_doctype": "Embark Onboarding",
				"attached_to_name": self.onboarding,
			},
		) or frappe.db.get_value(
			"File",
			{
				"file_url": self.file_url,
				"attached_to_doctype": "Embark Upload",
				"attached_to_name": self.name,
			},
		)
		if not name:
			frappe.throw(_("Upload the file to this onboarding first."))
		return frappe.get_doc("File", name)

	def evaluate(self, store=False):
		"""Read the file and check it. With ``store`` the results are kept on this document."""
		area = frappe.get_cached_doc("Embark Data Area", self.data_area)
		columns = build_columns(area, frappe.get_doc("Embark Onboarding", self.onboarding).answer_map())
		file_doc = self.get_file()
		headers, rows = read_file(file_doc)

		# A new file with different headings gets a fresh suggestion; the same
		# headings keep whatever the customer chose last time.
		column_map = frappe.parse_json(self.column_map) if self.column_map else None
		if column_map is None or (frappe.parse_json(self.headers) or []) != headers:
			column_map = match_columns(headers, columns)
		column_map = {h: f for h, f in column_map.items() if h in headers and f}

		result = check(
			columns=columns,
			headers=headers,
			rows=rows,
			column_map=column_map,
			overrides=frappe.parse_json(self.overrides) if self.overrides else {},
			known=known_values(self.onboarding, columns, exclude=self.name),
			key_field=area.key_field,
			target_doctype=area.target_doctype,
			link_areas=link_areas(onboarding_areas(self.onboarding)),
		)

		if store:
			self.file_name = file_doc.file_name
			self.headers = json.dumps(headers)
			self.column_map = json.dumps(column_map)
			self.rows = len(rows)
			self.errors = result.errors
			self.warnings = result.warnings
			self.issues = json.dumps(
				{
					"groups": result.groups,
					"items": result.issues[:MAX_STORED_ISSUES],
					"truncated": len(result.issues) > MAX_STORED_ISSUES,
				},
				default=str,
			)
			self.key_values = json.dumps(result.keys)

		return frappe._dict(area=area, columns=columns, headers=headers, rows=rows, result=result)

	def recheck_dependents(self):
		"""Re-check the other sheets that link to this one (Items name an Item Group)."""
		target = frappe.get_cached_value("Embark Data Area", self.data_area, "target_doctype")
		answers = frappe.get_doc("Embark Onboarding", self.onboarding).answer_map()
		for name in frappe.get_all(
			"Embark Upload",
			filters={"onboarding": self.onboarding, "name": ("!=", self.name)},
			pluck="name",
		):
			doc = frappe.get_doc("Embark Upload", name)
			columns = build_columns(frappe.get_cached_doc("Embark Data Area", doc.data_area), answers)
			if any(c.fieldtype == "Link" and c.link_doctype == target for c in columns):
				doc.flags.skip_dependents = True
				doc.flags.skip_parent_refresh = True
				doc.save()


def ensure_editable(status: str | None):
	"""Once sent for review, the customer's data is frozen until the consultant returns it."""
	if status in LOCKED_STATUSES and not is_staff():
		frappe.throw(
			_(
				"Your data has been sent for review, so it can't be changed now. Ask your consultant to return it if something needs fixing."
			),
			title=_("Sent for review"),
		)


def onboarding_areas(onboarding: str) -> list[str]:
	return frappe.get_all(
		"Embark Onboarding Area",
		filters={"parent": onboarding, "parenttype": "Embark Onboarding"},
		pluck="data_area",
	)


def link_areas(areas: list[str]) -> dict[str, str]:
	"""Target doctype → the step in this package that supplies it, e.g. Item Group → Item Groups."""
	return {frappe.get_cached_value("Embark Data Area", a, "target_doctype"): a for a in areas}


def known_values(onboarding: str, columns, exclude: str | None = None) -> dict[str, dict[str, str]]:
	"""Values each Link column may take: the customer's other sheets plus the reference masters."""
	needed = {c.link_doctype for c in columns if c.fieldtype == "Link" and c.link_doctype != "Company"}
	known: dict[str, dict[str, str]] = {dt: {} for dt in needed}

	country = frappe.db.get_value("Embark Onboarding", onboarding, "country") or frappe.db.get_default(
		"country"
	)
	for dt in needed & REFERENCE_DOCTYPES:
		# A new customer site has none of these until ERPNext's setup wizard runs;
		# accept what the wizard will create.
		for name in frappe.get_all(dt, pluck="name") or standard_values(dt, country):
			known[dt][name.lower()] = name

	for u in frappe.get_all(
		"Embark Upload",
		filters={"onboarding": onboarding, "name": ("!=", exclude or "")},
		fields=["data_area", "key_values"],
	):
		dt = frappe.get_cached_value("Embark Data Area", u.data_area, "target_doctype")
		if dt in known:
			for key in frappe.parse_json(u.key_values) or []:
				known[dt][key.lower()] = key
	return known
