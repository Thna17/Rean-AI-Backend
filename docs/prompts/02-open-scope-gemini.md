You are continuing work on ReanAI. GEMINI.md in this directory is your project
context — read all of it before doing anything. Ignore CLAUDE.md: it describes a
different project (LexiLingo) and none of its paths exist here.

Your task: open the tutor to Grade 12 Mathematics, Physics and Chemistry. Before
that, commit the scan-feature removal that is already done but not committed.

## This machine has 8 GB of RAM — plan around it

A previous session lost over an hour to this. Rules:

- Never run the full ai-service test suite. It is killed for running out of
  memory (exit 137). Use the fast command in GEMINI.md §6 (80 tests, about
  3 seconds) plus the test files for whatever you changed.
- Run one heavy job at a time: one test suite, or one Flutter build — never two
  at once.
- Do not build the Flutter web app unless a task needs it. `flutter test` is
  enough to verify Dart changes.
- If a check is slow, say so and move on. Do not work around it with sleeps or
  retries.

## Step 0 — commit the scan removal (already verified)

The scan/photo feature has been removed in all three repos but not committed.
A previous session checked it and reported:

- gateway: builds; 126 passing, 26 failing — one failure fewer than before
- Flutter: 300 passing, the same 9 old failures (306 before, minus 6 deleted
  scan tests); `flutter analyze` shows no errors; the web build succeeds
- ai-service: the app imports and the scan route is gone from the API schema
- the dashboard and home layouts have no gaps where scan buttons were removed
- `image_picker` stays — profile pictures still use it

Do NOT redo all of that. Re-check only what is quick:

```bash
cd backend-ai-tutor/backend && npx tsc --noEmit
cd ai_tutor && flutter analyze --no-fatal-infos --no-fatal-warnings
cd ai-service && venv/bin/python3 -c "import api.main"
```

and search for leftover references to the removed code
(`scan_problem`, `visual_tutor_scan`, `scanTutorImage`, `/scan`).

If those are clean, make one commit per repo containing ONLY the scan-removal
changes, with the message "remove the scan feature":

- outer repo (this directory) — ai-service files only. Stage by path; do not use
  `git add -A` here (docs/ and the nested repo directories must stay out).
- `ai_tutor/` — its own git repo
- `backend-ai-tutor/` — its own git repo

Do not push.

## Step 1 — open the scope

Only Grade 12 limits get through today. Two separate server gates must BOTH
change — changing only one still returns 403:

1. `ai-service/api/core/config.py:332` — `VISUAL_TUTOR_SCOPE_LOCK`, default
   `"grade12_math_limits"`. The orchestrator
   (`api/services/visual_tutor/orchestrator.py`) enforces it.
2. `ai-service/api/services/visual_tutor/pilot.py` — `enforce_pilot_scope()`,
   driven by `VISUAL_TUTOR_PILOT_GRADES` / `_SUBJECTS` / `_LESSONS` /
   `_LANGUAGE_MODES` (config.py around line 345). It returns 403 outside the
   allow-list.

The Flutter app also hard-codes the limits scope in
`ai_tutor/lib/screens/lessons/local_mvp_limits_scope.dart`.

Target scope: **Grade 12 only; Mathematics, Physics, Chemistry; language modes
`english` and `khmer`.** Everything else stays refused: Grade 10, Grade 11, and
other subjects such as biology.

Put the scope in ONE place, as data, that answers "is this grade + subject +
topic in scope?", and make both server gates use it. The app must not offer a
lesson the server then refuses.

## Step 2 — be honest about topics we cannot solve yet

Only limits have a checked worked solution
(`api/services/visual_tutor/worked_solution.py`, where sympy does the maths).
Physics and chemistry solvers are later tasks — do not build them now.

Find out what happens today when an in-scope physics or chemistry question has no
solver. If it falls through to the LLM planner and the model does the arithmetic
unchecked, that is not acceptable for a student. Return an honest "this topic
isn't ready yet" message, in the student's language, instead.

## Step 3 — helpful refusals

A refused student must be told what they CAN ask — Grade 12 maths, physics or
chemistry — in their own language (Khmer or English), not a bare error.

## Constraints

- Do not loosen `response_sanitizer.py` or the teaching-plan contract to make
  any of this work. They stop the tutor leaking answers or drifting off topic.
- Do not break the board rules in GEMINI.md §5.
- `tests/test_visual_tutor_routes.py` has 3 failures that already existed. Their
  cause is unknown — it is NOT the scope lock, because the test setup turns the
  lock off. Do not investigate them in this task; just report whether their
  count changed.

## Done when

- Tests cover, for EACH of the three subjects, one in-scope request that gets
  through and one out-of-scope request that is refused; plus a Grade 10 request
  and a Grade 12 biology request, both refused with a helpful message.
- An in-scope physics or chemistry question with no solver gets the honest
  "not ready yet" response, and a test covers it.
- Every new test fails on the code before your change. Run it that way once and
  say that you did.
- The fast ai-service tests, `flutter test`, and the gateway tests are no worse
  than the numbers in Step 0.

Commit per repo with clear messages. Do not push.

## Report back with

- what changed in each repo, and the commit hashes
- the real test numbers before and after
- whether the 3 old route failures changed
- anything you did not check, said plainly
