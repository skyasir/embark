"""Seed the interview questions and the data steps.

Only missing records are created, so edits made in the desk survive every
migrate. To pick up a changed default, delete the record and migrate.
"""

import frappe

CONTACT_COLUMNS = [
	{
		"fieldname": "contact_person",
		"label": "Contact Person",
		"fieldtype": "Data",
		"example": "Rahul Mehta",
		"aliases": "Contact, Contact Name",
	},
	{
		"fieldname": "contact_email",
		"label": "Email",
		"fieldtype": "Email",
		"example": "accounts@sunrisetraders.com",
		"aliases": "Email ID, Email Address, E-mail, Mail",
	},
	{
		"fieldname": "contact_phone",
		"label": "Phone",
		"fieldtype": "Phone",
		"example": "+91 98765 43210",
		"aliases": "Mobile, Mobile No, Phone No, Contact Number, Contact No, Telephone",
	},
	{
		"fieldname": "address_line1",
		"label": "Address",
		"fieldtype": "Data",
		"example": "12 MG Road",
		"aliases": "Address Line 1, Street, Billing Address",
	},
	{
		"fieldname": "address_city",
		"label": "City",
		"fieldtype": "Data",
		"example": "Pune",
		"aliases": "Town, Location",
	},
	{
		"fieldname": "address_state",
		"label": "State",
		"fieldtype": "Data",
		"example": "Maharashtra",
		"aliases": "Province, State Name",
	},
	{
		"fieldname": "address_pincode",
		"label": "PIN / Postal Code",
		"fieldtype": "Data",
		"example": "411001",
		"aliases": "Pincode, PIN, Postal Code, Zip, Zip Code",
	},
]

TAX_ID = {
	"fieldname": "tax_id",
	"label": "Tax ID",
	"example": "27AAACS1234A1Z5",
	"applies_when": "tax_registered == yes",
	"hint": "GSTIN, VAT or TRN number, if registered.",
	"aliases": "GSTIN, GST No, GST Number, VAT, VAT Number, TRN, Tax Number, Tax Registration Number",
}

AREAS = [
	{
		"area_name": "Users",
		"icon": "users",
		"required": 1,
		"target_doctype": "User",
		"key_field": "email",
		"sequence": 10,
		"description": "The people who will use ERPNext.",
		"help_text": "One row per person. Their logins are created during the implementation, with access that matches what they do.",
		"fields": [
			{
				"fieldname": "first_name",
				"label": "First Name",
				"required": 1,
				"example": "Aisha",
				"aliases": "Name, Given Name, Full Name",
			},
			{
				"fieldname": "last_name",
				"label": "Last Name",
				"example": "Khan",
				"aliases": "Surname, Family Name",
			},
			{
				"fieldname": "email",
				"label": "Email",
				"required": 1,
				"example": "aisha@yourcompany.com",
				"aliases": "Email Address, Email ID, E-mail, Mail, Login",
			},
			{
				"fieldname": "mobile_no",
				"label": "Mobile",
				"example": "+91 98765 43210",
				"aliases": "Phone, Mobile Number, Contact Number",
			},
			{
				"fieldname": "job_role",
				"label": "What They Do",
				"fieldtype": "Data",
				"example": "Accounts",
				"hint": "For example Sales, Purchase, Stores or Accounts. It decides their access.",
				"aliases": "Role, Department, Designation, Job, Job Title",
			},
		],
	},
	{
		"area_name": "Item Groups",
		"icon": "layers",
		"required": 0,
		"target_doctype": "Item Group",
		"key_field": "item_group_name",
		"sequence": 20,
		"description": "How you group your products and services.",
		"help_text": "ERPNext already has Products, Raw Material, Services, Sub Assemblies and Consumable. Only list the groups you want in addition to those.",
		"fields": [
			{
				"fieldname": "item_group_name",
				"label": "Item Group",
				"required": 1,
				"example": "Finished Goods",
				"aliases": "Group, Category, Item Group Name, Stock Group",
			},
			{
				"fieldname": "parent_item_group",
				"label": "Belongs To",
				"default_value": "All Item Groups",
				"example": "All Item Groups",
				"hint": "Leave empty to place it at the top.",
				"aliases": "Parent, Parent Group, Under",
			},
			{
				"fieldname": "is_group",
				"label": "Has Sub-groups",
				"default_value": "No",
				"example": "No",
				"hint": "Yes if other groups sit under this one.",
				"aliases": "Is Group",
			},
		],
	},
	{
		"area_name": "Units of Measure",
		"icon": "hash",
		"required": 0,
		"target_doctype": "UOM",
		"key_field": "uom_name",
		"sequence": 30,
		"description": "Extra units you buy, sell or stock in.",
		"help_text": "ERPNext already has more than 200 units, such as Nos, Kg, Litre, Box and Meter. Only list units that are missing.",
		"fields": [
			{
				"fieldname": "uom_name",
				"label": "Unit",
				"required": 1,
				"example": "Carton",
				"aliases": "UOM, Unit Name, Unit of Measure, Units",
			},
			{
				"fieldname": "must_be_whole_number",
				"label": "Whole Numbers Only",
				"default_value": "No",
				"example": "Yes",
				"hint": "Yes if you can't have half of this unit.",
				"aliases": "Whole Number",
			},
		],
	},
	{
		"area_name": "Warehouses",
		"icon": "archive",
		"required": 1,
		"applies_when": "keeps_stock == yes",
		"target_doctype": "Warehouse",
		"key_field": "warehouse_name",
		"sequence": 40,
		"description": "The places where you keep stock.",
		"help_text": "List every store, godown or location that holds stock. Your company's short name is added to each one when it is set up.",
		"fields": [
			{
				"fieldname": "warehouse_name",
				"label": "Warehouse",
				"required": 1,
				"example": "Main Store",
				"aliases": "Godown, Location, Store, Warehouse Name",
			},
			{
				"fieldname": "parent_warehouse",
				"label": "Belongs To",
				"hint": "Leave empty unless it sits inside another warehouse on this sheet.",
				"aliases": "Parent, Under",
			},
			{
				"fieldname": "is_group",
				"label": "Has Sub-warehouses",
				"default_value": "No",
				"example": "No",
				"aliases": "Is Group",
			},
			{"fieldname": "city", "label": "City", "example": "Pune", "aliases": "Town, Location City"},
		],
	},
	{
		"area_name": "Customers",
		"icon": "user-check",
		"required": 1,
		"target_doctype": "Customer",
		"key_field": "customer_name",
		"sequence": 50,
		"description": "Everyone you sell to.",
		"help_text": "One row per customer. Contact and address details are optional, but adding them now saves time later.",
		"fields": [
			{
				"fieldname": "customer_name",
				"label": "Customer Name",
				"required": 1,
				"example": "Sunrise Traders",
				"aliases": "Name, Party Name, Customer, Client, Client Name, Ledger Name, Account Name",
			},
			{
				"fieldname": "customer_type",
				"label": "Customer Type",
				"default_value": "Company",
				"example": "Company",
				"aliases": "Type, Party Type",
			},
			{
				"fieldname": "customer_group",
				"label": "Customer Group",
				"example": "Commercial",
				"hint": "Commercial, Individual, Government or Non Profit. Leave empty if unsure.",
				"aliases": "Group, Category",
			},
			{
				"fieldname": "territory",
				"label": "Territory",
				"example": "India",
				"aliases": "Region, Area, Zone",
			},
			TAX_ID,
			{
				"fieldname": "default_currency",
				"label": "Billing Currency",
				"applies_when": "multi_currency == yes",
				"example": "INR",
				"hint": "Only if you bill this customer in another currency.",
				"aliases": "Currency",
			},
			*CONTACT_COLUMNS,
			{
				"fieldname": "address_country",
				"label": "Country",
				"fieldtype": "Link",
				"options": "Country",
				"example": "India",
				"aliases": "Country Name",
			},
		],
	},
	{
		"area_name": "Suppliers",
		"icon": "truck",
		"required": 1,
		"target_doctype": "Supplier",
		"key_field": "supplier_name",
		"sequence": 60,
		"description": "Everyone you buy from.",
		"help_text": "One row per supplier. Contact and address details are optional, but adding them now saves time later.",
		"fields": [
			{
				"fieldname": "supplier_name",
				"label": "Supplier Name",
				"required": 1,
				"example": "Apex Steel Pvt Ltd",
				"aliases": "Name, Party Name, Supplier, Vendor, Vendor Name, Ledger Name, Account Name",
			},
			{
				"fieldname": "supplier_type",
				"label": "Supplier Type",
				"default_value": "Company",
				"example": "Company",
				"aliases": "Type, Vendor Type, Supplier Category",
			},
			{
				"fieldname": "supplier_group",
				"label": "Supplier Group",
				"example": "Raw Material",
				"hint": "For example Local, Raw Material or Services. Leave empty if unsure.",
				"aliases": "Group, Category",
			},
			{"fieldname": "country", "label": "Country", "example": "India", "aliases": "Country Name"},
			TAX_ID,
			{
				"fieldname": "default_currency",
				"label": "Billing Currency",
				"applies_when": "multi_currency == yes",
				"example": "INR",
				"hint": "Only if this supplier bills you in another currency.",
				"aliases": "Currency",
			},
			*CONTACT_COLUMNS,
		],
	},
	{
		"area_name": "Items",
		"icon": "package",
		"required": 1,
		"target_doctype": "Item",
		"key_field": "item_code",
		"sequence": 70,
		"description": "Everything you buy, sell or make.",
		"help_text": "One row per product or service. Keep the codes you use today, so everyone recognises them.",
		"fields": [
			{
				"fieldname": "item_code",
				"label": "Item Code",
				"required": 1,
				"example": "FG-1001",
				"aliases": "Code, SKU, Product Code, Part Number, Part No, Item No",
			},
			{
				"fieldname": "item_name",
				"label": "Item Name",
				"example": "Steel Rack 4 ft",
				"aliases": "Name, Product Name, Stock Item Name, Product",
			},
			{
				"fieldname": "item_group",
				"label": "Item Group",
				"required": 1,
				"example": "Products",
				"aliases": "Group, Category, Stock Group",
			},
			{
				"fieldname": "stock_uom",
				"label": "Unit",
				"required": 1,
				"example": "Nos",
				"hint": "Nos, Kg, Litre, Box... or a unit from your Units of Measure sheet.",
				"aliases": "UOM, Unit of Measure, Units, Base Unit",
			},
			{
				"fieldname": "is_stock_item",
				"applies_when": "keeps_stock == yes",
				"label": "Keep Stock",
				"default_value": "Yes",
				"example": "Yes",
				"hint": "No for services and anything you don't count in a warehouse.",
				"aliases": "Maintain Stock, Stock Item, Is Stock Item",
			},
			{
				"fieldname": "has_batch_no",
				"applies_when": "keeps_stock == yes and tracks_batches == yes",
				"label": "Batch Tracked",
				"default_value": "No",
				"example": "No",
				"aliases": "Batch, Has Batch",
			},
			{
				"fieldname": "has_serial_no",
				"applies_when": "keeps_stock == yes and tracks_serials == yes",
				"label": "Serial Numbered",
				"default_value": "No",
				"example": "No",
				"aliases": "Serial, Has Serial",
			},
			{
				"fieldname": "standard_rate",
				"label": "Selling Price",
				"example": "2500",
				"aliases": "Rate, Price, MRP, Sale Price, Selling Rate",
			},
			{
				"fieldname": "description",
				"label": "Description",
				"example": "Powder-coated, 4 shelves",
				"aliases": "Details, Remarks, Item Description",
			},
		],
	},
]

CORE_AREAS = [
	("Users", 1),
	("Item Groups", 0),
	("Units of Measure", 0),
	("Warehouses", 1),
	("Customers", 1),
	("Suppliers", 1),
	("Items", 1),
]

# The interview. Answers decide which steps and columns a customer sees, and
# later which ERPNext settings are switched on.
QUESTIONS = [
	{
		"question_key": "current_system",
		"label": "What do you use today?",
		"section_title": "What you do",
		"sequence": 5,
		"answer_type": "One choice",
		"choices": (
			"tally | Tally\n"
			"spreadsheets | Excel or Google Sheets\n"
			"other_software | Another ERP or accounting package\n"
			"paper | Books and invoices by hand"
		),
		"help_text": "Where your data lives now. If it is in Tally we can bring it across instead of asking you to type it again.",
	},
	{
		"question_key": "business_type",
		"label": "What does your business do?",
		"section_title": "What you do",
		"sequence": 10,
		"answer_type": "Several choices",
		"choices": "trading | Buy and sell goods\nmanufacturing | Make or assemble goods\nservices | Provide services\nretail | Sell over the counter\ndistribution | Distribute for other brands",
		"help_text": "Pick everything that applies.",
	},
	{
		"question_key": "keeps_stock",
		"label": "Do you keep stock of what you sell?",
		"section_title": "What you do",
		"sequence": 20,
		"help_text": "No if you only sell services or order in for each customer.",
	},
	{
		"question_key": "sells_on_orders",
		"label": "Do you confirm sales with a quotation or order before invoicing?",
		"section_title": "Selling",
		"sequence": 30,
	},
	{
		"question_key": "delivers_partially",
		"label": "Do you deliver one order in more than one go?",
		"section_title": "Selling",
		"sequence": 40,
		"applies_when": "keeps_stock == yes",
	},
	{
		"question_key": "price_lists",
		"label": "Do different customers get different prices?",
		"section_title": "Selling",
		"sequence": 50,
		"help_text": "For example wholesale and retail rates.",
	},
	{
		"question_key": "buys_on_orders",
		"label": "Do you send purchase orders to your suppliers?",
		"section_title": "Buying",
		"sequence": 60,
	},
	{
		"question_key": "receives_partially",
		"label": "Do suppliers deliver one order in more than one go?",
		"section_title": "Buying",
		"sequence": 70,
		"applies_when": "keeps_stock == yes",
	},
	{
		"question_key": "manufactures",
		"label": "Do you make or assemble anything yourself?",
		"section_title": "Making",
		"sequence": 80,
	},
	{
		"question_key": "subcontracts",
		"label": "Does anyone make or finish goods for you?",
		"section_title": "Making",
		"sequence": 90,
	},
	{
		"question_key": "tracks_batches",
		"label": "Do you track batches or expiry dates?",
		"section_title": "Stock",
		"sequence": 100,
		"applies_when": "keeps_stock == yes",
	},
	{
		"question_key": "tracks_serials",
		"label": "Do you track serial numbers?",
		"section_title": "Stock",
		"sequence": 110,
		"applies_when": "keeps_stock == yes",
	},
	{
		"question_key": "stock_locations",
		"label": "How many places do you keep stock in?",
		"section_title": "Stock",
		"sequence": 120,
		"answer_type": "Number",
		"applies_when": "keeps_stock == yes",
		"allow_not_sure": 0,
	},
	{
		"question_key": "multi_currency",
		"label": "Do you buy or sell in another currency?",
		"section_title": "Money",
		"sequence": 130,
	},
	{
		"question_key": "tax_registered",
		"label": "Is your business registered for GST, VAT or similar?",
		"section_title": "Money",
		"sequence": 140,
	},
]


# Embark's desk side: a tile on the apps screen and a sidebar for its records.
# Both doctypes are v16-only, so a v15 site quietly skips them and reaches
# Embark through the apps screen entry in hooks.py.
DESK_SIDEBAR = "Embark"
SIDEBAR_ITEMS = [
	{"label": "Open Embark", "link_type": "URL", "url": "/embark", "icon": "rocket"},
	{"label": "Onboarding", "link_type": "DocType", "link_to": "Embark Onboarding", "icon": "list-checks"},
	{"label": "Uploads", "link_type": "DocType", "link_to": "Embark Upload", "icon": "upload"},
	{"label": "Data Steps", "link_type": "DocType", "link_to": "Embark Data Area", "icon": "layers"},
	{
		"label": "Interview Questions",
		"link_type": "DocType",
		"link_to": "Embark Question",
		"icon": "message-square",
	},
]


def after_install():
	seed()


def after_migrate():
	seed()


def seed():
	for question in QUESTIONS:
		if not frappe.db.exists("Embark Question", question["question_key"]):
			frappe.get_doc({"doctype": "Embark Question", **question}).insert(ignore_permissions=True)

	for area in AREAS:
		if not frappe.db.exists("Embark Data Area", area["area_name"]):
			frappe.get_doc({"doctype": "Embark Data Area", **area}).insert(ignore_permissions=True)
		else:
			_fill_blanks(area)

	_seed_desk()


def _seed_desk():
	"""The tile on the desk's apps screen, and the sidebar behind it."""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return

	if not frappe.db.exists("Workspace Sidebar", DESK_SIDEBAR):
		frappe.get_doc(
			{
				"doctype": "Workspace Sidebar",
				"title": DESK_SIDEBAR,
				"module": "Embark",
				"app": "embark",
				"header_icon": "rocket",
				"items": [{"type": "Link", **item} for item in SIDEBAR_ITEMS],
			}
		).insert(ignore_permissions=True)

	# Frappe builds this tile itself from `add_to_apps_screen`; this is the
	# fallback, and it keeps the same shape so both look the same.
	if not frappe.db.exists("Desktop Icon", "Embark"):
		frappe.get_doc(
			{
				"doctype": "Desktop Icon",
				"label": "Embark",
				"icon_type": "App",
				"link_type": "External",
				"link": "/embark",
				"app": "embark",
				"logo_url": "/assets/embark/embark-logo.svg",
			}
		).insert(ignore_permissions=True)


def _fill_blanks(area: dict):
	"""Areas seeded before a field existed get that field once.

	Only blanks are filled, so a consultant's own edits stay.
	"""
	doc = frappe.get_doc("Embark Data Area", area["area_name"])
	wanted = {f["fieldname"]: f.get("applies_when") for f in area["fields"]}
	changed = False
	if area.get("applies_when") and not doc.applies_when:
		doc.applies_when = area["applies_when"]
		changed = True
	if area.get("icon") and not doc.icon:
		doc.icon = area["icon"]
		changed = True
	for row in doc.fields:
		if wanted.get(row.fieldname) and not row.applies_when:
			row.applies_when = wanted[row.fieldname]
			changed = True
	if changed:
		doc.save(ignore_permissions=True)
