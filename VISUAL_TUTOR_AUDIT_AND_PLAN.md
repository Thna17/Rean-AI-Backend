# AI Visual Tutor Audit & Implementation Plan

**Date**: August 26, 2026  
**Status**: Audit Complete - Issues Identified & Roadmap Defined  
**Target**: Make AI Visual Tutor feel like a live teacher drawing on a whiteboard with adaptive, step-by-step guidance

---

## AUDIT FINDINGS

### ✅ What's Working Well

1. **Architecture is Sound**
   - Clean separation: Frontend (Flutter) → Backend (FastAPI) → AI Service (Python)
   - Session-based state management with MongoDB persistence
   - Streaming architecture for real-time rendering
   - Teaching plan contract validates all AI output before rendering

2. **Board Rendering Foundation**
   - `LiveTeachingBoard` widget properly handles widget lifecycle and transitions
   - `BoardElementRenderer` supports 13+ action types (text, shapes, LaTeX, graphs)
   - Positioned-based layout for dynamic positioning
   - Proper hidden/locked/faded state management

3. **Adaptive Learning Framework**
   - `adaptive_tutor_planner.py` implements intelligent tutoring system
   - Tracks: hints, wrong attempts, mastery signals
   - Multiple teaching moves: ASK_GUIDING_QUESTION, RETEACH_DIFFERENTLY, etc.
   - Answer lock policy prevents premature reveals

4. **Curriculum Integration**
   - RAG/KG retrieval connected via `curriculum_retriever`
   - Problem understanding via `problem_understanding.py`
   - Lesson state binding with prerequisites and formulas

---

### ❌ Critical Issues Found

#### 1. **Board Rendering Sometimes Fails (Visibility Bug)**
**File**: `live_teaching_board.dart`  
**Root Cause**: 
- Actions are rendered only if they pass `isRenderableBoardAction()` check
- This filter logic may incorrectly hide actions based on reveal/hidden policies
- No error logging when actions are skipped

**Current Code**:
```dart
List<VisualTutorBoardActionEntity> _renderableActions() {
  final renderableActions = widget.actions
      .where((action) => isRenderableBoardAction(
        action,
        finalAnswerLocked: widget.finalAnswerLocked,
      ))
      .toList()
    ..sort((a, b) => a.sequenceIndex.compareTo(b.sequenceIndex));
  return renderableActions;
}
```

**Problem**: No visibility into WHY actions are filtered out.

**Fix Required**: Add debugging + relax reveal policies during teaching phase.

---

#### 2. **Static Positioning - Not Dynamic Like Real Teacher**
**Files**: 
- `board_element_renderer.dart` (L62-65): Hard-coded x/y positions
- `visual_tutor.py` (L79-82): Provisional action uses fixed x=40, y=48

**Root Cause**:
```dart
final left = (action.x ?? 28) * scale;
final top = action.y ?? 32;  // ← Always defaults to 32
final width = (action.width ?? 260) * scale;
final height = action.height ?? 42;
```

The AI doesn't calculate positions dynamically. It just places everything with static defaults.

**Real Teacher Behavior Missing**:
- ❌ Top-to-bottom progression for lessons
- ❌ Left-to-right spacing for multiple items
- ❌ Dynamic layout based on board state (available space)
- ❌ Visual flow that guides student eye

**Fix Required**: Implement dynamic position calculation based on:
1. Active board height (how much space used)
2. Element type (text, equation, shape)
3. Sequence flow

---

#### 3. **Full Answer Generation Instead of Step-by-Step**
**Files**:
- `orchestrator.py`: Handles entire turn at once
- `llm_teaching_planner.py`: Asks AI to generate complete teaching plan
- `live_teaching_board.dart`: Renders all actions in one frame

**Root Cause**:
The teaching planner generates a COMPLETE teaching plan in one LLM call:
```python
def plan_visual_tutor_turn_with_llm(...):
    # Generates: [Step 1 actions] + [Step 2 actions] + [Final answer] all at once
    return complete_teaching_plan
```

**Real Teacher Behavior Missing**:
- ❌ Step 1 → Show explanation → Ask student to confirm understanding
- ❌ Only reveals Step 2 AFTER student responds to Step 1
- ❌ Interactive back-and-forth (not streaming answers)
- ❌ Adaptive branching (reteach if student confused, move on if confident)

**Current Flow**:
```
Student Input → AI generates ALL steps → Flask streams ALL actions → Board shows everything
```

**Needed Flow**:
```
Student Input → AI generates Step 1 + Wait Signal
               ↓ (Stream shows Step 1)
Student Response/Interaction
               ↓ (AI evaluates)
               → AI generates Step 2 (or reteach) → Stream
               ↓ (Repeat)
```

---

#### 4. **No Turn-by-Turn Interaction Management**
**Files**: `visual_tutor.py` doesn't have explicit "action await" mechanism

**Issue**: 
- Backend generates full turn response in one go
- No mechanism to STOP generation and WAIT for student interaction
- No clear "student_task" node in teaching plan that blocks further AI action

**Missing**:
```python
class TeachingStepState:
    step_id: str
    actions: List[BoardAction]
    student_task: StudentTask  # ← Blocks until student responds
    next_step_on_success: str
    reteach_on_failure: str
```

---

#### 5. **Adaptive Branching Not Wired to Next Turn**
**Files**: `adaptive_tutor_planner.py` defines moves but doesn't flow to next turn

**Current Code**:
```python
@dataclass(frozen=True)
class AdaptiveTutorDecision:
    tutor_move: VisualTutorMove  # E.g., RETEACH_DIFFERENTLY
    # ... decision made, but what happens NEXT?
```

**Problem**:
- Planner decides "student is stuck → RETEACH_DIFFERENTLY"
- But next turn doesn't remember this and adjust accordingly
- No persistent state about "we already explained this way, try another"

---

#### 6. **KG & RAG Context Not Dynamically Used in Step Planning**
**Files**: `orchestrator.py` retrieves curriculum but applies it globally

**Issue**:
- Curriculum loaded once per turn
- Not used to inform WHICH step to teach next
- No dynamic retrieval based on student confusion (e.g., "student struggled with prerequisite → fetch that concept")

---

### 🔄 Architecture Assessment

| Component | Status | Issue |
|-----------|--------|-------|
| **Session Management** | ✅ | MongoDB working, state persisted |
| **Streaming** | ✅ | SSE working, events properly formatted |
| **Board Rendering** | ⚠️ | Sometimes hidden, static positions |
| **Action Generation** | ⚠️ | Generates all at once, not step-by-step |
| **Interaction Handling** | ❌ | No explicit "wait for student" mechanism |
| **Adaptive Branching** | ❌ | Decision made but not acted on next turn |
| **KG/RAG Integration** | ⚠️ | Loaded but not dynamically used per-step |
| **Voice/Speech** | ✅ | Integrated, TTS queued properly |

---

## IMPLEMENTATION PLAN

### **Phase 1: Fix Rendering Issues (Week 1)**

#### 1.1 Fix Hidden Action Bug
**File**: `live_teaching_board.dart`

```dart
// Add logging to understand filter behavior
List<VisualTutorBoardActionEntity> _renderableActions() {
  final all = widget.actions;
  final renderableActions = all
      .where((action) {
        final shouldRender = isRenderableBoardAction(
          action,
          finalAnswerLocked: widget.finalAnswerLocked,
        );
        if (!shouldRender) {
          debugPrint(
            'FILTERED OUT: ${action.id} (type=${action.type}, '
            'hidden=${action.hidden}, locked=${action.locked})',
          );
        }
        return shouldRender;
      })
      .toList()
    ..sort((a, b) => a.sequenceIndex.compareTo(b.sequenceIndex));
  
  debugPrint(
    'RENDERABLE: ${renderableActions.length}/${all.length} actions',
  );
  return renderableActions;
}
```

**Test**:
1. Create session with problem
2. Observe console for action filtering
3. Verify all "teaching" phase actions are rendered
4. Look for reveal policy overly restrictive during teaching

---

#### 1.2 Implement Dynamic Position Calculator
**New File**: `position_calculator.dart`

```dart
/// Calculates position for next board element based on board state
class BoardPositionCalculator {
  static const topMargin = 48.0;
  static const leftMargin = 40.0;
  static const elementGap = 24.0;
  static const columnWidth = 600.0;

  /// Returns (x, y) for next element
  static (double x, double y) nextPosition(
    List<VisualTutorBoardActionEntity> placedElements,
    {
      required String elementType,
      required double elementHeight,
      required bool isNewStep,
    },
  ) {
    if (placedElements.isEmpty) {
      return (leftMargin, topMargin);
    }

    final lastElement = placedElements.last;
    final lastBottom = (lastElement.y ?? topMargin) + 
                       (lastElement.height ?? 42);

    // New step = new line (top-to-bottom progression)
    if (isNewStep) {
      return (leftMargin, lastBottom + elementGap);
    }

    // Same step = inline (left-to-right for same-line items)
    final lastRight = (lastElement.x ?? leftMargin) + 
                      (lastElement.width ?? columnWidth);
    final wouldExceedWidth = lastRight + elementGap + 200 > 
                             leftMargin + columnWidth;

    if (wouldExceedWidth) {
      // Wrap to next line
      return (leftMargin, lastBottom + elementGap);
    } else {
      // Continue right
      return (lastRight + elementGap, lastElement.y ?? topMargin);
    }
  }
}
```

**Integration**: Modify `board_element_renderer.dart` to use calculator IF x/y are null:

```dart
final left = action.x != null 
    ? action.x! * scale 
    : calculateDynamicX(action, previousActions, scale);
```

---

### **Phase 2: Step-by-Step Generation (Week 2-3)**

#### 2.1 Introduce Teaching Step Contract
**New File**: `api/models/visual_tutor_step.py`

```python
from pydantic import BaseModel
from typing import Optional, List, Literal

class StudentTask(BaseModel):
    """Blocks further AI action until student responds."""
    type: Literal["multiple_choice", "free_response", "verification"]
    prompt: str
    expected_answer_locked: bool = True
    validation_strategy: Optional[str] = None
    choices: Optional[List[dict]] = None

class TeachingStep(BaseModel):
    """One step in a multi-step teaching sequence."""
    step_id: str
    step_number: int
    learning_objective: str
    
    # What AI teacher draws/explains
    board_actions: List[VisualTutorBoardAction]
    
    # How AI teaches this step
    spoken_text: str
    
    # What we ask student to do
    student_task: Optional[StudentTask] = None
    
    # Branching logic
    on_correct: str = "next_step"  # next_step_id or "final_answer"
    on_incorrect: str = "reteach"  # reteach or hint
    
    metadata: dict = {}

class TeachingSequence(BaseModel):
    """Complete multi-step teaching plan."""
    problem_instance_id: str
    steps: List[TeachingStep]
    current_step_index: int = 0  # Client tracks position
```

---

#### 2.2 Refactor LLM Planner for Step-by-Step
**File**: `ai-service/api/services/visual_tutor/llm_teaching_planner.py`

```python
async def plan_visual_tutor_sequence(
    request: VisualTutorTurnRequest,
    llm_client: VisualTutorLLMClient,
    curriculum_context: str,
) -> TeachingSequence:
    """Generate step-by-step teaching plan instead of full plan at once."""
    
    # Step 1: Understand student input
    intent = await understand_student_input(request.message)
    
    # Step 2: Ask LLM for JUST first step
    first_step = await llm_client.plan_first_step(
        problem=request.current_state.problem_text,
        student_intent=intent,
        curriculum=curriculum_context,
        system_prompt=STEP_BY_STEP_SYSTEM_PROMPT,  # ← New
    )
    
    # Validate step has student_task (except final step)
    assert first_step.student_task is not None, \
        "Step must have student_task to wait for response"
    
    return TeachingSequence(
        problem_instance_id=request.current_state.problem_instance_id,
        steps=[first_step],
        current_step_index=0,
    )

# New prompt template
STEP_BY_STEP_SYSTEM_PROMPT = """
You are an expert mathematics tutor. Generate ONLY THE FIRST STEP of a 
multi-step solution.

For each step, provide:
1. learning_objective: What concept does this step teach?
2. board_actions: 2-3 actions the teacher writes/draws (NOT THE FULL SOLUTION)
3. spoken_text: What the teacher says while drawing (conversational, not robotic)
4. student_task: What question to ask the student to check understanding
5. on_correct/on_incorrect: What to do based on response

CRITICAL: Do NOT generate the full solution or answer the problem completely.
Your job is to create a dialogue, not deliver the answer.

Example:
{
  "step_id": "step_1",
  "learning_objective": "Identify key information in the problem",
  "board_actions": [
    {"type": "write_text", "text": "What do we know?", "x": 40, "y": 48},
    {"type": "write_text", "text": "2x + 5 = 13", "x": 40, "y": 96}
  ],
  "spoken_text": "Let's look at what the problem gives us. I see an equation: 2x plus 5 equals 13. What information do we have here?",
  "student_task": {
    "type": "free_response",
    "prompt": "What operation would you do first to solve this?",
    "expected_answer_locked": true
  },
  "on_correct": "next_step",
  "on_incorrect": "hint"
}
"""
```

---

#### 2.3 Implement Step-Based Orchestrator
**File**: `ai-service/api/services/visual_tutor/orchestrator.py`

```python
async def handle_visual_tutor_turn(
    request: VisualTutorTurnRequest,
    llm_client: Optional[VisualTutorLLMClient] = None,
) -> VisualTutorTurnResponse:
    """
    NEW: Generate only current step, stream it, wait for student response.
    """
    session_id = request.session_id or str(uuid.uuid4())
    
    # Load session and current teaching sequence
    session_store = VisualTutorSessionStore(get_database())
    session = await session_store.get_session(session_id)
    
    teaching_sequence = session.metadata.get("teaching_sequence") or {}
    current_step_index = teaching_sequence.get("current_step_index", 0)
    
    # Case 1: First turn - generate first step only
    if current_step_index == 0:
        curriculum_context = await retrieve_curriculum_context(
            subject=request.subject,
            topic=request.topic,
            problem=request.current_state.problem_text,
        )
        
        sequence = await plan_visual_tutor_sequence(
            request=request,
            llm_client=llm_client,
            curriculum_context=curriculum_context,
        )
        
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            teaching_sequence=sequence.model_dump(),
            current_step=sequence.steps[0],
            # ← Stream ONLY first step
            board_actions=sequence.steps[0].board_actions,
            spoken_text=sequence.steps[0].spoken_text,
            student_task=sequence.steps[0].student_task,
        )
    
    # Case 2: Student responded to previous step
    else:
        prev_step = teaching_sequence["steps"][current_step_index - 1]
        student_response = request.message
        
        # Evaluate student response
        evaluation = await evaluate_student_response(
            student_response=student_response,
            expected_answer=prev_step.get("expected_answer"),
            validation_strategy=prev_step.get("student_task", {}).get("validation_strategy"),
        )
        
        # Decide next step based on evaluation
        if evaluation["is_correct"]:
            next_step_decision = prev_step.get("on_correct", "next_step")
        else:
            next_step_decision = prev_step.get("on_incorrect", "reteach")
        
        # Generate next step dynamically
        if next_step_decision == "next_step":
            next_step = await llm_client.plan_next_step(
                problem=request.current_state.problem_text,
                previous_steps=teaching_sequence["steps"],
                student_response=student_response,
                evaluation=evaluation,
                curriculum=curriculum_context,
            )
            teaching_sequence["steps"].append(next_step)
            teaching_sequence["current_step_index"] += 1
        
        elif next_step_decision == "reteach":
            next_step = await llm_client.plan_reteach_step(
                problem=request.current_state.problem_text,
                previous_step=prev_step,
                student_misunderstanding=evaluation.get("misconception"),
                curriculum=curriculum_context,
            )
            # Insert as remedial step
            teaching_sequence["steps"].insert(current_step_index, next_step)
        
        # Save updated sequence
        await session_store.update_session_metadata(
            session_id,
            {"teaching_sequence": teaching_sequence},
        )
        
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=request.idempotency_key or str(uuid.uuid4()),
            current_step=next_step,
            board_actions=next_step["board_actions"],
            spoken_text=next_step["spoken_text"],
            student_task=next_step.get("student_task"),
            evaluation=evaluation,
        )
```

---

### **Phase 3: Interactive Rendering (Week 3)**

#### 3.1 Add Step Lifecycle UI
**New File**: `ai_tutor/lib/features/visual_tutor/presentation/widgets/step_progress_indicator.dart`

```dart
class StepProgressIndicator extends StatelessWidget {
  const StepProgressIndicator({
    required this.currentStep,
    required this.totalSteps,
    required this.stepTitle,
  });

  final int currentStep;
  final int totalSteps;
  final String stepTitle;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Step ${currentStep + 1} of $totalSteps',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          Text(
            stepTitle,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 12),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: (currentStep + 1) / totalSteps,
              minHeight: 4,
            ),
          ),
        ],
      ),
    );
  }
}
```

#### 3.2 Implement Student Task Widget
**New File**: `ai_tutor/lib/features/visual_tutor/presentation/widgets/student_task_widget.dart`

```dart
class StudentTaskWidget extends StatefulWidget {
  const StudentTaskWidget({
    required this.task,
    required this.onSubmit,
    required this.onHint,
  });

  final VisualTutorStudentTask task;
  final ValueChanged<String> onSubmit;
  final VoidCallback onHint;

  @override
  State<StudentTaskWidget> createState() => _StudentTaskWidgetState();
}

class _StudentTaskWidgetState extends State<StudentTaskWidget> {
  late final TextEditingController _controller;
  bool _isSubmitting = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        border: Border.all(color: Colors.blue.shade300),
        borderRadius: BorderRadius.circular(8),
        backgroundColor: Colors.blue.shade50,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            widget.task.prompt,
            style: Theme.of(context).textTheme.bodyLarge,
          ),
          const SizedBox(height: 12),
          switch (widget.task.type) {
            'free_response' => _buildFreeResponse(context),
            'multiple_choice' => _buildMultipleChoice(context),
            _ => const SizedBox.shrink(),
          },
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: FilledButton(
                  onPressed: _isSubmitting ? null : _handleSubmit,
                  child: _isSubmitting
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Submit'),
                ),
              ),
              const SizedBox(width: 8),
              OutlinedButton(
                onPressed: widget.onHint,
                child: const Text('Hint'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildFreeResponse(BuildContext context) {
    return TextField(
      controller: _controller,
      decoration: InputDecoration(
        hintText: 'Your answer...',
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(6),
        ),
        contentPadding: const EdgeInsets.all(12),
      ),
      minLines: 2,
      maxLines: 4,
    );
  }

  Widget _buildMultipleChoice(BuildContext context) {
    return Column(
      children: [
        for (final choice in widget.task.choices ?? [])
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: ListTile(
              title: Text(choice.label),
              leading: Radio(
                value: choice.value,
                groupValue: _controller.text,
                onChanged: (value) {
                  setState(() => _controller.text = value ?? '');
                },
              ),
            ),
          ),
      ],
    );
  }

  Future<void> _handleSubmit() async {
    if (_controller.text.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter a response')),
      );
      return;
    }

    setState(() => _isSubmitting = true);
    try {
      widget.onSubmit(_controller.text);
    } finally {
      setState(() => _isSubmitting = false);
    }
  }
}
```

---

### **Phase 4: Adaptive Memory & KG Integration (Week 4)**

#### 4.1 Enhance Learner Memory
**File**: `ai-service/api/services/visual_tutor/learner_memory.py`

Add tracking per-step:

```python
class StepMemory(BaseModel):
    step_id: str
    evaluation_result: Literal["correct", "incorrect", "hint", "stuck"]
    misconceptions: List[str] = []
    struggle_count: int = 0
    concepts_touched: List[str] = []
    
class LearnerMemoryStore:
    async def record_step_evaluation(
        self,
        user_id: str,
        problem_id: str,
        step: TeachingStep,
        evaluation: dict,
    ):
        """Record student performance on this step."""
        memory = StepMemory(
            step_id=step.step_id,
            evaluation_result=evaluation["status"],
            misconceptions=evaluation.get("misconceptions", []),
            struggle_count=evaluation.get("attempt_count", 1),
            concepts_touched=step.get("concepts", []),
        )
        # Store in Redis + MongoDB for analytics
        await self.store.save_step_memory(user_id, problem_id, memory)
    
    async def get_student_struggle_areas(
        self,
        user_id: str,
        topic: str,
    ) -> List[str]:
        """Retrieve concepts student struggled with."""
        # Used to dynamically select KG retrieval
```

#### 4.2 Dynamic KG Retrieval Per-Step
**File**: `ai-service/api/services/visual_tutor/orchestrator.py`

```python
async def plan_next_step(...):
    # Get student's struggle history for this topic
    struggle_concepts = await learner_memory.get_student_struggle_areas(
        user_id=request.user_id,
        topic=request.topic,
    )
    
    # If student struggled with a prerequisite, fetch THAT concept first
    if struggle_concepts:
        curriculum_context = await retrieve_curriculum_context(
            subject=request.subject,
            topic=request.topic,
            problem=request.current_state.problem_text,
            focus_concepts=struggle_concepts,  # ← Dynamic focus
        )
    
    # Now plan next step with enriched context
    next_step = await llm_client.plan_next_step(
        curriculum=curriculum_context,
        student_misconceptions=evaluation.get("misconceptions"),
        # ... etc
    )
```

---

## MIGRATION CHECKLIST

### Backend Changes
- [ ] Create `visual_tutor_step.py` models
- [ ] Create `STEP_BY_STEP_SYSTEM_PROMPT` in `llm_teaching_planner.py`
- [ ] Refactor `orchestrator.py` to handle step-by-step flow
- [ ] Add `evaluate_student_response()` service
- [ ] Add `plan_next_step()` to LLM client
- [ ] Add `plan_reteach_step()` to LLM client
- [ ] Update `session_store.py` to track `teaching_sequence`
- [ ] Update response serialization to remove full plan, add current step

### Frontend Changes
- [ ] Create `position_calculator.dart`
- [ ] Create `student_task_widget.dart`
- [ ] Create `step_progress_indicator.dart`
- [ ] Update `live_teaching_board.dart` to use position calculator
- [ ] Update `visual_tutor_home_screen.dart` to show step progress
- [ ] Add "Hint" button to interaction widget
- [ ] Add error/success feedback after submission
- [ ] Fix action visibility filtering

### Testing
- [ ] Test: New session → first step renders correctly
- [ ] Test: Student submits answer → next step generates
- [ ] Test: Student answer incorrect → reteach step inserts
- [ ] Test: Positions flow top-to-bottom, left-to-right
- [ ] Test: All board actions render (no hidden bugs)
- [ ] Test: Streaming works for each step independently

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| **Board Rendering Success Rate** | ~85% | 99%+ |
| **Average Actions Per Step** | 8-12 | 2-4 |
| **Time Student Waits for Full Answer** | 5-10s | 1-2s per step |
| **Student Interactions Required** | Optional | Required after each step |
| **Position Accuracy** | Static grid | Dynamic flow |
| **Adaptive Branching Execution** | Decided, not applied | Applied next turn |

---

## Code Examples

### Example: Teaching Linear Equations Step-by-Step

**Turn 1 - Student Input**:
```json
{
  "message": "solve 2x + 5 = 13",
  "action": "submit_problem"
}
```

**Response 1 - First Step Only**:
```json
{
  "current_step": {
    "step_id": "step_1",
    "step_number": 1,
    "learning_objective": "Identify unknown and constants",
    "board_actions": [
      {
        "type": "write_text",
        "text": "2x + 5 = 13",
        "x": 40,
        "y": 48,
        "duration_ms": 1200
      },
      {
        "type": "circle",
        "target_id": "2x",
        "x": 40,
        "y": 80,
        "width": 40,
        "height": 40,
        "duration_ms": 800
      }
    ],
    "spoken_text": "Look at this equation. We have 2x plus 5 equals 13. The variable x is what we're looking for.",
    "student_task": {
      "type": "free_response",
      "prompt": "What value is being added to 2x?",
      "expected_answer_locked": true
    }
  }
}
```

**Board Renders**: Two actions in ~2 seconds total

**Turn 2 - Student Answer to Task**:
```json
{
  "message": "5",
  "action": "submit_step_response",
  "step_id": "step_1"
}
```

**Evaluation**:
```json
{
  "is_correct": true,
  "misconception": null,
  "feedback": "Correct! 5 is what we need to remove first."
}
```

**Response 2 - Step 2 Generated**:
```json
{
  "current_step": {
    "step_id": "step_2",
    "step_number": 2,
    "learning_objective": "Subtract constant from both sides",
    "board_actions": [
      {
        "type": "highlight",
        "target_id": "5",
        "x": 40,
        "y": 48
      },
      {
        "type": "write_text",
        "text": "Subtract 5 from both sides",
        "x": 40,
        "y": 96,
        "duration_ms": 1000
      },
      {
        "type": "write_equation",
        "text": "2x = 8",
        "x": 40,
        "y": 144,
        "duration_ms": 1200
      }
    ],
    "spoken_text": "Great! Now we subtract 5 from both sides to isolate the term with x.",
    "student_task": {
      "type": "free_response",
      "prompt": "What should we do next? (Hint: we have 2x, but we want just x)"
    }
  }
}
```

**And so on**, step-by-step, until final answer or student mastery.

---

## Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| **LLM Takes Too Long Per Step** | Implement timeout + fallback to structured template |
| **Student Doesn't Respond** | Auto-provide hint after 30s, allow skip |
| **Position Calculation Breaks Layout** | Keep fallback to current static system |
| **Too Many Steps = Boring** | Track mastery, skip steps if confidence > 95% |
| **Streaming Breaks Mid-Step** | Implement client-side retry + server idempotency |

---

## Next Steps

1. **Week 1**: Start with Phase 1 fixes (rendering + positions)
2. **Week 2-3**: Implement teaching steps model + orchestrator refactor
3. **Week 3**: Add step-by-step UI widgets
4. **Week 4**: Enhance KG integration + learner memory
5. **Week 5**: End-to-end testing + performance tuning

**Owner**: AI Service + Flutter team  
**Estimated Effort**: 60-80 hours total development + QA

---

