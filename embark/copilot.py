"""The changes the copilot knows how to make, and the endpoints behind them.

Each builder turns a plain request ("add a PO number field to Sales Order")
into rows of a Embark Change Set. Nothing here writes to the site: the change set
does that, in one transaction, keeping a snapshot so it can be undone.

Everything a builder produces lands in the customisation layer — Custom Field,
Property Setter, Client Script, Report, Workflow — so a mistake costs a click
of Undo, never a customer's data.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from embark.embark.doctype.embark_change_set.embark_change_set import ALLOWED

FIELDTYPES = (
	"Data",
	"Int",
	"Float",
	"Currency",
	"Percent",
	"Check",
	"Select",
	"Link",
	"Date",
	"Datetime",
	"Time",
	"Text",
	"Small Text",
	"Long Text",
	"Text Editor",
	"Attach",
	"Attach Image",
)


# Studio changes a site's customisations, which is implementation work, not
# something the site's own users do. A System Manager is not enough: the
# customer is one of those on their own site.
STUDIO_ROLE = "Embark Studio"


def _studio_user():
	if frappe.session.user == "Administrator" or STUDIO_ROLE in frappe.get_roles():
		return
	frappe.throw(
		_("Embark Studio is for whoever implements this site, not for its users."),
		frappe.PermissionError,
	)


def add_field(
	doctype: str,
	label: str,
	fieldtype: str = "Data",
	options: str | None = None,
	insert_after: str | None = None,
	reqd: bool = False,
	fieldname: str | None = None,
) -> dict:
	"""A new field on an existing form, as a Custom Field."""
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("There is no doctype called {0}.").format(doctype))
	if fieldtype not in FIELDTYPES:
		frappe.throw(_("{0} is not a field type this can add.").format(fieldtype))
	if fieldtype == "Link" and not frappe.db.exists("DocType", options or ""):
		frappe.throw(_("A Link field needs the doctype it points at."))

	fieldname = fieldname or frappe.scrub(label)
	meta = frappe.get_meta(doctype)
	if meta.get_field(fieldname):
		frappe.throw(_("{0} already has a field called {1}.").format(doctype, fieldname))
	if insert_after:
		insert_after = _resolve(meta, insert_after)

	return {
		"action": "Create",
		"ref_doctype": "Custom Field",
		"ref_name": f"{doctype}-{fieldname}",
		"summary": _("Add {0} ({1}) to {2}").format(label, fieldtype, doctype),
		"payload": json.dumps(
			{
				"dt": doctype,
				"fieldname": fieldname,
				"label": label,
				"fieldtype": fieldtype,
				"options": options,
				"insert_after": insert_after or _last_field(meta),
				"reqd": 1 if reqd else 0,
			}
		),
	}


def set_property(doctype: str, fieldname: str, prop: str, value, property_type: str = "Data") -> dict:
	"""Change one thing about an existing field: its label, whether it is required, hidden."""
	meta = frappe.get_meta(doctype)
	if fieldname:
		fieldname = _resolve(meta, fieldname)

	name = f"{doctype}-{fieldname}-{prop}"
	payload = {
		"doctype_or_field": "DocField" if fieldname else "DocType",
		"doc_type": doctype,
		"field_name": fieldname,
		"property": prop,
		"value": value,
		"property_type": property_type,
	}
	if frappe.db.exists("Property Setter", name):
		return {
			"action": "Update",
			"ref_doctype": "Property Setter",
			"ref_name": name,
			"summary": _("Set {0} of {1} to {2}").format(prop, fieldname or doctype, value),
			"payload": json.dumps({"value": value}),
		}
	return {
		"action": "Create",
		"ref_doctype": "Property Setter",
		"ref_name": name,
		"summary": _("Set {0} of {1} to {2}").format(prop, fieldname or doctype, value),
		"payload": json.dumps(payload),
	}


def create_report(title: str, ref_doctype: str, query: str, is_standard: str = "No") -> dict:
	"""A Query Report: one SELECT, shown as a report in the desk."""
	if not frappe.db.exists("DocType", ref_doctype):
		frappe.throw(_("There is no doctype called {0}.").format(ref_doctype))
	stripped = (query or "").strip().lower()
	if not stripped.startswith("select"):
		frappe.throw(_("A report's query has to be a SELECT."))
	for word in ("insert", "update", "delete", "drop", "alter", "truncate", "grant"):
		if f" {word} " in f" {stripped} ":
			frappe.throw(_("A report's query cannot contain {0}.").format(word.upper()))

	return {
		"action": "Create",
		"ref_doctype": "Report",
		"ref_name": title,
		"summary": _("Report: {0}").format(title),
		"payload": json.dumps(
			{
				"report_name": title,
				"ref_doctype": ref_doctype,
				"report_type": "Query Report",
				"is_standard": is_standard,
				"query": query,
				"module": frappe.db.get_value("DocType", ref_doctype, "module"),
			}
		),
	}


def create_workflow(
	doctype: str,
	title: str,
	states: list | str,
	transitions: list | str | None = None,
	field: str = "workflow_state",
) -> dict:
	"""A workflow: the states a document moves through, and who may move it.

	``states`` is a list of {state, role, doc_status?}; ``transitions`` a list of
	{state, action, next_state, role}. Frappe creates the state field itself.
	"""
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("There is no doctype called {0}.").format(doctype))
	states = frappe.parse_json(states) if isinstance(states, str) else states
	transitions = frappe.parse_json(transitions) if isinstance(transitions, str) else (transitions or [])
	if not states:
		frappe.throw(_("A workflow needs at least one state."))
	if frappe.db.exists("Workflow", title):
		frappe.throw(_("There is already a workflow called {0}.").format(title))

	rows, seen_states, seen_actions = [], set(), set()
	for s in states:
		name = (s.get("state") or "").strip()
		role = (s.get("role") or "System Manager").strip()
		_check_role(role)
		if not name:
			frappe.throw(_("Every state needs a name."))
		seen_states.add(name)
	for tr in transitions:
		_check_role((tr.get("role") or "System Manager").strip())
		seen_states.update(filter(None, [tr.get("state"), tr.get("next_state")]))
		if tr.get("action"):
			seen_actions.add(tr["action"].strip())

	# The states and actions a workflow refers to have to exist first.
	for state in sorted(seen_states):
		if not frappe.db.exists("Workflow State", state):
			rows.append(
				{
					"action": "Create",
					"ref_doctype": "Workflow State",
					"ref_name": state,
					"summary": _("State: {0}").format(state),
					"payload": json.dumps({"workflow_state_name": state}),
				}
			)
	for action in sorted(seen_actions):
		if not frappe.db.exists("Workflow Action Master", action):
			rows.append(
				{
					"action": "Create",
					"ref_doctype": "Workflow Action Master",
					"ref_name": action,
					"summary": _("Action: {0}").format(action),
					"payload": json.dumps({"workflow_action_name": action}),
				}
			)

	rows.append(
		{
			"action": "Create",
			"ref_doctype": "Workflow",
			"ref_name": title,
			"summary": _("Workflow on {0}: {1}").format(
				doctype, " → ".join(s.get("state", "") for s in states)
			),
			"payload": json.dumps(
				{
					"workflow_name": title,
					"document_type": doctype,
					"workflow_state_field": field,
					"is_active": 1,
					"send_email_alert": 0,
					"states": [
						{
							"state": s.get("state"),
							"allow_edit": s.get("role") or "System Manager",
							"doc_status": str(s.get("doc_status", 0)),
						}
						for s in states
					],
					"transitions": [
						{
							"state": tr.get("state"),
							"action": tr.get("action"),
							"next_state": tr.get("next_state"),
							"allowed": tr.get("role") or "System Manager",
							"allow_self_approval": 1,
						}
						for tr in transitions
					],
				}
			),
		}
	)
	return rows if len(rows) > 1 else rows[0]


def create_client_script(doctype: str, script: str, view: str = "Form", name: str | None = None) -> dict:
	"""A Client Script: what happens on the form as someone fills it in."""
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("There is no doctype called {0}.").format(doctype))
	if view not in ("Form", "List"):
		frappe.throw(_("A client script runs on a Form or a List."))
	if not (script or "").strip():
		frappe.throw(_("The script is empty."))

	name = name or f"{doctype}-{frappe.scrub(view)}-copilot"
	return {
		"action": "Create",
		"ref_doctype": "Client Script",
		"ref_name": name,
		"summary": _("Client script on {0} ({1})").format(doctype, view),
		"payload": json.dumps({"name": name, "dt": doctype, "view": view, "enabled": 1, "script": script}),
	}


def _check_role(role: str) -> None:
	if not frappe.db.exists("Role", role):
		frappe.throw(_("There is no role called {0}.").format(role))


def _resolve(meta, field: str) -> str:
	"""Take a fieldname, or the label someone reads on the form."""
	if meta.get_field(field):
		return field
	folded = field.strip().lower()
	for df in meta.fields:
		if (df.label or "").strip().lower() == folded:
			return df.fieldname
	frappe.throw(
		_("{0} has no field called {1}. Use the fieldname, for example item_name.").format(meta.name, field)
	)


def _last_field(meta) -> str | None:
	fields = [f.fieldname for f in meta.fields if f.fieldtype not in ("Section Break", "Column Break")]
	return fields[-1] if fields else None


@frappe.whitelist()
def propose(title: str, request: str = "", changes: str | list | None = None) -> dict:
	"""Write a change set down. Nothing happens to the site until it is applied."""
	_studio_user()
	rows = frappe.parse_json(changes) or []
	# A builder hands back one change, or several when one implies others.
	if isinstance(rows, dict):
		rows = [rows]
	if not rows:
		frappe.throw(_("A change set needs at least one change."))

	doc = frappe.get_doc(
		{
			"doctype": "Embark Change Set",
			"title": title,
			"request": request,
			"changes": rows,
		}
	).insert(ignore_permissions=True)
	return _as_dict(doc)


@frappe.whitelist()
def apply(name: str) -> dict:
	_studio_user()
	doc = frappe.get_doc("Embark Change Set", name)
	doc.apply()
	return _as_dict(doc.reload())


@frappe.whitelist()
def undo(name: str) -> dict:
	_studio_user()
	doc = frappe.get_doc("Embark Change Set", name)
	doc.undo()
	return _as_dict(doc.reload())


@frappe.whitelist()
def history(limit: int = 20) -> list[dict]:
	_studio_user()
	return frappe.get_all(
		"Embark Change Set",
		fields=["name", "title", "status", "applied_at", "applied_by"],
		order_by="creation desc",
		limit=limit,
	)


def _as_dict(doc) -> dict:
	return {
		"name": doc.name,
		"title": doc.title,
		"status": doc.status,
		"request": doc.request,
		"error": doc.error,
		"changes": [
			{
				"action": row.action,
				"doctype": row.ref_doctype,
				"name": row.ref_name,
				"summary": row.summary,
			}
			for row in doc.changes
		],
		"allowed": list(ALLOWED),
	}
