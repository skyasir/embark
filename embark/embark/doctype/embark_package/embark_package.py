# Copyright (c) 2026, Yasir Shaikh and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class EmbarkPackage(Document):
	def validate(self):
		areas = [row.data_area for row in self.areas]
		dupes = sorted({a for a in areas if areas.count(a) > 1})
		if dupes:
			frappe.throw(_("These data areas are listed twice: {0}").format(", ".join(dupes)))
		if any(row.role in ("System Manager", "Administrator") for row in self.desk_roles):
			frappe.throw(
				_("Desk roles can't include System Manager: setup and approval stay with the consultant.")
			)
