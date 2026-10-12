"""A chat that runs the onboarding, for customers who would rather talk.

It is a second front door to the same screens, not a different product: every
tool below calls the very function the button calls, so the chat gets the same
validation, the same permissions and the same results. It cannot invent a step,
write the plan or push anything past its own errors.

What it can do is the job end to end — see where you are, ask the interview
questions, take a spreadsheet, say what is wrong with it in plain words, fix
values, type rows in, and (for whoever implements the site) create the records
in ERPNext.

It is off until someone configures a provider, and Embark works exactly the
same without it: the screens are the product, the chat is a way of driving them.
"""

from __future__ import annotations

import json
import re

import frappe
import requests
from frappe import _

from embark import copilot
from embark.llm import looks_like_plumbing, recovered_calls

# A long conversation with a small model is still cheap; a runaway loop is not.
MAX_ROUNDS = 6
# How many open questions the chat is shown at once.
QUESTIONS_AT_A_TIME = 4
TIMEOUT = 60

SYSTEM_PROMPT = """You are Embark's assistant. Embark gets a business's data ready before its ERPNext implementation, and you run that with them.

Call where_am_i before your first reply in a conversation. Always. It tells you what is done, what is next and what is wrong, so you can lead instead of asking them what they want.

While the interview is unanswered:
1. Call open_questions.
2. If what they just told you answers any of them, call save_answers with those answers in the same turn. Do this before you ask anything else.
3. Then ask at most two of the remaining questions, in plain language, the way they are written.
Save only what they actually said. Never guess an answer for them, never invent a question or a choice, and never answer on their behalf to move faster.

Once it is answered, the data steps are the work:
- step_help says what a step wants. They can send a spreadsheet, or tell you the rows and you enter them with type_rows.
- check_step after anything arrives, and say how it went like a person would: how many rows came through, and what is wrong in their words. Never say a code or a column name — "four customers have no GST number", not "4 REQUIRED_MISSING on tax_id".
- Offer to fix what you can see. fix corrects one row, or every row with the same wrong value. Say what you are about to change before you change it, and never invent a value they have not given you.
- match_column connects a heading in their file to the column it means, when it was not recognised.
- A step with problems cannot go through. Fix them, or say plainly what they have to do, then move to the next step.
- send_for_review when everything required is ready and they agree.

How to speak: short, plain, warm. You are talking to a business owner, not a consultant. No ERPNext jargon, no field names, no tool names, no JSON. One or two sentences, then the next question."""


def _area_arg(description: str) -> dict:
	return {"type": "string", "description": description}


# Every tool here is one of Embark's own screens, reachable by talking.
_CATALOGUE = [
	{
		"name": "where_am_i",
		"description": "Where this onboarding stands: the interview, every step with its state and problems, and what to do next. Start here.",
		"parameters": {"type": "object", "properties": {}},
	},
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
	{
		"name": "step_help",
		"description": "What one step is for, the columns it wants with an example of each, and where to get its template.",
		"parameters": {
			"type": "object",
			"properties": {"area": _area_arg("The step name, exactly as where_am_i gives it.")},
			"required": ["area"],
		},
	},
	{
		"name": "check_step",
		"description": "The sheet on one step as it stands: rows that came through, and every problem with examples.",
		"parameters": {
			"type": "object",
			"properties": {"area": _area_arg("The step name.")},
			"required": ["area"],
		},
	},
	{
		"name": "type_rows",
		"description": "Enter rows the customer dictated, instead of a spreadsheet. Replaces whatever is on that step.",
		"parameters": {
			"type": "object",
			"properties": {
				"area": _area_arg("The step name."),
				"rows": {
					"type": "array",
					"description": 'One object per row, keyed by the column names step_help gives. For example [{"warehouse_name": "Main Store"}]',
					"items": {"type": "object", "additionalProperties": {"type": "string"}},
				},
			},
			"required": ["area", "rows"],
		},
	},
	{
		"name": "fix",
		"description": "Correct a value on a step: one row, or every row holding the same wrong value. Say what you are changing first.",
		"parameters": {
			"type": "object",
			"properties": {
				"area": _area_arg("The step name."),
				"column": {"type": "string", "description": "The column to correct, as check_step names it."},
				"value": {"type": "string", "description": "What it should say."},
				"row": {"type": "integer", "description": "The row number, for a one-row fix."},
				"old_value": {
					"type": "string",
					"description": "The wrong value, to correct it everywhere it appears.",
				},
			},
			"required": ["area", "column", "value"],
		},
	},
	{
		"name": "match_column",
		"description": "Connect a heading in the customer's sheet to the column Embark wants, when it was not recognised.",
		"parameters": {
			"type": "object",
			"properties": {
				"area": _area_arg("The step name."),
				"heading": {"type": "string", "description": "The heading as it is written in their file."},
				"column": {"type": "string", "description": "The Embark column it means."},
			},
			"required": ["area", "heading", "column"],
		},
	},
	{
		"name": "use_file",
		"description": "Put a file the customer has just attached onto a step, when it was not obvious which step it belonged to.",
		"parameters": {
			"type": "object",
			"properties": {
				"area": _area_arg("The step name."),
				"file_url": {
					"type": "string",
					"description": "The file as where_am_i or the attachment note gives it.",
				},
			},
			"required": ["area", "file_url"],
		},
	},
	{
		"name": "remove_sheet",
		"description": "Take the sheet off a step, when the customer says they sent the wrong file.",
		"parameters": {
			"type": "object",
			"properties": {"area": _area_arg("The step name.")},
			"required": ["area"],
		},
	},
	{
		"name": "send_for_review",
		"description": "Send the finished data to the consultant. Only when every required step is ready and the customer agrees.",
		"parameters": {"type": "object", "properties": {}},
	},
]

TOOLS = {tool["name"]: tool for tool in _CATALOGUE}

# Only the tools that make sense right now are offered. A model given twelve
# choices picks worse than one given four — and so does a reader.
WHILE_ANSWERING = ("where_am_i", "open_questions", "save_answers", "show_plan")
WHILE_COLLECTING = (
	"where_am_i",
	"show_plan",
	"step_help",
	"check_step",
	"type_rows",
	"fix",
	"match_column",
	"use_file",
	"remove_sheet",
)

# For whoever implements the site, not for the customer.
STAFF_TOOLS = [
	{
		"name": "create_in_erpnext",
		"description": "Create the approved data as real records in ERPNext. Records already there are skipped.",
		"parameters": {"type": "object", "properties": {}},
	},
]


def tools_for(onboarding: str) -> list[dict]:
	"""The tools worth offering at this point in the onboarding.

	During the interview there is nothing to do but answer questions, so those
	are the only tools on the table. Once it is answered the data steps open
	up. Sending for review appears when there is something to send.
	"""
	from embark import api
	from embark.permissions import is_staff

	o = api.get_overview(onboarding)
	names = list(WHILE_ANSWERING if not o["interview"]["done"] else WHILE_COLLECTING)
	if o["can_submit"]:
		names.append("send_for_review")

	tools = [TOOLS[name] for name in names]
	if is_staff() and o["status"] == "Approved":
		tools += STAFF_TOOLS
	return tools


def staff_tools() -> list[dict]:
	"""What only the implementer may do. The customer's chat never sees these."""
	from embark.permissions import is_staff

	return STAFF_TOOLS if is_staff() else []


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


def read_answer(question, text: str) -> dict:
	"""Read a written answer into one of a question's choices.

	No tools, no conversation: one small judgement, returned as JSON. With no
	provider configured it returns nothing, and the words are kept as they are
	for the consultant to read.
	"""
	from embark.api import _choices

	choices = _choices(question) or [{"value": "yes", "label": "Yes"}, {"value": "no", "label": "No"}]
	allowed = [c["value"] for c in choices]
	if question.allow_not_sure:
		allowed.append("not_sure")
	if not is_on():
		return {}

	listed = "\n".join(f"- {c['value']}: {c['label']}" for c in choices)
	prompt = (
		f'Question: "{question.label}"\n'
		f"Choices:\n{listed}\n\n"
		f'The customer wrote: "{text}"\n\n'
		"Which choice does that mean? Answer with JSON only, no other words: "
		'{"value": "<one of ' + ", ".join(allowed) + '>", "why": "<six words or fewer>"}. '
		"If it truly does not say, use an empty value."
	)
	try:
		reply = _complete([{"role": "user", "content": prompt}], tools=[])
	except Exception:
		return {}

	data = _json_object(reply.get("text") or "")
	value = (data.get("value") or "").strip()
	# Several choices are allowed to come back comma separated.
	values = [v.strip() for v in value.split(",") if v.strip() in allowed]
	if not values:
		return {}
	if question.answer_type != "Several choices":
		values = values[:1]
	return {"value": ",".join(values), "why": (data.get("why") or "").strip()[:80]}


def _json_object(text: str) -> dict:
	"""The JSON in a reply, whatever it is wrapped in."""
	import re

	for candidate in (text, *re.findall(r"\{.*?\}", text or "", re.S)):
		try:
			data = json.loads(candidate)
		except ValueError:
			continue
		if isinstance(data, dict):
			return data
	return {}


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


def opening(onboarding: str) -> dict:
	"""The first thing the chat says, worked out here rather than asked of the model.

	A greeting that already knows where the customer is costs nothing, arrives
	instantly and is never wrong — and it means the chat leads the conversation
	instead of waiting to be asked.
	"""
	from embark import api

	o = api.get_overview(onboarding)
	nothing_yet = not o["interview"]["answered"]
	if o["locked"]:
		# Nothing here can change, and ask() refuses a locked onboarding, so the
		# chat says so rather than inviting a question it cannot answer.
		greeting = _("Your data is with your consultant now, so there is nothing left for us to change here.")
	elif nothing_yet:
		greeting = _(
			"Hello. I am Embark, and I will get {0} ready for ERPNext with you. "
			"Tell me what your business does, in your own words, and I will take it from there."
		).format(o["client_name"])
	else:
		greeting = _("Welcome back. {0}").format(_next_thing(o))

	return {"greeting": greeting, "suggestions": _suggestions(o, nothing_yet)}


def _suggestions(o: dict, nothing_yet: bool) -> list[str]:
	"""Three things worth saying next, from where this onboarding actually is."""
	if o["locked"]:
		return []
	if nothing_yet:
		return [
			_("We sell auto parts wholesale from two godowns."),
			_("We make furniture to order and buy the timber in."),
			_("We are a services firm \u2014 no stock at all."),
		]

	out = []
	if not o["interview"]["done"]:
		out.append(_("Ask me the rest of the questions"))
	broken = [s for s in o["steps"] if s["errors"]]
	if broken:
		out.append(_("What is wrong with my {0}?").format(broken[0]["area"]))
	empty = [s for s in o["steps"] if s["required"] and s["status"] == "Not Started"]
	if empty:
		out.append(_("What do you need for {0}?").format(empty[0]["area"]))
	if o["can_submit"]:
		out.append(_("Send my data to the consultant"))
	out.append(_("Where am I up to?"))
	return out[:3]


def ask(
	onboarding: str, message: str, history: list[dict] | None = None, file_url: str | None = None
) -> dict:
	"""One turn of the conversation, tools and all.

	Frappe Flow runs it wherever Flow can run: its tools are typed from their
	signatures and their arguments are validated before anything executes. The
	loop below is the fallback for a site without it, and a site pins this one
	with ``"embark_engine": "embark"``.
	"""
	from embark import api, assistant_flow

	if not is_on():
		frappe.throw(_("The chat assistant is not set up on this site."))

	if assistant_flow.available():
		return assistant_flow.ask(onboarding, message, history, file_url)

	messages = _conversation(history)
	asked = next((m["content"] for m in reversed(messages) if m["role"] == "assistant"), None)
	messages.append({"role": "user", "content": message})
	if file_url:
		messages.append({"role": "user", "content": _attached(onboarding, file_url)})

	used: list[str] = []
	steps: list[dict] = []
	pending: list[dict] = []
	tools = tools_for(onboarding) + studio_tools()
	nudged = False
	for _round in range(MAX_ROUNDS):
		reply = _complete(messages, tools)
		calls = reply["tool_calls"] or recovered_calls(reply["text"])
		if not calls:
			text = reply["text"]
			if looks_like_plumbing(text) and not nudged:
				# It tried to call a tool and made a mess of it. Ask once for
				# the call itself before giving up on the turn.
				nudged = True
				messages.append({"role": "assistant", "content": text})
				messages.append(
					{
						"role": "user",
						"content": (
							"Use the tool itself rather than writing the call out, and use only "
							"the question keys from open_questions."
						),
					}
				)
				continue
			if looks_like_plumbing(text):
				# Never show the machinery: say something true instead.
				text = _("Sorry, I did not follow that. Could you say it another way?")
			return _answer(onboarding, text, used, steps, pending, message, asked)

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
		asked,
	)


def _attached(onboarding: str, file_url: str) -> str:
	"""Put a file the customer dropped into the chat on the step it belongs to.

	The step is guessed from the file name, because that is what a person would
	do with a file called "customers final.xlsx". A guess that is not clear
	enough is not made: the chat is told to ask instead.
	"""
	from embark import api

	o = api.get_overview(onboarding)
	steps = [s["area"] for s in o["steps"]]
	match = _best_step(file_url.rsplit("/", 1)[-1], steps)
	if not match:
		return _(
			"[The customer attached {0}. Its step is not obvious — ask which of these it is for: "
			"{1} — then call use_file with that step and this file_url.]"
		).format(file_url, ", ".join(steps))

	result = _guarded(lambda: _summarise_upload(api.attach_file(onboarding, match, file_url), match))
	return _("[The customer attached {0}. It was put on {1}. Here is how it checked out: {2}]").format(
		file_url, match, json.dumps(result, default=str)[:4000]
	)


def _best_step(file_name: str, steps: list[str]) -> str | None:
	"""The step whose name the file name actually says. No near-enough guesses."""
	words = {w for w in re.split(r"[^a-z0-9]+", file_name.lower()) if len(w) > 2}
	scored = []
	for step in steps:
		wanted = {w for w in re.split(r"[^a-z0-9]+", step.lower()) if len(w) > 2}
		# "customer" in the file name should match the "Customers" step.
		hits = sum(1 for w in wanted if any(w.startswith(f) or f.startswith(w) for f in words))
		if hits:
			scored.append((hits / len(wanted), step))
	scored.sort(reverse=True)
	if not scored or scored[0][0] < 0.5:
		return None
	if len(scored) > 1 and scored[1][0] == scored[0][0]:
		return None  # two steps fit equally well: ask, do not pick one
	return scored[0][1]


def _answer(onboarding, text, used, steps, pending, request, asked=None) -> dict:
	"""What the chat sends back: words, what it did, and any change to apply."""
	from embark import api
	from embark.copilot_chat import _title

	# A turn that answered a question and forgot to write it down is the
	# common failure, and it leaves the customer repeating themselves. If
	# nothing was saved, read the same sentence again as one small judgement.
	# "Called save_answers" is not the same as "saved something": a model that
	# calls it with an empty object has still written nothing down.
	wrote_something = any(
		step["tool"] == "save_answers" and not step["failed"] and (step["arguments"].get("answers"))
		for step in steps
	)
	if not wrote_something:
		caught = _catch_up(onboarding, request, asked)
		if caught:
			api.save_answers(onboarding, caught)
			used.append("save_answers")
			steps.append(
				{
					"tool": "save_answers",
					"label": _("Saved {0} answers").format(len(caught))
					if len(caught) != 1
					else _("Saved your answer"),
					"arguments": {"answers": caught},
					"outcome": _("Done"),
					"failed": False,
				}
			)
			# Say what was written down. Reading between the lines is a guess,
			# and a guess the customer cannot see is a guess they cannot correct.
			text = (text or "").rstrip() + "\n\n" + _noted(onboarding, caught)

	change_set = copilot.propose(_title(request), request, pending) if pending else None
	return {
		"reply": text or _("Sorry, I did not follow that. Could you say it another way?"),
		"used": used,
		"steps": steps,
		"change_set": change_set,
		"overview": api.get_overview(onboarding),
	}


def _noted(onboarding: str, caught: dict) -> str:
	"""The answers just taken from what they said, in their own words."""
	from embark import api

	by_key = {q["key"]: q for q in api.get_interview(onboarding)["questions"]}
	lines = []
	for key, value in caught.items():
		question = by_key.get(key)
		if not question:
			continue
		labels = {c["value"]: c["label"] for c in question["choices"]}
		said = ", ".join(labels.get(v, v) for v in value.split(","))
		lines.append(f"· {question['label']} {said}")
	if not lines:
		return ""
	return _("I have put you down for this — tell me if any of it is wrong:") + "\n" + "\n".join(lines)


def _catch_up(onboarding: str, said: str, asked: str | None) -> dict:
	"""Map what the customer just said onto the questions still open.

	One call, no tools, JSON out — the task a small model does well, unlike
	orchestrating a dozen tools. Everything that comes back is checked against
	the real questions and their real choices before it is saved, and anything
	that is not plainly stated is dropped.
	"""
	if not (said or "").strip():
		return {}
	# Every open question, not the handful the chat is shown: one sentence can
	# answer several, and this is the only pass that will see it.
	from embark import api

	open_now = [
		{
			"key": q["key"],
			"question": q["label"],
			"type": q["type"],
			"choices": [c["value"] for c in q["choices"]] or ["yes", "no"],
			"allow_not_sure": q["allow_not_sure"],
		}
		for q in api.get_interview(onboarding)["questions"]
		if not q["answer"]
	]
	if not open_now:
		return {}

	listed = "\n".join(
		'- {0} ("{1}"): one of {2}'.format(q["key"], q["question"], ", ".join(q["choices"])) for q in open_now
	)
	prompt = (
		"These questions are open:\n"
		+ listed
		+ "\n\n"
		+ (f'The assistant had just asked: "{asked}"\n' if asked else "")
		+ f'The customer replied: "{said}"\n\n'
		"Which of those questions does that reply answer? Answer with JSON only, no other words: "
		'{"<question key>": "<one of its choices>"}. Several choices for one question are comma '
		"separated, and only for choices the reply actually names.\n"
		"Be strict. Include a question only if the reply says its answer outright. Do not work it "
		"out from the kind of business they are, do not fill in what is likely, and do not answer a "
		"question the reply does not mention at all. Leaving a question out is always safe; "
		"inventing an answer is not. If it answers none of them, return {}."
	)
	try:
		reply = _complete([{"role": "user", "content": prompt}], tools=[])
	except Exception:
		return {}

	return _real_answers(_json_object(reply.get("text") or ""), open_now)


def _real_answers(data: dict, open_now: list[dict]) -> dict:
	"""Only question keys that exist, and only choices those questions allow."""
	by_key = {q["key"]: q for q in open_now}
	out = {}
	for key, value in (data or {}).items():
		question = by_key.get(key)
		if not question or not isinstance(value, str):
			continue
		allowed = set(question["choices"]) | ({"not_sure"} if question["allow_not_sure"] else set())
		chosen = [v.strip() for v in value.split(",") if v.strip() in allowed]
		if question["type"] == "Number":
			chosen = [value.strip()] if value.strip().isdigit() else []
		elif question["type"] != "Several choices":
			chosen = chosen[:1]
		if chosen:
			out[key] = ",".join(chosen)
	return out


def _step(call: dict, result: dict) -> dict:
	from embark.copilot_chat import _step as studio_step

	step = studio_step(call, result)
	# The panel shows this line. Nobody should ever read a tool name.
	step["label"] = _label(call, result) or step["tool"].replace("_", " ").capitalize()
	return step


def _label(call: dict, result: dict) -> str:
	"""What just happened, said the way a person would say it."""
	args = call.get("arguments") or {}
	area = args.get("area") or ""
	if result.get("error"):
		# The reason is for the model, which will correct itself and say
		# something useful. The customer gets the line, not the machinery.
		return _("That did not work, so I carried on")

	return {
		"where_am_i": _("Checked where you are"),
		"open_questions": _("Looked at what is still unanswered"),
		"save_answers": _("Saved {0}").format(
			_("{0} answers").format(len(args.get("answers") or {}))
			if len(args.get("answers") or {}) != 1
			else _("your answer")
		),
		"show_plan": _("Read your plan"),
		"step_help": _("Looked up what {0} needs").format(area),
		"check_step": _("Checked your {0}").format(area),
		"type_rows": _("Entered {0} rows in {1}").format(len(args.get("rows") or []), area),
		"fix": _("Changed {0} to \u201c{1}\u201d in {2}").format(
			args.get("column") or "", args.get("value") or "", area
		),
		"match_column": _("Matched \u201c{0}\u201d to {1}").format(
			args.get("heading") or "", args.get("column") or ""
		),
		"use_file": _("Put your file on {0}").format(area),
		"remove_sheet": _("Took the sheet off {0}").format(area),
		"send_for_review": _("Sent your data to the consultant"),
		"create_in_erpnext": _("Created the records in ERPNext"),
	}.get(call["name"], "")


def _conversation(history: list[dict] | None) -> list[dict]:
	"""Only what was actually said, in the shape a provider accepts.

	The panel also draws tool steps and change sets; they are not conversation,
	and one message without content is enough for a provider to reject the
	whole request.
	"""
	out = []
	for m in history or []:
		role, content = m.get("role"), m.get("content")
		if role in ("user", "assistant") and isinstance(content, str) and content.strip():
			out.append({"role": role, "content": content})
	return out


def _run_tool(onboarding: str, name: str, arguments: dict, pending: list[dict] | None = None) -> dict:
	"""Every tool goes through Embark's own API, so its rules still apply."""
	from embark import api

	area = (arguments.get("area") or "").strip()

	if name == "where_am_i":
		return _where_am_i(onboarding)

	if name == "open_questions":
		interview = api.get_interview(onboarding)
		open_now = [
			{
				"key": q["key"],
				"question": q["label"],
				"type": q["type"],
				"choices": [c["value"] for c in q["choices"]] or ["yes", "no"],
				"allow_not_sure": q["allow_not_sure"],
			}
			for q in interview["questions"]
			if not q["answer"]
		]
		return {
			# A handful at a time: a long list invites a long reply, and the
			# customer is answering a conversation, not a form.
			"questions": open_now[:QUESTIONS_AT_A_TIME],
			"still_to_come": max(len(open_now) - QUESTIONS_AT_A_TIME, 0),
			"answered": interview["progress"]["answered"],
			"total": interview["progress"]["total"],
		}

	if name == "save_answers":
		if not arguments.get("answers"):
			# An empty save is the model going through the motions. Say so,
			# rather than letting it count as having written something down.
			return {"error": _("No answers in that call. Give the question key and the choice.")}
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

	if name == "step_help":
		return _step_help(onboarding, area)

	if name == "check_step":
		return _check_step(onboarding, area)

	if name == "type_rows":
		return _guarded(lambda: _rows_in(onboarding, area, arguments.get("rows") or []))

	if name == "fix":
		return _guarded(
			lambda: _summarise_upload(
				api.fix_value(
					onboarding,
					area,
					fieldname=arguments.get("column"),
					value=arguments.get("value"),
					row=arguments.get("row"),
					old_value=arguments.get("old_value"),
				),
				area,
			)
		)

	if name == "match_column":
		return _guarded(
			lambda: _summarise_upload(
				api.set_column(onboarding, area, arguments.get("heading"), arguments.get("column")), area
			)
		)

	if name == "use_file":
		return _guarded(
			lambda: _summarise_upload(api.attach_file(onboarding, area, arguments.get("file_url")), area)
		)

	if name == "remove_sheet":
		return _guarded(
			lambda: {"removed": True, **_summarise_upload(api.remove_file(onboarding, area), area)}
		)

	if name == "send_for_review":
		return _guarded(lambda: {"sent": True, "status": api.submit_for_review(onboarding)["status"]})

	if name == "create_in_erpnext" and staff_tools():
		return _guarded(lambda: api.create_in_erpnext(onboarding)["summary"])

	# Anything else is Studio's: the builders that compose a change set.
	if pending is not None and any(tool["name"] == name for tool in studio_tools()):
		from embark.copilot_chat import _run_tool as studio_run

		result, _change_set = studio_run(name, arguments, pending, "")
		return result

	return {"error": f"No such tool: {name}"}


def _guarded(work) -> dict:
	"""Embark's own refusals are answers, not crashes: hand them to the model."""
	try:
		return work()
	except frappe.ValidationError as e:
		return {"error": frappe.utils.strip_html(str(e))[:300]}
	except frappe.PermissionError:
		return {"error": _("You are not allowed to do that on this onboarding.")}


def _where_am_i(onboarding: str) -> dict:
	"""The whole board in one call, so the chat can lead instead of asking."""
	from embark import api

	o = api.get_overview(onboarding)
	steps = [
		{
			"step": s["area"],
			"needed_because": s["because"],
			"required": s["required"],
			"state": s["status"],
			"rows": s["rows"],
			"problems": s["errors"],
		}
		for s in o["steps"]
	]
	ready = [s for s in steps if s["state"] == "Ready"]
	return {
		"customer": o["client_name"],
		"status": o["status"],
		"locked": o["locked"],
		"interview": o["interview"],
		"readiness_percent": o["readiness"],
		"steps": steps,
		"steps_ready": f"{len(ready)} of {len(steps)}",
		"next": _next_thing(o),
		"can_send_for_review": o["can_submit"],
	}


def _next_thing(o: dict) -> str:
	"""The one thing worth doing now, in the words the chat should use."""
	if o["locked"]:
		return _("Nothing: the data has been sent to the consultant.")
	if not o["interview"]["done"]:
		return _("Finish the questions — {0} of {1} answered.").format(
			o["interview"]["answered"], o["interview"]["total"]
		)
	if not o["company_complete"]:
		return _("Fill in the company details.")
	broken = [s for s in o["steps"] if s["errors"]]
	if broken:
		return _("Fix {0} in {1}.").format(
			_("{0} problems").format(broken[0]["errors"]) if broken[0]["errors"] > 1 else _("1 problem"),
			broken[0]["area"],
		)
	empty = [s for s in o["steps"] if s["required"] and s["status"] == "Not Started"]
	if empty:
		return _("Get the {0} in — nothing has been sent for that step yet.").format(empty[0]["area"])
	if o["can_submit"]:
		return _("Everything required is ready. Send it to the consultant.")
	return _("Finish the steps that are not ready yet.")


def _step_help(onboarding: str, area: str) -> dict:
	from embark import api

	data = _guarded(lambda: api.get_area(onboarding, area))
	if "error" in data:
		return data
	return {
		"step": data["area"]["name"],
		"what_it_is": data["area"]["description"],
		"how_to_fill": data["area"]["help_text"],
		"required": data["area"]["required"],
		"columns": [
			{
				"column": c["fieldname"],
				"called": c["label"],
				"must_have": c["required"],
				"example": c["example"],
				"choices": c["choices"][:20] or None,
			}
			for c in data["columns"]
		],
		"template": f"/api/method/embark.api.download_template?area={area}",
		"sheet": _sheet_state(data),
	}


def _check_step(onboarding: str, area: str) -> dict:
	from embark import api

	data = _guarded(lambda: api.get_area(onboarding, area))
	return data if "error" in data else _summarise_upload(data, area)


def _summarise_upload(data: dict, area: str) -> dict:
	"""A sheet as a person would describe it: what came through, what is wrong."""
	upload = data.get("upload")
	if not upload:
		return {"step": area, "sheet": None, "note": _("Nothing has been sent for this step yet.")}

	rows_by_group: dict[tuple, list] = {}
	for issue in upload["issues"]:
		rows_by_group.setdefault((issue["code"], issue["fieldname"]), []).append(issue)

	return {
		"step": area,
		"file": upload["file_name"],
		"rows": upload["rows"],
		"problems": upload["errors"],
		"warnings": upload["warnings"],
		"state": _("Ready") if not upload["errors"] else _("Needs fixing"),
		"unrecognised_headings": [h["header"] for h in upload["headers"] if not h["fieldname"]],
		"what_is_wrong": [
			{
				"column": group["fieldname"],
				"called": group["label"],
				"problem": group["title"],
				"how_many": group["count"],
				"how_to_fix": group["hint"],
				# The same wrong value in forty rows is one fix, not forty.
				"wrong_values": [v["value"] for v in group["values"][:8]],
				"example_rows": [
					{"row": i["row"], "value": i["value"], "suggestions": i.get("suggestions")}
					for i in rows_by_group.get((group["code"], group["fieldname"]), [])[:5]
				],
			}
			for group in upload["groups"]
		],
	}


def _sheet_state(data: dict) -> dict | None:
	upload = data.get("upload")
	if not upload:
		return None
	return {"file": upload["file_name"], "rows": upload["rows"], "problems": upload["errors"]}


def _rows_in(onboarding: str, area: str, rows: list) -> dict:
	from embark import api

	clean = [r for r in rows if isinstance(r, dict) and any(str(v).strip() for v in r.values())]
	if not clean:
		return {"error": _("No rows to enter.")}
	return _summarise_upload(api.enter_rows(onboarding, area, clean), area)


def _complete(messages: list[dict], tools: list[dict] | None = None) -> dict:
	"""One call to the provider, normalised to {text, tool_calls, raw}."""
	doc = settings()
	key = doc.get_password("api_key", raise_exception=False) or ""
	tools = tools if tools is not None else list(TOOLS.values())
	if doc.provider == "Anthropic":
		return _anthropic(doc, key, messages, tools)
	return _openai(doc, key, messages, tools)


def _openai(doc, key: str, messages: list[dict], tools: list[dict]) -> dict:
	body = {
		"model": doc.model,
		"messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
		"temperature": 0,
	}
	if tools:
		body["tools"] = [{"type": "function", "function": t} for t in tools]
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
	}
	if tools:
		body["tools"] = [
			{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
			for t in tools
		]
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
		frappe.throw(_unreachable(e))


def _unreachable(error: Exception) -> str:
	"""Why the model could not be reached, said usefully to whoever can fix it.

	A customer gets a sentence that tells them the rest still works. Whoever
	set the provider up gets the provider's own words, because "could not be
	reached" is the same message whether the key is wrong, the address is wrong
	or the model name simply does not exist on the other end.
	"""
	from embark.permissions import is_staff

	plain = _("The assistant could not be reached. The questions below still work.")
	if not is_staff():
		return plain

	doc = settings()
	reason = frappe.utils.strip_html(str(error))
	# A provider's 404 body names the model it could not find; that is the whole
	# answer, and it is lost if only the status code survives.
	body = getattr(getattr(error, "response", None), "text", "") or ""
	if body and body[:400] not in reason:
		reason = f"{reason} — {body[:400]}"
	return _("{0}\n\n{1} at {2} said: {3}").format(
		plain, doc.model or _("the model"), doc.base_url or doc.provider, reason[:500]
	)


def _loads(raw) -> dict:
	if isinstance(raw, dict):
		return raw
	try:
		return json.loads(raw or "{}")
	except ValueError:
		return {}
