"""Stop asking for a sheet of units of measure.

ERPNext ships 239 of them — Nos, Kg, Litre, Box and the rest — so the step asked
a customer to type a list their new site already had. Embark's whole promise is
that it only asks for what the business actually needs.

The step is switched off rather than deleted: a site where somebody already
uploaded units keeps the file, the rows and the history. It simply is not asked
for again.
"""

import frappe


def execute():
	if not frappe.db.exists("Embark Data Area", "Units of Measure"):
		return
	frappe.db.set_value("Embark Data Area", "Units of Measure", "is_active", 0)

	# Drop it from onboardings that have not sent anything for it. One that has
	# keeps its row, so the upload stays reachable.
	for row in frappe.get_all(
		"Embark Onboarding Area",
		filters={"data_area": "Units of Measure", "upload": ("is", "not set")},
		fields=["name", "parent"],
	):
		frappe.db.delete("Embark Onboarding Area", row.name)
		frappe.db.set_value(
			"Embark Onboarding", row.parent, "modified", frappe.utils.now(), update_modified=False
		)

	frappe.clear_cache()
