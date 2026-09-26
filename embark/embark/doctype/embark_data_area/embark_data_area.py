# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.model.document import Document


class EmbarkDataArea(Document):
	def validate(self):
		meta = frappe.get_meta(self.target_doctype)
		names = [row.fieldname for row in self.fields]

		dupes = sorted({n for n in names if names.count(n) > 1})
		if dupes:
			frappe.throw(_("These columns are listed twice: {0}").format(", ".join(dupes)))

		if self.key_field and self.key_field not in names:
			frappe.throw(_("The unique field {0} must be one of the columns.").format(self.key_field))

		for row in self.fields:
			if not meta.get_field(row.fieldname) and not row.fieldtype:
				frappe.throw(
					_("Row {0}: {1} is not a field of {2}, so set its Extra Column Type.").format(
						row.idx, row.fieldname, self.target_doctype
					)
				)

		# ERPNext will refuse the record later if a mandatory field is never
		# collected. Company is filled from the onboarding, naming series by ERPNext.
		missing = [
			_(df.label)
			for df in meta.fields
			if df.reqd
			and not df.default
			and df.fieldtype not in no_value_fields
			and df.fieldname != "naming_series"
			and not (df.fieldtype == "Link" and df.options == "Company")
			and df.fieldname not in names
		]
		if missing and not (frappe.flags.in_install or frappe.flags.in_migrate):
			frappe.msgprint(
				_("{0} requires these fields, which this area does not collect: {1}").format(
					self.target_doctype, ", ".join(missing)
				),
				indicator="orange",
				alert=True,
			)
