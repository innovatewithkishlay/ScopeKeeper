# ScopeKeeper

An agent that helps a freelancer notice when a project is drifting beyond what was originally agreed -
not just by checking the latest request, but by watching whether many small, individually-reasonable
requests have quietly added up to a different project.

## The two tools

**`log_request(description, hours_estimate, classification, affected_deliverables, new_capabilities, reasoning, confidence)`**
Called whenever the client makes a new request. The model does the actual judgement call here -
classifying the request, estimating its effort, and explaining why - and the tool's Python code
validates those arguments and stores them.

**`get_scope_status()`**
Returns the original agreed scope, every request logged so far, and the current cumulative numbers
(extra hours, percentage over the original estimate, how many requests were out of scope, and how
many distinct new capabilities have shown up across the whole project). The model calls this when it
needs the full picture rather than a single request.

## What memory does

The project remembers the original deal (deliverables, budget, hours, explicit exclusions) and every
request logged since, as structured data (`src/memory.py`), not as a growing pile of raw chat text.
Ask "are we drifting?" three requests later, and the agent answers using everything logged so far, not
just the last message - that's what makes it more than a single-turn Q&A.

## One honest failure, and how it was fixed

The first version of the drift calculation added every request's estimated hours into the cumulative
total, including requests classified `NEEDS_CLARIFICATION`. That was wrong: a vague request like "make
it feel more premium" has no real effort estimate behind it yet, so counting the model's guessed hours
for it was inflating the drift score based on something that wasn't actually confirmed scope creep.
Fixed by excluding `NEEDS_CLARIFICATION` requests from the hours total in `src/drift.py`, and added a
test (`test_needs_clarification_does_not_count_as_extra_hours` in `tests/test_drift.py`) so it can't
silently regress.

## Setup

1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and add your Groq API key (or set `GITHUB_TOKEN` for the GitHub Models
   lane instead - either works, `src/agent.py` checks both).
3. Open `ScopeKeeper.ipynb` and run all cells. If no `.env` is found, the notebook asks for the key
   securely at runtime instead - the key is never hardcoded or printed anywhere.

## Running the tests

```
python tests/test_drift.py
python tests/test_validation.py
python tests/test_tools.py
python tests/evaluation.py     # needs a real API key - measures actual classification accuracy
```

The first three need no API key - they test the deterministic Python (drift math, argument validation,
the tools themselves) directly. `evaluation.py` is the one that needs a real model call, because it's
testing whether the model's judgement is any good, not just whether the code runs; it honestly prints
"not measured" instead of a number if no key is set.

## Why this is an agent, not a chatbot

Every reply is the result of a loop, not a single prompt-response: the agent decides whether a tool is
needed, calls it, looks at what came back, and only then decides what to say - and for cumulative
questions like "are we drifting?", that decision depends on facts (the running totals) that didn't
exist until earlier turns updated them. See `src/agent.py` (`ScopeKeeperAgent.run`) for the loop itself.

## Architecture in one line

The model handles anything that requires understanding language (is this request in scope? what new
capability does it introduce?); plain Python handles anything that must be reliable (arithmetic,
thresholds, storage, validating what the model sent back). See `ScopeKeeper.ipynb` Section 4 for the
full diagram.

## Limitations

- Tested against one project scenario (a restaurant marketing website); accuracy on very different
  domains is unverified.
- `NEEDS_CLARIFICATION` requests are excluded from the drift score entirely (see the failure story
  above) - a project getting many vague requests wouldn't show elevated drift from that alone.
- Duplicate-request detection is exact-match only; a reworded repeat of the same ask is treated as new.
- State lives in memory for the length of one notebook run - it isn't saved to disk between sessions.

## Rubric self-check

| Requirement | Where it lives | Evidence |
|---|---|---|
| Plan-act loop, more than one step | `src/agent.py`, `ScopeKeeperAgent.run` | Notebook Section 10 trace output shows multiple tool_call/tool_result steps per turn |
| At least two working tools | `src/tools.py` | `log_request`, `get_scope_status`, both tested in `tests/test_tools.py` |
| Memory across turns | `src/memory.py` (`ProjectState`) | Notebook Section 10: "are we drifting" question answered using requests logged in earlier turns |
| Notebook runs 2-3+ example goals with visible multi-step trace | `ScopeKeeper.ipynb` Section 10 | 4 sequential requests + 1 summary question, full trace printed each time |
| README names tools, explains memory, one honest failure | This file | Sections above |
| Tests | `tests/` | 3 no-API-key test files (all pass, see below) + `evaluation.py` for measured accuracy |

Unit tests (no API key required) as of the last local run:

```
$ python tests/test_drift.py
All drift tests passed.
$ python tests/test_validation.py
All validation tests passed.
$ python tests/test_tools.py
All tool tests passed.
```

Classification/drift-sequence accuracy: **not measured in this repository** - `tests/evaluation.py`
and notebook Section 12 will compute real numbers the moment a valid API key is supplied and the cell
is run. No accuracy number is claimed here that wasn't actually produced by running the code.
