# Phase 0.3 Quick Start Guide

## Files Created

### Backend (Python/FastAPI)
```
ai-service/api/models/teaching_step.py        ← Data models
ai-service/api/services/step_sequencing_service.py  ← Business logic
ai-service/api/routes/step_sequencing.py      ← REST API
```

### Frontend (Dart/Flutter/Riverpod)
```
ai_tutor/lib/features/visual_tutor/domain/entities/teaching_step_entity.dart
                                               ← Domain entities
ai_tutor/lib/features/visual_tutor/presentation/providers/teaching_step_provider.dart
                                               ← State management
ai_tutor/lib/features/visual_tutor/presentation/pages/step_sequencing_page.dart
                                               ← UI page
```

## Key Classes

### Backend Models
- `TeachingStep`: Single step in lesson
- `TeachingPlan`: Complete multi-step lesson
- `EvaluationResult`: Response evaluation
- `StepType`, `Subject`, `DifficultyLevel`: Enums

### Backend Service
- `StepSequencingService.generate_teaching_plan()`: Create lesson plan
- `StepSequencingService.evaluate_step_response()`: Evaluate answer
- `StepSequencingService.get_next_step()`: Route to next step

### Backend API
- `POST /api/v1/teaching/plans`: Create plan
- `POST /api/v1/teaching/steps/{step_id}/evaluate`: Evaluate response
- `GET /api/v1/teaching/steps/{step_id}`: Get step details

### Frontend State
- `TeachingSessionState`: Session state
- `TeachingSessionNotifier`: State management
- `teachingSessionProvider`: Riverpod provider
- Computed providers: progress, loading, error, feedback, etc.

### Frontend UI
- `StepSequencingPage`: Main teaching interface
  - Visualizations
  - Student interactions
  - Feedback
  - Navigation controls

## Usage Example

### Backend Usage
```python
service = StepSequencingService(kg_service, model_gateway)

# Generate a plan
plan = await service.generate_teaching_plan(
    problem="Solve 2x + 5 = 13",
    subject=Subject.MATHEMATICS,
    grade_level=10,
    learning_style="visual",
)

# Evaluate response
result = await service.evaluate_step_response(
    step=plan.steps[0],
    student_response="Given: 2x + 5 = 13, Find: x",
)

# Get next step
next_step = service.get_next_step(plan, plan.steps[0].id, result)
```

### Frontend Usage
```dart
// In a ConsumerWidget
final session = ref.watch(teachingSessionProvider);
final progress = ref.watch(teachingProgressProvider);

// Load a plan
await ref.read(teachingSessionProvider.notifier).loadPlan(
  problem: "Solve 2x + 5 = 13",
  subject: Subject.mathematics,
  gradeLevel: 10,
);

// Evaluate response
await ref.read(teachingSessionProvider.notifier).evaluateResponse(
  response: "x = 4",
);

// Move to next step
await ref.read(teachingSessionProvider.notifier).nextStep();

// Navigate
StepSequencingPage(
  problem: "Solve 2x + 5 = 13",
  subject: Subject.mathematics,
  gradeLevel: 10,
)
```

## Integration Checklist

### Backend
- [ ] Register routes in main FastAPI app
- [ ] Wire up KnowledgeGraphService
- [ ] Wire up ModelGateway
- [ ] Implement database persistence
- [ ] Add authentication/authorization
- [ ] Create API tests

### Frontend
- [ ] Inject ApiClient via Riverpod
- [ ] Connect to backend API endpoints
- [ ] Integrate RichMediaCanvas for visualizations
- [ ] Add audio/TTS support
- [ ] Create widget/provider tests
- [ ] Add error handling UI

## Architecture

```
Student Problem
    ↓
[Backend: StepSequencingService]
    ├─ Analyze problem
    ├─ Generate steps
    └─ Create adaptive rules
    ↓
[Step Sequence Loop]
    ├─ Show step with visualization
    ├─ Collect student response
    ├─ Evaluate response
    ├─ Provide feedback
    └─ Route to next step
    ↓
[Frontend: StepSequencingPage]
    ├─ Display step content
    ├─ Handle student input
    ├─ Show feedback
    └─ Navigate steps
    ↓
Session Complete
```

## Step Types

1. **Explanation** - AI explains a concept
2. **Visualization** - Show diagram/graph
3. **Question** - Ask student to respond
4. **Feedback** - Respond to answer
5. **Hint** - Provide a clue
6. **Check** - Verify understanding

## Subject-Specific Sequences

### Mathematics
1. Understand problem
2. Choose method
3. Work through solution
4. Verify answer

### Physics
1. Visualize situation
2. Identify quantities
3. Apply principles
4. Perform calculations
5. Interpret results

### Chemistry
1. Identify substances
2. Visualize molecules
3. Balance equation
4. Verify stoichiometry

## Key Features

### Socratic Method
- Step-by-step guidance
- Questions, not answers
- Progressive complexity
- Student-centered

### Adaptive Routing
- Correct answer → next step
- Wrong answer → hint/retry
- Hint used → alternative path
- Timeout → fallback

### Progress Tracking
- Current step / total
- Percentage complete
- Hints used
- Wrong attempts

### Responsive Design
- Mobile-first layout
- Touch-friendly inputs
- Animations
- Accessible widgets

## Debugging

### Backend Logs
```python
logger.info(f"Generating plan for: {problem}")
logger.debug(f"Analysis: {analysis}")
logger.error(f"Error: {str(e)}")
```

### Frontend Logs
```dart
print('[INFO] $msg')
print('[ERROR] $msg')
print('[WARNING] $msg')
```

### Testing
```python
# Test service
service = StepSequencingService()
plan = await service.generate_teaching_plan(...)
assert len(plan.steps) > 0

# Test API
client = TestClient(app)
response = client.post("/api/v1/teaching/plans", json=request)
assert response.status_code == 201
```

## Performance Tips

### Backend
- Cache KG lookups
- Async I/O throughout
- Batch model calls
- Connection pooling

### Frontend
- Lazy load renderers
- Cache plans locally
- Minimize rebuilds
- Use const constructors

## Common Issues

| Issue | Solution |
|-------|----------|
| Import errors | Check __init__.py files |
| Type errors | Use Optional[] for Python 3.9 |
| API timeout | Increase timeout_ms in backend |
| State not updating | Check Riverpod provider watches |
| Visualization missing | Verify board_actions populated |

## Resources

- [Pydantic v2 Docs](https://docs.pydantic.dev/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Riverpod Docs](https://riverpod.dev/)
- [Flutter Docs](https://flutter.dev/docs)
- [Dart Docs](https://dart.dev/guides)
