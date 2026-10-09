"""The interview opens by asking which parts of ERPNext the customer needs.

Everything after it follows: the questions asked, the data steps and the setup
list. Sites seeded before the question have steps that run whatever the answer,
so the two conditions that were written without it are brought up to date —
only where they still read exactly as Embark seeded them, so a consultant's own
edit is never overwritten.
"""

import frappe

# area → (the condition Embark used to seed, the condition it seeds now)
REWRITTEN = {
	"Item Groups": (
		"business_type != services",
		"business_type != services and modules == stock,selling,buying,manufacturing",
	),
}


def execute():
	from embark.install import seed

	seed()  # brings in the modules question, its gates and the new setup tasks

	for area, (was, now) in REWRITTEN.items():
		if frappe.db.get_value("Embark Data Area", area, "applies_when") == was:
			frappe.db.set_value("Embark Data Area", area, "applies_when", now)

	frappe.clear_cache()
