"""ScopeKeeper's plan-act loop.

Setting up the original deal (start_project) is plain data entry - there
is nothing for the model to decide there, so it is a normal Python method,
not a tool. The two tools the model actually chooses to call are
log_request and get_scope_status; everything about how a new client
request is classified happens through those tool-call arguments, which
Python then validates and stores.

Design choices worth remembering for the viva:
  - temperature is low (0.2) because this agent needs consistent
    judgement calls, not creative writing - but not zero, so it can
    still phrase two similar requests slightly differently rather than
    getting stuck repeating itself.
  - the system prompt and tool schemas are the only large, fixed cost
    per call; the state sent each turn is a short summary
    (ProjectState.compact_context), not the full request history - the
    model asks for that via get_scope_status only when it needs it.
  - the loop is capped, and stops immediately if the model tries the
    exact same tool call twice in a row, instead of spending API calls
    on a repeat.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

from memory import ProjectState
from tools import ScopeTools

load_dotenv()

SYSTEM_PROMPT = """You are ScopeKeeper, an assistant that helps a freelancer or small \
agency notice when a project is growing beyond what was originally agreed.

You are not a general chatbot. Your job is to act on the project state using your tools, \
not just to talk about it.

You have exactly two tools:
1. log_request(description, hours_estimate, classification, affected_deliverables, \
new_capabilities, reasoning, confidence)
2. get_scope_status()

Whenever the user describes a NEW client request, you must:
- Compare it against the project's deliverables and exclusions (given below).
- Decide a classification: IN_SCOPE, PARTIALLY_IN_SCOPE, OUT_OF_SCOPE, or NEEDS_CLARIFICATION.
  - Use NEEDS_CLARIFICATION when the request is too vague to judge responsibly - do not \
guess just to avoid saying you're unsure. A request that names a specific, concrete feature \
or change (e.g. "add a contact form", "add customer login") can be judged. A request that \
does NOT name a specific feature (e.g. "make it better", "make it more modern", "add a \
booking feature" without saying what kind of booking) cannot be judged responsibly - use \
NEEDS_CLARIFICATION for these even if you could make an educated guess.
  - The IN_SCOPE vs PARTIALLY_IN_SCOPE line: a request that only changes CONTENT or STYLE on an \
already-included page (more list items, different text, a different photo, a different color or \
font, more revisions of something already built) is IN_SCOPE. A request that adds a new piece of \
INTERACTIVE FUNCTIONALITY to an already-included page (a filter/search box, a downloadable file, \
an embedded third-party widget like a map, a form with logic beyond "send me a message") is \
PARTIALLY_IN_SCOPE, even though it lives on a page that's already in scope - the page is included, \
but this specific behaviour was not.
  - Worked examples: "add three more dishes to the menu page" -> IN_SCOPE (more content, same \
structure). "add a search box to filter the menu" -> PARTIALLY_IN_SCOPE (new interactive feature \
on an included page). "add a downloadable PDF of the menu" -> PARTIALLY_IN_SCOPE (a new artifact, \
not just edited content). "change the button color" -> IN_SCOPE (pure style).
- List which existing deliverables it touches (affected_deliverables), and name any \
genuinely NEW capability it introduces (new_capabilities) - for a simple content or \
styling tweak, new_capabilities should be empty.
- Give a short, honest reasoning that refers only to the project state and the request \
itself. Never invent scope details, prices, or deadlines that were not given to you.
- Estimate the extra hours this would take (hours_estimate) - make clear in your reasoning \
that this is an estimate, not a contractual number.
- Then call log_request with all of this.

When asked whether the project is drifting, whether to worry, or what to do next, call \
get_scope_status() first and base your answer only on the numbers and history it returns. \
Pay attention to drift_level: LOW/MODERATE are usually fine to mention in passing, HIGH or \
CRITICAL deserve a clear warning and a recommendation (for example: re-negotiate scope, \
propose a change order, or confirm with the client before continuing). Also look at how \
many distinct new capability groups have appeared across all requests - that is often the \
real signal that the project has quietly become a different project, even if no single \
request looked alarming on its own.

Never claim you called a tool when you did not. If information is missing, say so plainly \
instead of filling it in.
"""


class ScopeKeeperAgent:
    def __init__(self, model: Optional[str] = None, fallback_model: Optional[str] = None):
        token = os.getenv("GROQ_API_KEY") or os.getenv("GITHUB_TOKEN")
        if not token:
            raise RuntimeError(
                "API key is missing. Set GROQ_API_KEY (or GITHUB_TOKEN) in your .env file."
            )
        endpoint = os.getenv("GROQ_API_ENDPOINT") or os.getenv(
            "GITHUB_MODELS_ENDPOINT", "https://models.github.ai/inference"
        )
        self.model = model or os.getenv("MODEL", "openai/gpt-oss-120b")
        self.fallback_model = fallback_model or os.getenv("FALLBACK_MODEL", "openai/gpt-oss-20b")
        self.client = OpenAI(base_url=endpoint, api_key=token)

        self.state = ProjectState()
        self.tools = ScopeTools(self.state)
        self.trace: List[Dict[str, Any]] = []

    # ---- one-time setup: plain data entry, not a model decision ----
    def start_project(
        self,
        name: str,
        objective: str,
        budget: float,
        estimated_hours: float,
        deliverables: List[str],
        exclusions: Optional[List[str]] = None,
        currency: str = "INR",
        deadline: Optional[str] = None,
    ) -> None:
        self.state.name = name
        self.state.objective = objective
        self.state.budget = budget
        self.state.currency = currency
        self.state.estimated_hours = estimated_hours
        self.state.deadline = deadline
        self.state.deliverables = list(deliverables)
        self.state.exclusions = list(exclusions or [])

    # ---- tool schemas ----
    def _tool_schemas(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "log_request",
                    "description": "Store a classified client request against the project.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"},
                            "hours_estimate": {"type": "number"},
                            "classification": {
                                "type": "string",
                                "enum": ["IN_SCOPE", "PARTIALLY_IN_SCOPE", "OUT_OF_SCOPE", "NEEDS_CLARIFICATION"],
                            },
                            "affected_deliverables": {"type": "array", "items": {"type": "string"}},
                            "new_capabilities": {"type": "array", "items": {"type": "string"}},
                            "reasoning": {"type": "string"},
                            "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                        },
                        "required": [
                            "description",
                            "hours_estimate",
                            "classification",
                            "reasoning",
                            "confidence",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_scope_status",
                    "description": "Get the original scope, full request history, and current cumulative drift numbers.",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
        ]

    def _call_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        if name == "log_request":
            return self.tools.log_request(**args)
        if name == "get_scope_status":
            return self.tools.get_scope_status()
        return {"status": "error", "message": f"Unknown tool: {name}"}

    def _complete(self, messages: List[Dict[str, Any]], model: str):
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            tools=self._tool_schemas(),
            tool_choice="auto",
            temperature=0.2,
            max_tokens=600,
        )

    def _complete_with_retry(self, messages: List[Dict[str, Any]]):
        try:
            return self._complete(messages, self.model)
        except Exception as first_error:
            # A rate limit needs a real pause, not a quick retry that just hits the
            # same limit again - a fixed short sleep would look like it's "handling"
            # the error while actually wasting the one retry we get.
            wait_seconds = 8 if "429" in str(first_error) or "rate" in str(first_error).lower() else 1.5
            time.sleep(wait_seconds)
            try:
                return self._complete(messages, self.model)
            except Exception:
                return self._complete(messages, self.fallback_model)

    def run(self, user_message: str, max_iterations: int = 4) -> str:
        self.trace = []
        self.state.add_message("user", user_message)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": "Current project state:\n" + self.state.compact_context()},
        ]
        messages.extend(self.state.recent_messages())

        last_call_signature = None

        for step in range(1, max_iterations + 1):
            try:
                response = self._complete_with_retry(messages)
            except Exception as exc:
                answer = f"Sorry - the model API is unavailable right now ({exc}). Please try again shortly."
                self.trace.append({"step": step, "type": "api_error", "message": str(exc)})
                return answer

            msg = response.choices[0].message
            assistant_message: Dict[str, Any] = {"role": "assistant", "content": msg.content or ""}

            if not msg.tool_calls:
                answer = msg.content or "I completed the request."
                self.state.add_message("assistant", answer)
                self.trace.append({"step": step, "type": "final", "message": answer})
                return answer

            assistant_message["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in msg.tool_calls
            ]
            messages.append(assistant_message)

            for call in msg.tool_calls:
                name = call.function.name
                try:
                    args = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                signature = (name, json.dumps(args, sort_keys=True))
                if signature == last_call_signature:
                    answer = (
                        "I tried the same action twice in a row without new information, "
                        "so I'm stopping here instead of repeating myself. "
                        "Please give me a bit more detail and I'll try again."
                    )
                    self.trace.append({"step": step, "type": "stuck", "tool": name, "arguments": args})
                    self.state.add_message("assistant", answer)
                    return answer
                last_call_signature = signature

                self.trace.append({"step": step, "type": "tool_call", "tool": name, "arguments": args})

                try:
                    result = self._call_tool(name, args)
                except Exception as exc:
                    result = {"status": "error", "message": f"Tool crashed: {exc}"}

                self.trace.append({"step": step, "type": "tool_result", "tool": name, "result": result})

                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
                )

        answer = "I could not finish within the allowed number of steps. Please try a more specific request."
        self.state.add_message("assistant", answer)
        self.trace.append({"step": max_iterations, "type": "final", "message": answer})
        return answer
