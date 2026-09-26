"""Embark has no roles or packages of its own any more.

Access comes from ERPNext (the site's System Managers), and the interview
answers decide which data steps a customer is asked for, so each step now
carries its own "required" flag.
"""

import frappe

from embark.install import AREAS


def execute():
	for role in ("Embark Consultant", "Embark Customer"):
		if frappe.db.exists("Role", role):
			frappe.db.delete("Has Role", {"role": role})
			frappe.delete_doc("Role", role, force=True, ignore_permissions=True)

	for doctype in ("Embark Package Area", "Embark Package Role", "Embark Package"):
		if frappe.db.exists("DocType", doctype):
			frappe.delete_doc("DocType", doctype, force=True, ignore_permissions=True)

	# The package used to say which steps were required.
	for area in AREAS:
		if frappe.db.exists("Embark Data Area", area["area_name"]):
			frappe.db.set_value("Embark Data Area", area["area_name"], "required", area["required"])
