# AI Implementation Prompts for Visual Tutor

**Guide for using Claude/Codex to implement the complete system**

These prompts are designed to be executed sequentially. Each prompt builds on the previous work and includes context so the AI understands what's been done.

---

## 📋 How to Use These Prompts

### Before You Start
1. Have Claude analyze all the audit documents:
   - VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md
   - VISUAL_TUTOR_TECHNICAL_SPEC.md
   - VISUAL_TUTOR_START_TODAY.md

2. Share your current project structure:
   - Directory layout
   - Current models
   - Current API routes
   - Current Flutter structure

3. Agree on coding standards:
   - Python version & style
   - Dart version & style
   - Database conventions
   - File naming conventions

### Execution Pattern
```
1. CONTEXT PROMPT (below) - First, always
   ↓ (Claude understands the whole vision)
2. PHASE 0 PROMPTS (Foundation)
   ↓ (Creates core infrastructure)
3. PHASE 1 PROMPTS (Math Expert)
   ↓ (Implements first subject)
4. PHASE 2 PROMPTS (Physics Expert)
   ↓ (Implements second subject)
5. PHASE 3 PROMPTS (Chemistry Expert)
   ↓ (Implements third subject)
6. PHASE 4 PROMPTS (Integration & Polish)
   ↓ (Brings everything together)
7. VALIDATION PROMPTS (Testing)
   ↓ (Ensures quality)
```

### Key Points
- **Always reference**: "As documented in VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md..."
- **Include constraints**: "Following the architecture in VISUAL_TUTOR_TECHNICAL_SPEC.md..."
- **Specify style**: "Using the code examples from VISUAL_TUTOR_QUICK_START.md..."
- **Track progress**: "Continuing from PHASE X, we've completed Y, now implementing Z"

---

## 🚀 INITIAL CONTEXT PROMPT

**Use this FIRST with Claude. Copy and paste exactly.**

```
I'm building an AI Visual Tutor system for Cambodia Grade 10-12 students 
in Math, Physics, and Chemistry. This is NOT a chatbot - it's a real AI teacher 
with an interactive whiteboard.

## Project Vision
- Multi-subject teaching (Math, Physics, Chemistry)
- Interactive, step-by-step guidance (NOT ChatGPT-like)
- Rich visualizations (graphs, diagrams, animations)
- Cambodia curriculum aligned
- Khmer language support
- Socratic teaching method (questions first, discovery-based)

## Detailed Documentation
I have comprehensive audit and planning documents:
1. VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md - Full vision & teaching patterns
2. VISUAL_TUTOR_TECHNICAL_SPEC.md - Architecture & data models
3. VISUAL_TUTOR_START_TODAY.md - Week 1 implementation tasks
4. VISUAL_TUTOR_QUICK_START.md - Code examples & patterns

## Current Project Structure
- Backend: FastAPI (Python 3.11+)
- Frontend: Flutter (Dart 3.x)
- Database: MongoDB
- AI Model: Claude/GPT-4
- Existing systems: Session management, curriculum KG, adaptive tutor planner

## Your First Task
1. Read and understand VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md
2. Read and understand VISUAL_TUTOR_TECHNICAL_SPEC.md
3. Review VISUAL_TUTOR_START_TODAY.md for implementation priorities
4. Confirm you understand the three teaching patterns (Math, Physics, Chemistry)
5. Confirm you understand this is NOT like ChatGPT - it's an interactive teacher

Then respond with:
- Your understanding of the vision
- Key architectural decisions you identified
- Questions about any aspect before we proceed with Phase 0

This is a 200-hour project across 10 weeks. Let's build it right.
```

---

## 🏗️ PHASE 0: FOUNDATION (Weeks 1-2)

### PROMPT 0.1: Rich Media Rendering Engine

```
CONTEXT: We're implementing Phase 0 (Foundation) of the AI Visual Tutor system.
I've shared the complete vision in VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md.

## Task: Create Rich Media Rendering Engine (Frontend)

We need a Flutter widget system that can render:
1. Mathematical equations (with animations)
2. Graphs (2D plots with Plotly)
3. Geometric shapes (triangles, circles, free body diagrams)
4. Physics vectors (forces, velocity, acceleration)
5. Chemistry molecules (2D structures, atoms, bonds)
6. Coordinate systems (with labels and scales)

## Requirements

### Deliverables
Create the following Dart files:

1. `ai_tutor/lib/features/visual_tutor/presentation/services/graph_renderer.dart`
   - Use Plotly.dart or custom Canvas
   - Plot functions, data points, graphs
   - Support annotations, highlighting
   - Example functions to test: f(x) = x^2, f(x) = sin(x)

2. `ai_tutor/lib/features/visual_tutor/presentation/services/geometric_renderer.dart`
   - Draw basic shapes: triangle, circle, rectangle, polygon
   - Support styling (colors, line width, fills)
   - Support labels and annotations
   - Support angle marking

3. `ai_tutor/lib/features/visual_tutor/presentation/services/vector_renderer.dart`
   - Draw vectors (arrows) with magnitudes
   - Vector addition visualization
   - Label support
   - Physics-specific (forces, acceleration, etc.)

4. `ai_tutor/lib/features/visual_tutor/presentation/services/molecule_renderer.dart`
   - Simple 2D molecular structure rendering
   - Atoms and bonds
   - Support common elements (H, C, N, O, etc.)
   - Basic electron visualization

5. `ai_tutor/lib/features/visual_tutor/presentation/widgets/rich_media_canvas.dart`
   - Main widget that coordinates all renderers
   - Animation controller integration
   - Responsive sizing
   - Gesture support

### Code Style
- Follow analysis_options.yaml
- Null safety (!)
- Proper error handling
- Clear documentation comments
- Type hints on everything

### Architecture
- Services are stateless (renderer functions)
- Widgets use CustomPaint or Plotly where appropriate
- Separation: Model → Service → Widget
- Reusable components

### Testing
- Create corresponding test files
- Basic unit tests for each renderer
- Visual tests (screenshots) would be nice but optional

## Constraints
- No external packages except what's already in pubspec.yaml (add Plotly.dart if needed)
- Must work on mobile (Android/iOS) and web
- Performance: Render in <100ms for typical visualizations
- Support animation (via AnimationController)

## Success Criteria
- All 5 files created with full implementations
- Can render sample: graph, triangle, vector, molecule
- Code is clean, documented, follows Dart best practices
- Tests pass

Please implement this completely. If you need specific graph examples or 
geometric shapes, I'll provide them. Assume all services are used by 
RichMediaCanvas widget.
```

### PROMPT 0.2: Curriculum Database & Models

```
CONTEXT: Continuing Phase 0 Foundation. We've created the rich media rendering engine.
Now we need the data structures for curriculum and problems.

## Task: Create Curriculum Database Models & Structure

Following VISUAL_TUTOR_TECHNICAL_SPEC.md Section 1, create the data models 
that represent Cambodia MOE curriculum for Math, Physics, Chemistry (Grades 10-12).

## Deliverables

### 1. Backend Models (ai-service/api/models/curriculum_cambodia.py)
Create Pydantic models for:

1. `Concept` - A single concept (e.g., "linear_equation", "force", "bonding")
   - Fields: concept_id, name, name_khmer, description, category, difficulty_level

2. `LearningOutcome` - MOE learning outcome
   - Fields: code, description, description_khmer, grade, subject

3. `Topic` - A topic in the curriculum (e.g., "Linear Equations")
   - Fields: topic_id, subject, grade, unit_name, name_khmer
   - Lists: concepts (covered), prerequisites (topic_ids), learning_outcomes
   - Example problems: List[str]

4. `CurriculumUnit` - A unit containing multiple topics
   - Fields: unit_id, subject, grade, name, name_khmer, weeks
   - Contains: List[Topic]

5. `CurriculumGraph` - Prerequisite dependency graph
   - Fields: subject, grade
   - Contains: topics (Dict), edges (prerequisite relationships)
   - Methods: get_prerequisites(), get_dependents(), get_path()

6. `RichProblem` - A problem that needs rich visualization (from TECHNICAL_SPEC)
   - Fields as documented in VISUAL_TUTOR_TECHNICAL_SPEC.md
   - Must support: problem_type, visualizations_needed, concepts, prerequisites

7. `VisualizationPlan` - Teaching plan with visualizations
   - Fields as documented in VISUAL_TUTOR_TECHNICAL_SPEC.md
   - Must support: visualization_steps, animations, student_questions

### 2. Curriculum Data File (ai-service/data/cambodia_curriculum.json)
Create JSON structure with:

- Grade 10 Math (5 units)
  - Linear Equations (3 topics)
  - Quadratic Functions (3 topics)
  - Polynomials (2 topics)
  - Exponential & Logarithm (2 topics)
  - Trigonometry (2 topics)

- Grade 10 Physics (5 units)
  - Kinematics (3 topics)
  - Dynamics (3 topics)
  - Energy & Work (2 topics)
  - Momentum (2 topics)
  - Circular Motion (2 topics)

- Grade 10 Chemistry (5 units)
  - Atomic Structure (3 topics)
  - Bonding (3 topics)
  - Chemical Reactions (2 topics)
  - Acids & Bases (2 topics)
  - Molarity (2 topics)

Each topic must include:
- Concepts covered
- Prerequisites (as topic_ids)
- Learning outcomes
- 3-5 problem examples (with problem_ids)

### 3. MongoDB Collection Setup (ai-service/api/services/curriculum_service.py)
Create service class for:

```python
class CurriculumService:
    async def load_curriculum(subject: str, grade: str) -> CurriculumGraph
    async def get_topic(topic_id: str) -> Topic
    async def get_prerequisites(topic_id: str) -> List[Topic]
    async def get_next_topics(topic_id: str) -> List[Topic]
    async def get_learning_outcomes(topic_id: str) -> List[LearningOutcome]
    async def find_related_problems(topic_id: str) -> List[RichProblem]
```

### 4. Seed Data Script (ai-service/scripts/seed_curriculum.py)
Create script that:
- Loads cambodia_curriculum.json
- Validates all prerequisites exist
- Validates all topics referenced are valid
- Inserts into MongoDB
- Reports: "Loaded X topics, Y problems, Z learning outcomes"

## Code Style
- Follow Python 3.11+ best practices
- Type hints on everything
- Pydantic v2
- Clear docstrings

## Constraints
- All text fields must support Khmer (UTF-8)
- IDs must be consistent (e.g., "math_g10_linear_eq_01")
- Prerequisites must form a valid DAG (no cycles)
- All learning outcomes must map to real MOE standards

## Success Criteria
- All Pydantic models defined and validated
- cambodia_curriculum.json complete with 15 units, 40+ topics
- CurriculumService fully functional
- Seed script runs without errors
- Can query: prerequisites, dependents, topics by grade

Use realistic Cambodia MOE curriculum. If you need help structuring topics,
I can provide a reference document.
```

### PROMPT 0.3: Subject Expert Base Framework

```
CONTEXT: Phase 0, we have rich media rendering and curriculum. 
Now creating the expert system framework that all subjects will inherit from.

## Task: Create Subject Expert Base Classes

Following VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md "Technical Stack Requirements",
create the expert system framework.

## Deliverables

### 1. Base Expert Class (ai-service/api/services/subject_experts/base_expert.py)

```python
from abc import ABC, abstractmethod
from api.models.curriculum_cambodia import RichProblem, Topic
from api.models.visualization_plan import VisualizationPlan, VisualizationStep
from api.models.visual_tutor_step import TeachingStep, StudentStepEvaluation

class SubjectExpert(ABC):
    """Base class for all subject experts (Math, Physics, Chemistry)"""
    
    subject: str  # "math", "physics", "chemistry"
    
    @abstractmethod
    async def analyze_problem(self, problem: RichProblem) -> dict:
        """Understand problem structure and identify key elements"""
        # Returns: {
        #   "problem_type": str,
        #   "key_elements": List[str],
        #   "relevant_concepts": List[str],
        #   "solution_approach": str
        # }
        pass
    
    @abstractmethod
    async def create_visualization_plan(
        self, 
        problem: RichProblem,
        teaching_approach: str = "socratic"
    ) -> VisualizationPlan:
        """Create step-by-step teaching plan with visualizations"""
        pass
    
    @abstractmethod
    async def evaluate_student_response(
        self,
        student_answer: str,
        step_id: str,
        expected_answer: Optional[str] = None,
        validation_strategy: Optional[str] = None,
    ) -> StudentStepEvaluation:
        """Evaluate student response and detect misconceptions"""
        pass
    
    @abstractmethod
    async def provide_hint(
        self, 
        step_id: str, 
        hint_level: int = 1
    ) -> str:
        """Provide escalating hints"""
        pass
    
    @abstractmethod
    async def detect_misconception(
        self,
        student_work: str,
        correct_answer: str,
        step_id: str
    ) -> Optional[dict]:
        """Identify conceptual errors"""
        # Returns: {
        #   "misconception_type": str,
        #   "description": str,
        #   "remediation": str
        # }
        pass
    
    @abstractmethod
    async def generate_reteach_step(
        self,
        original_step_id: str,
        misconception: Optional[str] = None
    ) -> TeachingStep:
        """Generate alternative explanation if student struggles"""
        pass
```

### 2. Math Expert (ai-service/api/services/subject_experts/math_expert.py)

Implement MathExpert(SubjectExpert) with:
- Problem type detection (linear, quadratic, polynomial, etc.)
- Visualization plan generation for math-specific patterns
- Expression parsing and validation
- Common misconception detection (e.g., distribution errors)
- Support for: algebra, geometry, trigonometry, basic calculus

### 3. Physics Expert (ai-service/api/services/subject_experts/physics_expert.py)

Implement PhysicsExpert(SubjectExpert) with:
- Scenario analysis (force, motion, energy, waves)
- Free body diagram generation
- Graph generation (v-t, a-t, x-t, F vs a)
- Vector operations
- Support for: mechanics, thermodynamics, waves, electricity

### 4. Chemistry Expert (ai-service/api/services/subject_experts/chemistry_expert.py)

Implement ChemistryExpert(SubjectExpert) with:
- Molecular structure analysis
- Bonding type identification
- Reaction mechanism generation
- Energy diagram creation
- Support for: general, organic bonding, reactions, solutions

### 5. Expert Factory (ai-service/api/services/subject_experts/__init__.py)

```python
async def get_expert(subject: str) -> SubjectExpert:
    """Factory to get correct expert for subject"""
    if subject == "math":
        return MathExpert()
    elif subject == "physics":
        return PhysicsExpert()
    elif subject == "chemistry":
        return ChemistryExpert()
    else:
        raise ValueError(f"Unknown subject: {subject}")
```

## Implementation Notes

### Each Expert Must Include
1. Error handling (invalid problems, unparseable input)
2. Logging (for debugging)
3. Caching of common visualizations (for speed)
4. Type hints throughout
5. Clear docstrings

### Subject-Specific Methods
- Math: equation_parser(), apply_operation(), simplify_expression()
- Physics: identify_forces(), create_free_body_diagram(), create_motion_graphs()
- Chemistry: parse_compound(), identify_bonding(), show_electron_configuration()

### Constraints
- All experts must follow Socratic teaching method (questions first)
- Visualizations must be rendered using RichMediaCanvas
- All text must support Khmer translations
- Performance: each method completes in <2 seconds

## Success Criteria
- Base class fully abstract
- All 3 experts implement all methods
- Expert factory works
- Each expert has subject-specific methods
- Full type hints and documentation
- Tests for base functionality

Create stub implementations for now (experts can return placeholder data).
We'll fill in real logic in Phases 1, 2, 3.
```

---

## 📊 PHASE 1: MATH EXPERT (Weeks 3-4)

### PROMPT 1.1: Math Problem Analysis & Visualization

```
CONTEXT: Phase 0 complete. Now implementing Phase 1 - Math Expert.
Reference: VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md "Math Teaching Pattern"

## Task: Implement MathExpert Problem Analysis & Visualization

We need the math expert to:
1. Parse math problems
2. Identify problem type (linear, quadratic, etc.)
3. Create step-by-step visualization plans
4. Generate appropriate graphs and equations

## Deliverables

### 1. Math Problem Parser (math_expert.py additions)

Implement methods:

```python
async def analyze_problem(self, problem: RichProblem) -> dict:
    """
    Parse a math problem and identify:
    - Problem type: "linear_equation", "quadratic", "factor", "inequality", "system"
    - Key elements: coefficients, variables, operations
    - Solution approach: "isolation", "factoring", "completing_square", etc.
    """
    # Example: "Solve 2x + 5 = 13" → 
    # {
    #   "problem_type": "linear_equation",
    #   "variables": ["x"],
    #   "coefficients": {"2": (variable: "x"), "5": (constant)},
    #   "operations": ["addition", "multiplication"],
    #   "solution_approach": "isolation",
    #   "steps_required": 3
    # }
```

### 2. Math Visualization Plans (math_expert.py additions)

Implement method:

```python
async def create_visualization_plan(
    self, 
    problem: RichProblem,
    teaching_approach: str = "socratic"
) -> VisualizationPlan:
    """
    Create step-by-step teaching plan with visualizations.
    
    For example, "Solve 2x + 5 = 13" should return:
    - Step 1: Show equation with labels (constant, coefficient, variable)
    - Step 2: Ask: "What do you notice?"
    - Step 3: Show operation to isolate variable
    - Step 4: Ask: "What's next?"
    - Step 5: Show final answer with verification
    """
    
    # Implementation should:
    # 1. Detect problem type
    # 2. Plan visualization sequence
    # 3. Generate student questions
    # 4. Define expected responses
    # 5. Create branching logic (correct/incorrect/hint)
```

### 3. Graph Generation for Math

Implement method:

```python
async def generate_graphs(
    self,
    problem: RichProblem,
    problem_type: str
) -> List[dict]:
    """
    Generate appropriate graphs for problem type.
    
    Linear: y = mx + b graphs, number lines, solution visualization
    Quadratic: parabola, roots, vertex, axis of symmetry
    Inequality: number line with highlighted solution set
    System: two lines intersecting at solution point
    """
```

### 4. Test Cases (tests/test_math_expert.py)

Create tests for:
- Linear equations: solve_2x_plus_5_equals_13()
- Quadratic equations: factor_x2_minus_5x_plus_6()
- Inequalities: solve_2x_plus_3_greater_than_7()
- Systems: solve_system_2x2()
- Polynomials: factor_trinomial()

Each test should verify:
1. Problem is parsed correctly
2. Visualization plan has correct number of steps
3. Student questions are non-trivial (not just "what's the answer?")
4. Visualizations are appropriate for problem type

## Constraints
- Each visualization step must include a student question
- Student question must require thinking (not just computation)
- No step should give away the answer directly
- Support Khmer language for questions/text

## Success Criteria
- analyze_problem() works for 5+ problem types
- create_visualization_plan() generates appropriate steps
- Test cases pass for all 5 problem types
- Graphs render correctly
- Code is documented and type-hinted

Focus on one problem type first (linear equations), then expand to others.
```

### PROMPT 1.2: Math Student Evaluation

```
CONTEXT: Math expert visualization working. Now implement student evaluation.

## Task: Implement Math Response Evaluation

When a student answers a math problem step, we need to:
1. Check if answer is correct
2. Identify common mistakes
3. Provide appropriate feedback
4. Decide: next_step, reteach, hint, or explain_differently

## Deliverables

### 1. Response Evaluator (math_expert.py additions)

```python
async def evaluate_student_response(
    self,
    student_answer: str,
    step_id: str,
    expected_answer: Optional[str] = None,
    validation_strategy: Optional[str] = None,
) -> StudentStepEvaluation:
    """
    Evaluate math response.
    
    Validation strategies:
    - "exact_match": 7 == "7"
    - "numeric": 7.0 == 7 == 7.00
    - "symbolic": 2x == 2*x == 2 * x
    - "semantic": equivalent expressions (2x + 0 == 2x)
    - "fuzzy": close numeric values (7.01 ≈ 7.00)
    """
    
    # Returns StudentStepEvaluation with:
    # - is_correct: bool
    # - confidence: float (0-1)
    # - feedback: str (user-facing)
    # - misconception: Optional[str] (for reteaching)
    # - recommended_action: "next_step" | "reteach" | "hint" | "explain_differently"
```

### 2. Misconception Detection (math_expert.py additions)

```python
async def detect_misconception(
    self,
    student_work: str,
    correct_answer: str,
    step_id: str
) -> Optional[dict]:
    """
    Identify common math misconceptions.
    
    Examples:
    - "Distribution error": Student wrote 2(x+3) = 2x+3 instead of 2x+6
    - "Sign error": Student forgot negative when subtracting
    - "Order of operations": Student did addition before multiplication
    - "Inverse operation error": Student added instead of subtracting
    """
    
    # Returns:
    # {
    #   "misconception_type": "distribution_error",
    #   "description": "Forgot to distribute the 2",
    #   "remediation": "Let's expand 2(x+3) step by step..."
    # }
```

### 3. Hint Generation (math_expert.py additions)

```python
async def provide_hint(
    self, 
    step_id: str, 
    hint_level: int = 1
) -> str:
    """
    Provide escalating hints.
    
    Level 1: Conceptual hint ("What operation undoes addition?")
    Level 2: Directional hint ("Try subtracting 5 from both sides")
    Level 3: Nearly the answer ("After subtracting 5 from both sides, you get 2x = 8")
    """
```

### 4. Reteaching Logic (math_expert.py additions)

```python
async def generate_reteach_step(
    self,
    original_step_id: str,
    misconception: Optional[str] = None
) -> TeachingStep:
    """
    Generate alternative explanation if student struggles.
    
    If misconception detected, explain the concept differently:
    - Use different example
    - Use different visualization (e.g., number line instead of symbolic)
    - Slow down and add intermediate steps
    """
```

## Test Cases (tests/test_math_evaluation.py)

Create tests for:
- Correct answer detection
- Common misconception detection (distribution, sign errors, order of operations)
- Hint generation (multiple levels)
- Reteach step generation
- Different validation strategies

Example test:
```python
async def test_distribution_error_detection():
    expert = MathExpert()
    
    # Student made distribution error
    misconception = await expert.detect_misconception(
        student_work="2(x+3) = 2x+3",
        correct_answer="2(x+3) = 2x+6",
        step_id="step_1"
    )
    
    assert misconception["misconception_type"] == "distribution_error"
    
    # Should provide reteach
    reteach = await expert.generate_reteach_step("step_1", misconception["type"])
    assert "distribute" in reteach.explanation_text.lower()
```

## Constraints
- Validation must be robust (handle spacing, different number formats)
- Misconception detection must be accurate (don't over-diagnose)
- Hints must actually help (not just repeat the step)
- All feedback must be encouraging and constructive

## Success Criteria
- Evaluator correctly identifies correct/incorrect answers
- Misconceptions detected for 5+ common errors
- Hints are helpful and escalate properly
- Reteach steps address specific misconceptions
- All tests pass

Use LLM (Claude) for semantic validation where helpful.
```

---

## ⚙️ PHASE 2: PHYSICS EXPERT (Weeks 5-6)

### PROMPT 2.1: Physics Visualization (Free Body Diagrams & Graphs)

```
CONTEXT: Phase 1 (Math) complete. Now Phase 2 - Physics Expert.
Reference: VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md "Physics Teaching Pattern"

## Task: Implement Physics Visualization System

Physics teaching needs:
1. Free Body Diagram (FBD) generation
2. Motion graphs (v-t, a-t, x-t)
3. Vector operations visualization
4. Force analysis

## Deliverables

### 1. Free Body Diagram Generator (physics_expert.py)

```python
async def create_free_body_diagram(
    self,
    scenario: str,
    forces: List[dict]
) -> dict:
    """
    Generate FBD visualization.
    
    Input scenario: "A 5kg box on an incline at 30°, pushed with 20N force"
    
    Returns:
    {
        "diagram_type": "free_body_diagram",
        "object": {"shape": "rectangle", "mass": 5, "unit": "kg"},
        "forces": [
            {
                "name": "Applied Force",
                "magnitude": 20,
                "unit": "N",
                "direction": "30°",
                "visualization": vector_data
            },
            ...
        ],
        "coordinate_system": {"x_axis": "horizontal", "y_axis": "vertical"},
        "annotations": ["neglect friction", "object on incline"]
    }
    """
```

### 2. Motion Graph Generator (physics_expert.py)

```python
async def create_motion_graphs(
    self,
    scenario: str,
    include_graphs: List[str] = ["position", "velocity", "acceleration"]
) -> List[dict]:
    """
    Generate v-t, a-t, x-t graphs for motion scenario.
    
    Returns list of graphs showing relationships between:
    - Position (x) vs time (t)
    - Velocity (v) vs time (t)
    - Acceleration (a) vs time (t)
    
    Example: "Car accelerating from 0 to 20 m/s in 5 seconds"
    - x-t: parabolic curve (x = 0.5*a*t²)
    - v-t: linear line (v = a*t)
    - a-t: horizontal line (a = constant = 4 m/s²)
    """
```

### 3. Vector Visualization (physics_expert.py)

```python
async def visualize_vector_addition(
    self,
    vectors: List[dict]
) -> dict:
    """
    Show vector addition visually.
    
    Input: [{"magnitude": 10, "direction": 30°}, {"magnitude": 15, "direction": 120°}]
    
    Output: Visualization showing:
    - Both vectors drawn to scale
    - Resultant vector
    - Head-to-tail arrangement
    - Magnitude and direction of resultant
    """
```

### 4. Test Cases (tests/test_physics_visualization.py)

Create tests for:
- FBD generation for various scenarios
- Motion graph generation
- Vector operations
- Annotation accuracy

## Integration with RichMediaCanvas

The physics visualizations must use:
- `VectorRenderer` for force vectors
- `GraphRenderer` for motion graphs
- Proper scale and labels

## Constraints
- All forces must be drawn to correct scale (with scale indicator)
- Graphs must have proper axes labels and units
- Vector directions must be physically accurate
- Support multiple coordinate systems (Cartesian, tilted plane)

## Success Criteria
- FBD generated correctly for 5+ scenarios
- Motion graphs show correct relationships
- Vectors drawn to scale
- All test cases pass
- Visualizations are clear and educational
```

### PROMPT 2.2: Physics Teaching Sequences

```
CONTEXT: Physics visualization system built. Now create teaching sequences.

## Task: Implement Physics Teaching Patterns

Following the physics teaching pattern from CAMBODIA_REVISED_PLAN.md:
1. Scenario visualization
2. Free body diagram
3. Force analysis
4. Apply Newton's laws
5. Motion graphs
6. Physical interpretation

## Deliverables

### 1. Physics Problem Analyzer (physics_expert.py)

```python
async def analyze_problem(self, problem: RichProblem) -> dict:
    """
    Analyze physics problem and extract:
    - Scenario type: "force", "motion", "energy", "waves", "circular_motion"
    - Objects involved: masses, distances
    - Forces/interactions
    - Given values and unknowns
    - Applicable laws: Newton's laws, work-energy, momentum, etc.
    """
```

### 2. Physics Teaching Plan (physics_expert.py)

```python
async def create_visualization_plan(
    self, 
    problem: RichProblem,
    teaching_approach: str = "socratic"
) -> VisualizationPlan:
    """
    Create step-by-step physics teaching plan.
    
    Example: "A car accelerates on a road. What's the net force?"
    
    Step 1: Draw scenario (car on road)
    - Visualization: Car diagram with road
    - Question: "What's happening to the car?"
    
    Step 2: Identify forces
    - Visualization: Arrows showing all forces (applied, friction, normal, weight)
    - Question: "Which forces act on the car?"
    
    Step 3: Analyze horizontal motion
    - Visualization: FBD focusing on horizontal forces
    - Question: "What's the net force in the horizontal direction?"
    
    Step 4: Apply F = ma
    - Visualization: Equation with values
    - Question: "What must be the acceleration?"
    
    Step 5: Verify with graphs
    - Visualization: v-t graph showing acceleration
    - Question: "Does this match the graph?"
    """
```

### 3. Physics-Specific Evaluation (physics_expert.py)

```python
async def evaluate_student_response(
    self,
    student_answer: str,
    step_id: str,
    expected_answer: Optional[str] = None,
    validation_strategy: Optional[str] = None,
) -> StudentStepEvaluation:
    """
    Evaluate physics responses with physics-aware validation.
    
    Validation strategies:
    - "unit_aware": 20 m/s == 20ms^-1 == 72 km/h (if equivalent)
    - "numeric": 9.8 ≈ 10 (if discussing g)
    - "conceptual": "friction opposes motion" is correct conceptually
    """
```

### 4. Physics Misconceptions (physics_expert.py)

Common physics misconceptions:
- "Heavier objects fall faster" (no air resistance)
- "Moving object must have force applied" (inertia)
- "Normal force always equals weight" (only on horizontal surface)
- "Acceleration requires increasing speed" (can change direction)

```python
async def detect_misconception(
    self,
    student_work: str,
    correct_answer: str,
    step_id: str
) -> Optional[dict]:
    """Detect physics-specific misconceptions"""
```

## Test Cases (tests/test_physics_teaching.py)

Test for:
- Force scenario analysis
- Motion scenario analysis
- Teaching plan generation for various physics topics
- Proper visualization sequencing
- Student evaluation for physics responses

## Constraints
- All force vectors must be to scale
- Units must be explicitly shown
- Standard physics notation (F_net, a, v, etc.)
- Support SI units and common alternatives

## Success Criteria
- Analyzer correctly identifies scenario types
- Teaching plans follow physics pattern
- Visualizations are scientifically accurate
- Misconceptions properly detected
- All tests pass
```

---

## 🧪 PHASE 3: CHEMISTRY EXPERT (Weeks 7-8)

### PROMPT 3.1: Chemistry Molecular Structures & Reactions

```
CONTEXT: Physics expert complete. Now Phase 3 - Chemistry Expert.
Reference: VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md "Chemistry Teaching Pattern"

## Task: Implement Chemistry Visualization & Teaching

Chemistry teaching needs:
1. Molecular structure visualization
2. Electron configuration
3. Bonding diagrams
4. Reaction mechanisms
5. Energy diagrams

## Deliverables

### 1. Molecular Structure Visualizer (chemistry_expert.py)

```python
async def create_molecular_structure(
    self,
    compound: str,
    show_electrons: bool = True,
    show_bonds: bool = True,
    show_lone_pairs: bool = True
) -> dict:
    """
    Generate 2D molecular structure visualization.
    
    Input: "H2O"
    Output: 
    {
        "structure": {
            "atoms": [
                {"element": "O", "position": (0, 0), "valence_electrons": 6},
                {"element": "H", "position": (-1, 1), "valence_electrons": 1},
                {"element": "H", "position": (1, 1), "valence_electrons": 1}
            ],
            "bonds": [
                {"from": "O", "to": "H", "type": "single", "electrons": 2}
            ]
        },
        "visualizations": {
            "lewis_structure": {...},
            "electron_dots": {...},
            "molecular_geometry": "bent"
        }
    }
    """
```

### 2. Bonding Analysis (chemistry_expert.py)

```python
async def analyze_bonding(
    self,
    compound: str
) -> dict:
    """
    Analyze bonding type and electronegativity.
    
    Returns:
    {
        "compound": "NaCl",
        "bonding_type": "ionic",
        "electronegativity_difference": 2.1,
        "explanation": "Electronegativity difference > 1.7 indicates ionic bonding",
        "visualizations": {
            "ionic_dissociation": {...},
            "electron_transfer": {...},
            "hydration": {...}
        }
    }
    """
```

### 3. Reaction Mechanism (chemistry_expert.py)

```python
async def visualize_reaction_mechanism(
    self,
    reaction: str,
    steps: List[str]
) -> List[dict]:
    """
    Animate reaction mechanism step-by-step.
    
    Input: "HCl + NaOH → NaCl + H2O"
    
    Output: Steps showing:
    1. Reactant molecules (HCl and NaOH)
    2. Electron movement (H+ toward OH-)
    3. Bond breaking (H-Cl breaks, H-O bond forms)
    4. Hydrated product ions
    5. Net ionic equation
    """
```

### 4. Energy Diagrams (chemistry_expert.py)

```python
async def create_energy_diagram(
    self,
    reaction: str
) -> dict:
    """
    Show energy profile for reaction.
    
    Returns diagram showing:
    - Initial energy (reactants)
    - Activation energy (barrier)
    - Final energy (products)
    - Whether exothermic or endothermic
    """
```

## Constraints
- Support common elements (H, C, N, O, S, P, halogens)
- Accurate Lewis structures
- Correct VSEPR geometry
- Periodic table reference available

## Success Criteria
- Molecular structures drawn correctly for 10+ compounds
- Bonding type correctly identified
- Reaction mechanisms animated properly
- Energy diagrams accurate
- All visualizations use ChemistryVisualizer
```

### PROMPT 3.2: Chemistry Teaching Sequences

```
CONTEXT: Chemistry visualizations working. Now create teaching sequences.

## Task: Implement Chemistry Teaching Patterns

Following chemistry teaching pattern:
1. Molecular level visualization
2. Electron behavior
3. Energy considerations
4. Reaction mechanism
5. Observable result
6. Predict/explain

## Deliverables

### 1. Chemistry Problem Analyzer (chemistry_expert.py)

```python
async def analyze_problem(self, problem: RichProblem) -> dict:
    """
    Analyze chemistry problem:
    - Problem type: "bonding", "reaction", "concentration", "electrochemistry"
    - Compounds involved
    - Chemical processes
    - Observable phenomena
    """
```

### 2. Chemistry Teaching Plan (chemistry_expert.py)

```python
async def create_visualization_plan(
    self, 
    problem: RichProblem,
    teaching_approach: str = "socratic"
) -> VisualizationPlan:
    """
    Create step-by-step chemistry teaching plan.
    
    Example: "Why does NaCl dissolve in water?"
    
    Step 1: Molecular visualization
    - Show NaCl crystal structure
    - Show water molecules approaching
    - Question: "What's happening at the molecular level?"
    
    Step 2: Dipole interaction
    - Show water dipole (δ+ and δ-)
    - Show ion orientation
    - Question: "Why do water molecules orient this way?"
    
    Step 3: Energy diagram
    - Show hydration energy vs lattice energy
    - Net energy favorable
    - Question: "Is this process energetically favorable?"
    
    Step 4: Reaction animation
    - Show crystal dissolving
    - Show hydrated ions
    - Question: "What's the final state?"
    
    Step 5: Real-world application
    - Seasoning food, salt in roads
    - Question: "Where else do you see this?"
    """
```

### 3. Chemistry Evaluation (chemistry_expert.py)

```python
async def evaluate_student_response(
    self,
    student_answer: str,
    step_id: str,
    expected_answer: Optional[str] = None,
    validation_strategy: Optional[str] = None,
) -> StudentStepEvaluation:
    """
    Evaluate chemistry responses.
    
    Accept equivalent:
    - "NaCl" == "sodium chloride" == "salt"
    - Lewis structures with correct bonding but different layout
    - Balanced equations in different forms
    """
```

### 4. Chemistry Misconceptions (chemistry_expert.py)

Common chemistry misconceptions:
- "Atoms are solid" (mostly empty space)
- "Ionic bonding is one atom giving electron to another" (more nuanced)
- "All reactions release energy" (endothermic reactions exist)
- "Dissolving is not a chemical reaction" (it is, just reversible)

```python
async def detect_misconception(
    self,
    student_work: str,
    correct_answer: str,
    step_id: str
) -> Optional[dict]:
    """Detect chemistry-specific misconceptions"""
```

## Test Cases (tests/test_chemistry_teaching.py)

Test for:
- Bonding type identification
- Molecular structure accuracy
- Reaction mechanism correctness
- Energy diagram accuracy
- Teaching plan generation

## Constraints
- Accurate chemistry (double-check formulas, structures)
- Clear visualization of microscopic processes
- Support 20+ common compounds
- Proper IUPAC naming

## Success Criteria
- Teaching plans generated correctly for various topics
- Misconceptions detected appropriately
- All visualizations are chemically accurate
- Student engagement high
```

---

## 🔗 PHASE 4: INTEGRATION & POLISH (Weeks 9-10)

### PROMPT 4.1: Backend Integration

```
CONTEXT: All 3 subject experts complete. Now integrate everything.

## Task: Integrate Experts with Main Visual Tutor Backend

Connect the new expert system to your existing FastAPI backend.

## Deliverables

### 1. Update Visual Tutor Route (ai-service/api/routes/visual_tutor.py)

Add new endpoint: `POST /api/v1/visual_tutor/turn/step`

```python
@router.post("/turn/step")
async def submit_visual_tutor_step_turn(
    request: VisualTutorStepTurnRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> VisualTutorStepTurnResponse:
    """
    New endpoint for step-by-step teaching.
    
    Flow:
    1. Load session and current step
    2. Evaluate student response (via expert)
    3. Determine next action (next step, reteach, hint, skip)
    4. Generate next step
    5. Stream response to client
    """
```

### 2. Orchestrator Integration (ai-service/api/services/visual_tutor/orchestrator.py)

Update handle_visual_tutor_turn to:
1. Detect subject (math, physics, chemistry)
2. Get appropriate expert
3. Call expert methods in sequence
4. Manage state transitions

```python
async def handle_visual_tutor_step_turn(
    request: VisualTutorStepTurnRequest,
    llm_client: Optional[VisualTutorLLMClient] = None,
) -> VisualTutorStepTurnResponse:
    """
    Handle step-based teaching flow.
    """
    
    # Get expert for this subject
    expert = await get_expert(request.subject)
    
    # Evaluate student response
    evaluation = await expert.evaluate_student_response(...)
    
    # Decide next action
    if evaluation.is_correct:
        next_step = await expert.create_next_step(...)
    else:
        next_step = await expert.generate_reteach_step(...)
    
    # Stream response
    return next_step
```

### 3. Database Updates (ai-service/api/models/visual_tutor.py)

Add to VisualTutorSession:
- teaching_sequence (TeachingSequence model)
- step_evaluations (List[StudentStepEvaluation])
- expert_metadata (which expert, subject, grade)

### 4. Error Handling

Add comprehensive error handling for:
- Unknown subjects
- Invalid problems
- LLM failures
- Parsing errors
- Edge cases

## Constraints
- Backward compatible (existing /turn endpoint still works)
- Consistent with existing MongoDB schema
- Follows project's error handling patterns
- Proper logging throughout

## Success Criteria
- New /turn/step endpoint works
- Can call any expert and get valid response
- State persists between turns
- All integration tests pass
```

### PROMPT 4.2: Frontend Integration

```
CONTEXT: Backend integrated. Now update Flutter frontend.

## Task: Update Flutter UI for Step-Based Teaching

## Deliverables

### 1. Update Visual Tutor Home Screen

Update `visual_tutor_home_screen.dart` to:
1. Show step progress (Step 1 of 5)
2. Display learning objective
3. Render rich media visualizations
4. Show student task with multiple input types
5. Handle student submission
6. Stream next step

### 2. Step Progress Indicator Widget

Create `step_progress_indicator.dart`:
```dart
class StepProgressIndicator extends StatelessWidget {
  final int currentStep;
  final int totalSteps;
  final String learningObjective;
  
  // Shows step number, title, progress bar
}
```

### 3. Student Task Interactive Widget

Update `step_interaction_widget.dart` to handle:
- Free response text input
- Multiple choice selection
- Numeric answers
- Drawing/sketch responses (optional)

### 4. Connect to New /turn/step Endpoint

Update repository to call new endpoint:
```dart
Future<VisualTutorStepTurnResponse> submitStepResponse(
  String sessionId,
  String stepId,
  String response,
) async {
  final request = VisualTutorStepTurnRequest(
    sessionId: sessionId,
    stepId: stepId,
    message: response,
    action: 'submit_step_response',
  );
  
  return await http.post('/api/v1/visual_tutor/turn/step', request);
}
```

### 5. State Management

Create StepBoardProvider to manage:
- Current step
- Teaching sequence
- Student responses
- Navigation between steps

### 6. Animation Improvements

Add smooth transitions:
- Step-to-step animations
- Visualization fade-in
- Student interaction feedback
- Success/error states

## Constraints
- Mobile responsive
- Performance optimized (smooth 60fps animations)
- Accessible (proper contrast, sizing)
- Support both English and Khmer

## Success Criteria
- UI matches design from CAMBODIA_REVISED_PLAN.md
- Smooth step progression
- All visualization types render
- Student can interact and submit answers
- Next step loads and displays correctly
```

### PROMPT 4.3: Performance & Optimization

```
CONTEXT: Integration complete. Now optimize for production.

## Task: Performance Optimization

Ensure system meets performance targets:

## Deliverables

### 1. Backend Performance

Target: <2 seconds per step generation

Optimize:
- LLM prompting (reduce tokens)
- Caching common visualizations
- Parallel processing where possible
- Database query optimization
- Connection pooling

### 2. Frontend Performance

Target: 60fps animations, <1s visualization render

Optimize:
- Lazy load visualizations
- Cache graphs and diagrams
- Optimize CustomPaint operations
- Reduce rebuild cycles
- Image compression

### 3. Memory Management

- Profile memory usage
- Fix leaks in stateful widgets
- Implement disposal of large objects
- Stream optimization

### 4. Load Testing

Test with:
- 100 concurrent users
- Varying problem complexity
- Different network conditions
- Mobile vs web

## Success Criteria
- 95% of requests complete in <2s
- UI remains responsive during loads
- Memory usage stable
- No crashes under load
```

---

## ✅ VALIDATION & TESTING PROMPTS

### PROMPT V.1: Comprehensive Testing

```
CONTEXT: All implementation complete. Now comprehensive testing.

## Task: Create & Run Complete Test Suite

## Test Coverage

### Unit Tests (90%+ coverage target)
- All expert methods
- Model validation
- Utility functions
- Error cases

### Integration Tests
- End-to-end flows for each subject
- Multi-step teaching sequences
- State persistence
- Error recovery

### UI/Widget Tests
- Component rendering
- User interactions
- State changes
- Navigation

### E2E Tests (Manual scenarios)
- Student solves 1 complete math problem
- Student solves 1 complete physics problem
- Student solves 1 complete chemistry problem
- Error scenarios (wrong answers, timeouts)

## Test Data

Create fixtures for:
- 10 math problems (various types)
- 10 physics problems (various scenarios)
- 10 chemistry problems (various reactions)
- Different student responses (correct, wrong, partial)
- Edge cases

## Success Criteria
- 90%+ code coverage
- All test suites pass
- No flaky tests
- Performance benchmarks met
- Manual scenarios work smoothly

Run all tests before Phase 4 deployment.
```

### PROMPT V.2: Quality Assurance

```
CONTEXT: All tests passing. Final QA before deployment.

## Task: Quality Assurance Checklist

## Verification

### Code Quality
- [ ] No unused imports
- [ ] No dead code
- [ ] Proper error handling everywhere
- [ ] Type hints complete
- [ ] Documentation complete
- [ ] No security vulnerabilities
- [ ] No hardcoded secrets

### Functionality
- [ ] Math expert: 5 problem types working
- [ ] Physics expert: 3 scenario types working
- [ ] Chemistry expert: 3 reaction types working
- [ ] Teaching sequences flow correctly
- [ ] Student interaction works
- [ ] Evaluation works
- [ ] Reteaching works

### User Experience
- [ ] UI is intuitive
- [ ] Animations are smooth
- [ ] Messages are clear
- [ ] Khmer translations complete
- [ ] Mobile responsive
- [ ] Accessibility OK

### Performance
- [ ] Step generation: <2s
- [ ] Visualization render: <1s
- [ ] UI animations: 60fps
- [ ] Memory usage stable
- [ ] No crashes

### Deployment Readiness
- [ ] All dependencies documented
- [ ] Database migrations ready
- [ ] Backward compatibility verified
- [ ] Rollback plan documented
- [ ] Monitoring configured
- [ ] Documentation complete

Sign off on this checklist before production.
```

---

## 📋 PROMPT EXECUTION GUIDE

### How to Use These Prompts With Claude

1. **Start with INITIAL CONTEXT PROMPT**
   - Copy entire "INITIAL CONTEXT PROMPT" section
   - Paste into Claude
   - Wait for confirmation Claude understands

2. **Execute Phase 0 Prompts (in order)**
   ```
   PROMPT 0.1: Rich Media Rendering
   PROMPT 0.2: Curriculum Database
   PROMPT 0.3: Expert Base Framework
   ```
   After each:
   - Claude writes complete implementation
   - You review and commit code
   - Move to next prompt

3. **Execute Phase 1-3 Prompts (in order)**
   - Same pattern as Phase 0
   - Claude implements feature
   - You integrate into project
   - Run tests
   - Commit

4. **Execute Phase 4 & Validation Prompts**
   - Integration prompts
   - Testing prompts
   - QA prompt
   - Final checklist

### Tips for Best Results

1. **Before Each Prompt**
   - Tell Claude: "I'm ready for PROMPT X.Y"
   - Provide any context about what's done
   - Share file structure if changed

2. **During Execution**
   - Ask Claude to explain architecture decisions
   - Request code reviews
   - Ask for alternatives if unsure
   - Request test coverage

3. **After Each Prompt**
   - Ask: "What should I do next?"
   - Ask: "Are there any gotchas?"
   - Ask: "How do I test this?"
   - Ask: "What metrics should I track?"

4. **For Integration**
   - Tell Claude about existing code
   - Ask how to integrate new code
   - Ask for migration strategies
   - Ask for backward compatibility checks

5. **For Debugging**
   - Share error messages
   - Ask Claude to analyze
   - Ask for debugging suggestions
   - Ask for refactoring if needed

---

## 🎯 Expected Outcomes By Phase

### Phase 0 (2 weeks)
- [ ] Rich media components work
- [ ] Curriculum database loaded
- [ ] Expert framework in place
- [ ] Foundation stable and tested

### Phase 1 (2 weeks)
- [ ] Math expert complete
- [ ] 10+ math problems working
- [ ] Teaching patterns validated
- [ ] Student evaluation working

### Phase 2 (2 weeks)
- [ ] Physics expert complete
- [ ] FBD and graphs working
- [ ] 10+ physics problems working
- [ ] Performance optimized

### Phase 3 (2 weeks)
- [ ] Chemistry expert complete
- [ ] Molecular structures working
- [ ] Reactions animated
- [ ] 10+ chemistry problems working

### Phase 4 (2 weeks)
- [ ] All systems integrated
- [ ] Frontend updated
- [ ] Full test coverage
- [ ] Production ready

---

## 📞 When Stuck

If Claude gets stuck or produces suboptimal code:

1. **Ask for clarification**: "Can you explain this section?"
2. **Request examples**: "Show me how this would work for [specific problem]"
3. **Ask for alternatives**: "Are there better approaches?"
4. **Request refactoring**: "Can this be simpler?"
5. **Check constraints**: "Does this follow the architecture?"
6. **Review documentation**: "How does this match the spec?"

Always reference the audit documents:
- "As documented in VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md..."
- "Following VISUAL_TUTOR_TECHNICAL_SPEC.md Section X..."
- "Using patterns from VISUAL_TUTOR_QUICK_START.md..."

---

## ✨ Final Notes

These prompts are:
- **Comprehensive**: Cover entire system
- **Sequential**: Each builds on previous
- **Specific**: Detailed enough to implement
- **Reference-based**: Tied to your audit documents
- **Flexible**: Can be adjusted for your needs
- **Tested**: Based on proven architecture patterns

The key to success:
1. Follow prompts in order
2. Test after each phase
3. Reference the audit documents
4. Ask Claude for clarification when needed
5. Review code quality regularly

Good luck building your AI Visual Tutor! 🚀

