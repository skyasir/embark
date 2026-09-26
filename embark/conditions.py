"""When a data step or a column applies, judged from the customer's answers.

Consultants write these in the desk, so the language is deliberately small:

    keeps_stock == yes
    tracks_batches == yes or tracks_serials == yes
    business_type == manufacturing
    keeps_stock != no

An answer holding several choices ("trading,manufacturing") is treated as a set,
so ``==`` reads as "is one of the answers".

It fails open on a question that *is* being asked but has no answer yet, or was
answered "not sure": asking for data that turns out to be unnecessary is a
smaller mistake than silently not collecting it.

A question that is not being asked at all is a different matter. "Do you track
batches?" is never asked of a business that keeps no stock, so a condition on
that answer is simply false — pass ``asked`` to get that reading.
"""

from __future__ import annotations

import re

UNKNOWN = ("", "not_sure", None)
TERM = re.compile(r"^\s*(?P<key>[a-z0-9_]+)\s*(?:(?P<op>==|!=|in)\s*(?P<value>.+?))?\s*$", re.I)


def applies(condition: str | None, answers: dict[str, str], asked: set[str] | None = None) -> bool:
	"""Is this step, column or task relevant, given the answers so far?

	``asked`` is the set of question keys the customer is actually being asked.
	A condition that reads a question outside it is false, because the interview
	has already ruled that branch out.
	"""
	condition = (condition or "").strip()
	if not condition:
		return True

	for or_part in re.split(r"\s+or\s+", condition, flags=re.I):
		if all(_term(term, answers, asked) for term in re.split(r"\s+and\s+", or_part, flags=re.I)):
			return True
	return False


def _term(term: str, answers: dict[str, str], asked: set[str] | None = None) -> bool:
	match = TERM.match(term)
	if not match:
		# An unreadable condition must not hide a step.
		return True

	key, op, value = match.group("key"), match.group("op"), match.group("value")
	if asked is not None and key not in asked:
		# The interview closed this branch. An answer left over from before it
		# closed is kept on the record, but it no longer decides anything.
		return False

	answer = answers.get(key)
	if answer in UNKNOWN:
		# Asked, but not answered yet or "not sure": fail open.
		return True

	chosen = {a.strip().lower() for a in str(answer).split(",") if a.strip()}
	if not op:
		return bool(chosen - {"no", "0", "false"})

	wanted = {v.strip().lower() for v in value.split(",") if v.strip()}
	if op in ("==", "in"):
		return bool(chosen & wanted)
	return not (chosen & wanted)


def keys_used(condition: str | None) -> list[str]:
	"""The question keys a condition reads, for validating it against the questions."""
	return [
		m.group("key")
		for m in (TERM.match(t) for t in re.split(r"\s+(?:and|or)\s+", condition or "", flags=re.I))
		if m
	]
