"""Endpoints for the customer portal and the consultant's actions.

Embark runs on the customer's own site, one onboarding per site. The site is
handed over before ERPNext's setup wizard has run, and until then the desk only
shows the wizard, so everything the consultant needs before setup (start,
review, download) is also available from the portal.

Every call loads the onboarding through ``_get_onboarding``, which applies the
normal permission check (and so the row-level hooks in permissions.py). A
customer can therefore only ever reach their own record.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import cstr, flt, get_fullname, validate_email_address
from werkzeug.wrappers import Response

from embark import assistant, configure, copilot, importer
from embark import wizard as wizard_engine
from embark.conditions import applies
from embark.embark.doctype.embark_onboarding.embark_onboarding import (
	LOCKED_STATUSES,
)
from embark.embark.doctype.embark_upload.embark_upload import known_values
from embark.engine import build_columns
from embark.permissions import is_staff
from embark.sheets import prepared_zip, template_xlsx, typed_xlsx

# The company questions the customer answers on the portal.
COMPANY_FIELDS = (
	"company_name",
	"country",
	"default_currency",
	"fiscal_year_start",
	"chart_of_accounts",
	"tax_id",
	"company_email",
	"company_phone",
	"company_address",
)

MAX_ISSUES_SENT = 500
PREVIEW_ROWS = 20
# Typing is for a handful of rows; past that a spreadsheet is the right tool.
MAX_TYPED_ROWS = 200


# ── Customer portal ───────────────────────────────────────────────────────────


@frappe.whitelist()
def get_overview(onboarding: str | None = None) -> dict:
	if not onboarding and not frappe.db.count("Embark Onboarding"):
		# A freshly created customer site: the consultant starts here.
		return {
			"needs_start": True,
			"is_staff": is_staff(),
			"user": {"name": frappe.session.user, "full_name": get_fullname(frappe.session.user)},
			"can_use_desk": True,
			# Setting up the AI is something to do before starting, not after.
			"can_configure_ai": _can_configure_ai(),
			"assistant": assistant.is_on(),
			"assistant_model": assistant.model_name(),
		}
	doc = _get_onboarding(onboarding)
	# Readiness and step status are derived, so recompute them for the read: a
	# new interview question or a deleted upload must not leave a stale figure
	# on screen until someone happens to save the record.
	doc.refresh_areas()
	_replan(doc)
	_adopt_company(doc)
	areas = {
		a.name: a
		for a in frappe.get_all(
			"Embark Data Area",
			filters={"name": ("in", [row.data_area for row in doc.areas] or [""])},
			fields=["name", "description", "sequence", "icon", "because"],
		)
	}
	steps = sorted(
		(
			{
				"area": row.data_area,
				"description": areas[row.data_area].description if row.data_area in areas else "",
				"icon": areas[row.data_area].icon if row.data_area in areas else "",
				"because": areas[row.data_area].because if row.data_area in areas else "",
				"sequence": areas[row.data_area].sequence if row.data_area in areas else 0,
				"required": bool(row.required),
				"status": row.status,
				"rows": row.rows,
				"errors": row.errors,
				"warnings": row.warnings,
			}
			for row in doc.areas
		),
		key=lambda s: s["sequence"],
	)
	return {
		"name": doc.name,
		"client_name": doc.client_name,
		"status": doc.status,
		"readiness": doc.readiness,
		"review_notes": doc.review_notes if doc.status == "Returned" else None,
		"target_go_live": doc.target_go_live,
		"locked": _locked(doc),
		"is_staff": is_staff(),
		"interview": doc.interview(),
		"company": {f: doc.get(f) for f in COMPANY_FIELDS},
		"company_complete": doc.company_complete(),
		"company_from_erpnext": bool(doc.company_name) and setup_done(),
		"steps": steps,
		"plan": _plan(doc),
		"can_submit": doc.readiness == 100 and doc.status not in LOCKED_STATUSES,
		"can_use_desk": _can_use_desk(),
		"has_data": any(row.rows for row in doc.areas),
		"setup_done": setup_done(),
		"imported_at": doc.imported_at,
		"import_summary": frappe.parse_json(doc.import_log) if doc.import_log else None,
		"tally": _tally(doc),
		"assistant": assistant.is_on(),
		"can_configure_ai": _can_configure_ai(),
		"assistant_model": assistant.model_name(),
		"assistant_engine": _engine(),
		"user": {"name": frappe.session.user, "full_name": get_fullname(frappe.session.user)},
	}


def _engine() -> str:
	"""Which engine answers here: Frappe Flow, or Embark's own loop."""
	from embark import assistant_flow

	return "flow" if assistant_flow.available() else "embark"


@frappe.whitelist()
def ai_settings() -> dict:
	"""What the chat is pointed at. The key itself never comes back."""
	copilot._studio_user()
	doc = frappe.get_single("Embark Settings")
	return {
		"enabled": bool(doc.assistant_enabled),
		"provider": doc.provider or "OpenAI compatible",
		"base_url": doc.base_url or "",
		"model": doc.model or "",
		"has_key": bool(doc.get_password("api_key", raise_exception=False)),
		"on": assistant.is_on(),
	}


@frappe.whitelist()
def save_ai_settings(
	enabled: int | bool = 0,
	provider: str = "OpenAI compatible",
	base_url: str = "",
	model: str = "",
	api_key: str | None = None,
) -> dict:
	"""Point the chat at a provider, from the portal: the desk may not be open yet."""
	copilot._studio_user()
	doc = frappe.get_single("Embark Settings")
	doc.assistant_enabled = 1 if frappe.parse_json(enabled) else 0
	doc.provider = provider
	doc.base_url = base_url.strip()
	doc.model = model.strip()
	# An empty key means "leave the one you have".
	if api_key:
		doc.api_key = api_key
	doc.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Embark Settings")
	return ai_settings()


@frappe.whitelist()
def ask(
	message: str,
	onboarding: str | None = None,
	history: str | list | None = None,
	file_url: str | None = None,
	ui_prompt: str | None = None,
) -> dict:
	"""One turn of the chat, which drives the same screens the buttons do."""
	doc = _get_onboarding(onboarding, "write")
	if _locked(doc):
		frappe.throw(_("This onboarding has been sent for review."))
	if file_url:
		_own_file(doc, file_url)
	out = assistant.ask(
		doc.name,
		message,
		frappe.parse_json(history) if history else [],
		file_url=file_url,
		ui_prompt=ui_prompt,
	)
	_catch_up_setup(doc, message, out)
	# The drawing is streamed separately, so the words arrive without waiting
	# for it. `ui_prompt` here only tells the conversation what it may draw.
	return out


def _own_file(doc, file_url: str) -> None:
	"""A file handed to the chat has to be one attached to this onboarding.

	Embark Upload checks the same thing when it reads the file; checking here
	too means the customer gets a plain refusal instead of the model being
	handed a path it cannot use.
	"""
	if not frappe.db.exists(
		"File",
		{"file_url": file_url, "attached_to_doctype": "Embark Onboarding", "attached_to_name": doc.name},
	):
		frappe.throw(_("That file does not belong to this onboarding."))


@frappe.whitelist()
def chat_opening(onboarding: str | None = None) -> dict:
	"""What the chat says before it is spoken to, and what to say back."""
	doc = _get_onboarding(onboarding)
	return assistant.opening(doc.name)


@frappe.whitelist()
def get_interview(onboarding: str | None = None) -> dict:
	"""The questions that apply right now, with whatever has been answered."""
	doc = _get_onboarding(onboarding)
	answers = doc.answer_map()
	questions = []
	for q in frappe.get_all(
		"Embark Question",
		filters={"is_active": 1},
		fields=[
			"name",
			"label",
			"section_title",
			"answer_type",
			"choices",
			"help_text",
			"applies_when",
			"allow_not_sure",
		],
		order_by="sequence asc",
	):
		if not applies(q.applies_when, answers):
			continue
		questions.append(
			{
				"key": q.name,
				"label": q.label,
				"section": q.section_title or _("About your business"),
				"type": q.answer_type,
				"help": q.help_text,
				"allow_not_sure": bool(q.allow_not_sure),
				"choices": _choices(q),
				"answer": answers.get(q.name, ""),
			}
		)
	return {"name": doc.name, "questions": questions, "progress": doc.interview(), "locked": _locked(doc)}


@frappe.whitelist(methods=["POST"])
def answer_in_words(onboarding: str, question: str, text: str) -> dict:
	"""An answer written rather than picked, read into one of the choices.

	"Not sure" is a poor place to put everything a customer wants to say. They
	can write instead, and what they wrote is kept beside whatever it was read
	as — so a consultant sees the words, and a wrong reading is corrected by
	picking.
	"""
	doc = _get_onboarding(onboarding, "write")
	text = (text or "").strip()
	if not text:
		frappe.throw(_("Write something first."))

	q = frappe.get_doc("Embark Question", question)
	reading = assistant.read_answer(q, text)
	value = reading.get("value") or ("not_sure" if q.allow_not_sure else "")

	for row in doc.answers:
		if row.question == question:
			row.answer, row.note = value, text
			break
	else:
		doc.append("answers", {"question": question, "answer": value, "note": text})
	doc.save()

	return {
		"value": value,
		"read_as": next((c["label"] for c in _choices(q) if c["value"] == value), value),
		"why": reading.get("why") or "",
		"understood": bool(reading.get("value")),
		"overview": get_overview(doc.name),
	}


@frappe.whitelist(methods=["POST"])
def save_answers(onboarding: str, answers: str | dict) -> dict:
	"""Store the answers, then rebuild the steps they imply."""
	doc = _get_onboarding(onboarding, "write")
	given = frappe.parse_json(answers) or {}
	questions = {
		q.name: q
		for q in frappe.get_all(
			"Embark Question", fields=["name", "answer_type", "choices", "allow_not_sure"]
		)
	}
	rows = {row.question: row for row in doc.answers}
	for key, value in given.items():
		question = questions.get(key)
		if not question:
			frappe.throw(_("{0} is not one of the questions.").format(key))
		clean = _clean_answer(question, value)
		if key in rows:
			rows[key].answer = clean
			rows[key].note = None
		else:
			doc.append("answers", {"question": key, "answer": clean})
	doc.save()
	return get_overview(doc.name)


def _choices(question) -> list[dict]:
	"""Choices are written as "key | What the customer sees", one per line."""
	out = []
	for line in (question.choices or "").splitlines():
		if not line.strip():
			continue
		value, _sep, label = line.partition("|")
		out.append({"value": value.strip(), "label": (label or value).strip()})
	return out


def _clean_answer(question, value) -> str:
	value = cstr(value).strip()
	if not value or value == "not_sure":
		if value and not question.allow_not_sure:
			frappe.throw(_("Please answer: {0}").format(question.name))
		return value
	if question.answer_type == "Yes / No":
		if value not in ("yes", "no"):
			frappe.throw(_("Answer {0} with yes or no.").format(question.name))
		return value
	if question.answer_type == "Number":
		number = flt(value)
		return str(int(number)) if number == int(number) else str(number)
	allowed = {c["value"] for c in _choices(question)}
	chosen = [v.strip() for v in value.split(",") if v.strip()]
	if not set(chosen) <= allowed:
		frappe.throw(_("{0} is not one of the choices for {1}.").format(value, question.name))
	if question.answer_type == "One choice" and len(chosen) > 1:
		frappe.throw(_("Pick one answer for {0}.").format(question.name))
	return ",".join(chosen)


@frappe.whitelist()
def get_company_choices() -> dict:
	return {
		"countries": frappe.get_all("Country", pluck="name", order_by="name asc"),
		# All currencies, not just enabled ones: a new site enables only a few,
		# and the setup wizard enables the one the customer picks.
		"currencies": frappe.get_all("Currency", pluck="name", order_by="name asc"),
	}


@frappe.whitelist(methods=["POST"])
def save_company_details(onboarding: str, values: str | dict) -> dict:
	doc = _get_onboarding(onboarding, "write")
	values = frappe.parse_json(values) or {}
	doc.update({f: values.get(f) or None for f in COMPANY_FIELDS if f in values})
	doc.save()
	return get_overview(doc.name)


@frappe.whitelist()
def get_area(onboarding: str, area: str) -> dict:
	doc = _get_onboarding(onboarding)
	_ensure_area(doc, area)
	area_doc = frappe.get_cached_doc("Embark Data Area", area)
	answers = doc.answer_map()
	columns = build_columns(area_doc, answers)
	suggestions = known_values(doc.name, columns)
	out = {
		"suggestions": {dt: sorted(values.values())[:200] for dt, values in suggestions.items()},
		"area": {
			"name": area_doc.name,
			"description": area_doc.description,
			"help_text": area_doc.help_text,
			"icon": area_doc.icon,
			"required": next(bool(r.required) for r in doc.areas if r.data_area == area),
		},
		"columns": [c.as_dict() for c in columns],
		"locked": _locked(doc),
		"upload": None,
	}

	name = _upload_name(doc.name, area)
	if not name:
		return out

	upload = frappe.get_doc("Embark Upload", name)
	ev = upload.evaluate()
	column_map = frappe.parse_json(upload.column_map) or {}
	by_field = {c.fieldname: c for c in ev.columns}
	mapped = [c for c in ev.columns if c.fieldname in column_map.values() or c.default]

	out["upload"] = {
		"file_name": upload.file_name,
		"file_url": upload.file_url,
		"headers": [
			{
				"header": h,
				"fieldname": column_map.get(h),
				"samples": _samples(ev.rows, i),
			}
			for i, h in enumerate(ev.headers)
		],
		"rows": len(ev.rows),
		"errors": ev.result.errors,
		"warnings": ev.result.warnings,
		"groups": ev.result.groups,
		"issues": ev.result.issues[:MAX_ISSUES_SENT],
		"preview": {
			"columns": [{"fieldname": c.fieldname, "label": c.label} for c in mapped],
			"rows": [{k: r.get(k) for k in ("_row", *by_field)} for r in ev.result.rows[:PREVIEW_ROWS]],
		},
	}
	return out


@frappe.whitelist()
def download_template(area: str, onboarding: str | None = None):
	"""The template for this step, with only the columns the answers call for."""
	doc = _get_onboarding(onboarding)
	_ensure_area(doc, area)
	area_doc = frappe.get_doc("Embark Data Area", area)
	area_doc.check_permission("read")
	_send_file(_("{0} - template.xlsx").format(area_doc.area_name), template_xlsx(area_doc, doc.answer_map()))


@frappe.whitelist(methods=["POST"])
def enter_rows(onboarding: str, area: str, rows: str | list) -> dict:
	"""Rows typed into the screen instead of uploaded as a file.

	Three warehouses do not deserve a spreadsheet. What is typed becomes one
	anyway, so the checks, the fixes and the export are the same either way —
	and it can be downloaded afterwards like any other upload.
	"""
	doc = _get_onboarding(onboarding, "write")
	_ensure_area(doc, area)
	if _locked(doc):
		frappe.throw(_("This onboarding has been sent for review."))

	given = [r for r in (frappe.parse_json(rows) or []) if any(cstr(v).strip() for v in r.values())]
	if not given:
		frappe.throw(_("Fill in at least one row."))
	if len(given) > MAX_TYPED_ROWS:
		frappe.throw(_("That many rows is a file, not a form. Upload a spreadsheet instead."))

	area_doc = frappe.get_doc("Embark Data Area", area)
	content = typed_xlsx(area_doc, given, doc.answer_map())
	file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"{frappe.scrub(area)}-typed.xlsx",
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Embark Onboarding",
			"attached_to_name": doc.name,
		}
	).insert(ignore_permissions=True)
	return attach_file(doc.name, area, file.file_url)


@frappe.whitelist(methods=["POST"])
def attach_file(onboarding: str, area: str, file_url: str) -> dict:
	"""Point the area at a newly uploaded file and check it straight away."""
	doc = _get_onboarding(onboarding, "write")
	_ensure_area(doc, area)
	name = _upload_name(doc.name, area)
	upload = frappe.get_doc("Embark Upload", name) if name else frappe.new_doc("Embark Upload")
	# A new file starts clean: column choices and fixes belong to the old one's rows.
	upload.update(
		{
			"onboarding": doc.name,
			"data_area": area,
			"file_url": file_url,
			"headers": None,
			"column_map": None,
			"overrides": None,
		}
	)
	upload.save()
	return get_area(doc.name, area)


@frappe.whitelist(methods=["POST"])
def set_column(onboarding: str, area: str, header: str, fieldname: str | None = None) -> dict:
	"""Say which ERPNext field a heading in the customer's file feeds (or none)."""
	upload = _get_upload(onboarding, area)
	columns = {
		c.fieldname
		for c in build_columns(
			frappe.get_cached_doc("Embark Data Area", area),
			frappe.get_doc("Embark Onboarding", onboarding).answer_map(),
		)
	}
	if fieldname and fieldname not in columns:
		frappe.throw(_("{0} is not a column of {1}.").format(fieldname, area))

	column_map = frappe.parse_json(upload.column_map) or {}
	# One heading per field: choosing a field for this heading frees it elsewhere.
	column_map = {h: f for h, f in column_map.items() if h != header and f != fieldname}
	if fieldname:
		column_map[header] = fieldname
	upload.column_map = json.dumps(column_map)
	upload.save()
	return get_area(onboarding, area)


@frappe.whitelist(methods=["POST"])
def fix_value(
	onboarding: str,
	area: str,
	fieldname: str,
	value: str | None = None,
	row: int | None = None,
	old_value: str | None = None,
) -> dict:
	"""Correct a value on screen: one row (``row``) or every row holding ``old_value``."""
	upload = _get_upload(onboarding, area)
	overrides = frappe.parse_json(upload.overrides) or {}
	if row is not None:
		overrides.setdefault(str(int(row)), {})[fieldname] = cstr(value)
	elif old_value is not None:
		overrides.setdefault("*", {}).setdefault(fieldname, {})[cstr(old_value).strip()] = cstr(value)
	else:
		frappe.throw(_("Say which row or which value to change."))
	upload.overrides = json.dumps(overrides)
	upload.save()
	return get_area(onboarding, area)


@frappe.whitelist(methods=["POST"])
def remove_file(onboarding: str, area: str) -> dict:
	upload = _get_upload(onboarding, area)
	upload.delete()
	return get_area(onboarding, area)


@frappe.whitelist(methods=["POST"])
def submit_for_review(onboarding: str) -> dict:
	doc = _get_onboarding(onboarding, "write")
	if doc.readiness != 100:
		frappe.throw(_("Finish every required step before sending your data for review."))
	doc.status = "Submitted"
	doc.save()
	doc.add_comment("Info", _("Sent for review by {0}").format(get_fullname(frappe.session.user)))
	_notify_consultant(doc)
	return get_overview(doc.name)


def _notify_consultant(doc):
	"""Email the consultant; a mail problem must never undo the customer's submission."""
	# The consultant is a User link, and a user's name is not always an address
	# ("Administrator"), so send to the User's email field.
	email = (
		validate_email_address(frappe.db.get_value("User", doc.consultant, "email") or "")
		if doc.consultant
		else ""
	)
	if not email:
		return
	try:
		frappe.sendmail(
			recipients=[email],
			subject=_("{0} has sent their onboarding data for review").format(doc.client_name),
			message=_("{0} is ready for review.").format(
				frappe.utils.get_link_to_form(doc.doctype, doc.name)
			),
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
	except Exception:
		frappe.log_error(title=f"Onboarding review email failed for {doc.name}")


# ── Consultant ────────────────────────────────────────────────────────────────


@frappe.whitelist(methods=["POST"])
def start_onboarding(client_name: str) -> dict:
	"""Set this site up for Embark. One site, one onboarding."""
	_require_staff()
	if frappe.db.count("Embark Onboarding"):
		frappe.throw(_("This site already has an onboarding. Each customer site has one."))
	doc = frappe.get_doc(
		{
			"doctype": "Embark Onboarding",
			"client_name": cstr(client_name).strip(),
			"consultant": frappe.session.user,
		}
	).insert()
	return {"overview": get_overview(doc.name)}


@frappe.whitelist(methods=["POST"])
def create_in_erpnext(onboarding: str | None = None) -> dict:
	"""Turn the collected data into records on this site."""
	doc = _get_onboarding(onboarding, "write")
	_require_staff()
	if not setup_done():
		frappe.throw(_("Run ERPNext's setup wizard first — there is no company to put these records in."))

	summary = importer.import_all(doc)
	doc.db_set("imported_at", frappe.utils.now())
	doc.db_set("import_log", json.dumps(summary, default=str)[:140000])
	return {"summary": summary, "overview": get_overview(doc.name)}


@frappe.whitelist()
def configure_preview(onboarding: str, task: str) -> dict:
	"""What one line of the plan would change in ERPNext, before it is written."""
	copilot._studio_user()
	doc = _get_onboarding(onboarding)
	return {"task": task, "changes": configure.preview(doc, task)}


@frappe.whitelist(methods=["POST"])
def configure_step(onboarding: str, task: str) -> dict:
	"""Write one line of the plan to this site."""
	copilot._studio_user()
	doc = _get_onboarding(onboarding, "write")
	result = configure.apply(doc, task)
	return {"result": result, "overview": get_overview(doc.name)}


@frappe.whitelist(methods=["POST"])
def configure_all(onboarding: str) -> dict:
	"""Write every line of the plan Embark can do itself, in plan order."""
	copilot._studio_user()
	doc = _get_onboarding(onboarding, "write")
	done, already, failed = [], [], []
	for row in doc.tasks:
		if row.status == "Skipped" or not configure.can_apply(row.setup_task):
			continue
		try:
			result = configure.apply(doc, row.setup_task)
			(already if result["already"] else done).append(row.title)
		except Exception as e:
			failed.append({"task": row.title, "why": frappe.utils.strip_html(str(e))[:200]})
			frappe.clear_messages()
	return {
		"configured": done,
		"already": already,
		"failed": failed,
		"overview": get_overview(doc.name),
	}


# ── The setup wizard ──────────────────────────────────────────────────────────


@frappe.whitelist()
def wizard(onboarding: str | None = None) -> dict:
	"""Every task, its questions, and what has been answered so far."""
	doc = _get_onboarding(onboarding)
	return wizard_engine.board(doc)


@frappe.whitelist(methods=["POST"])
def wizard_answer(question: str, value: str, onboarding: str | None = None) -> dict:
	"""One answer, saved against the question it belongs to."""
	doc = _get_onboarding(onboarding, "write")
	if _locked(doc):
		frappe.throw(_("This onboarding has been sent for review."))
	wizard_engine.save_answer(doc, question, value)
	return wizard_engine.board(doc)


def _catch_up_setup(doc, message: str, out: dict) -> None:
	"""Save what the customer said, whatever the model decided to do about it.

	Both engines run the conversation; neither reliably remembers to write an
	answer down. So after the turn, if nothing was saved, the message is read
	once more on its own — no tools, no conversation — and anything it plainly
	answers is saved. The reply then says what was written down, because a
	guess the customer cannot see is a guess they cannot correct.
	"""
	from embark import wizard

	# It runs whether or not the turn saved something. A model that writes one
	# answer down and forgets the other half of the same sentence is the common
	# case, not the rare one — and because this reads only the questions still
	# open, anything already saved is not in front of it to save twice.
	steps = out.get("steps") or []
	history = out.get("reply") or ""
	caught = assistant.catch_up_setup(doc.name, message, None)
	if not caught:
		return

	# The turn's own tools may already have written to this document, so the
	# copy loaded before the conversation is stale by now.
	wizard.save_answers(frappe.get_doc("Embark Onboarding", doc.name), caught)
	labels = assistant.question_labels(caught)
	out["steps"] = [
		*steps,
		{
			"tool": "answer_setup",
			"label": _("Saved {0} answers").format(len(caught)) if len(caught) != 1 else _("Saved your answer"),
			"arguments": {"answers": caught},
			"outcome": _("Done"),
			"failed": False,
		},
	]
	noted = "; ".join(f"{label} — {value}" for label, value in labels)
	out["reply"] = (history.rstrip() + "\n\n" + _("I have put you down for {0}.").format(noted)).strip()


@frappe.whitelist(methods=["POST"])
def draw(reply: str, ui_prompt: str, onboarding: str | None = None):
	"""The same answer, drawn, streamed as it is written.

	Frappe hands a Response straight back to the client untouched, so this is
	server-sent events: one `data:` line per piece, and `done` at the end. The
	browser renders each piece as it lands, which is what the drawing language
	is built for — the shell appears first and fills in.
	"""
	doc = _get_onboarding(onboarding)
	if _locked(doc):
		frappe.throw(_("This onboarding has been sent for review."))
	# Without the keys it has no way to name a real question, and it invents
	# one — which draws a box that says the question is not being asked.
	open_now = assistant.open_question_keys(doc.name)
	frappe.local.embark_ui_prompt = f"{ui_prompt}\n\n{open_now}" if open_now else ui_prompt

	def events():
		drawn = False
		for piece in assistant.draw_stream(reply):
			drawn = True
			# A newline would end the event, so the piece travels encoded.
			yield f"data: {json.dumps({'text': piece})}\n\n"
		yield f"data: {json.dumps({'done': True, 'drawn': drawn})}\n\n"

	return Response(
		events(),
		mimetype="text/event-stream",
		headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
	)


@frappe.whitelist(methods=["POST"])
def wizard_answers(answers: str, onboarding: str | None = None) -> dict:
	"""A whole form's worth of answers, saved in one go."""
	doc = _get_onboarding(onboarding, "write")
	if _locked(doc):
		frappe.throw(_("This onboarding has been sent for review."))
	given = frappe.parse_json(answers) or {}
	if not isinstance(given, dict):
		frappe.throw(_("Answers should be a question-to-answer map."))
	wizard_engine.save_answers(doc, {str(k): str(v or "") for k, v in given.items()})
	return wizard_engine.board(doc)


# A list the customer picks from has to hold the answer they want. Country has
# 250 rows and Currency 190, so a window of the most recent few would hide most
# of them; a list this size costs nothing to send whole. Only a table big
# enough to be a search in its own right is cut, and then to the newest.
WHOLE_LIST_UNDER = 500


@frappe.whitelist()
def suggestions(doctype: str, limit: int = 100) -> list[str]:
	"""What this site already has of a kind, for a question that links to one."""
	_get_onboarding(None)  # a question is only asked inside an onboarding
	if not frappe.db.exists("DocType", doctype):
		return []
	if frappe.db.count(doctype) < WHOLE_LIST_UNDER:
		return frappe.get_all(doctype, pluck="name", limit=0, order_by="name asc")
	return frappe.get_all(doctype, pluck="name", limit=limit, order_by="modified desc")


@frappe.whitelist()
def wizard_state(onboarding: str | None = None) -> dict:
	"""Every task and the ERPNext record it has produced, read back live."""
	doc = _get_onboarding(onboarding)
	return wizard_engine.state(doc)


@frappe.whitelist()
def wizard_check(task: str, onboarding: str | None = None) -> dict:
	"""What applying this task would write, before it is written."""
	doc = _get_onboarding(onboarding)
	return wizard_engine.check(doc, task)


@frappe.whitelist(methods=["POST"])
def wizard_apply(task: str, onboarding: str | None = None) -> dict:
	"""Write the task's record to ERPNext and hand back what it holds."""
	copilot._studio_user()
	doc = _get_onboarding(onboarding, "write")
	out = wizard_engine.apply(doc, task)
	return {**out, "board": wizard_engine.board(doc)}


@frappe.whitelist(methods=["POST"])
def review(onboarding: str, decision: str, notes: str | None = None) -> dict:
	_require_staff()
	if decision not in ("Approved", "Returned"):
		frappe.throw(_("Choose Approved or Returned."))
	doc = _get_onboarding(onboarding, "write")
	doc.status = decision
	if notes is not None:
		doc.review_notes = notes
	doc.save()
	doc.add_comment("Info", _("{0} by {1}").format(_(decision), get_fullname(frappe.session.user)))

	# Approving means the data is good, so it goes in — unless ERPNext has not
	# been set up yet, in which case it waits for the wizard.
	summary = None
	if decision == "Approved" and setup_done():
		summary = importer.import_all(doc)
		doc.db_set("imported_at", frappe.utils.now())
		doc.db_set("import_log", json.dumps(summary, default=str)[:140000])

	return {"status": doc.status, "summary": summary, "overview": get_overview(doc.name)}


@frappe.whitelist()
def download_prepared_data(onboarding: str):
	_require_staff()
	doc = _get_onboarding(onboarding)
	_send_file(f"{doc.client_name} - prepared data.zip", prepared_zip(doc))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _get_onboarding(onboarding: str | None = None, ptype: str = "read"):
	if not onboarding:
		onboarding = frappe.db.get_value("Embark Onboarding", {}, "name", order_by="creation desc")
		if not onboarding:
			frappe.throw(_("This site has no onboarding yet."), frappe.DoesNotExistError)
	doc = frappe.get_doc("Embark Onboarding", onboarding)
	doc.check_permission(ptype)
	return doc


def _get_upload(onboarding: str, area: str):
	doc = _get_onboarding(onboarding, "write")
	_ensure_area(doc, area)
	name = _upload_name(doc.name, area)
	if not name:
		frappe.throw(_("Upload a file for {0} first.").format(area))
	return frappe.get_doc("Embark Upload", name)


def _upload_name(onboarding: str, area: str) -> str | None:
	return frappe.db.get_value("Embark Upload", {"onboarding": onboarding, "data_area": area})


def _ensure_area(doc, area: str):
	if area not in {row.data_area for row in doc.areas}:
		frappe.throw(_("{0} is not one of your steps.").format(area), frappe.DoesNotExistError)


def _replan(doc) -> None:
	"""Keep the plan in step with the rules, not just with the last save.

	A step or a setup task added to the library after this onboarding started
	belongs in it too, so the plan is rebuilt on read and written back when it
	has actually moved — otherwise a step could show on the overview that the
	record does not hold.
	"""
	before = ([r.data_area for r in doc.areas], [r.setup_task for r in doc.tasks])
	doc.sync_areas()
	doc.sync_tasks()
	if doc.status in LOCKED_STATUSES:
		return
	if ([r.data_area for r in doc.areas], [r.setup_task for r in doc.tasks]) != before:
		doc.save(ignore_permissions=True)


def _plan(doc) -> list[dict]:
	"""The part of the plan that is not a sheet: settings, decisions, training.

	Generated from the answers like the steps are, and each line says why it is
	there. How it gets done is the consultant's note, not the customer's.
	"""
	if not doc.tasks:
		return []
	library = {
		t.name: t
		for t in frappe.get_all(
			"Embark Setup Task",
			filters={"name": ("in", [row.setup_task for row in doc.tasks])},
			fields=["name", "description", "detail"],
		)
	}
	staff = is_staff()
	return [
		{
			"key": row.setup_task,
			"title": row.title,
			"kind": row.kind,
			"because": row.because,
			"status": row.status,
			"description": library.get(row.setup_task, {}).get("description"),
			"detail": library.get(row.setup_task, {}).get("detail") if staff else None,
			# A line Embark can write to the site itself, rather than ask for.
			"can_apply": staff and configure.can_apply(row.setup_task),
			"notes": row.notes if staff else None,
		}
		for row in doc.tasks
	]


def _tally(doc) -> dict | None:
	"""Customers who answered "Tally" are offered Tally Migrator instead of typing.

	Frappe's own app reads a Tally export straight into ERPNext, so Embark points
	at it rather than asking for the same masters in a spreadsheet.
	"""
	if doc.answer_map().get("current_system") != "tally":
		return None
	return {
		"installed": "tally_migrator" in frappe.get_installed_apps(),
		"route": "/app/tally-migrator",
		"repo": "https://github.com/frappe/tally_migrator",
	}


def _can_configure_ai() -> bool:
	"""Pointing the chat at a provider is the implementer's job, not the customer's."""
	try:
		copilot._studio_user()
	except frappe.PermissionError:
		return False
	return True


def setup_done() -> bool:
	"""Has ERPNext's setup wizard been run on this site?

	frappe.is_setup_complete() reads the per-app flags, which is what the desk
	itself checks; System Settings can say complete while ERPNext is not.
	"""
	return bool(
		frappe.is_setup_complete()
		if hasattr(frappe, "is_setup_complete")
		else frappe.db.get_single_value("System Settings", "setup_complete")
	)


def _adopt_company(doc) -> None:
	"""Never ask for the company twice.

	If ERPNext has already been set up on this site, its company holds the
	answers, so Embark takes them instead of asking the customer again.
	"""
	if doc.company_name or not setup_done():
		return
	company = frappe.db.get_value(
		"Company",
		{},
		["name", "abbr", "country", "default_currency", "tax_id"],
		as_dict=True,
		order_by="creation asc",
	)
	if not company:
		return
	doc.company_name = company.name
	doc.abbr = company.abbr
	doc.country = company.country
	doc.default_currency = company.default_currency
	doc.tax_id = company.tax_id
	doc.fiscal_year_start = frappe.db.get_value(
		"Fiscal Year", {}, "year_start_date", order_by="year_start_date desc"
	)
	doc.save(ignore_permissions=True)


def _can_use_desk() -> bool:
	"""A desk login, and a desk that will let them in.

	Until ERPNext's setup wizard has run, the desk admits only System Managers.
	"""
	if frappe.db.get_value("User", frappe.session.user, "user_type") != "System User":
		return False
	return is_staff() or setup_done()


def _locked(doc) -> bool:
	"""Data is read-only once it has been sent for review, until it is returned."""
	return doc.status in LOCKED_STATUSES


def _require_staff():
	if not is_staff():
		frappe.throw(_("Only consultants can do this."), frappe.PermissionError)


def _samples(rows, index: int, limit: int = 3) -> list[str]:
	out = []
	for _row, cells in rows:
		value = cells[index] if index < len(cells) else None
		if value not in (None, ""):
			out.append(cstr(value)[:40])
			if len(out) == limit:
				break
	return out


def _send_file(filename: str, content: bytes):
	frappe.response.filename = filename
	frappe.response.filecontent = content
	frappe.response.type = "binary"
