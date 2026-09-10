# Visual Tutor: Quick Start Implementation

This guide provides step-by-step code examples to begin implementing the step-by-step teaching architecture.

---

## Phase 1: Bug Fix - Rendering Visibility (Day 1)

### Fix 1.1: Add Debug Logging to Board Rendering

**File**: `ai_tutor/lib/features/visual_tutor/presentation/widgets/live_teaching_board.dart`

Replace the `_renderableActions()` method:

```dart
List<VisualTutorBoardActionEntity> _renderableActions() {
  final all = widget.actions;
  
  debugPrint(
    '=== BOARD RENDERING DEBUG ===\n'
    'Total actions: ${all.length}\n'
    'finalAnswerLocked: ${widget.finalAnswerLocked}\n'
    'Actions:',
  );

  final renderableActions = all
      .where((action) {
        final shouldRender = isRenderableBoardAction(
          action,
          finalAnswerLocked: widget.finalAnswerLocked,
        );
        
        if (!shouldRender) {
          debugPrint(
            '❌ FILTERED OUT: ${action.id}\n'
            '   type: ${action.type}\n'
            '   hidden: ${action.hidden}\n'
            '   locked: ${action.locked}\n'
            '   metadata.faded: ${action.metadata['faded']}\n'
            '   revealPolicy: ${action.revealPolicy}',
          );
        } else {
          debugPrint(
            '✅ RENDERED: ${action.id}\n'
            '   type: ${action.type}\n'
            '   pos: (${action.x}, ${action.y}))',
          );
        }
        
        return shouldRender;
      })
      .toList()
    ..sort((a, b) => a.sequenceIndex.compareTo(b.sequenceIndex));

  debugPrint(
    'SUMMARY: ${renderableActions.length}/${all.length} actions rendered\n'
    '=============================\n',
  );

  return renderableActions.length > LiveTeachingBoard._maxRenderedActions
      ? renderableActions.sublist(
          renderableActions.length - LiveTeachingBoard._maxRenderedActions,
        )
      : renderableActions;
}
```

**Test**:
1. Run the app in debug mode
2. Create a visual tutor session
3. Watch console output
4. Look for filtered actions that shouldn't be filtered

---

### Fix 1.2: Review and Relax Reveal Policies

**File**: Check `isRenderableBoardAction()` in the same file

Look for the function definition and review conditions. The issue is likely:

```dart
// CURRENT (too restrictive):
bool shouldShow = !action.hidden && 
                 (!action.locked || widget.finalAnswerLocked);

// BETTER (during teaching phase):
bool shouldShow = !action.hidden && 
                 (!action.locked || !widget.finalAnswerLocked);
```

Find the actual implementation and verify the logic. Add a comment explaining when things should be hidden.

---

## Phase 1: Dynamic Positioning (Day 2-3)

### Create Position Calculator

**File**: `ai_tutor/lib/features/visual_tutor/presentation/services/board_position_calculator.dart` (NEW)

```dart
import 'package:flutter/material.dart';

/// Intelligently calculates positions for board elements to simulate
/// a teacher drawing top-to-bottom, left-to-right.
class BoardPositionCalculator {
  static const double topMargin = 48.0;
  static const double leftMargin = 40.0;
  static const double elementGap = 20.0;
  static const double maxColumnWidth = 620.0;

  /// Calculates next position for a board element.
  /// 
  /// Returns an Offset (x, y) for the new element.
  /// 
  /// Strategy:
  /// 1. If empty board → top-left
  /// 2. If new step (flag=true) → new row below
  /// 3. If same step → try to place right (inline)
  /// 4. If inline would overflow → wrap to next row
  static Offset calculatePosition({
    required List<PlacedElement> placedElements,
    required String elementType,
    required double elementHeight,
    required bool isNewStep,
    double? preferredWidth,
  }) {
    final width = preferredWidth ?? _defaultWidth(elementType);

    // Empty board
    if (placedElements.isEmpty) {
      return Offset(leftMargin, topMargin);
    }

    // Get bounds of all placed elements
    double maxBottom = topMargin;
    for (final element in placedElements) {
      final bottom = element.y + element.height;
      if (bottom > maxBottom) maxBottom = bottom;
    }

    // New step = start new row
    if (isNewStep) {
      return Offset(leftMargin, maxBottom + elementGap);
    }

    // Same step = try to place to the right
    final lastElement = placedElements.last;
    final nextX = lastElement.x + lastElement.width + elementGap;
    final wouldExceed = nextX + width > leftMargin + maxColumnWidth;

    if (wouldExceed) {
      // Wrap to next row
      return Offset(leftMargin, maxBottom + elementGap);
    } else {
      // Place inline, vertically aligned with last element
      return Offset(nextX, lastElement.y);
    }
  }

  /// Default width by element type (in logical units)
  static double _defaultWidth(String elementType) {
    return switch (elementType) {
      'write_text' => 280,
      'write_equation' => 240,
      'highlight' => 200,
      'circle' => 80,
      'draw_arrow' => 140,
      'draw_rectangle' => 150,
      'draw_point' => 60,
      'student_task' => 320,
      _ => 260,
    };
  }
}

/// Represents a placed element for position calculation
class PlacedElement {
  PlacedElement({
    required this.x,
    required this.y,
    required this.width,
    required this.height,
  });

  final double x;
  final double y;
  final double width;
  final double height;
}
```

### Integrate Position Calculator into Board Renderer

**File**: `ai_tutor/lib/features/visual_tutor/presentation/widgets/board_element_renderer.dart`

Find the `build()` method and update position calculation:

```dart
@override
Widget build(BuildContext context) {
  if (action.hidden) return const SizedBox.shrink();
  
  final effectiveFaded = faded || action.metadata['faded'] == true;

  // UPDATED: Use provided position OR calculate
  final left = action.x ?? 
      _calculateDynamicPosition(context).dx * scale;
  final top = action.y ??
      _calculateDynamicPosition(context).dy;
  
  final width = (action.width ?? 260) * scale;
  final height = action.height ?? 42;

  // ... rest of build method
}

Offset _calculateDynamicPosition(BuildContext context) {
  // Get all previously rendered actions from ancestor
  // This requires passing them via context or InheritedWidget
  // For now, return default if not available
  return const Offset(40, 48);
}
```

**Better approach**: Pass placed actions to renderer:

```dart
class BoardElementRenderer extends StatelessWidget {
  const BoardElementRenderer({
    super.key,
    required this.action,
    required this.placedActions,  // NEW
    this.scale = 1,
    this.faded = false,
    // ... other params
  });

  final VisualTutorBoardActionEntity action;
  final List<VisualTutorBoardActionEntity> placedActions;  // NEW
  
  @override
  Widget build(BuildContext context) {
    if (action.hidden) return const SizedBox.shrink();

    // Calculate position based on placed actions
    final position = action.x == null || action.y == null
        ? BoardPositionCalculator.calculatePosition(
            placedElements: placedActions
                .map((a) => PlacedElement(
                  x: a.x ?? 40,
                  y: a.y ?? 48,
                  width: a.width ?? 260,
                  height: a.height ?? 42,
                ))
                .toList(),
            elementType: action.type,
            elementHeight: action.height ?? 42,
            isNewStep: _isNewStep(action),
            preferredWidth: action.width,
          )
        : Offset(action.x ?? 40, action.y ?? 48);

    final left = position.dx * scale;
    final top = position.dy;
    final width = (action.width ?? 260) * scale;
    final height = action.height ?? 42;

    // ... rest of widget tree
  }

  bool _isNewStep(VisualTutorBoardActionEntity action) {
    // Check if this is the first action of its step
    // or if it's marked as starting a new section
    return action.sequenceIndex == 0 ||
        action.metadata['isNewStep'] == true;
  }
}
```

Then update `LiveTeachingBoard` to pass placed actions:

```dart
// In LiveTeachingBoard.build():
Stack(
  children: [
    for (int i = 0; i < boundedActions.length; i++)
      BoardElementRenderer(
        key: Key(boundedActions[i].id),
        action: boundedActions[i],
        placedActions: boundedActions.sublist(0, i),  // NEW
        // ... other params
      ),
  ],
)
```

---

## Phase 2: Backend Models (Day 4)

### Create Teaching Step Models

**File**: `ai-service/api/models/visual_tutor_step.py` (NEW)

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
import uuid


class StudentTask(BaseModel):
    """Task that requires student response."""
    type: Literal["free_response", "multiple_choice", "fill_blank", "verification"]
    prompt: str
    expected_answer_locked: bool = True
    validation_strategy: Optional[str] = "semantic"  # or "exact_match", "numeric"
    choices: Optional[List[Dict[str, str]]] = None
    hint: Optional[str] = None
    expected_answer: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingStep(BaseModel):
    """One step in multi-step teaching."""
    step_id: str
    step_number: int
    learning_objective: str
    concepts: List[str] = Field(default_factory=list)
    
    # Minimal board actions (will be in StreamEvent)
    board_actions: List[Dict[str, Any]]
    
    spoken_text: str
    student_task: Optional[StudentTask] = None
    
    on_correct: str = "next_step"
    on_incorrect: str = "reteach"
    on_no_response: str = "hint"
    
    hint_progression: List[str] = Field(default_factory=list)
    
    is_final_step: bool = False
    skip_if_mastery_above: Optional[float] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TeachingSequence(BaseModel):
    """Complete teaching sequence for a problem."""
    sequence_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    problem_instance_id: str
    problem_text: str
    steps: List[TeachingStep]
    current_step_index: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    generation_model: str = "gpt-4-turbo"
    curriculum_sources: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StudentStepEvaluation(BaseModel):
    """Result of evaluating student's step response."""
    step_id: str
    student_response: str
    is_correct: bool
    confidence: float = Field(ge=0, le=1)
    misconceptions: List[str] = Field(default_factory=list)
    validation_method: str = "semantic"
    feedback: str = ""
    recommended_action: Literal[
        "next_step", "reteach", "hint", "simpler", "skip"
    ] = "next_step"
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

### Update Main VisualTutorTurnResponse

**File**: `ai-service/api/models/visual_tutor.py`

Add these fields:

```python
class VisualTutorTurnResponse(BaseModel):
    # ... existing fields ...
    
    # NEW: Step-based teaching
    teaching_sequence: Optional[Dict[str, Any]] = None
    current_step: Optional[Dict[str, Any]] = None
    student_task: Optional[VisualTutorInteraction] = None
    
    # NEW: Step evaluation (if student just responded)
    step_evaluation: Optional[Dict[str, Any]] = None
    
    # NEW: Progress tracking
    current_step_index: Optional[int] = None
    total_steps: Optional[int] = None
    
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

---

## Phase 2: First LLM Integration (Day 5)

### Create Prompt Template

**File**: `ai-service/api/services/visual_tutor/prompts.py` (NEW)

```python
import json

VISUAL_TUTOR_FIRST_STEP_PROMPT = """
You are designing the FIRST STEP of a multi-step mathematics lesson.

## Your Task
Generate a SINGLE teaching step, not the full solution. The goal is to engage the student 
in thinking, not to give them answers.

## Input
Problem: {problem}
Student Intent: {student_intent}
Curriculum Context: {curriculum}

## Output Format (JSON)
{{
  "step_id": "step_1",
  "step_number": 0,
  "learning_objective": "What concept does this step teach? (max 10 words)",
  "concepts": ["concept_id_1", "concept_id_2"],
  
  "board_actions": [
    {{
      "id": "action_1",
      "type": "write_text",
      "text": "What will you write?",
      "duration_ms": 1000
    }},
    {{
      "id": "action_2", 
      "type": "circle",
      "text": "Circle what?",
      "duration_ms": 800
    }}
  ],
  
  "spoken_text": "What you'll say while drawing the board (conversational tone)",
  
  "student_task": {{
    "type": "free_response",
    "prompt": "Your question to check understanding",
    "expected_answer": "What is a correct answer?",
    "hint": "A helpful hint if student asks",
    "validation_strategy": "semantic"
  }},
  
  "on_correct": "next_step",
  "on_incorrect": "reteach"
}}

## Critical Rules
1. Generate ONLY this first step (2-4 board actions maximum)
2. Include a student_task to check understanding
3. Do NOT solve the problem completely
4. Make it visual and engaging
5. Use conversational language in spoken_text
6. Position (x, y) will be calculated dynamically - do NOT include them
7. Return valid JSON only
"""


def get_first_step_prompt(problem: str, student_intent: str, curriculum: str) -> str:
    return VISUAL_TUTOR_FIRST_STEP_PROMPT.format(
        problem=problem,
        student_intent=student_intent,
        curriculum=curriculum,
    )
```

---

### Create Step Planning Service

**File**: `ai-service/api/services/visual_tutor/step_planner.py` (NEW)

```python
import json
import logging
from typing import Optional
from api.models.visual_tutor_step import TeachingStep, StudentTask
from api.services.model_gateway import ModelGateway

logger = logging.getLogger(__name__)


class VisualTutorStepPlanner:
    """Plans individual teaching steps using LLM."""
    
    def __init__(self, model_gateway: ModelGateway):
        self.model_gateway = model_gateway
    
    async def plan_first_step(
        self,
        problem: str,
        student_intent: str,
        curriculum_context: str,
    ) -> TeachingStep:
        """Generate the first step of a lesson."""
        
        from api.services.visual_tutor.prompts import get_first_step_prompt
        
        prompt = get_first_step_prompt(
            problem=problem,
            student_intent=student_intent,
            curriculum=curriculum_context,
        )
        
        response = await self.model_gateway.complete(
            model="gpt-4-turbo",
            system_prompt="You are an expert mathematics tutor. Generate teaching plans in JSON format.",
            user_prompt=prompt,
            temperature=0.7,
            max_tokens=1500,
        )
        
        try:
            step_dict = json.loads(response)
            step = TeachingStep(**step_dict)
            logger.info(f"Generated first step: {step.step_id}")
            return step
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}\n{response}")
            raise ValueError("LLM did not return valid JSON")
        except Exception as e:
            logger.error(f"Failed to create TeachingStep: {e}")
            raise


async def plan_visual_tutor_first_step(
    problem: str,
    student_intent: str,
    curriculum_context: str,
    model_gateway: Optional[ModelGateway] = None,
) -> TeachingStep:
    """Async helper function."""
    if model_gateway is None:
        from api.services.model_gateway import get_model_gateway
        model_gateway = get_model_gateway()
    
    planner = VisualTutorStepPlanner(model_gateway)
    return await planner.plan_first_step(
        problem=problem,
        student_intent=student_intent,
        curriculum_context=curriculum_context,
    )
```

---

## Phase 2: Update Main Route (Day 6)

### Create New Endpoint for Step-Based Teaching

**File**: `ai-service/api/routes/visual_tutor.py`

Add new route:

```python
@router.post(
    "/turn/step",
    response_class=StreamingResponse,
    tags=["Visual Tutor - Step-Based"],
)
async def submit_visual_tutor_step_turn(
    request: VisualTutorStepTurnRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    user: User = Depends(require_visual_tutor_service),
) -> StreamingResponse:
    """
    Submit a response to a teaching step and get the next step.
    
    Flow:
    1. Student submits answer to current step's task
    2. Backend evaluates response
    3. Backend generates NEXT step (or reteach)
    4. Streams next step to client
    """
    
    stream_id = _stream_id_for(request)
    session_id = request.session_id
    
    async def event_generator():
        try:
            # Load session
            session_store = VisualTutorSessionStore(db)
            session = await session_store.get_session(session_id)
            
            if not session:
                yield _sse_frame({
                    "event_id": "error_0",
                    "event_type": "error",
                    "stream_id": stream_id,
                    "session_id": session_id,
                    "sequence": 0,
                    "data": {"error": "Session not found"},
                })
                return
            
            # Get current teaching sequence
            teaching_sequence = session.metadata.get("teaching_sequence", {})
            
            # Evaluate student response
            evaluation = await evaluate_student_response(
                student_response=request.message,
                step_id=request.step_id,
                db=db,
            )
            
            yield _sse_frame({
                "event_id": f"eval_{stream_id[:8]}",
                "event_type": "step_evaluation",
                "stream_id": stream_id,
                "session_id": session_id,
                "sequence": 1,
                "data": evaluation.model_dump(),
            })
            
            # Determine next step
            if evaluation.is_correct:
                # Generate next step
                curriculum_context = await retrieve_curriculum_context(
                    subject="Mathematics",
                    topic=session.topic or "General",
                )
                
                from api.services.visual_tutor.step_planner import plan_visual_tutor_first_step
                
                next_step = await plan_visual_tutor_first_step(
                    problem=session.problem_text or "",
                    student_intent=request.message,
                    curriculum_context=curriculum_context,
                )
            else:
                # Generate reteach step
                next_step = await generate_reteach_step(
                    previous_step=request.step_id,
                    misconception=evaluation.misconceptions[0] if evaluation.misconceptions else None,
                    db=db,
                )
            
            # Stream the next step
            for i, action in enumerate(next_step.board_actions):
                yield _sse_frame({
                    "event_id": f"action_{stream_id[:8]}_{i}",
                    "event_type": "board_action",
                    "stream_id": stream_id,
                    "session_id": session_id,
                    "turn_id": request.step_id,
                    "sequence": 2 + i,
                    "data": {
                        **action,
                        "step_id": next_step.step_id,
                    },
                })
                await asyncio.sleep(0.1)  # Rate limit
            
            # Stream student task
            if next_step.student_task:
                yield _sse_frame({
                    "event_id": f"task_{stream_id[:8]}",
                    "event_type": "board_action",
                    "stream_id": stream_id,
                    "session_id": session_id,
                    "sequence": 2 + len(next_step.board_actions),
                    "data": {
                        "id": f"task_{next_step.step_id}",
                        "type": "student_task",
                        "prompt": next_step.student_task.prompt,
                        "task_type": next_step.student_task.type,
                        "step_id": next_step.step_id,
                    },
                })
            
            # Mark complete
            yield _sse_frame({
                "event_id": f"done_{stream_id[:8]}",
                "event_type": "turn_complete",
                "stream_id": stream_id,
                "session_id": session_id,
                "sequence": 999,
                "data": {
                    "step_id": next_step.step_id,
                    "total_steps": teaching_sequence.get("steps", [1]).__len__(),
                },
            })
            
        except Exception as e:
            logger.error(f"Error in step turn: {e}")
            yield _sse_frame({
                "event_id": "error_final",
                "event_type": "error",
                "stream_id": stream_id,
                "session_id": session_id,
                "sequence": 999,
                "data": {"error": str(e)},
            })
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
```

---

## Testing Checklist

### Unit Tests

```dart
// ai_tutor/test/board_position_calculator_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:ai_tutor/features/visual_tutor/presentation/services/board_position_calculator.dart';

void main() {
  group('BoardPositionCalculator', () {
    test('empty board starts at top-left', () {
      final pos = BoardPositionCalculator.calculatePosition(
        placedElements: [],
        elementType: 'write_text',
        elementHeight: 42,
        isNewStep: true,
      );
      
      expect(pos.dx, 40); // leftMargin
      expect(pos.dy, 48); // topMargin
    });
    
    test('new step creates new row', () {
      final placed = [
        PlacedElement(x: 40, y: 48, width: 280, height: 42),
      ];
      
      final pos = BoardPositionCalculator.calculatePosition(
        placedElements: placed,
        elementType: 'write_text',
        elementHeight: 42,
        isNewStep: true,
      );
      
      expect(pos.dx, 40); // leftMargin
      expect(pos.dy, 48 + 42 + 20); // below previous
    });
    
    test('same step places inline if space available', () {
      final placed = [
        PlacedElement(x: 40, y: 48, width: 150, height: 42),
      ];
      
      final pos = BoardPositionCalculator.calculatePosition(
        placedElements: placed,
        elementType: 'highlight',
        elementHeight: 42,
        isNewStep: false,
      );
      
      expect(pos.dx, greaterThan(40 + 150)); // to the right
      expect(pos.dy, 48); // same vertical level
    });
  });
}
```

### Integration Test

```python
# ai-service/tests/test_visual_tutor_steps.py
import pytest
from api.models.visual_tutor_step import TeachingStep
from api.services.visual_tutor.step_planner import plan_visual_tutor_first_step


@pytest.mark.asyncio
async def test_plan_first_step():
    """Test that first step is generated correctly."""
    
    step = await plan_visual_tutor_first_step(
        problem="Solve 2x + 5 = 13",
        student_intent="solve_equation",
        curriculum_context="linear_equations",
    )
    
    # Verify step structure
    assert step.step_id
    assert step.step_number == 0
    assert step.learning_objective
    assert len(step.board_actions) <= 4
    assert len(step.board_actions) >= 1
    assert step.spoken_text
    assert step.student_task
    assert step.student_task.prompt


@pytest.mark.asyncio
async def test_step_validation():
    """Test that step meets contract."""
    
    step = await plan_visual_tutor_first_step(
        problem="Simplify: 3(2x + 1)",
        student_intent="simplify",
        curriculum_context="distributive_property",
    )
    
    # No positions in board_actions
    for action in step.board_actions:
        assert "x" not in action
        assert "y" not in action
    
    # student_task is required for non-final steps
    if not step.is_final_step:
        assert step.student_task is not None
```

---

## What to Do Next

### Immediate (This Week)
1. ✅ Run the debug logging fix
2. ✅ Verify which actions are being filtered incorrectly
3. ✅ Implement position calculator
4. ✅ Create teaching step models
5. ✅ Create first step prompt

### Next Week
1. ✅ Integrate position calculator into board renderer
2. ✅ Implement `plan_visual_tutor_first_step()` service
3. ✅ Add new `/turn/step` route
4. ✅ Create Flutter step interaction widget
5. ✅ End-to-end test: Student problem → AI generates step 1

### Week After
1. ✅ Implement next step generation
2. ✅ Add reteach step insertion
3. ✅ Implement mastery-based step skipping
4. ✅ Enhanced learner memory per step
5. ✅ Performance optimization

---

