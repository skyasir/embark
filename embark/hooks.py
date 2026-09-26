app_name = "embark"
app_title = "Embark"
app_publisher = "Yasir Shaikh"
app_description = "Package-based data readiness for fast-track standard ERPNext implementations."
app_email = "erp.yasirshaikh@gmail.com"
app_license = "mit"
required_apps = ["frappe/erpnext"]

# Packages, data areas and the two roles are seed records, not fixtures:
# fixtures would overwrite a consultant's edits on every migrate.
# Embark appears on the desk's Apps screen, next to ERPNext.
add_to_apps_screen = [
	{
		"name": "embark",
		"logo": "/assets/embark/embark-logo.svg",
		"title": "Embark",
		"route": "/embark",
		"has_permission": "embark.permissions.can_open_embark",
	}
]

# Embark Studio: the editor and the copilot, carried in with Embark so a
# customer's site needs one app, not two.
after_install = "embark.install.after_install"
after_migrate = "embark.install.after_migrate"

# The portal is a single-page app, so a reload on any sub-route must land on
# the same entry page instead of a 404.
website_route_rules = [
	{"from_route": "/embark/<path:app_path>", "to_route": "embark"},
]
