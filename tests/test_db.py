"""Tests for the SQLite persistence layer - no API key needed, this is
pure database logic. Uses a temporary database file so it never touches
the real scopekeeper.db a user might have local projects in."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import db
from models import RequestRecord


def _use_temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.remove(path)  # let sqlite create it fresh
    db.DB_PATH = path
    return path


def test_save_and_load_project_round_trips():
    _use_temp_db()
    project_id = db.save_project(
        name="Test project", objective="test", budget=1000, currency="INR",
        estimated_hours=10, deadline=None,
        deliverables=["Home"], exclusions=["Blog"],
    )
    loaded = db.load_project(project_id)
    assert loaded["name"] == "Test project"
    assert loaded["deliverables"] == ["Home"]
    assert loaded["exclusions"] == ["Blog"]
    assert loaded["requests"] == []


def test_save_request_persists_and_reloads():
    _use_temp_db()
    project_id = db.save_project(
        name="Test project", objective="test", budget=1000, currency="INR",
        estimated_hours=10, deadline=None, deliverables=["Home"], exclusions=[],
    )
    record = RequestRecord(
        index=1, description="Add a login page", hours_estimate=5,
        classification="OUT_OF_SCOPE", affected_deliverables=[],
        new_capabilities=["login"], reasoning="not agreed", confidence="HIGH",
    )
    db.save_request(project_id, record)

    loaded = db.load_project(project_id)
    assert len(loaded["requests"]) == 1
    assert loaded["requests"][0]["description"] == "Add a login page"
    assert loaded["requests"][0]["classification"] == "OUT_OF_SCOPE"


def test_list_projects_shows_request_count():
    _use_temp_db()
    project_id = db.save_project(
        name="Counted project", objective="test", budget=500, currency="INR",
        estimated_hours=5, deadline=None, deliverables=[], exclusions=[],
    )
    record = RequestRecord(
        index=1, description="Add a feature", hours_estimate=2,
        classification="IN_SCOPE", affected_deliverables=[], new_capabilities=[],
        reasoning="fine", confidence="HIGH",
    )
    db.save_request(project_id, record)

    rows = db.list_projects()
    match = [r for r in rows if r["id"] == project_id][0]
    assert match["request_count"] == 1


def test_find_similar_past_requests_matches_shared_words():
    _use_temp_db()
    project_id = db.save_project(
        name="Reference project", objective="test", budget=500, currency="INR",
        estimated_hours=5, deadline=None, deliverables=[], exclusions=[],
    )
    record = RequestRecord(
        index=1, description="Add customer login and account creation", hours_estimate=8,
        classification="OUT_OF_SCOPE", affected_deliverables=[], new_capabilities=["login"],
        reasoning="accounts were excluded", confidence="HIGH",
    )
    db.save_request(project_id, record)

    matches = db.find_similar_past_requests("Can customers create a login account?")
    assert len(matches) == 1
    assert matches[0]["classification"] == "OUT_OF_SCOPE"

    no_matches = db.find_similar_past_requests("Completely unrelated topic about weather forecasts")
    assert no_matches == []


if __name__ == "__main__":
    test_save_and_load_project_round_trips()
    test_save_request_persists_and_reloads()
    test_list_projects_shows_request_count()
    test_find_similar_past_requests_matches_shared_words()
    print("All db tests passed.")
