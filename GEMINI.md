# ReanAI — project context

Cambodia Grade 10–12 AI visual tutor. A student types a maths problem, and an
animated whiteboard writes the full worked solution while the tutor explains it,
then answers follow-up questions about any step. Currently scoped to **Grade 12
"Limits of Functions"**. The LLM is **DeepSeek**.

> `CLAUDE.md` and `GEMINI.md` describe the active ReanAI codebase and multi-agent coordination.

---

## 1. Layout

Four independent codebases under `ReanAI/`:

| Directory | Stack | Role |
|---|---|---|
| `ai-service/` | Python 3.11 (`venv/`), FastAPI | Tutor brain: solves, plans the board, validates |
| `backend-ai-tutor/backend/` | Node, Express, TypeScript | Public gateway: Firebase auth, rate limits, proxying |
| `ai_tutor/` | Flutter (web + mobile) | Student app: the whiteboard |
| `admin-ai-tutor/` | — | Admin surface (untracked, least developed) |

Git: the outer `ReanAI/` is a repo, and `ai_tutor/` is **its own repo** (it shows
as untracked `?? ai_tutor/` from the root). Commit inside the directory you are
changing. `backend-ai-tutor/` and `admin-ai-tutor/` are likewise untracked at the
root.

---

## 2. Running it

```bash
# AI service — port 8001 in this environment, NOT 8000
cd ai-service && source venv/bin/activate && python3 -m uvicorn api.main:app --reload --port 8001

# Gateway — port 4000
cd backend-ai-tutor/backend && npm run dev     # nodemon --watch src --ext ts

# Flutter web build (see §7 for why the flags matter)
cd ai_tutor && flutter build web --pwa-strategy=none
cd ai_tutor && python3 tool/serve_web.py 53123   # or 53124
```

The Flutter web app must be served from **http://localhost:53123** or **:53124**.
Any other port fails CORS at the gateway — and the allowlist comes from the shell
environment the gateway was launched with (`CORS_ALLOWED_ORIGINS`), which
**overrides** `backend-ai-tutor/backend/.env`. Editing that file does nothing for
an already-running gateway.

### Auth model

Firebase ID tokens are verified **only** at the TypeScript gateway. The AI
service is deliberately not a second public API: it authenticates the gateway
with a shared secret and trusts the UID the gateway supplies.

- `X-Visual-Tutor-Internal-Token` — must equal `VISUAL_TUTOR_INTERNAL_TOKEN`
- `X-Visual-Tutor-User-Id` — the gateway's verified UID

See `ai-service/api/core/visual_tutor_gateway_auth.py`
(`require_visual_tutor_gateway`, `enforce_gateway_user`). This lets you drive the
AI service directly for debugging without going through the app's login.

---

## 3. The tutor pipeline (ai-service)

Routes live in `api/routes/visual_tutor.py`, prefix `/api/v1/visual_tutor`:

| Endpoint | Purpose |
|---|---|
| `POST /sessions` | Create a session (`session_mode: draft \| confirmed_problem`; a confirmed one requires `problem_text`) |
| `POST /turn` | The authoritative turn. Everything else is presentation |
| `POST /turn/stream` | SSE preview of the same turn |
| `POST /turn/step` | Expert-authored persisted steps |
| `POST /telemetry` | Client board-action lifecycle counters |
| `GET /readiness` | Gateway health |

Services in `api/services/visual_tutor/`:

- **`worked_solution.py`** — the current teaching mode. sympy solves the limit,
  and the solution is written out as ordinary board actions with **deterministic
  ids**: `ws-step-<phase>-<n>`, `ws-answer-<n>`, `ws-next-<n>`. Entry points:
  `match_worked_solution`, `build_worked_solution_turn`, `solve_limit`,
  `answer_about_solution`, `match_worked_solution_followup`.
  The answer is written as `WRITE_TEXT` + `WRITE_EQUATION`, **not**
  `final_answer_reveal`, because the server contract forbids a student task
  alongside a reveal while the Flutter client requires exactly one task.
- **`orchestrator.py`** — entry point; scope gate; sanitisation. The gate
  classifies the *message text* (`parse_limit_of_function`), not just metadata —
  otherwise every free-form question is refused as out of scope.
- **`teaching_plan_builder.py`** — `_select_plan`. Note: `_to_teaching_timeline`
  reduces any plan to ONE visual; it is deliberately bypassed when
  `response.metadata["worked_solution"]` is set and the answer is unlocked.
- **`teaching_plan_contract.py`** — Pydantic, `extra="forbid"`. Mirrored in Dart
  by `ai_tutor/lib/features/visual_tutor/domain/entities/teaching_plan_contract.dart`.
  **Both sides must be changed together.**
- **`response_sanitizer.py`** — stops answer leakage. `_GIVEN_VALUES` exempts
  numbers that came from the student's own problem, so "substitute x = 3" is not
  mistaken for an answer leak and blanked.
- **`llm_teaching_planner.py`** — DeepSeek-authored plans, with repairs for what
  the model gets wrong (`_repair_action_style` for a string `style`,
  `_drop_unknown_action_fields`). Rejected actions are logged permanently.
- **`solvers.py`** — `parse_limit_of_function`, prefix clause forms
  (`lim x->3 (...)`, `lim_{x \to 3}`).

Scope lock: `VISUAL_TUTOR_SCOPE_LOCK` defaults to `grade12_math_limits`
(`api/core/config.py:332`). Widening the subject scope starts here.

### SSE contract — read this before touching streaming

Every frame is `event: visual_tutor`; the real type is `data.type`
(`status`, `speech_ready`, `board_action`, `board_patch`, `turn_complete`,
`error`). Event ids are `<stream_id>:<n>`.

Two things the client depends on:

1. **`turn_complete` repeats the same actions the stream already sent**, with the
   same ids. The stream is a preview; the completed turn is the authority.
2. **The stream also emits one provisional action the completed turn does not
   contain** — id `stream-preview-<stream_id>`, metadata
   `{provisional: true, source: server_live_preview}`, text "Let's identify the
   important information first." It fills the wait while the model plans.

Verified live on 2026-09-17: 16 streamed actions, 15 in `turn_complete`, the one
difference being that preview line.

The client also **rejects** streamed actions that lack strict identity fields:
`action_id == id`, `board_version`, `base_board_version`, `problem_instance_id`,
`active_step_id`, and valid timing. A malformed streamed action is silently
dropped, so if the board stays empty until the end, check these first.

---

## 4. The Flutter client

`ai_tutor/lib/screens/tutor/tutor_screen.dart` is very large (~7k lines) and holds
two state classes worth knowing:

- **`_TutorScreenState`** — session lifecycle, `_sendTurnWithStreaming`
  (consumes the SSE), applying the completed turn, `_renderedBoardActions`.
- **`_TeachingCanvasBoardState`** — playback timeline, page state, student ink,
  pan/zoom viewport, snapshots.

Supporting files under `lib/features/visual_tutor/presentation/`:

| File | Role |
|---|---|
| `live_board_state.dart` | Action validation, patching, stream timing, board identity |
| `board_pagination.dart` | `paginateBoardActions`, `boardTabsHeight` — splits a long solution into Board 1/2/3 |
| `semantic_board_layout.dart` | `SemanticBoardLayout.resolve` — real measurement, used by pagination |
| `widgets/board_page_switcher.dart` | `‹ Board 2 of 3 ›`, keys `visual-tutor-board-pages` / `-previous` / `-next` |
| `widgets/board_element_renderer.dart` | Draws each action |
| `visual_tutor_board_snapshot.dart` | Per-board ink/viewport persistence |

---

## 5. Invariants — breaking these has cost real days

**The board writes the solution once.** The board widget's key is
`ValueKey('board-$_boardIdentitySerial')`. A changed key destroys the board's
State, and a rebuilt board replays every action from the first line — the student
watches the whole solution written a second time. The serial is bumped only by
`_adoptBoardActions`, and only when a **non-provisional** action that is already
on the board is missing from the arriving board:

```dart
boardIdentityMustChange(
  renderedActionIds: _renderedBoardActions
      .where((action) => !isProvisionalBoardAction(action))
      .map((action) => action.id),
  nextActionIds: next.map((action) => action.id),
)
```

Two separate bugs came from this and both are covered by
`test/features/visual_tutor/board_single_write_test.dart`:
the key used to be `ValueKey(_boardStateId)` (`board-v<version>`), which changed
on every `turn_complete`; and once that was content-based, the dropped
*provisional preview* line still looked like a replaced board. Never route a
board-actions assignment around `_adoptBoardActions`.

**Equations reveal by clipping, never by truncating LaTeX.** Animating a
`write_equation` by cutting its source mid-string puts raw LaTeX on the board
(`\frac{x^{2} - 9}{x - 3} = x + 3, \q`). `board_element_renderer.dart` returns
full content for anything that is not `write_text` and clips with
`ClipRect(Align(widthFactor: progress))`. Covered by `equation_reveal_test.dart`.

**Pagination measures, it does not estimate.** A width-blind height estimate
over-fills pages and cuts steps off the bottom. `board_pagination.dart` measures
through `SemanticBoardLayout.resolve` with the real width.

**Switching boards resets the pan/zoom viewport.** A paged board is sized to the
screen, so a leftover pan offset from reading Board 1 hides Board 2 entirely —
this is what "Board 2 is blank" meant. `_showBoardFromTheTop()` resets
`_viewportController` to identity on every page change.

**Server and Dart contracts move together.** `teaching_plan_contract.py` and
`teaching_plan_contract.dart` both validate board actions; a field added to one
and not the other means actions are silently discarded.

---

## 6. Tests

```bash
cd ai-service && venv/bin/python3 -m pytest -q --ignore=tests/trace_cag
cd ai_tutor && flutter test                          # whole app
cd ai_tutor && flutter test test/features/visual_tutor   # the board
cd backend-ai-tutor/backend && npm test
```

Call `venv/bin/python3` explicitly. A bare `python3` after `source
venv/bin/activate` can still resolve to the system Python 3.9 in a
non-interactive shell, and every `str | None` annotation then fails to evaluate —
78 collection errors that look alarming and mean nothing.

**Do not run the full ai-service suite while you work.** On this 8 GB Mac it is
killed for running out of memory (exit 137), and even in chunks it takes a long
time. Iterate with the visual-tutor tests (80 tests, about 3 seconds):

```bash
cd ai-service && venv/bin/python3 -m pytest -q \
  tests/test_visual_tutor_worked_solution.py tests/test_local_limits_demo.py \
  tests/test_visual_tutor_teaching_plan_contract.py tests/test_visual_tutor_routes.py
```

plus the test files for whatever you changed. Run only one heavy job (a test
suite or a Flutter build) at a time.

`tests/trace_cag/` cannot run here at all (`ModuleNotFoundError: langgraph`). It
belongs to the other codebase lineage, like the stale `CLAUDE.md`. Ignore it.

**Baselines as of 2026-09-17 — these are what "green" means here.** Some suites
have failures that predate the current work; do not treat them as your
regression, and do not "fix" them by deleting assertions.

- Flutter, visual_tutor suite: **230 passing, 2 pre-existing failures**
  (both in `tutor_session_resume_test.dart`).
- Flutter, full suite: **306 passing, 9 pre-existing failures** — the 2 above,
  4 in `tutor_canvas_screen_test.dart`, 1 in `tutor_context_routing_test.dart`,
  2 in `visual_tutor_backend_connection_test.dart`. All 9 fail identically with
  and without the current changes.
- Gateway: a missing `getFirestore` mock still causes ~26 failures across 6 test
  files. The fix pattern is already applied in one file — copy it.
- ai-service: `test_visual_tutor_routes.py` has 3 failures that exist at HEAD
  and at older commits. Their cause is **unknown** — they are not caused by the
  scope lock, because the test setup disables it. Do not chase them inside an
  unrelated task.
- ai-service: the visual-tutor modules pass on their own (for example
  `tests/test_visual_tutor_worked_solution.py` — 12 passed). The full run takes
  several minutes and also contains failures that predate this work, so measure
  it once before you start and compare against that, not against zero.

### How to write a regression test here

The bar that has actually worked on this codebase: **prove it fails before your
fix and passes after**, and say so. Run the new test against the old code (revert
the one line, run, restore) — a test that passes both ways proves nothing, and
this project has already lost time to confident guesses that testing disproved.

Two harness traps in Flutter widget tests:

- `StreamIterator.cancel()` never completes under `flutter_test`'s fake async. A
  screen that awaits it stalls forever. Let the real loop breathe each frame:
  ```dart
  await tester.pump(const Duration(milliseconds: 100));
  await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 1)));
  ```
- Once real async runs, the audio and recorder plugins throw
  `MissingPluginException` and fail the test. Mock the channels
  (`xyz.luan/audioplayers`, `xyz.luan/audioplayers.global`,
  `com.llfbandit.record/messages`); audioplayers also opens a per-player event
  channel whose name contains a generated id, so register its handler from
  inside the `create` call. `board_single_write_test.dart` has the working setup.

---

## 7. Flutter web: the stale-bundle trap

This wasted more time than any real bug. A build that is "not taking effect" is
usually the browser serving old code.

- Build with `--pwa-strategy=none` so no service worker is emitted.
- Serve with `Cache-Control: no-store` — `ai_tutor/tool/serve_web.py` does
  this, refuses ports outside the CORS allowlist, and logs every request.
- A service worker registered by an **earlier** build keeps serving its own cache
  for that origin. Changing the **port** gives a clean origin — but only 53123
  and 53124 pass the gateway's CORS allowlist, so alternate between those two.
- Prove which bundle is live rather than assuming:
  ```bash
  md5 -q ai_tutor/build/web/main.dart.js
  curl -s http://localhost:53123/main.dart.js | md5 -q     # must match
  ```
  Logging static-server requests also shows whether the browser fetched
  `main.dart.js` at all or answered from its own cache.

---

## 8. Verifying the board without signing in

The app requires a Firebase login. To check rendering without one:

- Feed a captured server payload through the app's own parser and renderer in a
  widget test. Fixtures live in `ai_tutor/test/features/visual_tutor/fixtures/`
  (`worked_solution_turn.json`, `infinity_turn.json`) and are real responses.
- `board_screenshot_test.dart` renders the real board and writes PNGs to
  `build/board_shots/` — it loads a system font first, because the test font
  paints every glyph as a filled box.
- Drive the AI service directly with the internal token (§2) to see exactly what
  the server sends, including the SSE frames.

---

## 9. Current state (2026-09-17)

**Working end to end:** a student asks a limit problem, the board writes the full
worked solution grounded in sympy, splits across Board 1/2/3 with prev/next
navigation and history, and answers follow-up questions about individual steps.
The double-write and blank-board bugs are fixed and confirmed by the user.

**Uncommitted.** None of the recent work is committed. `ai-service` has modified
orchestrator/planner/sanitizer/solver/contract files plus new
`worked_solution.py` and `test_visual_tutor_worked_solution.py`; `ai_tutor` has a
wide set of modified files, including `tutor_screen.dart`,
`live_board_state.dart`, `board_pagination.dart` and the new
`board_page_switcher.dart`. Read the diff before changing this area:

```bash
git -C ai-service diff --stat        # from the outer repo: git diff --stat ai-service
git -C ai_tutor  diff --stat
```

Commit per repo, not from the root — `ai_tutor/` has its own history.

**Open work:**

1. `board_update_mode` comes back as `replace` on a turn. Check whether a
   follow-up question wipes the earlier boards instead of appending to them —
   board history across turns is an explicit product requirement. Start at
   `_shouldReplaceBoardFor` and `_nextRenderedBoardActions` in `tutor_screen.dart`.
2. The Lessons catalog is empty ("No lessons are available yet") — no published
   lessons exist yet.
3. Gateway test mocks: the `getFirestore` gap above.
4. Server-side: skip the equation verifier for follow-up *questions* (a question
   is not a submitted step, so there is nothing to verify).
5. Expanding past limits — the scope lock, the solver registry, and the worked
   solution templates are the three places that assume this one topic.
6. DeepSeek token use is high (~5.6M in a couple of days). Worth profiling which
   calls dominate before opening it to more students.

---

## 10. The work queue

`docs/ai-work-prompts.md` holds the remaining work as eleven self-contained
prompts, in order: remove the scan feature, open the scope to Grade 12 maths /
physics / chemistry, build the physics and chemistry solvers, make Khmer real,
make the layout work on phone / tablet / desktop, fix the weak UI, publish the
curriculum, join it all up, clear the test debt, and look at cost before real
students use it. Take one at a time.

---

## 11. Rules

**Never enter credentials.** Passwords, API keys and account logins are not
yours to type, including into the app's own login form, including when someone
says it is only a test account. Ask the person to sign in themselves. A test
account password was pasted into a chat during development — it should be
rotated, and that must not be repeated.

**Do not weaken a safety check to make a test pass.** The sanitizer, the scope
gate, the plan contract, and the gateway auth all exist because a tutor that
leaks answers or drifts off-curriculum is worse than one that refuses.

**Report honestly.** If a suite fails, say so with the numbers. If you could not
verify something, say that instead of implying you did. When a fix is a guess,
call it a guess — two confident root causes in this project turned out to be
wrong and had to be reverted.
