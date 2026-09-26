"""The chat that composes change sets.

A consultant says what they want in a sentence; the model uses the builders in
``copilot`` to turn it into changes, and then writes them down as a Embark Change
Set. Nothing reaches the site from here: the set is a proposal until someone
presses Apply, and Apply can be undone.

The provider is configured in the bench's site config, so one setting serves
every app on the bench::

    "ai_provider": "OpenAI compatible",   # or "Anthropic"
    "ai_base_url": "http://localhost:11434/v1",
    "ai_model": "llama3.2:3b",
    "ai_api_key": "…"                     # a local model needs none
"""

from __future__ import annotations

import json

import frappe
import requests
from frappe import _

from embark import copilot
from embark.llm import looks_like_plumbing, recovered_calls

MAX_ROUNDS = 8
TIMEOUT = 120

# A screenshot of a form is worth a paragraph of description, but a chat is not
# a file upload: a few, and small.
MAX_IMAGES = 4
MAX_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_TYPES = ("image/png", "image/jpeg", "image/gif", "image/webp")

SYSTEM_PROMPT = """You are the Embark Studio copilot. You change an ERPNext site for a consultant, by proposing changes they then apply.

How to work:
- Look before you change: describe_doctype tells you what fields a form already has, and what to put a new field after.
- Build the change with add_field, set_property, create_report, create_workflow or create_client_script. Each call adds one change to the set you are composing; it does not touch the site.
- When the set is complete, call propose with a short title. The consultant reviews it and presses Apply. Say in one sentence what you proposed.
- You can only change fields, form properties, reports, workflows and client scripts. Anything else — invoices, stock, customers, users — is out of reach, and you should say so plainly rather than pretend.
- If the request is unclear, ask one question instead of guessing. A wrong change on a live site costs the consultant time.

Keep replies to two or three sentences."""

TOOLS = [
	{
		"name": "describe_doctype",
		"description": "The fields a form already has, so a new field can be placed and an existing one referred to.",
		"parameters": {
			"type": "object",
			"properties": {"doctype": {"type": "string"}},
			"required": ["doctype"],
		},
	},
	{
		"name": "add_field",
		"description": "Add a field to a form. Adds one change to the set being composed.",
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string"},
				"label": {"type": "string", "description": "The label on the form, for example: PO Number"},
				"fieldtype": {
					"type": "string",
					"description": (
						"Data for a name or code, Int or Currency for numbers, Date, Check for yes/no, "
						"Select for a fixed list, Link to another record, Text only when several lines "
						"are wanted. Default to Data."
					),
				},
				"options": {
					"type": "string",
					"description": "For Link, the doctype it points at. For Select, the choices, one per line.",
				},
				"insert_after": {"type": "string", "description": "An existing fieldname."},
				"reqd": {"type": "boolean"},
			},
			"required": ["doctype", "label"],
		},
	},
	{
		"name": "set_property",
		"description": "Change one thing about an existing field: label, reqd, hidden, read_only, default.",
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string"},
				"fieldname": {"type": "string"},
				"prop": {"type": "string"},
				"value": {"type": "string"},
			},
			"required": ["doctype", "fieldname", "prop", "value"],
		},
	},
	{
		"name": "create_report",
		"description": "A report from a single SELECT query.",
		"parameters": {
			"type": "object",
			"properties": {
				"title": {"type": "string"},
				"ref_doctype": {"type": "string"},
				"query": {
					"type": "string",
					"description": "A SELECT. Table names are like `tabSales Order`.",
				},
			},
			"required": ["title", "ref_doctype", "query"],
		},
	},
	{
		"name": "create_workflow",
		"description": (
			"A workflow: the states a document moves through and who may move it. "
			"States are [{state, role, doc_status}], transitions [{state, action, next_state, role}]. "
			"doc_status is 0 draft, 1 submitted, 2 cancelled."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string"},
				"title": {"type": "string", "description": "What the workflow is called."},
				"states": {"type": "array", "items": {"type": "object"}},
				"transitions": {"type": "array", "items": {"type": "object"}},
			},
			"required": ["doctype", "title", "states"],
		},
	},
	{
		"name": "create_client_script",
		"description": "A script that runs on a form, for example to set a field or show a message.",
		"parameters": {
			"type": "object",
			"properties": {
				"doctype": {"type": "string"},
				"script": {"type": "string", "description": "JavaScript, as in Client Script."},
				"view": {"type": "string", "description": "Form or List."},
			},
			"required": ["doctype", "script"],
		},
	},
	{
		"name": "propose",
		"description": "Write the composed changes down as a change set for the consultant to apply.",
		"parameters": {
			"type": "object",
			"properties": {"title": {"type": "string"}},
			"required": ["title"],
		},
	},
]


def config() -> dict:
	return {
		"provider": frappe.conf.get("ai_provider") or "OpenAI compatible",
		"base_url": frappe.conf.get("ai_base_url") or "",
		"model": frappe.conf.get("ai_model") or "",
		"api_key": frappe.conf.get("ai_api_key") or "",
	}


@frappe.whitelist()
def status() -> dict:
	# Studio's own status: what the customer runs is the onboarding chat, and
	# that has its own switch.
	copilot._studio_user()

	from embark import copilot_flow

	if copilot_flow.available():
		return {"on": True, "provider": "Flow engine", "model": copilot_flow.model_name()}

	settings = config()
	return {
		"on": bool(settings["model"] and (settings["base_url"] or settings["provider"] == "Anthropic")),
		"provider": settings["provider"],
		"model": settings["model"],
	}


@frappe.whitelist()
def chat(message: str, history: str | list | None = None, images: str | list | None = None) -> dict:
	"""One turn. Returns what to say, and the change set if one was proposed."""
	copilot._studio_user()

	# Where the site runs Frappe Flow, Flow runs the conversation: same tools,
	# same change set, one engine less of ours to keep.
	from embark import copilot_flow

	if copilot_flow.available():
		return copilot_flow.chat(message, frappe.parse_json(history) or [])

	if not status()["on"]:
		frappe.throw(_("No AI is configured on this bench yet."))

	messages = list(frappe.parse_json(history) or [])
	messages.append(_user_message(message, _check_images(images)))

	pending: list[dict] = []
	errors: list[str] = []
	# What it did, in order, so the consultant watches the work rather than a
	# spinner: each tool call, what it was asked, and what came back.
	steps: list[dict] = []
	request = message
	nudged = False
	for _round in range(MAX_ROUNDS):
		reply = _complete(messages)
		# A model that wrote its tool call into the message meant to make it.
		reply["tool_calls"] = reply["tool_calls"] or recovered_calls(reply["text"])
		if reply["tool_calls"]:
			reply["text"] = ""
		if not reply["tool_calls"] and not pending and not nudged:
			# A small model will sometimes describe the change instead of making
			# it. One nudge, then take it at its word.
			nudged = True
			messages.append(reply["raw"])
			messages.append(
				{
					"role": "user",
					"content": "Use the tools to make that change now. Do not describe it in words.",
				}
			)
			continue
		if not reply["tool_calls"]:
			# A model that built changes and then stopped talking still meant to
			# propose them; writing them down is what it was asked for.
			change_set = copilot.propose(_title(request), request, pending) if pending else None
			# A model will happily say it made a change that was refused. If
			# nothing came of the turn, the refusal is the honest answer.
			text = "" if looks_like_plumbing(reply["text"]) else reply["text"]
			if not change_set and errors:
				text = _("I could not do that: {0}").format(errors[-1])
			return {"reply": text, "change_set": change_set, "steps": steps, "pending": []}

		messages.append(reply["raw"])
		for call in reply["tool_calls"]:
			result, change_set = _run_tool(call["name"], call["arguments"], pending, request)
			steps.append(_step(call, result))
			if result.get("error"):
				errors.append(result["error"])
			messages.append(
				{
					"role": "tool",
					"tool_call_id": call["id"],
					"name": call["name"],
					"content": json.dumps(result, default=str)[:6000],
				}
			)
			if change_set:
				# One more round, so it can say what it did.
				closing = _complete(messages)
				return {
					"reply": closing["text"] or _("Proposed {0}.").format(change_set["title"]),
					"change_set": change_set,
					"steps": steps,
					"pending": [],
				}

	return {
		"reply": _("I could not work that out. Could you say it more simply?"),
		"change_set": None,
		"steps": steps,
	}


def _check_images(images: str | list | None) -> list[str]:
	"""Data URLs the page collected, checked before they go anywhere."""
	items = frappe.parse_json(images) if isinstance(images, str) else (images or [])
	if not items:
		return []
	if len(items) > MAX_IMAGES:
		frappe.throw(_("Up to {0} images at a time.").format(MAX_IMAGES))
	for url in items:
		if not isinstance(url, str) or not url.startswith("data:"):
			frappe.throw(_("That is not an image."))
		media_type = url[5 : url.find(";")]
		if media_type not in IMAGE_TYPES:
			frappe.throw(_("{0} is not an image type this reads.").format(media_type or "?"))
		if len(url) * 3 // 4 > MAX_IMAGE_BYTES:
			frappe.throw(
				_("That image is too big — {0} MB is the limit.").format(MAX_IMAGE_BYTES // 1024 // 1024)
			)
	return items


def _user_message(message: str, images: list[str]) -> dict:
	"""What the customer said, with any images beside it, in the provider's shape."""
	if not images:
		return {"role": "user", "content": message}

	if config()["provider"] == "Anthropic":
		blocks = [
			{
				"type": "image",
				"source": {
					"type": "base64",
					"media_type": url[5 : url.find(";")],
					"data": url.split(",", 1)[1],
				},
			}
			for url in images
		]
	else:
		blocks = [{"type": "image_url", "image_url": {"url": url}} for url in images]
	return {"role": "user", "content": [{"type": "text", "text": message}, *blocks]}


def _step(call: dict, result: dict) -> dict:
	"""One line of the work, with the detail folded away behind it."""
	added = result.get("added")
	if result.get("error"):
		outcome = result["error"]
	elif added:
		outcome = ", ".join(added) if isinstance(added, list) else str(added)
	elif result.get("proposed"):
		outcome = _("Written down as {0}").format(result["proposed"])
	else:
		outcome = _("Done")
	return {
		"tool": call["name"],
		"arguments": {k: v for k, v in (call.get("arguments") or {}).items() if v not in (None, "")},
		"outcome": outcome,
		"failed": bool(result.get("error")),
	}


def _title(request: str) -> str:
	"""A change set is named after what was asked for."""
	title = " ".join((request or "").split())[:80]
	return title or _("Change")


def _run_tool(name: str, arguments: dict, pending: list[dict], request: str):
	"""Builders add to the set being composed; propose writes it down."""
	try:
		if name == "describe_doctype":
			return _describe(arguments.get("doctype", "")), None

		if name == "add_field":
			change = copilot.add_field(
				doctype=arguments.get("doctype"),
				label=arguments.get("label"),
				fieldtype=arguments.get("fieldtype") or "Data",
				options=arguments.get("options"),
				insert_after=arguments.get("insert_after"),
				reqd=bool(arguments.get("reqd")),
			)
		elif name == "set_property":
			change = copilot.set_property(
				doctype=arguments.get("doctype"),
				fieldname=arguments.get("fieldname"),
				prop=arguments.get("prop"),
				value=arguments.get("value"),
			)
		elif name == "create_workflow":
			change = copilot.create_workflow(
				doctype=arguments.get("doctype"),
				title=arguments.get("title"),
				states=arguments.get("states"),
				transitions=arguments.get("transitions"),
			)
		elif name == "create_client_script":
			change = copilot.create_client_script(
				doctype=arguments.get("doctype"),
				script=arguments.get("script"),
				view=arguments.get("view") or "Form",
			)
		elif name == "create_report":
			change = copilot.create_report(
				title=arguments.get("title"),
				ref_doctype=arguments.get("ref_doctype"),
				query=arguments.get("query"),
			)
		elif name == "propose":
			if not pending:
				return {"error": "There is nothing to propose yet."}, None
			change_set = copilot.propose(arguments.get("title") or _("Change"), request, pending)
			return {"proposed": change_set["name"]}, change_set
		else:
			return {"error": f"No such tool: {name}"}, None
	except frappe.ValidationError as e:
		# Hand the model its mistake, in its own words, so it can correct itself.
		return {"error": str(e)}, None

	# A workflow needs its states and actions to exist first, so a builder may
	# hand back several changes at once — and a repeat is dropped.
	return {"added": copilot.add_change(pending, change)}, None


def _describe(doctype: str) -> dict:
	if not frappe.db.exists("DocType", doctype):
		return {"error": f"There is no doctype called {doctype}."}
	meta = frappe.get_meta(doctype)
	return {
		"doctype": doctype,
		"fields": [
			{"fieldname": f.fieldname, "label": f.label, "fieldtype": f.fieldtype, "options": f.options}
			for f in meta.fields
			if f.fieldtype not in ("Section Break", "Column Break", "Tab Break", "HTML")
		][:120],
	}


def _complete(messages: list[dict]) -> dict:
	settings = config()
	if settings["provider"] == "Anthropic":
		return _anthropic(settings, messages)
	return _openai(settings, messages)


def _openai(settings: dict, messages: list[dict]) -> dict:
	body = {
		"model": settings["model"],
		"messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
		"tools": [{"type": "function", "function": t} for t in TOOLS],
		"temperature": 0,
	}
	data = _post(
		f"{settings['base_url'].rstrip('/')}/chat/completions",
		body,
		{"Authorization": f"Bearer {settings['api_key'] or 'none'}"},
	)
	choice = (data.get("choices") or [{}])[0].get("message") or {}
	return {
		"text": choice.get("content") or "",
		"raw": choice,
		"tool_calls": [
			{
				"id": c.get("id"),
				"name": (c.get("function") or {}).get("name"),
				"arguments": _loads((c.get("function") or {}).get("arguments")),
			}
			for c in choice.get("tool_calls") or []
		],
	}


def _anthropic(settings: dict, messages: list[dict]) -> dict:
	body = {
		"model": settings["model"],
		"max_tokens": 2048,
		"system": SYSTEM_PROMPT,
		"messages": _to_anthropic(messages),
		"tools": [
			{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
			for t in TOOLS
		],
	}
	url = f"{(settings['base_url'] or 'https://api.anthropic.com').rstrip('/')}/v1/messages"
	data = _post(url, body, {"x-api-key": settings["api_key"], "anthropic-version": "2023-06-01"})
	blocks = data.get("content") or []
	return {
		"text": "".join(b.get("text", "") for b in blocks if b.get("type") == "text"),
		"raw": {"role": "assistant", "content": blocks},
		"tool_calls": [
			{"id": b.get("id"), "name": b.get("name"), "arguments": b.get("input") or {}}
			for b in blocks
			if b.get("type") == "tool_use"
		],
	}


def _to_anthropic(messages: list[dict]) -> list[dict]:
	out = []
	for m in messages:
		if m.get("role") == "tool":
			out.append(
				{
					"role": "user",
					"content": [
						{"type": "tool_result", "tool_use_id": m["tool_call_id"], "content": m["content"]}
					],
				}
			)
		else:
			out.append(m)
	return out


def _post(url: str, body: dict, headers: dict) -> dict:
	try:
		response = requests.post(
			url, json=body, headers={"Content-Type": "application/json", **headers}, timeout=TIMEOUT
		)
		response.raise_for_status()
		return response.json()
	except requests.RequestException as e:
		frappe.log_error(f"Embark Studio copilot: {e}", "Embark Studio copilot")
		frappe.throw(_("The AI could not be reached."))


def _loads(raw) -> dict:
	if isinstance(raw, dict):
		return raw
	try:
		return json.loads(raw or "{}")
	except ValueError:
		return {}
