# ReanAI — Claude Code Project Context & Instructions

Cambodia Grade 10–12 AI Visual STEM Tutor (Mathematics, Physics, Chemistry).
A student enters or speaks a problem (in Khmer or English), and an animated interactive whiteboard renders the complete step-by-step worked solution while an AI tutor explains each step via text/speech, followed by interactive Q&A about any specific step. The core LLM is DeepSeek, backed by Sympy and deterministic solvers.

---

## 1. Monorepo Structure & Stack

There are 4 independent codebases under the `ReanAI/` root:

| Directory | Stack | Port | Role |
|---|---|---|---|
| `ai-service/` | Python 3.11 (`venv/`), FastAPI, Sympy, DeepSeek | **8001** | Tutor brain: solvers, whiteboard planning, curriculum RAG gate, SSE streaming |
| `backend-ai-tutor/backend/` | Node.js, Express, TypeScript, Firebase Admin | **4000** | Public API gateway: Firebase auth, rate limits, session management, proxying |
| `ai_tutor/` | Flutter (Web & Mobile), Dart, Provider/Bloc | **53123** or **53124** | Student client: animated canvas whiteboard, audio playback, chat & catalog |
| `admin-ai-tutor/` | Next.js (React 18), TypeScript, Tailwind CSS | **3000** | Admin dashboard: curriculum publishing, student monitoring, turn reviews |

*Git Note*: Outer `ReanAI/` is a git repo. `ai_tutor/` has its own separate git repository (`.git` inside `ai_tutor/`). `backend-ai-tutor/` and `admin-ai-tutor/` are untracked at the root. Always stage and commit within the respective repository.

---

## 2. Running Services & Environment Rules

### Commands to Run

```bash
# 1. AI Service (Python 3.11) — Always port 8001
cd ai-service && source venv/bin/activate && python3 -m uvicorn api.main:app --reload --port 8001

# 2. Gateway (TypeScript / Express) — Port 4000
cd backend-ai-tutor/backend && npm run dev

# 3. Flutter Web Student App — Ports 53123 or 53124 ONLY
cd ai_tutor && flutter build web --pwa-strategy=none
cd ai_tutor && python3 tool/serve_web.py 53123   # or 53124

# 4. Admin Portal (Next.js) — Port 3000
cd admin-ai-tutor && npm run dev
```

### Critical Development Rules

1. **Python Virtualenv**: Always invoke `venv/bin/python3` explicitly. Bare `python3` may invoke system Python 3.9 where modern union syntax (`str | None`) throws syntax errors.
2. **Flutter Web Origin & Ports**: Gateway CORS strictly permits `http://localhost:53123` and `http://localhost:53124`. Any other port fails CORS.
3. **Web Caching**: Flutter web must be built with `--pwa-strategy=none` and served via `tool/serve_web.py` with `Cache-Control: no-store` to prevent stale JS bundles.
4. **Auth Boundaries**:
   - Gateway verifies Firebase ID tokens from students and issues JWTs for admins.
   - `ai-service` is **internal only**; it authenticates the gateway via `X-Visual-Tutor-Internal-Token` (`visual-tutor-dev-token`) and trusts `X-Visual-Tutor-User-Id`. You can debug `ai-service` directly using these headers.

---

## 3. The Visual Tutor Engine (`ai-service`)

### Endpoints (`/api/v1/visual_tutor`)
- `POST /sessions`: Create session (`draft` or `confirmed_problem`).
- `POST /turn`: Authoritative full turn response containing all whiteboard actions, spoken message, and student task.
- `POST /turn/stream`: Server-Sent Events (SSE) live streaming preview of the turn.
- `POST /turn/step`: Interactive step submission & validation.
- `POST /telemetry`: Whiteboard client lifecycle telemetry.
- `POST /api/v1/internal/curriculum/publish`: Gateway-pushed curriculum topic sync.

### Key Modules in `ai-service/api/services/visual_tutor/`
- **`worked_solution.py`**: Solves limits via sympy; produces deterministic board actions: `ws-step-<phase>-<n>`, `ws-answer-<n>`, `ws-next-<n>`. Answer rendered as `WRITE_TEXT` + `WRITE_EQUATION` (not `final_answer_reveal` due to client task contract).
- **`solvers.py`**: Regex & sympy solver for limits. Supports both English and Khmer phrasing (`រកលីមីតនៃ`, `គណនាលីមីត`, `ពេល x ខិតទៅ`). Note: Khmer text has no word boundaries; never use `\b` with Khmer text.
- **`physics_kinematics.py` & `chemistry_stoichiometry.py`**: Solvers for Grade 10-12 physics and chemistry kinematics / stoichiometry.
- **`dynamic_worked_solution.py`**: Universal STEM problem solver fallback with step-by-step verification.
- **`rag_curriculum_gate.py` & `scope.py`**: Scope validation against Grade 10–12 MoEYS curriculum.
- **`llm_teaching_planner.py`**: DeepSeek API plan generation with prompt defense and auto-repair.
- **`response_sanitizer.py`**: Prevents answer leakage before the student reaches the solution stage.
- **`teaching_plan_contract.py`**: Strict Pydantic models (`extra="forbid"`). **Must match `teaching_plan_contract.dart` 1:1.**

### SSE Streaming Contract
- Event stream format: `event: visual_tutor\ndata: {...}`.
- Stream sends a provisional preview action (`stream-preview-<id>`) with text "Let's identify the important information first" while LLM/solver runs.
- `turn_complete` repeats the full authoritative list of actions.
- Actions must strictly include `action_id`, `board_version`, `base_board_version`, `problem_instance_id`, `active_step_id`, and timing fields, otherwise Flutter drops them silently.

---

## 4. Whiteboard & UI Invariants (`ai_tutor`)

1. **Board Writes Solution Once**:
   - The whiteboard canvas key is `ValueKey('board-$_boardIdentitySerial')`. Changing this key destroys canvas state and forces a full replay.
   - `_boardIdentitySerial` is incremented **only** via `_adoptBoardActions()` when an existing non-provisional action is removed from the arriving board.
   - Never assign board actions bypassing `_adoptBoardActions()`.
2. **Equation Reveal via Clipping**:
   - `write_equation` LaTeX animations must **never** truncate raw LaTeX strings mid-expression (which paints broken `\frac{...` syntax).
   - Render full LaTeX and clip using `ClipRect(Align(widthFactor: progress))` in `board_element_renderer.dart`.
3. **Width-Aware Layout & Pagination**:
   - Boards paginate using `SemanticBoardLayout.resolve` with actual pixel width, never line-count guesses.
   - Switching board pages (`Board 1 of 3`) must reset the pan/zoom viewport via `_showBoardFromTheTop()` to avoid blank screens.
4. **Contract Synchronization**:
   - Any schema changes in `ai-service/api/services/visual_tutor/teaching_plan_contract.py` must be mirrored in `ai_tutor/lib/features/visual_tutor/domain/entities/teaching_plan_contract.dart`.

---

## 5. Testing & Verification Guidelines

Run fast targeted tests while working; never run heavy full suites blindly on memory-constrained systems.

```bash
# AI Service — visual tutor & solvers (< 4 seconds)
cd ai-service && venv/bin/python3 -m pytest -q \
  tests/test_visual_tutor_worked_solution.py tests/test_local_limits_demo.py \
  tests/test_visual_tutor_teaching_plan_contract.py tests/test_universal_stem_solutions.py

# Flutter — visual tutor tests
cd ai_tutor && flutter test test/features/visual_tutor

# Backend Gateway — routes and controllers
cd backend-ai-tutor/backend && npm test
```

### Flutter Test Harness Rules
- In widget tests, avoid fake async deadlocks with SSE by letting the microtask loop breathe:
  ```dart
  await tester.pump(const Duration(milliseconds: 100));
  await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 1)));
  ```
- Mock audio channels (`xyz.luan/audioplayers`, `com.llfbandit.record/messages`) to prevent `MissingPluginException`.

---

## 6. Work Queue & Next Priorities

Detailed prompt specifications exist in `docs/ai-work-prompts.md`. The ordered roadmap:
1. **Remove Scan Feature**: Strip legacy camera/scanner dead code across all 3 codebases.
2. **STEM Curriculum Expansion**: Support Grade 10-12 Maths, Physics, Chemistry via RAG & deterministic solvers.
3. **Khmer Localization Depth**: Full Khmer voice & LaTeX math translation.
4. **Responsive Layout**: Seamless whiteboard scaling across phone, tablet, and desktop.
5. **Gateway & Admin Alignment**: Complete curriculum publishing lifecycle from Admin UI to AI Service RAG.
6. **Token & Cost Optimization**: DeepSeek response caching and degraded fallback mode under high load.

---

## 7. Strict Ground Rules

- **Zero Credential Typing**: Never enter passwords, Firebase secrets, or API keys into forms or terminal prompts.
- **Do Not Weaken Safety Gates**: Sanitizer, curriculum scope checks, and gateway auth must never be disabled to make a test pass.
- **Prove Before Fixing**: Reproduce bug with a failing test first, apply the minimal fix, and confirm passing.
