# AI Visual Tutor - Current State Audit & Implementation Plan

**Date**: August 26, 2024  
**Status**: Phase 0 (Foundation) - In Progress  
**Target**: Cambodia Grade 10-12 (Math, Physics, Chemistry)  
**Vision**: Interactive AI Teacher with Live Whiteboard (NOT a chatbot)

> **Implementation update — 2026-08-28:** The historical gaps below are no
> longer an accurate release status. The implementation now has declarative
> semantic board layout, progressive action playback, typed STEM primitives,
> scoped curriculum/KG retrieval, a durable learner model, Khmer/English/
> bilingual routing, and one-teaching-moment policy gates. Remaining release
> evidence is tracked through the privacy-safe telemetry and acceptance gates
> in `ai-service/api/services/visual_tutor/observability.py`; this document is
> retained as the original baseline, not a list of current defects.

---

## 📊 Executive Summary

### What's Done ✅
- **Architecture & Design**: Complete multi-layer plan with 10 comprehensive documentation files
- **Flutter Foundation**: Core visual_tutor feature with entities, repositories, presentation widgets
- **Board System**: Live teaching board with action rendering (shapes, text, highlights)
- **UI Design System**: Colors, typography, spacing tokens for whiteboard experience
- **Entity Models**: Session, turn, response, board action data structures
- **Data Layer**: Remote data sources, repositories, models for API integration

### What's Broken or Incomplete 🟡
1. **Rendering Issues**:
   - ❌ Widgets sometimes don't render (visibility state problem)
   - ❌ Position/animation not dynamic (fixed coordinates instead of relative)
   - ❌ No step-by-step sequential animation (whole problem at once)

2. **Rich Media Missing**:
   - ❌ No graph renderer (Plotly or Canvas)
   - ❌ No geometric shape system (triangles, circles, FBDs)
   - ❌ No vector/arrow system for physics
   - ❌ No molecule renderer for chemistry
   - ❌ No coordinate system with dynamic labels

3. **Pedagogical Gaps**:
   - ❌ No step sequencing (Step 1 → Step 2 → Step 3 flow)
   - ❌ No Socratic questioning system
   - ❌ No adaptive branching (if correct → next step, if wrong → reteach)
   - ❌ No misconception detection
   - ❌ No visual focus/highlighting system

4. **Curriculum Integration**:
   - ❌ No Cambodia MOE curriculum database
   - ❌ No subject prerequisites mapping
   - ❌ No learning outcomes tracking
   - ❌ No Khmer language content

5. **Backend Teaching Pipeline**:
   - ❌ No multi-step teaching sequence generation
   - ❌ No step evaluation (is student answer correct?)
   - ❌ No adaptive branching logic
   - ❌ No concept prerequisite checking

### Why the Rendering Issues Happen
```
Current Flow (BROKEN):
┌────────────────┐
│ AI generates   │
│ ALL actions    │  ← Problem: Whole solution at once
│ for solution   │
└────────────────┘
         ↓
┌────────────────┐
│ Flutter gets   │
│ list of actions│  ← Problem: No sequencing info
└────────────────┘
         ↓
┌────────────────┐
│ Renderer tries │
│ to show all at │  ← Problem: Some render, some don't
│ once (position │     (visibility, z-index issues)
│ conflicts)     │
└────────────────┘

Desired Flow (NEEDED):
┌────────────────┐
│ AI generates   │
│ STEP 1 only    │  ← Fix: One step = 2-4 actions
│                │
└────────────────┘
         ↓
┌────────────────┐
│ Flutter renders│
│ with animation │  ← Fix: Top-to-bottom, left-to-right
│ (left-to-right,│     dynamic positioning
│ top-to-bottom) │
└────────────────┘
         ↓
┌────────────────┐
│ Student sees  │
│ step, responds │  ← Fix: Wait for interaction
│                │
└────────────────┘
         ↓
┌────────────────┘
│ AI generates   │
│ STEP 2 (adapt  │  ← Fix: Adaptive based on response
│ to response)   │
└────────────────┘
```

---

## 📁 Current Architecture Audit

### 1. Flutter Frontend (`ai_tutor/lib/features/visual_tutor/`)

#### ✅ What Exists

**Presentation Layer** (`presentation/`)
- **Widgets** (`widgets/`):
  - `live_teaching_board.dart` - Main board rendering widget (handles action sequencing, transitions)
  - `board_element_renderer.dart` - Renders individual actions (shapes, text, highlights, tables)
  - `graph_board_painter.dart` - Simple 2D graph painter (basic coordinate system)
  - `check_work_board.dart`, `final_answer_board.dart` - Board variants
  - `unsupported_board.dart` - Error states

- **Services** (`services/` - MISSING):
  - Need: `graph_renderer.dart`, `geometric_renderer.dart`, `vector_renderer.dart`, `molecule_renderer.dart`
  - Need: `rich_media_canvas.dart` (widget that coordinates all)

- **Core Files**:
  - `visual_tutor_design.dart` - Design tokens (colors, spacing, typography, decorations)
  - `live_board_state.dart` - State management for board (action sequencing, transitions)
  - `visual_tutor_board_snapshot.dart` - Snapshot/replay capture
  - `visual_tutor_voice.dart`, `visual_tutor_recorder.dart` - Audio I/O (platform-specific)

**Domain Layer** (`domain/`)
- **Entities**:
  - `visual_tutor_entities.dart` - Session, Turn, Response, BoardAction, BoardElement entities
  - `teaching_plan_contract.dart` - Teaching plan interface (not implemented)

- **Repositories**:
  - `visual_tutor_repository.dart` - Abstract repository

**Data Layer** (`data/`)
- **Models**:
  - `visual_tutor_models.dart` - Serializable models (JSON to/from entities)

- **Data Sources**:
  - `visual_tutor_remote_data_source.dart` - API client (calls backend)

- **Repositories**:
  - `visual_tutor_repository_impl.dart` - Concrete implementation

#### ❌ What's Missing or Broken

1. **Rendering Services** (CRITICAL):
   - No graph/plot rendering system
   - No geometric shapes (triangles, circles, polygons, FBDs)
   - No vector system (arrows with magnitudes, vector addition)
   - No molecule rendering (atoms, bonds, electron configurations)
   - No coordinate system builder
   - **Impact**: Can't visualize Math, Physics, Chemistry concepts

2. **Animation System** (CRITICAL):
   - Current: Actions rendered in order but not sequential
   - Need: Step 1 → Student responds → Step 2 → etc.
   - Need: Dynamic positioning (top-to-bottom for problem statement, left-to-right for solution steps)
   - Need: Board "scroll" effect (like a real teacher writing more on board)
   - **Impact**: Doesn't feel like a real teacher; feels like static answer dump

3. **Visibility/Rendering Issues**:
   - Some widgets don't appear on screen
   - Problem: Positioned widgets with fixed coordinates might be off-screen
   - Problem: Z-index/stacking context issues with overlapping elements
   - Need: Dynamic layout system (responsive to screen size, orientation)
   - **Impact**: Inconsistent rendering, students can't see all content

4. **Pedagogical System** (MAJOR):
   - No step sequencing (Step 1, Step 2, Step 3 data structure)
   - No student task handling (question, expected answer, validation)
   - No branching logic (correct → next, incorrect → reteach)
   - No hint system
   - **Impact**: Can't implement Socratic teaching method

---

### 2. Backend System (`ai-service/api/`)

#### ✅ What Exists
- FastAPI server with routes for:
  - Session creation
  - Turn processing
  - Board action generation
  - Audio transcription, speech synthesis
- Integration with:
  - Knowledge graph (KuzuDB)
  - AI models (via ModelGateway - Qwen, Gemini, Whisper, Piper, HuBERT)
  - Learning patterns service (spaced repetition, mastery estimation)

#### ❌ What's Missing

1. **Multi-Step Teaching Sequence** (CRITICAL):
   - No `TeachingStep` model (defined in spec but not implemented)
   - No `TeachingSequence` service (generates multi-step plans)
   - No step evaluation (is student response correct?)
   - No adaptive branching (reteach if wrong, next if correct)
   - **Impact**: Can only generate one answer; can't teach step-by-step

2. **Curriculum Database** (CRITICAL):
   - No MOE curriculum data
   - No subject prerequisites
   - No learning outcomes per unit
   - No problem classification system
   - **Impact**: No adaptive learning; can't check if student is ready for topic

3. **Concept Prerequisite System**:
   - Knowledge graph exists but not connected to teaching
   - Can't determine: "Does student know X before teaching Y?"
   - **Impact**: Can teach irrelevant concepts

4. **Subject Experts** (IMPORTANT):
   - No Math-specific teaching patterns
   - No Physics-specific teaching patterns
   - No Chemistry-specific teaching patterns
   - **Impact**: Generic responses; not specialized for each subject

---

### 3. Data Models & Contracts

#### ✅ Defined (in VISUAL_TUTOR_TECHNICAL_SPEC.md)
```
TeachingStep {
  step_id, step_number, learning_objective, concepts
  board_actions: [2-4 actions], spoken_text
  student_task: {type, prompt, expected_answer, hint}
  on_correct, on_incorrect, on_no_response
  hint_progression, is_final_step
}

TeachingSequence {
  sequence_id, problem_instance_id, problem_text
  steps: [TeachingStep]
  current_step_index
}

StudentTask {
  type: free_response | multiple_choice | fill_blank | verification | matching
  prompt, expected_answer, validation_strategy
  choices (for multiple_choice)
}
```

#### ❌ Not Implemented
- No models in `ai-service/api/models/`
- No routes in backend for:
  - POST `/api/v1/visual_tutor/turn_step` - Process one step
  - POST `/api/v1/visual_tutor/evaluate_step` - Check student answer
  - GET `/api/v1/visual_tutor/next_step` - Generate next step with branching

---

## 🎯 Root Cause Analysis

### Why Rendering Fails
```
Issue: Widgets don't always render

Root Causes:
1. Fixed Position Coordinates
   - Actions have hardcoded (x, y) values
   - If board is smaller than expected, content goes off-screen
   - Positioned() widget clips to parent bounds

2. No Visibility/Rendering State
   - Action visibility determined only by `action.hidden` flag
   - No "not yet rendered" state
   - No sequential reveal with animation

3. Z-Index/Stacking Issues
   - Multiple Positioned() children in Stack
   - Overlapping elements conflict
   - No explicit layering strategy

Solution: Use dynamic layout (LayoutBuilder) with responsive positioning
```

### Why Position Animation Doesn't Feel Like Teacher Writing
```
Issue: Can't tell it's being drawn (position is instant, not animated)

Root Causes:
1. No Sequential Timing
   - All actions appear together
   - No "first the problem, then the solution" sequencing
   - Progress parameter exists but not used meaningfully

2. No Spatial Logic
   - Doesn't understand "top to bottom" or "left to right"
   - Teacher writing naturally fills board space
   - UI doesn't plan this

3. Animation is Linear
   - Progress animation is 0→1 instantly for whole board
   - Need separate animation per action
   - Each action should have own start/end timing

Solution: Implement step-based sequencing with per-action timing
```

### Why Solution Shows All At Once (Not Step-by-Step)
```
Issue: Doesn't feel like learning; feels like answer dump

Root Cause:
- Backend generates all actions for complete solution
- Frontend renders all actions in one board state
- No pedagogical "step" concept
- Student doesn't have to think; all answers visible

Solution: Change backend to:
1. Generate Step 1 only (2-4 actions)
2. Ask student question
3. Wait for response
4. Evaluate response
5. Generate Step 2 (adaptive, based on response)
6. Repeat
```

---

## 🔄 Integration Issues

### AI Service → Flutter Communication
```
Current (BROKEN):
┌─────────────┐                ┌──────────────┐
│ AI Service  │ generates ALL  │  Turn        │ POST all
│ (/turn)     │  board actions │  Response    │ actions at once
└─────────────┘                └──────────────┘
       ↓                               ↓
    Response has:                  Flutter renders
    - boardActions: [100 items]     all 100 at once
    - No step info                  (overwhelming)

Needed (CORRECT):
┌──────────────┐  generates  ┌──────────────┐
│ AI Service   │  STEP 1     │  Step        │ Step contains:
│ (/turn_step) │  only       │  Response    │ - 2-4 actions
└──────────────┘             └──────────────┘ - student_task
       ↓                               ↓
    Response has:                  Flutter renders
    - step_number: 1              step 1
    - board_actions: [3 items]    waits for input
    - student_task: {...}         
    - on_correct, on_incorrect

Then:
┌──────────────┐  generates  ┌──────────────┐
│ AI Service   │  STEP 2     │  Step 2      │
│ (/turn_step) │  (adaptive) │  Response    │
│ POST student │             │              │
│ response     │             │              │
└──────────────┘             └──────────────┘
```

---

## 📋 Current Codebase Checklist

### Flutter (`ai_tutor/`)

#### ✅ Complete
- [ ] Color system (done: `visual_tutor_design.dart`)
- [ ] Typography system (done: `visual_tutor_design.dart`)
- [ ] Spacing tokens (done: `visual_tutor_design.dart`)
- [ ] Board paper background (done: `board_element_renderer.dart`)
- [ ] Action types: text, highlight, circle, line, arrow, point, table
- [ ] Basic board layout (done: `live_teaching_board.dart`)

#### 🟡 Partially Done
- [ ] Graph rendering (exists: `graph_board_painter.dart` - too simplistic)
- [ ] Positioned element rendering (works but visibility issues)
- [ ] Animation (exists but not per-action timing)

#### ❌ Missing
- [ ] Graph/plot service (Plotly or Canvas-based)
- [ ] Geometric shape library (triangles, circles, polygons)
- [ ] Vector system (physics arrows)
- [ ] Molecule rendering (chemistry)
- [ ] Coordinate system builder
- [ ] Rich media canvas widget
- [ ] Gesture support (pan, zoom, tap)
- [ ] Responsive layout system
- [ ] Step sequencing UI
- [ ] Student task UI (question, input field, validation)
- [ ] Branching logic UI (showing next step based on correctness)

### Backend (`ai-service/`)

#### ✅ Complete
- [ ] FastAPI framework
- [ ] Knowledge graph integration
- [ ] Model gateway (Qwen, Gemini, etc.)
- [ ] Board action generation (basic)
- [ ] Audio I/O (Whisper, Piper)

#### ❌ Missing
- [ ] `TeachingStep` model
- [ ] `TeachingSequence` service
- [ ] Step evaluation service
- [ ] Adaptive branching logic
- [ ] Curriculum database
- [ ] Subject expert systems (Math, Physics, Chemistry)
- [ ] Concept prerequisite checking
- [ ] Problem classification system
- [ ] Multi-step teaching routes

---

## 🚨 Critical Path to Fix

### Priority 1: Fix Rendering Issues (Hours: 8-12)
**Goal**: Make board reliably render all content in correct positions

**Tasks**:
1. Implement `RichMediaCanvas` widget with LayoutBuilder
   - Dynamic sizing based on parent constraints
   - Responsive positioning (% of available space, not pixels)
   - ScrollView with SingleChildScrollView or CustomScrollView for large boards
   
2. Fix Positioned widget stacking
   - Use explicit indexing for z-order
   - Test on multiple screen sizes
   - Add RepaintBoundary for performance

3. Test rendering with:
   - 5 actions on phone screen
   - 20 actions on tablet
   - Different orientations
   - Different screen sizes

**Validation**: All content visible, no clipping, scales appropriately

---

### Priority 2: Implement Rich Media Renderers (Hours: 40-60)
**Goal**: Render Math, Physics, Chemistry visualizations

**Tasks**:
1. **GraphRenderer** (12-16 hours)
   - Plot functions: f(x) = x^2, sin(x), linear, exponential
   - Plot data points
   - Annotate (labels, arrows, highlights)
   - Support custom domains, ranges
   - Example: Parabola for quadratic equations

2. **GeometricRenderer** (12-16 hours)
   - Triangle (right, equilateral, isosceles)
   - Circle (with radius, center)
   - Rectangle, Polygon
   - Free body diagram (box + force arrows)
   - Angle marking and labels
   - Example: Right triangle for Pythagorean theorem

3. **VectorRenderer** (8-12 hours)
   - Draw vector (point, direction, magnitude)
   - Vector addition (resultant)
   - Component visualization (Vx, Vy)
   - Physics units (Newtons, m/s)
   - Example: Force vectors for statics problem

4. **MoleculeRenderer** (12-16 hours)
   - Atoms (H, C, N, O, S, P, halogens)
   - Single/double/triple bonds
   - Electron configuration
   - 2D Lewis structures
   - Example: H2O, CO2, NH3

5. **CoordinateSystemBuilder** (4-8 hours)
   - X-Y axes with labels
   - Grid option
   - Scale/zoom
   - Rotate (for inclined planes)
   - Example: Tilted axis for incline problems

6. **Tests** (4-8 hours)
   - Unit tests for each renderer
   - Visual regression tests (golden files)
   - Performance benchmarks (<100ms)

**Validation**: Each renderer has 2-3 working examples, tests pass

---

### Priority 3: Implement Step Sequencing (Hours: 20-30)
**Goal**: Render steps one-at-a-time with student interaction

**Tasks**:
1. Create `StepSequenceWidget`
   - Display current step (number, objective)
   - Display board actions for this step
   - Animate with timing (per-action)
   - Show student task (question, input, validation)
   - Next button (enabled after interaction)

2. Implement step-based state machine
   - State: `waiting_for_step` → `rendering_step` → `waiting_for_input` → `evaluating` → `next_step`
   - Emit events for transitions
   - Handle student input (answer submission)

3. Animate board content sequentially
   - First action (top-to-bottom): problem statement
   - Wait 1 second
   - Second action: hint or visualization
   - Wait 0.5 second
   - Third action: student task question
   - Wait for input

4. Test with:
   - 3-step problem (Step 1: Visualize, Step 2: Discover, Step 3: Solve)
   - Student correct answer
   - Student incorrect answer
   - Student timeout

**Validation**: Feels like real teacher guidance, not answer dump

---

### Priority 4: Backend Step Sequencing (Hours: 30-40)
**Goal**: Generate multi-step teaching plans with adaptation

**Tasks**:
1. Implement `TeachingStep` model and data structure
2. Implement `TeachingSequence` service
   - Takes: problem, student_profile, curriculum_context
   - Returns: sequence of 3-5 steps
   - Each step has: board_actions, student_task, on_correct/incorrect

3. Implement step evaluation service
   - Takes: student_response, expected_answer, validation_strategy
   - Returns: is_correct, confidence, misconceptions, feedback

4. Implement adaptive branching
   - If correct: generate next_step
   - If incorrect: reteach (explain differently, simpler)
   - If timeout: show hint then simplified explanation

5. Implement for each subject:
   - Math: algebraic, geometric, trigonometric problems
   - Physics: kinematics, dynamics, energy problems
   - Chemistry: stoichiometry, reactions, molecular structure

6. Test with:
   - Math: Solve 2x + 5 = 13 (3 steps)
   - Physics: Free body diagram problem (4 steps)
   - Chemistry: Balance equation (3 steps)

**Validation**: Backend generates 3-5 steps per problem, adapts to student responses

---

### Priority 5: Curriculum & Adaptation (Hours: 20-30)
**Goal**: Align teaching to Cambodia curriculum with prerequisites

**Tasks**:
1. Build curriculum database
   - MOE standards per subject, grade
   - Learning outcomes per unit
   - Prerequisite chains (e.g., must know "linear equations" before "quadratic")

2. Implement prerequisite checking
   - Before teaching concept X, verify student knows prerequisites
   - If not, generate remedial step

3. Implement problem classification
   - Difficulty (easy, medium, hard)
   - Curriculum unit
   - Skill tags (solve_equation, visualize_graph, etc.)

4. Test with:
   - Grade 10 Linear Equations
   - Grade 11 Quadratic Functions
   - Grade 12 Calculus Basics

**Validation**: System correctly identifies prerequisites and adapts teaching

---

## 📊 Implementation Roadmap (10-12 Weeks)

```
Week 1-2:  Priority 1 + Priority 2.1 (GraphRenderer)
           → Board rendering fixed + graphs work
           
Week 3-4:  Priority 2.2-2.5 (Geometric, Vector, Molecule, Coordinate)
           → All visualizations available
           
Week 5-6:  Priority 3 (Step Sequencing UI)
           → Flutter UI feels like live teacher
           
Week 7-8:  Priority 4 (Backend Step Generation)
           → Full backend pipeline for step teaching
           
Week 9-10: Priority 5 (Curriculum & Adaptation)
           → Aligned to Cambodia MOE curriculum
           
Week 11-12: Integration, Testing, Polish
            → Full system working end-to-end
```

---

## 🎓 Teaching Examples Needed

### Math Problem: Solve 2x + 5 = 13

**Step 1: Visualize**
- Action 1: Write equation "2x + 5 = 13"
- Action 2: Draw number line (visual context)
- Board shows: Equation with highlighting
- Student Task: "What do you notice about this equation?"

**Step 2: Discover**
- Action 1: Highlight "+5" with color
- Action 2: Draw bracket showing "+5"
- Board shows: Problem element highlighted
- Student Task: "What needs to happen to undo +5?"
- Expected: "Subtract 5" or "Subtract 5 from both sides"
- If correct: Go to Step 3
- If incorrect: Hint "Think about inverse operations"

**Step 3: Solve**
- Action 1: Show "2x + 5 - 5 = 13 - 5"
- Action 2: Simplify to "2x = 8"
- Board shows: Transformation animation
- Student Task: "Now what do you need to do?"
- Expected: "Divide by 2" or "Divide both sides by 2"

**Step 4: Verify**
- Action 1: Show "x = 4"
- Action 2: Check "2(4) + 5 = 8 + 5 = 13 ✓"
- Board shows: Solution with verification
- Student Task: Final answer is x = 4

### Physics Problem: Free Body Diagram

**Step 1: Visualize**
- Action 1: Draw object (box/circle)
- Action 2: Draw all forces (Normal, Weight, Applied, Friction)
- Board shows: FBD with all forces as arrows
- Student Task: "Label the forces"

**Step 2: Analyze**
- Action 1: Break into horizontal/vertical components
- Action 2: Write equations (ΣFx = max, ΣFy = 0)
- Board shows: Components and Newton's 2nd law
- Student Task: "Are there unbalanced forces?"

### Chemistry Problem: Lewis Structure of CO₂

**Step 1: Count Electrons**
- Action 1: Show atoms: C (4 valence), O (6 valence each)
- Action 2: Total = 4 + 6 + 6 = 16 electrons
- Board shows: Valence electron count
- Student Task: "How many electron pairs?"

**Step 2: Draw Bonds**
- Action 1: Connect atoms: O=C=O (double bonds)
- Action 2: Show lone pairs on oxygens
- Board shows: Lewis structure
- Student Task: "Count electrons around each atom"

---

## 🔧 Technical Decisions to Make

### 1. Graph/Plot Library
**Options**:
- ✅ **Plotly.dart** (ideal) - Interactive, many features, web support
- ❌ **fl_chart** - Limited, less suitable for math functions
- 🟡 **Custom Canvas** - Full control but more work
- 🟡 **Charts package** - Material design focused

**Recommendation**: Use Plotly.dart for graphs, custom Canvas for shapes

### 2. Animation Approach
**Options**:
- ✅ **AnimationController + Tween** (ideal) - Per-action timing, smooth
- 🟡 **Implicit animations** - Simpler but less control
- 🟡 **GestureDetector + manual position** - Over-engineered

**Recommendation**: AnimationController with per-action tween composition

### 3. State Management
**Options**:
- ✅ **Provider** (current) - Already used in project
- 🟡 **Riverpod** - Better but migration cost
- 🟡 **BLoC** - Overkill for this scope

**Recommendation**: Keep Provider, add step-based state layer

### 4. Layout System
**Options**:
- ✅ **LayoutBuilder + Positioned** (current approach with fixes)
- 🟡 **CustomMultiChildLayout** - More control but complex
- 🟡 **Stack + Align** - Simpler but less flexible

**Recommendation**: LayoutBuilder + SingleChildScrollView for overflow

---

## 🎯 Success Criteria

### Phase 0.1 (Board Rendering) - DONE when:
- [ ] All content renders on screen (no clipping)
- [ ] Content scales responsively (phone, tablet, web)
- [ ] Performance <100ms render time
- [ ] Tests cover >80% of code
- [ ] No compiler warnings

### Phase 0.2 (Rich Media) - DONE when:
- [ ] Graph: Can plot f(x) = x^2, sin(x), data points
- [ ] Geometric: Can draw triangle, circle, FBD, angles
- [ ] Vector: Can show force vectors with magnitudes
- [ ] Molecule: Can draw H2O, CO2, NH3 structures
- [ ] All with labels, annotations, styling
- [ ] Tests pass, <100ms render time

### Phase 0.3 (Step Sequencing) - DONE when:
- [ ] Step 1 renders, student answers question
- [ ] Step 2 generates based on response (correct or incorrect path)
- [ ] Feels like real teacher guiding discovery
- [ ] Student can't see full answer (prevents cheating)

### Phase 1 (Math Specific) - DONE when:
- [ ] Can teach: linear equations, quadratics, geometry, trigonometry
- [ ] Each problem has 3-5 step sequence
- [ ] Adapts to student response (correct, incorrect, timeout)
- [ ] Shows visualizations (graphs, diagrams)

---

## 📋 Immediate Next Steps

### This Week:
1. **Review & Clarify**:
   - [ ] Confirm rendering issues (reproduce with small example)
   - [ ] Identify exact positioning problem
   - [ ] Check asset loading (Khmer fonts, images)

2. **Create Audit Prompt for AI**:
   - [ ] Document current issues in prompt format
   - [ ] Include code snippets showing problems
   - [ ] Ask AI to diagnose root causes

3. **Plan Phase 0.1 Fix**:
   - [ ] Design responsive layout system
   - [ ] Create test cases for rendering
   - [ ] Estimate effort for each issue

### Next 2 Weeks:
1. **Fix Rendering** (8-12 hours):
   - Implement RichMediaCanvas with dynamic layout
   - Test on multiple devices
   - Fix visibility issues

2. **Start Rich Media** (16-20 hours):
   - Implement GraphRenderer
   - Add Plotly.dart to pubspec.yaml
   - Create test graphs

3. **Document Progress**:
   - Update VISUAL_TUTOR_IMPLEMENTATION_LOG.md
   - Track blockers
   - Plan adjustments

---

## 📝 How to Use This Audit

### For AI Implementation (Claude/Codex)

When running implementation prompts, reference this document:

```
"Following the audit in VISUAL_TUTOR_AUDIT_CURRENT_STATE.md:
- Current rendering issues: [specific issue]
- Missing: [component]
- Root cause: [from analysis]
- Implementation approach: [from roadmap]"
```

### For Code Review

Check against criteria:
- ✅ Addressing root cause (not symptoms)
- ✅ Following architecture in TECHNICAL_SPEC.md
- ✅ Tests included
- ✅ No compiler warnings
- ✅ Follows Dart best practices

### For Progress Tracking

Update `Status` field in sections:
- ❌ Not started
- 🟡 In progress
- ✅ Complete
- 🔧 Needs review

---

## 🚀 Launch Checklist

**Before claiming "Visual Tutor Ready"**:

- [ ] Board renders reliably on all screen sizes
- [ ] Step 1: Visualize problem (graph/diagram)
- [ ] Student can answer question
- [ ] Step 2: Generated based on student answer (adaptive)
- [ ] Feels like learning with teacher (not reading answer)
- [ ] Works on iOS, Android, and Web
- [ ] Khmer language supported
- [ ] Performance acceptable (<100ms per step)
- [ ] Tests pass (>80% coverage)
- [ ] Documentation complete
- [ ] Ready for user testing

---

## 📚 Reference Documents

- `VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md` - Vision and teaching patterns
- `VISUAL_TUTOR_TECHNICAL_SPEC.md` - Data models and API contracts
- `VISUAL_TUTOR_QUICK_START.md` - Code examples
- `AI_IMPLEMENTATION_PROMPTS.md` - Prompts for Claude/Codex
- `VISUAL_TUTOR_MASTER_INDEX.md` - Complete reference index

---

**Last Updated**: August 26, 2024  
**Next Review**: When Priority 1 (Rendering Fix) is complete
