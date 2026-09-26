"""A chat that fills in the interview, and nothing else.

The assistant is a second way to answer the questions, for customers who would
rather describe their business than click through fifteen of them. It is off
until someone configures a provider, and Embark works exactly the same without
it.

What it can do is the whole of this file's tool list: read the open questions,
save answers, read the plan. It cannot invent a step, change the plan or write
anything to ERPNext — the plan is still generated from the answers by the same
rules, so it stays explainable and the same answers always give the same plan.
"""

from __future__ import annotations

import json

import frappe
import requests
from frappe import _

from embark import copilot
from embark.llm import looks_like_plumbing, recovered_calls

# A long conversation with a small model is still cheap; a runaway loop is not.
MAX_ROUNDS = 6
TIMEOUT = 60

SYSTEM_PROMPT = """You are Embark's assistant. Embark prepares a business's data before its ERPNext implementation.

Your one job is to fill in the interview: the short list of questions that decides which steps and settings that business needs. Work like this:

- Call open_questions to see what is still unanswered. Never invent a question or a choice.
- The customer may describe their business in a sentence. Map what they say onto the open questions and save it with save_answers, then tell them briefly what you recorded.
- Ask at most two questions at a time, in plain language, the way the questions are written. No jargon, no ERPNext terms.
- Save only what the customer has actually told you. Never guess an answer they have not given, and never answer a question on their behalf to move faster.
- If you are not sure what they meant, ask. Do not guess. "not_sure" is a valid answer where the question allows it.
- When everything is answered, call show_plan and tell them in two or three sentences what their implementation will involve.

Keep every reply short. You are talking to a business owner, not a consultant."""

TOOLS = [
	{
		"name": "open_questions",
		"description": "The interview questions that still need an answer, with the allowed choices.",
		"parameters": {"type": "object", "properties": {}},
	},
	{
		"name": "save_answers",
		"description": (
			"Save one or more answers. Keys are question keys from open_questions; values are "
			"choice values from that question. Several choices are comma separated."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"answers": {
					"type": "object",
					"description": 'For example {"keeps_stock": "yes", "business_type": "trading,retail"}',
					"additionalProperties": {"type": "string"},
				}
			},
			"required": ["answers"],
		},
	},
	{
		"name": "show_plan",
		"description": "The steps, settings, decisions and training the answers have produced so far.",
		"parameters": {"type": "object", "properties": {}},
	},
]


def studio_tools() -> list[dict]:
	"""The change-making tools, for whoever implements this site.

	The customer's chat fills in their interview. The implementer's chat also
	reaches Studio: the same builders, the same change set, proposed and applied
	from here rather than from a second screen.
	"""
	from embark.copilot_chat import TOOLS as STUDIO_TOOLS

	try:
		copilot._studio_user()
	except frappe.PermissionError:
		return []
	return STUDIO_TOOLS


def settings():
	return frappe.get_cached_doc("Embark Settings")


def model_name() -> str:
	"""Shown in the chat, so it is never a mystery what is answering."""
	return settings().model or "" if is_on() else ""


def is_on() -> bool:
	"""Is there a provider to talk to? If not, no chat is offered at all."""
	if not frappe.db.exists("DocType", "Embark Settings"):
		return False
	doc = settings()
	return bool(doc.assistant_enabled and doc.model and (doc.base_url or doc.provider == "Anthropic"))


def ask(onboarding: str, message: str, history: list[dict] | None = None) -> dict:
	"""One turn of the conversation, tools and all."""
	from embark import api

	if not is_on():
		frappe.throw(_("The chat assistant is not set up on this site."))

	messages = [
		{"role": "user", "content": m["content"]} if m["role"] == "user" else m for m in (history or [])
	]
	messages.append({"role": "user", "content": message})

	used: list[str] = []
	steps: list[dict] = []
	pending: list[dict] = []
	extra = studio_tools()
	for _round in range(MAX_ROUNDS):
		reply = _complete(messages, extra)
		calls = reply["tool_calls"] or recovered_calls(reply["text"])
		if not calls:
			text = reply["text"]
			if looks_like_plumbing(text):
				# Never show the machinery: say something true instead.
				text = _("Sorry, I did not follow that. Could you say it another way?")
			return _answer(onboarding, text, used, steps, pending, message)

		messages.append(reply["raw"])
		for call in calls:
			result = _run_tool(onboarding, call["name"], call["arguments"], pending)
			used.append(call["name"])
			steps.append(_step(call, result))
			messages.append(
				{
					"role": "tool",
					"tool_call_id": call["id"],
					"name": call["name"],
					"content": json.dumps(result, default=str)[:8000],
				}
			)

	return _answer(
		onboarding,
		_("That took longer than it should have. Could you try again, more simply?"),
		used,
		steps,
		pending,
		message,
	)


def _answer(onboarding, text, used, steps, pending, request) -> dict:
	"""What the chat sends back: words, what it did, and any change to apply."""
	from embark import api
	from embark.copilot_chat import _title

	change_set = copilot.propose(_title(request), request, pending) if pending else None
	return {
		"reply": text or _("Sorry, I did not follow that. Could you say it another way?"),
		"used": used,
		"steps": steps,
		"change_set": change_set,
		"overview": api.get_overview(onboarding),
	}


def _step(call: dict, result: dict) -> dict:
	from embark.copilot_chat import _step as studio_step

	return studio_step(call, result)


def _run_tool(onboarding: str, name: str, arguments: dict, pending: list[dict] | None = None) -> dict:
	"""Every tool goes through Embark's own API, so its rules still apply."""
	from embark import api

	if name == "open_questions":
		interview = api.get_interview(onboarding)
		return {
			"questions": [
				{
					"key": q["key"],
					"question": q["label"],
					"type": q["type"],
					"choices": [c["value"] for c in q["choices"]] or ["yes", "no"],
					"allow_not_sure": q["allow_not_sure"],
				}
				for q in interview["questions"]
				if not q["answer"]
			],
			"answered": interview["progress"]["answered"],
			"total": interview["progress"]["total"],
		}

	if name == "save_answers":
		try:
			overview = api.save_answers(onboarding, arguments.get("answers") or {})
		except frappe.ValidationError as e:
			# Hand the model its mistake so it can correct itself.
			return {"error": str(e)}
		return {"saved": True, "interview": overview["interview"]}

	if name == "show_plan":
		overview = api.get_overview(onboarding)
		return {
			"steps": [{"step": s["area"], "because": s["because"]} for s in overview["steps"]],
			"plan": [
				{"kind": line["kind"], "title": line["title"], "because": line["because"]}
				for line in overview["plan"]
			],
		}

	# Anything else is Studio's: the builders that compose a change set.
	if pending is not None and any(tool["name"] == name for tool in studio_tools()):
		from embark.copilot_chat import _run_tool as studio_run

		result, _change_set = studio_run(name, arguments, pending, "")
		return result

	return {"error": f"No such tool: {name}"}


def _complete(messages: list[dict], extra_tools: list[dict] | None = None) -> dict:
	"""One call to the provider, normalised to {text, tool_calls, raw}."""
	doc = settings()
	key = doc.get_password("api_key", raise_exception=False) or ""
	tools = [*TOOLS, *(extra_tools or [])]
	if doc.provider == "Anthropic":
		return _anthropic(doc, key, messages, tools)
	return _openai(doc, key, messages, tools)


def _openai(doc, key: str, messages: list[dict], tools: list[dict]) -> dict:
	body = {
		"model": doc.model,
		"messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
		"tools": [{"type": "function", "function": t} for t in tools],
		"temperature": 0,
	}
	data = _post(f"{doc.base_url.rstrip('/')}/chat/completions", body, {"Authorization": f"Bearer {key}"})
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


def _anthropic(doc, key: str, messages: list[dict], tools: list[dict]) -> dict:
	body = {
		"model": doc.model,
		"max_tokens": 1024,
		"system": SYSTEM_PROMPT,
		"messages": _to_anthropic(messages),
		"tools": [
			{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
			for t in tools
		],
	}
	url = f"{(doc.base_url or 'https://api.anthropic.com').rstrip('/')}/v1/messages"
	data = _post(url, body, {"x-api-key": key, "anthropic-version": "2023-06-01"})
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
	"""Tool results are user-role blocks in Anthropic's shape."""
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
		frappe.log_error(f"Embark assistant: {e}", "Embark assistant")
		frappe.throw(_("The assistant could not be reached. The questions below still work."))


def _loads(raw) -> dict:
	if isinstance(raw, dict):
		return raw
	try:
		return json.loads(raw or "{}")
	except ValueError:
		return {}
