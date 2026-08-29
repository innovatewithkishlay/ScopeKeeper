"""The two tools ScopeKeeper is allowed to call.

log_request stores a client request the model has already classified, and
recomputes the running drift numbers. get_scope_status hands back the
full current picture. Neither function calls the model - they only read
and write ProjectState and run the deterministic math in drift.py. This
is the "Python does the deterministic part" half of the hybrid design;
agent.py is where the model's classification actually gets produced.
"""

from typing import Any, Dict

import drift
from memory import ProjectState
from models import RequestRecord
from validation import validate_log_request_args


class ScopeTools:
    def __init__(self, state: ProjectState):
        self.state = state

    def log_request(self, **args: Any) -> Dict[str, Any]:
        if not self.state.is_initialized():
            return {"status": "error", "message": "No project scope has been set up yet."}

        ok, cleaned = validate_log_request_args(args)
        if not ok:
            return {"status": "error", "message": cleaned["message"]}

        existing = self.state.find_duplicate(cleaned["description"])
        if existing is not None:
            return {
                "status": "duplicate",
                "message": f"This exact request was already logged as request #{existing.index}. Not counted again.",
                "existing_request": existing.to_dict(),
            }

        record = RequestRecord(
            index=self.state.next_request_index(),
            description=cleaned["description"],
            hours_estimate=cleaned["hours_estimate"],
            classification=cleaned["classification"],
            affected_deliverables=cleaned["affected_deliverables"],
            new_capabilities=cleaned["new_capabilities"],
            reasoning=cleaned["reasoning"],
            confidence=cleaned["confidence"],
        )
        self.state.add_request(record)

        stats = drift.compute_stats(self.state.requests, self.state.estimated_hours)
        return {
            "status": "logged",
            "request": record.to_dict(),
            "updated_status": stats.to_dict(),
        }

    def get_scope_status(self, **_ignored: Any) -> Dict[str, Any]:
        if not self.state.is_initialized():
            return {"status": "error", "message": "No project scope has been set up yet."}

        stats = drift.compute_stats(self.state.requests, self.state.estimated_hours)
        return {
            "status": "ok",
            "project": {
                "name": self.state.name,
                "objective": self.state.objective,
                "budget": self.state.budget,
                "currency": self.state.currency,
                "estimated_hours": self.state.estimated_hours,
                "deadline": self.state.deadline,
                "deliverables": self.state.deliverables,
                "exclusions": self.state.exclusions,
            },
            "requests": [r.to_dict() for r in self.state.requests],
            "cumulative": stats.to_dict(),
        }
