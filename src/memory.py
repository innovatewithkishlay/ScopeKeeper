"""ScopeKeeper's memory.

This is deliberately NOT "send the whole conversation back to the model
every time." The facts that actually matter (the original deal, the
deliverables, every request logged so far) live in a structured object
below. A short rolling conversation log is kept only so the model has
enough of the recent back-and-forth to sound natural - the facts it needs
to reason correctly always come from ProjectState, not from re-reading
old chat turns.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from models import RequestRecord


@dataclass
class ProjectState:
    """The one source of truth for a project. Everything the agent knows
    about the deal lives here, and it survives across every turn."""

    name: Optional[str] = None
    objective: Optional[str] = None
    budget: Optional[float] = None
    currency: str = "INR"
    estimated_hours: Optional[float] = None
    deadline: Optional[str] = None
    deliverables: List[str] = field(default_factory=list)
    exclusions: List[str] = field(default_factory=list)

    # Set once the project has been saved to (or loaded from) the database -
    # this is what lets a later session write new requests to the same
    # project row instead of creating a duplicate.
    project_id: Optional[int] = None

    requests: List[RequestRecord] = field(default_factory=list)
    conversation: List[dict] = field(default_factory=list)

    def is_initialized(self) -> bool:
        return self.name is not None and self.estimated_hours is not None

    def next_request_index(self) -> int:
        return len(self.requests) + 1

    def add_request(self, record: RequestRecord) -> None:
        self.requests.append(record)

    def find_duplicate(self, description: str) -> Optional[RequestRecord]:
        """Exact match only, after trimming whitespace and case - not fuzzy
        matching. Good enough to catch a client re-sending the same ask
        twice without risking a false match on two genuinely different
        requests that just happen to share a few words."""
        normalized = " ".join(description.strip().lower().split())
        for r in self.requests:
            if " ".join(r.description.strip().lower().split()) == normalized:
                return r
        return None

    def add_message(self, role: str, content: str) -> None:
        self.conversation.append({"role": role, "content": content})

    def recent_messages(self, limit: int = 6) -> List[dict]:
        return self.conversation[-limit:]

    def compact_context(self) -> str:
        """A short, plain-English summary of the deal, sent to the model
        every turn instead of a full JSON dump of everything. Request
        history is deliberately left out here - the model calls
        get_scope_status() when it actually needs those details, instead
        of every message carrying the full history whether it's needed
        or not."""
        if not self.is_initialized():
            return "No project has been set up yet."

        lines = [
            f"Project: {self.name}",
            f"Objective: {self.objective}",
            f"Budget: {self.currency} {self.budget}",
            f"Estimated effort: {self.estimated_hours} hours",
        ]
        if self.deadline:
            lines.append(f"Deadline: {self.deadline}")
        lines.append(f"Included deliverables: {', '.join(self.deliverables) or 'none listed'}")
        lines.append(f"Explicitly excluded: {', '.join(self.exclusions) or 'none stated'}")
        lines.append(f"Requests logged so far: {len(self.requests)}")
        return "\n".join(lines)

    def snapshot(self) -> dict:
        return {
            "project": {
                "name": self.name,
                "objective": self.objective,
                "budget": self.budget,
                "currency": self.currency,
                "estimated_hours": self.estimated_hours,
                "deadline": self.deadline,
                "deliverables": self.deliverables,
                "exclusions": self.exclusions,
            },
            "requests": [r.to_dict() for r in self.requests],
            "conversation_messages": len(self.conversation),
        }
