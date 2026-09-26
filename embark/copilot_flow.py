"""Embark's copilot, run on Frappe Flow's engine when the site has it.

Flow is Frappe's own agent app: it manages providers and models, runs the
tool-calling loop, and keeps sessions. Where it is installed there is no reason
for Embark to run a second loop of its own — so it hands Flow the same
builders, and Flow drives them.

What does *not* change is the safety: Flow's tools here only compose changes.
Nothing touches the site until the change set is applied, and it can still be
undone in one go. Embark never gives Flow its own write tools, which can create
and delete records outright.

On a site without Flow, ``copilot_chat`` runs its own loop instead, and the two
behave the same from the panel.
"""

from __future__ import annotations

import frappe
from frappe import _

from embark import copilot
from embark.copilot_chat import MAX_ROUNDS, SYSTEM_PROMPT, _title


def available() -> bool:
	"""Flow installed, switched on for Embark, and a model for it to use.

	It is opt-in rather than automatic. Flow's loop is stricter than ours: it
	validates every tool argument and has no patience for a model that answers
	sloppily, so on a small local model it circles where ours gets there. With
	a capable model it is the better engine, so this is a switch, not a rule:

	    "embark_engine": "flow"     # in site config
	"""
	if frappe.conf.get("embark_engine") != "flow":
		return False
	if "flow" not in frappe.get_installed_apps():
		return False
	return bool(model_name())


def model_name() -> str | None:
	"""The Flow Model to run on: the one named in site config, else any enabled one."""
	wanted = frappe.conf.get("embark_flow_model")
	if wanted and frappe.db.exists("Flow Model", wanted):
		return wanted
	return frappe.db.get_value("Flow Model", {"enabled": 1}, "name", order_by="modified desc")


def chat(message: str, history: list[dict] | None = None) -> dict:
	"""One turn, run by Flow, composing a change set the consultant applies."""
	from flow import Agent, tool

	pending: list[dict] = []

	def describe_doctype(doctype: str) -> dict:
		"""The fields a form already has, so a new field can be placed correctly."""
		from embark.copilot_chat import _describe

		return _describe(doctype)

	def add_field(
		doctype: str,
		label: str,
		fieldtype: str = "Data",
		options: str = "",
		insert_after: str = "",
		reqd: bool = False,
	) -> str:
		"""Add a field to a form. Data for a name or code, Int or Currency for numbers,
		Date, Check for yes/no, Select for a fixed list, Link to another record."""
		return _compose(
			pending,
			copilot.add_field(
				doctype=doctype,
				label=label,
				fieldtype=fieldtype or "Data",
				options=options or None,
				insert_after=insert_after or None,
				reqd=reqd,
			),
		)

	def set_property(doctype: str, fieldname: str, prop: str, value: str) -> str:
		"""Change one thing about an existing field: label, reqd, hidden, read_only, default."""
		return _compose(pending, copilot.set_property(doctype, fieldname, prop, value))

	def create_report(title: str, ref_doctype: str, query: str) -> str:
		"""A report from a single SELECT query."""
		return _compose(pending, copilot.create_report(title, ref_doctype, query))

	def create_workflow(doctype: str, title: str, states: list, transitions: list | None = None) -> str:
		"""A workflow: states are [{state, role, doc_status}], transitions
		[{state, action, next_state, role}]."""
		return _compose(pending, copilot.create_workflow(doctype, title, states, transitions))

	def create_client_script(doctype: str, script: str, view: str = "Form") -> str:
		"""A script that runs on a form, for example to set a field or show a message."""
		return _compose(pending, copilot.create_client_script(doctype, script, view))

	agent = Agent(
		model=model_name(),
		name="embark-copilot",
		instructions=SYSTEM_PROMPT,
		tools=[
			tool(f)
			for f in (
				describe_doctype,
				add_field,
				set_property,
				create_report,
				create_workflow,
				create_client_script,
			)
		],
		# Nothing these tools do reaches the site, so there is nothing to approve
		# here: the change set is the approval.
		auto_approve=True,
		# A weak model will circle: ask, describe, ask again. Stop it early and
		# keep whatever it did compose.
		max_iterations=MAX_ROUNDS,
	)

	result, ran_out = None, False
	try:
		result = agent.run([*(history or []), {"role": "user", "content": message}])
	except RuntimeError:
		ran_out = True

	change_set = copilot.propose(_title(message), message, pending) if pending else None
	if change_set:
		reply = (result.output if result else "") or _("Proposed {0}.").format(change_set["title"])
	elif ran_out:
		reply = _("I went round in circles on that. Could you say it more plainly?")
	else:
		reply = result.output or ""
	return {
		"reply": reply,
		"change_set": change_set,
		"steps": _steps(result),
		"engine": "flow",
	}


def _compose(pending: list[dict], change) -> str:
	"""A builder's changes join the set being composed; its summary goes back."""
	changes = change if isinstance(change, list) else [change]
	pending.extend(changes)
	return "; ".join(c["summary"] for c in changes)


def _steps(result) -> list[dict]:
	"""Flow's tool calls, in the shape the panel already draws."""
	steps = []
	if result is None:
		return steps
	for call in getattr(result, "tool_calls", []) or []:
		steps.append(
			{
				"tool": getattr(call, "name", "") or getattr(call, "tool", ""),
				"arguments": getattr(call, "arguments", None) or getattr(call, "args", {}) or {},
				"outcome": str(getattr(call, "result", "") or _("Done"))[:300],
				"failed": bool(getattr(call, "error", None)),
			}
		)
	return steps
