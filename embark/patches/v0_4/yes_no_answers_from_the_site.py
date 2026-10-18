"""An adopted checkbox was stored as 1, and the question offers Yes and No.

Anything taken off the site before this looked unanswered on screen: the tick
was green, the step counted it, and the answer box was empty.
"""

import frappe


def execute():
	yes_no = frappe.get_all(
		"Embark Wizard Question", filters={"answer_type": "Yes / No"}, pluck="name"
	)
	if not yes_no:
		return

	rows = frappe.get_all(
		"Embark Wizard Answer",
		filters={"question": ("in", yes_no), "value": ("in", ["0", "1"])},
		fields=["name", "value"],
	)
	for row in rows:
		frappe.db.set_value(
			"Embark Wizard Answer", row.name, "value", "Yes" if row.value == "1" else "No",
			update_modified=False,
		)
