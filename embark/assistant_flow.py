"""Ask Embark, run on Frappe Flow's agent engine.

The chat the customer talks to is the same chat; what runs it is Flow — the
loop, the typed tools and the model resolver vendored under ``embark/vendor/flow``.
Embark keeps its own simpler loop in ``assistant`` for sites where Flow cannot
run, and a site can pin either one.

What Flow brings that the hand-written loop does not:

* **Tools are typed from their signatures.** A Python function with annotations
  and a docstring *is* the tool schema, so the description a model reads and the
  code that runs can never drift apart.
* **Arguments are validated before anything executes.** A model that answers
  sloppily is corrected by the engine rather than by Embark's own guesswork.
* **The run is a stream of events** — text, tool started, tool ended — which is
  what a chat that feels alive is made of.

What does not change is the safety. Every tool here calls the same ``embark.api``
function the button calls, so the permissions, the validation and the refusals
are the ones Embark already has. The engine is never handed a write of its own.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from embark import assistant

# Flow is strict with a model that answers sloppily, so it is worth saying which
# engine ran when something looks odd.
ENGINE = "flow"


def available() -> bool:
	"""Can this site run the chat on Flow?

	Flow talks to providers through litellm. A site that does not have it falls
	back to Embark's own loop rather than losing the chat.
	"""
	if frappe.conf.get("embark_engine") == "embark":
		return False
	if not assistant.is_on():
		return False
	try:
		import litellm
	except ImportError:
		return False
	return True


def model():
	"""A Flow model built from the one place a customer configures AI.

	Embark Settings is what the Configure AI dialog writes, so there is no
	second place to set this up. litellm names a provider in the model id.
	"""
	from embark.vendor.flow.model import Model

	doc = assistant.settings()
	prefix = "anthropic" if doc.provider == "Anthropic" else "openai"
	return Model(
		model_id=f"{prefix}/{doc.model}",
		api_key=doc.get_password("api_key", raise_exception=False) or "not-needed",
		base_url=(doc.base_url or None) if prefix == "openai" else None,
	)


def ask(
	onboarding: str, message: str, history: list[dict] | None = None, file_url: str | None = None
) -> dict:
	"""One turn of Ask Embark, run by Flow."""
	from embark.vendor.flow import Agent, tool

	offered = {t["name"] for t in assistant.tools_for(onboarding)}
	tools = [tool(f) for f in _functions(onboarding) if f.__name__ in offered]

	agent = Agent(
		model=model(),
		name="ask-embark",
		instructions=assistant._system(),
		tools=tools,
		# Every tool is one of Embark's own screens, with Embark's own rules
		# already around it. There is nothing here to approve twice.
		auto_approve=True,
		max_iterations=assistant.MAX_ROUNDS,
	)

	turns = [*(assistant._conversation(history) or []), {"role": "user", "content": message}]
	if file_url:
		turns.append({"role": "user", "content": assistant._attached(onboarding, file_url)})
	asked = next((m["content"] for m in reversed(turns[:-1]) if m["role"] == "assistant"), None)

	result, circled = None, False
	try:
		result = agent.run(turns)
	except RuntimeError:
		# The engine gave up going round. Whatever it did still counts.
		circled = True
	except Exception as e:
		# The provider refused or could not be reached. Say which, the same way
		# the other engine does — a bare traceback helps nobody.
		frappe.log_error(f"Ask Embark on Flow: {e}", "Embark assistant")
		frappe.throw(assistant._unreachable(e))

	steps = _steps(result)
	used = [step["tool"] for step in steps]
	text = (result.output if result else "") or ""
	if circled and not text:
		text = _("I went round in circles on that. Could you say it more plainly?")

	return assistant._answer(onboarding, text, used, steps, None, message, asked) | {"engine": ENGINE}


def _functions(onboarding: str) -> list:
	"""Ask Embark's tools as Python functions, which is what Flow reads.

	Each one hands straight to the dispatcher the other engine uses, so there is
	one implementation of every tool and no second place for it to go stale.
	"""

	def run(name: str, **arguments):
		return assistant._run_tool(onboarding, name, arguments)

	def where_am_i() -> dict:
		"""Where this onboarding stands: the interview, every step with its state
		and problems, and what to do next. Start here."""
		return run("where_am_i")

	def open_questions() -> dict:
		"""The interview questions that still need an answer, with the allowed choices."""
		return run("open_questions")

	def save_answers(answers: dict) -> dict:
		"""Save answers the customer has given. Keys are question keys from
		open_questions, values are that question's choice values. Several choices
		are comma separated."""
		return run("save_answers", answers=answers)

	def show_plan() -> dict:
		"""The steps, settings, decisions and training the answers have produced."""
		return run("show_plan")

	def step_help(area: str) -> dict:
		"""What one step is for, the columns it wants with an example of each, and
		where to get its template."""
		return run("step_help", area=area)

	def check_step(area: str) -> dict:
		"""The sheet on one step as it stands: rows that came through, and every
		problem with examples."""
		return run("check_step", area=area)

	def type_rows(area: str, rows: list) -> dict:
		"""Enter rows the customer dictated instead of a spreadsheet. One object per
		row, keyed by the column names step_help gives."""
		return run("type_rows", area=area, rows=rows)

	def fix(area: str, column: str, value: str, row: int = 0, old_value: str = "") -> dict:
		"""Correct a value on a step: one row by its number, or every row holding the
		same wrong value. Say what you are changing first."""
		return run(
			"fix",
			area=area,
			column=column,
			value=value,
			row=row or None,
			old_value=old_value or None,
		)

	def match_column(area: str, heading: str, column: str) -> dict:
		"""Connect a heading in the customer's sheet to the column Embark wants."""
		return run("match_column", area=area, heading=heading, column=column)

	def use_file(area: str, file_url: str) -> dict:
		"""Put a file the customer just attached onto a step."""
		return run("use_file", area=area, file_url=file_url)

	def remove_sheet(area: str) -> dict:
		"""Take the sheet off a step, when they sent the wrong file."""
		return run("remove_sheet", area=area)

	def send_for_review() -> dict:
		"""Send the finished data to the consultant. Only when every required step is
		ready and the customer agrees."""
		return run("send_for_review")

	def create_in_erpnext() -> dict:
		"""Create the approved data as real records in ERPNext."""
		return run("create_in_erpnext")

	return [
		where_am_i,
		open_questions,
		save_answers,
		show_plan,
		step_help,
		check_step,
		type_rows,
		fix,
		match_column,
		use_file,
		remove_sheet,
		send_for_review,
		create_in_erpnext,
	]


def _steps(result) -> list[dict]:
	"""The engine's tool calls, in the shape the panel already draws."""
	out = []
	for call in getattr(result, "tool_calls", []) or []:
		name = getattr(call, "name", "") or ""
		arguments = getattr(call, "arguments", None) or {}
		raw = getattr(call, "result", "")
		try:
			parsed = json.loads(raw) if isinstance(raw, str) else (raw or {})
		except ValueError:
			parsed = {}
		if not isinstance(parsed, dict):
			parsed = {}
		step = assistant._step({"name": name, "arguments": arguments}, parsed)
		out.append(step)
	return out
