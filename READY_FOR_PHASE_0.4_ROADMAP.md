# 🚀 Ready for Phase 0.4: Subject Experts Roadmap

**Status**: Phase 0.3 ✅ COMPLETE | Phase 0.4 🟡 READY TO START  
**Phase 0 Progress**: 90% (three of four phases complete)  
**Estimated Time**: 12-16 hours  
**Complexity**: High (domain-specific expert logic)

---

## 📊 Current State

### What You Have (Phase 0.1-0.3)

```
Phase 0: Foundation (90% Complete)
├── ✅ Phase 0.1: Board Rendering (365 lines)
│   └── RichMediaCanvas - responsive whiteboard
│
├── ✅ Phase 0.2: Rich Media Renderers (3,550 lines)
│   ├── GraphRenderer - math graphs
│   ├── GeometricRenderer - shapes & FBDs
│   ├── VectorRenderer - physics vectors
│   └── MoleculeRenderer - chemistry structures
│
├── ✅ Phase 0.3: Step Sequencing (3,280 lines)
│   ├── Backend models (Pydantic)
│   ├── Backend service (step generation)
│   ├── API routes (FastAPI)
│   ├── Flutter entities
│   ├── State management (Riverpod)
│   └── UI page (Material Design)
│
└── 🟡 Phase 0.4: Subject Experts (0% - READY TO START)
    ├── Math Expert Service
    ├── Physics Expert Service
    └── Chemistry Expert Service
```

### Capabilities Ready

✅ Responsive whiteboard  
✅ Math graphs, geometric shapes, vectors, molecules  
✅ Step-by-step teaching UI  
✅ Adaptive branching  
✅ Student interaction system  

### Missing (Phase 0.4)

🟡 **Math Expert**: Problem type detection, solution steps, misconceptions  
🟡 **Physics Expert**: Diagram analysis, vector calculations, energy  
🟡 **Chemistry Expert**: Structure analysis, bonding, reactions  

---

## 🎯 What Phase 0.4 Does

### The Problem

Current `StepSequencingService` generates generic steps. We need **subject experts** that:
1. Understand problem types (e.g., "solve quadratic" vs "projectile motion")
2. Generate domain-specific steps (not generic)
3. Detect misconceptions (e.g., "forgot to distribute")
4. Create accurate visualizations
5. Provide expert feedback

### The Solution

Three **Expert Services** (Math, Physics, Chemistry) that:
1. Analyze problem using KG and problem context
2. Generate step sequences tailored to problem type
3. Create subject-specific visualizations
4. Detect and address misconceptions
5. Evaluate student responses in domain context

### Example: Math Expert

**Input Problem**: "Solve 2x + 5 = 13"

**Expert Analysis**:
- Type: Linear equation
- Difficulty: Grade 10, basic algebra
- Concepts: Inverse operations, equality

**Generated Steps**:
1. Explain: "To solve, we isolate the variable"
2. Question: "What operation gets rid of the +5?"
3. Feedback: "Yes, subtract 5" (if correct) or Hint (if wrong)
4. Visualization: Show 2x = 8
5. Continue until solved...

**Misconceptions Detected**:
- If student adds instead of subtracts → Immediate correction
- If student forgets order of operations → Teach PEMDAS
- If student doesn't understand equality → Provide analogy

---

## 🛠️ Implementation Plan

### Phase 0.4.1: Math Expert Service (5-6 hours)

**File**: `ai_service/api/services/math_expert_service.py`

**Responsibilities**:
- Detect problem type (linear, quadratic, geometry, algebra)
- Generate step sequences for each type
- Create math visualizations
- Detect algebra misconceptions

**Problem Types to Support** (Grade 10-12):
1. **Linear Equations**: 2x + 5 = 13
2. **Quadratic Equations**: x² + 5x + 6 = 0
3. **Systems of Equations**: 2x + y = 5, x - y = 1
4. **Geometry**: Area, perimeter, angle calculation
5. **Algebra Manipulation**: Factoring, expanding, simplifying
6. **Functions**: f(x) = x², domain, range
7. **Inequalities**: 2x + 5 > 13

**Key Methods**:
```python
class MathExpertService:
    async def analyze_problem(problem: str) -> MathProblemAnalysis
    async def generate_steps(analysis: MathProblemAnalysis) -> List[TeachingStep]
    async def create_visualization(step: TeachingStep) -> VisualizationConfig
    async def evaluate_response(question: str, response: str) -> EvaluationResult
    async def detect_misconception(error: str) -> Optional[Misconception]
    
    # Problem type specific
    async def _solve_linear_equation(equation: str) -> List[TeachingStep]
    async def _solve_quadratic_equation(equation: str) -> List[TeachingStep]
    async def _solve_geometry_problem(problem: str) -> List[TeachingStep]
    # ... etc
```

**Step Generation Patterns**:
- Linear: Isolate variable → Check solution
- Quadratic: Factor or formula → Check roots
- Geometry: Identify shape → Apply formula → Calculate
- Algebra: Identify operation → Apply step → Simplify

**Visualizations**:
- Number lines for inequalities
- Graphs for functions
- Shapes for geometry
- Equation rearrangement animations

---

### Phase 0.4.2: Physics Expert Service (4-5 hours)

**File**: `ai_service/api/services/physics_expert_service.py`

**Responsibilities**:
- Detect problem type (kinematics, dynamics, energy, waves)
- Generate physics-specific steps
- Create FBDs and vector diagrams
- Validate physics reasoning

**Problem Types to Support** (Grade 10-12):
1. **Kinematics**: Displacement, velocity, acceleration
2. **Dynamics**: Forces, Newton's laws, friction
3. **Circular Motion**: Centripetal force, angular velocity
4. **Energy**: KE, PE, conservation, work
5. **Waves & Sound**: Frequency, wavelength, speed
6. **Electricity**: Current, voltage, resistance
7. **Magnetism**: Forces, fields

**Key Methods**:
```python
class PhysicsExpertService:
    async def analyze_problem(problem: str) -> PhysicsProblemAnalysis
    async def generate_steps(analysis: PhysicsProblemAnalysis) -> List[TeachingStep]
    async def create_visualization(step: TeachingStep) -> VisualizationConfig
    async def evaluate_response(question: str, response: str) -> EvaluationResult
    
    # Visualization helpers
    async def _create_free_body_diagram(forces: List[Vector]) -> VisualizationConfig
    async def _create_motion_graph(v0, a, t) -> VisualizationConfig
    async def _create_force_diagram(scenario: str) -> VisualizationConfig
```

**Step Generation Patterns**:
- Kinematics: Identify known/unknown → Choose equation → Solve
- Dynamics: Draw FBD → Find net force → Apply F=ma
- Energy: Identify types → Apply conservation → Solve

**Visualizations**:
- Free body diagrams (forces as vectors)
- Motion graphs (position, velocity, acceleration)
- Vector addition for resultant forces
- Energy diagrams (bars showing KE, PE, total)

---

### Phase 0.4.3: Chemistry Expert Service (3-4 hours)

**File**: `ai_service/api/services/chemistry_expert_service.py`

**Responsibilities**:
- Detect problem type (structure, bonding, reactions, stoichiometry)
- Generate chemistry-specific steps
- Draw molecular structures
- Predict reaction outcomes

**Problem Types to Support** (Grade 10-12):
1. **Molecular Structure**: Lewis structures, VSEPR, hybridization
2. **Bonding**: Covalent, ionic, metallic, intermolecular forces
3. **Reactions**: Equilibrium, redox, acid-base
4. **Stoichiometry**: Limiting reagent, percent yield
5. **Bonding Energy**: Exothermic, endothermic

**Key Methods**:
```python
class ChemistryExpertService:
    async def analyze_problem(problem: str) -> ChemistryProblemAnalysis
    async def generate_steps(analysis: ChemistryProblemAnalysis) -> List[TeachingStep]
    async def create_visualization(step: TeachingStep) -> VisualizationConfig
    async def evaluate_response(question: str, response: str) -> EvaluationResult
    
    # Structure drawing
    async def _draw_lewis_structure(formula: str) -> VisualizationConfig
    async def _draw_molecular_geometry(formula: str) -> VisualizationConfig
```

**Step Generation Patterns**:
- Lewis structure: Count electrons → Draw structure → Assign charges
- Bonding: Identify atoms → Check electronegativity → Predict bond
- Reactions: Balance → Identify type → Predict products

**Visualizations**:
- Molecular structures (atoms + bonds)
- Electron configurations
- Reaction mechanism diagrams
- Energy level diagrams

---

## 📋 Integration Pattern (Critical!)

### How Subject Experts Integrate with StepSequencingService

**Current Flow**:
```python
# In step_sequencing_service.py
async def generate_teaching_plan(problem, subject, grade_level):
    # Analyze problem
    analysis = await self._analyze_problem(problem, subject)
    
    # Route to subject expert
    if subject == "mathematics":
        steps = await self.math_expert.generate_steps(analysis)
    elif subject == "physics":
        steps = await self.physics_expert.generate_steps(analysis)
    elif subject == "chemistry":
        steps = await self.chemistry_expert.generate_steps(analysis)
    
    # Create visualizations
    for step in steps:
        step.visualizations = await self.math_expert.create_visualization(step)
    
    return TeachingPlan(steps=steps, ...)
```

**Interface Each Expert Must Implement**:
```python
class BaseExpertService:
    async def analyze_problem(problem: str) -> ProblemAnalysis
    async def generate_steps(analysis: ProblemAnalysis) -> List[TeachingStep]
    async def create_visualization(step: TeachingStep) -> VisualizationConfig
    async def evaluate_response(question: str, response: str) -> EvaluationResult
    async def detect_misconception(error: str) -> Optional[Misconception]
```

**Key Points**:
- All methods async
- All return types match StepSequencingService expectations
- Subject experts are pluggable
- Can add more subjects (biology, history, etc.) later

---

## 🧠 Knowledge Graph Integration

### What You'll Use

The Knowledge Graph (`kg_service_v3.py`) stores:
- Concepts (e.g., "linear_equation", "free_body_diagram")
- Relationships (e.g., "uses" → inverse operations)
- Examples for each concept
- Common misconceptions

### Integration Points

```python
# In each expert service:
async def _get_concept_knowledge(concept: str) -> ConceptInfo:
    return await self.kg.get_concept(
        name=concept,
        grade_level=grade_level,
        subject=subject,
    )

# For misconception detection:
misconceptions = await self.kg.get_misconceptions(concept)
```

---

## 📊 Skill Progression (What to Build)

### Level 1: Basic Problem Types (3-4 hours)
- [x] Problem type detection
- [x] Basic step generation
- [x] Simple visualizations

### Level 2: Enhanced Steps (2-3 hours)
- [x] Multi-step solutions
- [x] Misconception detection
- [x] Adaptive difficulty

### Level 3: Advanced Features (2-3 hours)
- [x] Alternative solution methods
- [x] Real-world applications
- [x] Interactive explanations

---

## 🚀 How to Start Phase 0.4

### Option 1: Implement All Three (Recommended for Completeness)

**Order** (dependent steps):
1. Math Expert (5-6 hrs) - Simplest, establishes patterns
2. Physics Expert (4-5 hrs) - Builds on math patterns
3. Chemistry Expert (3-4 hrs) - Similar patterns to others

**Estimated Time**: 12-16 hours total

**Result**: Complete Phase 0 (all 4 sub-phases)

### Option 2: Start with Math Only

**Time**: 5-6 hours

**Result**: Full teaching system for math problems

**Next**: Add Physics and Chemistry later (Phase 1+)

### Option 3: Delegate to AI

Use similar pattern to Phase 0.3:
1. Get code templates from prompts below
2. Have Claude/ChatGPT implement
3. Review and integrate
4. Test end-to-end

---

## 💻 Prompt Templates for AI

### For Math Expert Implementation

```
CONTEXT: Implementing Phase 0.4.1 - Math Expert Service
Previous: Phase 0.3 (Step Sequencing) fully implemented

TASK: Create ai_service/api/services/math_expert_service.py

Requirements:
1. MathExpertService class with methods:
   - analyze_problem(problem: str) -> MathProblemAnalysis
   - generate_steps(analysis) -> List[TeachingStep]
   - create_visualization(step) -> VisualizationConfig
   - evaluate_response(question, response) -> EvaluationResult
   - detect_misconception(error) -> Optional[Misconception]

2. Problem types to support:
   - Linear equations (2x + 5 = 13)
   - Quadratic equations (x² + 5x + 6 = 0)
   - Systems of equations
   - Geometry (area, perimeter, angles)
   - Algebra (factoring, expanding)
   - Functions (domain, range, graphs)
   - Inequalities

3. Step generation patterns:
   - Explain concept
   - Ask guiding question
   - Provide feedback
   - Guide to next step
   - Verify solution

4. Visualizations:
   - Use GraphRenderer for function graphs
   - Use GeometricRenderer for shapes
   - Number lines for inequalities
   - Step-by-step equation solving animation

5. Misconception detection:
   - Check for common algebra errors
   - Sign errors, distribution, order of operations
   - Integration with Knowledge Graph

Code style: Python 3.11+, async/await, type hints, FastAPI patterns
Integration: Plugs into StepSequencingService via dependency injection
```

### For Physics Expert Implementation

```
CONTEXT: Implementing Phase 0.4.2 - Physics Expert Service
Previous: Math Expert done

TASK: Create ai_service/api/services/physics_expert_service.py

Requirements:
1. PhysicsExpertService class with same interface as MathExpertService
   - analyze_problem(problem: str) -> PhysicsProblemAnalysis
   - generate_steps(analysis) -> List[TeachingStep]
   - create_visualization(step) -> VisualizationConfig
   - evaluate_response(question, response) -> EvaluationResult

2. Problem types:
   - Kinematics (v = u + at, s = ut + 0.5at²)
   - Dynamics (F = ma, friction)
   - Energy (KE, PE, conservation)
   - Waves and circular motion

3. Visualizations:
   - Free body diagrams (VectorRenderer)
   - Motion graphs
   - Vector addition for forces
   - Energy diagrams

4. Solution steps:
   - Draw free body diagram
   - Identify forces
   - Calculate net force
   - Apply Newton's laws
   - Solve for unknowns

5. Physics validation:
   - Units checking
   - Magnitude validation
   - Direction accuracy
   - Energy conservation verification
```

### For Chemistry Expert Implementation

```
CONTEXT: Implementing Phase 0.4.3 - Chemistry Expert Service
Previous: Math & Physics Experts done

TASK: Create ai_service/api/services/chemistry_expert_service.py

Requirements:
1. ChemistryExpertService with same interface
   - analyze_problem(problem: str) -> ChemistryProblemAnalysis
   - generate_steps(analysis) -> List[TeachingStep]
   - create_visualization(step) -> VisualizationConfig
   - evaluate_response(question, response) -> EvaluationResult

2. Problem types:
   - Molecular structure (Lewis, VSEPR)
   - Bonding types (covalent, ionic, metallic)
   - Reactions (balancing, type identification)
   - Stoichiometry

3. Visualizations:
   - Molecular structures (MoleculeRenderer)
   - Electron configurations
   - Reaction arrows and mechanisms
   - Bonding diagrams

4. Chemistry-specific logic:
   - Atom electron counting
   - Bond type determination
   - Reaction balancing
   - Stoichiometry calculations
```

---

## 🧪 Testing Phase 0.4

### Unit Tests (For each expert)

```python
test_math_expert.py
├── test_linear_equation_detection
├── test_quadratic_equation_detection
├── test_linear_equation_steps
├── test_quadratic_equation_steps
├── test_misconception_detection_sign_error
├── test_misconception_detection_distribution
└── test_visualization_creation

test_physics_expert.py
├── test_kinematics_detection
├── test_dynamics_detection
├── test_fbd_creation
├── test_force_calculation
└── test_energy_conservation_validation

test_chemistry_expert.py
├── test_lewis_structure_detection
├── test_molecular_geometry
├── test_bonding_type_identification
└── test_reaction_balancing
```

### Integration Tests

```python
test_full_teaching_flow.py
├── test_math_problem_full_sequence
├── test_physics_problem_full_sequence
├── test_chemistry_problem_full_sequence
└── test_adaptive_branching_by_subject
```

---

## 📈 Success Criteria for Phase 0.4

| Criterion | Status |
|-----------|--------|
| Math Expert implemented | ⏳ |
| Physics Expert implemented | ⏳ |
| Chemistry Expert implemented | ⏳ |
| All problem types detected | ⏳ |
| Step generation working | ⏳ |
| Visualizations created | ⏳ |
| Misconceptions detected | ⏳ |
| Tests passing (>80% coverage) | ⏳ |
| Integrated with StepSequencingService | ⏳ |
| End-to-end flow working | ⏳ |

---

## 🎯 What Comes After Phase 0.4

### Phase 0.4 Complete → Phase 1: Math Problem Bank (8-10 hours)

Once all three experts are done:
- Create 20-30 carefully-selected math problems
- Build problem bank with difficulty levels
- Implement spaced repetition
- Add performance tracking

### Then Phase 1 → Phase 2, 3, etc.

Each subject gets its own Phase with problem banks and adaptive logic.

---

## 📚 Reference Implementation

The **Math Expert** implementation serves as a template:
- Use it as reference for Physics Expert
- Use Physics Expert pattern for Chemistry Expert
- All follow same interface
- All return compatible data structures

---

## 🚀 Timeline Estimate

```
Phase 0.4: Subject Experts (12-16 hours)
├── Math Expert (5-6 hours)
│   ├── Problem type detection (1 hr)
│   ├── Step generation (2 hrs)
│   ├── Visualization (1 hr)
│   ├── Misconception detection (1 hr)
│   └── Testing (1 hr)
│
├── Physics Expert (4-5 hours)
│   ├── Problem analysis (1 hr)
│   ├── Step generation (1.5 hrs)
│   ├── FBD/visualization (1 hr)
│   ├── Misconception detection (0.5 hrs)
│   └── Testing (0.5 hrs)
│
└── Chemistry Expert (3-4 hours)
    ├── Structure analysis (1 hr)
    ├── Step generation (1 hr)
    ├── Visualization (0.5 hrs)
    ├── Misconception detection (0.5 hrs)
    └── Testing (0.5 hrs)

Total: 12-16 hours
```

---

## 💡 Key Implementation Insights

### Don't Reinvent the Wheel

✅ Use existing renderers (Graph, Geometric, Vector, Molecule)  
✅ Follow StepSequencingService patterns  
✅ Leverage Knowledge Graph for concept data  
✅ Use Model Gateway for LLM evaluation  

### Focus on Domain Logic

✅ Problem type detection (how to recognize "solve quadratic"?)  
✅ Solution step generation (what are natural steps?)  
✅ Visualization generation (what diagrams help?)  
✅ Misconception detection (what errors are common?)  

### Keep It Simple (at First)

✅ Start with basic problem types  
✅ Add complexity as you go  
✅ Test frequently  
✅ Refactor as patterns emerge  

---

## ✅ Ready to Start Phase 0.4?

### Checklist Before Starting

- [x] Phase 0.3 complete and verified
- [x] Backend API working
- [x] Flutter UI rendering correctly
- [x] Knowledge Graph accessible
- [x] Model Gateway available
- [x] All renderers working
- [x] Ready to implement subject experts!

### Next Steps

1. **Read** this document thoroughly (you're doing it!)
2. **Decide** whether to implement or delegate
3. **Plan** which expert to start with (Math recommended)
4. **Implement** following patterns above
5. **Test** with real problems
6. **Integrate** with StepSequencingService
7. **Verify** full end-to-end flow

---

## 🎉 Final Notes

**You're 90% of the way through Phase 0!**

Phase 0.4 is where the system becomes **truly smart** - it understands problems in their domain context and teaches like a subject expert.

After Phase 0.4:
- Complete teaching system ready ✅
- Subject experts integrated ✅
- Adaptive branching working ✅
- Ready for Phase 1 (Problem Bank) ✅

---

**Status**: Phase 0.3 ✅ Complete | Phase 0.4 🟡 Ready to Start  
**Time Estimate**: 12-16 hours  
**Complexity**: High (domain-specific logic)  
**Next Action**: Choose your approach and start implementing! 🚀

**Let's finish Phase 0 and get to Phase 1! 💪**
