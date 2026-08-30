# ScopeKeeper - Testing Guide and Viva Prep

One file that covers three things: how to test everything from scratch, what every file in this
project actually does in plain English, and how to answer the questions you're likely to get asked.
Written so a teammate, a professor, or you six months from now could pick this up cold.

---

## Part 1 - How to test everything, step by step

### 1.1 Setup (5 minutes)

```
cd ScopeKeeper
pip install -r requirements.txt
copy .env.example .env        # (or: cp .env.example .env on Mac/Linux)
```

Open `.env` in a text editor and paste your Groq key in as `GROQ_API_KEY=gsk_...`. Get a free key at
console.groq.com -> API Keys -> Create API Key. Never commit this file - it's already listed in
`.gitignore`, so a normal `git add .` will not pick it up.

### 1.2 The tests that need NO API key (run these first, always)

```
python tests/test_drift.py
python tests/test_validation.py
python tests/test_tools.py
```

Each one prints `All ... tests passed.` on success and raises an `AssertionError` with a clear message
if something's broken. These test the deterministic Python layer directly - no model call, no network,
so if these fail, the bug is in plain arithmetic/logic, not in the AI. Run these any time you change
`src/drift.py`, `src/validation.py`, `src/tools.py`, or `src/memory.py`.

### 1.3 The test that DOES need an API key

```
python tests/evaluation.py
```

This runs the agent against 32 hand-labelled requests and 4 hand-labelled multi-request sequences, and
reports real accuracy. If `GROQ_API_KEY` isn't set, it prints "not measured" and exits cleanly instead
of guessing - that's deliberate, see README "Measured accuracy" for why that distinction matters.

This makes ~40+ real API calls, so:
- It costs a small amount of your free-tier quota - fine to run occasionally, don't loop it.
- Running it several times back-to-back can hit Groq's rate limit (see Part 3, "the second bug" -
  this actually happened during development and is documented as a real failure case).

### 1.4 The live demo (what you'd actually run in front of an evaluator)

Open `ScopeKeeper.ipynb` and run every cell top to bottom (`Kernel -> Restart & Run All` in Jupyter, or
`Runtime -> Run all` in Colab). Section 10 is the actual demo: it sets up a ₹80,000 restaurant website
project, then feeds it four client requests one at a time, printing the agent's classification and the
running drift numbers after each one. Watch the `drift_level` go LOW -> MODERATE -> HIGH -> CRITICAL as
individually-reasonable-looking requests pile up - that's the whole point of the project in one scroll.

### 1.5 Failure-handling tests (Section 13 of the notebook, or run directly)

Three deliberate ways to break it, to prove it doesn't crash:

```python
# Malformed model output (simulates what happens if the model sends bad arguments)
# see notebook Section 13, cell 1 - or read src/validation.py directly

# Duplicate request (same request logged twice shouldn't double-count)
# see notebook Section 13, cell 2

# Loop-step cap (force max_iterations=1 on something that needs 2 steps)
# see notebook Section 13, cell 3 - needs an API key
```

### 1.6 Full checklist before you present

- [ ] `python tests/test_drift.py` - passes
- [ ] `python tests/test_validation.py` - passes
- [ ] `python tests/test_tools.py` - passes
- [ ] `.env` has a valid, working `GROQ_API_KEY`
- [ ] Notebook runs top to bottom with no errors (`Restart & Run All`)
- [ ] Section 10 (live demo) shows drift climbing from LOW to CRITICAL as expected
- [ ] Section 12 (accuracy) prints real numbers, not "not measured"
- [ ] `git status` shows a clean working tree, and `.env` is NOT listed as tracked

---

## Part 2 - What every file does, in plain English

```
ScopeKeeper/
├── ScopeKeeper.ipynb          the actual deliverable - open this and run it
├── README.md                  tools, memory, honest failures, measured accuracy
├── TESTING_AND_VIVA_GUIDE.md  this file
├── requirements.txt           what to pip install
├── .env / .env.example        API key config (.env is yours, .env.example is the template)
├── .gitignore                 keeps .env and __pycache__ out of git
│
├── src/
│   ├── models.py       the fixed vocabulary - what values are even allowed
│   ├── memory.py       ProjectState - the agent's memory
│   ├── drift.py         the pure-Python drift-score math - no AI here at all
│   ├── validation.py    checks the model's tool-call arguments before trusting them
│   ├── tools.py          the two actual tools: log_request, get_scope_status
│   └── agent.py           the plan-act loop that ties everything together
│
├── tests/
│   ├── test_drift.py       tests drift.py alone
│   ├── test_validation.py  tests validation.py alone
│   ├── test_tools.py        tests tools.py alone
│   └── evaluation.py         runs the agent for real and measures accuracy
│
└── data/
    ├── evaluation_cases.json   32 hand-labelled single requests
    └── drift_sequences.json    4 hand-labelled multi-request scenarios
```

### `src/models.py`
Just constants and two small data containers. `CLASSIFICATIONS` is the list of the only four words the
model is allowed to use to classify a request. `RequestRecord` is "one logged request" as a plain
object. `DriftStats` is "the current cumulative numbers" as a plain object. Nothing clever here on
purpose - if someone asks "what are the valid classification values," the answer is one line in this
file, not buried in a prompt string somewhere.

### `src/memory.py` - `ProjectState`
This **is** the agent's memory. It holds the original deal (name, budget, hours, deliverables,
exclusions) and the list of every request logged so far, plus a short rolling conversation log. The
important method to know for a viva is `compact_context()` - it turns all of that into a short,
plain-English paragraph that gets sent to the model every turn, instead of dumping the entire request
history into every single API call. That's the token-saving design decision in one method.

### `src/drift.py` - `compute_stats()`
No AI in this file at all - pure arithmetic over a list of already-classified requests. It adds up
extra hours (skipping `NEEDS_CLARIFICATION` ones on purpose - see the "honest failure" story in the
README), works out what percentage that is of the original estimate, counts out-of-scope requests, and
counts distinct new "capability groups" that have shown up. Those three numbers get combined into a
single 0-100 `drift_score` using a documented, weighted formula (read the comment at the top of the
file - it explains exactly why hours are 40%, out-of-scope ratio is 30%, and capability spread is 30%).
The score is then bucketed into LOW / MODERATE / HIGH / CRITICAL.

**Why this matters for the viva:** if asked "couldn't the AI just make this number up," the answer is
no - this function never sees the model at all, it only sees data the model already produced earlier
and validated.

### `src/validation.py` - `validate_log_request_args()`
Takes whatever arguments the model sent when it called `log_request`, and checks every one of them:
is `classification` actually one of the four allowed words? Is `hours_estimate` actually a number, and
a sane one (0-500)? Are the list fields actually lists of short strings? If anything's wrong, it
returns a clear error message instead of raising an exception - so a bad model response becomes a tool
result the agent can react to, not a crash.

### `src/tools.py` - `ScopeTools`
The two actual tools live here, as plain methods. `log_request` validates its arguments (calling
`validation.py`), checks whether this exact request was already logged (to avoid double-counting a
repeated ask), stores it, and recomputes the drift numbers (calling `drift.py`). `get_scope_status`
just returns everything currently known about the project. Neither method calls the model - by the
time code execution reaches this file, the model has already made its decision; this file only stores
and calculates.

### `src/agent.py` - `ScopeKeeperAgent`
The part that actually talks to Groq. Three things worth knowing here:

- `SYSTEM_PROMPT` is the full set of instructions given to the model every turn - including the exact
  wording used to fix the "answered too confidently on vague requests" issue found during testing (see
  Part 3 below), and the worked examples added to fix the IN_SCOPE/PARTIALLY_IN_SCOPE boundary.
- `run()` is the actual agent loop: it calls the model, checks whether it asked to use a tool, runs the
  tool if so, feeds the result back, and repeats - up to `max_iterations` times (default 4). It also
  detects when the model tries to make the exact same tool call twice in a row and stops immediately
  instead of looping pointlessly.
- `_complete_with_retry()` is the failure-handling for the API call itself: try the main model, wait
  and retry once (longer if it looks like a rate limit), and only fall back to a second model if both
  attempts on the main one fail.

### `tests/evaluation.py`
The one script in this project that makes real API calls to measure something. `run_classification_eval`
runs all 32 cases from `data/evaluation_cases.json` through a fresh agent each time, and compares what
got logged against the expected label. `run_drift_eval` does the same for the 4 sequences in
`data/drift_sequences.json`, checking the final `drift_level` against what was expected. If no API key
is set, it says so and stops - it never reports a made-up number.

---

## Part 3 - Real bugs found during testing, and how they were diagnosed

Genuinely useful material for a viva, because these are things that actually happened, with real
before/after numbers, not hypothetical scenarios made up for the presentation.

### Bug 1: counting "estimate" hours for requests that weren't real estimates

**What happened:** the very first version of `drift.py` added every logged request's `hours_estimate`
into the cumulative total, including requests classified `NEEDS_CLARIFICATION`. A vague request like
"make it feel more premium" doesn't have a real effort estimate behind it - the number the model puts
there is close to a guess about a guess. Counting it was inflating the drift score based on something
that wasn't confirmed scope creep at all.

**How it was found:** while writing the drift formula, before any live testing - a moment of "wait, is
this the right thing to add up?"

**Fix:** excluded `NEEDS_CLARIFICATION` requests from the hours total in `drift.py`
(`sum(r.hours_estimate for r in requests if r.classification != "NEEDS_CLARIFICATION")`). A regression
test, `test_needs_clarification_does_not_count_as_extra_hours` in `tests/test_drift.py`, makes sure
this can't silently break again.

### Bug 2: a dead fallback model was masking a rate limit

**What happened:** after running the accuracy evaluation four times in one session (~130 API calls),
the fourth run came back with almost every single prediction as `NO_CALL` - 6.2% accuracy. That looked
like the newest prompt change had broken everything.

**How it was found:** instead of trusting the aggregate number, one single request was run directly
with the full trace printed. The actual error was: `Error code: 404 - The model llama-3.1-8b-instant
does not exist or you do not have access to it.` The real sequence of events was: the main model hit
Groq's free-tier rate limit, the retry logic (correctly) fell back to a second model, and that second
model had been deprecated and no longer existed on Groq - so the fallback itself failed, and the whole
turn silently became an apologetic error message with no tool call ever made.

**Fix:** two changes in `src/agent.py` - the fallback model was changed to `openai/gpt-oss-20b` (confirmed
available via `client.models.list()`), and the retry backoff was changed to wait 8 seconds instead of
1.5 when the error looks like a rate limit, giving the free-tier limit an actual chance to reset before
retrying.

**Why this is worth bringing up in a viva even though it's not flattering:** it demonstrates the
difference between "the code ran and produced a number" and "the number was actually investigated
before being trusted." A 6.2% accuracy score that goes unquestioned is a worse outcome than a bug that
gets found and fixed.

---

## Part 4 - Viva questions and answers

Grouped by theme. Every number below is a real measured result from this repository, not an estimate.

### Product / problem

**Q: Who would actually use this?**
Freelancers and small agencies who take on scoped project work (web design, development, consulting)
where clients tend to add "just one more thing" over time.

**Q: Would someone really pay for this?**
There's already a live market: ScopeShield ($20/month, launched Feb 2026), StopScopeCreep ($9/month),
ScopeAuditor, and ScopeGuard all charge for versions of this problem today. Industry write-ups put
unpaid scope creep at $7,800-$15,600 lost per freelancer per year. The pain and willingness to pay are
both independently confirmed, not assumed.

**Q: Isn't this already available, then? What's different about yours?**
Yes, it's a crowded space for the "watch individual requests against a contract" idea - that part alone
isn't novel and shouldn't be presented as if it were. What this build focuses on instead is the
**cumulative** picture: not just "is this one request in scope," but "have five individually-small
requests quietly turned a marketing website into an operations platform." That's demonstrated directly
in Section 10 of the notebook.

### Agent design

**Q: Why is this an agent and not a chatbot with extra steps?**
Because the number of tool calls and what happens next isn't scripted - it depends on what the tools
return. Answering "are we drifting?" requires the model to call `get_scope_status()`, read real
numbers that didn't exist until earlier turns created them, and decide what to say based on those
numbers. See `src/agent.py`, function `run()`, for the actual loop.

**Q: Why exactly two tools, and why these two?**
`log_request` is where the model's classification judgement gets recorded and validated;
`get_scope_status` is where the model reads back the cumulative picture it needs for anything beyond a
single request. Setting up the *original* scope deliberately isn't a tool - there's no judgement call
in typing in the agreed deliverables, so it's a plain method (`agent.start_project()`), keeping both
tools reserved for steps that actually need the model's reasoning.

**Q: What does memory actually consist of?**
`ProjectState` in `src/memory.py` - a structured object, not "the whole chat history." It holds the
original deal and every logged request as data, plus a short rolling conversation log used only for
natural phrasing. Ask about drift three turns later, and the answer is built from that structured
state, not from re-reading old messages and hoping the facts are still in there somewhere.

**Q: How do you stop it looping forever?**
A hard cap of 4 steps per turn (`max_iterations` in `agent.run()`), and an immediate stop if the model
tries the exact same tool call with the exact same arguments twice in a row (see the
`last_call_signature` check in `src/agent.py`).

### AI / model engineering

**Q: Why this model, and why this temperature?**
`openai/gpt-oss-120b` on Groq - reliable tool-calling, generous free tier. Temperature 0.2: this is a
judgement task, not creative writing, so it needs to be low - but not zero, so a retried attempt can
genuinely differ from a failed first one instead of repeating it verbatim.

**Q: How do you control token usage?**
Two things: the system prompt and tool schemas are the only large fixed cost per call, and the project
state sent each turn is a short compact summary (`ProjectState.compact_context()`), not the full
request history - the model only sees the full history when it explicitly calls `get_scope_status()`.

**Q: How do you stop the model from inventing information?**
The system prompt explicitly instructs it to reason only from the given project state and request, and
to say plainly when something is missing rather than guessing. Separately, `validation.py` rejects
anything structurally implausible (an invented classification value, an unreasonable hours number)
regardless of how confidently the model states it.

**Q: What happens when the model returns something invalid?**
`validation.py` catches it and returns a clear error as the tool result, which the model then sees and
can react to within the same loop - it's not a crash, and it's not silently accepted either. There's a
runnable demonstration of exactly this in notebook Section 13.

**Q: What happens if the API itself fails or rate-limits?**
This is the one documented from a real incident (see Part 3, Bug 2): the agent retries once, waiting
longer if the error looks like a rate limit, then falls back to a second model. The bug that was found
and fixed wasn't the fallback existing - it was that the fallback model itself had been deprecated,
which is now spot-checked rather than assumed.

**Q: How is accuracy measured, exactly? Why should I trust the number?**
`tests/evaluation.py` runs 32 hand-labelled cases and 4 hand-labelled sequences through the real agent
and compares actual output to the expected label - see Part 1.3 to run it yourself. The final measured
numbers are 96.9% (31/32) on single-request classification and 75% (3/4) on cumulative drift sequences,
and the README documents every run that led there, including the two that went badly and why.

### Engineering discipline

**Q: Why split the model's job and Python's job the way you did?**
Arithmetic, thresholds, storage and validation should never depend on the model getting it right by
chance - so they live in plain Python (`drift.py`, `validation.py`, `tools.py`). Understanding what a
sentence *means* - whether "add a loyalty program" fits inside "a marketing website" - genuinely needs
language understanding, so that part, and only that part, goes to the model.

**Q: What was the hardest bug you hit, and how did you find it?**
The dead-fallback-model bug (Part 3, Bug 2) - a 6.2% accuracy score that looked like a prompt failure
was actually an infrastructure bug two layers deep. Found by refusing to trust the aggregate number and
running one request directly with the full error trace visible.

**Q: What would you improve with more time?**
Average several evaluation runs instead of reporting single runs (the model's own hours estimates
visibly vary run to run, which is enough to shift a borderline drift-level result); sharpen the
IN_SCOPE/PARTIALLY_IN_SCOPE boundary further, since it's still the single largest source of measured
error; and persist project state to disk so a project can be picked back up across sessions.
