# 🎓 AI VISUAL TUTOR VISION DOCUMENT
## Cambodia Grade 10-12 (Math, Physics, Chemistry)

**Vision**: Build an AI tutor that teaches like a **real 1-1 teacher drawing on a whiteboard**, not a chatbot.

---

## 🎯 THE PROBLEM WE'RE SOLVING

Current AI tutors (ChatGPT, Claude) feel like **static chatbots**:
- ❌ Just text responses
- ❌ Answers entire problem at once (not step-by-step)
- ❌ No dynamic visualizations
- ❌ No adaptation to student understanding
- ❌ Doesn't teach; just answers

**What students really need**: A **dynamic visual tutor** that:
- ✅ Teaches step-by-step (Socratic method)
- ✅ Draws diagrams, graphs, shapes in real-time
- ✅ Listens to student input and adapts
- ✅ Detects misconceptions
- ✅ Feels like asking a real teacher for help

---

## 🎨 WHAT THE STUDENT EXPERIENCES

### Scenario: Student Asks "Help me solve 2x + 5 = 13"

#### Step 1: Read the Problem (Interactive)
```
AI Tutor draws on board:
┌─────────────────────────┐
│  2x + 5 = 13            │
│                         │
│  What operation do we   │
│  see first?            │
└─────────────────────────┘

Student sees equation drawn with animation (left to right).
Student answers: "Addition with 5"
```

#### Step 2: Clarify (Ask Before Telling)
```
AI Tutor draws on board:
┌─────────────────────────┐
│  2x + 5 = 13            │
│  ↑      ↑               │
│  coeff  constant        │
│                         │
│  To isolate 2x, what do │
│  we do with the +5?    │
└─────────────────────────┘

AI highlights "5" with animation.
Student answers: "Subtract 5 from both sides"
```

#### Step 3: Execute (Guided Practice)
```
AI Tutor draws on board:
┌─────────────────────────┐
│  2x + 5 = 13            │
│  -5    -5               │
│  ────────────────       │  ← Animated operation
│  2x = 8                 │
│                         │
│  What's the next step?  │
└─────────────────────────┘

Student answers: "Divide both sides by 2"
```

#### Step 4: Solve (Final Step)
```
AI Tutor draws on board:
┌─────────────────────────┐
│  2x = 8                 │
│  ÷2   ÷2                │
│  ────────────────       │
│  x = 4                  │
│                         │
│  ✅ Correct! Well done! │
└─────────────────────────┘

AI shows celebration animation.
Student sees: Time taken, Confidence level, Next problem suggestion.
```

---

## 🖼️ VISUAL COMPONENTS (What AI Draws)

### 1. **Mathematical Equations**
- Rendered with LaTeX → Canvas animation
- Animations: Show step-by-step simplification
- Color coding: Highlight operations, terms, variables
- Example:
  ```
  2x + 5 = 13
  ↓ (subtract 5 from both sides)
  2x = 8
  ↓ (divide both sides by 2)
  x = 4
  ```

### 2. **Graphs & Plots**
- 2D plots: f(x) = x², sin(x), etc.
- Annotations: Points, asymptotes, intercepts
- Interactive: Mark solutions, zoom, annotations
- Example:
  ```
  Parabola: f(x) = x² - 4x + 3
  Points marked: Vertex, Roots, Y-intercept
  ```

### 3. **Geometric Shapes**
- Triangles: With angle marking, side labels
- Circles: With radius, diameter, arc angle
- Free body diagrams: For physics
- Molecular structures: For chemistry
- Example:
  ```
  Triangle ABC with angle marking at A
  Side labels: AB = 5, BC = 7, AC = ?
  ```

### 4. **Physics Vectors**
- Arrows showing: Forces, velocity, acceleration
- Magnitude labels and colors
- Vector addition visualization
- Example:
  ```
  Free body diagram: Weight↓ 100N, Normal↑ 100N, Applied→ 50N
  ```

### 5. **Chemistry Molecules**
- Atomic structure: Atoms (C, H, O, N) with bonds
- Lewis structures: Showing electrons
- 2D representation (3D in Phase 3)
- Example:
  ```
  H2O: H—O—H with lone pair dots
  ```

### 6. **Coordinate Systems**
- Grid with labels and scales
- Points plotted
- Equation reference
- Example:
  ```
  Cartesian plane with quadrants labeled
  Point (2, 3) marked
  ```

---

## 💡 TEACHING METHODOLOGY (Socratic Method)

### Principle: **Ask Before Telling**

1. **Scaffold**: Show the problem, ask what student sees
2. **Guide**: Ask questions that lead to next step
3. **Check**: Confirm understanding before moving forward
4. **Adapt**: If wrong, diagnose misconception, re-teach
5. **Celebrate**: Praise effort and progress

### Misconception Detection
```
Student says: "x = -4" (signed error)
AI detects: "sign_error" from misconception list
AI teaches: "When we subtract 5, we get a positive result"
AI visualizes: Highlighting the -5 operation
```

### Adaptive Path (No Fixed Sequence)
```
If student confident → Skip detailed steps, move faster
If student confused → Add more examples, simpler explanations
If misconception detected → Teach the concept first, then solve
```

---

## 🔧 TECHNICAL ARCHITECTURE

```
┌─────────────────────────────────────────────────────┐
│                  Flutter App (UI)                   │
│  ┌────────────────────────────────────────────────┐ │
│  │ Problem Select Page (Material Design)          │ │
│  │  - Dashboard: Math, Physics, Chemistry counts  │ │
│  │  - Filter: Subject, Difficulty, Topic          │ │
│  │  - Problem cards with difficulty colors        │ │
│  └────────────────────────────────────────────────┘ │
│                      ↓ (Click problem)               │
│  ┌────────────────────────────────────────────────┐ │
│  │ Step Sequencing Page (Main Teaching)           │ │
│  │  - Rich Media Canvas (graphs, shapes, vectors) │ │
│  │  - Student input (text, selection)             │ │
│  │  - Feedback & next step                        │ │
│  │  - Progress tracking (spaced repetition)       │ │
│  └────────────────────────────────────────────────┘ │
│                      ↓ (Submit response)             │
│  ┌────────────────────────────────────────────────┐ │
│  │ Progress Page                                  │ │
│  │  - Stats: Problems solved, due, accuracy       │ │
│  │  - Spaced repetition schedule                  │ │
│  │  - Misconceptions to focus on                  │ │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
         ↓ (HTTP REST API)
┌─────────────────────────────────────────────────────┐
│            AI Service (Teaching Logic)              │
│  ┌────────────────────────────────────────────────┐ │
│  │ Step Sequencing Service                        │ │
│  │  - generate_teaching_plan(problem)             │ │
│  │  - evaluate_response(student_answer)           │ │
│  │  - get_next_step(session)                      │ │
│  │  - detect_misconception(response)              │ │
│  └────────────────────────────────────────────────┘ │
│                      ↓                               │
│  ┌────────────────────────────────────────────────┐ │
│  │ Expert Services (Subject-Specific)             │ │
│  │  - MathExpertService                           │ │
│  │  - PhysicsExpertService                        │ │
│  │  - ChemistryExpertService                      │ │
│  │                                                 │ │
│  │  Each has: problem_types, solutions,           │ │
│  │  misconceptions, visualization hints           │ │
│  └────────────────────────────────────────────────┘ │
│                      ↓                               │
│  ┌────────────────────────────────────────────────┐ │
│  │ Knowledge Graph Service (KG)                   │ │
│  │  - Get concepts for problem                    │ │
│  │  - Get prerequisites                           │ │
│  │  - Get misconceptions                          │ │
│  │  - Build concept map                           │ │
│  └────────────────────────────────────────────────┘ │
│                      ↓                               │
│  ┌────────────────────────────────────────────────┐ │
│  │ Model Gateway (LLM)                            │ │
│  │  - Qwen 3 (main tutor)                         │ │
│  │  - Gemini (fallback, edge cases)               │ │
│  │  - Whisper (speech recognition)                │ │
│  │  - Piper (text-to-speech)                      │ │
│  └────────────────────────────────────────────────┘ │
│                      ↓                               │
│  ┌────────────────────────────────────────────────┐ │
│  │ Problem Repository & Services                  │ │
│  │  - list_problems() → filtered by subject/difficulty │
│  │  - get_problem(id) → full problem details      │
│  │  - spaced_repetition_service → when to review  │
│  └────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
         ↓ (Queries)
┌─────────────────────────────────────────────────────┐
│              PostgreSQL Database                    │
│  - problems (24 curated)                            │
│  - student_progress (tracking)                      │
│  - concepts (from KG)                               │
│  - misconceptions (from KG)                         │
└─────────────────────────────────────────────────────┘
```

---

## 📚 CURRICULUM COVERAGE

### Mathematics (Grade 10-12)
| Topic | Subtopic | Problems | Example |
|-------|----------|----------|---------|
| Linear Equations | Two-step, multi-step, variables | 3 | 2x + 5 = 13 |
| Quadratic | Standard form, vertex form, roots | 2 | x² - 5x + 6 = 0 |
| Geometry | Triangles, circles, areas | 3 | Find circle area with radius r |
| Functions | Domain, range, composition | 2 | f(x) = x² + 2x, find f(3) |
| Trigonometry | SOHCAHTOA, identities | 1 | sin(θ) = 0.5, find θ |

**Total: 11 Problems**

### Physics (Grade 10-12)
| Topic | Subtopic | Problems | Example |
|-------|----------|----------|---------|
| Kinematics | Distance, velocity, acceleration | 2 | v = at, find v if a=2, t=3 |
| Dynamics | Force, mass, Newton's laws | 2 | F = ma, find a if F=100, m=5 |
| Energy | Kinetic, potential, conservation | 1 | KE = ½mv², find v if m=2, KE=4 |
| Circular Motion | Centripetal force, angular velocity | 1 | F_c = mv²/r, find r |
| Waves | Frequency, wavelength, speed | 1 | v = fλ, find λ if v=340, f=100 |

**Total: 7 Problems**

### Chemistry (Grade 10-12)
| Topic | Subtopic | Problems | Example |
|-------|----------|----------|---------|
| Bonding | Lewis structures, electronegativity | 2 | Draw H2O Lewis structure |
| Reactions | Balancing, stoichiometry | 2 | Balance: Fe + O2 → Fe2O3 |
| Molecular Structures | VSEPR, bond angles | 1 | What's bond angle in H2O? |
| Equilibrium | K_eq, Le Chatelier | 1 | Shift direction if temp increases |

**Total: 6 Problems**

**Grand Total: 24 Problems** (Curated, tested, difficulty-calibrated)

---

## 🔄 STUDENT EXPERIENCE FLOW

```
┌─────────────────────┐
│  Student Opens App  │
└──────────┬──────────┘
           ↓
┌─────────────────────────────────────────────────────┐
│ Problem Selection Page                              │
│ - See dashboard: Math (3/11), Physics (1/7), ...   │
│ - Filter by subject, difficulty, or topic          │
│ - Browse problem cards with difficulty colors      │
│ - See "Due for Review" section (from spaced rep)   │
└──────────┬──────────────────────────────────────────┘
           ↓ (Click "Solve" on a problem)
┌─────────────────────────────────────────────────────┐
│ Step Sequencing Page (Main Teaching Experience)     │
│                                                     │
│ [Rich Media Canvas]                                 │
│ ┌──────────────────────────┐                        │
│ │ Problem & First Step     │                        │
│ │ (with animations)        │                        │
│ │ "What operation do we    │                        │
│ │  see first?"             │                        │
│ └──────────────────────────┘                        │
│                                                     │
│ [Student Input]                                     │
│ ┌──────────────────────────┐                        │
│ │ > Addition               │  ← Student types/picks │
│ │                          │                        │
│ │ [Submit] [Skip]          │                        │
│ └──────────────────────────┘                        │
│                                                     │
│ [Feedback]                                          │
│ ┌──────────────────────────┐                        │
│ │ ✅ Correct! Next...      │  ← AI evaluates       │
│ │ [Continue]               │                        │
│ └──────────────────────────┘                        │
│                                                     │
│ Repeat for steps 2, 3, 4, 5...                     │
│                                                     │
│ Final: "x = 4 ✅" + Time Taken, Confidence Level   │
└──────────┬──────────────────────────────────────────┘
           ↓ (Submit final response)
┌─────────────────────────────────────────────────────┐
│ Progress Update                                     │
│ - Spaced Repetition schedules next review          │
│ - Updates stats (times solved, accuracy)           │
│ - Flags misconceptions detected                    │
│ - Suggests next problem (adaptive difficulty)      │
│ - Shows achievement badges                         │
└──────────┬──────────────────────────────────────────┘
           ↓ (Back to Problem Selection)
           └─→ [Repeat]
```

---

## 📊 DATA STRUCTURES (Key Models)

### Problem
```python
{
  "id": "math_linear_001",
  "subject": "mathematics",
  "grade_level": 10,
  "topic": "linear_equations",
  "subtopic": "two_step_equations",
  "difficulty": 1,  # 1-5 scale
  "problem": "Solve 2x + 5 = 13 for x",
  "answer": "4",
  "expected_steps": 4,
  "misconceptions": ["sign_error", "forgot_division"],
  "concepts": ["inverse_operations", "equality"],
  "tags": ["cambodia_grade_10"]
}
```

### TeachingStep
```python
{
  "id": "step_1",
  "step_number": 1,
  "type": "question",  # question, explanation, confirmation
  "content": "What operation do we see first?",
  "visualization": {
    "type": "equation",
    "data": "2x + 5 = 13",
    "highlights": ["5"],  # Highlight the +5
    "annotations": {"5": "constant"}
  },
  "expected_answer": "addition",
  "hints": ["Look at the number without x", "What sign is it?"],
  "misconceptions": ["sign_error", "variable_confusion"]
}
```

### StudentProgress
```python
{
  "student_id": "student_001",
  "problem_id": "math_linear_001",
  "times_solved": 1,
  "times_failed": 0,
  "confidence_level": "medium",
  "next_review": "2024-08-29 10:30:00",  # SM-2 scheduling
  "time_spent_seconds": 180,
  "misconceptions_detected": ["sign_error"],
  "last_seen": "2024-08-26 10:30:00"
}
```

---

## 🎬 ANIMATION PRIORITIES

### Phase 1 (MVP - Now)
- ✅ Fade in/out for equations
- ✅ Color highlighting for operations
- ✅ Step-by-step simplification (top-to-bottom)
- ✅ Basic graph rendering

### Phase 2 (Next)
- 🔄 Smooth transitions between steps
- 🔄 Draw animations (shapes appearing)
- 🔄 Vector animations (arrows moving)
- 🔄 Molecule bond animations

### Phase 3 (Later)
- 📅 Complex math animations (Geogebra-like)
- 📅 3D molecular structures
- 📅 Interactive drag-and-drop
- 📅 Video explanations

---

## 🧪 SUCCESS CRITERIA (Measurable)

### Functionality
- ✅ Student can solve 24 problems end-to-end
- ✅ All visualizations render correctly
- ✅ Spaced repetition schedules correctly
- ✅ Misconceptions detected in 80% of cases

### Learning Outcomes
- 📊 Time to solve decreases by 20% after review
- 📊 Accuracy increases by 30% after feedback
- 📊  90% of students prefer visual tutor over text-based
- 📊 Learning gains measurable with pre/post tests

### Performance
- ⚡ Step rendering <100ms
- ⚡ Problem loading <500ms
- ⚡ Response evaluation <200ms
- ⚡ No crashes on 100+ concurrent users (Phase 3)

### User Experience
- 😊 NPS > 50 (Net Promoter Score)
- 😊 Session completion rate > 80%
- 😊 Misconception feedback rated "helpful" by 75%+
- 😊 Would use again: 85%+

---

## 🚀 PHASE BREAKDOWN

| Phase | Duration | Scope | MVP? |
|-------|----------|-------|------|
| **0** | ✅ Done | Rich media rendering, subject experts, step sequences | N/A |
| **1** | ✅ Done | Problem bank, spaced rep, Flutter UI | N/A |
| **2** | 🚀 NOW | KG integration, auth, step API, testing | YES → Ready for real students |
| **3** | 📅 Later | Analytics, recommendations, mobile optimization | No |
| **4** | 📅 Later | Classroom mode, peer collaboration | No |

---

## 📝 IMPLEMENTATION PRIORITIES

### 🔴 CRITICAL (Phase 2)
1. Wire Step Sequencing to REST API (students can't access teaching)
2. Integrate Knowledge Graph (AI needs knowledge to teach)
3. Real authentication (can't test with real students without it)

### 🟠 HIGH (Phase 2)
4. Database migration (JSON not production-ready)
5. Integration testing (ensure everything works together)

### 🟡 MEDIUM (Phase 2)
6. LLM evaluation (rule-based works, LLM is fallback)
7. Adaptive difficulty (nice-to-have, calibrate with real data)

### 🟢 LOW (Phase 3+)
8. Advanced visualizations (3D, interactive)
9. Analytics dashboard
10. Mobile app optimization

---

## 🎓 CAMBODIA CURRICULUM ALIGNMENT

This system is **designed specifically** for Cambodia Grade 10-12:

### Alignment with National Curriculum
- ✅ Math topics match Ministry of Education standards
- ✅ Physics topics follow Cambodia High School physics
- ✅ Chemistry aligned with Grade 10-12 standard syllabus

### Language Support
- ✅ English (primary for now)
- 🔄 Khmer translation in Phase 2
- 🔄 Khmer speech-to-text in Phase 3

### Cultural Adaptation
- ✅ Respect for Khmer learning styles (step-by-step, visual)
- ✅ Examples relevant to Cambodia (no Western-centric problems)
- ✅ Time zone and accessibility for rural schools

---

## 📞 FEEDBACK LOOPS (Always Iterating)

1. **Real Student Testing** (Phase 2 end)
   - Deploy to 5-10 Cambodia schools
   - Collect performance data
   - Measure: accuracy, time, engagement

2. **Difficulty Calibration**
   - Analyze: Which problems too easy/hard?
   - Adjust levels based on real data
   - Update misconceptions from actual mistakes

3. **Teacher Feedback**
   - Interview teachers: How would you teach this?
   - Align step sequences to teaching practice
   - Improve explanations based on feedback

4. **Continuous Improvement**
   - Monitor: Session logs, error rates
   - Update: Misconceptions, visualizations, difficulty
   - Iterate monthly with real student cohorts

---

## ✨ VISION STATEMENT

> **"An AI Visual Tutor that teaches like your best teacher drawing on a whiteboard—step-by-step, visually, with understanding, not just answers. Available to every student in Cambodia, 24/7, personalized to their needs and learning pace."**

---

**This vision is driven by real student need in Cambodia.**  
**Every design decision serves this goal.**  
**Let's build it together.** 🚀
