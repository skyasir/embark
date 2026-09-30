"""The standard masters ERPNext creates in its setup wizard.

Embark runs on the customer's new site before the setup wizard has run, so the
standard units, item groups, customer and supplier groups and territories do not
exist yet. Without these a customer writing "Nos" or "Commercial" would be told
the value is unknown, although the setup wizard is about to create it.
"""

from __future__ import annotations

import frappe

# ERPNext v15 writes these records inline in install_fixtures.install(); v16 moved
# them into get_preset_records(), which is used when it exists.
V15_NAMES = {
	# The two price lists ERPNext's setup wizard always creates.
	"Price List": ["Standard Selling", "Standard Buying"],
	"Item Group": ["All Item Groups", "Products", "Raw Material", "Services", "Sub Assemblies", "Consumable"],
	"Customer Group": ["All Customer Groups", "Individual", "Commercial", "Non Profit", "Government"],
	"Supplier Group": [
		"All Supplier Groups",
		"Services",
		"Local",
		"Raw Material",
		"Electrical",
		"Hardware",
		"Pharmaceutical",
		"Distributor",
	],
	"Territory": ["All Territories", "Rest Of The World"],
}


def standard_values(doctype: str, country: str | None = None) -> list[str]:
	if doctype == "UOM":
		path = frappe.get_app_path("erpnext", "setup", "setup_wizard", "data", "uom_data.json")
		return [row["uom_name"] for row in frappe.get_file_json(path)]

	try:
		from erpnext.setup.setup_wizard.operations.install_fixtures import get_preset_records
	except ImportError:
		get_preset_records = None

	# get_preset_records builds the country's own territory, so it needs a country.
	if get_preset_records and country:
		field = frappe.scrub(doctype) + "_name"
		return [
			r.get(field) or r.get("name") for r in get_preset_records(country) if r.get("doctype") == doctype
		]

	names = list(V15_NAMES.get(doctype, []))
	if doctype == "Territory" and country:
		names.append(country.replace("'", ""))
	return names
