# 🤖 PHASE 1 AI IMPLEMENTATION PROMPTS
**For Use With**: Claude, ChatGPT, or Codex  
**Purpose**: Iterative, AI-guided implementation of Phase 1  
**Status**: Ready to use sequentially  

---

## How to Use These Prompts

1. **Copy the entire prompt** for your target task
2. **Paste into Claude/ChatGPT/Codex**
3. **Include context**: Copy relevant files from the codebase (provided in prompts)
4. **Let AI generate code**
5. **Review output**, test it
6. **Move to next prompt** when ready

Each prompt includes:
- Task description
- Required context/files
- Success criteria
- Code style guidelines

---

## ✅ PROMPT 1.1: Problem Models

**Task**: Create Pydantic models for problem representation

**Copy-paste this entire prompt into Claude:**

```
# TASK: Create Problem Models for AI Visual Tutor Phase 1

## PROJECT CONTEXT
You are implementing Phase 1 of an AI Visual Tutor for Cambodia Grade 10-12 students.
- Phase 0 is complete (expert services, step sequencing, rich media rendering)
- Phase 1 adds: Problem Bank, Spaced Repetition, Progress Tracking

## OBJECTIVE
Create a new file: `ai-service/api/models/problem_models.py`

With complete Pydantic models for:
1. Problem (main problem definition)
2. ProblemSubject (enum: math, physics, chemistry)
3. ProblemDifficulty (enum: 1-5 scale)
4. ProblemTopic (enum: curriculum topics)
5. StudentProgress (tracks individual problem progress)
6. ProgressUpdate (request model for marking solved)

## REFERENCE STRUCTURE (DO NOT IMPLEMENT YET, JUST REFERENCE)

Here's the existing TeachingStep model from Phase 0:

```python
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class Subject(str, Enum):
    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"

class DifficultyLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"
```

## YOUR TASK: Implement Problem Models

Create `ai-service/api/models/problem_models.py` with:

### 1. ProblemSubject Enum
```
MATHEMATICS = "mathematics"
PHYSICS = "physics"
CHEMISTRY = "chemistry"
```

### 2. ProblemDifficulty Enum
```
EASY = 1
MEDIUM = 2
INTERMEDIATE = 3
ADVANCED = 4
EXPERT = 5
```

### 3. Problem BaseModel
Fields:
- id: str (unique identifier, e.g., "math_linear_001")
- subject: ProblemSubject
- grade_level: int (10, 11, or 12)
- topic: str (e.g., "linear_equations", "kinematics")
- subtopic: Optional[str] (e.g., "two_step_equations")
- difficulty: int (1-5)
- problem: str (the actual problem statement)
- answer: str (expected final answer)
- solution_method: str (primary approach, e.g., "inverse_operations")
- expected_steps: int (typical step count)
- misconceptions: List[str] (common errors students make)
- concepts: List[str] (learning concepts involved)
- tags: List[str] (metadata for filtering)
- created_at: datetime (ISO format)
- metadata: Dict[str, Any] (any extra data)

### 4. StudentProgress BaseModel
Tracks individual progress on each problem
Fields:
- student_id: str
- problem_id: str
- times_solved: int = 0
- times_failed: int = 0
- last_seen: Optional[datetime] = None
- confidence_level: str = "new" (options: "new", "easy", "medium", "hard")
- next_review: Optional[datetime] = None
- time_spent_seconds: int = 0
- misconceptions_detected: List[str] = []
- created_at: datetime
- updated_at: datetime

### 5. ProgressUpdate BaseModel (Request)
What student sends when completing a problem
Fields:
- confidence_level: str (e.g., "easy", "medium", "hard")
- time_spent_seconds: int
- misconceptions_detected: Optional[List[str]] = None
- student_response: Optional[str] = None (optional for analysis)

## CODE STYLE REQUIREMENTS
- Use Pydantic v2 syntax
- Add docstrings to every field (using Field(..., description="..."))
- Use type hints everywhere
- Import from __future__ import annotations at top
- Organize: enums first, then BaseModels
- Add class docstrings explaining purpose

## EXAMPLE OUTPUT FORMAT

Your output should have:
1. All imports (pydantic, enum, typing, datetime)
2. Enum classes with clear docstrings
3. BaseModel classes with Field definitions and descriptions
4. Config classes if needed (e.g., json_encoders)
5. Test-able - can be imported and instantiated

## SUCCESS CRITERIA
- ✅ No type errors
- ✅ All models instantiate correctly
- ✅ Enums work properly
- ✅ Fields have docstrings and descriptions
- ✅ datetime fields can be serialized to JSON
- ✅ Code follows analysis_options.yaml style

## FILE PATH
Create: `ai-service/api/models/problem_models.py`

Go ahead and implement the complete file now.
```

---

## ✅ PROMPT 1.2: Spaced Repetition Service

**Task**: Implement SM-2 scheduling and progress tracking

**Copy-paste this entire prompt into Claude:**

```
# TASK: Implement Spaced Repetition Service for Phase 1

## PROJECT CONTEXT
You're implementing Phase 1 of the AI Visual Tutor.
- Phase 0: Expert services, step sequencing (complete)
- Phase 1: Problem bank, spaced repetition, progress tracking
- Just completed: problem_models.py

## OBJECTIVE
Create: `ai-service/api/services/spaced_repetition_service.py`

A service that:
1. Manages student progress on problems
2. Schedules reviews using SM-2 algorithm (simplified for MVP)
3. Returns due problems for review
4. Updates progress when student solves a problem

## REFERENCE: Existing Service Pattern

Here's how services are structured in Phase 0 (MathExpertService pattern):

```python
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SomeService:
    def __init__(self):
        # Initialize any dependencies
        pass
    
    async def some_method(self, param: str) -> dict:
        """Docstring explaining what it does"""
        logger.info(f"Starting operation for {param}")
        # Implementation
        return {"result": "value"}
```

## YOUR TASK: Implement SpacedRepetitionService

### SM-2 Algorithm (Simplified for MVP)
```
Based on confidence_level after solving:
- confidence_level = "easy" (4-5): interval = 7 days, next_review = today + 7 days
- confidence_level = "medium" (3): interval = 3 days, next_review = today + 3 days  
- confidence_level = "hard" (1-2): interval = 1 day, next_review = today + 1 day
- confidence_level = "new": interval = 0, next_review = today (available immediately)
```

### Methods to Implement

1. **__init__()**
   - Initialize empty progress dictionary: self.student_progress = {}
   - Set up logger

2. **mark_solved(student_id: str, problem_id: str, progress_update: ProgressUpdate) -> dict**
   - Input: student_id, problem_id, confidence_level, time_spent_seconds, misconceptions
   - Logic:
     a. Get or create StudentProgress for this (student_id, problem_id)
     b. Increment times_solved
     c. Add time_spent_seconds to total
     d. Store misconceptions_detected
     e. Calculate next_review based on confidence_level
     f. Update last_seen = now, updated_at = now
     g. Save to self.student_progress
   - Return: Updated StudentProgress object with next_review date
   - Log: "Student {student_id} solved {problem_id}, next review: {next_review}"

3. **mark_failed(student_id: str, problem_id: str, time_spent_seconds: int) -> dict**
   - Similar to mark_solved but:
     a. Increment times_failed instead
     b. Set confidence_level to "hard"
     c. next_review = today + 1 day
     d. Return updated progress

4. **get_due_problems(student_id: str) -> List[str]**
   - Find all problems where:
     a. next_review <= today (time to review)
     b. OR confidence_level = "new" (never seen)
   - Return: List of problem IDs (sorted by priority: hard > medium > easy)

5. **get_student_progress(student_id: str) -> Dict[str, Any]**
   - Return stats for dashboard:
     a. total_solved: count of times_solved > 0
     b. total_failed: count of times_failed > 0
     c. problems_due: count of due problems
     d. total_time_spent: sum of time_spent_seconds
     e. average_confidence: mean of confidence levels
     f. recent_problems: last 5 problems studied
   - Return: dictionary with all stats

6. **get_problem_progress(student_id: str, problem_id: str) -> Optional[StudentProgress]**
   - Get progress for single problem
   - Return: StudentProgress or None if not attempted

7. **reset_progress(student_id: str = None) -> str**
   - If student_id: reset all problems for that student
   - If student_id is None: reset all progress (for testing)
   - Return: confirmation message

## IMPORTS NEEDED
```python
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from api.models.problem_models import (
    StudentProgress,
    ProgressUpdate,
    Problem,
)

logger = logging.getLogger(__name__)
```

## CODE STYLE REQUIREMENTS
- Use docstrings for every method
- Type hints on all parameters and returns
- Use logger.info/logger.error (not print)
- Store progress in self.student_progress (dict, keyed by f"{student_id}:{problem_id}")
- Handle edge cases (None, empty lists, etc.)
- Use datetime.now() for current time (not datetime.utcnow())

## TESTING THE SERVICE
Your code should work like this:

```python
service = SpacedRepetitionService()

# Student solves a problem
progress = await service.mark_solved(
    student_id="student_001",
    problem_id="math_linear_001",
    progress_update=ProgressUpdate(
        confidence_level="medium",
        time_spent_seconds=180,
        misconceptions_detected=["sign_error"]
    )
)
# Returns: StudentProgress with next_review = today + 3 days

# Get problems due for review
due = await service.get_due_problems("student_001")
# Returns: List[str] of problem IDs

# Get student stats
stats = await service.get_student_progress("student_001")
# Returns: {"total_solved": 1, "problems_due": 0, ...}
```

## SUCCESS CRITERIA
- ✅ All methods implemented
- ✅ SM-2 scheduling works correctly
- ✅ Progress tracks times_solved, times_failed, time_spent
- ✅ Can mark problems as easy/medium/hard
- ✅ get_due_problems returns correct subset
- ✅ No type errors
- ✅ Docstrings on all methods
- ✅ Logging in place

## FILE PATH
Create: `ai-service/api/services/spaced_repetition_service.py`

Implement now!
```

---

## ✅ PROMPT 1.3: Problem Repository

**Task**: Load and query problems from JSON file

**Copy-paste this entire prompt into Claude:**

```
# TASK: Implement Problem Repository for Phase 1

## PROJECT CONTEXT
- Phase 0 complete (expert services)
- Phase 1: Building problem bank
- Completed: problem_models.py, spaced_repetition_service.py
- Next: Load problems from JSON, query them

## OBJECTIVE
Create: `ai-service/api/repositories/problem_repository.py`

A repository that:
1. Loads problems from JSON file
2. Provides query methods (by subject, difficulty, topic, etc.)
3. Returns Problem objects with full metadata
4. Is testable (can mock JSON loading)

## REFERENCE: Repository Pattern

In Python, repositories handle data access:

```python
class ProblemRepository:
    def __init__(self, data_path: str = "ai-service/data/problems.json"):
        self.data_path = data_path
        self.problems = []
        self._load_problems()
    
    def _load_problems(self):
        # Load from JSON file
        # Parse into Problem objects
        # Store in self.problems
        pass
    
    def get_by_id(self, problem_id: str) -> Optional[Problem]:
        # Find problem by ID
        return next((p for p in self.problems if p.id == problem_id), None)
```

## YOUR TASK: Implement ProblemRepository

### Methods to Implement

1. **__init__(data_path: str = "ai-service/data/problems.json")**
   - Initialize: self.data_path, self.problems = []
   - Call _load_problems()
   - Log: "Loaded {count} problems from {path}"

2. **_load_problems() -> None** (private)
   - Read JSON file from self.data_path
   - Parse each item as a Problem object
   - Handle errors: JSON invalid, missing file, etc.
   - Log errors with logger.error()
   - Store all Problem objects in self.problems
   - Note: File doesn't exist yet (created in Task 1.4), so handle gracefully

3. **get_all() -> List[Problem]**
   - Return all problems
   - Return: List[Problem]

4. **get_by_id(problem_id: str) -> Optional[Problem]**
   - Find problem by exact ID match
   - Return: Problem or None

5. **get_by_subject(subject: str) -> List[Problem]**
   - Filter by subject (case-insensitive)
   - Subject values: "mathematics", "physics", "chemistry"
   - Return: List[Problem] (sorted by difficulty)

6. **get_by_difficulty(difficulty: int) -> List[Problem]**
   - Filter by difficulty (1-5)
   - Return: List[Problem]

7. **get_by_topic(topic: str) -> List[Problem]**
   - Filter by topic (case-insensitive substring match)
   - Return: List[Problem]

8. **get_by_grade_level(grade_level: int) -> List[Problem]**
   - Filter by grade (10, 11, or 12)
   - Return: List[Problem]

9. **get_random(count: int = 1, subject: Optional[str] = None) -> List[Problem]**
   - Return random problems
   - If subject specified, filter first
   - Shuffle and return top {count}
   - Return: List[Problem]

10. **search(subject: Optional[str] = None, difficulty: Optional[int] = None, topic: Optional[str] = None, grade_level: Optional[int] = None) -> List[Problem]**
    - Apply multiple filters
    - All filters are optional (if None, don't filter on that dimension)
    - Return: List[Problem] matching ALL filters

## IMPORTS NEEDED
```python
import json
import logging
from pathlib import Path
from typing import Optional, List
from api.models.problem_models import Problem, ProblemSubject

logger = logging.getLogger(__name__)
```

## FILE STRUCTURE
The JSON file (created in Task 1.4) will look like:
```json
[
  {
    "id": "math_linear_001",
    "subject": "mathematics",
    "grade_level": 10,
    "topic": "linear_equations",
    "subtopic": "two_step_equations",
    "difficulty": 1,
    "problem": "Solve 2x + 5 = 13 for x",
    "answer": "4",
    "solution_method": "inverse_operations",
    "expected_steps": 4,
    "misconceptions": ["sign_error", "forgot_division"],
    "concepts": ["inverse_operations", "equality"],
    "tags": ["cambodia_grade_10"],
    "created_at": "2024-08-26T10:00:00",
    "metadata": {}
  }
]
```

## CODE STYLE REQUIREMENTS
- Type hints on all methods
- Docstrings on all public methods
- Use logger.info/logger.error (not print)
- Handle JSON parse errors gracefully
- Problem objects should be Pydantic validated

## TESTING THE REPOSITORY
```python
repo = ProblemRepository("ai-service/data/problems.json")

# Get all problems
all_problems = repo.get_all()  # List[Problem]

# Get by ID
problem = repo.get_by_id("math_linear_001")  # Problem or None

# Filter by subject
math_problems = repo.get_by_subject("mathematics")  # List[Problem]

# Complex search
grade10_easy_math = repo.search(
    subject="mathematics",
    grade_level=10,
    difficulty=1
)  # List[Problem]
```

## SUCCESS CRITERIA
- ✅ All methods implemented
- ✅ JSON file loading works (or handles missing file gracefully)
- ✅ All queries return correct results
- ✅ No type errors
- ✅ Docstrings present
- ✅ Case-insensitive filtering
- ✅ Can handle empty problem list

## FILE PATH
Create: `ai-service/api/repositories/problem_repository.py`

Go ahead and implement!
```

---

## ✅ PROMPT 1.4: Problem Curation (JSON Data)

**Task**: Curate 20-30 problems across Math, Physics, Chemistry

**Copy-paste this entire prompt into Claude:**

```
# TASK: Curate 20-30 Problems for Phase 1 MVP

## PROJECT CONTEXT
- Phase 1: Building problem bank for Cambodia Grade 10-12
- Completed: Models, SpacedRepetitionService, ProblemRepository
- Next: Fill the problem bank with real problems

## OBJECTIVE
Create: `ai-service/data/problems.json`

A curated JSON file with 20-30 problems:
- Curriculum-aligned to Cambodia standards
- Solvable by existing expert services (Phase 0)
- Mix of difficulties (1-5 scale)
- Across Math (10-12), Physics (6-8), Chemistry (4-6)

## CURRICULUM ALIGNMENT RULES

### MATHEMATICS (10-12 problems)
**Grade 10 (Difficulty 1-2)**
- Linear equations (2-3 problems)
  - Example: "Solve 2x + 5 = 13"
  - Example: "Solve 3x - 7 = 2"
  - Concepts: Inverse operations, balancing equations
  
- Basic algebra (2 problems)
  - Expanding: (x + 2)(x + 3)
  - Factoring: x² + 5x + 6
  
- Geometry basics (2 problems)
  - Area of triangle given base and height
  - Angle sum in triangle

**Grade 11 (Difficulty 2-3)**
- Quadratic equations (2-3 problems)
  - Example: "Solve x² - 5x + 6 = 0"
  - Example: "Find roots of 2x² + 3x - 2 = 0"
  - Concepts: Factoring, quadratic formula
  
- Functions (2 problems)
  - Evaluate function at point
  - Find domain/range

**Grade 12 (Difficulty 3-5)**
- Complex problems combining multiple concepts
- Trigonometry applications
- Polynomial equations

### PHYSICS (6-8 problems)
**Grade 10-11 (Difficulty 1-3)**
- Kinematics (2-3 problems)
  - "An object accelerates at 5 m/s². Starting from rest, what is velocity after 3 seconds?"
  - "Using v = u + at, find final velocity"
  - Concepts: Velocity, acceleration, displacement
  
- Dynamics (2 problems)
  - "A force of 10 N acts on a 2 kg mass. Find acceleration (F=ma)"
  - Friction problems

- Simple motion (2 problems)
  - Speed, distance, time relationships

**Grade 12 (Difficulty 3-4)**
- Energy problems (KE, PE, conservation)
- Waves (frequency, wavelength)
- Electricity basics

### CHEMISTRY (4-6 problems)
**Grade 10 (Difficulty 1-2)**
- Bonding (2-3 problems)
  - "Draw Lewis structure of H₂O"
  - "Determine valence electrons of Carbon"
  - "Is NaCl ionic or covalent?"
  - Concepts: Lewis dots, electronegativity, bonding types

- Simple molecules (1-2 problems)
  - Molecular weight calculation
  - Electron configuration

**Grade 11-12 (Difficulty 2-4)**
- Reactions (2 problems)
  - Balance chemical equations
  - Stoichiometry
  
- Advanced (1-2 problems)
  - Thermodynamics
  - Kinetics

## JSON STRUCTURE TEMPLATE

```json
[
  {
    "id": "math_linear_001",
    "subject": "mathematics",
    "grade_level": 10,
    "topic": "linear_equations",
    "subtopic": "two_step_equations",
    "difficulty": 1,
    "problem": "Solve 2x + 5 = 13 for x",
    "answer": "4",
    "solution_method": "inverse_operations",
    "expected_steps": 4,
    "misconceptions": ["sign_error", "forgot_division", "forgot_to_divide_both_sides"],
    "concepts": ["inverse_operations", "equality", "variables", "arithmetic"],
    "tags": ["cambodia_grade_10", "algebra", "linear"],
    "created_at": "2024-08-26T10:00:00",
    "metadata": {
      "source": "cambodia_curriculum",
      "difficulty_calibrated": false,
      "tested_with_expert": true
    }
  }
]
```

## YOUR TASK: Create Problems JSON

Create a JSON file with these problems:

### REQUIRED: Math Problems (10-12 total)

1. **Linear Equations** (Grade 10, Difficulty 1)
   - ID: math_linear_001
   - Problem: "Solve 2x + 5 = 13 for x"
   - Answer: "4"
   - Misconceptions: ["sign_error", "forgot_division"]

2. **Linear Equations** (Grade 10, Difficulty 1)
   - ID: math_linear_002
   - Problem: "Solve x - 7 = 3 for x"
   - Answer: "10"
   - Misconceptions: ["sign_error"]

3. **Linear Equations** (Grade 10, Difficulty 2)
   - ID: math_linear_003
   - Problem: "Solve 3(x + 2) = 15 for x"
   - Answer: "3"
   - Misconceptions: ["distribution_error", "sign_error"]

4. **Quadratic Equations** (Grade 11, Difficulty 2)
   - ID: math_quadratic_001
   - Problem: "Solve x² - 5x + 6 = 0"
   - Answer: "x = 2 or x = 3"
   - Misconceptions: ["factoring_error", "sign_error"]

5. **Quadratic Equations** (Grade 11, Difficulty 3)
   - ID: math_quadratic_002
   - Problem: "Solve 2x² + 3x - 2 = 0"
   - Answer: "x = -2 or x = 0.5"
   - Misconceptions: ["quadratic_formula_error", "sign_error"]

6. **Factoring** (Grade 10, Difficulty 2)
   - ID: math_factoring_001
   - Problem: "Factor x² + 5x + 6"
   - Answer: "(x + 2)(x + 3)"
   - Misconceptions: ["ac_method_error", "sign_error"]

7. **Expanding** (Grade 10, Difficulty 1)
   - ID: math_expanding_001
   - Problem: "Expand (x + 2)(x + 3)"
   - Answer: "x² + 5x + 6"
   - Misconceptions: ["distribution_error", "forgot_middle_term"]

8. **Geometry** (Grade 10, Difficulty 1)
   - ID: math_geometry_001
   - Problem: "Find the area of a triangle with base 10 cm and height 5 cm"
   - Answer: "25 cm²"
   - Misconceptions: ["forgot_division_by_2", "unit_error"]

9. **Functions** (Grade 11, Difficulty 2)
   - ID: math_functions_001
   - Problem: "If f(x) = 2x + 1, find f(3)"
   - Answer: "7"
   - Misconceptions: ["substitution_error", "arithmetic_error"]

10. **Trigonometry** (Grade 12, Difficulty 3)
    - ID: math_trigonometry_001
    - Problem: "Find sin(30°)"
    - Answer: "0.5"
    - Misconceptions: ["degree_radian_confusion", "memorization_error"]

### REQUIRED: Physics Problems (6-8 total)

11. **Kinematics** (Grade 10, Difficulty 2)
    - ID: physics_kinematics_001
    - Problem: "An object accelerates at 5 m/s². Starting from rest, what is velocity after 3 seconds? (Use v = u + at)"
    - Answer: "15 m/s"
    - Misconceptions: ["forgot_starting_velocity", "arithmetic_error"]

12. **Kinematics** (Grade 11, Difficulty 2)
    - ID: physics_kinematics_002
    - Problem: "A car travels 100 m in 5 seconds at constant acceleration. If starting from rest, find acceleration. (Use s = ut + ½at²)"
    - Answer: "8 m/s²"
    - Misconceptions: ["forgot_half", "arithmetic_error"]

13. **Dynamics** (Grade 11, Difficulty 2)
    - ID: physics_dynamics_001
    - Problem: "A force of 10 N acts on a mass of 2 kg. Find the acceleration. (Use F = ma)"
    - Answer: "5 m/s²"
    - Misconceptions: ["inverse_calculation", "unit_error"]

14. **Energy** (Grade 11, Difficulty 3)
    - ID: physics_energy_001
    - Problem: "What is the kinetic energy of a 2 kg object moving at 5 m/s? (Use KE = ½mv²)"
    - Answer: "25 J"
    - Misconceptions: ["forgot_half", "forgot_square"]

15. **Waves** (Grade 12, Difficulty 3)
    - ID: physics_waves_001
    - Problem: "A wave has frequency 10 Hz and wavelength 2 m. Find wave speed. (Use v = f × λ)"
    - Answer: "20 m/s"
    - Misconceptions: ["confused_formula", "unit_error"]

16. **Circular Motion** (Grade 12, Difficulty 4)
    - ID: physics_circular_motion_001
    - Problem: "A car moves in a circle of radius 50 m at speed 20 m/s. Find centripetal acceleration. (Use a = v²/r)"
    - Answer: "8 m/s²"
    - Misconceptions: ["forgot_square", "confused_formula"]

### REQUIRED: Chemistry Problems (4-6 total)

17. **Bonding - Lewis Structure** (Grade 10, Difficulty 2)
    - ID: chemistry_bonding_001
    - Problem: "How many valence electrons does Carbon have?"
    - Answer: "4"
    - Misconceptions: ["atomic_number_confusion", "period_confusion"]

18. **Bonding - Ionic vs Covalent** (Grade 10, Difficulty 1)
    - ID: chemistry_bonding_002
    - Problem: "Is NaCl ionic or covalent?"
    - Answer: "Ionic"
    - Misconceptions: ["confused_definition", "electronegativity_error"]

19. **Reactions - Balancing** (Grade 11, Difficulty 2)
    - ID: chemistry_reactions_001
    - Problem: "Balance: H₂ + O₂ → H₂O"
    - Answer: "2H₂ + O₂ → 2H₂O"
    - Misconceptions: ["changed_subscripts", "wrong_coefficients"]

20. **Stoichiometry** (Grade 11, Difficulty 3)
    - ID: chemistry_stoichiometry_001
    - Problem: "In the reaction 2H₂ + O₂ → 2H₂O, if you have 4 moles of H₂, how many moles of O₂ are needed?"
    - Answer: "2 moles"
    - Misconceptions: ["ratio_error", "forgot_stoichiometry"]

---

**OPTIONAL (Extra problems for variety)**

21. **Equations** (Grade 10, Difficulty 2)
    - ID: math_systems_001
    - Problem: "Solve: x + y = 5 and x - y = 1"
    - Answer: "x = 3, y = 2"

22. **Electricity** (Grade 12, Difficulty 3)
    - ID: physics_electricity_001
    - Problem: "What is the current if voltage is 10V and resistance is 2Ω? (Use I = V/R)"
    - Answer: "5 A"

23. **Molecular Weight** (Grade 10, Difficulty 1)
    - ID: chemistry_molecular_weight_001
    - Problem: "Find molecular weight of CO₂ (C=12, O=16)"
    - Answer: "44 g/mol"

---

## REQUIREMENTS
✅ All problems must be:
1. Solvable by existing expert services
2. Curriculum-aligned to Cambodia Grade 10-12
3. Properly formatted JSON
4. Include all required fields
5. Have realistic misconceptions
6. Sorted by subject then difficulty

✅ Must create directory if missing:
- `ai-service/data/` (create if not exists)

✅ File must be valid JSON:
- Test with `python -m json.tool ai-service/data/problems.json`

## SUCCESS CRITERIA
- [ ] 20-30 problems total
- [ ] 10-12 math problems
- [ ] 6-8 physics problems
- [ ] 4-6 chemistry problems
- [ ] All difficulties represented (1-5)
- [ ] All grades represented (10, 11, 12)
- [ ] Valid JSON format
- [ ] No missing required fields
- [ ] Realistic misconceptions per problem

## FILE PATH
Create: `ai-service/data/problems.json`

Go ahead and create the JSON file now!
```

---

## ✅ PROMPT 1.5: Backend API Routes

**Task**: Create REST API endpoints for problem selection and progress

**Copy-paste this entire prompt into Claude:**

```
# TASK: Implement Problem API Routes for Phase 1

## PROJECT CONTEXT
- Phase 1: Building problem bank
- Completed: Models, SpacedRepetitionService, ProblemRepository, problems.json
- Next: Create FastAPI routes to expose problems and progress

## OBJECTIVE
Create: `ai-service/api/routes/problems.py`

A FastAPI router that provides:
- GET /problems (list all, with filters)
- GET /problems/{id} (get single)
- POST /problems/{id}/solve (mark solved, update progress)
- GET /student/{student_id}/progress (dashboard stats)
- GET /student/{student_id}/due-problems (what to review)

## REFERENCE: FastAPI Route Pattern (Phase 0)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/some-path", tags=["some-tag"])
logger = logging.getLogger(__name__)

@router.get("/endpoint")
async def get_something(param: str) -> dict:
    """Docstring explaining the endpoint"""
    try:
        # Implementation
        return {"result": "value"}
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
```

## YOUR TASK: Implement Problem Routes

### Imports Needed
```python
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
import logging
from api.models.problem_models import (
    Problem,
    ProgressUpdate,
    StudentProgress,
)
from api.repositories.problem_repository import ProblemRepository
from api.services.spaced_repetition_service import SpacedRepetitionService

router = APIRouter(prefix="/problems", tags=["problems"])
logger = logging.getLogger(__name__)

# Initialize services (in production, use dependency injection)
problem_repo = ProblemRepository()
spaced_rep_service = SpacedRepetitionService()
```

### Routes to Implement

#### 1. GET /problems
**Purpose**: List all problems with optional filters
**Query Parameters**:
- subject: Optional[str] = None (filter by "mathematics", "physics", "chemistry")
- difficulty: Optional[int] = None (filter by 1-5)
- topic: Optional[str] = None (filter by topic)
- grade_level: Optional[int] = None (filter by 10, 11, 12)
- limit: int = 50 (max results)

**Response**:
```python
{
    "total": 5,
    "problems": [
        {
            "id": "math_linear_001",
            "subject": "mathematics",
            "grade_level": 10,
            "topic": "linear_equations",
            "difficulty": 1,
            "problem": "Solve 2x + 5 = 13",
            ...
        }
    ]
}
```

**Implementation**:
- Call problem_repo.search() with filters
- Return list with metadata
- If no results, return empty list (not error)
- Log: "Listed {count} problems"

---

#### 2. GET /problems/{problem_id}
**Purpose**: Get single problem by ID
**Response**: Single Problem object

**Implementation**:
- Call problem_repo.get_by_id(problem_id)
- If None: raise HTTPException(404, "Problem not found")
- Return Problem object
- Log: "Retrieved problem {problem_id}"

---

#### 3. POST /problems/{problem_id}/solve
**Purpose**: Mark a problem as solved, update progress, return next review date
**Request Body**:
```python
{
    "student_id": "student_001",
    "confidence_level": "medium",  # "easy", "medium", "hard"
    "time_spent_seconds": 180,
    "misconceptions_detected": ["sign_error"],
    "student_response": "4"  # optional
}
```

**Response**:
```python
{
    "status": "success",
    "message": "Problem marked as solved",
    "progress": {
        "student_id": "student_001",
        "problem_id": "math_linear_001",
        "times_solved": 1,
        "times_failed": 0,
        "next_review": "2024-08-29T10:00:00Z",
        "confidence_level": "medium"
    },
    "next_review_date": "2024-08-29"
}
```

**Implementation**:
- Get problem by ID (404 if not found)
- Call spaced_rep_service.mark_solved(student_id, problem_id, progress_update)
- Return updated progress + next_review_date
- Log: "Student {student_id} solved {problem_id}"

---

#### 4. GET /student/{student_id}/progress
**Purpose**: Get progress dashboard for student
**Response**:
```python
{
    "student_id": "student_001",
    "total_solved": 5,
    "total_failed": 2,
    "problems_due": 1,
    "total_time_spent_seconds": 1200,
    "average_confidence": "medium",
    "recent_problems": [
        {
            "problem_id": "math_linear_001",
            "subject": "mathematics",
            "confidence_level": "medium",
            "last_seen": "2024-08-26T10:30:00Z",
            "next_review": "2024-08-29T10:30:00Z"
        }
    ],
    "problems_by_subject": {
        "mathematics": 3,
        "physics": 1,
        "chemistry": 1
    }
}
```

**Implementation**:
- Call spaced_rep_service.get_student_progress(student_id)
- Return stats
- If no progress found, return empty/zero stats
- Log: "Retrieved progress for {student_id}"

---

#### 5. GET /student/{student_id}/due-problems
**Purpose**: Get problems due for review (spaced repetition schedule)
**Query Parameters**:
- limit: int = 10

**Response**:
```python
{
    "student_id": "student_001",
    "due_count": 2,
    "problems": [
        {
            "id": "math_linear_001",
            "subject": "mathematics",
            "topic": "linear_equations",
            "difficulty": 1,
            "problem": "Solve 2x + 5 = 13",
            "confidence_level": "medium",
            "last_seen": "2024-08-26T10:30:00Z",
            "next_review": "2024-08-29T10:30:00Z"
        }
    ]
}
```

**Implementation**:
- Call spaced_rep_service.get_due_problems(student_id)
- Get problem objects from problem_repo
- Combine problem data + progress data
- Return sorted by priority (hard > medium > easy)
- Log: "Retrieved {count} due problems for {student_id}"

---

#### 6. POST /problems/{problem_id}/fail
**Purpose**: Mark a problem as failed (student couldn't solve it)
**Request Body**:
```python
{
    "student_id": "student_001",
    "time_spent_seconds": 120
}
```

**Response**: Updated progress (same as /solve)

**Implementation**:
- Call spaced_rep_service.mark_failed(student_id, problem_id, time_spent_seconds)
- Return updated progress
- Log: "Student {student_id} failed {problem_id}"

---

## ERROR HANDLING
- Problem not found → 404
- Invalid student_id → 400 (or accept any string)
- Invalid difficulty → 400
- Missing required fields → 422
- Server error → 500

## LOGGING EXAMPLES
```python
logger.info(f"Listed {len(problems)} problems with filters")
logger.error(f"Failed to mark problem solved: {str(e)}")
```

## MOUNTING THE ROUTER

In `ai-service/api/main.py`, add:

```python
from api.routes.problems import router as problems_router

app.include_router(problems_router)
```

## SUCCESS CRITERIA
- ✅ All 6 routes implemented
- ✅ Query parameters work correctly
- ✅ Request body validation
- ✅ Error handling with HTTPException
- ✅ Logging on all routes
- ✅ Type hints on all parameters/returns
- ✅ Docstrings on all routes
- ✅ Integrates with ProblemRepository and SpacedRepetitionService
- ✅ Can be tested with curl or Postman

## FILE PATH
Create: `ai-service/api/routes/problems.py`

Implement now!
```

---

## ✅ PROMPT 1.6: Flutter Problem Selection UI

**Task**: Create problem selection page with filters and integration

**Copy-paste this entire prompt into Claude:**

```
# TASK: Implement Problem Selection Page (Flutter) for Phase 1

## PROJECT CONTEXT
- Phase 1: Building problem bank MVP
- Backend complete: Models, API routes, problem data
- Next: Flutter UI to select and solve problems

## OBJECTIVE
Create: `ai_tutor/lib/features/visual_tutor/presentation/pages/problem_select_page.dart`

A Flutter page that:
1. Shows curated problem list with filters
2. Displays problem difficulty/metadata
3. Allows filtering by subject, difficulty, topic
4. Navigates to StepSequencingPage when selected
5. Shows progress dashboard (problems solved, due for review)
6. Displays spaced repetition scheduling

## REFERENCE: Existing Flutter Patterns (Phase 0)

From teaching_step_provider.dart:
```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

// State definition
class TeachingStepState {
  final TeachingPlanEntity? plan;
  final String? currentStepId;
  
  TeachingStepState({this.plan, this.currentStepId});
  
  TeachingStepState copyWith({
    TeachingPlanEntity? plan,
    String? currentStepId,
  }) {
    return TeachingStepState(
      plan: plan ?? this.plan,
      currentStepId: currentStepId ?? this.currentStepId,
    );
  }
}

// Provider
final teachingStepProvider = 
    StateNotifierProvider<TeachingStepNotifier, TeachingStepState>(
  (ref) => TeachingStepNotifier(),
);
```

From step_sequencing_page.dart:
```dart
class StepSequencingPage extends ConsumerWidget {
  final String problem;
  final String subject;
  
  const StepSequencingPage({
    required this.problem,
    required this.subject,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(teachingStepProvider);
    // Render based on state
  }
}
```

## YOUR TASK: Implement ProblemSelectPage

### 1. Create Domain Entity
**File**: `ai_tutor/lib/features/visual_tutor/domain/entities/problem_entity.dart`

```dart
class ProblemEntity {
  final String id;
  final String subject;  // 'mathematics', 'physics', 'chemistry'
  final int gradeLevel;  // 10, 11, 12
  final String topic;    // 'linear_equations', etc.
  final int difficulty;  // 1-5
  final String problem;
  final String answer;
  final List<String> concepts;
  final DateTime createdAt;

  ProblemEntity({
    required this.id,
    required this.subject,
    required this.gradeLevel,
    required this.topic,
    required this.difficulty,
    required this.problem,
    required this.answer,
    required this.concepts,
    required this.createdAt,
  });

  // fromJson for API response
  factory ProblemEntity.fromJson(Map<String, dynamic> json) {
    return ProblemEntity(
      id: json['id'] as String,
      subject: json['subject'] as String,
      gradeLevel: json['grade_level'] as int,
      topic: json['topic'] as String,
      difficulty: json['difficulty'] as int,
      problem: json['problem'] as String,
      answer: json['answer'] as String,
      concepts: List<String>.from(json['concepts'] as List),
      createdAt: DateTime.parse(json['created_at'] as String),
    );
  }
}
```

### 2. Create Progress Entity
**File**: `ai_tutor/lib/features/visual_tutor/domain/entities/progress_entity.dart`

```dart
class StudentProgressEntity {
  final String studentId;
  final int totalSolved;
  final int totalFailed;
  final int problemsDue;
  final int totalTimeSpentSeconds;
  final String averageConfidence;
  final List<RecentProblemEntity> recentProblems;

  StudentProgressEntity({
    required this.studentId,
    required this.totalSolved,
    required this.totalFailed,
    required this.problemsDue,
    required this.totalTimeSpentSeconds,
    required this.averageConfidence,
    required this.recentProblems,
  });

  factory StudentProgressEntity.fromJson(Map<String, dynamic> json) {
    return StudentProgressEntity(
      studentId: json['student_id'] as String,
      totalSolved: json['total_solved'] as int,
      totalFailed: json['total_failed'] as int,
      problemsDue: json['problems_due'] as int,
      totalTimeSpentSeconds: json['total_time_spent_seconds'] as int,
      averageConfidence: json['average_confidence'] as String,
      recentProblems: (json['recent_problems'] as List?)
          ?.map((e) => RecentProblemEntity.fromJson(e))
          .toList() ?? [],
    );
  }
}

class RecentProblemEntity {
  final String problemId;
  final String subject;
  final String confidenceLevel;
  final DateTime lastSeen;
  final DateTime? nextReview;

  RecentProblemEntity({
    required this.problemId,
    required this.subject,
    required this.confidenceLevel,
    required this.lastSeen,
    required this.nextReview,
  });

  factory RecentProblemEntity.fromJson(Map<String, dynamic> json) {
    return RecentProblemEntity(
      problemId: json['problem_id'] as String,
      subject: json['subject'] as String,
      confidenceLevel: json['confidence_level'] as String,
      lastSeen: DateTime.parse(json['last_seen'] as String),
      nextReview: json['next_review'] != null 
          ? DateTime.parse(json['next_review'] as String)
          : null,
    );
  }
}
```

### 3. Create Provider
**File**: `ai_tutor/lib/features/visual_tutor/presentation/providers/problem_provider.dart`

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

// State
class ProblemSelectState {
  final List<ProblemEntity> problems;
  final StudentProgressEntity? progress;
  final bool isLoading;
  final String? error;
  final String? selectedSubject;  // filter
  final int? selectedDifficulty;  // filter
  final String? selectedTopic;    // filter

  ProblemSelectState({
    required this.problems,
    this.progress,
    this.isLoading = false,
    this.error,
    this.selectedSubject,
    this.selectedDifficulty,
    this.selectedTopic,
  });

  ProblemSelectState copyWith({
    List<ProblemEntity>? problems,
    StudentProgressEntity? progress,
    bool? isLoading,
    String? error,
    String? selectedSubject,
    int? selectedDifficulty,
    String? selectedTopic,
  }) {
    return ProblemSelectState(
      problems: problems ?? this.problems,
      progress: progress ?? this.progress,
      isLoading: isLoading ?? this.isLoading,
      error: error,
      selectedSubject: selectedSubject ?? this.selectedSubject,
      selectedDifficulty: selectedDifficulty ?? this.selectedDifficulty,
      selectedTopic: selectedTopic ?? this.selectedTopic,
    );
  }
}

// Notifier
class ProblemSelectNotifier extends StateNotifier<ProblemSelectState> {
  final String backendUrl = 'http://localhost:8001';  // Change to your backend URL
  final String studentId = 'student_001';  // Mock student ID for MVP

  ProblemSelectNotifier()
      : super(ProblemSelectState(problems: [], isLoading: true)) {
    _init();
  }

  Future<void> _init() async {
    await loadProblems();
    await loadProgress();
  }

  Future<void> loadProblems() async {
    state = state.copyWith(isLoading: true);
    try {
      final uri = Uri.parse('$backendUrl/problems')
          .replace(queryParameters: {
        if (state.selectedSubject != null) 'subject': state.selectedSubject,
        if (state.selectedDifficulty != null)
          'difficulty': state.selectedDifficulty.toString(),
        if (state.selectedTopic != null) 'topic': state.selectedTopic,
      });

      final response = await http.get(uri);
      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final problems = (data['problems'] as List)
            .map((p) => ProblemEntity.fromJson(p))
            .toList();
        state = state.copyWith(problems: problems, isLoading: false);
      } else {
        state = state.copyWith(
          error: 'Failed to load problems',
          isLoading: false,
        );
      }
    } catch (e) {
      state = state.copyWith(error: e.toString(), isLoading: false);
    }
  }

  Future<void> loadProgress() async {
    try {
      final response = await http
          .get(Uri.parse('$backendUrl/student/$studentId/progress'));
      if (response.statusCode == 200) {
        final progress = StudentProgressEntity.fromJson(jsonDecode(response.body));
        state = state.copyWith(progress: progress);
      }
    } catch (e) {
      // Log but don't error
    }
  }

  void setSubjectFilter(String? subject) {
    state = state.copyWith(selectedSubject: subject);
    loadProblems();
  }

  void setDifficultyFilter(int? difficulty) {
    state = state.copyWith(selectedDifficulty: difficulty);
    loadProblems();
  }

  void setTopicFilter(String? topic) {
    state = state.copyWith(selectedTopic: topic);
    loadProblems();
  }
}

// Provider
final problemSelectProvider =
    StateNotifierProvider<ProblemSelectNotifier, ProblemSelectState>(
  (ref) => ProblemSelectNotifier(),
);
```

### 4. Create Page Widget
**File**: `ai_tutor/lib/features/visual_tutor/presentation/pages/problem_select_page.dart`

Create a Material Design page with:

**Sections**:
1. **Progress Dashboard** (top)
   - Show: "X problems solved", "Y due for review"
   - Show: "Total time: Z minutes"
   - Show: Average confidence level

2. **Filter Buttons** (below dashboard)
   - Subject filters: All, Math, Physics, Chemistry
   - Difficulty slider: 1-5
   - Optional: Topic dropdown

3. **Problem List** (main content)
   - Problem cards with:
     - Title (problem text, truncated)
     - Subject badge (color-coded)
     - Difficulty stars (1-5)
     - "Start Problem" button
   - Pull to refresh
   - Loading state
   - Empty state

4. **Bottom Navigation** (if applicable)
   - Back button or exit

**UI Framework**:
- Use Material Design 3
- Color scheme: Subject badges (blue=math, green=physics, purple=chemistry)
- Responsive layout

**Navigation**:
- On "Start Problem" tap:
  ```dart
  Navigator.push(
    context,
    MaterialPageRoute(
      builder: (context) => StepSequencingPage(
        problem: problem.problem,
        subject: problem.subject,
      ),
    ),
  );
  ```
- On back from StepSequencingPage: reload progress

## IMPORTS NEEDED
```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:ai_tutor/features/visual_tutor/domain/entities/problem_entity.dart';
import 'package:ai_tutor/features/visual_tutor/presentation/providers/problem_provider.dart';
import 'package:ai_tutor/features/visual_tutor/presentation/pages/step_sequencing_page.dart';
```

## SUCCESS CRITERIA
- ✅ Page loads problems from API
- ✅ Filters work (subject, difficulty)
- ✅ Problem cards display correctly
- ✅ Navigation to StepSequencingPage works
- ✅ Progress dashboard shows stats
- ✅ Loading/error states handled
- ✅ No compiler warnings
- ✅ Null safety enforced
- ✅ Responsive on mobile/web

## FILE PATHS
Create:
- `ai_tutor/lib/features/visual_tutor/domain/entities/problem_entity.dart`
- `ai_tutor/lib/features/visual_tutor/domain/entities/progress_entity.dart`
- `ai_tutor/lib/features/visual_tutor/presentation/providers/problem_provider.dart`
- `ai_tutor/lib/features/visual_tutor/presentation/pages/problem_select_page.dart`

Go ahead and implement all 4 files!
```

---

## ✅ PROMPT 1.7: Integration & Testing

**Task**: Write tests and verify end-to-end flow

**Copy-paste this entire prompt into Claude:**

```
# TASK: Write Tests for Phase 1 (Backend + Frontend)

## PROJECT CONTEXT
- Phase 1: Problem bank + spaced repetition
- All major components built
- Next: Tests to verify everything works together

## OBJECTIVE
Create test files:
1. `ai-service/tests/test_problem_models.py` - Pydantic model validation
2. `ai-service/tests/test_spaced_repetition.py` - Service logic
3. `ai-service/tests/test_problem_repository.py` - Data access
4. `ai_tutor/test/problem_select_page_test.dart` - Flutter UI

## BACKEND TESTS: PYTHON

### File 1: test_problem_models.py

Test Pydantic models can be created and serialized:

```python
import pytest
from datetime import datetime
from api.models.problem_models import (
    Problem,
    StudentProgress,
    ProgressUpdate,
    ProblemSubject,
)

class TestProblemModel:
    def test_problem_creation(self):
        """Test Problem model creation"""
        problem = Problem(
            id="math_linear_001",
            subject=ProblemSubject.MATHEMATICS,
            grade_level=10,
            topic="linear_equations",
            subtopic="two_step",
            difficulty=1,
            problem="Solve 2x + 5 = 13",
            answer="4",
            solution_method="inverse_operations",
            expected_steps=4,
            misconceptions=["sign_error"],
            concepts=["equality"],
            tags=["cambodia"],
            created_at=datetime.now(),
        )
        assert problem.id == "math_linear_001"
        assert problem.difficulty == 1

    def test_problem_json_serialization(self):
        """Test Problem can be converted to JSON"""
        problem = Problem(...)
        json_data = problem.model_dump()
        assert json_data["id"] == "math_linear_001"

    def test_student_progress_creation(self):
        """Test StudentProgress model"""
        progress = StudentProgress(
            student_id="student_001",
            problem_id="math_linear_001",
            times_solved=1,
            confidence_level="medium",
        )
        assert progress.times_solved == 1

    def test_progress_update_validation(self):
        """Test ProgressUpdate validation"""
        update = ProgressUpdate(
            confidence_level="medium",
            time_spent_seconds=180,
        )
        assert update.confidence_level == "medium"
```

### File 2: test_spaced_repetition.py

Test SM-2 scheduling logic:

```python
import pytest
from datetime import datetime, timedelta
from api.services.spaced_repetition_service import SpacedRepetitionService
from api.models.problem_models import ProgressUpdate

@pytest.mark.asyncio
class TestSpacedRepetitionService:
    def setup_method(self):
        """Setup before each test"""
        self.service = SpacedRepetitionService()

    @pytest.mark.asyncio
    async def test_mark_solved_easy(self):
        """Test marking problem as easy (7-day review)"""
        progress = await self.service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=120,
            ),
        )
        # Should schedule review 7 days from now
        expected_review = datetime.now() + timedelta(days=7)
        assert progress.next_review is not None
        assert (progress.next_review - expected_review).days == 0

    @pytest.mark.asyncio
    async def test_get_due_problems(self):
        """Test retrieving due problems"""
        # Mark a problem as solved (hard = 1-day review)
        await self.service.mark_solved(
            "student_001", "math_001",
            ProgressUpdate(confidence_level="hard", time_spent_seconds=100),
        )
        # Next day, should be due
        # (Mock datetime.now() for testing)
        
        due = await self.service.get_due_problems("student_001")
        # Should include the problem

    @pytest.mark.asyncio
    async def test_student_progress_stats(self):
        """Test progress summary statistics"""
        await self.service.mark_solved(
            "student_001", "math_001",
            ProgressUpdate(confidence_level="medium", time_spent_seconds=180),
        )
        
        stats = await self.service.get_student_progress("student_001")
        assert stats["total_solved"] == 1
        assert stats["total_time_spent"] == 180
```

### File 3: test_problem_repository.py

Test problem loading and querying:

```python
import pytest
from api.repositories.problem_repository import ProblemRepository

class TestProblemRepository:
    def setup_method(self):
        """Setup before each test"""
        self.repo = ProblemRepository("ai-service/data/problems.json")

    def test_load_problems(self):
        """Test problems are loaded from JSON"""
        problems = self.repo.get_all()
        assert len(problems) > 0

    def test_get_by_id(self):
        """Test retrieving problem by ID"""
        problem = self.repo.get_by_id("math_linear_001")
        assert problem is not None
        assert problem.id == "math_linear_001"

    def test_get_by_subject(self):
        """Test filtering by subject"""
        math_problems = self.repo.get_by_subject("mathematics")
        assert all(p.subject == "mathematics" for p in math_problems)

    def test_get_by_difficulty(self):
        """Test filtering by difficulty"""
        easy = self.repo.get_by_difficulty(1)
        assert all(p.difficulty == 1 for p in easy)

    def test_search_multiple_filters(self):
        """Test search with multiple filters"""
        results = self.repo.search(
            subject="mathematics",
            difficulty=1,
            grade_level=10,
        )
        assert all(
            p.subject == "mathematics" and p.difficulty == 1 
            for p in results
        )
```

## FRONTEND TESTS: DART

### File 4: problem_select_page_test.dart

Test Flutter page with mock API:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mockito/mockito.dart';
import 'package:http/http.dart' as http;

void main() {
  group('ProblemSelectPage', () {
    testWidgets('Displays problem list when loaded', 
        (WidgetTester tester) async {
      // Mock HTTP responses
      // Build widget tree
      // Verify UI rendered
    });

    testWidgets('Filters problems by subject', 
        (WidgetTester tester) async {
      // Verify filter buttons work
    });

    testWidgets('Navigates to StepSequencingPage on problem tap', 
        (WidgetTester tester) async {
      // Tap problem card
      // Verify navigation
    });

    testWidgets('Shows loading state while fetching', 
        (WidgetTester tester) async {
      // Verify loading indicator
    });

    testWidgets('Shows error state on API failure', 
        (WidgetTester tester) async {
      // Mock API error
      // Verify error message displayed
    });
  });
}
```

## HOW TO RUN TESTS

### Backend (Python)
```bash
# Install pytest
pip install pytest pytest-asyncio

# Run all tests
pytest ai-service/tests/

# Run specific test
pytest ai-service/tests/test_problem_models.py

# Run with coverage
pytest --cov=api ai-service/tests/
```

### Frontend (Dart/Flutter)
```bash
# Run all tests
flutter test ai_tutor/test/

# Run specific test
flutter test ai_tutor/test/problem_select_page_test.dart

# Generate coverage
flutter test --coverage ai_tutor/test/
```

## SUCCESS CRITERIA
- ✅ All backend tests pass
- ✅ All frontend tests pass
- ✅ >80% code coverage
- ✅ No compiler warnings
- ✅ Tests run in <30 seconds
- ✅ All imports resolved
- ✅ Mocks/fixtures work correctly

## FILE PATHS
Create:
- `ai-service/tests/test_problem_models.py`
- `ai-service/tests/test_spaced_repetition.py`
- `ai-service/tests/test_problem_repository.py`
- `ai_tutor/test/problem_select_page_test.dart`

Implement now!
```

---

## 📋 PROMPT USAGE GUIDE

| Prompt | Task | Duration | Prereq |
|--------|------|----------|--------|
| 1.1 | Problem Models | 30 min | None |
| 1.2 | Spaced Rep Service | 1 hour | 1.1 |
| 1.3 | Problem Repository | 45 min | 1.1 |
| 1.4 | Problem Curation | 1-2 hours | 1.1-1.3 |
| 1.5 | API Routes | 1 hour | 1.1-1.3 |
| 1.6 | Flutter Page | 1-2 hours | 1.1, backend complete |
| 1.7 | Testing | 1 hour | All above |

---

## 🎯 NEXT STEPS

1. **Copy Prompt 1.1** → Paste into Claude
2. **Generate code** → Copy output to project
3. **Test locally** → Verify no errors
4. **Move to Prompt 1.2** → Continue
5. **Repeat** for all 7 prompts
6. **Integration test** → End-to-end flow
7. **Document learnings** → Update this file with progress

---

## 💡 TIPS FOR BEST RESULTS

### With Claude/ChatGPT
- **Copy full context**: Include reference code
- **Be specific**: Ask for specific file paths
- **Iterate**: If output is wrong, ask "fix line X"
- **Review**: Check generated code before integrating

### With Codex/GitHub Copilot
- Start comment blocks with task description
- Use proper type hints in docstrings
- Ask Copilot to complete specific functions
- Verify generated code against spec

### Integration Workflow
1. Generate one prompt
2. Copy code to file
3. Fix any issues locally
4. Commit/test
5. Next prompt
6. Keep doc updated with progress

---

## 📊 TRACKING PROGRESS

Copy this table and update as you go:

| Task | Status | File | Tests Pass | Notes |
|------|--------|------|-----------|-------|
| 1.1 | ⏳ | problem_models.py | ⏳ | |
| 1.2 | ⏳ | spaced_repetition_service.py | ⏳ | |
| 1.3 | ⏳ | problem_repository.py | ⏳ | |
| 1.4 | ⏳ | problems.json | N/A | |
| 1.5 | ⏳ | problems.py (routes) | ⏳ | |
| 1.6 | ⏳ | problem_select_page.dart | ⏳ | |
| 1.7 | ⏳ | test_*.py, *_test.dart | ⏳ | |

---

## 🎓 LEARNING OUTCOMES

After Phase 1, you will have:
- ✅ Understanding of Pydantic models
- ✅ Experience with FastAPI routing
- ✅ Knowledge of SM-2 spaced repetition
- ✅ Flutter Riverpod state management
- ✅ End-to-end API integration
- ✅ Testing patterns (Python + Dart)
- ✅ Production-ready problem bank

---

## 🚀 READY?

Start with **Prompt 1.1** → Copy → Paste → Generate → Integrate → Next!

Questions? Check PHASE_1_AUDIT_AND_PLAN.md for context.
