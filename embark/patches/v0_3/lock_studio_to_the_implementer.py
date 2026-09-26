"""Studio is implementation work, so its page and records follow the new role.

The page and the change sets shipped open to System Managers, which on a
customer's own site includes the customer. Both now sit behind Embark Studio.
"""

import frappe

from embark.copilot import STUDIO_ROLE


def execute():
	if not frappe.db.exists("Role", STUDIO_ROLE):
		frappe.get_doc({"doctype": "Role", "role_name": STUDIO_ROLE, "desk_access": 1}).insert(
			ignore_permissions=True
		)

	if frappe.db.exists("Page", "embark-studio"):
		page = frappe.get_doc("Page", "embark-studio")
		page.set("roles", [{"role": STUDIO_ROLE}])
		page.save(ignore_permissions=True)

	for doctype in ("Embark Change Set", "Embark Change"):
		if frappe.db.exists("DocType", doctype):
			frappe.db.delete("DocPerm", {"parent": doctype, "role": ("!=", STUDIO_ROLE)})
	frappe.clear_cache()
