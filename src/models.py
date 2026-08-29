"""Shared vocabulary for ScopeKeeper: the fixed sets of values the model
is allowed to choose from, and the plain data shapes used everywhere else.

Keeping these in one place means validation.py, tools.py and agent.py all
agree on what a valid classification/confidence value looks like.
"""

from dataclasses import dataclass, field
from typing import List, Optional

CLASSIFICATIONS = ("IN_SCOPE", "PARTIALLY_IN_SCOPE", "OUT_OF_SCOPE", "NEEDS_CLARIFICATION")
CONFIDENCE_LEVELS = ("HIGH", "MEDIUM", "LOW")
DRIFT_LEVELS = ("LOW", "MODERATE", "HIGH", "CRITICAL")

MAX_HOURS_ESTIMATE = 500
MAX_LIST_ITEMS = 8
MAX_ITEM_LENGTH = 60
MAX_DESCRIPTION_LENGTH = 300
MAX_REASONING_LENGTH = 500


@dataclass
class RequestRecord:
    """One client request, after the agent has classified it."""

    index: int
    description: str
    hours_estimate: float
    classification: str
    affected_deliverables: List[str]
    new_capabilities: List[str]
    reasoning: str
    confidence: str

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "description": self.description,
            "hours_estimate": self.hours_estimate,
            "classification": self.classification,
            "affected_deliverables": self.affected_deliverables,
            "new_capabilities": self.new_capabilities,
            "reasoning": self.reasoning,
            "confidence": self.confidence,
        }


@dataclass
class DriftStats:
    """Deterministic numbers computed from the request history. Nothing
    here comes from the model - it's plain arithmetic over stored facts."""

    total_requests: int = 0
    extra_hours: float = 0.0
    percentage_increase: float = 0.0
    out_of_scope_count: int = 0
    partially_in_scope_count: int = 0
    needs_clarification_count: int = 0
    capability_groups: List[str] = field(default_factory=list)
    drift_score: float = 0.0
    drift_level: str = "LOW"

    def to_dict(self) -> dict:
        return {
            "total_requests": self.total_requests,
            "extra_hours": round(self.extra_hours, 1),
            "percentage_increase": round(self.percentage_increase, 1),
            "out_of_scope_count": self.out_of_scope_count,
            "partially_in_scope_count": self.partially_in_scope_count,
            "needs_clarification_count": self.needs_clarification_count,
            "capability_groups": self.capability_groups,
            "drift_score": round(self.drift_score, 1),
            "drift_level": self.drift_level,
        }
