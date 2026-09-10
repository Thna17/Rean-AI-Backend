# Visual Tutor: Architecture Diagrams & Data Flow

## Current Architecture (Simplified)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUTTER APP                                   │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Visual Tutor Screen                                             │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│
│  │  │  Problem Input   │  │ Board (rendering)│  │  Student Task    ││
│  │  │  (text/image)    │  │  (all at once)   │  │  (sometimes OK)  ││
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘│
│  │         ↓                        ↑                     ↑            │
│  │    HTTP POST                 SSE Stream            HTTP POST       │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
          ↓ POST /api/v1/visual_tutor/turn               ↑ SSE
          
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND SERVICE (FastAPI)                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  routes/visual_tutor.py                                        │ │
│  │  ├─ POST /turn  (main endpoint)                               │ │
│  │  └─ [Returns full teaching plan at once]                      │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Orchestrator (handle_visual_tutor_turn)                       │ │
│  │  ├─ Understand student input                                  │ │
│  │  ├─ Detect intent                                             │ │
│  │  ├─ Call AI Service for complete solution                    │ │
│  │  └─ Build full teaching plan                                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  AI SERVICE (Python)                                           │ │
│  │  ├─ Curriculum retrieval (KG + RAG)                           │ │
│  │  ├─ Problem understanding                                     │ │
│  │  ├─ Adaptive tutor planner (decides on moves)                 │ │
│  │  ├─ LLM (generates full teaching plan)                        │ │
│  │  └─ Returns: All board actions + speech + all steps          │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  MongoDB Session Store                                         │ │
│  │  └─ Save complete turn for replay                             │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

PROBLEMS WITH CURRENT DESIGN:
❌ #1: Board elements don't all render (visibility bug)
❌ #2: Static positions (elements stack, not flow)
❌ #3: Full solution at once (not interactive)
```

---

## Proposed Architecture (New)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUTTER APP (Updated)                        │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │  Visual Tutor Screen                                             │ │
│  │  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐│
│  │  │  Problem Input   │  │ Board (rendering)│  │  Student Task    ││
│  │  │  (text/image)    │  │  (STEP only)     │  │  (REQUIRED)      ││
│  │  └──────────────────┘  └──────────────────┘  └──────────────────┘│
│  │         ↓                    ↑                     ↑↓              │
│  │    HTTP POST            Smooth animations    StepInteraction   │
│  │  (first step)         (top-to-bottom flow)     Widget           │
│  │                                              (new)              │
│  │                                                                   │
│  │  Step Progress Indicator (new)                                   │
│  │  ├─ Step 1 of 5                                                  │
│  │  ├─ Learning Objective: "Identify constants"                    │
│  │  └─ [=====>        ] (progress bar)                             │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
          ↓ POST /api/v1/visual_tutor/turn/step (new!)
          
TURN 1: Student inputs problem
        ↓ (Backend generates STEP 1 ONLY)
        ↑ SSE with board actions for Step 1
        
        Student sees: "Step 1: Identify Information"
        Board displays: 2-3 drawing actions
        Question: "What value is being added?"
        
        (Student answers)
        
        ↓ POST answer
        
TURN 2: Backend evaluates answer
        (is_correct=true, feedback="Great!")
        ↓ (Backend generates STEP 2)
        ↑ SSE with board actions for Step 2
        
        Student sees: "Step 2: Subtract from both sides"
        Board displays: 2-3 more drawing actions
        Question: "What's the result?"
        
        (Student answers)
        
[REPEAT until mastery or final step]

┌─────────────────────────────────────────────────────────────────────┐
│                  BACKEND SERVICE (Updated)                          │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  routes/visual_tutor.py                                        │ │
│  │  ├─ POST /turn           (keeps working)                      │ │
│  │  └─ POST /turn/step      (NEW: step-based)                    │ │
│  │        ├─ Input: step_id, student_response                    │ │
│  │        └─ Output: Next step only                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Step Planner (NEW)                                            │ │
│  │  ├─ LLM generates CURRENT STEP ONLY (not full solution)       │ │
│  │  ├─ Step contains: 2-4 actions + question                     │ │
│  │  └─ Returns: TeachingStep object                              │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Step Evaluator (NEW)                                          │ │
│  │  ├─ LLM evaluates student response                            │ │
│  │  ├─ Detects misconceptions                                    │ │
│  │  └─ Returns: StudentStepEvaluation                            │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  Orchestrator (Updated)                                        │ │
│  │  ├─ If correct: plan_next_step()                              │ │
│  │  ├─ If incorrect: plan_reteach_step()                         │ │
│  │  ├─ If stuck: provide_hint()                                  │ │
│  │  └─ If mastered: skip_remaining_steps()                       │ │
│  └────────────────────────────────────────────────────────────────┘ │
│          ↓                                                            │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  MongoDB Session Store (Updated)                               │ │
│  │  └─ Save teaching_sequence + step_evaluations                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

✅ IMPROVEMENTS:
✅ #1: All elements render (debug logging identifies issues)
✅ #2: Dynamic positions (BoardPositionCalculator)
✅ #3: Interactive, step-by-step (TeachingStep model + branching)
```

---

## Data Flow Comparison

### BEFORE: Full Answer at Once

```
┌──────────────────┐
│ Student Input    │
│ "solve 2x+5=13"  │
└────────┬─────────┘
         │
         ↓
    ┌─────────────────────────────────┐
    │ AI Service                      │
    │ • Understand problem            │
    │ • Retrieve curriculum           │
    │ • Plan FULL solution steps      │
    │ • Generate ALL board actions    │
    └────────┬────────────────────────┘
             │
             ↓ (All at once)
    ┌──────────────────────────────────┐
    │ Board Actions (50+)              │
    │ • Write equation                 │
    │ • Highlight constant             │
    │ • Circle coefficient             │
    │ • Write "subtract 5"             │
    │ • Show: 2x = 8                   │
    │ • Write "divide by 2"            │
    │ • Show: x = 4                    │
    │ • [Many more steps...]           │
    └────────┬──────────────────────────┘
             │
             ↓
    ┌──────────────────────────────────┐
    │ Flutter Board Rendering          │
    │ (Streams all actions smoothly)   │
    │                                  │
    │ Student watches full solution    │
    │ (Passive, no interaction)        │
    └──────────────────────────────────┘

Time: 0s → 8s (full solution visible)
Student engagement: Low (just watching)
Opportunity for adaptation: Zero
```

### AFTER: Step-by-Step with Interaction

```
┌──────────────────┐                TIME FLOW
│ Student Input    │  0s
│ "solve 2x+5=13"  │  (POST /turn/step)
└────────┬─────────┘
         │
         ↓
    ┌─────────────────────────────────┐
    │ AI Service (STEP 1 ONLY)        │  1-2s
    │ • Understand problem            │  (LLM
    │ • Retrieve curriculum           │   call)
    │ • Plan FIRST STEP only          │
    │ • Generate 3 actions for step 1 │
    └────────┬────────────────────────┘
             │
             ↓ (Only Step 1)
    ┌──────────────────────────────────┐
    │ Board Actions (3)                │  2-3s
    │ • Write "2x + 5 = 13"            │  (SSE
    │ • Highlight "5"                  │   stream)
    │ • Write "What's being added?"    │
    └────────┬──────────────────────────┘
             │
             ↓
    ┌──────────────────────────────────┐  3-4s
    │ Flutter Board Rendering          │  (smooth
    │ Student sees STEP 1 & QUESTION   │   animation)
    │                                  │
    │ [Board shows first 3 elements]   │
    │ [Tutor asks: "What's added?"]    │
    │ [Student thinks & answers]       │
    └────────┬──────────────────────────┘
             │ (Student types "5")
             │ (POST answer)
             ↓
    ┌─────────────────────────────────┐  4-5s
    │ Backend Evaluates               │  (evaluate
    │ • Check: "5" == correct         │   response)
    │ • Feedback: "Great!"            │
    │ • Plan NEXT STEP                │
    └────────┬────────────────────────┘
             │
             ↓ (Only Step 2)
    ┌──────────────────────────────────┐  5-6s
    │ Board Actions (3)                │  (LLM +
    │ • Highlight "- 5"                │   SSE)
    │ • Write "2x = 8"                 │
    │ • Write "What's next?"           │
    └────────┬──────────────────────────┘
             │
             ↓
    ┌──────────────────────────────────┐  6-7s
    │ Flutter Board Rendering          │  (smooth
    │ Student sees STEP 2 & QUESTION   │   animation)
    │ (Previous elements fade)         │
    │                                  │
    │ [Board shows next 3 elements]    │
    │ [Tutor asks: "Divide by what?"]  │
    │ [Student answers again]          │
    └────────┬──────────────────────────┘
             │
             ↓ [REPEAT until mastery]
    
Duration: ~30s total (vs 8s)
BUT: Student engaged, thinking, answering
     Perfect pacing for learning
     Adaptive branching possible
     Memory of interaction strong
```

---

## Board Positioning: Before vs After

### BEFORE: Static Grid

```
     0      100     200     300     400     500     600
     ↓      ↓       ↓       ↓       ↓       ↓       ↓
 48 ┌──────────────────────────────────────────────────┐
    │                                                  │
    │ ┌─────────────────────────────┐                │
    │ │ write_text: "2x + 5 = 13"   │                │
    │ └─────────────────────────────┘                │
    │                                                  │
 90 │ ┌────────────────────┐                          │
    │ │ highlight: (5)     │                          │
    │ └────────────────────┘                          │
    │                                                  │
132 │ ┌─────────────────────────────────────────────┐ │
    │ │ write_text: "Subtract 5 from both sides"   │ │
    │ └─────────────────────────────────────────────┘ │
    │                                                  │
174 │ ┌─────────────────────┐                         │
    │ │ write_text: "2x=8"  │                         │
    │ └─────────────────────┘                         │
    │                                                  │
    │ ⚠️  PROBLEMS:
    │ • Perfectly vertical (grid)
    │ • Looks machine-generated
    │ • Hard to follow flow
    │ • Doesn't match real whiteboard
    │
└───────────────────────────────────────────────────────┘
```

### AFTER: Dynamic Flow Layout

```
     0      100     200     300     400     500     600
     ↓      ↓       ↓       ↓       ↓       ↓       ↓
 48 ┌──────────────────────────────────────────────────┐
    │                                                  │
    │ ┌──────────────────────────────┐               │
    │ │ write_text: "2x + 5 = 13"    │               │
    │ └──────────────────────────────┘               │
    │                    STEP 1
    │ ┌────────────┐  ┌──────────────────┐           │
    │ │ highlight  │  │ write_text:      │           │
    │ │ (5)        │  │ "What's added?"  │           │
    │ └────────────┘  └──────────────────┘           │
    │
    │ ────────────────────────────────────────────────  (Step 2 starts)
    │
    │ ┌───────────────────┐  ┌──────────────────────┐ │
    │ │ highlight:        │  │ write_equation:      │ │
    │ │ "- 5"             │  │ "2x = 8"             │ │
    │ └───────────────────┘  └──────────────────────┘ │
    │                    STEP 2
    │ ┌──────────────────────────────────────┐        │
    │ │ write_text: "Now divide both sides"  │        │
    │ └──────────────────────────────────────┘        │
    │
    │ ✅  IMPROVEMENTS:
    │ • Flows naturally
    │ • Matches teaching style
    │ • Clear step boundaries
    │ • Dynamic based on content
    │
└───────────────────────────────────────────────────────┘

Calculator Algorithm:
1. Track all placed elements
2. For new step: y = lastElement.bottom + gap
3. For same step: x = lastElement.right + gap
4. If would overflow: wrap to next line
```

---

## Database Schema Evolution

### BEFORE: VisualTutorSession (Current)

```python
{
  "session_id": "sess_123",
  "user_id": "user_456",
  "problem_text": "Solve 2x + 5 = 13",
  "problem_type": "linear_equation",
  
  "status": "active",
  "current_step_index": 0,
  "hintCount": 0,
  "wrongAttempts": 0,
  "finalAnswerRevealed": false,
  
  "teachingBoard": {
    "actions": [
      // 50+ actions all generated at once
      {"id": "a1", "type": "write_text", "text": "2x + 5 = 13", ...},
      {"id": "a2", "type": "highlight", ...},
      // ... all the way to final answer
    ]
  },
  
  "metadata": {
    "teaching_plan": {...},  // Full plan
    "curriculum_context": [...],
  }
}
```

### AFTER: VisualTutorSession (New)

```python
{
  "session_id": "sess_123",
  "user_id": "user_456",
  "problem_text": "Solve 2x + 5 = 13",
  "problem_type": "linear_equation",
  
  "status": "active",
  
  # NEW: Teaching sequence tracking
  "teaching_sequence": {
    "sequence_id": "seq_789",
    "problem_instance_id": "prob_123",
    "current_step_index": 1,  # On step 2 now
    "steps": [
      {
        "step_id": "step_1",
        "step_number": 0,
        "learning_objective": "Identify constants in equation",
        "board_actions": [
          {"id": "a1", "type": "write_text", "text": "2x + 5 = 13"},
          {"id": "a2", "type": "highlight", "duration_ms": 800},
          {"id": "a3", "type": "write_text", "text": "What's added?"},
        ],
        "spoken_text": "...",
        "student_task": {
          "type": "free_response",
          "prompt": "What value is being added?",
          "expected_answer": "5",
        }
      },
      {
        "step_id": "step_2",
        "step_number": 1,
        "learning_objective": "Subtract constant from both sides",
        "board_actions": [
          {"id": "b1", "type": "highlight", "target_id": "5"},
          {"id": "b2", "type": "write_text", "text": "Subtract 5"},
          {"id": "b3", "type": "write_equation", "text": "2x = 8"},
        ],
        "student_task": {...},
      },
      // ... more steps
    ]
  },
  
  # NEW: Track evaluations
  "step_evaluations": [
    {
      "step_id": "step_1",
      "student_response": "5",
      "is_correct": true,
      "confidence": 0.95,
      "feedback": "Exactly right!",
      "recommended_action": "next_step"
    },
    // ... more evaluations as student progresses
  ],
  
  "metadata": {
    "curriculum_sources": [...],
    "generation_model": "gpt-4-turbo",
  }
}
```

---

## State Machine: Step Progression

```
                    ┌──────────────────┐
                    │  Student submits  │
                    │  problem          │
                    └────────┬──────────┘
                             │
                             ↓
                    ┌──────────────────┐
                    │ Generate STEP 1  │
                    │ (AI Service)     │
                    └────────┬──────────┘
                             │
                             ↓
        ┌────────────────────────────────────┐
        │ Render Step 1                      │
        │ • Display board actions            │
        │ • Show student task question       │
        │ • Wait for student input           │
        └────────┬─────────────────────────────┘
                 │
                 ↓
        ┌────────────────────────────────────┐
        │ Student submits answer to Step 1  │
        └────────┬──────────────────────────────┘
                 │
                 ↓
      ┌──────────────────────────────────────────┐
      │ Evaluate Student Response                │
      └──────┬─────────────┬──────────┬──────────┘
             │             │          │
         Correct       Incorrect      Stuck
             │             │          │
             ↓             ↓          ↓
        Next Step     Reteach Step   Hint
             │             │          │
             └──────┬──────┴─────┬────┘
                    ↓            ↓
         ┌────────────────────────────────────┐
         │ Generate Next/Reteach/Hint Step   │
         │ (Adaptive decision logic)         │
         └────────┬─────────────────────────────┘
                  │
                  ↓
      ┌───────────────────────────────────────┐
      │ Render Step N                         │
      │ (Update board, show new question)     │
      └────────┬────────────────────────────────┘
               │
        [LOOP back to "Student submits"]
               │
               ↓ (after final step)
      ┌────────────────────────────────────┐
      │ Mastery Detected                   │
      │ • Save performance metrics         │
      │ • Update learner memory            │
      │ • Close session                    │
      └────────────────────────────────────┘
```

---

## Component Dependencies

### Frontend (Flutter)

```
visual_tutor_home_screen.dart
    ↓ uses
    ├─ LiveTeachingBoard (rendered board)
    │   ├─ uses
    │   └─ BoardElementRenderer
    │       └─ uses
    │           └─ BoardPositionCalculator (NEW)
    │
    ├─ StepProgressIndicator (NEW)
    │   └─ Shows: Step X of Y
    │
    ├─ StepInteractionWidget (NEW)
    │   ├─ StudentTask display
    │   ├─ Free response / Multiple choice
    │   └─ Submit + Hint buttons
    │
    └─ StepBoardNotifier (NEW - State)
        ├─ Manages current step
        ├─ Tracks evaluation
        └─ Handles step advancement
```

### Backend (FastAPI)

```
routes/visual_tutor.py
    ├─ POST /turn (existing)
    │   └─ handle_visual_tutor_turn()
    │
    └─ POST /turn/step (NEW)
        ├─ Evaluate previous step
        ├─ Generate next step via StepPlanner
        └─ Stream response
        
StepPlanner (NEW)
    ├─ Uses LLMClient
    └─ Returns TeachingStep
    
StepEvaluator (NEW)
    ├─ Uses LLMClient
    └─ Returns StudentStepEvaluation
    
Orchestrator (updated)
    ├─ Receives evaluation
    ├─ Decides: next_step? reteach? hint? skip?
    └─ Calls StepPlanner accordingly
    
LearnerMemory (updated)
    ├─ Records per-step performance
    └─ Informs adaptive decisions
```

---

## Success Metric Visualization

```
BEFORE                          AFTER
────────────────────────────────────────

Rendering Success:
██████████████████░░░  85%      ████████████████████  99%+

Element Positioning:
████████░░░░░░░░░░░░░  40%      ████████████████████  100%
(static grid)                   (dynamic flow)

Student Engagement:
████████░░░░░░░░░░░░░  40%      ███████████████░░░░░  75%
(passive watching)              (active interaction)

Step Interactivity:
░░░░░░░░░░░░░░░░░░░░░   0%     ████████████████████  100%
(none)                          (after each step)

Adaptive Response Time:
░░░░░░░░░░░░░░░░░░░░░   0%     ██████████░░░░░░░░░░   50%
(no adaptation)                 (reteach, hints)

Total Teaching Time:
████████░░░░░░░░░░░░░  40%      ███████████████████░   90%
(3-5 min)                       (8-12 min)

Learning Outcome:
████████░░░░░░░░░░░░░  60%      ███████████░░░░░░░░░   75%
(estimated)                     (estimated)
```

---

