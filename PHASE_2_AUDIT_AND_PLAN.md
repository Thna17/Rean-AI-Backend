# 🔍 PHASE 2 AUDIT & IMPLEMENTATION PLAN
## AI Visual Tutor: Cambodia Grade 10-12 (Math, Physics, Chemistry)

**Date**: August 26, 2024  
**Status**: Phase 1 ✅ Verified | Phase 2 🚀 Ready to Begin  
**Target**: Real student testing after Phase 2

---

## 📊 PHASE 1 AUDIT RESULTS

### ✅ WHAT'S WORKING WELL

#### Backend (Python/FastAPI)
- **Problem Models** (`problem_models.py`): Clean Pydantic v2 models with excellent documentation
  - `Problem`: 11 fields including misconceptions, concepts, metadata
  - `StudentProgress`: 11 fields for tracking progress, next_review, confidence_level
  - `ProgressUpdate`: Request model for marking problems solved
  - ✅ All enums typed (ProblemSubject, ProblemDifficulty)
  - ✅ JSON schema examples included
  - ✅ Validation rules present (grade_level 10-12, difficulty 1-5)

- **Spaced Repetition Service** (`spaced_repetition_service.py`): SM-2 scheduling
  - ✅ Correct scheduling intervals (easy→7d, medium→3d, hard→1d)
  - ✅ Progress tracking with times_solved/times_failed
  - ✅ Methods: `mark_solved()`, `mark_failed()`, `get_due_problems()`, `get_stats()`
  - ✅ Uses datetime correctly with timezone awareness

- **Problem Repository** (`problem_repository.py`): JSON-based persistence
  - ✅ Loads 24 curated problems from `data/problems.json`
  - ✅ Query methods: `get_by_id()`, `get_all()`, `filter_by_subject()`, `filter_by_difficulty()`
  - ✅ Error handling present

- **Problems Router** (`routes/problems.py`): 8 REST endpoints
  - ✅ GET `/problems` → list all
  - ✅ GET `/problems/{id}` → get one problem
  - ✅ POST `/problems/{id}/solve` → mark solved + progress update
  - ✅ POST `/problems/{id}/fail` → mark failed
  - ✅ GET `/problems/due` → spaced rep schedule
  - ✅ GET `/problems/stats` → progress stats
  - ✅ Integrated into `api/main.py` (line 315+)

- **Step Sequencing Service** (`step_sequencing_service.py`): Socratic method engine
  - ✅ Enums for math/physics/chemistry step sequences
  - ✅ Initialized with kg_service and model_gateway integration points
  - ✅ Methods: `generate_teaching_plan()`, `evaluate_response()`, `get_next_step()`
  - ✅ Uses expert services (MathExpertService, PhysicsExpertService, ChemistryExpertService)
  - ⚠️ **ISSUE**: Not fully wired to routes yet (see Phase 2 tasks)

#### Frontend (Flutter/Dart)
- **Problem Entities** (`domain/entities/`): Clean data models
  - ✅ `ProblemEntity`: 11 fields matching backend
  - ✅ `StudentProgressEntity`: progress tracking
  - ✅ JSON serialization/deserialization implemented

- **Problem Provider** (`problem_provider.dart`): Riverpod state management
  - ✅ `ProblemSelectState`: filters (subject, difficulty, topic)
  - ✅ `filteredProblems` getter with multi-filter logic
  - ✅ HTTP client to fetch from `http://localhost:8001/problems`
  - ⚠️ **ISSUE**: Hardcoded URL (need config for production)

- **Problem Select Page** (`problem_select_page.dart`): Material Design UI
  - ✅ Dashboard with problem counts per subject
  - ✅ Filter chips (subject, difficulty, topic)
  - ✅ Problem cards with difficulty colors
  - ✅ Navigation to StepSequencingPage

#### Tests
- ✅ `test_problem_models.py`: Validation, serialization
- ✅ `test_spaced_repetition.py`: SM-2 scheduling, due problems, stats
- ✅ >85% coverage, all passing
- ✅ 0 warnings

#### Data
- ✅ `data/problems.json`: 24 curated problems
  - ✅ 11 Mathematics (linear, quadratic, geometry, functions)
  - ✅ 7 Physics (kinematics, dynamics, energy, etc.)
  - ✅ 6 Chemistry (bonding, reactions, stoichiometry, etc.)
  - ✅ All Grade 10-12 Cambodia curriculum aligned
  - ✅ Difficulty levels calibrated (1-5 scale)

---

### ⚠️ ISSUES FOUND

#### 1. **Step Sequencing Not Integrated to Routes**
- **Issue**: `step_sequencing_service.py` exists but NO route endpoint `/problems/{id}/teach` or `/step-sequencing`
- **Impact**: Students click problem → should go to StepSequencingPage → but API not ready
- **Phase 2 Task**: Create route `/problems/{id}/teach` that calls StepSequencingService
- **See**: Phase 2.1 below

#### 2. **Knowledge Graph Not Wired**
- **Issue**: `StepSequencingService.__init__` accepts `kg_service` but it's never used in methods
- **Impact**: No concept retrieval, prerequisite checking, or misconception guidance from KG
- **Phase 2 Task**: Implement KG calls in `generate_teaching_plan()`
- **See**: Phase 2.1 below

#### 3. **Model Gateway Integration Missing**
- **Issue**: `model_gateway` parameter accepted but not used for LLM evaluation
- **Impact**: All response grading is rule-based only (no LLM fallback)
- **Phase 2 Task**: Use model_gateway for edge cases in expert services
- **See**: Phase 2.4 below

#### 4. **User ID Hardcoded as "student_001"**
- **Issue**: Routes use hardcoded `student_id = "student_001"` 
- **Impact**: Multiple students can't be tracked separately
- **Phase 2 Task**: Extract user_id from JWT token or request context
- **See**: Phase 2.3 below

#### 5. **Flask URL Hardcoded in Flutter**
- **Issue**: `problem_provider.dart` uses `http://localhost:8001` hardcoded
- **Impact**: Won't work in production or with different ports
- **Phase 2 Task**: Move to environment config file
- **See**: Phase 2.5 below

#### 6. **Data Storage: JSON → PostgreSQL (MVP Limitation)**
- **Issue**: Problems stored in `data/problems.json` (local file, not persistent DB)
- **Impact**: Can't scale to multiple servers or persist student data long-term
- **Phase 2 Task**: Migrate to PostgreSQL in backend-service
- **See**: Phase 2.2 below

#### 7. **KG Database Re-Seeds on Every Restart**
- **Issue**: `kg_service_v3.py` line ~34 does `shutil.rmtree()` on init
- **Impact**: KG data loss on restart, not production-ready
- **Phase 2 Task**: Fix initialization pattern (migrate mode or lazy-init)
- **See**: Phase 2.1 (KG Integration)

#### 8. **No Adaptive Difficulty Yet**
- **Issue**: All problems presented equally; no "zone of proximal development" calculation
- **Impact**: Students stuck on too-hard or too-easy problems
- **Phase 2 Task**: Implement adaptive difficulty service
- **See**: Phase 2.5 below

#### 9. **No Real Student Testing Data**
- **Issue**: Difficulty levels (1-5 scale) not validated against real students
- **Impact**: May need recalibration after testing
- **Phase 2 Task**: Collect performance data from real students
- **See**: Phase 2.6 below

#### 10. **Visualization Rendering Not Tested End-to-End**
- **Issue**: Phase 0 renderers (graph, shapes, vectors, molecules) exist but not tested with actual teaching steps
- **Impact**: May have bugs when real steps try to render
- **Phase 2 Task**: Create integration tests (StepSequencing → Rich Media Canvas)
- **See**: Phase 2.7 below

---

## 🚀 PHASE 2 IMPLEMENTATION ROADMAP

### Overview
Phase 2 has **7 major tasks** = **12-16 hours** of implementation.

| Task | Hours | Priority | Status |
|------|-------|----------|--------|
| 2.1: KG Integration | 2-3 | 🔴 CRITICAL | ⏳ Ready |
| 2.2: Database Migration | 2-3 | 🟠 HIGH | ⏳ Ready |
| 2.3: Real Authentication | 2-3 | 🟠 HIGH | ⏳ Ready |
| 2.4: LLM Evaluation | 2 | 🟡 MEDIUM | ⏳ Ready |
| 2.5: Adaptive Difficulty | 1-2 | 🟡 MEDIUM | ⏳ Ready |
| 2.6: Step Sequencing Routes | 1-2 | 🔴 CRITICAL | ⏳ Ready |
| 2.7: Integration Testing | 2-3 | 🟠 HIGH | ⏳ Ready |

---

## 📋 DETAILED TASK BREAKDOWN

### **Task 2.1: Knowledge Graph Integration** (2-3 hours)
**Goal**: Connect `kg_service_v3` to expert services for concept retrieval

#### What to Do:
1. **Fix KG initialization** (`kg_service_v3.py`)
   - Remove `shutil.rmtree()` on every restart
   - Implement lazy-init or migration pattern
   
2. **Fetch prerequisites in StepSequencingService**
   - In `generate_teaching_plan()`, call `kg_service.get_prerequisites(problem.concepts)`
   - Return list of prerequisite concepts in first teaching step
   
3. **Retrieve misconceptions from KG**
   - Replace hardcoded misconceptions in expert services
   - Call `kg_service.get_misconceptions(concept)` dynamically
   
4. **Show concept map in teaching steps**
   - Add `concept_graph` field to `TeachingStep` model
   - Render in Flutter (use Rich Media Canvas)

#### Files to Modify:
- `ai-service/api/services/kg_service_v3.py` (fix initialization)
- `ai-service/api/services/step_sequencing_service.py` (integrate KG calls)
- `ai-service/api/models/teaching_step.py` (add concept_graph field)
- `ai_tutor/lib/features/visual_tutor/presentation/widgets/rich_media_canvas.dart` (render concepts)

#### Success Criteria:
- ✅ KG doesn't re-seed on startup
- ✅ Prerequisites shown in teaching steps
- ✅ Misconceptions fetched dynamically
- ✅ Concept map renders correctly

#### Test Case:
```
Student asks: "Solve 2x + 5 = 13"
Step 1 shows:
  - Question: "What operation did we start with?"
  - Concept: linear_equations
  - Prerequisites: [equality, variables, inverse_operations]
  - Misconception: "Forgetting to apply operation to both sides"
```

---

### **Task 2.2: Database Migration** (2-3 hours)
**Goal**: Move problem persistence from JSON to PostgreSQL

#### What to Do:
1. **Check backend-service schema**
   - See if `Problem` and `StudentProgress` tables exist in PostgreSQL
   - If not, create Alembic migration

2. **Create migration script**
   - `backend-service/migrations/versions/001_create_problems_tables.py`
   - Tables: `problems`, `student_progress`

3. **Migrate 24 problems from JSON to DB**
   - Script: `ai-service/scripts/migrate_problems_to_db.py`
   - Seed database with `data/problems.json` content

4. **Update ProblemRepository**
   - Replace JSON file loading with SQLAlchemy ORM queries
   - Keep same interface (methods: `get_all()`, `get_by_id()`, etc.)

5. **Test all queries still work**
   - Existing tests should pass without changes

#### Files to Create/Modify:
- New: `backend-service/migrations/versions/001_create_problems.py`
- New: `ai-service/scripts/migrate_problems_to_db.py`
- Modify: `ai-service/api/repositories/problem_repository.py`
- Modify: `ai-service/tests/test_problem_models.py` (update setup)

#### Success Criteria:
- ✅ PostgreSQL has problems table with 24 rows
- ✅ ProblemRepository queries from DB (not JSON file)
- ✅ All existing tests pass
- ✅ No API surface changes (same endpoints)

#### PostgreSQL Schema (Example):
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
  times_solved INT DEFAULT 0,
  times_failed INT DEFAULT 0,
  confidence_level VARCHAR(20),
  next_review TIMESTAMP,
  created_at TIMESTAMP,
  FOREIGN KEY (problem_id) REFERENCES problems(id)
);
```

---

### **Task 2.3: Real Authentication** (2-3 hours)
**Goal**: Replace mock "student_001" with real user context

#### What to Do:
1. **Hook Firebase Auth** (already in backend-service)
   - Extract `user_id` from JWT token in request header
   - Implement in `api/core/security.py` (create if missing)

2. **Update /problems routes**
   - Change `student_id = "student_001"` to extract from request
   - Add auth dependency to all routes

3. **Update Flutter**
   - Get `user_id` from auth provider (Firebase)
   - Pass in HTTP headers: `Authorization: Bearer {token}`

4. **Test with multiple users**
   - Each user should see separate progress

#### Files to Create/Modify:
- New/Modify: `ai-service/api/core/security.py`
- Modify: `ai-service/api/routes/problems.py`
- Modify: `ai_tutor/lib/features/visual_tutor/presentation/providers/problem_provider.dart`
- New: `ai-service/tests/test_auth_integration.py`

#### Success Criteria:
- ✅ Token extraction works
- ✅ Different users have separate progress
- ✅ Backward compatible with mock "student_001" for testing

#### Code Example (FastAPI):
```python
from fastapi import Depends, HTTPException
from api.core.security import get_user_id

@router.get("/problems")
async def list_problems(user_id: str = Depends(get_user_id)):
    return await problem_service.list_problems_for_user(user_id)
```

---

### **Task 2.4: LLM-Based Evaluation** (2 hours)
**Goal**: Use Gemini/Qwen for smarter response grading

#### What to Do:
1. **Integrate model_gateway** (already exists in Phase 0)
   - Import into expert services
   - Create grading prompt template

2. **Call LLM for edge cases**
   - Rule-based first (deterministic)
   - LLM only if rule not confident
   
3. **Extract confidence + misconceptions**
   - Parse LLM response for structured output
   - Return confidence score and detected misconceptions

4. **Add fallback logic**
   - If LLM times out or fails, use rule-based result

#### Files to Modify:
- `ai-service/api/services/math_expert_service.py` (add LLM fallback)
- `ai-service/api/services/physics_expert_service.py`
- `ai-service/api/services/chemistry_expert_service.py`
- New: `ai-service/tests/test_llm_evaluation.py`

#### Success Criteria:
- ✅ LLM used for edge cases
- ✅ Fallback works if LLM fails
- ✅ Confidence scores returned
- ✅ Tests pass

#### Prompt Template (Example):
```
Given this problem and student response:
Problem: {problem}
Student Answer: {student_answer}

Is this correct? What misconceptions might the student have?

Response format: {"is_correct": bool, "confidence": 0.0-1.0, "misconceptions": [...]}
```

---

### **Task 2.5: Adaptive Difficulty** (1-2 hours)
**Goal**: Suggest harder/easier problems based on performance

#### What to Do:
1. **Calculate zone of proximal development (ZPD)**
   - Formula: Average success rate of past 5 problems
   - If >80% → recommend harder problem
   - If <50% → recommend easier problem
   - Otherwise → similar difficulty

2. **Implement in problem selection**
   - New method: `get_recommended_next_problem(user_id)`
   - Return next problem slightly above current level

3. **Add to routes**
   - New endpoint: `GET /problems/recommend`
   - Return recommended problem with reasoning

#### Files to Create:
- New: `ai-service/api/services/adaptive_difficulty_service.py`
- Modify: `ai-service/api/routes/problems.py` (add recommend endpoint)
- New: `ai-service/tests/test_adaptive_difficulty.py`
- Modify: `ai_tutor/lib/features/visual_tutor/presentation/providers/problem_provider.dart` (call recommend)

#### Success Criteria:
- ✅ ZPD calculation accurate
- ✅ Recommendations appropriate
- ✅ Tests verify logic

#### Example:
```
Student solved last 5 problems:
- Problem 1 (Difficulty 1): ✅ Easy → 90% confidence → Mark: EASY
- Problem 2 (Difficulty 1): ✅ Easy → 85% confidence → Mark: EASY
- Problem 3 (Difficulty 2): ✅ Medium → 70% confidence → Mark: MEDIUM
- Problem 4 (Difficulty 2): ✅ Medium → 65% confidence → Mark: MEDIUM
- Problem 5 (Difficulty 3): ❌ Hard → Failed → Mark: HARD

ZPD = (EASY + EASY + MEDIUM + MEDIUM + HARD) / 5 ≈ Medium
Recommendation: Try Difficulty 3 (slightly harder)
```

---

### **Task 2.6: Step Sequencing Routes** (1-2 hours)
**Goal**: Wire StepSequencingService to REST API

#### What to Do:
1. **Create routes/step_sequencing.py**
   - Endpoint: `POST /step-sequencing/start` → Start teaching a problem
   - Endpoint: `POST /step-sequencing/{session_id}/respond` → Student responds to step
   - Endpoint: `GET /step-sequencing/{session_id}` → Get current session

2. **Manage teaching sessions**
   - Store session state in Redis or memory
   - Track: problem, steps shown, student responses, current step

3. **Hook into Flutter navigation**
   - Click problem → calls `/step-sequencing/start`
   - Loads StepSequencingPage with first teaching step

#### Files to Create/Modify:
- New: `ai-service/api/routes/step_sequencing.py`
- Modify: `ai-service/api/main.py` (include router)
- Modify: `ai_tutor/lib/features/visual_tutor/presentation/pages/step_sequencing_page.dart` (call routes)
- New: `ai-service/tests/test_step_sequencing_routes.py`

#### Success Criteria:
- ✅ Routes created and tested
- ✅ Session management works
- ✅ Flutter integration works

#### API Example:
```
POST /step-sequencing/start
Body: {
  "problem_id": "math_linear_001",
  "student_id": "student_001"
}
Response: {
  "session_id": "sess_abc123",
  "current_step": { ... TeachingStep ... },
  "total_steps": 5
}

POST /step-sequencing/sess_abc123/respond
Body: {
  "student_response": "x = 4",
  "confidence": "medium"
}
Response: {
  "is_correct": true,
  "feedback": "Good! Now...",
  "next_step": { ... }
}
```

---

### **Task 2.7: Integration Testing & Validation** (2-3 hours)
**Goal**: Test full flow: Problem → Teaching Steps → Rich Media Rendering

#### What to Do:
1. **Create end-to-end test scenario**
   - Student selects problem → API returns teaching plan
   - Flutter renders each step → student responds
   - API evaluates → provides feedback → next step

2. **Test visualization rendering**
   - Ensure graphs, shapes, vectors, molecules render correctly
   - Test with actual teaching steps (not isolated)

3. **Performance testing**
   - Measure response time: problem selection → first teaching step
   - Target: <500ms end-to-end

4. **Test with real curriculum data**
   - Run full workflow with 5-10 sample problems per subject

#### Files to Create:
- New: `ai-service/tests/test_integration_full_workflow.py`
- New: `ai_tutor/test/integration/visual_tutor_integration_test.dart`
- New: `PHASE_2_TESTING_REPORT.md`

#### Success Criteria:
- ✅ Full workflow works end-to-end
- ✅ Visualizations render correctly
- ✅ Performance acceptable (<500ms)
- ✅ No regression in Phase 0 or Phase 1

#### Test Scenario (Python):
```python
async def test_full_teaching_flow():
    # 1. Get problem
    problem = await problem_repo.get_by_id("math_linear_001")
    
    # 2. Generate teaching plan
    plan = await step_seq_service.generate_teaching_plan(
        problem=problem.problem,
        subject="mathematics",
        grade_level=10
    )
    
    # 3. Verify step count
    assert len(plan.steps) >= 3
    
    # 4. Verify visualizations
    for step in plan.steps:
        if step.visualization:
            assert step.visualization.type in ["equation", "graph", "shape"]
    
    # 5. Simulate student response
    response = await step_seq_service.evaluate_response(
        step_id=plan.steps[0].id,
        student_response="2x = 8",
        confidence="medium"
    )
    assert response.is_correct == True
    
    # 6. Get next step
    next_step = plan.steps[1]
    assert next_step is not None
```

---

## 🎯 EXECUTION STRATEGY

### Recommended Order:
1. **Start with Task 2.6** (Step Sequencing Routes)
   - Quick win, unblocks UI testing
   - Builds on existing StepSequencingService

2. **Then Task 2.1** (KG Integration)
   - Critical for realistic teaching
   - Most impact on learning quality

3. **Then Task 2.3** (Real Auth)
   - Necessary before real student testing
   - Medium complexity

4. **Then Task 2.2** (Database Migration)
   - Largest refactor, but non-blocking
   - Do after other features working

5. **Then Task 2.4** (LLM Evaluation)
   - Optional for MVP (rule-based good enough)
   - Can be added later if needed

6. **Then Task 2.5** (Adaptive Difficulty)
   - Nice-to-have, depends on real student data
   - Do after Phase 2.6 testing

7. **Finally Task 2.7** (Integration Testing)
   - Continuous throughout; final validation

---

## ⚙️ IMPLEMENTATION PATTERNS (FROM PHASE 0 & 1)

### Python Services
```python
class MyService:
    def __init__(self, kg_service=None, model_gateway=None):
        self.kg_service = kg_service
        self.model_gateway = model_gateway
        self.service_name = "my_service"
        logger = logging.getLogger(__name__)
    
    async def do_something(self, input_data: InputModel) -> OutputModel:
        # Type hints everywhere
        # Async/await
        # Raise HTTPException for errors
        # Log with logger, never print()
        pass
```

### Dart Widgets
```dart
class MyWidget extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(myProvider);
    
    return state.when(
      loading: () => const LoadingWidget(),
      error: (error, stack) => ErrorWidget(error: error),
      data: (data) => DataWidget(data: data),
    );
  }
}
```

### Tests
```python
# pytest fixture for setup
@pytest.fixture
def service():
    return MyService()

async def test_do_something(service):
    result = await service.do_something(input_data)
    assert result.is_correct == True
```

---

## 📊 SUCCESS METRICS

After Phase 2, you should have:

- ✅ **Backend**: 12 REST endpoints (8 from Phase 1 + 4 new step sequencing)
- ✅ **Frontend**: 3 main pages (problem selection, step sequencing, progress)
- ✅ **Database**: Problems and progress persisted in PostgreSQL
- ✅ **Teaching**: Step-by-step Socratic method with visualizations
- ✅ **Knowledge Graph**: Concepts, prerequisites, misconceptions integrated
- ✅ **Spaced Repetition**: SM-2 scheduling working
- ✅ **Tests**: >85% coverage, all passing
- ✅ **Documentation**: Clear, up-to-date

---

## 🚨 CRITICAL REMINDERS

### Do NOT:
1. ❌ Skip KG integration (it's why this is "AI" tutor)
2. ❌ Hardcode user IDs (makes multi-user testing impossible)
3. ❌ Leave JSON file as final storage (not production-ready)
4. ❌ Forget to test visualization rendering end-to-end
5. ❌ Add new features beyond Phase 2 scope (save for Phase 3)

### Watch Out For:
1. ⚠️ KG database re-seeding on restart
2. ⚠️ Model Gateway first call timeout (lazy loading)
3. ⚠️ PostgreSQL migration data validation
4. ⚠️ Firebase token format in Flutter
5. ⚠️ Visualization performance with complex graphs

---

## 📚 QUICK REFERENCE

| Issue | Root Cause | Phase 2 Task | Fix Time |
|-------|-----------|-------------|----------|
| No step sequencing API | Not wired to routes | 2.6 | 1-2h |
| KG unused | Integration missing | 2.1 | 2-3h |
| Hardcoded user_id | No real auth | 2.3 | 2-3h |
| JSON data storage | MVP limitation | 2.2 | 2-3h |
| No adaptive difficulty | Feature not built | 2.5 | 1-2h |
| Visualizations untested E2E | No integration tests | 2.7 | 2-3h |

---

## ✅ NEXT STEPS

1. **Read this document** ← You're here
2. **Start with Task 2.6** (Step Sequencing Routes)
   - Takes 1-2 hours
   - Unblocks UI testing
   - Then move to 2.1, 2.3, etc.

3. **Follow coding patterns** from Phase 0/1
   - Async/await in Python
   - Riverpod in Flutter
   - Comprehensive tests

4. **Run tests constantly**
   - `pytest` for Python
   - `flutter test` for Dart
   - Target >85% coverage

5. **Document as you go**
   - Update PHASE_2_AUDIT_AND_PLAN.md as tasks complete
   - Keep README.md current

---

**Status**: Phase 1 ✅ → Phase 2 🚀 Ready  
**Next Agent Start Point**: Task 2.6 (Step Sequencing Routes)  
**Expected Completion**: 12-16 hours  
**Ready to Build?** YES! 🚀
