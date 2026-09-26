app_name = "embark"
app_title = "Embark"
app_publisher = "Yasir Shaikh"
app_description = "Package-based data readiness for fast-track standard ERPNext implementations."
app_email = "erp.yasirshaikh@gmail.com"
app_license = "mit"
required_apps = ["frappe/erpnext"]

# Packages, data areas and the two roles are seed records, not fixtures:
# fixtures would overwrite a consultant's edits on every migrate.
# A customer with desk access lands in Embark (their default app) and can switch
# to the desk; the Apps screen brings them back.
add_to_apps_screen = [
	{
		"name": "embark",
		"logo": "/assets/embark/embark-logo.svg",
		"title": "Embark",
		"route": "/embark",
		"has_permission": "embark.permissions.can_open_embark",
	}
]

after_install = "embark.install.after_install"
after_migrate = "embark.install.after_migrate"

# A customer is a Website User and must only ever see their own onboarding.
has_permission = {
	"Embark Onboarding": "embark.permissions.onboarding_has_permission",
	"Embark Upload": "embark.permissions.upload_has_permission",
}
permission_query_conditions = {
	"Embark Onboarding": "embark.permissions.onboarding_query",
	"Embark Upload": "embark.permissions.upload_query",
}

# The portal is a single-page app, so a reload on any sub-route must land on
# the same entry page instead of a 404.
website_route_rules = [
	{"from_route": "/embark/<path:app_path>", "to_route": "embark"},
]

# A customer signing in should land on their onboarding, not the website home.
role_home_page = {"Embark Customer": "embark"}
