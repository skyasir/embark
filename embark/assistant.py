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

SYSTEM_PROMPT = """You are Embark. You set up ERPNext for a business by asking them about it, and you do the work yourself rather than telling them where to click.

You are told where things stand before every message. Never ask the customer where they are, what stage they are at, or what they would like to do — you already know, and asking it back is the one thing that makes you useless.

The setup questions are the work. Each one fills a real field in ERPNext.
1. If what they just said answers any open question, call answer_setup with it, in the same turn, before anything else.
2. Then ask the next open question, in the words it is written in. Exactly one.

Never list questions. Not numbered, not bulleted, not "here are the next few".
One question, by itself, is the whole of your reply after any answer you saved.
If they greet you, greet them back in one line and ask that one question.
3. Save only what they actually said. Never guess, never invent a question or a choice, never answer for them.
4. When every question in a step is answered, offer to build it, and call build_in_erpnext when they agree. Then say what it made.

If they ask something open — what is next, where are we, what is left — answer it from what you were told and ask the next question. Do not call a tool to find out what you already know.

Spreadsheets of their own data are a separate job: step_help says what a step wants, check_step says how it went, fix corrects a row. Only reach for these when they are sending you data, not during setup.

How to speak: short, plain, warm. You are talking to a business owner, not a consultant. No ERPNext jargon, no field names, no tool names, no JSON. Two or three sentences at the very most, then the one question. A long reply is a wrong reply."""


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
		"name": "open_setup_questions",
		"description": (
			"The setup questions still to answer, with the key to answer each by. "
			"These are what actually configures ERPNext. Read them before asking anything."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"limit": {"type": "integer", "description": "How many to return. Six is usually plenty."}
			},
		},
	},
	{
		"name": "answer_setup",
		"description": (
			"Save answers to setup questions. Use the key exactly as open_setup_questions gave it. "
			"Save only what they actually said."
		),
		"parameters": {
			"type": "object",
			"properties": {
				"answers": {
					"type": "object",
					"description": 'Key to answer, for example {"company_name": "Sunrise Traders Pvt Ltd"}.',
					"additionalProperties": {"type": "string"},
				}
			},
			"required": ["answers"],
		},
	},
	{
		"name": "build_in_erpnext",
		"description": (
			"Write a finished setup step into ERPNext. Only a step whose questions are all "
			"answered can be built. Say what it made afterwards."
		),
		"parameters": {
			"type": "object",
			"properties": {"step": {"type": "string", "description": "The step's name, as given to you."}},
			"required": ["step"],
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
# Four at a time, deliberately. A small model given a dozen tools picks none.
WHILE_SETTING_UP = ("open_setup_questions", "answer_setup", "build_in_erpnext", "where_am_i")
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
	# Setup comes first and is most of the work, so while any of it is open
	# those are the tools. Only then do the data steps get a look in.
	try:
		unfinished = _setup_questions(onboarding, 1)["left"]
	except Exception:
		unfinished = 0
	if unfinished:
		names = list(WHILE_SETTING_UP)
	else:
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
	elif not o["company_complete"]:
		greeting = _(
			"Hello. I am Embark, and I will get {0} ready for ERPNext with you. "
			"Start with the company details — the name, country, currency and financial year — "
			"and then tell me what the business does."
		).format(o["client_name"])
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
	if not o["company_complete"]:
		out.append(_("What company details do you need?"))
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


def draw(reply: str) -> str:
	"""Turn a finished reply into something to show, rather than read.

	A second pass, with no tools and nothing else to think about. The first
	pass is a conversation: it decides what to do, calls what it needs and says
	what happened. Asking it to do that *and* answer in a drawing language at
	the same time is two jobs, and a small model does neither well — it ignored
	the drawing rules entirely while tools were on the table. So the drawing is
	its own call, the way reading an answer back already is.

	It returns "" the moment anything is off, and the words are shown instead.
	"""
	instructions = getattr(frappe.local, "embark_ui_prompt", "")
	if not instructions or not (reply or "").strip():
		return ""
	try:
		out = _complete(
			[
				{"role": "system", "content": instructions},
				{
					"role": "user",
					"content": (
						"Write this answer as a program, following the rules above. "
						"Keep the meaning and the wording; add nothing.\n\n" + reply
					),
				},
			],
			tools=[],
		)
	except Exception:
		return ""

	text = (out.get("text") or "").strip()
	# A fenced block is the one thing it still does now and then.
	if text.startswith("```"):
		text = text.strip("`").split("\n", 1)[-1].rsplit("```", 1)[0].strip()
	return text if _ROOT.search(text) else ""


def draw_stream(reply: str):
	"""The drawing pass, a piece at a time.

	OpenUI re-parses on every chunk, so a program arriving in pieces draws
	itself: the shell first, then each part as its line lands. That is the
	whole reason to stream — not to watch words appear, but to watch the
	answer assemble.

	Yields the text as it comes. A provider that cannot stream, or a reply
	that turns out not to be a program, yields nothing and the caller falls
	back to the finished text.
	"""
	instructions = getattr(frappe.local, "embark_ui_prompt", "")
	if not instructions or not (reply or "").strip():
		return

	doc = settings()
	if doc.provider == "Anthropic" or not doc.base_url:
		# One shape at a time: the OpenAI-compatible endpoint covers Ollama,
		# Groq, OpenAI and Google. Anthropic draws in one go, as before.
		drawn = draw(reply)
		if drawn:
			yield drawn
		return

	key = doc.get_password("api_key", raise_exception=False) or ""
	body = {
		"model": doc.model,
		"messages": [
			{"role": "system", "content": instructions},
			{
				"role": "user",
				"content": (
					"Write this answer as a program, following the rules above. "
					"Keep the meaning and the wording; add nothing.\n\n" + reply
				),
			},
		],
		"temperature": 0,
		"stream": True,
	}
	try:
		with requests.post(
			f"{doc.base_url.rstrip('/')}/chat/completions",
			json=body,
			headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
			stream=True,
			timeout=TIMEOUT,
		) as response:
			response.raise_for_status()
			for line in response.iter_lines(decode_unicode=True):
				if not line or not line.startswith("data:"):
					continue
				chunk = line[5:].strip()
				if chunk == "[DONE]":
					return
				try:
					delta = json.loads(chunk)["choices"][0].get("delta") or {}
				except (ValueError, KeyError, IndexError):
					continue
				if delta.get("content"):
					yield delta["content"]
	except requests.RequestException as e:
		frappe.log_error(f"Embark assistant (drawing): {e}", "Embark assistant")
		return


# What a drawn answer has to start with, whatever else is around it.
_ROOT = re.compile(r"\broot\s*=\s*[A-Z]\w*\s*\(")


def _setup_questions(onboarding: str, limit: int = 6, with_links: bool = False) -> dict:
	"""The setup questions still open, with what each one accepts."""
	from embark import wizard

	board = wizard.board(frappe.get_doc("Embark Onboarding", onboarding))
	# Stage order, not sequence order: the wizard asks who the company is
	# first and the chat has to agree with it, or the two are asking different
	# things at the same time.
	stages = {stage["key"]: n for n, stage in enumerate(board["stages"])}
	tasks = sorted(board["tasks"], key=lambda t: (stages.get(t["stage"], 99), t.get("sequence", 0)))
	open_now = []
	for task in tasks:
		for q in task["questions"]:
			if q["answer"]:
				continue
			one = {
				"key": q["key"],
				"question": q["label"],
				"step": task["title"],
				"type": q["type"],
				"choices": [c["value"] for c in q["choices"]][:12],
				"example": q["example"],
			}
			if with_links and q["type"] == "Link":
				one["link_doctype"] = q["link_doctype"]
			open_now.append(one)
	return {
		"questions": open_now[:limit],
		"answered": board["answered"],
		"total": board["total"],
		"left": len(open_now),
	}


def standing(onboarding: str) -> str:
	"""Where this onboarding stands, in a line, given before it is asked for.

	The chat used to have to call a tool to find out, and a small model would
	rather ask the customer than call anything — so it answered "could you
	tell me where you are?" to someone who had opened it to be told. Handing
	it the state removes the question.
	"""
	try:
		state = _setup_questions(onboarding, 1)
	except Exception:
		return ""
	if not state["left"]:
		return "Every setup question is answered. What is left is building the steps in ERPNext."
	# One. Handing over three was an invitation to recite all three, and a
	# customer who says hello gets a wall of questions back.
	nxt = state["questions"][0]
	return (
		f"Where this stands: {state['answered']} of {state['total']} setup questions answered, "
		f"{state['left']} still open. The one to ask next is {nxt['key']}: \"{nxt['question']}\". "
		"Ask only that one."
	)


def _system() -> str:
	"""The system prompt, plus whatever the screen asked for this turn.

	Ask Embark can answer by drawing Embark's own controls rather than
	describing them. The list of what it may draw is generated in the browser
	from the component library itself, so a component added there is one the
	model is told about here, with no second copy to keep in step.
	"""
	extra = getattr(frappe.local, "embark_ui_prompt", "")
	return f"{SYSTEM_PROMPT}\n\n{extra}" if extra else SYSTEM_PROMPT


def open_question_keys(onboarding: str, limit: int = 14) -> str:
	"""The setup questions still open, so a drawn question can name a real one."""
	from embark import wizard

	try:
		board = wizard.board(frappe.get_doc("Embark Onboarding", onboarding))
	except Exception:
		return ""
	rows = [
		f"{q['key']}: {q['label']}"
		for task in board["tasks"]
		for q in task["questions"]
		if not q["answer"]
	][:limit]
	if not rows:
		return ""
	return "The setup questions still open, as key: question — use the key exactly:\n" + "\n".join(rows)


def ask(
	onboarding: str,
	message: str,
	history: list[dict] | None = None,
	file_url: str | None = None,
	ui_prompt: str | None = None,
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

	if ui_prompt:
		open_now = open_question_keys(onboarding)
		frappe.local.embark_ui_prompt = f"{ui_prompt}\n\n{open_now}" if open_now else ui_prompt

	if assistant_flow.available():
		return assistant_flow.ask(onboarding, message, history, file_url)

	messages = _conversation(history)
	asked = next((m["content"] for m in reversed(messages) if m["role"] == "assistant"), None)
	# Where things stand, handed over rather than looked up.
	here = standing(onboarding)
	if here:
		messages.append({"role": "system", "content": here})
	messages.append({"role": "user", "content": message})
	if file_url:
		messages.append({"role": "user", "content": _attached(onboarding, file_url)})

	used: list[str] = []
	steps: list[dict] = []
	pending: list[dict] = []
	tools = tools_for(onboarding)
	if not any(t["name"] == "answer_setup" for t in tools):
		tools += studio_tools()
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


def question_labels(answers: dict) -> list[tuple[str, str]]:
	"""Each saved answer as the question it answered, for saying so out loud."""
	out = []
	for key, value in (answers or {}).items():
		label = frappe.db.get_value("Embark Wizard Question", key, "label") or key
		out.append((label.rstrip("?"), value))
	return out


LIST_LINE = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s+", re.MULTILINE)


def one_question(onboarding: str, reply: str) -> str:
	"""Cut a recited list back to one question.

	Telling a model to ask one thing at a time gets you one thing at a time
	most of the time, and a numbered list of eleven the rest of it — and a
	customer who typed "hi" should not be handed the whole wizard. So a reply
	that has turned into a list is trimmed to what it said before the list
	began, plus the one question that was actually next.

	A reply that is not a list is left exactly as it is.
	"""
	text = (reply or "").strip()
	if len(LIST_LINE.findall(text)) < 2:
		return reply

	lead = LIST_LINE.split(text)[0].strip()
	# Keep at most two sentences of the lead-in; the rest was preamble to the
	# list that is no longer there.
	lead = " ".join(re.split(r"(?<=[.!?])\s+", lead)[:2]).strip()

	try:
		open_now = _setup_questions(onboarding, 1)["questions"]
	except Exception:
		open_now = []
	if not open_now:
		return lead or text

	question = open_now[0]["question"]
	if question.lower() in lead.lower():
		return lead
	return f"{lead}\n\n{question}".strip()


# What people say that answers nothing. "Yes" is not here on purpose: it is
# small talk as a company's name and a real answer to "do you keep stock
# elsewhere?", so it is turned away where it is a value, not at the door.
SMALL_TALK = {
	"hi", "hey", "hello", "yo", "hiya", "ok", "okay", "k", "sure", "right", "fine",
	"thanks", "thank you", "ta", "cheers", "ok thanks", "okay thanks", "thanks a lot",
	"hmm", "um", "test", "testing", "what", "huh", "help", "start", "next", "go on",
	"good morning", "good afternoon", "good evening", "how are you", "whats up",
}
NOT_A_NAME = SMALL_TALK | {"yes", "no", "yep", "nope", "yeah", "nah", "true", "false"}


def small_talk(said: str) -> bool:
	"""Whether this was a greeting rather than something to write down."""
	plain = re.sub(r"[^a-z ]", "", (said or "").lower()).strip()
	return not plain or plain in SMALL_TALK or len(plain) < 2


def catch_up_setup(onboarding: str, said: str, asked: str | None = None) -> dict:
	"""What the customer just said, mapped onto the open setup questions.

	The same trick as the interview's catch-up, for the questions that now do
	the work. One call, no tools, JSON out: a small model is poor at deciding
	*when* to call a tool and good at reading one sentence and saying what it
	answers. So the conversation is left to do the talking and this makes sure
	nothing said is lost.

	Everything is checked against the real questions and their real choices
	before it is saved, and anything not plainly stated is dropped.
	"""
	# "Hi" is not the company's name. Reading a greeting for answers is how a
	# hello ends up written into ERPNext as a legal entity.
	if small_talk(said):
		return {}
	open_now = _setup_questions(onboarding, 40, with_links=True)["questions"]
	if not open_now:
		return {}

	listed = []
	for q in open_now:
		allowed = ", ".join(q["choices"]) if q["choices"] else ("yes, no" if q["type"] == "Yes / No" else "free text")
		listed.append(f'- {q["key"]} ("{q["question"]}"): {allowed}')
	prompt = (
		"These setup questions are open:\n"
		+ "\n".join(listed)
		+ "\n\n"
		+ (f'The assistant had just asked: "{asked}"\n' if asked else "")
		+ f'The customer replied: "{said}"\n\n'
		'Which of those does that reply answer? Answer with JSON only, no other words: '
		'{"<question key>": "<the answer>"}. Where the question lists choices, use one of them '
		"exactly; where it says free text, use the customer's own words.\n"
		"Be strict. Include a question only if the reply says its answer outright. Do not work it "
		"out from the kind of business they are and do not fill in what is likely. Leaving a "
		"question out is always safe; inventing an answer is not. If it answers none, return {}."
	)
	try:
		reply = _complete([{"role": "user", "content": prompt}], tools=[])
	except Exception:
		return {}
	known = {row.question: row.value for row in frappe.get_doc("Embark Onboarding", onboarding).wizard_answers}
	return _real_setup_answers(_json_object(reply.get("text") or ""), open_now, known)


def _real_setup_answers(data: dict, open_now: list[dict], known: dict | None = None) -> dict:
	"""Only keys that are being asked, and only values those questions accept."""
	by_key = {q["key"]: q for q in open_now}
	out = {}
	for key, value in (data or {}).items():
		question = by_key.get(key)
		if not question or not isinstance(value, str) or not value.strip():
			continue
		value = value.strip()
		kind, choices = question["type"], question["choices"]
		if kind == "Yes / No":
			if value.lower() in ("yes", "true", "1"):
				out[key] = "Yes"
			elif value.lower() in ("no", "false", "0"):
				out[key] = "No"
		elif kind == "Multiple Choice":
			picked = [v.strip() for v in value.split(",") if v.strip() in choices]
			if picked:
				out[key] = ",".join(picked)
		elif choices:
			if value in choices:
				out[key] = value
		elif kind == "Number":
			if value.replace(".", "", 1).isdigit():
				out[key] = value
		elif kind == "Link":
			# "rupees" is not a Currency. A link that names no record would be
			# saved happily and then fail the moment the step is built, so it
			# is resolved here or dropped.
			found = _link_match(question.get("link_doctype"), value, {**(known or {}), **out})
			if found:
				out[key] = found
		else:
			# Free text still has to look like an answer rather than a nod: a
			# company is not called "hi", and it is not called "yes" either.
			plain = re.sub(r"[^a-z ]", "", value.lower()).strip()
			if plain and plain not in NOT_A_NAME and len(plain) > 1:
				out[key] = value

	# One sentence does not answer two questions with the same words. Told
	# "the company is Harness Traders Private Limited", a model will happily
	# offer that as the company's short code as well; the first question it
	# fits keeps it.
	seen = {}
	for key, value in list(out.items()):
		if value in seen:
			del out[key]
		else:
			seen[value] = key
	return out


def _link_match(doctype: str | None, value: str, known: dict | None = None) -> str:
	"""The record this answer means, by name or by what it is called.

	People say "rupees", not "INR", and a Currency is named by its code. So
	the record is looked for by its name, then by whatever it calls itself —
	a Currency's currency_name is "Rupee" — and singular or plural either way.
	One match counts; two mean it was not clear enough to guess.
	"""
	if not doctype or not frappe.db.exists("DocType", doctype):
		return ""
	if frappe.db.exists(doctype, value):
		return value

	meta = frappe.get_meta(doctype)
	tried = {value, value.rstrip("s")} if len(value) > 3 else {value}
	fields = [f for f in (meta.title_field, "currency_name", f"{frappe.scrub(doctype)}_name") if f and meta.get_field(f)]

	several = []
	for word in tried:
		for field in ["name", *fields]:
			found = frappe.get_all(doctype, filters={field: ("like", f"%{word}%")}, pluck="name", limit=6)
			if len(found) == 1:
				return found[0]
			several += found

	# A Currency record is named by its code and calls itself by its code, so
	# nothing in the table says "rupee". Frappe's own country data does, and a
	# customer who has said where they are has already said which rupee they
	# mean. It is only accepted when the word really is that country's money —
	# "dollars" in India stays unanswered rather than becoming INR.
	if doctype == "Currency" and (known or {}).get("company_country"):
		code, called = _money_of(known["company_country"])
		word = value.lower().rstrip("s")
		if code and word and (word in called.lower() or word == code.lower()):
			return code
	return several[0] if len(set(several)) == 1 else ""


def _money_of(country: str) -> tuple[str, str]:
	"""A country's currency and what it is called, as Frappe already knows."""
	try:
		from frappe.geo.country_info import get_country_info

		info = get_country_info(country) or {}
		return info.get("currency") or "", info.get("currency_name") or ""
	except Exception:
		return "", ""


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

	if name == "open_setup_questions":
		return _setup_questions(onboarding, int(arguments.get("limit") or 6))

	if name == "answer_setup":
		given = arguments.get("answers") or {}
		if not isinstance(given, dict) or not given:
			return {"error": "Nothing to save. Give the answers as key to value."}
		doc = frappe.get_doc("Embark Onboarding", onboarding)
		from embark import wizard

		known = {q["key"] for q in _setup_questions(onboarding, 200)["questions"]}
		unknown = [key for key in given if key not in known]
		if unknown:
			return {"error": f"Not a question being asked: {', '.join(unknown)}."}
		wizard.save_answers(doc, {k: str(v or "") for k, v in given.items()})
		return {"saved": list(given), "left": _setup_questions(onboarding, 3)["questions"]}

	if name == "build_in_erpnext":
		from embark import wizard

		doc = frappe.get_doc("Embark Onboarding", onboarding)
		step = (arguments.get("step") or "").strip()
		if not frappe.db.exists("Embark Wizard Task", step):
			return {"error": f"There is no step called {step}."}
		out = wizard.apply(doc, step)
		return {"built": [{"kind": r["doctype"], "name": r["name"]} for r in out.get("records") or []]}

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
	# The company comes first: it is who the onboarding is for, and everything
	# after it is set up in that company's name.
	if not o["company_complete"]:
		return _("Fill in the company details — the name, country, currency and financial year.")
	if not o["interview"]["done"]:
		return _("Finish the questions — {0} of {1} answered.").format(
			o["interview"]["answered"], o["interview"]["total"]
		)
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
		"messages": [{"role": "system", "content": _system()}, *messages],
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
		"system": _system(),
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
