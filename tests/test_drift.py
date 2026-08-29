"""Tests for the deterministic drift math in src/drift.py. No API key or
model call needed - this is plain arithmetic over a list of RequestRecord
objects, so it can (and should) be checked without ever touching Groq."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import drift
from models import RequestRecord


def _record(index, hours, classification, capabilities=None):
    return RequestRecord(
        index=index,
        description=f"request {index}",
        hours_estimate=hours,
        classification=classification,
        affected_deliverables=[],
        new_capabilities=capabilities or [],
        reasoning="test",
        confidence="HIGH",
    )


def test_no_requests_is_low_drift():
    stats = drift.compute_stats([], original_hours=20)
    assert stats.drift_level == "LOW"
    assert stats.drift_score == 0
    assert stats.total_requests == 0


def test_small_in_scope_requests_stay_low():
    requests = [
        _record(1, 1, "IN_SCOPE"),
        _record(2, 1, "IN_SCOPE"),
    ]
    stats = drift.compute_stats(requests, original_hours=20)
    assert stats.drift_level == "LOW"
    assert stats.out_of_scope_count == 0


def test_needs_clarification_does_not_count_as_extra_hours():
    requests = [_record(1, 50, "NEEDS_CLARIFICATION")]
    stats = drift.compute_stats(requests, original_hours=20)
    assert stats.extra_hours == 0
    assert stats.needs_clarification_count == 1


def test_many_out_of_scope_requests_trigger_high_or_critical_drift():
    requests = [
        _record(1, 4, "OUT_OF_SCOPE", ["authentication"]),
        _record(2, 5, "OUT_OF_SCOPE", ["loyalty program"]),
        _record(3, 6, "OUT_OF_SCOPE", ["staff dashboard"]),
        _record(4, 6, "OUT_OF_SCOPE", ["order management"]),
    ]
    stats = drift.compute_stats(requests, original_hours=20)
    assert stats.out_of_scope_count == 4
    assert len(stats.capability_groups) == 4
    assert stats.drift_level in ("HIGH", "CRITICAL")


def test_duplicate_capability_names_are_deduplicated_case_insensitively():
    requests = [
        _record(1, 2, "OUT_OF_SCOPE", ["Authentication"]),
        _record(2, 2, "OUT_OF_SCOPE", ["authentication "]),
    ]
    stats = drift.compute_stats(requests, original_hours=20)
    assert stats.capability_groups == ["authentication"]


if __name__ == "__main__":
    test_no_requests_is_low_drift()
    test_small_in_scope_requests_stay_low()
    test_needs_clarification_does_not_count_as_extra_hours()
    test_many_out_of_scope_requests_trigger_high_or_critical_drift()
    test_duplicate_capability_names_are_deduplicated_case_insensitively()
    print("All drift tests passed.")
