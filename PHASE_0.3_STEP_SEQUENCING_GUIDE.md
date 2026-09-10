# Phase 0.3: Step Sequencing Implementation Guide

**Status**: 🟡 READY TO START  
**Estimated Duration**: 8-12 hours  
**Complexity**: Medium (orchestration layer)  

---

## 🎯 What is Step Sequencing?

Instead of AI responding with full solution at once (like ChatGPT), we want:

**Student**: "I need to solve 2x + 5 = 13"

**AI** (Step by step):
1. Write problem: `2x + 5 = 13`
2. "Subtract 5 from both sides"
3. Write: `2x = 8`
4. "Divide by 2"
5. Write: `x = 4`
6. "Check: 2(4) + 5 = 13 ✓"

**Not**: Full solution in one message.

---

## 🏗️ Architecture

```
Student Input
    ↓
[Backend: Adaptive Learning Service]
    ↓
1. Detect what student needs
2. Generate teaching steps
3. Apply adaptive rules
    ↓
[Step Sequencer]
    ↓
For each step:
  - Create action objects
  - Send to Flutter
  - Wait for student interaction
  - Evaluate response
  - Branch to next step
    ↓
[Flutter: RichMediaCanvas]
    ↓
Render step visually
```

---

## 📋 Implementation Tasks

### Task 1: Backend Models (Python)

**File**: `ai_service/api/models/teaching_step.py`

```python
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class StepType(str, Enum):
    EXPLANATION = "explanation"      # AI explains concept
    VISUALIZATION = "visualization"  # Show diagram/graph
    QUESTION = "question"            # Ask student to do something
    FEEDBACK = "feedback"            # Respond to student
    HINT = "hint"                    # Give a clue
    CHECK = "check"                  # Verify student understands

class TeachingStep(BaseModel):
    id: str
    step_number: int
    type: StepType
    title: str
    description: str
    
    # Visual content (for RichMediaCanvas)
    visualizations: List[dict]  # List of board actions
    
    # Interaction
    question: Optional[str] = None
    expected_answer: Optional[str] = None
    
    # Branching
    next_step_id: Optional[str] = None
    wrong_answer_next_step: Optional[str] = None
    
    # Metadata
    learning_objective: str
    difficulty: int  # 1-5
    estimated_time_seconds: int

class TeachingPlan(BaseModel):
    """Complete multi-step lesson plan"""
    id: str
    problem: str
    subject: str  # "math", "physics", "chemistry"
    grade_level: int
    
    steps: List[TeachingStep]
    adaptive_rules: dict  # JSON rules for branching
```

---

### Task 2: Backend Service (Python)

**File**: `ai_service/api/services/step_sequencing_service.py`

```python
import logging
from typing import List, Optional
from pydantic import BaseModel
from services.graph_cag.state import TRACECAGState
from services.knowledge_graph import KGService
from models.teaching_step import TeachingStep, TeachingPlan

logger = logging.getLogger(__name__)

class StepSequencingService:
    """Generates and manages multi-step teaching plans"""
    
    def __init__(self, kg_service: KGService, model_gateway):
        self.kg = kg_service
        self.models = model_gateway
    
    async def generate_teaching_plan(
        self,
        problem: str,
        subject: str,
        grade_level: int,
        student_learning_style: Optional[str] = None,
    ) -> TeachingPlan:
        """
        Generate complete step-by-step teaching plan
        
        Args:
            problem: Student's question/problem
            subject: "math", "physics", or "chemistry"
            grade_level: 10-12 (Cambodia curriculum)
            student_learning_style: "visual", "analytical", "kinesthetic"
        
        Returns:
            TeachingPlan with multiple sequenced steps
        
        Process:
        1. Analyze problem with TRACECAG
        2. Retrieve relevant concepts from KG
        3. Plan steps using Socratic method
        4. Generate visualizations for each step
        5. Define branching rules
        """
        logger.info(f"Generating {subject} teaching plan for: {problem}")
        
        # Step 1: Analyze problem
        cag_state = await self._analyze_problem(problem, subject)
        
        # Step 2: Retrieve concepts
        concepts = await self.kg.retrieve_concepts(
            cag_state["concepts"],
            grade_level=grade_level,
        )
        
        # Step 3: Generate steps
        steps = await self._generate_steps(
            problem,
            concepts,
            subject,
            student_learning_style or "visual",
        )
        
        # Step 4: Generate visualizations
        for step in steps:
            step.visualizations = await self._generate_visualizations(
                step,
                subject,
            )
        
        # Step 5: Create branching rules
        adaptive_rules = self._create_adaptive_rules(steps)
        
        return TeachingPlan(
            id=f"plan_{hash(problem)}",
            problem=problem,
            subject=subject,
            grade_level=grade_level,
            steps=steps,
            adaptive_rules=adaptive_rules,
        )
    
    async def evaluate_step(
        self,
        step: TeachingStep,
        student_response: str,
    ) -> dict:
        """
        Evaluate student's response to a step
        
        Returns:
            {
                "is_correct": bool,
                "feedback": str,
                "next_step_id": str,
                "hint": Optional[str],
            }
        """
        logger.info(f"Evaluating step {step.id}")
        
        # Use LLM to evaluate
        evaluation = await self.models.gemini.evaluate(
            question=step.question,
            student_answer=student_response,
            expected_answer=step.expected_answer,
        )
        
        if evaluation["is_correct"]:
            next_step = step.next_step_id
            feedback = evaluation.get("praise", "Great!")
        else:
            next_step = step.wrong_answer_next_step
            feedback = evaluation.get("hint", "Try again")
        
        return {
            "is_correct": evaluation["is_correct"],
            "feedback": feedback,
            "next_step_id": next_step,
            "confidence": evaluation.get("confidence", 0.0),
        }
    
    async def _analyze_problem(self, problem: str, subject: str) -> dict:
        """Use TRACECAG to analyze problem"""
        # Placeholder - would call actual TRACECAG
        return {
            "concepts": [],
            "difficulty": 3,
            "topics": [],
        }
    
    async def _generate_steps(
        self,
        problem: str,
        concepts: List[dict],
        subject: str,
        learning_style: str,
    ) -> List[TeachingStep]:
        """Generate multi-step solution using Socratic method"""
        steps = []
        
        # Step 1: Restate problem (confirm understanding)
        steps.append(TeachingStep(
            id="step_1",
            step_number=1,
            type=StepType.EXPLANATION,
            title="Understand the Problem",
            description=f"Let's analyze: {problem}",
            question=f"Do you understand what we need to find?",
            visualizations=[],
            learning_objective="Problem comprehension",
            difficulty=1,
            estimated_time_seconds=30,
        ))
        
        # Step 2-N: Guided solving
        # This would be subject-specific
        
        return steps
    
    async def _generate_visualizations(
        self,
        step: TeachingStep,
        subject: str,
    ) -> List[dict]:
        """
        Generate visual actions for a step
        
        Returns list of board actions like:
        - write_equation: "2x + 5 = 13"
        - write_text: "Subtract 5 from both sides"
        - show_graph: render a graph
        """
        actions = []
        
        # This is subject-specific
        if subject == "math":
            actions = await self._generate_math_visuals(step)
        elif subject == "physics":
            actions = await self._generate_physics_visuals(step)
        elif subject == "chemistry":
            actions = await self._generate_chemistry_visuals(step)
        
        return actions
    
    def _create_adaptive_rules(self, steps: List[TeachingStep]) -> dict:
        """Create branching rules for adaptive learning"""
        return {
            "if_struggling": "provide_hint",
            "if_advanced": "skip_to_harder",
            "if_misconception": "address_directly",
        }

# Usage in API route
@app.post("/api/teaching-plans")
async def create_teaching_plan(request: ProblemRequest):
    service = StepSequencingService(kg_service, model_gateway)
    
    plan = await service.generate_teaching_plan(
        problem=request.problem,
        subject=request.subject,
        grade_level=request.grade_level,
    )
    
    return plan
```

---

### Task 3: API Endpoints

**File**: `ai_service/api/routes/step_sequencing.py`

```python
from fastapi import APIRouter, HTTPException
from models.teaching_step import TeachingStep, TeachingPlan

router = APIRouter(prefix="/teaching", tags=["teaching"])

@router.post("/plans")
async def create_teaching_plan(request: CreatePlanRequest) -> TeachingPlan:
    """
    Generate multi-step teaching plan for a problem
    
    Request:
    {
        "problem": "Solve 2x + 5 = 13",
        "subject": "math",
        "grade_level": 10,
        "learning_style": "visual"
    }
    
    Response:
    {
        "id": "plan_123",
        "steps": [
            {
                "id": "step_1",
                "type": "explanation",
                "title": "Understand",
                "visualizations": [...]
            },
            ...
        ]
    }
    """
    # Implementation

@router.post("/steps/{step_id}/evaluate")
async def evaluate_step(step_id: str, response: StudentResponse) -> dict:
    """
    Evaluate student's response to a teaching step
    
    Returns:
    {
        "is_correct": true,
        "feedback": "Great! Now divide...",
        "next_step_id": "step_3"
    }
    """
    # Implementation

@router.get("/steps/{step_id}")
async def get_step(step_id: str) -> TeachingStep:
    """Get specific step details"""
    # Implementation
```

---

### Task 4: Flutter Models

**File**: `ai_tutor/lib/features/visual_tutor/domain/entities/teaching_step_entity.dart`

```dart
import 'package:equatable/equatable.dart';

enum TeachingStepType {
  explanation,
  visualization,
  question,
  feedback,
  hint,
  check,
}

/// Single step in a multi-step teaching plan
class TeachingStepEntity extends Equatable {
  const TeachingStepEntity({
    required this.id,
    required this.stepNumber,
    required this.type,
    required this.title,
    required this.description,
    required this.visualizations,
    this.question,
    this.expectedAnswer,
    this.nextStepId,
    this.wrongAnswerNextStepId,
    required this.learningObjective,
    required this.difficulty,
    required this.estimatedTimeSeconds,
  });

  /// Unique step identifier
  final String id;
  
  /// Sequential number (1, 2, 3, ...)
  final int stepNumber;
  
  /// Type of step (explanation, question, etc.)
  final TeachingStepType type;
  
  /// Step title
  final String title;
  
  /// Step description
  final String description;
  
  /// Visual actions to render on board
  final List<VisualTutorBoardActionEntity> visualizations;
  
  /// Question to ask student (if applicable)
  final String? question;
  
  /// Expected answer pattern
  final String? expectedAnswer;
  
  /// Next step if student answers correctly
  final String? nextStepId;
  
  /// Next step if student answers incorrectly
  final String? wrongAnswerNextStepId;
  
  /// Learning objective for this step
  final String learningObjective;
  
  /// Difficulty 1-5
  final int difficulty;
  
  /// Estimated time to complete (seconds)
  final int estimatedTimeSeconds;

  /// Check if step is complete
  bool get isComplete => false; // Will be set by UI

  /// Get next step based on correctness
  String? getNextStepId(bool wasCorrect) {
    return wasCorrect ? nextStepId : wrongAnswerNextStepId;
  }

  @override
  List<Object?> get props => [
    id,
    stepNumber,
    type,
    title,
    description,
    visualizations,
    question,
    expectedAnswer,
    nextStepId,
    wrongAnswerNextStepId,
    learningObjective,
    difficulty,
    estimatedTimeSeconds,
  ];
}

/// Complete teaching plan
class TeachingPlanEntity extends Equatable {
  const TeachingPlanEntity({
    required this.id,
    required this.problem,
    required this.subject,
    required this.gradeLLevel,
    required this.steps,
    this.adaptiveRules,
  });

  final String id;
  final String problem;
  final String subject; // "math", "physics", "chemistry"
  final int gradeLLevel; // 10-12
  final List<TeachingStepEntity> steps;
  final Map<String, dynamic>? adaptiveRules;

  /// Get step by ID
  TeachingStepEntity? getStepById(String id) {
    try {
      return steps.firstWhere((s) => s.id == id);
    } catch (e) {
      return null;
    }
  }

  /// Get first step
  TeachingStepEntity? get firstStep => steps.isNotEmpty ? steps.first : null;

  @override
  List<Object?> get props => [
    id,
    problem,
    subject,
    gradeLLevel,
    steps,
    adaptiveRules,
  ];
}
```

---

### Task 5: Flutter Provider/State Management

**File**: `ai_tutor/lib/features/visual_tutor/presentation/providers/teaching_step_provider.dart`

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// State for tracking current teaching session
class TeachingSessionState {
  final TeachingPlanEntity? plan;
  final String? currentStepId;
  final bool isLoading;
  final String? error;
  
  TeachingSessionState({
    this.plan,
    this.currentStepId,
    this.isLoading = false,
    this.error,
  });
  
  TeachingStepEntity? get currentStep => 
    plan?.getStepById(currentStepId ?? '');
  
  int get progressPercent {
    if (plan == null || plan!.steps.isEmpty) return 0;
    final currentIndex = plan!.steps
        .indexWhere((s) => s.id == currentStepId);
    return ((currentIndex + 1) / plan!.steps.length * 100).toInt();
  }
}

/// Provider for teaching session
final teachingSessionProvider = StateNotifierProvider<
  TeachingSessionNotifier,
  TeachingSessionState
>(
  (ref) => TeachingSessionNotifier(),
);

class TeachingSessionNotifier extends StateNotifier<TeachingSessionState> {
  TeachingSessionNotifier() : super(TeachingSessionState());
  
  /// Load teaching plan for a problem
  Future<void> loadPlan(String problem, String subject) async {
    state = state.copyWith(isLoading: true);
    
    try {
      final plan = await _fetchPlan(problem, subject);
      state = state.copyWith(
        plan: plan,
        currentStepId: plan.firstStep?.id,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        error: e.toString(),
        isLoading: false,
      );
    }
  }
  
  /// Move to next step
  Future<void> nextStep(bool wasCorrect) async {
    if (state.currentStep == null) return;
    
    final nextId = state.currentStep!.getNextStepId(wasCorrect);
    if (nextId != null) {
      state = state.copyWith(currentStepId: nextId);
    }
  }
  
  /// Evaluate student response
  Future<String?> evaluateResponse(String response) async {
    if (state.currentStep == null) return null;
    
    final evaluation = await _evaluateStep(
      state.currentStep!.id,
      response,
    );
    
    await nextStep(evaluation['is_correct']);
    return evaluation['feedback'];
  }
  
  Future<dynamic> _fetchPlan(String problem, String subject) async {
    // API call to backend
    throw UnimplementedError();
  }
  
  Future<Map<String, dynamic>> _evaluateStep(
    String stepId,
    String response,
  ) async {
    // API call to backend
    throw UnimplementedError();
  }
}
```

---

### Task 6: Flutter UI for Step Sequencing

**File**: `ai_tutor/lib/features/visual_tutor/presentation/pages/step_sequencing_page.dart`

```dart
class StepSequencingPage extends ConsumerWidget {
  const StepSequencingPage({
    required this.problem,
    required this.subject,
  });
  
  final String problem;
  final String subject;
  
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final sessionState = ref.watch(teachingSessionProvider);
    
    return Scaffold(
      appBar: AppBar(
        title: Text('Learning: ${sessionState.plan?.subject}'),
        actions: [
          Padding(
            padding: EdgeInsets.all(16),
            child: Center(
              child: Text(
                'Step ${sessionState.currentStep?.stepNumber} '
                'of ${sessionState.plan?.steps.length}',
              ),
            ),
          ),
        ],
      ),
      body: sessionState.isLoading
          ? Center(child: CircularProgressIndicator())
          : sessionState.error != null
              ? Center(child: Text('Error: ${sessionState.error}'))
              : _buildStepContent(context, ref, sessionState),
    );
  }
  
  Widget _buildStepContent(
    BuildContext context,
    WidgetRef ref,
    TeachingSessionState state,
  ) {
    final step = state.currentStep;
    if (step == null) return SizedBox.shrink();
    
    return SingleChildScrollView(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Progress bar
            LinearProgressIndicator(
              value: state.progressPercent / 100,
            ),
            SizedBox(height: 24),
            
            // Step title
            Text(
              step.title,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            SizedBox(height: 8),
            
            // Step description
            Text(step.description),
            SizedBox(height: 24),
            
            // Visual board
            SizedBox(
              height: 400,
              child: RichMediaCanvas(
                actions: step.visualizations,
              ),
            ),
            SizedBox(height: 24),
            
            // Student interaction (if question)
            if (step.question != null)
              _buildInteraction(context, ref, step),
          ],
        ),
      ),
    );
  }
  
  Widget _buildInteraction(
    BuildContext context,
    WidgetRef ref,
    TeachingStepEntity step,
  ) {
    final controller = TextEditingController();
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          step.question!,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        SizedBox(height: 12),
        TextField(
          controller: controller,
          decoration: InputDecoration(
            hintText: 'Your answer...',
            border: OutlineInputBorder(),
          ),
        ),
        SizedBox(height: 12),
        ElevatedButton(
          onPressed: () async {
            final feedback = await ref
                .read(teachingSessionProvider.notifier)
                .evaluateResponse(controller.text);
            
            if (feedback != null) {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text(feedback)),
              );
            }
          },
          child: Text('Check Answer'),
        ),
      ],
    );
  }
}
```

---

## 🎓 The Socratic Method Pattern

**Idea**: Guide student to answer, not give answer.

### Pattern 1: Guided Problem Solving

```
Step 1: "What operation should we do first?"
  [Wait for student response]
  
Step 2a (if correct): "Good! Now apply it"
Step 2b (if wrong): "Hint: Look at the problem again"
```

### Pattern 2: Concept Building

```
Step 1: Show simple example
Step 2: Ask what changed
Step 3: Show harder example
Step 4: Ask student to predict
```

### Pattern 3: Misconception Detection

```
Step 1: Ask question
Step 2a (if correct): Continue
Step 2b (if shows misconception): 
  - Address misconception
  - Show counterexample
  - Reteach concept
  - Go back to Step 1
```

---

## 🧪 Testing Phase 0.3

### Unit Tests

```dart
test('TeachingPlan creates correct steps', () {
  final plan = TeachingPlanEntity(
    id: 'test',
    problem: 'Solve 2x + 5 = 13',
    subject: 'math',
    gradeLLevel: 10,
    steps: [
      TeachingStepEntity(id: '1', stepNumber: 1, ...),
      TeachingStepEntity(id: '2', stepNumber: 2, ...),
    ],
  );
  
  expect(plan.steps.length, 2);
  expect(plan.firstStep?.id, '1');
});

test('Step branching works correctly', () {
  final step = TeachingStepEntity(
    id: '1',
    nextStepId: '2',
    wrongAnswerNextStepId: '1b',
    ...
  );
  
  expect(step.getNextStepId(true), '2');
  expect(step.getNextStepId(false), '1b');
});
```

### Integration Tests

```dart
test('Full teaching session flow', () async {
  // 1. Load plan
  // 2. Render first step
  // 3. Student answers
  // 4. Evaluate and move to next
  // 5. Verify progression
});
```

---

## 📊 Success Criteria for Phase 0.3

| Criterion | Status |
|-----------|--------|
| TeachingStep models complete | ⏳ |
| Backend service implemented | ⏳ |
| API endpoints working | ⏳ |
| Flutter providers set up | ⏳ |
| UI page complete | ⏳ |
| Socratic branching working | ⏳ |
| Tests passing | ⏳ |

---

## 🚀 Implementation Order

1. **Backend Models** (1 hour) - Python dataclasses
2. **Backend Service** (2 hours) - Step generation logic
3. **API Endpoints** (1 hour) - Route definitions
4. **Flutter Models** (1 hour) - Dart entities
5. **Flutter State** (1.5 hours) - Provider/Notifier
6. **Flutter UI** (2 hours) - Pages and widgets
7. **Testing** (2 hours) - Unit and integration tests
8. **Integration** (1 hour) - Connect front/back

**Total**: 11.5 hours

---

## 🎯 Next: Phase 1 (Math Teaching)

Once Phase 0.3 is complete, we can start Phase 1 with:
- Problem bank (15-20 algebra/geometry problems)
- Step generation templates for each problem type
- Adaptive rules based on student performance
- Testing on real students

---

**Ready to implement Phase 0.3?** Follow the task order above, test each component, then integrate! 🚀
