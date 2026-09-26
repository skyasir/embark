"""What the two chats both need from a model's reply.

Small models often write a tool call into the message instead of making one:

    {"name": "save_answers", "parameters": {"answers": {"keeps_stock": "yes"}}}

The API says there were no tool calls, so the loop ends and the customer is
shown that JSON. Reading it back turns it into the call the model meant, and
whatever is left is checked before it reaches a screen: a chat should never
show its own plumbing.
"""

from __future__ import annotations

import json
import re

# {"name": "…", "parameters"|"arguments"|"input": {…}}, possibly fenced in
# ```json, possibly with a sentence around it.
CALL = re.compile(r"\{.*?\"name\"\s*:\s*\"(?P<name>[a-z_]+)\".*\}", re.S | re.I)


def recovered_calls(text: str) -> list[dict]:
	"""Tool calls a model wrote as text, in the shape the loop expects."""
	if not text or '"name"' not in text:
		return []

	for candidate in _candidates(text):
		try:
			data = json.loads(candidate)
		except ValueError:
			continue
		for call in data if isinstance(data, list) else [data]:
			if not isinstance(call, dict) or not call.get("name"):
				continue
			arguments = call.get("parameters") or call.get("arguments") or call.get("input") or {}
			if isinstance(arguments, str):
				try:
					arguments = json.loads(arguments)
				except ValueError:
					arguments = {}
			return [{"id": f"recovered-{call['name']}", "name": call["name"], "arguments": arguments}]
	return []


def _candidates(text: str) -> list[str]:
	text = text.strip()
	out = [text]
	fenced = re.findall(r"```(?:json)?\s*(.+?)```", text, re.S)
	out.extend(f.strip() for f in fenced)
	match = CALL.search(text)
	if match:
		out.append(match.group(0))
	return out


def looks_like_plumbing(text: str) -> bool:
	"""Is this the model's machinery rather than something to read?"""
	stripped = (text or "").strip()
	if not stripped:
		return False
	return bool(
		(stripped.startswith("{") and stripped.endswith("}"))
		or (stripped.startswith("[") and stripped.endswith("]"))
		or re.search(r'"(?:name|parameters|arguments|tool_calls)"\s*:', stripped)
	)
