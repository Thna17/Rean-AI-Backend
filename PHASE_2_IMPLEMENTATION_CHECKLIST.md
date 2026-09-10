# ✅ PHASE 2 IMPLEMENTATION CHECKLIST

Use this to track progress as you implement each task.

---

## 📋 TASK 2.6: STEP SEQUENCING ROUTES (1-2 hours)

**Status**: ⏳ Not Started  
**Start Date**: ___________  
**End Date**: ___________  
**Actual Hours**: ___________

### Deliverables
- [ ] File created: `ai-service/api/routes/step_sequencing.py`
- [ ] File created: `ai-service/tests/test_step_sequencing_routes.py`
- [ ] File modified: `ai-service/api/main.py` (include router)
- [ ] File modified: `ai_tutor/lib/features/visual_tutor/presentation/pages/step_sequencing_page.dart`

### Code Requirements
- [ ] Endpoint: `POST /step-sequencing/start`
  - [ ] Takes: `problem_id`, `student_id`
  - [ ] Returns: `session_id`, `current_step`, `total_steps`
  - [ ] Calls: `step_sequencing_service.generate_teaching_plan()`
  - [ ] Stores session in Redis or memory

- [ ] Endpoint: `POST /step-sequencing/{session_id}/respond`
  - [ ] Takes: `student_response`, `confidence`
  - [ ] Returns: `is_correct`, `feedback`, `next_step`
  - [ ] Calls: `step_sequencing_service.evaluate_response()`
  - [ ] Routes to next step or completion

- [ ] Endpoint: `GET /step-sequencing/{session_id}`
  - [ ] Returns current session state
  - [ ] For progress tracking

### Testing
- [ ] Test: Can start teaching a problem?
- [ ] Test: Can respond to a step?
- [ ] Test: Can get session state?
- [ ] Test: Session expires after timeout?
- [ ] Coverage: >85%
- [ ] No warnings in `flutter analyze`

### Integration
- [ ] Flutter `step_sequencing_page.dart` calls `POST /step-sequencing/start`
- [ ] Flutter displays returned `current_step`
- [ ] Flutter sends student response via `POST /step-sequencing/{session_id}/respond`
- [ ] Flutter navigates to next step or completion page

### Verification
- [ ] Run: `pytest ai-service/tests/test_step_sequencing_routes.py`
- [ ] Result: ✅ All passing
- [ ] Run: `flutter test`
- [ ] Result: ✅ All passing
- [ ] Run: `flutter analyze`
- [ ] Result: ✅ 0 warnings

---

## 📋 TASK 2.1: KNOWLEDGE GRAPH INTEGRATION (2-3 hours)

**Status**: ⏳ Not Started  
**Start Date**: ___________  
**End Date**: ___________  
**Actual Hours**: ___________

### Fix KG Re-Seeding
- [ ] Open: `ai-service/api/services/kg_service_v3.py`
- [ ] Find: `shutil.rmtree()` call on init
- [ ] Problem: Database deleted on every restart
- [ ] Solution: Use migration pattern or lazy-init
- [ ] Verify: KG data persists after restart

### Integrate KG into Step Sequencing
- [ ] Modify: `ai-service/api/services/step_sequencing_service.py`
- [ ] In method `generate_teaching_plan()`:
  - [ ] Call: `self.kg_service.get_prerequisites(problem.concepts)`
  - [ ] Call: `self.kg_service.get_misconceptions(concept)`
  - [ ] Return prerequisites in first teaching step
  - [ ] Include misconceptions in step guidance

### Update Teaching Step Model
- [ ] Modify: `ai-service/api/models/teaching_step.py`
- [ ] Add field: `concept_graph: Optional[Dict[str, Any]]`
- [ ] Populate: With concept prerequisites and relationships
- [ ] Document: What concept_graph contains

### Flutter Visualization
- [ ] Modify: `ai_tutor/lib/features/visual_tutor/presentation/widgets/rich_media_canvas.dart`
- [ ] Add rendering for `concept_graph`
- [ ] Display: Concept map or prerequisite list
- [ ] Test: Renders without errors

### Testing
- [ ] Test: KG doesn't re-seed on startup
- [ ] Test: Prerequisites fetched correctly
- [ ] Test: Misconceptions included in steps
- [ ] Test: Concept graph renders in Flutter
- [ ] Coverage: >85%
- [ ] All tests passing

### Verification
- [ ] Run: `pytest ai-service/tests/test_kg_integration.py`
- [ ] Result: ✅ All passing
- [ ] Check: `data/` folder (KG data still there after restart)
- [ ] Run: Flutter app (visualize concept map)

---

## 📋 TASK 2.3: REAL AUTHENTICATION (2-3 hours)

**Status**: ⏳ Not Started  
**Start Date**: ___________  
**End Date**: ___________  
**Actual Hours**: ___________

### Implement Token Extraction
- [ ] Create/Modify: `ai-service/api/core/security.py`
- [ ] Implement: `get_user_id(request: Request) -> str`
  - [ ] Extract JWT from `Authorization: Bearer {token}`
  - [ ] Decode token using Firebase public keys
  - [ ] Return `user_id` from token claims
  - [ ] Raise `HTTPException(401)` if invalid token

### Update Backend Routes
- [ ] Modify: `ai-service/api/routes/problems.py`
  - [ ] Add dependency: `user_id = Depends(get_user_id)` to all routes
  - [ ] Remove hardcoded: `student_id = "student_001"`
  - [ ] Pass `user_id` to services

- [ ] Modify: `ai-service/api/routes/step_sequencing.py`
  - [ ] Same dependency injection pattern
  - [ ] Pass `user_id` to all service calls

### Update Flutter
- [ ] Modify: `ai_tutor/lib/features/visual_tutor/presentation/providers/problem_provider.dart`
  - [ ] Import: Firebase auth provider
  - [ ] In HTTP client setup:
    - [ ] Get `user_id` from `ref.watch(firebaseAuthProvider)`
    - [ ] Add header: `Authorization: Bearer {token}`
  - [ ] Pass `user_id` in request body if needed

### Backward Compatibility
- [ ] Keep mock user "student_001" for local testing
- [ ] Check for token; use mock if missing
- [ ] Environment variable: `USE_MOCK_AUTH=true` for testing

### Testing
- [ ] Test: Token extraction works
- [ ] Test: Different users tracked separately
- [ ] Test: Invalid token returns 401
- [ ] Test: Mock auth still works (for testing)
- [ ] Test: Progress stored per user

### Verification
- [ ] Run: `pytest ai-service/tests/test_auth_integration.py`
- [ ] Result: ✅ All passing
- [ ] Create 2 test users, verify separate progress
- [ ] Curl test: `curl -H "Authorization: Bearer {token}" http://localhost:8001/problems`

---

## 📋 TASK 2.2: DATABASE MIGRATION (2-3 hours)

**Status**: ⏳ Not Started  
**Start Date**: ___________  
**End Date**: ___________  
**Actual Hours**: ___________

### Create PostgreSQL Migrations
- [ ] Check: Does `backend-service` exist with PostgreSQL?
- [ ] Create: `backend-service/migrations/versions/001_create_problems.py`
  - [ ] Table: `problems` (11 fields)
  - [ ] Table: `student_progress` (11 fields)
  - [ ] Indexes: On problem_id, student_id, next_review
  - [ ] Foreign keys: student_progress → problems

### Schema Verification
- [ ] Table `problems` has columns:
  - [ ] id (TEXT, PRIMARY KEY)
  - [ ] subject (VARCHAR)
  - [ ] grade_level (INT)
  - [ ] topic (VARCHAR)
  - [ ] difficulty (INT)
  - [ ] problem (TEXT)
  - [ ] answer (TEXT)
  - [ ] expected_steps (INT)
  - [ ] misconceptions (JSONB)
  - [ ] concepts (JSONB)
  - [ ] created_at (TIMESTAMP)

- [ ] Table `student_progress` has columns:
  - [ ] id (UUID, PRIMARY KEY)
  - [ ] student_id (TEXT)
  - [ ] problem_id (TEXT, FK)
  - [ ] times_solved (INT)
  - [ ] times_failed (INT)
  - [ ] confidence_level (VARCHAR)
  - [ ] next_review (TIMESTAMP)
  - [ ] time_spent_seconds (INT)
  - [ ] misconceptions_detected (JSONB)
  - [ ] created_at (TIMESTAMP)
  - [ ] updated_at (TIMESTAMP)

### Data Migration
- [ ] Create: `ai-service/scripts/migrate_problems_to_db.py`
- [ ] Script loads `data/problems.json`
- [ ] Script inserts 24 problems into PostgreSQL
- [ ] Verify: 24 rows in `problems` table

### Update Repository
- [ ] Modify: `ai-service/api/repositories/problem_repository.py`
  - [ ] Remove: JSON file loading logic
  - [ ] Add: SQLAlchemy ORM queries
  - [ ] Implement: `get_all()`, `get_by_id()`, `filter_by_subject()`, `filter_by_difficulty()`
  - [ ] Keep same interface (no API changes)

### Connection String
- [ ] `.env` file has: `DATABASE_URL=postgresql://user:pass@localhost:5432/problems`
- [ ] Test connection before running migration

### Testing
- [ ] Test: All Phase 1 tests still pass (same API interface)
- [ ] Test: Can query 24 problems from DB
- [ ] Test: Filters work (by subject, difficulty)
- [ ] Test: Can insert/update progress in DB
- [ ] Coverage: >85%

### Verification
- [ ] Run: `python ai-service/scripts/migrate_problems_to_db.py`
- [ ] Check: `psql` → `SELECT COUNT(*) FROM problems;` → 24 ✅
- [ ] Run: `pytest ai-service/tests/`
- [ ] Result: ✅ All Phase 1 tests still passing

---

## 📋 TASK 2.4: LLM EVALUATION (2 hours)

**Status**: ⏳ Not Started  
**Start Date**: ___________  
**End Date**: ___________  
**Actual Hours**: ___________

### Integrate Model Gateway
- [ ] Check: `ai-service/api/services/model_gateway.py` exists
- [ ] Verify: Has methods for Qwen, Gemini, etc.
- [ ] Test: Model gateway can be imported and initialized

### Add LLM Fallback to Expert Services
- [ ] Modify: `ai-service/api/services/math_expert_service.py`
  - [ ] In `evaluate_response()` method:
    - [ ] Step 1: Try rule-based evaluation
    - [ ] Step 2: If confidence < 0.8, call LLM
    - [ ] Step 3: Return LLM result or rule-based if LLM fails
    - [ ] Add timeout handling (max 3 seconds)

- [ ] Modify: `ai-service/api/services/physics_expert_service.py`
  - [ ] Same pattern as math

- [ ] Modify: `ai-service/api/services/chemistry_expert_service.py`
  - [ ] Same pattern as math

### Create Grading Prompt
- [ ] Define prompt template for LLM:
  ```
  Given problem: {problem}
  Student answer: {student_response}
  
  Is this correct? What misconceptions?
  
  Return JSON: {"is_correct": bool, "confidence": 0-1, "misconceptions": [...]}
  ```

### Fallback Logic
- [ ] If LLM timeout → Use rule-based result
- [ ] If LLM error → Use rule-based result
- [ ] If LLM succeeds → Use LLM result
- [ ] Log all evaluations for debugging

### Testing
- [ ] Test: Rule-based evaluation first (fast)
- [ ] Test: LLM fallback triggered on low confidence
- [ ] Test: Timeout handling works
- [ ] Test: Error handling works
- [ ] Create: `ai-service/tests/test_llm_evaluation.py`

### Verification
- [ ] Run: `pytest ai-service/tests/test_llm_evaluation.py`
- [ ] Result: ✅ All passing
- [ ] Test with actual problem: See LLM called for edge cases

---

## 📋 TASK 2.5: ADAPTIVE DIFFICULTY (1-2 hours)

**Status**: ⏳ Not Started  
**Start Date**: ___________  
**End Date**: ___________  
**Actual Hours**: ___________

### Create Service
- [ ] Create: `ai-service/api/services/adaptive_difficulty_service.py`
- [ ] Implement: `calculate_zpd(student_history: List[ProgressUpdate]) -> float`
  - [ ] Get last 5 problems
  - [ ] Average confidence level
  - [ ] Return "easy" / "medium" / "hard" or numeric score (1-5)

### Implement Algorithm
- [ ] If avg_confidence > 80%:
  - [ ] Recommend difficulty +1
  - [ ] Or recommend harder topic

- [ ] If avg_confidence < 50%:
  - [ ] Recommend difficulty -1
  - [ ] Or recommend easier topic

- [ ] Otherwise:
  - [ ] Recommend similar difficulty

### Add Route
- [ ] Modify: `ai-service/api/routes/problems.py`
- [ ] Add endpoint: `GET /problems/recommend`
  - [ ] Query param: `student_id`
  - [ ] Response: Problem object + reasoning
  - [ ] Call: `adaptive_difficulty_service.get_recommendation()`

### Testing
- [ ] Test: ZPD calculation accurate
- [ ] Test: Recommendations appropriate
- [ ] Test: Handles edge cases (new student, all easy, all hard)
- [ ] Create: `ai-service/tests/test_adaptive_difficulty.py`

### Verification
- [ ] Run: `pytest ai-service/tests/test_adaptive_difficulty.py`
- [ ] Result: ✅ All passing
- [ ] Test endpoint: `curl http://localhost:8001/problems/recommend?student_id=student_001`

---

## 📋 TASK 2.7: INTEGRATION TESTING (2-3 hours)

**Status**: ⏳ Not Started  
**Start Date**: ___________  
**End Date**: ___________  
**Actual Hours**: ___________

### End-to-End Test
- [ ] Create: `ai-service/tests/test_integration_full_workflow.py`
- [ ] Scenario 1: Select problem → Get first step
  - [ ] Get problem from DB
  - [ ] Call `POST /step-sequencing/start`
  - [ ] Verify: current_step returned with visualization
  - [ ] Measure: Response time <500ms

- [ ] Scenario 2: Respond to step → Get next step
  - [ ] Call `POST /step-sequencing/{session_id}/respond`
  - [ ] Verify: is_correct, feedback, next_step
  - [ ] Measure: Response time <200ms

- [ ] Scenario 3: Complete problem → Progress updated
  - [ ] Complete all steps
  - [ ] Verify: Problem marked solved in DB
  - [ ] Verify: next_review scheduled (SM-2)

### Visualization Testing
- [ ] Create: `ai_tutor/test/integration/visual_tutor_integration_test.dart`
- [ ] Test: Graph rendering (equation animation)
- [ ] Test: Shape rendering (triangle, circle)
- [ ] Test: Vector rendering (arrows, forces)
- [ ] Test: Molecule rendering (atoms, bonds)
- [ ] Verify: No exceptions, smooth animation

### Performance Testing
- [ ] Measure: Problem load time (<100ms)
- [ ] Measure: Step render time (<100ms)
- [ ] Measure: Response evaluation (<200ms)
- [ ] Measure: Full workflow start-to-first-step (<500ms)
- [ ] Use: Benchmarking tools or stopwatch

### Problem Coverage
- [ ] Test with: 5 Math problems (different types)
- [ ] Test with: 5 Physics problems (different types)
- [ ] Test with: 5 Chemistry problems (different types)
- [ ] Verify: All render correctly, all complete

### Data Validation
- [ ] Verify: Student progress saved to DB
- [ ] Verify: Misconceptions tracked
- [ ] Verify: Time spent recorded
- [ ] Verify: Spaced repetition scheduled

### Testing
- [ ] Run: `pytest ai-service/tests/test_integration_full_workflow.py`
- [ ] Result: ✅ All passing
- [ ] Run: `flutter test ai_tutor/test/integration/`
- [ ] Result: ✅ All passing
- [ ] Performance: All metrics <target

### Final Validation
- [ ] No regressions in Phase 0 or Phase 1 tests
- [ ] Coverage remains >85%
- [ ] 0 warnings in Flutter

---

## 📊 OVERALL PROGRESS

```
TASK 2.6: Step Sequencing Routes
  Progress: ░░░░░░░░░░ 0%

TASK 2.1: Knowledge Graph Integration
  Progress: ░░░░░░░░░░ 0%

TASK 2.3: Real Authentication
  Progress: ░░░░░░░░░░ 0%

TASK 2.2: Database Migration
  Progress: ░░░░░░░░░░ 0%

TASK 2.4: LLM Evaluation
  Progress: ░░░░░░░░░░ 0%

TASK 2.5: Adaptive Difficulty
  Progress: ░░░░░░░░░░ 0%

TASK 2.7: Integration Testing
  Progress: ░░░░░░░░░░ 0%

TOTAL PHASE 2: ░░░░░░░░░░ 0%
```

---

## 📝 NOTES & ISSUES

### Issues Found During Implementation:
```
Issue 1: ___________
Status: ⏳ Open
Solution: ___________
Resolution Date: ___________

Issue 2: ___________
Status: ⏳ Open
Solution: ___________
Resolution Date: ___________
```

### Decisions Made:
```
Decision 1: ___________
Rationale: ___________
Date: ___________

Decision 2: ___________
Rationale: ___________
Date: ___________
```

### Performance Improvements:
```
Optimization 1: ___________
Benchmark: Before ___ ms, After ___ ms
Date: ___________

Optimization 2: ___________
Benchmark: Before ___ ms, After ___ ms
Date: ___________
```

---

## ✅ FINAL SIGN-OFF

**Phase 2 Implementation Checklist**

- [ ] All 7 tasks completed
- [ ] All code tested (>85% coverage)
- [ ] All tests passing
- [ ] 0 warnings in Python and Dart
- [ ] All documentation updated
- [ ] Ready for student testing

**Completed By**: ___________  
**Date**: ___________  
**Sign-Off**: ___________

---

## 🎉 NEXT STEPS (After Phase 2)

1. **Deploy to staging environment**
2. **Invite 5-10 Cambodia students for beta testing**
3. **Collect performance data** (accuracy, time, engagement)
4. **Analyze results** and adjust difficulty levels
5. **Plan Phase 3** (analytics, mobile optimization, classroom mode)

---

**Status**: Phase 2 Implementation Checklist  
**Last Updated**: August 26, 2024  
**Ready to Start?** ✅ YES!
