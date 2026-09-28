# End-to-end tests

Tests that drive the running services over HTTP, across process boundaries, the way
the student app does.

Nothing here imports application code. That is the point: the unit suites already
cover everything inside each process — roughly 1,539 pytest, 444 Flutter and 191 Jest
tests — and none of them crosses a boundary. The gateway's tests mock `fetch`, the
Flutter tests inject fake repositories, and the AI service's own `test_e2e_*` files
call the orchestrator in-process. A bug that lives *between* two services is
invisible to all of them.

This suite found four bugs on its first run. Two are fixed; the rest are pinned
below.

## Running it

Bring the stack up first, in four terminals:

```bash
cd ai-service && venv/bin/python3 -m uvicorn api.main:app --port 8001
```
```bash
cd backend-ai-tutor/backend && npm run dev
```
```bash
cd ai_tutor && flutter build web --pwa-strategy=none && python3 tool/serve_web.py 53123
```
```bash
cd admin-ai-tutor && npm run dev
```

Then:

```bash
ai-service/venv/bin/python3 -m pytest e2e -q
```

The suite skips itself with a clear message if the stack is not reachable, rather
than failing with connection errors. The AI service takes about 25 seconds to report
healthy because it loads STT/TTS models first; `conftest.py` polls for it.

Tests that need a live DeepSeek call are marked `llm` and **excluded by default**,
because DeepSeek bills per token and a provider hiccup would make the suite flaky.
To include them:

```bash
ai-service/venv/bin/python3 -m pytest e2e -q -m "llm or not llm"
```

Everything in the default run is answered by deterministic SymPy-backed solvers, so
it costs nothing and does not depend on the network beyond localhost.

## Environment

No configuration is needed for a normal local run. Overrides, if you need them:

| Variable | Default | Purpose |
|---|---|---|
| `E2E_GATEWAY_BASE` | `http://localhost:4000/api/v1` | the public API |
| `E2E_AI_BASE` | `http://localhost:8001` | the internal AI service |
| `E2E_DEMO_TOKEN` | `demo-token` | the development student identity |
| `VISUAL_TUTOR_INTERNAL_TOKEN` | read from `ai-service/.env` | gateway↔AI-service secret |

The internal token is read from the env file at runtime and never written into a test
file. `demo-token` resolves to uid `demo-student` and works only because
`ALLOW_DEVELOPMENT_FALLBACKS=true` locally; `src/config/env.ts` refuses to boot with it
in staging or production.

## What is covered

| File | Seam it guards |
|---|---|
| `test_student_turns.py` | a worked solution for every subject, and the public turn shape the Flutter client needs |
| `test_streaming.py` | the SSE contract, frame versions, ordering, and resume by `Last-Event-ID` |
| `test_language_and_scope.py` | non-problems, prompt injection, one language per student, the topic lock, curriculum scope |
| `test_visual_primitives.py` | STEM diagrams surviving the gateway, and contract drift between the three implementations |
| `test_auth_and_privacy.py` | student auth, the internal-only boundary, one student reading another, CORS, secret leakage |
| `test_sessions_and_health.py` | session restore, follow-up turns, board-version conflicts, health, rate-limit fail-open |
| `test_answer_equivalence.py` | quiz grading judging meaning rather than spelling |

## Conventions

- **A fresh `student_id` per test.** The AI service caches solutions in-process and
  the rate limiter shares Redis keys, so a test reusing an identity can pass only
  because of the order it ran in. The gateway's own suite had exactly this bug.
- **Assert on the public contract, not on internals.** `assert_contract_shape` checks
  the fields the Flutter client needs — including the per-action ones it drops
  silently when absent, which is how a board can come back half-empty with no error.
- **A genuine product bug is recorded as `xfail(strict=True)`**, with the diagnosis in
  the reason. That keeps the suite green while making the bug visible, and turns the
  test into a passing check the moment someone fixes it. Never loosen an assertion to
  get green.

## Known failures

Three real bugs are pinned as `xfail`. They are product defects, not test problems.

**1. All six STEM visual primitives are dropped at the gateway.** The AI service
declares `draw_free_body_diagram`, `draw_molecule`, `draw_atom_model`,
`draw_particle_diagram`, `draw_circuit_diagram` and `show_reaction_layout`. The
gateway's action allowlist contains none of them, so each is replaced with a "One
board item could not be shown" notice. The Flutter renderer supports them; only the
middle layer disagrees.

**2. Kinematics answers only the first quantity asked.** "Find its velocity and the
distance travelled" returns `v = 10 m/s` and never computes `s = 25 m`.

**3. An upstream failure returns a stack trace.** Acceptable in development, but the
same handler serves production, so it needs an explicit environment guard.

A softer finding is recorded too: an action outside the contract (say `ask_question`)
reaches the AI service, comes back 422, and is reported to the student as "The tutor
service could not complete this request. Please retry." — inviting a retry that cannot
succeed. It should be a 400.

One more, pinned in the unit suite rather than here
(`tests/test_dynamic_followup.py`): `_identify_referenced_step` points at the wrong
step. Asked "why is u = 0?" it explains Step 3, whose prose and latex both name `u`,
rather than Step 1, which lists the givens generically and puts the values in a
`show_table` the matcher cannot read. It was invisible while every follow-up failed
with a 502 before a student saw it.

### Fixed by this suite

**Every follow-up turn returned 502 — the interactive Q&A loop was dead.** The AI
service set `board_update_mode="append"` on follow-ups, but the public contract allows
only `replace` and `patch`, and both the gateway and the Flutter client enforce that.
Three things were wrong underneath: deterministic solutions were never cached, so a
follow-up re-solved the problem by a different route and renumbered every action; the
follow-up passed the student's question to the solver instead of the problem; and the
mode string was overloaded to mean both "how to merge" and "is this a follow-up", so
correcting it broke board versioning until the two were separated. Follow-ups now
return 200 with the board intact — verified end to end: `board_version` advances
1→2→3→4→5 and all ten prior actions survive each turn.

**The off-topic refusal concatenated Khmer and English**, so a student in either
language was shown prose they could not read. Same defect as one already fixed in
`build_not_a_problem_message`; `build_off_topic_message` had been missed.

## CI

Keep this out of the unit-test jobs. It needs the whole stack up, and a flaky
external dependency must not be able to redden the main build.
