"""Frappe Flow's agent engine, vendored.

Taken from https://github.com/frappe/flow_client at 4a3189b — the loop,
the model resolver and the tool decorator, with their copyright notices intact
and LICENSE.txt beside them. Frappe's, not ours.

Only the engine came across. Flow's agents, triggers, knowledge bases and desk
panel did not: Embark has its own panel, and the knowledge machinery drags in
OCR and a vector store that a customer's site has no use for.

Two changes were needed to stand it up on its own: the loop's optional session
and knowledge imports are dropped, and the model reads Embark's own provider
records rather than Flow's.

Keep the diff small. To take their fixes later, fetch the app again and diff
these files against ours.
"""

from embark.vendor.flow.agent import Agent, RunResult
from embark.vendor.flow.model import ChatResponse, Model, ToolCall
from embark.vendor.flow.tool import Tool, build_schema, tool

__all__ = ["Agent", "ChatResponse", "Model", "RunResult", "Tool", "ToolCall", "build_schema", "tool"]
