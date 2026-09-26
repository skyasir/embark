"""Row-level access: a customer sees only the onboarding they were invited to.

Role permissions decide *what* a customer may do (read, write, upload); these
hooks decide *which* records. Staff get no extra restriction.
"""

import frappe

STAFF_ROLES = {"System Manager", "Embark Consultant"}


def is_staff(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(STAFF_ROLES & set(frappe.get_roles(user)))


def can_open_embark() -> bool:
	return is_staff() or "Embark Customer" in frappe.get_roles()


def onboarding_has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if is_staff(user):
		return None
	return bool(doc.portal_user) and doc.portal_user == user


def upload_has_permission(doc, ptype=None, user=None, **kwargs):
	user = user or frappe.session.user
	if is_staff(user):
		return None
	if not doc.onboarding:
		return False
	return frappe.db.get_value("Embark Onboarding", doc.onboarding, "portal_user") == user


def onboarding_query(user=None, **kwargs):
	user = user or frappe.session.user
	if is_staff(user):
		return ""
	return f"`tabEmbark Onboarding`.`portal_user` = {frappe.db.escape(user)}"


def upload_query(user=None, **kwargs):
	user = user or frappe.session.user
	if is_staff(user):
		return ""
	return (
		"`tabEmbark Upload`.`onboarding` in (select `name` from `tabEmbark Onboarding`"
		f" where `portal_user` = {frappe.db.escape(user)})"
	)
