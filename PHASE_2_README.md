# 🎓 AI VISUAL TUTOR - Phase 2 Implementation Guide

**Project Goal**: Build an AI visual tutor that teaches like a real 1-1 teacher for Cambodia Grade 10-12 (Math, Physics, Chemistry).

**Current Status**: Phase 1 ✅ Complete | Phase 2 🚀 Starting Now

---

## 📚 DOCUMENTATION (Read in This Order)

### 1. **START HERE**: `PHASE_2_QUICK_START.md`
   - ⏱️ 5 minutes to read
   - 📋 Checklist format (what to do)
   - 🎯 Recommended execution order
   - ✅ Success criteria per task

### 2. **UNDERSTAND THE VISION**: `VISUAL_TUTOR_VISION.md`
   - ⏱️ 10 minutes to read
   - 🎨 How students experience the tutor
   - 🔧 Technical architecture
   - 📊 Curriculum coverage (24 problems)

### 3. **DETAILED PLAN**: `PHASE_2_AUDIT_AND_PLAN.md`
   - ⏱️ 15 minutes to read
   - 🔍 10 issues found in Phase 1 audit
   - 📋 7 detailed tasks with code examples
   - ⚠️ Pitfalls to avoid

### 4. **PROJECT STATUS**: `PHASE_2_STATUS_SUMMARY.md`
   - ⏱️ 10 minutes to read
   - 📈 What Phase 0 & 1 built
   - 🎯 What Phase 2 will build
   - 📊 Metrics and timeline

### 5. **CODING STANDARDS**: `.github/copilot-instructions.md`
   - Conventions for Python (FastAPI)
   - Conventions for Dart/Flutter
   - Architecture patterns (Model → Service → Route)

---

## 🗂️ PROJECT STRUCTURE

```
ReanAI/
├── ai-service/                          # Python FastAPI AI Service
│   ├── api/
│   │   ├── models/
│   │   │   └── problem_models.py         ✅ Phase 1 (done)
│   │   │   └── teaching_step.py          ✅ Phase 0 (done)
│   │   ├── services/
│   │   │   ├── step_sequencing_service.py   ✅ Phase 0 (done, not wired)
│   │   │   ├── spaced_repetition_service.py ✅ Phase 1 (done)
│   │   │   ├── problem_repository.py        ✅ Phase 1 (done)
│   │   │   ├── math_expert_service.py       ✅ Phase 0 (done)
│   │   │   ├── physics_expert_service.py    ✅ Phase 0 (done)
│   │   │   ├── chemistry_expert_service.py  ✅ Phase 0 (done)
│   │   │   ├── kg_service_v3.py             ✅ Phase 0 (exists, not wired)
│   │   │   └── model_gateway.py             ✅ Phase 0 (exists, not used)
│   │   ├── routes/
│   │   │   ├── problems.py                  ✅ Phase 1 (done)
│   │   │   └── step_sequencing.py           ⏳ Phase 2 Task 2.6
│   │   ├── core/
│   │   │   ├── database.py                  ✅ Exists
│   │   │   └── security.py                  ⏳ Phase 2 Task 2.3 (needs update)
│   │   └── main.py                          ✅ Phase 1 (update for Phase 2)
│   ├── data/
│   │   └── problems.json                    ✅ 24 curated problems
│   └── tests/
│       ├── test_problem_models.py           ✅ Phase 1
│       ├── test_spaced_repetition.py        ✅ Phase 1
│       └── test_step_sequencing_routes.py   ⏳ Phase 2 Task 2.6
│
├── ai_tutor/                            # Flutter App
│   └── lib/features/visual_tutor/
│       ├── domain/entities/
│       │   ├── problem_entity.dart          ✅ Phase 1
│       │   └── progress_entity.dart         ✅ Phase 1
│       ├── presentation/
│       │   ├── providers/
│       │   │   └── problem_provider.dart    ✅ Phase 1 (update for Phase 2)
│       │   ├── pages/
│       │   │   ├── problem_select_page.dart ✅ Phase 1
│       │   │   └── step_sequencing_page.dart ⏳ Update for Phase 2 Task 2.6
│       │   ├── widgets/
│       │   │   └── rich_media_canvas.dart   ✅ Phase 0
│       │   └── services/
│       │       ├── graph_renderer.dart      ✅ Phase 0
│       │       ├── geometric_renderer.dart  ✅ Phase 0
│       │       ├── vector_renderer.dart     ✅ Phase 0
│       │       └── molecule_renderer.dart   ✅ Phase 0
│       └── test/
│           └── problem_integration_test.dart ⏳ Phase 2 Task 2.7
│
├── backend-service/                     # Django/FastAPI (external)
│   └── (Needs: Problem/StudentProgress tables in Phase 2 Task 2.2)
│
├── Documentation Files (READ THESE):
│   ├── PHASE_2_QUICK_START.md               ← START HERE
│   ├── VISUAL_TUTOR_VISION.md               ← Read next
│   ├── PHASE_2_AUDIT_AND_PLAN.md            ← Detailed tasks
│   ├── PHASE_2_STATUS_SUMMARY.md            ← Project status
│   ├── PHASE_2_README.md                    ← This file
│   ├── PHASE_1_IMPLEMENTATION_COMPLETE.md   ← Reference
│   └── PHASE_0_COMPLETE_FINAL_SUMMARY.md    ← Reference
│
└── .github/
    └── copilot-instructions.md              ← Coding standards
```

---

## 🚀 QUICK START (5 Minutes)

### Prerequisites
```bash
# Python 3.11+
python --version

# Node.js + Flutter 3.x
flutter doctor

# PostgreSQL (for Phase 2 Task 2.2)
postgres --version

# Dependencies
cd ai-service && pip install -r requirements.txt
cd ai_tutor && flutter pub get
```

### Run Phase 1 (Current)
```bash
# Terminal 1: Start AI Service
cd ai-service
python -m uvicorn api.main:app --reload --port 8001

# Terminal 2: Test API
curl http://localhost:8001/problems

# Terminal 3: Start Flutter App
cd ai_tutor
flutter run
```

### Run Tests
```bash
# Python tests
cd ai-service
pytest                  # All tests
pytest -v              # Verbose
pytest --cov=api       # With coverage (>85% target)

# Dart tests
cd ai_tutor
flutter test           # All tests
flutter analyze        # Check warnings (0 target)
```

---

## 🎯 PHASE 2 TASKS (Summary)

### Task 2.6: Step Sequencing Routes (1-2h) ← **START HERE**
**What**: Create API endpoints for teaching workflow  
**Why**: Students can't access teaching without routes  
**Files**:
- Create: `ai-service/api/routes/step_sequencing.py`
- Modify: `ai-service/api/main.py`
- Create: `ai-service/tests/test_step_sequencing_routes.py`
- Modify: `ai_tutor/lib/features/visual_tutor/presentation/pages/step_sequencing_page.dart`

**Endpoints**:
```
POST /step-sequencing/start
  Body: {problem_id, student_id}
  Response: {session_id, current_step, total_steps}

POST /step-sequencing/{session_id}/respond
  Body: {student_response, confidence}
  Response: {is_correct, feedback, next_step}

GET /step-sequencing/{session_id}
  Response: {current_step, progress, session_state}
```

---

### Task 2.1: Knowledge Graph Integration (2-3h)
**What**: Connect KG to teaching logic  
**Why**: AI needs knowledge to teach, not just rules  
**Files**:
- Modify: `ai-service/api/services/kg_service_v3.py` (fix re-seeding)
- Modify: `ai-service/api/services/step_sequencing_service.py`
- Modify: `ai-service/api/models/teaching_step.py`

**Integration Points**:
- Fetch prerequisites before teaching
- Retrieve misconceptions from KG
- Build concept map for student visualization

---

### Task 2.3: Real Authentication (2-3h)
**What**: Replace mock "student_001" with JWT tokens  
**Why**: Real student testing requires multi-user support  
**Files**:
- Create/Modify: `ai-service/api/core/security.py`
- Modify: `ai-service/api/routes/problems.py`
- Modify: `ai-service/api/routes/step_sequencing.py`
- Modify: `ai_tutor/lib/features/visual_tutor/presentation/providers/problem_provider.dart`

**Pattern**:
```python
@router.get("/problems")
async def list_problems(user_id: str = Depends(get_user_id)):
    # user_id extracted from JWT token
    return await service.list_for_user(user_id)
```

---

### Task 2.2: Database Migration (2-3h)
**What**: Move problems/progress from JSON to PostgreSQL  
**Why**: JSON not scalable or persistent  
**Files**:
- Create: `backend-service/migrations/versions/001_create_problems.py`
- Create: `ai-service/scripts/migrate_problems_to_db.py`
- Modify: `ai-service/api/repositories/problem_repository.py`

**Schema**:
```sql
CREATE TABLE problems (
  id TEXT PRIMARY KEY,
  subject VARCHAR(20),
  grade_level INT,
  topic VARCHAR(100),
  difficulty INT,
  problem TEXT,
  answer TEXT,
  expected_steps INT,
  misconceptions JSONB,
  concepts JSONB,
  created_at TIMESTAMP
);

CREATE TABLE student_progress (
  id UUID PRIMARY KEY,
  student_id TEXT,
  problem_id TEXT,
  times_solved INT,
  next_review TIMESTAMP,
  FOREIGN KEY (problem_id) REFERENCES problems(id)
);
```

---

### Task 2.4: LLM Evaluation (2h)
**What**: Use Gemini/Qwen for edge case grading  
**Why**: Rule-based works, LLM adds intelligence  
**Files**:
- Modify: `ai-service/api/services/math_expert_service.py`
- Modify: `ai-service/api/services/physics_expert_service.py`
- Modify: `ai-service/api/services/chemistry_expert_service.py`
- Create: `ai-service/tests/test_llm_evaluation.py`

**Pattern**:
```python
async def evaluate_response(self, problem, response):
    # Rule-based first (fast, deterministic)
    rule_result = self._rule_based_evaluate(problem, response)
    
    if rule_result.confidence > 0.8:
        return rule_result
    
    # LLM fallback for uncertain cases
    llm_result = await self.model_gateway.evaluate(problem, response)
    return llm_result
```

---

### Task 2.5: Adaptive Difficulty (1-2h)
**What**: Recommend problems based on student performance  
**Why**: Personalization improves learning outcomes  
**Files**:
- Create: `ai-service/api/services/adaptive_difficulty_service.py`
- Modify: `ai-service/api/routes/problems.py`
- Create: `ai-service/tests/test_adaptive_difficulty.py`

**Algorithm** (Zone of Proximal Development):
```python
def calculate_zpd(student_history):
    # Average confidence of last 5 problems
    if avg_confidence > 80%:
        return "recommend_harder"  # Difficulty +1
    elif avg_confidence < 50%:
        return "recommend_easier"  # Difficulty -1
    else:
        return "similar_difficulty"
```

---

### Task 2.7: Integration Testing (2-3h)
**What**: Test full workflow end-to-end  
**Why**: Ensure all parts work together  
**Tests**:
- End-to-end: Problem → Teaching → Response → Feedback
- Performance: All actions <500ms
- Visualization: Graphs/shapes/vectors render correctly
- Data: Progress properly tracked in DB

**Test Scenario**:
```python
async def test_full_teaching_flow():
    # 1. Select problem
    problem = await problem_repo.get_by_id("math_linear_001")
    
    # 2. Start teaching
    session = await step_seq_service.start(problem)
    assert len(session.steps) > 0
    
    # 3. Student responds
    result = await step_seq_service.respond(session.id, "x = 4")
    assert result.is_correct == True
    
    # 4. Progress updated
    progress = await spaced_rep_service.get_progress(student_id, problem.id)
    assert progress.times_solved == 1
```

---

## 📊 EXECUTION ROADMAP

```
Week 1 (Mon-Tue):
  Task 2.6: Routes (1-2h)     → Unblocks UI
  Task 2.1: KG Integration (2-3h) → High impact

Week 1 (Wed):
  Task 2.3: Auth (2-3h)       → Multi-user ready

Week 1 (Thu-Fri):
  Task 2.2: Database (2-3h)   → Persistent storage
  Task 2.4: LLM (2h)          → Smart grading
  Task 2.5: Adaptive (1-2h)   → Personalization

Week 2 (Mon):
  Task 2.7: Testing (2-3h)    → Full validation

Week 2 (Tue-Wed):
  Real student testing begins!
```

---

## ✅ SUCCESS CRITERIA

### Code Quality
- [ ] Test coverage >85% (Python + Dart)
- [ ] 0 warnings in `flutter analyze`
- [ ] All type hints present
- [ ] Clear docstrings on public APIs

### Functionality
- [ ] 12 REST endpoints (8 from Phase 1 + 4 Phase 2)
- [ ] Full teaching workflow works (select → teach → respond → feedback)
- [ ] Multi-user auth working
- [ ] Data persisted in PostgreSQL
- [ ] Knowledge graph integrated
- [ ] LLM evaluation fallback working
- [ ] Adaptive difficulty recommendations working

### Performance
- [ ] Problem load: <100ms
- [ ] Step rendering: <100ms
- [ ] Response evaluation: <200ms
- [ ] Full workflow (start → first step): <500ms

### Testing
- [ ] Unit tests for each service (Phase 2 tasks)
- [ ] Integration tests for full workflow
- [ ] Performance benchmarks
- [ ] Real problem scenarios tested (5-10 per subject)

---

## 🛠️ TROUBLESHOOTING

### Python
```bash
# ModuleNotFoundError: No module named 'api'
# → Make sure you're in ai-service directory with right Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# PostgreSQL connection error
# → Ensure PostgreSQL running: brew services start postgresql

# Tests failing
# → pytest --tb=short (show short traceback)
# → pytest -v (verbose mode)
# → pytest --lf (run last failing)
```

### Dart/Flutter
```bash
# pubspec.yaml dependencies not found
flutter clean && flutter pub get

# Compilation errors
flutter analyze

# Widget not rendering
# → Check hot reload (r key)
# → Check error logs (flutter run verbose)

# Tests failing
flutter test --verbose
```

---

## 📞 CODE REVIEW CHECKLIST (Before Committing)

- [ ] Functions/methods have type hints
- [ ] Docstrings present for public APIs
- [ ] No `print()` statements (use `logger` in Python)
- [ ] All async operations are properly awaited
- [ ] Error handling with exceptions (not silent failures)
- [ ] Tests written (>85% coverage target)
- [ ] Tests passing locally
- [ ] No hardcoded credentials or URLs
- [ ] Configuration external (use .env or config files)
- [ ] Code follows patterns from Phase 0/1

---

## 📚 REFERENCE LINKS

| Document | Purpose | Read Time |
|----------|---------|-----------|
| `PHASE_2_QUICK_START.md` | Execution checklist | 5 min |
| `VISUAL_TUTOR_VISION.md` | Product vision | 10 min |
| `PHASE_2_AUDIT_AND_PLAN.md` | Detailed tasks | 20 min |
| `PHASE_2_STATUS_SUMMARY.md` | Project status | 10 min |
| `.github/copilot-instructions.md` | Coding standards | 10 min |
| `PHASE_1_IMPLEMENTATION_COMPLETE.md` | Phase 1 details | Reference |
| `PHASE_0_COMPLETE_FINAL_SUMMARY.md` | Phase 0 details | Reference |

---

## 🎓 LEARNING RESOURCES

### AI Teaching (Pedagogical)
- Socratic Method: Ask questions, guide discovery
- Misconception-Driven Teaching: Diagnose, teach concept, reteach
- Spaced Repetition: Optimal review timing (SM-2 algorithm)
- Zone of Proximal Development (ZPD): Personalize difficulty

### Technical Stack
- **Python**: FastAPI, Pydantic v2, async/await
- **Dart/Flutter**: Riverpod, Provider pattern, Material Design 3
- **Database**: PostgreSQL, SQLAlchemy ORM
- **Testing**: pytest, flutter_test

### Cambodia Curriculum
- Grade 10-12 Mathematics (linear, quadratic, geometry, trig)
- Grade 10-12 Physics (kinematics, dynamics, energy, waves)
- Grade 10-12 Chemistry (bonding, reactions, stoichiometry, equilibrium)

---

## 🚀 NEXT STEPS

1. **Read** `PHASE_2_QUICK_START.md` (5 min)
2. **Review** `PHASE_2_AUDIT_AND_PLAN.md` (20 min)
3. **Start coding** Task 2.6 (1-2 hours)
4. **Run tests** constantly
5. **Document** progress in this file
6. **Move to** Task 2.1, 2.3, 2.2, etc. in order

---

## 📞 SUPPORT

If stuck:
1. Check the issue in `PHASE_2_AUDIT_AND_PLAN.md` (10 issues listed)
2. Review code patterns in `PHASE_0_COMPLETE_FINAL_SUMMARY.md`
3. Check Phase 1 implementation for reference patterns
4. Run tests with verbose output (`pytest -v`)
5. Check error logs in terminal output

---

## ✨ REMEMBER

This is not just a chatbot—it's an **AI Visual Tutor** that teaches like a real teacher.

Every design decision should serve this goal:
- ✅ Step-by-step teaching (not full answers)
- ✅ Visual rendering (graphs, shapes, diagrams)
- ✅ Socratic method (questions before telling)
- ✅ Misconception detection (diagnose and teach)
- ✅ Adaptation (personalize to each student)

**You're building something meaningful for Cambodia students.** 🚀

---

**Status**: Phase 1 ✅ | Phase 2 🚀 Ready | MVP Testing 📅 Sept 3

**Last Updated**: August 26, 2024  
**Ready to Build?** YES! 🎉
