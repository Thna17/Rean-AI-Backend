# AI Visual Tutor - Detailed Implementation Plan

**Project**: AI Visual Tutor for Cambodia Grade 10-12  
**Timeline**: 10-12 weeks (200+ hours)  
**Status**: Phase 0 - Foundation  
**Updated**: August 26, 2024

---

## Table of Contents

1. [Problem Statement & Vision](#problem-statement--vision)
2. [Architecture Overview](#architecture-overview)
3. [Phase-by-Phase Breakdown](#phase-by-phase-breakdown)
4. [Detailed Implementation Guide](#detailed-implementation-guide)
5. [Code Examples & Patterns](#code-examples--patterns)
6. [Testing Strategy](#testing-strategy)
7. [Validation Criteria](#validation-criteria)
8. [Risk Management](#risk-management)

---

## Problem Statement & Vision

### The Challenge
Students use ChatGPT/Claude for homework help, but:
- ❌ Feels like reading a textbook (passive)
- ❌ Can't visualize concepts (graphs, diagrams, forces)
- ❌ No guidance ("here's the full answer")
- ❌ No interaction (student just reads)
- ❌ Not adapted to student's thinking
- ❌ No depth for visual learners (Math, Physics, Chemistry)

### The Solution
**AI Visual Tutor**: Real teacher with interactive whiteboard that:
- ✅ Draws problems on board (graphs, diagrams, equations)
- ✅ Asks questions first (Socratic method)
- ✅ Waits for student response
- ✅ Adapts teaching based on answer
- ✅ Explains through visualization (not just text)
- ✅ Makes student discover answers (not reveal them)

### Target Users
- **Who**: Cambodia Grade 10-12 students
- **Subjects**: Mathematics, Physics, Chemistry
- **Usage**: Homework help with live tutor experience
- **Language**: Khmer (with English fallback)
- **Access**: Web (primary), iOS/Android (secondary)

---

## Architecture Overview

### System Layers (Bottom to Top)

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Student-Board Interaction                    │
│  • Interactive whiteboard UI                           │
│  • Student input (typing, voice, gesture)              │
│  • Real-time feedback                                  │
└─────────────────────────────────────────────────────────┘
                      ↑↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Teaching Orchestration                       │
│  • Step sequencing (Step 1 → Step 2 → Step 3)          │
│  • Socratic questioning                                │
│  • Adaptive branching (correct vs incorrect)           │
│  • Hint progression                                    │
│  • Subject-specific patterns (Math/Physics/Chemistry) │
└─────────────────────────────────────────────────────────┘
                      ↑↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Rich Media Rendering                         │
│  • Graphs & plots (functions, data points)             │
│  • Geometric shapes (triangles, circles, polygons)     │
│  • Physics vectors (forces, acceleration, etc.)       │
│  • Chemistry molecules (atoms, bonds, structures)      │
│  • Coordinate systems (with labels, scales)           │
│  • Animations & transitions                           │
└─────────────────────────────────────────────────────────┘
                      ↑↓
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Knowledge & Curriculum                       │
│  • Cambodia MOE curriculum database                    │
│  • Subject prerequisites (concept graph)              │
│  • Problem bank (classified by difficulty, topic)     │
│  • Learning outcomes & standards                       │
│  • Student mastery profiles                           │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

```
Student Input
    ↓
┌───────────────────┐
│ Backend: Turn     │  1. Receive problem
│ Processor         │  2. Classify by curriculum
└───────────────────┘  3. Plan teaching steps
    ↓
┌───────────────────┐
│ Backend: Step     │  1. Generate Step 1
│ Generator         │  2. Create board actions
└───────────────────┘  3. Plan student task
    ↓
Flutter: Render Step 1
    ↓
┌───────────────────┐
│ Student Task      │  Student answers question
│ (Question UI)     │
└───────────────────┘
    ↓
┌───────────────────┐
│ Backend: Step     │  1. Evaluate answer
│ Evaluator         │  2. Check if correct
└───────────────────┘  3. Detect misconceptions
    ↓
Student Response: Correct → Next Step
Student Response: Incorrect → Reteach/Hint
Student Response: No input → Timeout → Hint
    ↓
Back to Step Generator (repeat)
```

### Technology Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Frontend | Flutter 3.x + Dart 3.x | Cross-platform (iOS, Android, Web) |
| Backend | FastAPI + Python 3.11+ | Async, fast, type-safe |
| Database | MongoDB | Flexible document structure |
| Graph DB | KuzuDB | Knowledge graph (concepts, prerequisites) |
| AI Models | Claude/GPT-4 (via API) | Step generation, evaluation, adaptation |
| Graph Rendering | Plotly.dart or custom Canvas | Math functions, data visualization |
| Shape Rendering | Flutter CustomPaint | Geometric shapes, vectors, molecules |
| State Management | Provider | Reactive UI updates |
| Testing | flutter_test + pytest | Unit, integration, visual tests |

---

## Phase-by-Phase Breakdown

### Phase 0: Foundation (Weeks 1-2)

**Goal**: Build core infrastructure for step-based teaching

#### Phase 0.1: Board Rendering System
**Hours**: 8-12  
**Priority**: CRITICAL

**Tasks**:
1. Diagnose & fix rendering issues
   - Reproduce visibility problems
   - Identify positioning bugs
   - Check for off-screen content

2. Implement RichMediaCanvas widget
   - Use LayoutBuilder for responsive sizing
   - Implement dynamic positioning (not fixed pixels)
   - Add ScrollView for large boards
   - Test on multiple screen sizes

3. Create responsive position system
   - % of board width/height (not pixels)
   - Handle orientation changes
   - Support mobile (320px) to desktop (1920px)

4. Test rendering
   - Unit tests for position calculation
   - Visual tests (golden files) on multiple devices
   - Performance benchmarks (<100ms)

**Success Criteria**:
- ✅ All actions render on screen
- ✅ No clipping, no off-screen content
- ✅ Scales to any screen size
- ✅ Performance acceptable

**Deliverables**:
- `lib/features/visual_tutor/presentation/widgets/rich_media_canvas.dart`
- Updated `live_teaching_board.dart` (use RichMediaCanvas)
- Test file: `test/features/visual_tutor/presentation/widgets/rich_media_canvas_test.dart`
- Documentation with examples

---

#### Phase 0.2: Rich Media Rendering Services
**Hours**: 40-60  
**Priority**: CRITICAL

**Tasks**:

##### 0.2.1: GraphRenderer (12-16 hours)
Renders mathematical functions and data plots

**Deliverable**: `lib/features/visual_tutor/presentation/services/graph_renderer.dart`

```dart
class GraphRenderer {
  // Plot a mathematical function
  static Widget plotFunction(
    String expression,  // e.g., "x^2", "sin(x)"
    {
    double xMin = -10,
    double xMax = 10,
    double yMin = -10,
    double yMax = 10,
    Color lineColor = Colors.blue,
    double lineWidth = 2,
    String? xLabel,
    String? yLabel,
    bool showGrid = true,
  }) { }

  // Plot data points
  static Widget plotPoints(
    List<Point> points,
    {
    PointStyle? style,
    bool connectLines = false,
    String? colorByField,
  }) { }

  // Plot dataset (line, bar, scatter, histogram)
  static Widget plotDataset(
    Dataset data,
    String type,
    {String? title, String? xLabel, String? yLabel},
  ) { }

  // Add annotations
  static Widget annotate(
    Widget graph,
    String text,
    Point position,
    {ArrowStyle? arrow},
  ) { }

  // Highlight region
  static Widget highlightRegion(
    Widget graph,
    double xStart,
    double xEnd,
    Color color,
  ) { }
}
```

**Examples to implement**:
- Parabola: f(x) = x²
- Sine wave: f(x) = sin(x)
- Linear: f(x) = 2x + 1
- Exponential: f(x) = e^x
- Circle data: plotting (x,y) points

**Test cases**:
- Render function in domain [-10, 10]
- Plot 50 data points
- Add title and axis labels
- Highlight region [2, 4]

---

##### 0.2.2: GeometricRenderer (12-16 hours)
Renders geometric shapes and diagrams

**Deliverable**: `lib/features/visual_tutor/presentation/services/geometric_renderer.dart`

```dart
class GeometricRenderer {
  // Basic shapes
  static Widget drawTriangle(
    Point p1, Point p2, Point p3,
    {
    Color? fillColor,
    Color? strokeColor = Colors.black,
    double strokeWidth = 2,
    Map<String, String>? labels,  // "p1" -> "A", etc.
    bool rightAngle = false,
  }) { }

  static Widget drawCircle(
    Point center,
    double radius,
    {
    Color? fillColor,
    Color? strokeColor = Colors.black,
    double strokeWidth = 2,
    String? label,
    bool showRadius = false,
  }) { }

  static Widget drawRectangle(
    Point topLeft,
    double width,
    double height,
    {Color? fillColor, Color? strokeColor, double strokeWidth = 2},
  ) { }

  static Widget drawPolygon(
    List<Point> vertices,
    {Color? fillColor, Color? strokeColor, double strokeWidth = 2},
  ) { }

  // Physics diagrams
  static Widget drawFreeBodybody(
    Point objectCenter,
    double objectRadius,
    List<NamedVector> forces,
    {
    String? objectLabel,
    double forceScale = 1.0,
    bool showMagnitudes = true,
  }) { }

  // Angles
  static Widget drawAngle(
    Point vertex,
    Vector vector1,
    Vector vector2,
    {
    bool showArc = true,
    String? label,
    Color? arcColor = Colors.blue,
  }) { }

  // Annotations
  static Widget addLabel(
    Widget shape,
    String text,
    Point position,
    {TextStyle? style},
  ) { }
}

class NamedVector {
  final String name;  // "F" for force
  final Vector vector;
  final String? unit;  // "N", "m/s", etc.
}
```

**Examples to implement**:
- Right triangle with 3-4-5 sides
- Equilateral triangle
- Circle with center point
- Rectangle with width/height labels
- Free body diagram (box with Normal, Weight, Applied, Friction forces)
- Angle marking (arc with degree label)

**Test cases**:
- Draw right triangle, check side lengths
- Draw FBD with 4 forces
- Mark 60° angle
- Label all vertices

---

##### 0.2.3: VectorRenderer (8-12 hours)
Renders physics vectors (forces, velocity, acceleration)

**Deliverable**: `lib/features/visual_tutor/presentation/services/vector_renderer.dart`

```dart
class VectorRenderer {
  // Single vector
  static Widget drawVector(
    Point origin,
    Vector vector,
    {
    Color color = Colors.red,
    String? label,
    String? unit,  // "N", "m/s"
    double magnitude,
    double arrowHeadSize = 10,
    bool showMagnitude = true,
  }) { }

  // Vector addition (A + B = R)
  static Widget drawVectorAddition(
    List<Vector> vectors,
    Vector resultant,
    {
    List<Color>? colors,
    List<String>? labels,
    bool showComponents = false,
  }) { }

  // Component vectors (Vx, Vy)
  static Widget drawComponents(
    Vector vector,
    {
    bool showX = true,
    bool showY = true,
    Color xColor = Colors.red,
    Color yColor = Colors.blue,
  }) { }

  // Coordinate system
  static Widget drawCoordinateSystem(
    Point origin,
    {
    double xMax = 10,
    double yMax = 10,
    String? xLabel,
    String? yLabel,
    double rotation = 0,  // For inclined planes
    bool showGrid = true,
  }) { }
}

class Vector {
  final double magnitude;
  final double angleRadians;  // From x-axis

  double get vx => magnitude * cos(angleRadians);
  double get vy => magnitude * sin(angleRadians);
}
```

**Examples to implement**:
- Force vector: 20N @ 30° (shows Fx=17.3N, Fy=10N)
- Two forces: 10N @ 0° + 10N @ 90° = 14.14N @ 45°
- Velocity on incline (rotated coordinate system)

**Test cases**:
- Draw 20N force vector
- Show vector addition (correct resultant)
- Component breakdown

---

##### 0.2.4: MoleculeRenderer (12-16 hours)
Renders chemistry molecular structures

**Deliverable**: `lib/features/visual_tutor/presentation/services/molecule_renderer.dart`

```dart
class MoleculeRenderer {
  // Atoms
  static Widget drawAtom(
    String element,  // "H", "C", "N", "O", etc.
    Point position,
    {
    bool showElectrons = false,
    bool highlight = false,
    double electronOrbitRadius = 40,
  }) { }

  // Bonds
  static Widget drawBond(
    Atom atom1,
    Atom atom2,
    {
    BondType type = BondType.single,  // single, double, triple
    Color color = Colors.black,
    double bondLength = 50,
  }) { }

  // Complete molecule
  static Widget drawMolecule(
    Molecule molecule,
    {
    bool showElectrons = false,
    bool show2D = true,
    bool showBondAngles = false,
    double scale = 1.0,
  }) { }

  // Electron configuration
  static Widget drawElectronConfiguration(
    String element,
    {String? title},
  ) { }
}

class Atom {
  final String element;
  final Point position;
  final int valence;
  final int atomicNumber;

  // Get color based on element
  Color get atomicColor => _elementColors[element] ?? Colors.grey;
}

class Molecule {
  final String formula;  // "H2O", "CO2"
  final List<Atom> atoms;
  final List<Bond> bonds;

  // Predefined molecules
  static final water = Molecule(...);
  static final carbonDioxide = Molecule(...);
  static final ammonia = Molecule(...);
}

enum BondType { single, double, triple }
```

**Examples to implement**:
- Water (H2O): bent structure with O in middle
- Carbon dioxide (CO2): linear O=C=O
- Ammonia (NH3): pyramidal with N and 3 H
- Methane (CH4): tetrahedral

**Test cases**:
- Draw H2O with correct geometry
- Show electron pairs on oxygen
- Count valence electrons

---

##### 0.2.5: CoordinateSystemBuilder (4-8 hours)
Builds and annotates coordinate systems

**Deliverable**: `lib/features/visual_tutor/presentation/services/coordinate_system_renderer.dart`

```dart
class CoordinateSystemRenderer {
  static Widget buildSystem(
    {
    double xMin = -10,
    double xMax = 10,
    double yMin = -10,
    double yMax = 10,
    String? xLabel = "x",
    String? yLabel = "y",
    bool showGrid = true,
    double rotation = 0,  // For inclines
    String? title,
  }) { }

  static Widget withAngle(
    Widget system,
    double angleDegrees,
    {String? label},
  ) { }

  static Widget markPoint(
    Widget system,
    Point point,
    {String? label, Color? color},
  ) { }
}
```

**Examples**:
- Standard xy-plane
- Tilted axis (for incline problems)
- Point marking

---

##### 0.2.6: Tests (4-8 hours)

**Test file**: `test/features/visual_tutor/presentation/services/`

```
graph_renderer_test.dart
├── test_plot_function()
├── test_plot_points()
├── test_with_annotations()
└── test_performance()

geometric_renderer_test.dart
├── test_triangle_rendering()
├── test_fbd_rendering()
├── test_angle_marking()
└── test_performance()

vector_renderer_test.dart
├── test_vector_direction()
├── test_vector_addition()
├── test_components()
└── test_performance()

molecule_renderer_test.dart
├── test_water_structure()
├── test_carbon_dioxide()
├── test_electron_config()
└── test_performance()

rich_media_canvas_test.dart
├── test_responsive_sizing()
├── test_action_sequencing()
├── test_multiple_renderers()
└── test_performance()
```

**Coverage Target**: >80% of code

---

#### Phase 0.3: Step Sequencing Data Model
**Hours**: 8-12  
**Priority**: HIGH

**Task**: Define data structures for multi-step teaching

**Deliverables**:
- Backend: `ai-service/api/models/teaching_step.py`
- Flutter: `ai_tutor/lib/features/visual_tutor/domain/entities/teaching_step_entity.dart`
- API routes: `/api/v1/visual_tutor/turn_step`, `/api/v1/visual_tutor/evaluate_step`

**Key Models**:
```python
# Backend
class TeachingStep(BaseModel):
    step_id: str
    step_number: int
    learning_objective: str
    board_actions: List[BoardAction]  # 2-4 actions per step
    spoken_text: str  # What tutor says
    student_task: StudentTask  # Question for student
    on_correct: str  # "next_step", "final_answer", etc.
    on_incorrect: str  # "reteach", "hint", "simpler"
    is_final_step: bool

class TeachingSequence(BaseModel):
    sequence_id: str
    problem_id: str
    steps: List[TeachingStep]
    current_step_index: int
```

**Success Criteria**:
- ✅ Models defined for both frontend and backend
- ✅ API contracts clear
- ✅ Examples documented (3-step problem, 4-step problem)

---

### Phase 1: Math Teaching System (Weeks 3-4)

**Goal**: Implement complete teaching for Math topics

**Hours**: 40-60

#### Phase 1.1: Algebra Teaching
- Linear equations: Solve 2x + 5 = 13
- Quadratic equations: Solve x² - 5x + 6 = 0
- Systems: Solve 2x + y = 5, x - y = 1

#### Phase 1.2: Geometry Teaching
- Pythagorean theorem
- Triangle properties
- Circle theorems
- Area and perimeter

#### Phase 1.3: Trigonometry Teaching
- Basic trig ratios (sin, cos, tan)
- Special angles (30°, 45°, 60°)
- Solving triangles

**Deliverables for Each Topic**:
1. Problem bank (5-10 problems per topic)
2. Teaching sequence generator (backend)
3. Board visualization system
4. Student interaction UI
5. Tests covering >80% of code

**Test Coverage**:
- Unit tests for step generation
- Integration tests (student response → next step)
- Visual tests (board rendering)
- Performance tests (<100ms per step)

---

### Phase 2: Physics Teaching System (Weeks 5-6)

**Goal**: Implement complete teaching for Physics topics

**Hours**: 40-60

#### Phase 2.1: Kinematics
- Motion with constant acceleration
- Graphical analysis (v-t, x-t graphs)
- Free fall

#### Phase 2.2: Dynamics
- Newton's laws
- Free body diagrams
- Force analysis
- Friction and tension

#### Phase 2.3: Energy
- Work and kinetic energy
- Potential energy
- Conservation of energy

**Deliverables for Each Topic**:
1. Physics-specific visualizations (graphs, diagrams, vectors)
2. Equation rendering system (with units)
3. Vector analysis (force components, resultants)
4. Problem solver backend
5. Tests

---

### Phase 3: Chemistry Teaching System (Weeks 7-8)

**Goal**: Implement complete teaching for Chemistry topics

**Hours**: 40-60

#### Phase 3.1: Atomic Structure
- Electron configuration
- Lewis structures
- Molecular geometry

#### Phase 3.2: Chemical Reactions
- Balancing equations
- Stoichiometry
- Types of reactions

#### Phase 3.3: Equilibrium & Kinetics
- Chemical equilibrium
- Le Chatelier's principle
- Reaction rates

**Deliverables for Each Topic**:
1. Molecule visualization system
2. Equation balancing helper
3. Stoichiometry calculator
4. Equilibrium visualization
5. Tests

---

### Phase 4: Curriculum & Adaptation (Weeks 9-10)

**Goal**: Align to Cambodia MOE curriculum with adaptation

**Hours**: 30-40

#### Phase 4.1: Curriculum Database
- Grade 10 topics (Algebra, Geometry, Physics basics)
- Grade 11 topics (Trig, Conic sections, Dynamics)
- Grade 12 topics (Calculus, Energy, Chemistry)
- Prerequisite chains

#### Phase 4.2: Mastery & Adaptation
- Track student mastery per concept
- Adapt problem difficulty
- Skip already-mastered steps
- Reteach if confidence low

#### Phase 4.3: Khmer Language Support
- Translate all UI text
- Khmer font support
- Culturally appropriate examples

**Deliverables**:
1. Curriculum database
2. Mastery tracking system
3. Adaptive path generator
4. i18n infrastructure
5. Tests

---

### Phase 5: Integration & Polish (Weeks 11-12)

**Goal**: Full end-to-end system with quality

**Hours**: 20-30

#### Phase 5.1: Integration Testing
- Full flow: problem → steps → solution
- All platforms: iOS, Android, Web
- All subjects: Math, Physics, Chemistry

#### Phase 5.2: Performance Optimization
- Render time <100ms
- Network latency <1s per step
- Memory usage acceptable
- Battery impact minimal

#### Phase 5.3: User Testing
- Beta test with students
- Gather feedback
- Fix issues
- Iterate on teaching patterns

#### Phase 5.4: Documentation
- API documentation
- Frontend component guide
- Teaching pattern examples
- Deployment guide

---

## Detailed Implementation Guide

### How to Implement Each Phase

#### Step 1: Read & Understand
1. Review the audit document (VISUAL_TUTOR_AUDIT_CURRENT_STATE.md)
2. Review the technical spec (VISUAL_TUTOR_TECHNICAL_SPEC.md)
3. Review code examples (VISUAL_TUTOR_QUICK_START.md)
4. Identify any gaps or questions

#### Step 2: Design the Solution
1. Create data models (Dart entities, Python pydantic models)
2. Design the API contracts (request/response)
3. Plan the UI/UX flow
4. Create test cases

#### Step 3: Implement
1. Write backend (Python)
2. Write frontend (Dart/Flutter)
3. Write tests (pytest + flutter_test)
4. Commit to git with clear messages

#### Step 4: Validate
1. Run tests locally
2. Test on multiple devices
3. Test on multiple platforms (iOS, Android, Web)
4. Check performance
5. Check code style/linting

#### Step 5: Document
1. Add inline documentation (docstrings, comments)
2. Update VISUAL_TUTOR_IMPLEMENTATION_LOG.md
3. Update this plan with actual hours/effort

---

## Code Examples & Patterns

### Flutter: RichMediaCanvas Widget

```dart
class RichMediaCanvas extends StatefulWidget {
  final VisualTutorBoardEntity? board;
  final List<VisualTutorBoardActionEntity> actions;
  final Animation<double> animation;
  final bool reducedMotion;

  @override
  State<RichMediaCanvas> createState() => _RichMediaCanvasState();
}

class _RichMediaCanvasState extends State<RichMediaCanvas>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      duration: Duration(milliseconds: 500),
      vsync: this,
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = constraints.maxWidth;
        final height = constraints.maxHeight;

        return SingleChildScrollView(
          child: BoardPaperScaffold(
            child: Stack(
              children: [
                // Render board actions dynamically
                for (final action in widget.actions)
                  _renderAction(
                    action,
                    width,
                    height,
                  ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _renderAction(
    VisualTutorBoardActionEntity action,
    double boardWidth,
    double boardHeight,
  ) {
    if (action.hidden) return const SizedBox.shrink();

    // Calculate responsive position (% of board, not pixels)
    final x = (action.x ?? 0) / 100 * boardWidth;
    final y = (action.y ?? 0) / 100 * boardHeight;
    final width = ((action.width ?? 0) / 100 * boardWidth).clamp(0, boardWidth);
    final height = (action.height ?? 42).toDouble();

    return switch (action.type) {
      'graph' => _renderGraph(action, x, y, width, height),
      'shape' => _renderShape(action, x, y, width, height),
      'vector' => _renderVector(action, x, y, width, height),
      'molecule' => _renderMolecule(action, x, y, width, height),
      _ => BoardElementRenderer(action: action),
    };
  }

  Widget _renderGraph(action, x, y, width, height) {
    return Positioned(
      left: x,
      top: y,
      width: width,
      height: height,
      child: GraphRenderer.plot(
        action.metadata['expression'] as String,
        xMin: -10,
        xMax: 10,
      ),
    );
  }

  // Similar methods for _renderShape, _renderVector, _renderMolecule
}
```

### Backend: TeachingSequenceService

```python
from typing import List
from pydantic import BaseModel

class TeachingSequenceService:
    """Generate multi-step teaching plans."""

    async def generate_sequence(
        self,
        problem: str,
        subject: str,
        student_profile: StudentProfile,
    ) -> TeachingSequence:
        """
        Generate 3-5 step teaching plan.

        Flow:
        1. Classify problem (algebra, geometry, etc.)
        2. Plan prerequisite checks
        3. Generate Step 1: Visualize
        4. Generate Step 2: Discover
        5. Generate Step 3: Solve (student must answer)
        6. Generate Step 4: Verify (if needed)
        """

        # Step 1: Classify problem
        classification = await self._classify(problem, subject)

        # Step 2: Check prerequisites
        prerequisites = classification["prerequisites"]
        student_ready = await self._check_readiness(
            student_profile, prerequisites
        )
        if not student_ready:
            # Add remedial step
            return self._generate_remedial_sequence(
                classification, student_profile
            )

        # Step 3: Plan sequence
        steps = await self._plan_steps(problem, classification)

        # Step 4: Generate board actions for each step
        for i, step in enumerate(steps):
            step.board_actions = await self._generate_board_actions(
                step, problem
            )
            step.student_task = await self._generate_student_task(step)

        return TeachingSequence(
            sequence_id=str(uuid.uuid4()),
            problem_id=problem,
            steps=steps,
        )

    async def evaluate_step(
        self,
        step_id: str,
        student_response: str,
        expected_answer: str,
    ) -> StepEvaluation:
        """Check if student response is correct."""
        # LLM-based evaluation
        is_correct = await self._evaluate_with_llm(
            student_response, expected_answer
        )

        return StepEvaluation(
            step_id=step_id,
            is_correct=is_correct,
            feedback=await self._generate_feedback(is_correct),
        )
```

### Testing Pattern: Unit Test for GraphRenderer

```dart
void main() {
  group('GraphRenderer', () {
    test('plotFunction renders parabola correctly', () {
      final graph = GraphRenderer.plotFunction(
        'x^2',
        xMin: -5,
        xMax: 5,
      );

      expect(find.byType(CustomPaint), findsWidgets);
      expect(graph, isNotNull);
    });

    test('plotPoints connects data correctly', () {
      final points = [
        Point(0, 0),
        Point(1, 1),
        Point(2, 4),
      ];

      final graph = GraphRenderer.plotPoints(
        points,
        connectLines: true,
      );

      expect(graph, isNotNull);
      // Could add visual regression test with golden files
    });

    test('renders in <100ms', () {
      final stopwatch = Stopwatch()..start();

      GraphRenderer.plotFunction('sin(x)');

      stopwatch.stop();
      expect(stopwatch.elapsedMilliseconds, lessThan(100));
    });
  });
}
```

---

## Testing Strategy

### Test Pyramid

```
         /\
        /  \  Integration Tests (10%)
       /    \
      /______\ Unit Tests (60%)
     /        \ Widget Tests (20%)
    /          \
   /____________\ Golden/Visual Tests (10%)
```

### Test Scope

1. **Unit Tests** (60%)
   - Renderer functions (graph, geometric, vector, molecule)
   - Position calculation logic
   - Data model serialization
   - Step generation logic
   - Evaluation logic

2. **Widget Tests** (20%)
   - RichMediaCanvas rendering
   - Step UI components
   - Student task UI
   - Animation behavior

3. **Integration Tests** (10%)
   - Full flow: problem → steps → solution
   - Backend integration (API calls)
   - End-to-end teaching sequence

4. **Golden/Visual Tests** (10%)
   - Graph rendering (golden files)
   - Geometric shape rendering
   - Molecule structure rendering
   - Vector diagrams

### Test Tools

- **Backend**: pytest + fixtures
- **Frontend**: flutter_test + mockito
- **Performance**: Benchmark via stopwatch
- **Visual**: Golden files (flutter test --update-goldens)

---

## Validation Criteria

### Code Quality
- ✅ Follows analysis_options.yaml (Dart)
- ✅ No compiler warnings
- ✅ No linting errors
- ✅ Test coverage >80%
- ✅ Documentation complete

### Functionality
- ✅ Rendering works reliably
- ✅ Performance <100ms per action
- ✅ Animations smooth (60fps)
- ✅ Works on iOS, Android, Web
- ✅ Responsive to screen size

### Pedagogy
- ✅ Feels like live teacher (not static answer)
- ✅ Step-by-step learning (not overwhelming)
- ✅ Student engagement (questions before answers)
- ✅ Adaptive (different paths for correct/incorrect)

### User Experience
- ✅ Visually appealing (colors, spacing, fonts)
- ✅ Khmer language support
- ✅ Intuitive interactions
- ✅ Fast responsiveness (no lag)

---

## Risk Management

### Risk 1: Rendering Issues Persist
**Probability**: Medium  
**Impact**: High (blocks progression)

**Mitigation**:
- Diagnose root cause first (don't guess)
- Implement simple test case
- Fix in isolation before moving on
- Add tests to prevent regression

---

### Risk 2: Rich Media Rendering Slow
**Probability**: Medium  
**Impact**: Medium (bad UX)

**Mitigation**:
- Profile early (use DevTools)
- Use RepaintBoundary for optimization
- Cache rendered outputs where appropriate
- Simplify visuals if needed

---

### Risk 3: Step Sequencing Complexity
**Probability**: High  
**Impact**: High (core feature)

**Mitigation**:
- Start with simple 3-step problem
- Test in isolation
- Build complexity incrementally
- Document edge cases

---

### Risk 4: LLM Quality (Step Generation)
**Probability**: Medium  
**Impact**: High (teaching quality)

**Mitigation**:
- Use few-shot examples (show LLM good sequences)
- Validate generated steps before rendering
- Have fallback explanations
- Iterate on prompts

---

### Risk 5: Curriculum Data Incomplete
**Probability**: High  
**Impact**: Medium (affects adaptation)

**Mitigation**:
- Start with one subject (Math)
- Expand gradually
- Get MOE curriculum official sources
- Crowdsource from teachers if needed

---

## How to Use This Plan

### For Implementation (with Claude/Codex)

When running prompts with AI, reference this plan:

```
"Following the implementation plan in VISUAL_TUTOR_IMPLEMENTATION_PLAN.md:
- Phase 0.2.1 (GraphRenderer): [specific task]
- Requirements: [from plan]
- Success criteria: [from plan]
- Examples to implement: [from plan]"
```

### For Project Management

- **Weekly**: Update this document with actual progress
- **Per-phase**: Check off tasks as complete
- **Risk**: Review risks and mitigation strategies
- **Blockers**: Update risk section if issues arise

### For Code Review

Validate each submission against:
1. Success criteria in this plan
2. Code quality standards
3. Test coverage >80%
4. Documentation complete

---

## Related Documents

- **VISUAL_TUTOR_AUDIT_CURRENT_STATE.md** - Current state analysis
- **VISUAL_TUTOR_TECHNICAL_SPEC.md** - Data models and APIs
- **VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md** - Vision and teaching patterns
- **VISUAL_TUTOR_QUICK_START.md** - Code examples and patterns
- **AI_IMPLEMENTATION_PROMPTS.md** - Prompts for Claude/Codex

---

**Created**: August 26, 2024  
**Phase**: 0 (Foundation)  
**Status**: Ready for implementation  
**Estimated Effort**: 200+ hours  
**Timeline**: 10-12 weeks  
**Next Steps**: Begin Phase 0.1 (Board Rendering Fix)
