"""Remove contact columns that were added a second time under shorter names.

The Customers and Suppliers steps have always collected contact and address
details as contact_email, contact_phone, address_city and so on. A later seed
briefly added email, phone, city, state and pincode beside them, which made the
same thing appear twice on the typing grid and in the template.

Only the duplicates go, and only where the original is still there.
"""

import frappe

DUPLICATES = ("email", "phone", "city", "state", "pincode")
ORIGINALS = ("contact_email", "contact_phone", "address_city", "address_state", "address_pincode")


def execute():
	for area in ("Customers", "Suppliers"):
		if not frappe.db.exists("Embark Data Area", area):
			continue
		doc = frappe.get_doc("Embark Data Area", area)
		have = {row.fieldname for row in doc.fields}
		if not set(ORIGINALS) <= have:
			continue  # nothing to fall back on; leave the step alone
		keep = [row for row in doc.fields if row.fieldname not in DUPLICATES]
		if len(keep) == len(doc.fields):
			continue
		doc.fields = keep
		for i, row in enumerate(doc.fields, start=1):
			row.idx = i
		doc.save(ignore_permissions=True)
