from urllib.parse import quote

import frappe
from frappe.boot import load_translations

no_cache = 1


def get_context(context):
	"""Serve the portal SPA to signed-in users; send guests to the login page first."""
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=" + quote(
			frappe.request.full_path.rstrip("?")
		)
		raise frappe.Redirect

	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()  # nosemgrep

	context = frappe._dict()
	context.csrf_token = csrf_token
	context.boot = get_boot()
	return context


def get_boot():
	bootinfo = frappe._dict({"site_name": frappe.local.site, "default_route": "/embark"})
	load_translations(bootinfo)
	# load_translations sets lang to a LocalProxy, which Jinja's tojson refuses.
	# Coerce it after the call, never before.
	bootinfo.lang = str(bootinfo.lang)
	return bootinfo
