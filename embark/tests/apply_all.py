import frappe
from embark import wizard


def run(onboarding=None):
	"""Try to build every step whose questions are answered, and say what happened."""
	name = onboarding or frappe.get_all("Embark Onboarding", pluck="name", order_by="modified desc")[0]
	doc = frappe.get_doc("Embark Onboarding", name)
	board = wizard.board(doc)
	ok, bad, skipped = [], [], []
	for task in board["tasks"]:
		if task["answered"] != task["total"] or not task["total"]:
			skipped.append(task["title"])
			continue
		doc = frappe.get_doc("Embark Onboarding", name)
		plans = wizard._records(doc, task["task"])
		if not plans:
			skipped.append(task["title"] + " (writes nothing)")
			continue
		try:
			out = wizard.apply(doc, task["task"])
			made = ", ".join(f"{r['doctype']} {r['name']}" for r in out.get("records") or [])
			ok.append(f"{task['title']} -> {made}")
			frappe.db.commit()
		except Exception as e:
			bad.append(f"{task['title']} -> {type(e).__name__}: {str(e)[:120]}".replace("\n", " "))
			frappe.db.rollback()
	print("APPLY-OK (%d):" % len(ok))
	for line in ok:
		print("   ", line)
	print("APPLY-FAILED (%d):" % len(bad))
	for line in bad:
		print("   ", line)
	print("SKIPPED (%d)" % len(skipped))


def rehearse(client="Demo Rehearsal"):
	"""Answer every question on a scratch onboarding and build every step.

	This is the dress rehearsal: it finds the steps that cannot be built at
	all, which is what a demo discovers in front of an audience. It rolls
	everything back at the end, so the site is as it was.
	"""
	frappe.set_user("Administrator")
	for old in frappe.get_all("Embark Onboarding", filters={"client_name": client}, pluck="name"):
		frappe.delete_doc("Embark Onboarding", old, force=True, ignore_permissions=True)
	doc = frappe.get_doc(
		{"doctype": "Embark Onboarding", "client_name": client, "consultant": "Administrator"}
	).insert(ignore_permissions=True)

	# Answer the lot, the way a customer eventually would.
	for _round in range(40):
		doc.reload()
		board = wizard.board(doc)
		todo = {}
		for task in board["tasks"]:
			for q in task["questions"]:
				if q["answer"]:
					continue
				if q["type"] == "Multiple Choice":
					todo[q["key"]] = ",".join(c["value"] for c in q["choices"])
				elif q["choices"]:
					todo[q["key"]] = q["choices"][0]["value"]
				elif q["type"] == "Number":
					todo[q["key"]] = "5"
				elif q["type"] == "Date":
					todo[q["key"]] = "2026-04-01"
				elif q["type"] == "Link":
					# What the product would actually offer, so the rehearsal
					# cannot pick something the screen never shows.
					from embark import api

					rows = api.suggestions(q["link_doctype"]) if q["link_doctype"] else []
					todo[q["key"]] = rows[0] if rows else ""
				elif q["key"] == "company_abbr":
					todo[q["key"]] = "DRH"
				else:
					todo[q["key"]] = f"Rehearsal {q['key'][:18]}"
		todo = {k: v for k, v in todo.items() if v}
		if not todo:
			break
		wizard.save_answers(doc, todo)

	doc.reload()
	board = wizard.board(doc)
	ok, bad, nothing = [], [], []
	for task in board["tasks"]:
		doc.reload()
		if not wizard._records(doc, task["task"]):
			nothing.append(task["title"])
			continue
		try:
			out = wizard.apply(doc, task["task"])
			ok.append(f"{task['title']} -> " + ", ".join(f"{r['doctype']} {r['name']}" for r in out["records"]))
		except Exception as e:
			bad.append(f"{task['title']} -> {type(e).__name__}: {str(e)[:150]}".replace("\n", " "))

	print("REHEARSAL BUILT (%d):" % len(ok))
	for line in ok:
		print("   ", line)
	print("REHEARSAL FAILED (%d):" % len(bad))
	for line in bad:
		print("   ", line)
	print("REHEARSAL WRITES NOTHING (%d): %s" % (len(nothing), ", ".join(nothing)))
	frappe.db.rollback()
	print("REHEARSAL rolled back")


def why_nothing(onboarding="ONB-2026-0003"):
	"""Which steps write nothing, and whether that is right."""
	doc = frappe.get_doc("Embark Onboarding", onboarding)
	board = wizard.board(doc)
	for task in board["tasks"]:
		writes = [q for q in task["questions"] if q["field"]]
		if writes:
			continue
		keys = ", ".join(q["key"] for q in task["questions"])
		print(f"NOTHING  {task['title']}: {keys}")


def step(title, onboarding="ONB-2026-0003"):
	"""One step as the screen sees it."""
	doc = frappe.get_doc("Embark Onboarding", onboarding)
	board = wizard.board(doc)
	task = next((t for t in board["tasks"] if t["title"] == title), None)
	if not task:
		print("STEP not shown:", title)
		return
	print(f"STEP {title}: {task['answered']}/{task['total']} state={task['state']} doctype={task['doctype']}")
	for q in task["questions"]:
		print(f"   {q['key']}: field={q['field'] or 'NONE'} doctype={q['doctype']} answer={q['answer']!r}")


def audit():
	"""Which questions configure something, which decide something, which do neither."""
	import re

	rows = frappe.get_all(
		"Embark Wizard Question",
		filters={"is_active": 1},
		fields=["name", "task", "label", "fieldname", "applies_when"],
	)
	conditions = " ".join(r.applies_when or "" for r in rows)
	order = {
		t.name: t.sequence
		for t in frappe.get_all(
			"Embark Wizard Task", filters={"is_active": 1}, fields=["name", "sequence"]
		)
	}

	writes, gates, idle = [], [], []
	for r in rows:
		if r.fieldname:
			writes.append(r)
		elif re.search(r"\b%s\b" % re.escape(r.name), conditions):
			gates.append(r)
		else:
			idle.append(r)

	print(f"AUDIT configures={len(writes)} decides={len(gates)} neither={len(idle)}")
	by_task = {}
	for r in idle:
		by_task.setdefault(r.task, []).append(f"{r.name} — {r.label[:58]}")
	for task in sorted(by_task, key=lambda t: order.get(t, 999)):
		print(f"IDLE {task}")
		for line in by_task[task]:
			print(f"      {line}")


def shape():
	"""What the wizard is made of now."""
	q = frappe.db.count("Embark Wizard Question", {"is_active": 1})
	tasks = frappe.get_all(
		"Embark Wizard Task", filters={"is_active": 1}, fields=["name", "kind"], order_by="sequence"
	)
	asked = [t.name for t in tasks if t.kind != "Work"]
	work = [t.name for t in tasks if t.kind == "Work"]
	print(f"SHAPE {q} questions across {len(asked)} question steps, and {len(work)} work steps")
	print("WORK " + " | ".join(work))


def check_bank(path="_bank_v2_check.json"):
	"""Does every question in a proposed bank point at something real?"""
	import json
	import pathlib

	rows = json.loads((pathlib.Path(frappe.get_app_path("embark")) / "data" / path).read_text())
	bad_dt, bad_field, bad_choice = [], [], []
	for r in rows:
		dt, fn = r["target_doctype"], r["fieldname"]
		if not frappe.db.exists("DocType", dt):
			bad_dt.append(f"{r['question_key']} -> {dt}")
			continue
		meta = frappe.get_meta(dt)
		field = meta.get_field(fn) if fn else None
		if fn and not field:
			bad_field.append(f"{r['question_key']} -> {dt}.{fn}")
			continue
		if r["answer_type"] == "Select" and field and field.fieldtype == "Select" and field.options:
			theirs = [o for o in (r["options"] or "").split("\n") if o]
			real = [o for o in (field.options or "").split("\n") if o]
			missing = [o for o in theirs if o not in real]
			if missing:
				bad_choice.append(f"{r['question_key']}: {missing} not in {real[:4]}")
	print(f"BANKCHECK {len(rows)} questions | missing doctypes {len(bad_dt)} | missing fields {len(bad_field)} | bad choices {len(bad_choice)}")
	for line in bad_dt + bad_field + bad_choice:
		print("   ", line)
