"""Who may use Embark.

Embark has no roles of its own: the people setting a site up are its System
Managers, and everything they import is created through ERPNext's own
permissions anyway.
"""

import frappe


def is_staff(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def can_open_embark() -> bool:
	"""Shown on the Apps screen to anyone who may read an onboarding."""
	return bool(frappe.has_permission("Embark Onboarding", "read"))
