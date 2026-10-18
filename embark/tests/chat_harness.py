"""Run real conversations through Ask Embark and report what it actually did.

Not a unit test: this talks to whatever model the site is configured with. It
is how you find out whether the chat is any use, which a stubbed test can
never tell you — a model that replies pleasantly and writes nothing down
passes every unit test there is.

	bench --site <site> console
	>>> from embark.tests import chat_harness
	>>> chat_harness.report("flow")     # or "embark" for the built-in loop

It makes its own onboarding, so it never touches a real one.
"""

import json
import time

import frappe


def fresh(client="Harness Traders"):
	"""A clean onboarding, so every run starts from the same place."""
	frappe.set_user("Administrator")
	for old in frappe.get_all("Embark Onboarding", filters={"client_name": client}, pluck="name"):
		frappe.delete_doc("Embark Onboarding", old, force=True, ignore_permissions=True)
	doc = frappe.get_doc(
		{"doctype": "Embark Onboarding", "client_name": client, "consultant": "Administrator"}
	).insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def answers_of(onboarding):
	doc = frappe.get_doc("Embark Onboarding", onboarding)
	return {row.question: row.value for row in doc.wizard_answers}


SCENARIOS = [
	{
		"say": "What should I do next?",
		"expect": "asks a real setup question rather than asking the customer where they are",
		"check": lambda reply, steps, before, after: (
			"?" in reply and not _asks_where(reply),
			f"reply={reply[:120]!r}",
		),
	},
	{
		"say": "The company is called Harness Traders Private Limited.",
		"expect": "saves that as the company name",
		"check": lambda reply, steps, before, after: (
			after.get("company_name", "").lower().startswith("harness traders"),
			f"company_name={after.get('company_name')!r}",
		),
	},
	{
		"say": "We are in India and we keep our books in rupees.",
		"expect": "saves country and currency",
		"check": lambda reply, steps, before, after: (
			bool(after.get("company_country")) and bool(after.get("company_currency")),
			f"country={after.get('company_country')!r} currency={after.get('company_currency')!r}",
		),
	},
	{
		"say": "How many questions are left?",
		"expect": "answers with a number instead of asking a question back",
		"check": lambda reply, steps, before, after: (
			any(ch.isdigit() for ch in reply) and not _asks_where(reply),
			f"reply={reply[:120]!r}",
		),
	},
]


def _asks_where(reply):
	"""The failure that makes it useless: handing the question back."""
	lowered = (reply or "").lower()
	# Asking a setup question is the job. The failure is handing back the
	# question of where things stand, which it is told before every message.
	return any(
		phrase in lowered
		for phrase in (
			"where are you in",
			"where you are in",
			"what stage",
			"what would you like to do",
			"let me know what you",
			"tell me more about what you",
			"could you please specify where",
		)
	)


def run(engine="flow"):
	from embark import api, assistant

	frappe.local.conf["embark_engine"] = engine
	onboarding = fresh()
	history, results = [], []

	for scenario in SCENARIOS:
		before = answers_of(onboarding)
		started = time.time()
		try:
			out = api.ask(message=scenario["say"], onboarding=onboarding, history=json.dumps(history))
			reply, steps = out.get("reply") or "", out.get("steps") or []
		except Exception as e:
			reply, steps = f"<failed: {e}>", []
		frappe.db.commit()
		after = answers_of(onboarding)

		passed, detail = scenario["check"](reply, steps, before, after)
		results.append(
			{
				"said": scenario["say"],
				"expected": scenario["expect"],
				"passed": passed,
				"detail": detail,
				"tools": [s.get("tool") for s in steps],
				"seconds": round(time.time() - started, 1),
				"reply": reply[:200],
			}
		)
		history += [{"role": "user", "content": scenario["say"]}, {"role": "assistant", "content": reply}]

	return results


def report(engine="flow"):
	results = run(engine)
	print("\n" + "=" * 72)
	for r in results:
		print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['said']}")
		print(f"      expected: {r['expected']}")
		print(f"      tools:    {r['tools'] or 'none called'}   ({r['seconds']}s)")
		print(f"      {r['detail']}")
		print(f"      said: {r['reply']!r}")
		print("-" * 72)
	passed = sum(1 for r in results if r["passed"])
	print(f"RESULT {passed} of {len(results)} passed on engine={engine}")
	return results
