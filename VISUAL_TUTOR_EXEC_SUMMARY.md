# AI Visual Tutor - Executive Summary

**Project**: Interactive AI Teacher with Live Whiteboard for Cambodia Grade 10-12  
**Vision**: Replace ChatGPT-style tutoring with real teacher-like learning  
**Status**: Phase 0 (Foundation) - Audit Complete, Implementation Starting  
**Date**: August 26, 2024

---

## What We're Building

### The Problem
Students use ChatGPT/Claude for homework:
- Passive learning (reading answers, not discovering)
- No visual concepts (graphs, diagrams, forces)
- No interaction (teacher doesn't wait for student thinking)
- Not adapted (same explanation for everyone)
- Feels like a chatbot, not a teacher

### The Solution
**AI Visual Tutor**: Interactive whiteboard where AI teacher:
1. Draws problem on board (equations, diagrams, graphs)
2. Asks question ("What do you notice?")
3. **Waits for student response** ← Key difference
4. Adapts next step based on answer
5. Continues step-by-step (not dumping full answer)

### Result
- ✅ Feels like learning with real teacher
- ✅ Visual understanding (graphs, vectors, molecules)
- ✅ Student is active (must think and respond)
- ✅ Personalized (adapts to their answer)
- ✅ Efficient (doesn't teach concepts student already knows)

---

## Current Status

### What's Done ✅
- **Complete planning** (10 comprehensive documents, 7,500+ lines)
- **Architecture designed** (multi-layer system, data models, APIs)
- **Flutter foundation** (board system, action rendering, design tokens)
- **Entity models** (session, turn, response, board action structures)
- **Audit & diagnosis** (root causes identified for current issues)

### What's Broken 🚨
1. **Board rendering**: Widgets sometimes don't show (positioning issue)
2. **Not step-by-step**: Shows all answers at once (not teaching)
3. **No visualizations**: Can't draw graphs, shapes, vectors, molecules
4. **No pedagogy**: No questions, no student interaction, no adaptation

### Why It's Broken
- Board uses fixed pixel coordinates (doesn't respond to screen size)
- No layout system (LayoutBuilder missing)
- AI generates whole solution at once (should be Step 1, Step 2, Step 3)
- No data structures for steps, student tasks, or branching
- Backend doesn't have teaching pipeline (just generates answers)

---

## The Fix (5 Phases, 10-12 Weeks)

### Phase 0: Foundation (Weeks 1-2) - STARTING NOW
**Goal**: Make board rendering reliable and add rich media

**Critical Fixes**:
1. Fix board rendering (responsive layout, dynamic positioning)
2. Build visualization engines:
   - GraphRenderer (functions, data plots)
   - GeometricRenderer (triangles, circles, FBDs)
   - VectorRenderer (forces, arrows)
   - MoleculeRenderer (atoms, bonds, structures)
3. Define step/sequence data models

**Hours**: 100-120  
**Owner**: TBD (2 developers)

---

### Phase 1: Math Teaching (Weeks 3-4)
**Subjects**: Linear equations, quadratics, geometry, trigonometry
- Implement subject-specific visualizations
- Build problem bank (15-20 problems per topic)
- Implement step sequencing UI (Step 1 → wait → Step 2)
- Implement student task UI (question, answer input)

**Hours**: 40-60

---

### Phase 2: Physics Teaching (Weeks 5-6)
**Topics**: Kinematics, dynamics, energy
- Free body diagrams with force vectors
- Motion graphs (v-t, x-t, a-t)
- Energy visualizations

**Hours**: 40-60

---

### Phase 3: Chemistry Teaching (Weeks 7-8)
**Topics**: Atomic structure, reactions, equilibrium
- Molecular structure visualization
- Lewis structures, electron configurations
- Reaction balancing

**Hours**: 40-60

---

### Phase 4: Curriculum & Adaptation (Weeks 9-10)
**Features**:
- Cambodia MOE curriculum alignment
- Prerequisite checking (can student learn this topic?)
- Adaptive difficulty (skip easy problems if student is advanced)
- Khmer language support

**Hours**: 30-40

---

### Phase 5: Integration & Polish (Weeks 11-12)
**Focus**: Quality, performance, user testing
- End-to-end testing (iOS, Android, Web)
- Performance optimization (<100ms per step)
- User testing with students
- Documentation

**Hours**: 20-30

---

## Key Metrics

| Metric | Target | Status |
|--------|--------|--------|
| **Timeline** | 10-12 weeks | On track |
| **Effort** | 200+ hours | Estimated |
| **Code Coverage** | >80% | Not started |
| **Performance** | <100ms per action | To verify |
| **Platforms** | iOS, Android, Web | Phase 5 target |
| **Languages** | Khmer + English | Phase 4 target |
| **Subjects** | Math, Physics, Chemistry | Phases 1-3 |

---

## Why This Approach

### ✅ Strengths
1. **Step-by-step**: Students discover answers, don't just read them
2. **Adaptive**: Different path if student answers wrong
3. **Visual**: Graphs, diagrams help understanding
4. **Engaging**: Student is active (must respond to questions)
5. **Broad scope**: Works for Math, Physics, Chemistry

### Risks Mitigated
1. **Rendering issues** → Implement RichMediaCanvas with dynamic layout
2. **Performance** → Test <100ms, use Canvas optimization
3. **LLM quality** → Use few-shot examples, validate outputs
4. **Curriculum gaps** → Start with common topics, expand
5. **Language support** → Add Khmer fonts, i18n infrastructure

---

## Technical Architecture

```
FRONTEND (Flutter)                   BACKEND (FastAPI)
├── RichMediaCanvas                  ├── TeachingSequenceService
│   ├── GraphRenderer                │   └── Generate Steps 1-5
│   ├── GeometricRenderer            │
│   ├── VectorRenderer               ├── StepEvaluatorService
│   └── MoleculeRenderer             │   └── Check Student Answer
│                                     │
├── StepSequenceWidget               ├── AdaptiveBranchingService
│   └── Render 1 step at time        │   └── Correct? Wrong? Timeout?
│                                     │
└── StudentTaskWidget                ├── CurriculumService
    └── Question + Input              │   └── Check prerequisites
                                      │
                                      └── KG Service
                                          └── Concept graph
```

### Data Flow
```
Student: "How do I solve this?"
    ↓
Backend: Classify problem (algebra, geometry, etc.)
    ↓
Backend: Plan 3-5 teaching steps
    ↓
Backend: Generate STEP 1 only (board actions + question)
    ↓
Flutter: Render Step 1, wait for student input
    ↓
Student: Answer question
    ↓
Backend: Evaluate answer
    ├─ If correct: Generate STEP 2 (next concept)
    ├─ If incorrect: Generate STEP 2 (reteach differently)
    └─ If timeout: Provide hint + simplified explanation
    ↓
Repeat until problem solved
```

---

## What Success Looks Like

### User Experience
```
Student: "Solve 2x + 5 = 13"

AI Teacher (on board):
┌─────────────────────────────┐
│ Step 1:                     │
│ Writes: 2x + 5 = 13         │
│ Asks: "What do you see?"    │
│                             │
│ [Student thinks... answers] │
└─────────────────────────────┘

Step 2:
┌─────────────────────────────┐
│ Highlights: +5              │
│ Asks: "How to undo +5?"     │
│                             │
│ [Student: "Subtract 5"]     │
└─────────────────────────────┘

Step 3:
┌─────────────────────────────┐
│ Shows: 2x + 5 - 5 = 13 - 5  │
│        2x = 8               │
│ Asks: "Now divide by what?" │
│                             │
│ [Student: "Divide by 2"]    │
└─────────────────────────────┘

Step 4:
┌─────────────────────────────┐
│ Shows: x = 4                │
│ Verifies: 2(4) + 5 = 13 ✓   │
│ "Great discovery!"          │
└─────────────────────────────┘
```

### Key Differences from ChatGPT
| Feature | ChatGPT | Visual Tutor |
|---------|---------|--------------|
| Shows full answer | ✅ Immediately | ❌ Never (discovers step-by-step) |
| Asks questions | ❌ No | ✅ After each step |
| Waits for student | ❌ No | ✅ Yes, for each question |
| Uses visuals | ❌ No | ✅ Graphs, diagrams, vectors, molecules |
| Adapts to answer | ❌ No | ✅ Different path if wrong |
| Feels like teacher | ❌ No | ✅ Yes (interactive whiteboard) |

---

## Deliverables Timeline

| Week | Phase | Deliverables |
|------|-------|-------------|
| 1-2 | 0 | Board rendering fixed + visualization engines |
| 3-4 | 1 | Math teaching (algebra, geometry, trig) |
| 5-6 | 2 | Physics teaching (kinematics, dynamics, energy) |
| 7-8 | 3 | Chemistry teaching (structures, reactions) |
| 9-10 | 4 | Curriculum DB + adaptation system |
| 11-12 | 5 | Full integration + testing + polish |

---

## Investment & Impact

### Effort Required
- **Total**: 200+ developer hours
- **Duration**: 10-12 weeks
- **Team Size**: 2-3 developers (overlap on phases)
- **Cost**: ~$10,000-15,000 (dev rates)

### Expected Impact
- **Users**: Cambodia students (Grade 10-12)
- **Subjects**: Math, Physics, Chemistry
- **Languages**: Khmer + English
- **Platforms**: iOS, Android, Web
- **Competitive advantage**: Only AI tutor with interactive whiteboard + Khmer support

### Risk-Adjusted ROI
- **Low risk** (MVP works for Math alone)
- **High impact** (solves real problem: passive vs active learning)
- **Scalable** (can add more subjects, grades, languages)

---

## Critical Success Factors

### 1. Phase 0 Execution
- **Why critical**: Unblocks all other phases
- **Risk**: Rendering might have other hidden issues
- **Mitigation**: Fix in isolation, test thoroughly

### 2. Step Sequencing
- **Why critical**: Core differentiator from ChatGPT
- **Risk**: Student might skip ahead, see full answer
- **Mitigation**: Hide future steps, lock until question answered

### 3. LLM Quality
- **Why critical**: Step generation needs to be pedagogically sound
- **Risk**: AI might generate steps that confuse students
- **Mitigation**: Few-shot examples, human review, iterate

### 4. Subject Matter Expertise
- **Why critical**: Math ≠ Physics ≠ Chemistry teaching patterns
- **Risk**: Generic explanations don't work
- **Mitigation**: Domain experts review each subject, build subject-specific templates

### 5. Curriculum Alignment
- **Why critical**: Must match Cambodia MOE standards
- **Risk**: Could teach wrong concepts at wrong grade level
- **Mitigation**: Get curriculum docs, validate learning outcomes

---

## Next Immediate Steps

### This Week
1. **Review this audit** (everyone reads & understands)
2. **Assign team members** (who does Phase 0.1, 0.2, 0.3?)
3. **Set up process** (code review, testing, QA gates)
4. **Kick off Phase 0.1** (board rendering fix)

### By Next Monday (Sept 2)
1. Phase 0.1 rendering system implemented
2. RichMediaCanvas widget working
3. Basic tests passing
4. PR ready for review

### By Week 2 End (Sept 8)
1. Phase 0.2 (renderers) at 50% complete
2. Phase 0.3 (models) designed and approved
3. Backend API routes stubbed
4. Problem ready for Phase 1 (Math teaching)

---

## Questions & Decisions

### For Stakeholders
1. **Budget**: $10-15k development cost - approved?
2. **Timeline**: 10-12 weeks realistic? OK?
3. **Team**: Need 2-3 devs or outsource? Budget available?
4. **Scope**: Focus on Math first, expand later? OK?

### For Development Team
1. **Team lead**: Who owns this project end-to-end?
2. **Phase owners**: Who owns Phase 0, 1, 2, etc.?
3. **Code review**: Who reviews PRs? Quality bar?
4. **Escalation**: How to handle blockers?

### For Curriculum
1. **MOE alignment**: Where do we get official curriculum?
2. **Problem bank**: Who writes problems? How many per topic?
3. **Teacher review**: Can Cambodian teachers review our sequences?
4. **Khmer content**: Who translates/writes in Khmer?

---

## Key Documents

| Document | Purpose | Audience |
|----------|---------|----------|
| VISUAL_TUTOR_CAMBODIA_REVISED_PLAN.md | Vision & teaching patterns | Everyone |
| VISUAL_TUTOR_TECHNICAL_SPEC.md | Data models & APIs | Developers |
| VISUAL_TUTOR_AUDIT_CURRENT_STATE.md | What works, what's broken | Developers |
| VISUAL_TUTOR_IMPLEMENTATION_PLAN.md | How to build (phase by phase) | Developers |
| VISUAL_TUTOR_IMPLEMENTATION_LOG.md | Progress tracking | Project manager |
| AI_IMPLEMENTATION_PROMPTS.md | Prompts for Claude/Codex | AI operators |
| VISUAL_TUTOR_QUICK_START.md | Code examples | Developers |

---

## Contact & Escalation

- **Project Lead**: TBD
- **Flutter Lead**: TBD
- **Backend Lead**: TBD
- **Curriculum Lead**: TBD
- **Weekly Sync**: Monday 10am (30 min)

---

## Approval & Sign-Off

| Role | Name | Date | Notes |
|------|------|------|-------|
| Project Sponsor | TBD | TBD | Approves scope, budget, timeline |
| Tech Lead | TBD | TBD | Approves architecture |
| QA/Testing | TBD | TBD | Approves quality bar |
| Curriculum | TBD | TBD | Approves educational approach |

---

## Summary

**What**: Interactive AI teacher with live whiteboard for Cambodia students (Math, Physics, Chemistry)  
**Why**: Current ChatGPT-style tutoring is passive; students need active learning with visuals  
**How**: Step-by-step teaching with student interaction, adaptive branching, rich visualizations  
**When**: 10-12 weeks starting Aug 26, 2024  
**Cost**: ~$10-15k  
**Payoff**: Real competitive advantage (only Khmer AI tutor with interactive whiteboard)

**Status**: Phase 0 audit complete, ready to start building  
**Next**: Assign team, kick off Phase 0.1 (board rendering fix)

---

**Created**: August 26, 2024  
**Status**: Ready for decision & approval  
**Confidence**: HIGH (plan is detailed, risks mitigated, timeline realistic)
