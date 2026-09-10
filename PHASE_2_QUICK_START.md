# ⚡ PHASE 2 QUICK START CHECKLIST

**For the next agent**: Start here. Read this + PHASE_2_AUDIT_AND_PLAN.md

---

## 🎯 YOUR MISSION (12-16 hours)

Turn Phase 1 (working problem bank) into Phase 2 (working teaching system).

### Key Wins:
- ✅ Students can ask a problem and AI teaches step-by-step
- ✅ Knowledge graph provides real concept guidance
- ✅ Multiple students tracked separately (real auth)
- ✅ Data persisted in database (not JSON)
- ✅ All tested, 0 warnings, >85% coverage

---

## 📋 PRE-FLIGHT CHECKLIST (Before You Start)

- [ ] Read `PHASE_2_AUDIT_AND_PLAN.md` (understanding of 10 issues found)
- [ ] Read `VISUAL_TUTOR_VISION.md` (why we're building this)
- [ ] Run existing tests: `cd ai-service && pytest` → All pass?
- [ ] Run Flutter: `cd ai_tutor && flutter analyze` → 0 warnings?
- [ ] Check file locations:
  - [ ] `ai-service/api/models/problem_models.py` exists
  - [ ] `ai-service/api/services/step_sequencing_service.py` exists
  - [ ] `ai_tutor/lib/features/visual_tutor/` exists with entities, providers, pages

---

## 🚀 RECOMMENDED EXECUTION ORDER

Do tasks in this order (tested sequence):

### 1️⃣ **TASK 2.6: Step Sequencing Routes** (1-2 hours) ⭐ START HERE
**Why first?** Unblocks UI testing. Quick win.

**What to do**:
- [ ] Create `ai-service/api/routes/step_sequencing.py` (3 endpoints)
- [ ] Add routes to `ai-service/api/main.py`
- [ ] Create tests `ai-service/tests/test_step_sequencing_routes.py`
- [ ] Update Flutter page to call new routes
- [ ] Test: Can start teaching a problem? Get first step? Respond?

**Expected time**: 1-2 hours  
**Result**: Students can access teaching workflow

---

### 2️⃣ **TASK 2.1: Knowledge Graph Integration** (2-3 hours)
**Why second?** Most impactful for learning quality.

**What to do**:
- [ ] Fix KG database re-seeding in `kg_service_v3.py`
- [ ] Call KG in `step_sequencing_service.generate_teaching_plan()`
- [ ] Fetch prerequisites and misconceptions from KG
- [ ] Add `concept_graph` field to `TeachingStep` model
- [ ] Test: Teaching plan includes KG concepts?

**Expected time**: 2-3 hours  
**Result**: AI teaches using knowledge graph

---

### 3️⃣ **TASK 2.3: Real Authentication** (2-3 hours)
**Why third?** Necessary before real student testing.

**What to do**:
- [ ] Implement token extraction in `api/core/security.py`
- [ ] Update routes to use `get_user_id()` dependency
- [ ] Update Flutter to pass auth token in requests
- [ ] Test: Different users have separate progress?

**Expected time**: 2-3 hours  
**Result**: Multi-user system ready

---

### 4️⃣ **TASK 2.2: Database Migration** (2-3 hours)
**Why fourth?** Largest refactor, but non-blocking.

**What to do**:
- [ ] Create PostgreSQL migrations for `problems`, `student_progress` tables
- [ ] Migrate 24 problems from JSON to DB
- [ ] Update `ProblemRepository` to use SQLAlchemy
- [ ] Test: All queries work with DB?

**Expected time**: 2-3 hours  
**Result**: Production-ready data persistence

---

### 5️⃣ **TASK 2.4: LLM Evaluation** (2 hours)
**Why fifth?** Optional for MVP but nice-to-have.

**What to do**:
- [ ] Integrate `model_gateway` into expert services
- [ ] Add LLM fallback for edge cases
- [ ] Create grading prompt template
- [ ] Test: LLM evaluation works?

**Expected time**: 2 hours  
**Result**: Smarter response grading

---

### 6️⃣ **TASK 2.5: Adaptive Difficulty** (1-2 hours)
**Why sixth?** Depends on real student data.

**What to do**:
- [ ] Implement `adaptive_difficulty_service.py`
- [ ] Calculate ZPD for each student
- [ ] Add `/problems/recommend` endpoint
- [ ] Test: Recommendations are appropriate?

**Expected time**: 1-2 hours  
**Result**: Smart problem recommendations

---

### 7️⃣ **TASK 2.7: Integration Testing** (2-3 hours)
**Why last?** Final validation.

**What to do**:
- [ ] Create end-to-end test scenario (problem selection → teaching → response → feedback)
- [ ] Test visualization rendering in real teaching
- [ ] Performance test (response time <500ms?)
- [ ] Test with 5-10 sample problems per subject

**Expected time**: 2-3 hours  
**Result**: Full workflow validated

---

## 📊 TIME ALLOCATION

```
Task 2.6 (Routes)           1-2h    ✅ QUICK WIN
Task 2.1 (KG)               2-3h    ✅ HIGH IMPACT
Task 2.3 (Auth)             2-3h    ✅ CRITICAL
Task 2.2 (Database)         2-3h    ✅ FOUNDATIONAL
Task 2.4 (LLM)              2h      ✅ FALLBACK
Task 2.5 (Adaptive)         1-2h    ✅ NICE-TO-HAVE
Task 2.7 (Testing)          2-3h    ✅ VALIDATION
────────────────────────────
TOTAL:                       12-16h
```

**Realistic timeline**: 3-4 working days (assuming 4h/day coding)

---

## 🛠️ TOOLS YOU'LL NEED

- **Python**: FastAPI, Pydantic, pytest, SQLAlchemy
- **Dart/Flutter**: Riverpod, http, flutter_test
- **Database**: PostgreSQL (or SQLite for local testing)
- **Testing**: pytest (Python), flutter test (Dart)
- **API Testing**: Postman or curl

---

## 📖 CODE PATTERNS TO FOLLOW

### Python Service Pattern
```python
async def my_method(self, input_data: MyModel) -> OutputModel:
    """Clear docstring with Args and Returns"""
    # Type hints everywhere
    # Async/await (no blocking I/O)
    logger.info(f"Processing {input_data.id}")
    
    # Raise HTTPException for errors
    if not input_data.is_valid():
        raise HTTPException(status_code=400, detail="Invalid input")
    
    result = await self.kg_service.fetch(input_data.id)
    return OutputModel(**result)
```

### Dart Widget Pattern
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

### Test Pattern
```python
@pytest.fixture
async def service():
    return MyService()

async def test_my_method(service):
    result = await service.my_method(input_data)
    assert result.is_valid == True
```

---

## ✅ SUCCESS CRITERIA (Per Task)

### Task 2.6 (Routes)
- [ ] Endpoint: `POST /step-sequencing/start` works
- [ ] Endpoint: `POST /step-sequencing/{session_id}/respond` works
- [ ] Flutter calls routes and displays steps
- [ ] Tests pass

### Task 2.1 (KG)
- [ ] KG doesn't re-seed on startup
- [ ] Prerequisites shown in teaching steps
- [ ] Misconceptions fetched from KG
- [ ] Tests pass

### Task 2.3 (Auth)
- [ ] Token extraction works
- [ ] Different users tracked separately
- [ ] Backward compatible with mock "student_001"
- [ ] Tests pass

### Task 2.2 (Database)
- [ ] PostgreSQL has 24 problems
- [ ] ProblemRepository queries DB
- [ ] All Phase 1 tests still pass
- [ ] No API surface changes

### Task 2.4 (LLM)
- [ ] LLM grading works
- [ ] Fallback to rule-based if LLM fails
- [ ] Tests pass

### Task 2.5 (Adaptive)
- [ ] ZPD calculation accurate
- [ ] Recommendations appropriate
- [ ] Tests pass

### Task 2.7 (Testing)
- [ ] End-to-end workflow works
- [ ] Visualizations render correctly
- [ ] Response time <500ms
- [ ] All tests pass

---

## 🐛 COMMON PITFALLS (Avoid These!)

### ❌ Don't Do:
1. Skip testing—test as you go
2. Hardcode user IDs—use auth
3. Forget to handle errors—raise exceptions properly
4. Ignore performance—measure response times
5. Leave TODOs without fixing—complete your task

### ⚠️ Watch Out For:
1. **KG Re-Seeding**: Check `kg_service_v3.py` line ~34
2. **Model Gateway Timeout**: First call loads models (slow)
3. **PostgreSQL Migration Risk**: Test migrations thoroughly
4. **Firebase Token Format**: Different from mock auth
5. **Visualization Performance**: Don't render huge graphs

---

## 📞 DECISION TREE (If Stuck)

```
Question: Should I add a new feature?
├─ Is it in Phase 2 scope? → YES: Do it | NO: Save for Phase 3
│
Question: Test failing, what now?
├─ Is the test correct? → YES: Fix code | NO: Fix test
│
Question: Performance slow, what now?
├─ Is it <500ms? → YES: Ship it | NO: Optimize
│
Question: Unsure about architecture?
├─ Check Phase 0 or 1 code for patterns
│
Question: Need new dependency?
├─ Does Phase 0/1 use it? → YES: Use same version | NO: Ask
```

---

## 📚 REFERENCE FILES (Keep These Open)

1. **PHASE_2_AUDIT_AND_PLAN.md** — Detailed task breakdown (read this!)
2. **VISUAL_TUTOR_VISION.md** — Why we're building this
3. **.github/copilot-instructions.md** — Project conventions
4. **PHASE_1_IMPLEMENTATION_COMPLETE.md** — What Phase 1 built (reference)
5. **PHASE_0_COMPLETE_FINAL_SUMMARY.md** — Phase 0 context (reference)

---

## 🚀 QUICK REFERENCE: CRITICAL COMMANDS

```bash
# Python (ai-service)
cd ai-service
pytest                          # Run all tests
pytest -v                       # Verbose
pytest --cov=api               # With coverage
python -m uvicorn api.main:app --reload   # Run server

# Dart/Flutter (ai_tutor)
cd ai_tutor
flutter analyze                 # Check for warnings
flutter test                    # Run tests
flutter run                     # Run app
flutter clean && flutter pub get  # Clean cache
```

---

## 📝 PROGRESS TRACKING

After each task, update: `PHASE_2_AUDIT_AND_PLAN.md`

Add at the top:
```markdown
## 🔄 PROGRESS

- [x] Task 2.6: Step Sequencing Routes (2h) ✅ Complete
- [ ] Task 2.1: Knowledge Graph Integration
- [ ] Task 2.3: Real Authentication
- ...
```

---

## ⏰ TIME ESTIMATE

If you work efficiently and follow patterns from Phase 0/1:

- **2.6 (Routes)**: 1-2h → Quick win
- **2.1 (KG)**: 2-3h → Medium complexity
- **2.3 (Auth)**: 2-3h → Dependent on backend design
- **2.2 (DB)**: 2-3h → Largest refactor
- **2.4 (LLM)**: 1-2h → Integration work
- **2.5 (Adaptive)**: 1-2h → Algorithm + service
- **2.7 (Testing)**: 2-3h → Validation pass

**Total**: 12-16 hours  
**Per day** (4h): 3-4 days  
**Per week**: Should be done by Friday if started Monday

---

## ✨ FINAL CHECKLIST (Before You Start Coding)

- [ ] Read PHASE_2_AUDIT_AND_PLAN.md (understanding)
- [ ] Read VISUAL_TUTOR_VISION.md (context)
- [ ] All Phase 1 tests pass (`pytest`, `flutter analyze`)
- [ ] Understand 10 issues found in audit
- [ ] Know the 7 tasks and recommended order
- [ ] Have PostgreSQL/SQLite ready for Task 2.2
- [ ] Have Postman or curl for API testing
- [ ] Have flutter test ready for Flutter tests

---

## 🎬 YOU'RE READY TO START

**Next step**: Implement **Task 2.6 (Step Sequencing Routes)**

This task:
- Takes only 1-2 hours
- Unblocks entire UI testing flow
- Uses patterns from existing codebase
- Has clear success criteria

**After 2.6**, move to 2.1, 2.3, etc. in order.

---

**Status**: Phase 2 🚀 Ready to Begin  
**Estimated Completion**: 12-16 hours  
**Quality Target**: >85% test coverage, 0 warnings  
**MVP Target**: Real student testing after Phase 2

**LET'S BUILD IT!** 🚀
