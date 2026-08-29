"""Deterministic drift math. No model call happens in this file - it only
turns the request history that's already been logged into numbers and a
plain-English drift level.

Why this lives in plain Python and not in a prompt: percentages, sums and
thresholds are the kind of thing a calculator gets right every single
time and a language model sometimes doesn't. The model's job is deciding
*what a request means*; this file's job is turning those decisions into
a reliable running total.

Drift score formula (0-100), and why each piece is weighted the way it is:

  hours_component        up to 40 points - how much extra effort has
                          piled up, as a percentage of the original
                          estimate, capped at 100%.
  out_of_scope_component up to 30 points - what fraction of all requests
                          so far have been outright out of scope.
  capability_component   up to 30 points - how many distinct *new kinds*
                          of functionality have been introduced (this is
                          the piece that catches "many small requests
                          quietly add up to a different project", even
                          when no single request used much time).

  drift_score = hours_component + out_of_scope_component + capability_component

Levels: 0-24 LOW, 25-49 MODERATE, 50-74 HIGH, 75-100 CRITICAL.
These thresholds are a judgement call, not a scientific constant - they're
documented here so they can be defended and adjusted, not hidden inside a
prompt.
"""

from typing import List

from models import DriftStats, RequestRecord

CAPABILITY_CAP = 6  # capability_component maxes out once 6+ distinct groups appear


def _normalize(items: List[str]) -> List[str]:
    seen = []
    for item in items:
        key = item.strip().lower()
        if key and key not in seen:
            seen.append(key)
    return seen


def compute_stats(requests: List[RequestRecord], original_hours: float) -> DriftStats:
    stats = DriftStats()
    stats.total_requests = len(requests)

    extra_hours = sum(r.hours_estimate for r in requests if r.classification != "NEEDS_CLARIFICATION")
    stats.extra_hours = extra_hours
    stats.percentage_increase = (extra_hours / original_hours * 100) if original_hours else 0.0

    stats.out_of_scope_count = sum(1 for r in requests if r.classification == "OUT_OF_SCOPE")
    stats.partially_in_scope_count = sum(1 for r in requests if r.classification == "PARTIALLY_IN_SCOPE")
    stats.needs_clarification_count = sum(1 for r in requests if r.classification == "NEEDS_CLARIFICATION")

    all_capabilities: List[str] = []
    for r in requests:
        all_capabilities.extend(r.new_capabilities)
    stats.capability_groups = _normalize(all_capabilities)

    hours_component = min(stats.percentage_increase, 100.0) * 0.40
    out_of_scope_ratio = (stats.out_of_scope_count / stats.total_requests) if stats.total_requests else 0.0
    out_of_scope_component = out_of_scope_ratio * 30.0
    capability_component = min(len(stats.capability_groups), CAPABILITY_CAP) / CAPABILITY_CAP * 30.0

    stats.drift_score = hours_component + out_of_scope_component + capability_component

    if stats.drift_score >= 75:
        stats.drift_level = "CRITICAL"
    elif stats.drift_score >= 50:
        stats.drift_level = "HIGH"
    elif stats.drift_score >= 25:
        stats.drift_level = "MODERATE"
    else:
        stats.drift_level = "LOW"

    return stats
