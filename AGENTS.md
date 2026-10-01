# ReanAI — Multi-Agent Coordination

## Agent Roles & Responsibilities

| Role | Target Area | Trigger |
|---|---|---|
| Code Reviewer | `ai-service/`, `ai_tutor/`, `backend-ai-tutor/backend/`, `admin-ai-tutor/` | After non-trivial features or refactors |
| Test Writer | `ai-service/tests/`, `ai_tutor/test/`, `backend/src/**/__tests__/` | Bug fixes, new solvers, curriculum changes |
| Contract Guardian | `teaching_plan_contract.py` & `teaching_plan_contract.dart` | Whenever whiteboard actions or payload schemas change |
| Whiteboard Specialist | `ai_tutor/lib/screens/tutor/` & `visual_tutor/presentation/` | Board single-write, SVG/Canvas rendering, pagination |

## Ownership Map

| Area | Stack | Owner |
|---|---|---|
| `ai-service/` | FastAPI, Python 3.11 | AI Brain: Solvers (Sympy), DeepSeek LLM, RAG curriculum gate, SSE streaming |
| `backend-ai-tutor/backend/` | Express, TypeScript | Gateway: Firebase Auth, Rate limiting, Session proxy, Admin API |
| `ai_tutor/` | Flutter (Web/Mobile) | Student Client: Whiteboard Canvas, Audio/Speech, Catalog navigation |
| `admin-ai-tutor/` | Next.js, React 18 | Admin Portal: Curriculum authoring/publishing, telemetry review |

## Coordination Protocol

1. **Read `CLAUDE.md` and `GEMINI.md` first**: Respect the whiteboard invariants (§5 in `GEMINI.md`).
2. **Contract parity**: Never change `teaching_plan_contract.py` without updating `teaching_plan_contract.dart`.
3. **Prove with tests**: Write a failing test first, verify the failure, fix, and report exact test counts.
4. **No credential exposure**: Never embed or automate passwords, Firebase credentials, or secret keys.
