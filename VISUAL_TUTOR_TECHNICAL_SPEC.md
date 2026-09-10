# Visual Tutor: Technical Implementation Specification

## 1. Teaching Step Data Model

### 1.1 Backend Model Definition
**File**: `ai-service/api/models/visual_tutor_step.py`

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime


class StudentTask(BaseModel):
    """Represents a task that requires student response before advancing."""
    
    type: Literal[
        "free_response",
        "multiple_choice", 
        "fill_blank",
        "verification",
        "matching"
    ] = Field(..., description="Type of interaction")
    
    prompt: str = Field(..., description="Question/prompt for student")
    
    expected_answer_locked: bool = Field(
        default=True,
        description="If true, AI won't reveal answer until student tries"
    )
    
    validation_strategy: Optional[str] = Field(
        default=None,
        description="Validation: 'exact_match', 'fuzzy_match', 'symbolic', 'numeric', 'semantic'"
    )
    
    choices: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="For multiple_choice: [{'id': 'a', 'label': 'Option 1', 'value': 'opt1'}, ...]"
    )
    
    hint: Optional[str] = Field(
        default=None,
        description="Hint if student asks or makes attempt"
    )
    
    expected_answer: Optional[str] = Field(
        default=None,
        description="Expected answer (for validation after student submits)"
    )
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class BoardActionReference(BaseModel):
    """Minimal board action for teaching steps (full version in VisualTutorBoardAction)."""
    
    id: str
    type: str
    sequence_index: int
    duration_ms: int = 0
    
    # Positioning (now can be null - will be calculated dynamically)
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    
    # Content
    text: Optional[str] = None
    latex: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingStep(BaseModel):
    """One atomic teaching step in a multi-step sequence."""
    
    # Identity
    step_id: str = Field(..., description="Unique ID for this step")
    step_number: int = Field(..., description="Sequential position (0-indexed)")
    
    # Learning
    learning_objective: str = Field(
        ..., 
        description="What concept/skill does this step teach?"
    )
    
    concepts: List[str] = Field(
        default_factory=list,
        description="Knowledge graph concept IDs touched in this step"
    )
    
    prerequisites: List[str] = Field(
        default_factory=list,
        description="Concepts that should be understood before this step"
    )
    
    # Visual rendering
    board_actions: List[BoardActionReference] = Field(
        ...,
        description="Actions teacher writes/draws (2-4 typically, not full answer)"
    )
    
    # Speech/narration
    spoken_text: str = Field(
        ...,
        description="What the tutor says while drawing (conversational)"
    )
    
    # Student engagement
    student_task: Optional[StudentTask] = Field(
        default=None,
        description="Task to check understanding (required for non-final steps)"
    )
    
    # Branching logic
    on_correct: str = Field(
        default="next_step",
        description="What to do if student answers correctly: 'next_step', 'final_answer', etc."
    )
    
    on_incorrect: str = Field(
        default="reteach",
        description="What to do if student answers incorrectly: 'reteach', 'hint', 'simpler', etc."
    )
    
    on_no_response: str = Field(
        default="hint",
        description="What to do if student doesn't respond after timeout"
    )
    
    # Hints
    hint_progression: List[str] = Field(
        default_factory=list,
        description="Escalating hints if student is stuck"
    )
    
    # Mastery estimation
    is_final_step: bool = Field(
        default=False,
        description="Is this the final answer reveal?"
    )
    
    skip_if_mastery_above: Optional[float] = Field(
        default=None,
        description="Skip this step if student mastery > threshold (0-1)"
    )
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingSequence(BaseModel):
    """Complete multi-step teaching plan for a problem."""
    
    sequence_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique ID for this sequence"
    )
    
    problem_instance_id: str = Field(
        ...,
        description="Which problem is this sequence solving?"
    )
    
    problem_text: str = Field(..., description="Problem statement")
    
    # Steps
    steps: List[TeachingStep] = Field(
        ...,
        description="All steps for this sequence"
    )
    
    current_step_index: int = Field(
        default=0,
        description="Which step is client currently on?"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    generation_model: str = Field(
        default="gpt-4-turbo",
        description="Which LLM generated this sequence"
    )
    
    curriculum_sources: List[str] = Field(
        default_factory=list,
        description="Which curriculum chunks were used"
    )
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StudentStepEvaluation(BaseModel):
    """Evaluation of student's response to a step."""
    
    step_id: str
    student_response: str
    
    # Evaluation result
    is_correct: bool
    confidence: float = Field(..., ge=0, le=1)
    
    # Diagnostics
    misconceptions: List[str] = Field(
        default_factory=list,
        description="What conceptual errors did we detect?"
    )
    
    validation_method: str = Field(
        default="llm",
        description="How we validated: 'exact_match', 'llm', 'symbolic', etc."
    )
    
    feedback: str = Field(
        default="",
        description="Feedback to show student"
    )
    
    # Next action
    recommended_action: Literal[
        "next_step",
        "reteach",
        "hint",
        "simpler_explanation",
        "skip_step"
    ] = Field(
        default="next_step"
    )
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## 2. API Request/Response Contracts

### 2.1 New Route: `/api/v1/visual_tutor/turn_step`

**Purpose**: Process one step of teaching, wait for student, generate next step.

```python
# REQUEST
class VisualTutorStepTurnRequest(BaseModel):
    """A turn in step-based teaching."""
    
    # Session
    user_id: str
    session_id: str
    problem_instance_id: str
    
    # Step context
    step_id: str = Field(..., description="Which step is student responding to?")
    current_step_index: int
    
    # Student input (one of these should be set)
    message: Optional[str] = Field(
        default=None, 
        description="Text response to student task"
    )
    
    action: Literal[
        "submit_step_response",
        "request_hint", 
        "skip_step",
        "go_back"
    ] = "submit_step_response"
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


# RESPONSE
class VisualTutorStepTurnResponse(BaseModel):
    """Response with next step to execute."""
    
    # IDs
    session_id: str
    turn_id: str
    sequence_id: str
    
    # Previous step evaluation (if student just answered)
    previous_step_evaluation: Optional[StudentStepEvaluation] = None
    
    # Next step to render
    current_step: TeachingStep
    
    # Full sequence (for client reference)
    teaching_sequence: Optional[TeachingSequence] = None
    
    # Streaming hint
    board_actions: List[Dict[str, Any]] = Field(
        ...,
        description="Board actions from current step (for SSE streaming)"
    )
    
    spoken_text: str
    
    student_task: Optional[StudentTask] = None
    
    # UI hints
    is_final_step: bool = False
    total_steps: int = 0
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

### 2.2 Updated SSE Stream Format

Current format works; add new event types:

```python
_STREAM_EVENT_TYPES = {
    "status",
    "speech_ready", 
    "board_action",
    "board_patch",
    "turn_complete",
    "error",
    # NEW:
    "step_evaluation",
    "step_complete",
    "reteach_inserted",
}

# Example: step_evaluation event
{
    "event_id": "evt_123",
    "event_type": "step_evaluation",
    "stream_id": "stream_xyz",
    "session_id": "sess_abc",
    "turn_id": "turn_def",
    "sequence": 5,
    "timestamp": "2026-08-26T12:00:00Z",
    "data": {
        "step_id": "step_1",
        "is_correct": true,
        "feedback": "Great! You identified the constant correctly.",
        "recommended_action": "next_step",
        "confidence": 0.92
    }
}
```

---

## 3. Frontend: Step-Based UI Components

### 3.1 Position Calculator Service
**File**: `ai_tutor/lib/features/visual_tutor/presentation/services/board_position_calculator.dart`

```dart
/// Calculates dynamic positions for board elements.
/// 
/// Rules:
/// - Start at (40, 48) for first element
/// - Top-to-bottom progression for new steps (Y += prev_height + gap)
/// - Left-to-right for same-step items (X += prev_width + gap)
/// - Wrap to next line if X exceeds column width
/// - No overlap, visual hierarchy maintained

class BoardPositionCalculator {
  static const double topMargin = 48.0;
  static const double leftMargin = 40.0;
  static const double elementGap = 24.0;
  static const double columnWidth = 600.0;
  static const double rowHeight = 64.0;

  /// Calculates (x, y) for next board element.
  ///
  /// [placedElements]: All elements already rendered.
  /// [elementType]: Type of element ('text', 'equation', 'shape', etc.)
  /// [elementHeight]: Expected height of new element.
  /// [isNewStep]: Is this element starting a new step? (forces new row)
  /// [preferredWidth]: Desired width (defaults per type).
  static Offset calculatePosition(
    List<VisualTutorBoardActionEntity> placedElements, {
    required String elementType,
    required double elementHeight,
    required bool isNewStep,
    double? preferredWidth,
  }) {
    // Default width by element type
    final width = preferredWidth ?? _defaultWidth(elementType);

    // Empty board = start at top-left
    if (placedElements.isEmpty) {
      return Offset(leftMargin, topMargin);
    }

    final lastElement = placedElements.last;
    final lastX = lastElement.x ?? leftMargin;
    final lastY = lastElement.y ?? topMargin;
    final lastWidth = lastElement.width ?? _defaultWidth(lastElement.type);
    final lastHeight = lastElement.height ?? rowHeight;
    final lastRight = lastX + lastWidth;
    final lastBottom = lastY + lastHeight;

    // NEW STEP: Force new row below previous
    if (isNewStep) {
      return Offset(leftMargin, lastBottom + elementGap);
    }

    // SAME STEP: Try to place right of last element
    final nextX = lastRight + elementGap;
    final wouldExceedWidth = nextX + width > leftMargin + columnWidth;

    if (wouldExceedWidth) {
      // Wrap to next line at same Y as last element + height + gap
      return Offset(leftMargin, lastBottom + elementGap);
    } else {
      // Continue on same row, vertically aligned
      return Offset(nextX, lastY);
    }
  }

  /// Default width for element type.
  static double _defaultWidth(String elementType) {
    return switch (elementType) {
      'write_text' => 280,
      'write_equation' => 240,
      'highlight' => 200,
      'circle' => 100,
      'draw_arrow' => 150,
      'student_task' => 320,
      _ => 260,
    };
  }
}
```

### 3.2 Step Board State Manager
**File**: `ai_tutor/lib/features/visual_tutor/presentation/providers/step_board_provider.dart`

```dart
class StepBoardState {
  const StepBoardState({
    required this.teachingSequence,
    required this.currentStepIndex,
    required this.renderedActions,
    this.evaluation,
    this.isEvaluating = false,
    this.error,
  });

  final VisualTutorTeachingSequenceEntity teachingSequence;
  final int currentStepIndex;
  final List<VisualTutorBoardActionEntity> renderedActions;
  final StudentStepEvaluationEntity? evaluation;
  final bool isEvaluating;
  final String? error;

  StepBoardState copyWith({
    VisualTutorTeachingSequenceEntity? teachingSequence,
    int? currentStepIndex,
    List<VisualTutorBoardActionEntity>? renderedActions,
    StudentStepEvaluationEntity? evaluation,
    bool? isEvaluating,
    String? error,
  }) {
    return StepBoardState(
      teachingSequence: teachingSequence ?? this.teachingSequence,
      currentStepIndex: currentStepIndex ?? this.currentStepIndex,
      renderedActions: renderedActions ?? this.renderedActions,
      evaluation: evaluation ?? this.evaluation,
      isEvaluating: isEvaluating ?? this.isEvaluating,
      error: error ?? this.error,
    );
  }

  VisualTutorTeachingStepEntity? get currentStep {
    if (currentStepIndex >= 0 && 
        currentStepIndex < teachingSequence.steps.length) {
      return teachingSequence.steps[currentStepIndex];
    }
    return null;
  }

  double get progressPercent =>
      (currentStepIndex + 1) / teachingSequence.steps.length;

  bool get hasNextStep =>
      currentStepIndex < teachingSequence.steps.length - 1;

  bool get isFinalStep =>
      currentStepIndex == teachingSequence.steps.length - 1;
}

class StepBoardNotifier extends StateNotifier<StepBoardState> {
  StepBoardNotifier({
    required this.visualTutorRepository,
    required this.initialSequence,
  }) : super(StepBoardState(
    teachingSequence: initialSequence,
    currentStepIndex: 0,
    renderedActions: [],
  )) {
    _initializeRenderableActions();
  }

  final VisualTutorRepository visualTutorRepository;
  final VisualTutorTeachingSequenceEntity initialSequence;

  void _initializeRenderableActions() {
    final current = state.currentStep;
    if (current != null) {
      final actions = current.boardActions
          .asMap()
          .entries
          .map((entry) {
            final action = entry.value;
            // Calculate dynamic position if null
            final position = BoardPositionCalculator.calculatePosition(
              state.renderedActions,
              elementType: action.type,
              elementHeight: action.height ?? 64,
              isNewStep: entry.key == 0,
            );
            return action.copyWith(
              x: action.x ?? position.dx,
              y: action.y ?? position.dy,
            );
          })
          .toList();

      state = state.copyWith(renderedActions: actions);
    }
  }

  Future<void> submitStepResponse(String response) async {
    state = state.copyWith(isEvaluating: true, error: null);

    try {
      final result = await visualTutorRepository.submitStepResponse(
        sessionId: state.teachingSequence.problem_instance_id,
        stepId: state.currentStep?.step_id ?? '',
        response: response,
      );

      // Update with evaluation result
      state = state.copyWith(
        evaluation: result.evaluation,
        isEvaluating: false,
      );

      // Recommended action: advance or reteach
      if (result.evaluation?.recommendedAction == 'next_step') {
        await advanceToNextStep();
      } else if (result.evaluation?.recommendedAction == 'reteach') {
        // Insert reteach step at current position
        // TODO: Implement reteach insertion
      }
    } catch (e) {
      state = state.copyWith(
        error: e.toString(),
        isEvaluating: false,
      );
    }
  }

  Future<void> advanceToNextStep() async {
    if (!state.hasNextStep) return;

    // In future: fetch next step from backend if available
    state = state.copyWith(
      currentStepIndex: state.currentStepIndex + 1,
      evaluation: null,
      renderedActions: [],
    );

    _initializeRenderableActions();
  }

  Future<void> requestHint() async {
    final currentStep = state.currentStep;
    if (currentStep?.student_task?.hint != null) {
      // Show hint in UI
      // TODO: Implement hint display
    }
  }
}

final stepBoardProvider = StateNotifierProvider<
    StepBoardNotifier,
    StepBoardState
>((ref) {
  throw UnimplementedError(
    'stepBoardProvider must be overridden with initialize()',
  );
});
```

### 3.3 Step Interaction Widget
**File**: `ai_tutor/lib/features/visual_tutor/presentation/widgets/step_interaction_widget.dart`

```dart
class StepInteractionWidget extends StatefulWidget {
  const StepInteractionWidget({
    super.key,
    required this.studentTask,
    required this.onSubmit,
    required this.onHint,
    this.isSubmitting = false,
    this.feedback,
    this.evaluation,
  });

  final VisualTutorStudentTaskEntity studentTask;
  final ValueChanged<String> onSubmit;
  final VoidCallback onHint;
  final bool isSubmitting;
  final String? feedback;
  final StudentStepEvaluationEntity? evaluation;

  @override
  State<StepInteractionWidget> createState() => _StepInteractionWidgetState();
}

class _StepInteractionWidgetState extends State<StepInteractionWidget> {
  late final TextEditingController _controller;
  late final FocusNode _focusNode;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
    _focusNode = FocusNode();
    // Auto-focus after board draws
    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted) _focusNode.requestFocus();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Question/Prompt
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Text(
            widget.studentTask.prompt,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ),

        // Input widget based on task type
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: switch (widget.studentTask.type) {
            'multiple_choice' => _buildMultipleChoice(),
            'free_response' => _buildFreeResponse(),
            'fill_blank' => _buildFillBlank(),
            _ => const SizedBox.shrink(),
          },
        ),

        // Feedback (after submission)
        if (widget.feedback != null) ...[
          const SizedBox(height: 12),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: widget.evaluation?.is_correct ?? false
                    ? Colors.green.shade50
                    : Colors.orange.shade50,
                border: Border.all(
                  color: widget.evaluation?.is_correct ?? false
                      ? Colors.green.shade300
                      : Colors.orange.shade300,
                ),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                children: [
                  Icon(
                    widget.evaluation?.is_correct ?? false
                        ? Icons.check_circle
                        : Icons.info,
                    color: widget.evaluation?.is_correct ?? false
                        ? Colors.green
                        : Colors.orange,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      widget.feedback!,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],

        // Buttons
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Expanded(
                child: FilledButton(
                  onPressed: widget.isSubmitting ? null : _handleSubmit,
                  child: widget.isSubmitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            valueColor:
                                AlwaysStoppedAnimation(Colors.white),
                          ),
                        )
                      : const Text('Submit'),
                ),
              ),
              if (widget.studentTask.hint != null) ...[
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: widget.onHint,
                  icon: const Icon(Icons.lightbulb_outline),
                  label: const Text('Hint'),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildFreeResponse() {
    return TextField(
      controller: _controller,
      focusNode: _focusNode,
      decoration: InputDecoration(
        hintText: 'Your answer...',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
        contentPadding: const EdgeInsets.all(12),
      ),
      minLines: 2,
      maxLines: 4,
      enabled: !widget.isSubmitting,
    );
  }

  Widget _buildMultipleChoice() {
    final choices = widget.studentTask.choices ?? [];
    return Column(
      children: [
        for (final choice in choices)
          RadioListTile<String>(
            title: Text(choice.label),
            value: choice.value,
            groupValue: _controller.text,
            onChanged: widget.isSubmitting
                ? null
                : (value) {
                  setState(() => _controller.text = value ?? '');
                },
          ),
      ],
    );
  }

  Widget _buildFillBlank() {
    return TextField(
      controller: _controller,
      focusNode: _focusNode,
      decoration: InputDecoration(
        hintText: 'Fill in the blank',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(8),
        ),
      ),
      enabled: !widget.isSubmitting,
    );
  }

  Future<void> _handleSubmit() async {
    if (_controller.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please provide a response')),
      );
      return;
    }

    widget.onSubmit(_controller.text.trim());
  }
}
```

---

## 4. LLM Prompts

### 4.1 System Prompt: First Step
**File**: `ai-service/api/services/visual_tutor/prompts.py`

```python
VISUAL_TUTOR_FIRST_STEP_SYSTEM_PROMPT = """
You are an expert mathematics tutor designing a SINGLE STEP of a multi-step lesson.
Your goal is to make the student think deeply, not to give them the answer.

## Guidelines

1. **One Step Only**: Generate ONLY the first step of the solution.
   Do NOT solve the entire problem or give the final answer.

2. **Board Actions** (2-4 actions):
   - Start simple: identify what's given, write the problem
   - Make visually clear: use highlighting, circling, underlining
   - Be concise: each action should be one thought
   
   Example: For "solve 2x + 5 = 13"
   - Action 1: Write the equation
   - Action 2: Circle the constant (5)
   - Action 3: Write a guiding question

3. **Spoken Text**:
   - Conversational, not robotic
   - Narrate what you're drawing in real-time
   - Ask the student a question, don't tell them the answer
   
   Bad: "We subtract 5 from both sides to get 2x = 8."
   Good: "I'm circling the 5. What do you think we should do next with this constant?"

4. **Student Task**:
   - REQUIRED: Ask the student a question to check understanding
   - The question should be answerable after this step
   - Don't ask for the full solution, just the next idea
   
   Examples:
   - "What number needs to go away first?"
   - "Which term doesn't have a variable?"
   - "What operation is being applied to x?"

5. **Concepts Touched**:
   - Identify 1-2 key concepts this step teaches
   - Don't mention every concept, focus on the primary one

## Output Format

{
  "step_id": "step_1",
  "step_number": 0,
  "learning_objective": "Identify given information in the problem",
  "concepts": ["equation_identification", "constant_recognition"],
  
  "board_actions": [
    {
      "id": "action_1",
      "type": "write_text",
      "text": "2x + 5 = 13",
      "duration_ms": 1000
    },
    {
      "id": "action_2",
      "type": "highlight",
      "duration_ms": 800
    },
    {
      "id": "action_3",
      "type": "write_text",
      "text": "What do we know?",
      "duration_ms": 600
    }
  ],
  
  "spoken_text": "Here's our equation. I'm highlighting 5—the number being added. What's something we need to find in this problem?",
  
  "student_task": {
    "type": "free_response",
    "prompt": "What is being added to 2x?",
    "expected_answer": "5",
    "validation_strategy": "exact_match",
    "hint": "Look at the equation: 2x + ? = 13"
  },
  
  "on_correct": "next_step",
  "on_incorrect": "reteach"
}

## Important

- X, Y positioning will be calculated dynamically by the client.
  You should NOT include x/y in board_actions.
- Keep board_actions brief (2-4 maximum)
- Prioritize student engagement over content coverage
- Never jump ahead to advanced steps
- Always pair visual actions with a question for the student
"""
```

### 4.2 System Prompt: Next Step (After Student Response)
**File**: `ai-service/api/services/visual_tutor/prompts.py`

```python
VISUAL_TUTOR_NEXT_STEP_SYSTEM_PROMPT = """
You are an expert mathematics tutor designing the NEXT STEP in a multi-step lesson.

## Context
- Student just answered: {student_response}
- That answer was CORRECT (confidence: {confidence})
- Previous step's objective: {previous_objective}
- Student is now ready for: the next logical concept

## Guidelines

1. **Progress Logically**: Move to the next natural step, building on what the student just understood.
   
2. **Build Momentum**: The student got the last part right—show them they're making progress.

3. **Keep the Pattern**: Use similar visual patterns (highlighting, circling, writing equations) 
   to maintain consistency.

4. **Stay Focused**: Introduce ONE new concept/step, not multiple.

5. **Dialogue**: Continue the conversation style from the first step.

## Output Format
[Same as VISUAL_TUTOR_FIRST_STEP_SYSTEM_PROMPT]

## Example: Linear Equation Progression

Step 1: Identify the constant (DONE ✓)
Step 2: Subtract constant from both sides
Step 3: Divide both sides by coefficient
Step 4: Check the answer (optional final step)

Generate Step 2 now.
"""
```

---

## 5. Database Schema Updates

### 5.1 Session Metadata Structure
**File**: `ai-service/api/models/visual_tutor.py`

```python
class VisualTutorSession(Document):
    # ... existing fields ...
    
    # NEW: Teaching sequence tracking
    teaching_sequence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Current teaching sequence (all steps + current index)"
    )
    
    sequence_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="All teaching sequences for this session (for replay)"
    )
    
    step_evaluations: List[StudentStepEvaluation] = Field(
        default_factory=list,
        description="Student's performance on each step"
    )

    class Settings:
        name = "visual_tutor_sessions"
```

---

## 6. Integration Checklist

- [ ] Create `visual_tutor_step.py` models
- [ ] Update `orchestrator.py` to use step-by-step flow
- [ ] Update route `/api/v1/visual_tutor/turn` to accept step context
- [ ] Create new route `/api/v1/visual_tutor/step_turn` 
- [ ] Create LLM prompt templates
- [ ] Implement `evaluate_student_response()` service
- [ ] Create Flutter position calculator
- [ ] Create Flutter step state provider
- [ ] Create Flutter step interaction widget
- [ ] Update main visual tutor screen to use new components
- [ ] Add unit tests for position calculator
- [ ] Add integration tests for step flow
- [ ] Performance test: LLM response time per step (<2s target)

---

