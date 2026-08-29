"""Tests for the two tools themselves, calling them directly with
hand-written arguments (standing in for what the model would send). This
never touches the network - it proves the tools behave correctly on
their own, independent of whether the model calls them correctly."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from memory import ProjectState
from tools import ScopeTools

BASE_PROJECT = dict(
    name="Restaurant marketing website",
    objective="A marketing website for a restaurant",
    budget=80000,
    estimated_hours=20,
    deliverables=["Home page", "About page", "Menu page", "Contact page", "Gallery"],
    exclusions=["online ordering", "user accounts", "payment processing"],
)


def _new_tools():
    state = ProjectState()
    state.name = BASE_PROJECT["name"]
    state.objective = BASE_PROJECT["objective"]
    state.budget = BASE_PROJECT["budget"]
    state.estimated_hours = BASE_PROJECT["estimated_hours"]
    state.deliverables = list(BASE_PROJECT["deliverables"])
    state.exclusions = list(BASE_PROJECT["exclusions"])
    return state, ScopeTools(state)


def test_log_request_before_setup_fails_cleanly():
    state = ProjectState()
    tools = ScopeTools(state)
    result = tools.log_request(
        description="Add a form",
        hours_estimate=1,
        classification="IN_SCOPE",
        reasoning="test",
        confidence="HIGH",
    )
    assert result["status"] == "error"


def test_log_request_stores_and_updates_status():
    state, tools = _new_tools()
    result = tools.log_request(
        description="Add a contact form to the contact page.",
        hours_estimate=2,
        classification="IN_SCOPE",
        reasoning="Already part of the contact page deliverable.",
        confidence="HIGH",
        affected_deliverables=["Contact page"],
        new_capabilities=[],
    )
    assert result["status"] == "logged"
    assert result["updated_status"]["total_requests"] == 1
    assert len(state.requests) == 1


def test_log_request_rejects_malformed_arguments():
    state, tools = _new_tools()
    result = tools.log_request(
        description="Add something",
        hours_estimate=-5,
        classification="IN_SCOPE",
        reasoning="test",
        confidence="HIGH",
    )
    assert result["status"] == "error"
    assert len(state.requests) == 0


def test_duplicate_request_is_not_double_counted():
    state, tools = _new_tools()
    tools.log_request(
        description="Add customer login so people can save favorites.",
        hours_estimate=6,
        classification="OUT_OF_SCOPE",
        reasoning="Introduces authentication, not part of the marketing site.",
        confidence="HIGH",
        new_capabilities=["authentication"],
    )
    result = tools.log_request(
        description="Add customer login so people can save favorites.",
        hours_estimate=6,
        classification="OUT_OF_SCOPE",
        reasoning="Introduces authentication, not part of the marketing site.",
        confidence="HIGH",
        new_capabilities=["authentication"],
    )
    assert result["status"] == "duplicate"
    assert len(state.requests) == 1


def test_get_scope_status_reflects_logged_requests():
    state, tools = _new_tools()
    tools.log_request(
        description="Add a loyalty points system.",
        hours_estimate=8,
        classification="OUT_OF_SCOPE",
        reasoning="New capability, not part of a marketing site.",
        confidence="HIGH",
        new_capabilities=["loyalty program"],
    )
    status = tools.get_scope_status()
    assert status["status"] == "ok"
    assert status["cumulative"]["out_of_scope_count"] == 1
    assert "loyalty program" in status["cumulative"]["capability_groups"]


if __name__ == "__main__":
    test_log_request_before_setup_fails_cleanly()
    test_log_request_stores_and_updates_status()
    test_log_request_rejects_malformed_arguments()
    test_duplicate_request_is_not_double_counted()
    test_get_scope_status_reflects_logged_requests()
    print("All tool tests passed.")
