# Work prompts for ReanAI

Each numbered section below is one prompt: copy it whole into a fresh AI session.
They are ordered so that each one can assume the previous ones are done. Run them
one at a time and check the result before moving on — an agent that is asked for
four things at once tends to do three of them badly.

**Scope these prompts assume:** Grade 12 only; Mathematics, Physics and
Chemistry; Khmer and English; phone, tablet and desktop; **the scan/photo
feature is removed**.

Every prompt ends with the same three rules. They are there because this project
has lost days to each of them:

- Read `GEMINI.md` first; the board invariants in §5 are not suggestions.
- Prove a fix: run the new test against the old code, watch it fail, then fix.
- Report honestly — real numbers, and say what you did not verify.

---

## 1. Remove the scan feature

```
Read GEMINI.md first.

Remove the photo/scan-a-problem feature completely. It is out of scope: students
type or speak their problem instead.

Delete it in all three codebases and leave no dead references:

ai-service/
  api/routes/visual_tutor_scan.py        (whole route, and its registration in api/main.py)
  api/services/visual_tutor/orchestrator.py  (scan references)
  any scan tests under tests/

backend-ai-tutor/backend/src/
  controllers/tutor.controller.ts
  routes/tutor.routes.ts
  services/tutor.service.ts
  routes/__tests__/tutor-api.test.ts

ai_tutor/lib/
  screens/tutor/scan_problem_screen.dart            (delete)
  features/visual_tutor/data/scan_problem_repository.dart  (delete)
  app/tutor_shell.dart                              (remove the entry point)
  screens/tutor/visual_tutor_home_screen.dart
  screens/Dashboard/dashboard_screen.dart
  screens/learning_selection/learning_selection_repository.dart
  features/visual_tutor/presentation/visual_tutor_design.dart

Also remove: camera/image-picker permissions and plugins that nothing else uses
(check ios/Runner/Info.plist, android/app/src/main/AndroidManifest.xml,
pubspec.yaml), and any scan strings or icons.

Where removing a button leaves a gap in a layout, close the gap properly —
do not leave an empty slot or a lone centred button.

Done when: nothing matches a case-insensitive search for "scan" in lib/, src/ or
api/ except unrelated words (e.g. "scanner" in a parser); the app builds; and
each repo's test suite is no worse than the baseline in GEMINI.md §6.

Rules: prove any behaviour change with a test that fails before your change.
Report the real test numbers, and say what you could not verify.
```

---

## 2. Open the curriculum to Grade 12 Maths, Physics and Chemistry

```
Read GEMINI.md first, especially §3 on the scope gate.

Today the tutor only accepts Grade 12 limits. Open it to Grade 12 Mathematics,
Physics and Chemistry, and keep everything else locked out — an over-wide scope
is how the tutor starts answering questions it cannot check.

Two gates have to agree, and they are separate:

1. ai-service/api/core/config.py:332 — VISUAL_TUTOR_SCOPE_LOCK, default
   "grade12_math_limits"
2. ai-service/api/services/visual_tutor/pilot.py — enforce_pilot_scope(), driven
   by VISUAL_TUTOR_PILOT_GRADES / _SUBJECTS / _LESSONS / _LANGUAGE_MODES, which
   returns 403 for anything outside the allow-list

Design the scope as data, not as a string comparison scattered through the code:
one place that answers "is this grade + subject + topic in scope?", used by both
gates and by the client's lesson catalog. Grade 12 only, three subjects, both
language modes (english, khmer).

The refusal message a student sees must say what IS available, not just "no".

Do not widen the sanitizer or the plan contract to make this work.

Done when: a Grade 12 physics or chemistry question reaches the orchestrator
instead of 403-ing; a Grade 10 question, or a Grade 12 biology question, is still
refused with a helpful message; and tests cover an in-scope and an out-of-scope
request for each of the three subjects.

Rules: prove it with tests that fail before the change. Report real numbers.
```

---

## 3. Physics: make one topic work end to end before adding more

```
Read GEMINI.md first, especially §3 (worked_solution.py) and §5.

Pick ONE Grade 12 physics topic — kinematics (constant acceleration) is the best
first one — and make it work as well as limits already does: the student asks, the
board writes the full worked solution, and follow-up questions about any step are
answered correctly.

Copy the shape of api/services/visual_tutor/worked_solution.py:
- the physics, not the model, decides the numbers. Parse the given quantities,
  solve symbolically with sympy, and carry units explicitly
- deterministic action ids, so a streamed action and the completed turn match
- the model writes the explaining sentences, never the arithmetic

Use the board primitives that already exist rather than inventing new ones:
draw_free_body_diagram, draw_axes, plot_function, show_table, draw_arrow.
See api/services/visual_tutor/high_school_stem.py for the topic metadata already
in place, and solver_registry.py for how a solver is registered.

A physics answer is wrong if the unit is wrong. Test that explicitly.

Done when: at least 8 real kinematics problems produce a correct worked solution
with correct units, each covered by a test; a problem the solver cannot handle
degrades to an honest "I can't solve this one yet" rather than a guess.

Rules: prove each solver behaviour with a test. Report real numbers, and list
which problem shapes you did NOT cover.
```

---

## 4. Chemistry: one topic, same standard

```
Read GEMINI.md first, especially §3 and §5.

Same as the physics work, for ONE Grade 12 chemistry topic — stoichiometry
(mole/mass/reaction calculations) is the best first one.

The chemistry primitives already exist on the board and are validated by
live_board_state.dart: show_reaction_layout, draw_molecule, draw_atom_model,
draw_particle_diagram. Use them; a balanced equation drawn on the board teaches
more than the same equation as a line of text.

Ground truth rules:
- balance equations programmatically and verify the balance before teaching it
- molar masses come from a table in the code, not from the model
- significant figures matter in the final answer; decide the rule and apply it
  consistently

Done when: at least 8 real stoichiometry problems produce a correct worked
solution, each covered by a test, including one that needs the equation balanced
first; an unsupported problem says so honestly.

Rules: prove it with tests that fail before the change. Report real numbers and
name the gaps.
```

---

## 5. Make Khmer a real language, not a label

```
Read GEMINI.md first.

The app claims to support Khmer but barely does:
ai_tutor/lib/core/localization/app_localizations.dart is 41 lines with four
strings (appName, loading, retry, emptyStateTitle). Everything else on screen is
hard-coded English.

Make Khmer a first-class language:

1. Move to real localisation (flutter gen-l10n with .arb files, or keep the
   current class if you prefer, but every user-visible string must come from it).
   Find the hard-coded strings — grep lib/ for Text(' with English inside.
2. Khmer typography is not English typography with a different font. Khmer has
   taller line boxes, no spaces between words, and breaks differently. Check line
   height, wrapping and truncation on every screen, especially the board and the
   chat panel. Fonts already referenced: Kantumruy Pro, Noto Sans Khmer.
3. The tutor's own teaching text is separate from the UI: the turn request
   carries language_mode, and speech carries language "km". Make sure a Khmer
   lesson is Khmer end to end — board text, spoken text, hints, and error
   messages.
4. The language switch must be reachable in an obvious place and must persist
   across restarts.
5. Do not machine-translate the maths. Numbers, symbols and equations stay as
   they are; the sentences around them are translated.

Done when: every screen can be read end to end in Khmer with nothing clipped,
overlapping or still in English; switching language mid-session does not break
the lesson; and there is a test that fails if a new hard-coded English string
appears in a screen widget.

Rules: prove it with tests. Report real numbers, and list any screen you could
not check.
```

---

## 6. One responsive layout for phone, tablet and desktop

```
Read GEMINI.md first, especially §5 on the board.

The app must work properly at three sizes, not just "not crash":

- phone   (~390-430 wide): one column, the board is the hero, chat below
- tablet  (~768-1024):     the board gets the space, controls beside it
- desktop (1280+):         a wide board with a side panel, and a maximum content
                           width so text lines do not run 200 characters long

Rules of thumb for this app specifically:
- the board is the point of the screen. Anything competing with it for vertical
  space on a phone is a candidate for removal
- board pagination (board_pagination.dart) measures against the real viewport, so
  changing the layout changes how many boards a solution takes. Re-check
  Board 1/2/3 at each size after any layout change
- touch targets at least 44pt; the board's own pan/zoom must not fight page
  scrolling on a phone
- test both orientations on tablet

Define the breakpoints in one place and use them everywhere; do not scatter
MediaQuery width checks through widgets.

Done when: a widget test renders the tutor screen, the lessons list and the
home screen at 400x800, 834x1112 and 1440x900 with no overflow errors and no
horizontally-scrolling body, and the board's own tests still pass at each size.

Rules: prove it with tests that fail before the change. Report real numbers.
```

---

## 7. Fix the UI/UX that is actually weak

```
Read GEMINI.md first.

These are known weak points, in the order a student meets them. Fix them as a
set, and keep the visual language consistent across all of them.

1. The lessons catalog is empty — it says "No lessons are available yet" because
   no lessons are published. An empty catalog is the first thing a new student
   sees. Either publish the Grade 12 lessons or make the empty state useful
   (explain what is coming, and offer the "type your own problem" path).
2. There is no way for a first-time student to understand what the app does.
   Add a short, skippable first-run explanation — one screen, not a carousel.
3. Error and refusal states are developer-shaped. A student who asks something
   out of scope should be told what they CAN ask, in their own language.
4. Waiting states: the tutor can take several seconds to plan. The live preview
   line helps, but check that every wait somewhere in the app shows something
   honest, and that nothing shows a spinner forever if a request fails.
5. Density on a phone: audit everything on the tutor screen that is not the
   board or the input. If it does not earn its vertical space, remove it.

You may change any UI you judge to be poor — this is an explicit invitation — but
change it for a reason you can state in one sentence, and keep it consistent with
the rest of the app.

Done when: a student can open the app, understand what it does, ask a Grade 12
question in Khmer or English, and read the answer, without meeting an empty
screen, a dead end, or a developer message.

Rules: prove behaviour changes with tests. Report real numbers, and list what you
changed on judgement rather than instruction so it can be reviewed.
```

---

## 8. Publish the Grade 12 curriculum

```
Read GEMINI.md first.

The catalog that feeds the lessons list is empty. Populate it for the descoped
product: Grade 12, Mathematics + Physics + Chemistry, with Khmer and English
titles and descriptions for every entry.

Start from ai_tutor/lib/screens/lessons/student_lessons_repository.dart and
whatever publishes lessons on the server side; follow the existing shape rather
than inventing a new one.

For each subject, list the topics you are actually able to teach today (limits;
whatever topics prompts 3 and 4 delivered) and mark the rest clearly as not yet
available, rather than listing them and failing when a student taps one.

Done when: the lessons list shows real Grade 12 content in both languages, every
listed lesson opens and produces a real lesson, and nothing listed is a dead end.

Rules: prove it with tests. Report real numbers.
```

---

## 9. Make the whole path work as one product

```
Read GEMINI.md first.

Everything above is separate pieces. This prompt is about the joins.

Walk the full student path yourself and fix what breaks, in both languages and at
all three screen sizes:

  open the app -> sign in -> pick a Grade 12 lesson (or type a problem)
  -> watch the solution being written -> page through the boards
  -> ask a follow-up question -> get an answer about the right step
  -> leave the app and come back -> the session is still there

Specific joins that are known to be fragile:
- the board writes the solution ONCE (GEMINI.md §5). Re-check this after any
  change to the streaming path or the turn application
- board_update_mode comes back as "replace" on every turn. Check whether a
  follow-up question wipes the earlier boards instead of adding to them — board
  history across turns is a product requirement. Start at _shouldReplaceBoardFor
  and _nextRenderedBoardActions in tutor_screen.dart
- session resume: two tests in test/features/visual_tutor/tutor_session_resume_
  test.dart have been failing for a while. Find out whether they are describing a
  real bug in resume, and either fix the bug or fix the test
- switching language mid-lesson, and rotating a tablet mid-lesson

Do not paper over a break with a retry or a delay. Find why it breaks.

Done when: you can describe the full path working, with the evidence you used
(test output, screenshots from board_screenshot_test.dart, request logs), in both
languages, at all three sizes.

Rules: verify, don't assume. Report exactly what you ran and what you saw.
```

---

## 10. Clear the known debt

```
Read GEMINI.md first, especially §6 on test baselines.

Three known pieces of debt, none of which are urgent but all of which make the
next bug harder to find:

1. backend-ai-tutor/backend: 26 test failures across six suites, all from a
   missing getFirestore mock. The working pattern is already in
   src/routes/__tests__/tutor-api.test.ts — apply it to the rest.
2. ai-service: three failures in tests/test_visual_tutor_routes.py. They exist
   at HEAD and at older commits, and they are NOT caused by the scope lock (the
   test setup disables it). Find the real cause of each, then fix the code or
   the test.
3. ai_tutor: nine failing tests across tutor_canvas_screen_test,
   tutor_context_routing_test, visual_tutor_backend_connection_test and
   tutor_session_resume_test. Work out for each whether it is a stale test or a
   real bug, and say which.

A test that is wrong should be fixed or deleted with a reason, never weakened
until it passes.

Done when: each repo's suite is green, or every remaining failure has a one-line
explanation of why it is still there.

Rules: report real numbers before and after.
```

---

## 11. Cost and readiness before real students

```
Read GEMINI.md first.

Before this goes to a class of students, two things need a look:

1. DeepSeek spend: roughly 5.6M tokens went through in about two days of
   development. Find which calls dominate — planning, follow-ups, retries, or
   something repeating that should not — and cut the waste. Caching a worked
   solution the sympy layer already computed deterministically is the obvious
   candidate.
2. Failure behaviour: what a student sees when DeepSeek is slow, rate-limited or
   down. The sympy-grounded worked solution does not need the model to produce
   the mathematics, so there may be a useful degraded mode instead of an error.

Measure before you optimise, and show the measurement.

Done when: you can state the per-lesson token cost, what you changed, and the new
number; and a student meets something useful rather than a spinner when the model
is unavailable.

Rules: no guessed numbers. Show how you measured.
```

---

## How to run these

Work one prompt at a time, and after each one:

```bash
cd ai-service         && venv/bin/python3 -m pytest -q --ignore=tests/trace_cag --ignore=tests/benchmark
cd ai_tutor           && flutter test
cd backend-ai-tutor/backend && npm test
```

Compare against the baselines in `GEMINI.md` §6 — not against zero — and commit
per repo once a prompt is finished and verified, so a bad step can be undone
without losing the good ones.
