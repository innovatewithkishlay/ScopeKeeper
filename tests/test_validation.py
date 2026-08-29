"""Tests for validation.py - making sure malformed or out-of-range tool
arguments from the model are rejected with a clear message instead of
being stored as if they were trustworthy."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from validation import validate_log_request_args

GOOD_ARGS = {
    "description": "Add a contact form to the contact page.",
    "hours_estimate": 2,
    "classification": "IN_SCOPE",
    "reasoning": "Simple form addition to an already-included page.",
    "confidence": "HIGH",
    "affected_deliverables": ["Contact page"],
    "new_capabilities": [],
}


def test_valid_args_pass():
    ok, cleaned = validate_log_request_args(GOOD_ARGS)
    assert ok is True
    assert cleaned["classification"] == "IN_SCOPE"


def test_missing_description_fails():
    args = dict(GOOD_ARGS, description="")
    ok, result = validate_log_request_args(args)
    assert ok is False
    assert "description" in result["message"]


def test_invalid_classification_fails():
    args = dict(GOOD_ARGS, classification="MAYBE_SCOPE")
    ok, result = validate_log_request_args(args)
    assert ok is False
    assert "classification" in result["message"]


def test_negative_hours_fails():
    args = dict(GOOD_ARGS, hours_estimate=-3)
    ok, result = validate_log_request_args(args)
    assert ok is False


def test_hours_above_cap_fails():
    args = dict(GOOD_ARGS, hours_estimate=10000)
    ok, result = validate_log_request_args(args)
    assert ok is False


def test_non_numeric_hours_fails():
    args = dict(GOOD_ARGS, hours_estimate="a lot")
    ok, result = validate_log_request_args(args)
    assert ok is False


def test_invalid_confidence_fails():
    args = dict(GOOD_ARGS, confidence="VERY_SURE")
    ok, result = validate_log_request_args(args)
    assert ok is False


def test_non_list_capabilities_fails():
    args = dict(GOOD_ARGS, new_capabilities="authentication")
    ok, result = validate_log_request_args(args)
    assert ok is False


def test_missing_reasoning_fails():
    args = dict(GOOD_ARGS)
    del args["reasoning"]
    ok, result = validate_log_request_args(args)
    assert ok is False


if __name__ == "__main__":
    test_valid_args_pass()
    test_missing_description_fails()
    test_invalid_classification_fails()
    test_negative_hours_fails()
    test_hours_above_cap_fails()
    test_non_numeric_hours_fails()
    test_invalid_confidence_fails()
    test_non_list_capabilities_fails()
    test_missing_reasoning_fails()
    print("All validation tests passed.")
