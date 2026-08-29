"""Accuracy evaluation - the one part of the test suite that needs a real
model call, because it's testing whether the LLM's classification
judgement is actually any good, not just whether the Python plumbing
works.

This script does NOT print made-up numbers. If no API key is available it
says so and stops - accuracy is either measured by actually running this
against Groq, or it is reported as "not measured", never guessed.

Run it directly:
    python tests/evaluation.py

Or import run_classification_eval / run_drift_eval from the notebook.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from agent import ScopeKeeperAgent
from models import CLASSIFICATIONS

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def _fresh_agent(project: dict) -> ScopeKeeperAgent:
    agent = ScopeKeeperAgent()
    agent.start_project(
        name=project["name"],
        objective=project["objective"],
        budget=project["budget"],
        estimated_hours=project["estimated_hours"],
        deliverables=project["deliverables"],
        exclusions=project.get("exclusions", []),
        currency=project.get("currency", "INR"),
    )
    return agent


def _last_logged_classification(agent: ScopeKeeperAgent) -> str:
    for event in reversed(agent.trace):
        if event["type"] == "tool_result" and event["tool"] == "log_request":
            result = event["result"]
            if result.get("status") == "logged":
                return result["request"]["classification"]
    return "NO_CALL"


def run_classification_eval(cases_path: str = None) -> dict:
    cases_path = cases_path or os.path.join(DATA_DIR, "evaluation_cases.json")
    with open(cases_path) as f:
        data = json.load(f)

    confusion = {expected: {label: 0 for label in list(CLASSIFICATIONS) + ["NO_CALL"]} for expected in CLASSIFICATIONS}
    results = []

    for case in data["cases"]:
        agent = _fresh_agent(data["project"])
        agent.run(f"New client request: {case['description']}")
        predicted = _last_logged_classification(agent)
        confusion[case["expected"]][predicted] += 1
        results.append({"id": case["id"], "description": case["description"], "expected": case["expected"], "predicted": predicted})

    total = len(results)
    correct = sum(1 for r in results if r["predicted"] == r["expected"])
    accuracy = correct / total if total else 0.0

    per_class = {}
    for label in CLASSIFICATIONS:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted_as_label = sum(confusion[expected][label] for expected in CLASSIFICATIONS)
        precision = tp / predicted_as_label if predicted_as_label else 0.0
        recall = tp / support if support else 0.0
        per_class[label] = {"precision": round(precision, 2), "recall": round(recall, 2), "support": support}

    return {
        "total": total,
        "correct": correct,
        "accuracy": round(accuracy, 3),
        "confusion_matrix": confusion,
        "per_class": per_class,
        "results": results,
    }


def run_drift_eval(sequences_path: str = None) -> dict:
    sequences_path = sequences_path or os.path.join(DATA_DIR, "drift_sequences.json")
    with open(sequences_path) as f:
        data = json.load(f)

    results = []
    for seq in data["sequences"]:
        agent = _fresh_agent(data["project"])
        for description in seq["requests"]:
            agent.run(f"New client request: {description}")
        status = agent.tools.get_scope_status()
        actual_level = status["cumulative"]["drift_level"]
        results.append(
            {
                "id": seq["id"],
                "expected_final_drift_level": seq["expected_final_drift_level"],
                "actual_drift_level": actual_level,
                "match": actual_level == seq["expected_final_drift_level"],
                "cumulative": status["cumulative"],
            }
        )

    correct = sum(1 for r in results if r["match"])
    return {"total": len(results), "correct": correct, "accuracy": round(correct / len(results), 3) if results else 0.0, "results": results}


if __name__ == "__main__":
    if not (os.getenv("GROQ_API_KEY") or os.getenv("GITHUB_TOKEN")):
        print("No GROQ_API_KEY (or GITHUB_TOKEN) set - accuracy not measured.")
        print("Set your API key and re-run this script to get real numbers.")
        sys.exit(0)

    print("Running single-request classification evaluation...")
    classification_results = run_classification_eval()
    print(f"Accuracy: {classification_results['accuracy']*100:.1f}% ({classification_results['correct']}/{classification_results['total']})")
    for label, stats in classification_results["per_class"].items():
        print(f"  {label}: precision={stats['precision']}, recall={stats['recall']}, support={stats['support']}")

    print("\nRunning cumulative drift-sequence evaluation...")
    drift_results = run_drift_eval()
    print(f"Accuracy: {drift_results['accuracy']*100:.1f}% ({drift_results['correct']}/{drift_results['total']})")
    for r in drift_results["results"]:
        status = "OK" if r["match"] else "MISMATCH"
        print(f"  [{status}] {r['id']}: expected={r['expected_final_drift_level']}, actual={r['actual_drift_level']}")
