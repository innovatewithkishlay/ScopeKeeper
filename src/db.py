"""Persistent storage for ScopeKeeper, using SQLite (Python's built-in
database - no extra service to install or run).

This is what makes the agent's memory survive closing the notebook: without
this file, everything lives in a plain Python object that disappears the
moment the process exits. With it, every project and every classified
request is written to a real database file (scopekeeper.db) as it happens,
so a brand new ScopeKeeperAgent() in a brand new session can load a project
back exactly as it was left.

This is retrieval-based memory, not model fine-tuning: nothing here changes
the AI model's weights. What it does is let the agent look up how it (or a
past session) classified similar requests before, and use that as reference
context for a new decision - the same idea a human would use flipping back
through their own notes, not the model "learning" in the machine-learning
sense.
"""

import json
import os
import re
import sqlite3
from contextlib import contextmanager
from typing import List, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scopekeeper.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    objective TEXT,
    budget REAL,
    currency TEXT,
    estimated_hours REAL,
    deadline TEXT,
    deliverables TEXT,      -- JSON list
    exclusions TEXT,        -- JSON list
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    description TEXT NOT NULL,
    hours_estimate REAL,
    classification TEXT,
    affected_deliverables TEXT,   -- JSON list
    new_capabilities TEXT,        -- JSON list
    reasoning TEXT,
    confidence TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_project(name, objective, budget, currency, estimated_hours, deadline, deliverables, exclusions) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, objective, budget, currency, estimated_hours, deadline, deliverables, exclusions) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, objective, budget, currency, estimated_hours, deadline, json.dumps(deliverables), json.dumps(exclusions)),
        )
        return cur.lastrowid


def save_request(project_id: int, record) -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO requests (project_id, description, hours_estimate, classification, "
            "affected_deliverables, new_capabilities, reasoning, confidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_id,
                record.description,
                record.hours_estimate,
                record.classification,
                json.dumps(record.affected_deliverables),
                json.dumps(record.new_capabilities),
                record.reasoning,
                record.confidence,
            ),
        )
        return cur.lastrowid


def list_projects() -> List[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT id, name, budget, currency, estimated_hours, created_at, "
            "(SELECT COUNT(*) FROM requests WHERE requests.project_id = projects.id) AS request_count "
            "FROM projects ORDER BY created_at DESC"
        ).fetchall()


def load_project(project_id: int) -> Optional[dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            return None
        requests = conn.execute(
            "SELECT * FROM requests WHERE project_id = ? ORDER BY id ASC", (project_id,)
        ).fetchall()
        return {
            "id": row["id"],
            "name": row["name"],
            "objective": row["objective"],
            "budget": row["budget"],
            "currency": row["currency"],
            "estimated_hours": row["estimated_hours"],
            "deadline": row["deadline"],
            "deliverables": json.loads(row["deliverables"]),
            "exclusions": json.loads(row["exclusions"]),
            "requests": [
                {
                    "description": r["description"],
                    "hours_estimate": r["hours_estimate"],
                    "classification": r["classification"],
                    "affected_deliverables": json.loads(r["affected_deliverables"]),
                    "new_capabilities": json.loads(r["new_capabilities"]),
                    "reasoning": r["reasoning"],
                    "confidence": r["confidence"],
                }
                for r in requests
            ],
        }


def _words(text: str) -> set:
    """Lowercase, strip punctuation, and treat a trailing 's' as a plural so
    'accounts' matches 'account' - still one sentence to explain (not
    stemming or embeddings), but without this a stray '?' or a plural was
    enough to silently produce zero matches, which is worse than useless in
    a demo meant to show the mechanism working."""
    raw = re.findall(r"[a-z0-9]+", text.lower())
    out = set()
    for w in raw:
        if len(w) <= 3:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 else w)
    return out


def find_similar_past_requests(description: str, limit: int = 3, exclude_project_id: Optional[int] = None) -> List[dict]:
    """A deliberately simple retrieval step: score every past request by how
    many words it shares with the new one, and return the closest few. This
    is word-overlap, not embeddings - transparent enough to explain in one
    sentence, and good enough to surface genuinely similar past decisions."""
    words = _words(description)
    if not words:
        return []

    with _connect() as conn:
        rows = conn.execute(
            "SELECT r.description, r.classification, r.reasoning, p.name AS project_name "
            "FROM requests r JOIN projects p ON r.project_id = p.id"
        ).fetchall()

    scored = []
    for row in rows:
        if exclude_project_id is not None:
            pass  # kept simple: cross-project matches are allowed and useful, not excluded
        row_words = _words(row["description"])
        overlap = len(words & row_words)
        if overlap > 0:
            scored.append((overlap, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "project_name": row["project_name"],
            "description": row["description"],
            "classification": row["classification"],
            "reasoning": row["reasoning"],
        }
        for _, row in scored[:limit]
    ]
