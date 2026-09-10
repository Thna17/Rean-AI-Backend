# 📋 PHASE 1 AUDIT: Problem Bank + Spaced Repetition
**Date**: August 26, 2024  
**Status**: Pre-Implementation Audit  
**Target**: 8-10 hours to MVP  

---

## 🎯 PHASE 1 VISION

Transform Phase 0 foundation into a **curriculum-aligned problem bank** with **adaptive spaced repetition**. After Phase 1, the system will be a testable MVP ready for real students.

### Core Goals
1. **Problem Bank**: 20-30 curated problems (Math focus, Physics/Chemistry secondary)
2. **Spaced Repetition**: SM-2 algorithm for scheduling reviews
3. **Curriculum Alignment**: Cambodia Grade 10-12 standards
4. **End-to-End Flow**: Select problem → Solve step-by-step → Track progress

---

## 🔍 PHASE 0 STATE (BASELINE)

### What's Already Built
✅ **Visual Rendering**
- RichMediaCanvas with % positioning (responsive)
- Graph, Geometric, Vector, Molecule renderers
- Animation support, <100ms performance

✅ **Step Sequencing**
- Backend: TeachingStep models, StepSequencingService
- Frontend: Riverpod state, Material Design UI
- API routes for `/teaching/plans` endpoint

✅ **Subject Experts**
- MathExpertService: 10 problem types, intelligent detection
- PhysicsExpertService: 7 problem types
- ChemistryExpertService: 6 problem types
- Total: 23 problem types, 25+ misconceptions detected

### What's NOT Built (Phase 1 Targets)
❌ **Problem Bank**: No persistent problem storage
❌ **Spaced Repetition**: No progress tracking, no scheduling
❌ **Problem Selection UI**: No interface to browse/select problems
❌ **User Progress**: No way to track solved/pending problems
❌ **Curriculum Alignment**: Problems exist but not in structured format

---

## 📁 FILE STRUCTURE (EXISTING)

### Backend
```
ai-service/
├── api/
│   ├── models/
│   │   ├── teaching_step.py          ✅ Phase 0
│   │   └── subject_expert_models.py  ✅ Phase 0
│   ├── services/
│   │   ├── step_sequencing_service.py        ✅ Phase 0
│   │   ├── math_expert_service.py            ✅ Phase 0
│   │   ├── physics_expert_service.py         ✅ Phase 0
│   │   ├── chemistry_expert_service.py       ✅ Phase 0
│   │   ├── problem_bank_service.py           ❌ Phase 1
│   │   └── spaced_repetition_service.py      ❌ Phase 1
│   ├── routes/
│   │   ├── step_sequencing.py        ✅ Phase 0
│   │   └── problems.py               ❌ Phase 1
│   ├── repositories/
│   │   └── problem_repository.py      ❌ Phase 1
│   └── main.py                        ✅ Phase 0
├── data/
│   └── problems.json                  ❌ Phase 1
├── tests/
│   ├── test_expert_services.py        ✅ Phase 0
│   └── test_problem_bank.py           ❌ Phase 1
└── requirements.txt                   ✅ (May need updates)
```

### Frontend
```
ai_tutor/lib/features/visual_tutor/
├── domain/
│   ├── entities/
│   │   ├── teaching_step_entity.dart  ✅ Phase 0
│   │   └── problem_entity.dart        ❌ Phase 1
├── presentation/
│   ├── providers/
│   │   ├── teaching_step_provider.dart ✅ Phase 0
│   │   └── problem_provider.dart       ❌ Phase 1
│   ├── pages/
│   │   ├── step_sequencing_page.dart   ✅ Phase 0
│   │   └── problem_select_page.dart    ❌ Phase 1
│   ├── services/
│   │   └── (renderers)                 ✅ Phase 0
│   └── widgets/
│       └── (board widgets)             ✅ Phase 0
└── test/
    └── problem_select_test.dart        ❌ Phase 1
```

---

## 🏗️ ARCHITECTURE DECISIONS (PHASE 1)

### 1. Problem Model Design
```python
# Problem structure (from curriculum)
{
  "id": "math_linear_001",
  "subject": "mathematics",  # math, physics, chemistry
  "grade_level": 10,         # 10, 11, 12
  "topic": "linear_equations",
  "subtopic": "two_step_equations",
  "difficulty": 1,           # 1 (easy) to 5 (hard)
  "problem": "Solve 2x + 5 = 13 for x",
  "answer": "4",
  "solution_method": "inverse_operations",
  "expected_steps": 4,
  "misconceptions": [
    "sign_error",
    "forgot_division",
    "division_before_subtraction"
  ],
  "concepts": [
    "inverse_operations",
    "equality",
    "variables"
  ],
  "tags": ["cambodia_grade_10", "algebra"]
}
```

### 2. Progress Tracking Model
```python
# Student progress (per problem)
{
  "student_id": "student_001",
  "problem_id": "math_linear_001",
  "times_solved": 2,
  "times_failed": 1,
  "last_seen": "2024-08-26T10:30:00Z",
  "confidence_level": "medium",  # easy, medium, hard
  "next_review": "2024-08-29T10:30:00Z",  # SM-2 schedule
  "time_spent_seconds": 450,
  "misconceptions_detected": ["sign_error"]
}
```

### 3. Spaced Repetition Algorithm (SM-2)
**Simplified for MVP** (not full SM-2, but industry-standard approach):
- **Easy** (confidence 4-5): Review in 7 days, increment interval
- **Medium** (confidence 3): Review in 3 days, reset interval
- **Hard** (confidence 1-2): Review tomorrow, reset interval
- **Never seen**: Available for new problems

**Key Formula**:
```
next_review = today + interval_days
interval_days = {
  "easy": 7,
  "medium": 3,
  "hard": 1,
  "new": 0 (available now)
}
```

### 4. Problem Selection Strategy (MVP)
For Phase 1, use **simple curriculum-based selection**:
- Filter by subject, grade, difficulty
- Return problems due for review (spaced repetition schedule)
- OR return new problems if none due
- Randomize order within difficulty band

**Later (Phase 2)**: Add knowledge graph prerequisites, adaptive difficulty.

### 5. Data Storage (MVP)
Use **JSON file** for Phase 1 MVP:
- `ai-service/data/problems.json`: Curated problem bank
- Progress stored in **temporary in-memory dict** (keyed by student_id)
- Mock user_id: "student_001" for testing

**Later (Phase 2)**: Migrate to PostgreSQL via backend-service.

---

## 📋 PHASE 1 TASKS (BREAKDOWN)

### Task 1.1: Problem Bank Models (1 hour) ✅
**File**: `ai-service/api/models/problem_models.py`

Create Pydantic models:
- `Problem`: Complete problem definition
- `ProblemDifficulty`: Enum (EASY, MEDIUM, HARD, ADVANCED, EXPERT)
- `ProblemSubject`: Enum (MATH, PHYSICS, CHEMISTRY)
- `ProblemTopic`: Enum (curriculum topics)

**Success**: All models validate correctly, match data structure

---

### Task 1.2: Spaced Repetition Service (2 hours) ✅
**File**: `ai-service/api/services/spaced_repetition_service.py`

Implement:
- `StudentProgress` model
- `SpacedRepetitionService`:
  - `schedule_review(problem_id, confidence_level)` → next_review date
  - `get_due_problems(student_id)` → List[Problem]
  - `mark_solved(student_id, problem_id, confidence_level)` → update progress
  - `get_progress_summary(student_id)` → stats (solved, pending, etc.)

**Success**: SM-2 scheduling works, progress updates correctly

---

### Task 1.3: Problem Repository (1 hour) ✅
**File**: `ai-service/api/repositories/problem_repository.py`

Implement:
- Load problems from JSON
- Query methods:
  - `get_all()` → List[Problem]
  - `get_by_id(problem_id)` → Problem
  - `get_by_subject(subject)` → List[Problem]
  - `get_by_difficulty(difficulty)` → List[Problem]
  - `get_by_topic(topic)` → List[Problem]
  - `search(filters)` → List[Problem]

**Success**: All queries return correct filtered results

---

### Task 1.4: Problem Curation (2-3 hours) 🎯
**File**: `ai-service/data/problems.json`

Curate 20-30 problems:
- **Mathematics (10-12 problems)**:
  - Linear equations (2-3): 2x+5=13, x-7=3, 3x=12
  - Quadratic (2-3): x²-5x+6=0, 2x²+3x-2=0
  - Geometry (2): Area of triangle, angle sum
  - Functions (2): f(x)=2x+1 evaluation, domain/range
  - Algebra (2-3): Factoring, expanding, simplifying

- **Physics (6-8 problems)**:
  - Kinematics (2): v=u+at, s=ut+½at²
  - Dynamics (2): F=ma, friction problems
  - Energy (2): KE=½mv², PE=mgh
  - Waves (1): Frequency/wavelength

- **Chemistry (4-6 problems)**:
  - Bonding (2): Lewis structures, valence electrons
  - Reactions (2): Balancing, stoichiometry
  - Molecular structure (1): Molecular weight

**Requirements**:
- Each problem must be solvable via existing expert services
- Difficulty: Mix of 1 (easy) to 5 (hard)
- Include Cambodia curriculum keywords
- All verified before inclusion

**Success**: JSON is valid, all problems solvable by experts

---

### Task 1.5: Backend API Routes (1-2 hours) ✅
**File**: `ai-service/api/routes/problems.py`

Implement endpoints:
- `GET /problems` → List problems (with filters: subject, difficulty, topic)
- `GET /problems/{id}` → Get single problem
- `POST /problems/{id}/solve` → Mark solved, update progress, return next_review
- `GET /student/{student_id}/progress` → Progress summary
- `GET /student/{student_id}/due-problems` → Due for review

**Success**: All endpoints work, return correct JSON, integrate with services

---

### Task 1.6: Flutter Integration (2-3 hours) ✅
**File**: `ai_tutor/lib/features/visual_tutor/presentation/pages/problem_select_page.dart`

Implement:
- `ProblemSelectPage`: Shows problem list
  - Filter buttons: Subject, Difficulty, Topic
  - Problem cards: Title, difficulty badge, last seen, confidence
  - CTA: "Start Problem" button
  
- UI state management:
  - Load problems via API
  - Apply filters (client-side or API-based)
  - Show loading/error states
  
- Navigation:
  - Tap problem → navigate to `StepSequencingPage` (already exists)
  - Pass problem data via route args
  - On completion → return to problem list

- Progress dashboard:
  - Show: "3/10 problems solved", "2 due for review"
  - Streak counter
  - Time spent

**Success**: Can select, start, and track problems end-to-end

---

### Task 1.7: Testing (1 hour) ✅
**Files**: 
- `ai-service/tests/test_problem_models.py`
- `ai-service/tests/test_spaced_repetition.py`
- `ai_tutor/test/features/visual_tutor/problem_select_page_test.dart`

Tests:
- Problem model validation
- Spaced repetition scheduling
- Problem repository queries
- API endpoint responses
- Flutter state management
- End-to-end flow

**Success**: >80% coverage, all tests pass

---

## 🧩 INTEGRATION POINTS (PHASE 1)

### Backend Integration (ALREADY DONE via Phase 0)
```python
# In StepSequencingService (Phase 0):
async def generate_teaching_plan(problem: str, subject: str, ...):
    # Already routes to math/physics/chemistry experts
    # Phase 1 will call this AFTER problem is selected
```

### Frontend Integration (NEW)
```dart
// Problem selection → Step sequencing (NEW)
ProblemSelectPage:
  onProblemTap() {
    // Load problem data
    // Navigate to StepSequencingPage(problem_data)
    // Back button: return to ProblemSelectPage
  }

// Completion → Progress update (NEW)
StepSequencingPage:
  onComplete() {
    // POST /problems/{id}/solve
    // Update progress
    // Return to ProblemSelectPage
  }
```

---

## 🎓 CURRICULUM ALIGNMENT (CAMBODIA GRADE 10-12)

### Mathematics
- **Linear**: Equations, systems, inequalities
- **Algebra**: Factoring, expanding, polynomials
- **Geometry**: Triangles, circles, area, volume
- **Functions**: Domain, range, composition, inverses
- **Trigonometry**: Sine, cosine, tangent, identities

### Physics
- **Kinematics**: Motion, velocity, acceleration
- **Dynamics**: Forces, Newton's laws, friction
- **Energy**: Kinetic, potential, conservation
- **Waves**: Properties, interference, resonance
- **Electricity**: Circuits, resistance, current

### Chemistry
- **Bonding**: Ionic, covalent, metallic, Lewis structures
- **Reactions**: Balancing, types, stoichiometry
- **Solutions**: Concentration, molarity, dilution
- **Thermodynamics**: Heat, entropy, equilibrium
- **Kinetics**: Rate, catalysts, mechanisms

---

## 🚀 PHASE 1 TIMELINE

| Task | Duration | Status |
|------|----------|--------|
| 1.1: Models | 1 hour | ⏳ |
| 1.2: Spaced Rep | 2 hours | ⏳ |
| 1.3: Repository | 1 hour | ⏳ |
| 1.4: Curation | 2-3 hours | ⏳ |
| 1.5: API Routes | 1-2 hours | ⏳ |
| 1.6: Flutter | 2-3 hours | ⏳ |
| 1.7: Testing | 1 hour | ⏳ |
| **Total** | **8-10 hours** | **⏳** |

---

## ✅ SUCCESS CRITERIA

- [ ] `problem_models.py` with all Pydantic models
- [ ] `spaced_repetition_service.py` with SM-2 scheduling
- [ ] `problem_repository.py` with query methods
- [ ] `ai-service/data/problems.json` with 20-30 curated problems
- [ ] `problems.py` routes with all endpoints
- [ ] `problem_select_page.dart` with filter/select UI
- [ ] End-to-end flow works: Select → Solve → Track → Review
- [ ] >80% test coverage
- [ ] Zero compiler warnings
- [ ] Ready for MVP testing with real students

---

## 🎯 MVP SUCCESS DEFINITION

**A student can**:
1. Open the app and see "Problem Selection" page
2. Filter by subject/difficulty/topic
3. Select a problem
4. Solve it step-by-step (via Phase 0 Step Sequencing)
5. Mark as complete
6. See progress updated
7. Get shown next review date
8. Come back later and see "due for review" problems
9. Understand they're learning with an AI teacher, not a chatbot

**System can**:
- Load problems from curriculum-aligned bank
- Intelligently schedule reviews (SM-2)
- Evaluate responses via expert services
- Render visualizations for each subject
- Track progress per student
- Suggest next problem based on difficulty/topic

---

## 🔗 INTEGRATION WITH PHASE 0

### What We Keep
- ✅ RichMediaCanvas (Phase 0.1)
- ✅ Rich Media Renderers (Phase 0.2)
- ✅ StepSequencingService (Phase 0.3)
- ✅ Subject Experts (Phase 0.4)

### What We Add
- ✅ Problem selection UI (Problem Select Page)
- ✅ Progress tracking (Spaced Repetition Service)
- ✅ Problem persistence (Problem Bank)
- ✅ Curriculum alignment (Curated problem JSON)

### What We DON'T Touch Yet (Phase 2)
- ❌ Knowledge Graph integration (KG service exists, not wired)
- ❌ LLM-based evaluation (rule-based first)
- ❌ Authentication (mock user_id for MVP)
- ❌ Database migration (JSON for MVP)
- ❌ Analytics/metrics (log locally for MVP)

---

## 🎓 NEXT STEPS AFTER PHASE 1

### Phase 2: Knowledge Graph Integration
- Wire `kg_service` to expert services
- Retrieve prerequisites before showing problem
- Show concept map
- Track misconceptions per student

### Phase 3: Adaptive Difficulty
- Use learning data to adjust problem difficulty
- Implement "zone of proximal development" (ZPD)
- Suggest problems just above current level

### Phase 4: Real Student Testing
- Deploy MVP to Cambodia partner school
- Collect real performance data
- Calibrate difficulty levels
- Gather user feedback

### Phase 5: Mobile Optimization
- Offline-first problem selection
- Caching visualizations
- Better mobile gestures for drawing

---

## 📞 BLOCKERS & DEPENDENCIES

### No Blockers for Phase 1
- ✅ Phase 0 is production-ready
- ✅ All models/services available
- ✅ Flutter build is stable
- ✅ Backend API working

### Dependencies
- Python 3.11+ (already installed)
- Flutter 3.x (already installed)
- Dart 3.x (already installed)

### Assumptions
- Cambodia curriculum topics defined (we'll use standard ones)
- Problem difficulty calibration comes from expert review (not ML, not yet)
- User auth mocked for MVP (real auth in Phase 2)

---

## 📊 QUALITY METRICS (TARGET)

| Metric | Target | Status |
|--------|--------|--------|
| Compiler Errors | 0 | ⏳ |
| Compiler Warnings | 0 | ⏳ |
| Type Hints | 100% | ⏳ |
| Test Coverage | >80% | ⏳ |
| Code Style | analysis_options.yaml | ⏳ |
| Documentation | All public methods | ⏳ |
| Performance | <500ms per API call | ⏳ |

---

## 🎯 READY TO IMPLEMENT?

**Yes!** Phase 0 is solid. Phase 1 is well-defined. Time to build the MVP.

Next: Create implementation prompts for AI code generation.
