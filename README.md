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

## Persistent memory - a real database

The in-session memory above is only half the picture. Every project and every logged request is also
written immediately to a real SQLite database file (`scopekeeper.db`, via `src/db.py`) - not just held
in memory until the notebook closes. `ScopeKeeperAgent.load_project(project_id)` rebuilds a project's
full state, including every past request, in a brand new agent instance with no other memory of
anything - proof this survives closing the notebook completely, not just closing one cell's output.
`ScopeKeeperAgent.list_saved_projects()` lists what's available to resume, and the Streamlit UI
(`app.py`) has a "Resume a previous project" screen built on exactly this.

On top of that, before classifying any new request, the agent looks up past requests - from this
project or any earlier one - that share real words with it (`db.find_similar_past_requests`, plain
word-overlap scoring after stripping punctuation and simple plurals) and includes the closest few as
reference context. **This is retrieval-based memory, not model fine-tuning** - nothing about the AI's
weights ever changes. It's the same idea as a freelancer flipping back through their own old notes
before answering a new client, done automatically.

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
4. Optional: `streamlit run app.py` for a small UI on top of the same agent, including a "resume a
   previous project" screen backed by the same database.

## Running the tests

```
python tests/test_drift.py
python tests/test_validation.py
python tests/test_tools.py
python tests/test_db.py
python tests/evaluation.py     # needs a real API key - measures actual classification accuracy
```

The first four need no API key - they test the deterministic Python (drift math, argument validation,
the tools themselves, and the SQLite persistence/retrieval layer) directly, using a temporary throwaway
database file so they never touch a real project's data. `evaluation.py` is the one that needs a real
model call, because it's testing whether the model's judgement is any good, not just whether the code
runs; it honestly prints "not measured" instead of a number if no key is set.

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
- Classification accuracy varies by a few points run to run (see "Measured accuracy" above) because
  the model isn't fully deterministic - a single evaluation run shouldn't be read as a precise number.
- The drift score's hours component can shift a borderline sequence into the next drift level purely
  because the model's own hours estimate for one request varied between runs (see "Measured accuracy").
- Groq's available model list changes over time - the fallback model name is read from `.env` rather
  than hardcoded for exactly this reason, but it should still be spot-checked occasionally
  (`client.models.list()`) rather than assumed to still exist.
- Running the evaluation script repeatedly in a short window can hit the free-tier rate limit; the
  agent backs off and retries once, but heavy back-to-back testing is still the fastest way to see it.

## Rubric self-check

| Requirement | Where it lives | Evidence |
|---|---|---|
| Plan-act loop, more than one step | `src/agent.py`, `ScopeKeeperAgent.run` | Notebook Section 10 trace output shows multiple tool_call/tool_result steps per turn |
| At least two working tools | `src/tools.py` | `log_request`, `get_scope_status`, both tested in `tests/test_tools.py` |
| Memory across turns | `src/memory.py` (`ProjectState`) | Notebook Section 10: "are we drifting" question answered using requests logged in earlier turns |
| Notebook runs 2-3+ example goals with visible multi-step trace | `ScopeKeeper.ipynb` Section 10 | 4 sequential requests + 1 summary question, full trace printed each time |
| README names tools, explains memory, one honest failure | This file | Sections above |
| Tests | `tests/` | 3 no-API-key test files (all pass, see below) + `evaluation.py` for measured accuracy |

One design decision, tuned using the measured results above: the system prompt explicitly tells the
model to use `NEEDS_CLARIFICATION` for any request that doesn't name a specific feature, added after
run 2 showed it answering confidently on vague requests instead. See "Measured accuracy" for the
honest before/after result, including a side effect that wasn't fully resolved.

Unit tests (no API key required) as of the last local run:

```
$ python tests/test_drift.py
All drift tests passed.
$ python tests/test_validation.py
All validation tests passed.
$ python tests/test_tools.py
All tool tests passed.
```

## Measured accuracy

Run against the real Groq API on 2026-08-30, using `tests/evaluation.py`. Every run is reported below,
including the two that went badly, because a single cherry-picked number would misrepresent what was
actually measured.

**Single-request classification accuracy (`data/evaluation_cases.json`, 32 cases):**

| Run | Accuracy | What changed / what happened |
|---|---:|---|
| 1 (baseline prompt) | 90.6% (29/32) | NEEDS_CLARIFICATION recall was the weak point (0.71) |
| 2 (baseline prompt) | 84.4% (27/32) | Confirmed the same weak point: 2 vague requests ("better for mobile", "a booking feature") answered confidently instead of flagged |
| 3 (added a NEEDS_CLARIFICATION push to the prompt) | 84.4% (27/32) | NEEDS_CLARIFICATION recall improved (0.71→0.86), but a new pattern appeared: PARTIALLY_IN_SCOPE recall dropped to 0.33 |
| 4 (added worked examples for the IN_SCOPE/PARTIALLY_IN_SCOPE boundary) | 6.2% (2/32) - **discarded, not a real accuracy result** | Every request after the first two came back `NO_CALL`. Not a classification failure - see "the bug this uncovered" below. |
| 5 (same prompt as run 4, after fixing the bug) | **96.9% (31/32)** | Clean run. Only miss: the FAQ-section case, which is arguably a borderline label to begin with (see below). |

**The bug this uncovered.** Run 4's near-total collapse looked at first like the new prompt had
somehow broken everything. Investigating one request directly (instead of trusting the aggregate
number) showed the real cause: after 4 evaluation runs in the same session (~130 API calls), the
free-tier rate limit on `openai/gpt-oss-120b` was being hit, `agent.py`'s retry logic fell back to a
second model, `llama-3.1-8b-instant` - and that model no longer exists on Groq (confirmed by listing
`client.models.list()`), so the fallback itself failed with a 404, and every one of those requests
silently became a "the AI is unavailable" message with no tool call, hence `NO_CALL` on every
prediction. **Fixed** by: (1) swapping the fallback to `openai/gpt-oss-20b`, a model actually offered
today, and (2) making the retry back off 8 seconds on a detected rate limit instead of the original
flat 1.5 seconds, which was too short to matter. Run 5, right after the fix, came back clean. This is
arguably the more instructive failure of the two documented in this project: it shows that a bad
accuracy number needs the same "why" investigation as a bad classification does, before you trust it.

**Cumulative drift-sequence accuracy: 3/4 (75%) on the same clean run**, down from 4/4 measured
earlier. The miss: sequence `D_mixed_with_ambiguity` was expected to land on MODERATE and instead
scored HIGH. Looking at the actual logged numbers, the cause wasn't a classification mistake - the one
genuinely out-of-scope request in that sequence ("book a table online with real-time availability")
got a noticeably higher hours estimate on this run than on earlier runs, which alone was enough to push
`hours_component` (40% of the drift score) over the MODERATE/HIGH line. This is a legitimate limitation
worth stating plainly: **the model's own effort estimates vary between runs, and because hours make up
40% of the drift score, that variance alone can occasionally shift a borderline case into the next
drift level.** Averaging several runs (see Future Improvements) would smooth this out; a single run
should be read as directionally correct, not exact to the point.
