# Start Building Your AI Visual Tutor Today

**Vision**: Create a real 1-on-1 AI teacher (NOT a chatbot) for Cambodia Grade 10-12 students in Math, Physics, Chemistry.

This guide tells you exactly what to do this week.

---

## 🎯 This Week's Goals

By end of this week, you should have:
- [ ] Decision on tech stack for visualizations
- [ ] Curriculum data structure designed
- [ ] First sample problem with visuals
- [ ] Subject expert framework started
- [ ] Team roles assigned

---

## 📋 Day 1: Planning (2 hours)

### Task 1.1: Understand the Current System (30 min)
**What you're building on**:
```
Your current system: Student inputs problem → AI generates full answer
Your new system:    Student inputs problem → AI guides step-by-step discovery
```

**Read**:
1. VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md → "Teaching Patterns by Subject"
2. VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md → "Example: Complete Flow"

**Action**: Draw a diagram showing:
- What happens NOW (chatbot-like flow)
- What should happen (teacher-like flow)

---

### Task 1.2: Decide on Visualization Tech (1.5 hours)

**Question 1: How will you draw graphs?**

Option A: **Plotly.dart** (Recommended for start)
```dart
// Easy to use, good for math/physics
plotly.plot(
  data: PlotlyData(
    x: [1, 2, 3, 4, 5],
    y: [1, 4, 9, 16, 25],
    mode: 'lines+markers',
  ),
);
// Pros: Simple, looks good, interactive
// Cons: Limited customization for physics vectors
```

Option B: **Canvas + Custom** (Full control)
```dart
// More work, but ultimate control
canvas.drawPath(...);
canvas.drawArc(...);
canvas.drawLine(...);
// Pros: Complete control
// Cons: More code, more bugs to fix
```

Option C: **Rive** (Pre-made animations)
```
// Great for animations
// Can design in Rive editor
// Pros: Beautiful, pre-made
// Cons: Less flexible, limited types
```

**Decision Matrix**:
| Need | Plotly | Canvas | Rive |
|------|--------|--------|------|
| Graphs | ✅ Good | ✅ Perfect | ❌ No |
| FBD (Physics) | ❌ Limited | ✅ Perfect | ⚠️ Possible |
| Molecules (Chem) | ❌ No | ✅ Perfect | ❌ No |
| Speed | ✅ Fast | ⚠️ Slower | ✅ Fast |
| Learning curve | ✅ Easy | ❌ Hard | ⚠️ Medium |

**Recommendation**: 
- Start with **Plotly.dart** for graphs (math + physics)
- Add **Canvas** for custom shapes (FBD, molecules)
- Use **Rive** for premade animations (transitions)

**Your Decision** (fill in):
- Graphs → _________
- Physics Diagrams → _________
- Chemistry Molecules → _________

---

### Task 1.3: Understand 3 Teaching Approaches (1 hour)

**Read**: VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md → "Teaching Patterns by Subject"

**For each subject, identify**:
1. What visualization comes first?
2. What question is asked?
3. How does student respond?
4. What's revealed next?

**Fill in for Math (Linear Equation)**:
```
Visualization 1: ____________
Question 1: ____________
Student Response: ____________
Visualization 2: ____________
```

**Fill in for Physics (Force)**:
```
Visualization 1: ____________
Question 1: ____________
Student Response: ____________
Visualization 2: ____________
```

**Fill in for Chemistry (Bonding)**:
```
Visualization 1: ____________
Question 1: ____________
Student Response: ____________
Visualization 2: ____________
```

---

## 📚 Day 2: Foundation Structure (3 hours)

### Task 2.1: Create Problem Data Structure (1 hour)

**File**: `ai-service/api/models/rich_problem.py` (NEW)

```python
from pydantic import BaseModel
from typing import List, Optional, Literal
from enum import Enum

class Subject(str, Enum):
    MATH = "math"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"

class Grade(str, Enum):
    GRADE_10 = "grade_10"
    GRADE_11 = "grade_11"
    GRADE_12 = "grade_12"

class RichProblem(BaseModel):
    """A problem that needs rich visualization"""
    
    problem_id: str
    subject: Subject
    grade: Grade
    unit: str  # e.g., "Linear Equations", "Forces", "Bonding"
    
    # The problem itself
    problem_text: str
    problem_text_khmer: str  # Khmer translation
    
    # What type of problem
    problem_type: str
    # For math: "linear_equation", "quadratic", "trigonometry"
    # For physics: "force", "motion", "energy"
    # For chemistry: "bonding", "reaction", "concentration"
    
    # What visualizations are needed
    visualizations_needed: List[str]
    # Examples: ["graph", "number_line", "free_body_diagram", "molecule_structure"]
    
    # Concepts this covers
    concepts: List[str]
    prerequisites: List[str]
    
    # Solution approach
    teaching_approach: Literal["socratic", "discovery", "guided"]
    
    class Config:
        json_schema_extra = {
            "example": {
                "problem_id": "prob_001",
                "subject": "math",
                "grade": "grade_10",
                "unit": "Linear Equations",
                "problem_text": "Solve: 2x + 5 = 13",
                "problem_text_khmer": "ដោះស្រាយ៖ ២x + ៥ = ១៣",
                "problem_type": "linear_equation",
                "visualizations_needed": ["equation", "number_line"],
                "concepts": ["linear_equation", "inverse_operations"],
                "prerequisites": ["arithmetic", "variables"],
                "teaching_approach": "socratic"
            }
        }
```

**Your Action**:
1. Copy above code
2. Create file
3. Add 5 more examples (different subjects)

---

### Task 2.2: Create Visualization Plan Structure (1 hour)

**File**: `ai-service/api/models/visualization_plan.py` (NEW)

```python
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class VisualizationStep(BaseModel):
    """One visualization element in the teaching sequence"""
    
    step_id: str
    visualization_type: str
    # "graph", "equation", "diagram", "animation", "number_line", 
    # "free_body_diagram", "molecule", "energy_diagram"
    
    # What to render
    content: Dict[str, Any]
    # For graph: {"function": "x^2", "xmin": -5, "xmax": 5, "highlight": [2]}
    # For diagram: {"type": "triangle", "angles": [60, 60, 60]}
    # For molecule: {"compound": "H2O", "show_bonds": true}
    
    # How to animate
    animation_type: Optional[str]  # "fade_in", "draw", "highlight", etc.
    duration_ms: int = 1000
    
    # What to ask student
    student_question: str
    student_question_khmer: str
    expected_response_type: str
    # "multiple_choice", "numeric", "text", "draw"
    
    # Next action based on response
    on_correct: str  # "next_step", "ask_deeper", "show_application"
    on_incorrect: str  # "reteach", "hint", "explain_differently"

class VisualizationPlan(BaseModel):
    """Complete plan for teaching a problem"""
    
    plan_id: str
    problem_id: str
    
    steps: List[VisualizationStep]
    
    total_duration_ms: int  # Total teaching time
    difficulty_level: str  # "easy", "medium", "hard"
    
    # Success criteria
    mastery_signals: List[str]
    # ["student answered step 1 correctly", 
    #  "student reasoned about concept",
    #  "student applied formula"]
```

**Your Action**:
1. Copy above code
2. Create file
3. Create sample plan for: "Solve 2x + 5 = 13"

---

### Task 2.3: Create Subject Expert Base (1 hour)

**File**: `ai-service/api/services/subject_experts/base_expert.py` (NEW)

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from api.models.rich_problem import RichProblem
from api.models.visualization_plan import VisualizationPlan

class SubjectExpert(ABC):
    """Base class for subject-specific experts"""
    
    subject: str  # "math", "physics", "chemistry"
    
    @abstractmethod
    async def analyze_problem(self, problem: RichProblem) -> dict:
        """Understand the problem and identify key elements"""
        pass
    
    @abstractmethod
    async def create_visualization_plan(
        self, 
        problem: RichProblem,
    ) -> VisualizationPlan:
        """Create step-by-step teaching plan with visualizations"""
        pass
    
    @abstractmethod
    async def evaluate_student_response(
        self,
        student_answer: str,
        correct_answer: str,
        step_number: int,
    ) -> dict:
        """Check if student understood this step"""
        # Returns: {"is_correct": bool, "misconception": str, "feedback": str}
        pass
    
    @abstractmethod
    async def provide_hint(self, step_id: str) -> str:
        """Provide a hint if student is stuck"""
        pass
    
    @abstractmethod
    async def detect_misconception(
        self,
        student_work: str,
        correct_answer: str,
    ) -> Optional[str]:
        """Identify common misconceptions"""
        pass

class MathExpert(SubjectExpert):
    """Expert for mathematics problems"""
    subject = "math"
    
    async def analyze_problem(self, problem: RichProblem) -> dict:
        # Parse math expression
        # Identify operation type (linear, quadratic, etc.)
        # Find key elements (coefficients, variables, etc.)
        pass
    
    async def create_visualization_plan(self, problem: RichProblem) -> VisualizationPlan:
        # For linear: show number line, then equation manipulation
        # For quadratic: show graph, then factors
        # For trig: show unit circle, then identities
        pass
    
    # ... implement other methods

class PhysicsExpert(SubjectExpert):
    """Expert for physics problems"""
    subject = "physics"
    
    async def create_visualization_plan(self, problem: RichProblem) -> VisualizationPlan:
        # Identify scenario type (force, motion, energy, etc.)
        # Create free body diagram
        # Show relevant graphs (v-t, a-t, etc.)
        # Build to solution
        pass
    
    # ... implement other methods

class ChemistryExpert(SubjectExpert):
    """Expert for chemistry problems"""
    subject = "chemistry"
    
    async def create_visualization_plan(self, problem: RichProblem) -> VisualizationPlan:
        # Identify molecule/reaction type
        # Show molecular structure
        # Show electron/bonding interactions
        # Show macroscopic result
        pass
    
    # ... implement other methods
```

**Your Action**:
1. Copy above code
2. Create file
3. Implement stub methods (just `pass` for now)

---

## 🗂️ Day 3: Data Structure (2 hours)

### Task 3.1: Create Curriculum Database Schema (1 hour)

**File**: `ai-service/api/models/curriculum_cambodia.py` (NEW)

```python
from pydantic import BaseModel
from typing import List, Dict

class LearningOutcome(BaseModel):
    """What student should be able to do"""
    code: str  # "MG.10.1.1"
    description: str
    description_khmer: str

class Topic(BaseModel):
    """A topic in Cambodia curriculum"""
    topic_id: str
    subject: str  # "math", "physics", "chemistry"
    grade: str
    unit: str
    
    name: str
    name_khmer: str
    
    # Concepts covered
    concepts: List[str]
    prerequisites: List[str]  # Topic IDs
    
    # Learning outcomes
    learning_outcomes: List[LearningOutcome]
    
    # Problem examples for this topic
    problem_examples: List[str]  # Problem IDs

class CurriculumGraph(BaseModel):
    """Concept prerequisite graph for a subject"""
    subject: str
    
    # All topics
    topics: Dict[str, Topic]
    
    # Edges: topic_id -> [prerequisite_topic_ids]
    prerequisites: Dict[str, List[str]]
    
    def get_prerequisites(self, topic_id: str) -> List[Topic]:
        """Get all prerequisite topics"""
        pass
    
    def get_next_topics(self, topic_id: str) -> List[Topic]:
        """Get topics that build on this one"""
        pass
```

**Your Action**:
1. Copy above code
2. Create file
3. Create sample curriculum for: "Grade 10 Math - Linear Equations"

---

### Task 3.2: Map Cambodia Grade 10-12 Curriculum (1 hour)

**Create**: `ai-service/data/cambodia_curriculum.json`

```json
{
  "subjects": {
    "math": {
      "grade_10": [
        {
          "unit": "Linear Equations",
          "topics": [
            {
              "name": "Solving Linear Equations",
              "concepts": ["variable", "equation", "inverse_operations"],
              "prerequisites": ["arithmetic", "integers"],
              "problems": ["solve_2x+5=13", "solve_3x-7=14"]
            },
            {
              "name": "Systems of Equations",
              "concepts": ["system", "substitution", "elimination"],
              "prerequisites": ["linear_equations"],
              "problems": ["system_2x2", "system_3x3"]
            }
          ]
        },
        {
          "unit": "Quadratic Functions",
          "topics": [
            {
              "name": "Graphing Quadratics",
              "concepts": ["parabola", "vertex", "roots"],
              "prerequisites": ["linear_functions", "polynomials"],
              "problems": ["graph_x^2+bx+c", "find_vertex"]
            }
          ]
        }
      ],
      "grade_11": [...],
      "grade_12": [...]
    },
    "physics": {
      "grade_10": [
        {
          "unit": "Mechanics",
          "topics": [
            {
              "name": "Forces and Newton's Laws",
              "concepts": ["force", "mass", "acceleration", "F=ma"],
              "prerequisites": ["kinematics"],
              "problems": ["force_on_incline", "tension_in_rope"]
            }
          ]
        }
      ]
    },
    "chemistry": {
      "grade_10": [
        {
          "unit": "Bonding",
          "topics": [
            {
              "name": "Ionic vs Covalent Bonding",
              "concepts": ["ions", "covalent", "electronegativity"],
              "prerequisites": ["atomic_structure"],
              "problems": ["predict_bonding_type", "draw_lewis_structure"]
            }
          ]
        }
      ]
    }
  }
}
```

**Your Action**:
1. Research Cambodia MOE curriculum (or use above as template)
2. Create JSON with 5-10 topics per grade
3. Map to your problems

---

## 🎬 Day 4: First Example (3 hours)

### Task 4.1: Create First Problem (1 hour)

**Problem**: Solve 2x + 5 = 13

**File**: `ai-service/data/sample_problems.py`

```python
from api.models.rich_problem import RichProblem, Subject, Grade

SAMPLE_PROBLEM_LINEAR_EQUATION = RichProblem(
    problem_id="prob_math_001",
    subject=Subject.MATH,
    grade=Grade.GRADE_10,
    unit="Linear Equations",
    
    problem_text="Solve: 2x + 5 = 13",
    problem_text_khmer="ដោះស្រាយ៖ ២x + ៥ = ១៣",
    
    problem_type="linear_equation",
    
    visualizations_needed=[
        "equation",
        "number_line",
        "step_transformation",
    ],
    
    concepts=["linear_equation", "variable", "inverse_operations"],
    prerequisites=["arithmetic", "integers"],
    
    teaching_approach="socratic",
)

# Solution approach
SOLUTION_STEPS = [
    {
        "step_id": "step_1",
        "title": "Identify the equation",
        "visualization": {
            "type": "equation",
            "content": "2x + 5 = 13",
        },
        "question": "What do you notice about this equation?",
        "expected_responses": [
            "There are two terms on the left",
            "One term has a variable",
            "One term is just a number",
        ]
    },
    {
        "step_id": "step_2",
        "title": "Isolate the variable term",
        "visualization": {
            "type": "equation_transformation",
            "from": "2x + 5 = 13",
            "to": "2x = 8",
            "operation": "subtract 5 from both sides",
        },
        "question": "What operation would undo the +5?",
        "expected_response": "Subtract 5 from both sides",
    },
    {
        "step_id": "step_3",
        "title": "Solve for x",
        "visualization": {
            "type": "equation_transformation",
            "from": "2x = 8",
            "to": "x = 4",
            "operation": "divide both sides by 2",
        },
        "question": "Now what needs to happen to isolate x?",
        "expected_response": "Divide by 2",
    },
    {
        "step_id": "step_4",
        "title": "Verify the solution",
        "visualization": {
            "type": "verification",
            "check": "2(4) + 5 = 13 ✓",
            "number_line": {"highlight": 4},
        },
        "question": "Does our answer check out?",
        "expected_response": "Yes, it works!",
    }
]
```

**Your Action**:
1. Copy above code
2. Create file
3. Define 3 more problems (physics, chemistry)

---

### Task 4.2: Design Visualization for First Problem (1.5 hours)

**File**: `ai-service/api/services/math_expert_sample.py`

```python
async def create_linear_equation_visualization():
    """
    Create visual teaching plan for: Solve 2x + 5 = 13
    """
    
    return {
        "steps": [
            {
                "step_id": "math_001_s1",
                "visualization_type": "equation_with_labels",
                "content": {
                    "equation": "2x + 5 = 13",
                    "labels": {
                        "2": "coefficient",
                        "x": "variable",
                        "5": "constant",
                        "13": "result",
                    },
                    "highlight": ["x"],  # Show what we're solving for
                },
                "animation_type": "fade_in",
                "duration_ms": 1500,
                
                "student_question": "What do you notice about this equation?",
                "student_question_khmer": "តើអ្វីដែលអ្នកកត់សម្គាល់ក្នុងសមីការនេះ?",
                "expected_response_type": "text",
                
                "on_correct": "next_step",
                "on_incorrect": "ask_again",
            },
            {
                "step_id": "math_001_s2",
                "visualization_type": "equation_transformation",
                "content": {
                    "before": "2x + 5 = 13",
                    "operation": "subtract 5 from both sides",
                    "after": "2x = 8",
                    "show_work": true,
                },
                "animation_type": "transform",
                "duration_ms": 2000,
                
                "student_question": "What operation should we do next?",
                "expected_response_type": "multiple_choice",
                "choices": [
                    "Add 5",
                    "Subtract 5",
                    "Multiply by 2",
                    "Divide by 2",
                ],
                
                "on_correct": "explain",
                "on_incorrect": "provide_hint",
            },
            # ... more steps
        ],
        
        "total_duration_ms": 8000,
        "difficulty_level": "easy",
    }
```

**Your Action**:
1. Create file with sample function
2. Test that it returns valid structure
3. Add visualization content for each step

---

### Task 4.3: Create Frontend Visualization Component (1 hour)

**File**: `ai_tutor/lib/features/visual_tutor/presentation/widgets/rich_visualization_renderer.dart` (NEW)

```dart
import 'package:flutter/material.dart';

/// Renders rich visualizations (not just board actions)
class RichVisualizationRenderer extends StatelessWidget {
  const RichVisualizationRenderer({
    required this.visualization,
    required this.onInteraction,
  });

  final Map<String, dynamic> visualization;
  final ValueChanged<String> onInteraction;

  @override
  Widget build(BuildContext context) {
    final visualizationType = visualization['visualization_type'] as String;

    return switch (visualizationType) {
      'equation' => _buildEquationVisualization(),
      'equation_with_labels' => _buildLabeledEquationVisualization(),
      'equation_transformation' => _buildTransformationVisualization(),
      'graph' => _buildGraphVisualization(),
      'free_body_diagram' => _buildFreeBodyDiagramVisualization(),
      'molecule' => _buildMoleculeVisualization(),
      'number_line' => _buildNumberLineVisualization(),
      _ => Center(
        child: Text('Unknown visualization type: $visualizationType'),
      ),
    };
  }

  Widget _buildEquationVisualization() {
    return Container(
      padding: const EdgeInsets.all(24),
      child: Text(
        visualization['content']['equation'] ?? '?',
        style: const TextStyle(
          fontSize: 32,
          fontFamily: 'Courier',
        ),
      ),
    );
  }

  Widget _buildLabeledEquationVisualization() {
    // Draw equation with labels below each term
    return Column(
      children: [
        Text(visualization['content']['equation']),
        const SizedBox(height: 16),
        // Show labels for each part
      ],
    );
  }

  Widget _buildTransformationVisualization() {
    // Show before → operation → after
    return Column(
      children: [
        Text(visualization['content']['before']),
        const SizedBox(height: 8),
        Text(visualization['content']['operation']),
        const SizedBox(height: 8),
        Text(visualization['content']['after']),
      ],
    );
  }

  Widget _buildGraphVisualization() {
    // Use Plotly or Canvas to draw graph
    // TODO: Implement
    return placeholder();
  }

  Widget _buildFreeBodyDiagramVisualization() {
    // Draw forces as vectors
    // TODO: Implement
    return placeholder();
  }

  Widget _buildMoleculeVisualization() {
    // Draw molecular structure
    // TODO: Implement
    return placeholder();
  }

  Widget _buildNumberLineVisualization() {
    // Draw number line with highlighted point
    // TODO: Implement
    return placeholder();
  }

  Widget placeholder() =>
      const Center(child: Text('Visualization coming soon'));
}
```

**Your Action**:
1. Copy above code
2. Create file
3. Implement `_buildEquationVisualization()` fully
4. Leave others as TODO

---

## 🧪 Day 5: Testing & Integration (2 hours)

### Task 5.1: Test First Problem Flow (1 hour)

**File**: `ai-service/tests/test_math_expert_sample.py`

```python
import pytest
from api.services.math_expert_sample import create_linear_equation_visualization

@pytest.mark.asyncio
async def test_linear_equation_visualization():
    """Test that first visualization is created correctly"""
    
    result = await create_linear_equation_visualization()
    
    # Verify structure
    assert "steps" in result
    assert len(result["steps"]) > 0
    
    first_step = result["steps"][0]
    assert first_step["visualization_type"] == "equation_with_labels"
    assert "2x + 5 = 13" in first_step["content"]["equation"]
    assert first_step["student_question"] is not None

@pytest.mark.asyncio
async def test_problem_parsing():
    """Test that problem is parsed correctly"""
    
    problem = SAMPLE_PROBLEM_LINEAR_EQUATION
    
    assert problem.subject == Subject.MATH
    assert problem.grade == Grade.GRADE_10
    assert "linear_equation" in problem.visualizations_needed
```

**Your Action**:
1. Copy above code
2. Create file
3. Run tests: `pytest`
4. Verify they pass

---

### Task 5.2: Create End-to-End Example (1 hour)

**What**: Show full flow from student input to visualization

**Create**: `ai-service/examples/linear_equation_flow.py`

```python
"""
Example: Complete flow for "Solve 2x + 5 = 13"
"""

async def demo_linear_equation_teaching():
    """Demonstrate the full teaching flow"""
    
    # Step 1: Student input
    problem = SAMPLE_PROBLEM_LINEAR_EQUATION
    
    # Step 2: Expert creates teaching plan
    math_expert = MathExpert()
    visualization_plan = await math_expert.create_visualization_plan(problem)
    
    # Step 3: Show first step
    step_1 = visualization_plan.steps[0]
    print(f"Question: {step_1.student_question}")
    print(f"Visualization: {step_1.content}")
    
    # Step 4: Student responds
    student_answer = "There's a variable and a number"
    evaluation = await math_expert.evaluate_student_response(
        student_answer,
        correct_answer=step_1.expected_response_type,
        step_number=1,
    )
    
    # Step 5: Show next step
    if evaluation["is_correct"]:
        step_2 = visualization_plan.steps[1]
        print(f"Next question: {step_2.student_question}")
        print(f"Next visualization: {step_2.content}")
    
    # Continue...

if __name__ == "__main__":
    import asyncio
    asyncio.run(demo_linear_equation_teaching())
```

**Your Action**:
1. Copy above code
2. Create file
3. Run it: `python example_linear_equation_flow.py`
4. See the flow printed out

---

## ✅ Week 1 Checklist

- [ ] Tech stack decided (Plotly for graphs, Canvas for custom shapes)
- [ ] Problem data model created
- [ ] Visualization plan model created
- [ ] Subject expert base class created
- [ ] First sample problem defined (2x + 5 = 13)
- [ ] Teaching steps designed
- [ ] Visualization renderer component created
- [ ] Tests written and passing
- [ ] End-to-end example working
- [ ] Khmer translations added for first problem

---

## 📝 Your Action Items (Copy & Paste)

**Copy this to your project tracker**:

```
WEEK 1: Foundation
[ ] Decide visualization tech (Plotly, Canvas, Rive)
[ ] Create rich_problem.py model
[ ] Create visualization_plan.py model
[ ] Create subject_experts/base_expert.py
[ ] Create sample_problems.py with first 3 problems
[ ] Map Cambodia curriculum to JSON
[ ] Create RichVisualizationRenderer widget
[ ] Write unit tests
[ ] Create end-to-end example
[ ] Add Khmer translations

WEEK 2: Math Expert
[ ] Implement MathExpert class
[ ] Create equation visualization functions
[ ] Create graph visualization functions
[ ] Implement evaluation logic
[ ] Test with 5 different math problems
[ ] Add misconception detection

WEEK 3: Physics Expert
[ ] Implement PhysicsExpert class
[ ] Create FBD visualization functions
[ ] Create graph visualization functions
[ ] Implement motion analysis
[ ] Test with 5 physics problems

WEEK 4: Chemistry Expert
[ ] Implement ChemistryExpert class
[ ] Create molecule visualization functions
[ ] Create reaction visualization functions
[ ] Implement bonding analysis
[ ] Test with 5 chemistry problems

WEEK 5: Integration & Polish
[ ] Connect to existing tutor backend
[ ] Update Flutter frontend
[ ] Add performance optimizations
[ ] User acceptance testing
[ ] Production deployment
```

---

## 🚀 Quick Reference: What to Build

### This Week
1. **Backend**: Problem models + Expert base class
2. **Data**: Curriculum structure + First 3 problems
3. **Frontend**: Visualization renderer component
4. **Example**: End-to-end flow for linear equation

### Result
You'll have:
- ✅ Data structure for rich problems
- ✅ Framework for subject experts
- ✅ First visualization example
- ✅ Clear path forward

### Time: ~10 hours this week

---

## 📞 Questions?

**"Which visualization library should I use?"**  
→ Start with **Plotly.dart** (fast, easy)  
→ Add Canvas later (fine-grained control)

**"How do I structure Khmer translations?"**  
→ Add `_khmer` suffix to all text fields  
→ Use translation service wrapper

**"When do I connect to the existing tutor?"**  
→ Week 5, after basic flow works

**"Is this replacing the current system?"**  
→ No, building on top of it  
→ New `/turn/step` endpoint  
→ Existing code stays intact

---

**Start with the first task TODAY. You've got this!** 🚀

