# 🚀 PHASE 1: READY TO IMPLEMENT

**Status**: ✅ Complete Audit + Prompts Ready  
**Date**: August 26, 2024  
**Target**: 8-10 hours to MVP  

---

## 📋 WHAT YOU HAVE

### 1. **PHASE_1_AUDIT_AND_PLAN.md** (This folder)
Complete audit of Phase 0 state and Phase 1 requirements:
- Architecture decisions
- Data models
- File structure
- Timeline (8-10 hours)
- Success criteria

### 2. **PHASE_1_AI_IMPLEMENTATION_PROMPTS.md** (This folder)
7 ready-to-use AI prompts for Claude/ChatGPT/Codex:
- Prompt 1.1: Problem Models (30 min)
- Prompt 1.2: Spaced Repetition Service (1 hour)
- Prompt 1.3: Problem Repository (45 min)
- Prompt 1.4: Problem Curation - JSON (1-2 hours)
- Prompt 1.5: Backend API Routes (1 hour)
- Prompt 1.6: Flutter UI Page (1-2 hours)
- Prompt 1.7: Testing Suite (1 hour)

**Each prompt includes**: Context, code style, success criteria, file paths

---

## 🎯 QUICK START WORKFLOW

### Step 1: Read the Audit
```
1. Read: PHASE_1_AUDIT_AND_PLAN.md (10 min)
2. Understand: What Phase 0 built, what Phase 1 adds
3. Note: File locations, architecture decisions
```

### Step 2: Generate Backend Code (5 hours)
```
Prompt 1.1 → Problem Models
Prompt 1.2 → Spaced Repetition Service
Prompt 1.3 → Problem Repository
Prompt 1.4 → Problem JSON (curated 20-30 problems)
Prompt 1.5 → Backend API Routes (/problems, /student/)
```

### Step 3: Integrate Backend
```
1. Copy generated files to project
2. Update ai-service/api/main.py to mount new router
3. Run: pytest ai-service/tests/
4. Verify: All tests pass, no warnings
```

### Step 4: Generate Frontend Code (2-3 hours)
```
Prompt 1.6 → Flutter Problem Select Page + Providers
```

### Step 5: Integrate Frontend
```
1. Copy generated files to ai_tutor/lib/
2. Add navigation from main page to problem_select_page.dart
3. Run: flutter analyze
4. Run: flutter test
5. Verify: No warnings, tests pass
```

### Step 6: Test End-to-End (1 hour)
```
Prompt 1.7 → Write tests
1. Backend tests (pytest)
2. Frontend tests (flutter test)
3. Manual testing: Select problem → Solve → Track
```

---

## 💻 HOW TO USE THE PROMPTS

### FOR EACH PROMPT:

1. **Copy the ENTIRE prompt** from `PHASE_1_AI_IMPLEMENTATION_PROMPTS.md`
2. **Paste into Claude** (claude.ai) or **ChatGPT** or **Cursor**
3. **Let it generate code**
4. **Review the output** for:
   - ✅ All required methods present
   - ✅ Type hints everywhere
   - ✅ Docstrings on public methods
   - ✅ Proper error handling
5. **Copy generated code** to project file
6. **Test locally**:
   ```bash
   # Python
   python -m pytest ai-service/tests/test_new_feature.py -v
   
   # Dart
   flutter analyze
   flutter test ai_tutor/test/new_feature_test.dart
   ```
7. **Fix any issues** (ask AI to fix specific lines)
8. **Move to next prompt**

---

## 📁 FILE STRUCTURE (WHAT GETS CREATED)

```
ai-service/
├── api/
│   ├── models/
│   │   ├── problem_models.py                     ← Prompt 1.1
│   ├── services/
│   │   ├── spaced_repetition_service.py          ← Prompt 1.2
│   ├── repositories/
│   │   ├── problem_repository.py                 ← Prompt 1.3
│   ├── routes/
│   │   ├── problems.py                           ← Prompt 1.5
│   └── main.py                                   (UPDATE: mount router)
├── data/
│   └── problems.json                             ← Prompt 1.4
├── tests/
│   ├── test_problem_models.py                    ← Prompt 1.7
│   ├── test_spaced_repetition.py                 ← Prompt 1.7
│   └── test_problem_repository.py                ← Prompt 1.7

ai_tutor/
└── lib/features/visual_tutor/
    ├── domain/entities/
    │   ├── problem_entity.dart                   ← Prompt 1.6
    │   └── progress_entity.dart                  ← Prompt 1.6
    ├── presentation/
    │   ├── providers/
    │   │   └── problem_provider.dart             ← Prompt 1.6
    │   └── pages/
    │       └── problem_select_page.dart          ← Prompt 1.6
    └── test/
        └── problem_select_page_test.dart         ← Prompt 1.7
```

---

## 🔄 INTEGRATION CHECKLIST

### Backend
- [ ] Generate code from Prompts 1.1-1.5
- [ ] Copy to project files
- [ ] Update `ai-service/api/main.py`:
  ```python
  from api.routes.problems import router as problems_router
  app.include_router(problems_router)
  ```
- [ ] Run tests: `pytest ai-service/tests/ -v`
- [ ] Check no warnings: `python -m pytest --tb=short`
- [ ] Test manually with curl:
  ```bash
  curl http://localhost:8001/problems
  curl http://localhost:8001/problems?subject=mathematics&difficulty=1
  curl http://localhost:8001/student/student_001/progress
  ```

### Frontend
- [ ] Generate code from Prompt 1.6
- [ ] Copy to project files
- [ ] Update main page to navigate to ProblemSelectPage
- [ ] Run: `flutter analyze` (no warnings)
- [ ] Run: `flutter test` (all tests pass)
- [ ] Test manually:
  - Open app
  - See problem list
  - Filter by subject
  - Tap a problem
  - Should navigate to StepSequencingPage
  - On complete, should return to problem list

### End-to-End
- [ ] Backend running: `python -m uvicorn api.main:app --reload`
- [ ] Frontend running: `flutter run -d web`
- [ ] Full flow works:
  1. Open problem select page
  2. Select a math problem
  3. Solve it step-by-step (Phase 0)
  4. Mark as easy/medium/hard
  5. See progress updated
  6. See next review date
  7. Navigate back
  8. Problem should show as reviewed

---

## ⚡ QUICK TIME BREAKDOWN

| Task | Time | Status |
|------|------|--------|
| Read audit | 15 min | ⏳ |
| Prompt 1.1: Models | 30 min | ⏳ |
| Prompt 1.2: SpacedRep | 1 hour | ⏳ |
| Prompt 1.3: Repository | 45 min | ⏳ |
| Prompt 1.4: Problems JSON | 1.5 hours | ⏳ |
| Prompt 1.5: API Routes | 1 hour | ⏳ |
| Backend integration + test | 1 hour | ⏳ |
| Prompt 1.6: Flutter UI | 1.5 hours | ⏳ |
| Frontend integration + test | 1 hour | ⏳ |
| End-to-end testing | 1 hour | ⏳ |
| **TOTAL** | **~10 hours** | **⏳** |

---

## 🎓 LEARNING CHECKLIST

After Phase 1, you should understand:

- ✅ Pydantic v2 model design
- ✅ FastAPI route organization
- ✅ SM-2 spaced repetition algorithm
- ✅ JSON data loading in Python
- ✅ Riverpod state management in Flutter
- ✅ HTTP requests from Flutter to Python backend
- ✅ Entity mapping (JSON ↔ Dart objects)
- ✅ Testing patterns (pytest + flutter_test)
- ✅ End-to-end integration

---

## 🎯 SUCCESS CRITERIA

**By end of Phase 1, you should have**:

✅ **Backend**:
- [ ] `problem_models.py` with all Pydantic models
- [ ] `spaced_repetition_service.py` with SM-2 scheduling
- [ ] `problem_repository.py` with query methods
- [ ] `problems.json` with 20-30 curated problems
- [ ] `problems.py` routes with all 6 endpoints
- [ ] All pytest tests passing (>80% coverage)
- [ ] Zero compiler warnings
- [ ] API endpoints tested with curl/Postman

✅ **Frontend**:
- [ ] `problem_entity.dart` & `progress_entity.dart`
- [ ] `problem_provider.dart` with Riverpod state
- [ ] `problem_select_page.dart` with UI
- [ ] All flutter tests passing
- [ ] Zero compiler warnings
- [ ] Null safety enforced

✅ **Integration**:
- [ ] Backend and frontend communicate successfully
- [ ] Can select problem → solve → track → return
- [ ] Progress updates after solving
- [ ] Spaced repetition scheduling works
- [ ] End-to-end flow tested manually

✅ **Documentation**:
- [ ] All public methods have docstrings
- [ ] Code follows style guides (analysis_options.yaml)
- [ ] README for how to run Phase 1
- [ ] Test coverage report (>80%)

---

## 🚨 COMMON ISSUES & FIXES

### Backend Issues

**Issue**: `ModuleNotFoundError: No module named 'api'`
**Fix**: Make sure you're running from project root with correct PYTHONPATH
```bash
cd ai-service
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
python -m pytest tests/
```

**Issue**: `FileNotFoundError: problems.json`
**Fix**: Repository doesn't find JSON file
- Verify file exists: `ai-service/data/problems.json`
- Use absolute path or fix relative path in code

**Issue**: Pydantic validation errors
**Fix**: Check JSON field types match model definitions
- `grade_level` should be int, not string
- `difficulty` should be int 1-5
- `created_at` should be ISO datetime string

### Frontend Issues

**Issue**: `Provider not found` error
**Fix**: Ensure providers are defined before being used
- Check imports in problem_select_page.dart
- Verify file paths match project structure

**Issue**: `http.get()` fails to reach backend
**Fix**: Backend URL may be wrong
- Update `backendUrl` in problem_provider.dart
- Make sure backend is running on correct port (8001)
- For web, may need CORS headers in backend

**Issue**: `FlutterError: Binding has not been initialized`
**Fix**: Ensure test setup is correct
- Add `TestWidgetsFlutterBinding.ensureInitialized()`
- Use proper `testWidgets` wrapper

---

## 🔗 RELATED DOCUMENTS

Inside this folder, you have:
- **PHASE_0_COMPLETE_FINAL_SUMMARY.md** - What Phase 0 built
- **PHASE_1_AUDIT_AND_PLAN.md** - Detailed plan (this folder)
- **PHASE_1_AI_IMPLEMENTATION_PROMPTS.md** - 7 prompts to copy-paste (this folder)
- **VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md** - Overall vision

---

## 📞 QUICK REFERENCE

### Backend Architecture
- **Models**: `api/models/problem_models.py`
- **Services**: `api/services/{spaced_repetition,problem_bank}_service.py`
- **Repositories**: `api/repositories/problem_repository.py`
- **Routes**: `api/routes/problems.py`
- **Data**: `data/problems.json`

### Frontend Architecture
- **Entities**: `domain/entities/{problem,progress}_entity.dart`
- **Providers**: `presentation/providers/problem_provider.dart`
- **Pages**: `presentation/pages/problem_select_page.dart`
- **Tests**: `test/problem_select_page_test.dart`

### Key Files to Update
- `ai-service/api/main.py` - Add problem router
- `ai_tutor/lib/screens/main_page.dart` (or navigation) - Add ProblemSelectPage

---

## ✨ PHASE 1 VISION REALIZED

After Phase 1, your AI Visual Tutor will:

🎯 **For Students**:
- See a curated problem bank (20-30 problems)
- Filter by subject (Math, Physics, Chemistry), difficulty (1-5), topic
- Select a problem and solve step-by-step (AI teacher on whiteboard)
- Get immediate feedback and misconception detection
- See spaced repetition schedule ("Review in 3 days")
- Track progress (problems solved, time spent, confidence)

🧠 **For Teachers**:
- Understand which concepts students struggle with
- See misconception patterns
- Identify students who need intervention
- Track class-wide progress

🤖 **For AI**:
- Route problems to correct expert (math/physics/chemistry)
- Generate step-by-step Socratic guidance
- Render visualizations (graphs, shapes, vectors, molecules)
- Detect and address misconceptions
- Adapt next problem based on confidence
- Track learning trajectory

---

## 🎬 FINAL STEPS

1. **Read**: PHASE_1_AUDIT_AND_PLAN.md (understand the vision)
2. **Grab Prompt 1.1**: Copy from PHASE_1_AI_IMPLEMENTATION_PROMPTS.md
3. **Paste into Claude**: Let it generate
4. **Integrate**: Copy to project, test
5. **Repeat**: Prompts 1.2-1.7
6. **Verify**: All tests pass, no warnings
7. **Celebrate**: Phase 1 MVP complete! 🎉

---

## 💪 YOU'VE GOT THIS!

Phase 0 was massive (10k+ lines, 485+ tests). Phase 1 builds on that solid foundation and adds the missing piece: **real problem management and adaptive learning scheduling**.

With these prompts, you can implement Phase 1 in one long day or spread it over a few sessions. The structure is clear, the examples are provided, and the success criteria are defined.

**Start with Prompt 1.1 now!** ⚡

---

## 📊 PROGRESS TRACKER

Update this as you implement:

```
Prompt 1.1 (Models):              [ ] Generated [ ] Integrated [ ] Tests Pass
Prompt 1.2 (SpacedRep):           [ ] Generated [ ] Integrated [ ] Tests Pass
Prompt 1.3 (Repository):          [ ] Generated [ ] Integrated [ ] Tests Pass
Prompt 1.4 (Problems JSON):       [ ] Generated [ ] Integrated [ ] Tests Pass
Prompt 1.5 (API Routes):          [ ] Generated [ ] Integrated [ ] Tests Pass
Prompt 1.6 (Flutter):             [ ] Generated [ ] Integrated [ ] Tests Pass
Prompt 1.7 (Tests):               [ ] Generated [ ] Integrated [ ] Tests Pass

Backend Integration:              [ ] Complete [ ] All Tests Pass
Frontend Integration:             [ ] Complete [ ] All Tests Pass
End-to-End Testing:              [ ] Complete [ ] All Features Work
```

---

**Ready to implement Phase 1? Copy Prompt 1.1 and let's go! 🚀**
