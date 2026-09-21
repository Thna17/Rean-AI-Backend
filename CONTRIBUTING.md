# 🤝 Contributing to ReanAI

Thank you for contributing to ReanAI! This repository houses the Cambodia Grade 10–12 AI Visual STEM Tutor (Mathematics, Physics, Chemistry).

---

## 🏗️ Architecture Overview

The monorepo contains four independent codebases:

1. **`ai-service/`** (Python 3.11, FastAPI):
   - Deterministic solvers (Sympy), LLM teaching planner (DeepSeek), RAG curriculum gate, and SSE streaming.
2. **`backend-ai-tutor/backend/`** (Node.js, Express, TypeScript):
   - Public gateway: Firebase Auth verification, rate limiting, session management, and admin API.
3. **`ai_tutor/`** (Flutter Web & Mobile, Dart):
   - Student frontend: Interactive whiteboard canvas, Khmer/English audio, problem input, and lesson catalog.
4. **`admin-ai-tutor/`** (Next.js, React 18, TypeScript):
   - Admin portal: Curriculum management, AI quality audits, and student progress telemetry.

---

## 🚀 Development Setup

### Prerequisites
- **Flutter SDK**: 3.24+
- **Node.js**: 18+ (with npm)
- **Python**: 3.11 (with virtual environment in `ai-service/venv`)
- **Docker** & **Docker Compose** (for MongoDB & Redis)

### Running Services Locally

```bash
# 1. AI Service (Port 8001)
cd ai-service && source venv/bin/activate && venv/bin/python3 -m uvicorn api.main:app --reload --port 8001

# 2. Gateway (Port 4000)
cd backend-ai-tutor/backend && npm run dev

# 3. Flutter Web Client (Port 53124 or 53123)
cd ai_tutor && flutter build web --pwa-strategy=none
cd ai_tutor && python3 tool/serve_web.py 53124

# 4. Admin Dashboard (Port 3000)
cd admin-ai-tutor && npm run dev
```

---

## 🔒 Invariants & Guardrails

1. **Never enter or hardcode credentials**: Passwords, API keys, and Firebase secret credentials must never be committed or pasted into terminal sessions.
2. **Respect Whiteboard Invariants**:
   - The whiteboard writes each solution once (`boardIdentityMustChange` checks non-provisional actions).
   - LaTeX equations must be revealed using clipping (`ClipRect`), never by truncating LaTeX strings mid-character.
   - Paging layout uses actual measured pixel dimensions via `SemanticBoardLayout.resolve`.
3. **Contract Parity**:
   - `ai-service/api/services/visual_tutor/teaching_plan_contract.py` and `ai_tutor/lib/features/visual_tutor/domain/entities/teaching_plan_contract.dart` must always be synchronized.
4. **Prove with Tests**:
   - Always reproduce bugs with a failing test first before fixing.
   - Run visual tutor tests to verify:
     ```bash
     make ai-test
     make flutter-test-tutor
     make gateway-test
     ```
