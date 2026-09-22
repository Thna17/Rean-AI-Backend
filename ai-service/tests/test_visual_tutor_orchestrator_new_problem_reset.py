from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)

from api.services.visual_tutor import orchestrator

import pytest

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


def test_new_problem_reset_does_not_repeat_curriculum_retrieval(monkeypatch) -> None:
    """A new problem resets state in-place instead of recursively restarting a turn."""
    original_retrieve = orchestrator.retrieve_curriculum_context
    retrieval_requests = []

    def record_retrieval(request):
        retrieval_requests.append(request)
        return original_retrieve(request)

    monkeypatch.setattr(
        orchestrator,
        "retrieve_curriculum_context",
        record_retrieval,
    )

    response = orchestrator.handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="new-problem-reset-test",
            session_id="new-problem-reset-session",
            subject="Mathematics",
            topic="Linear Equations",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
            message="2x + 10 = 20",
            current_state=VisualTutorTurnState(
                problem_text="an earlier problem",
                current_step_index=3,
                hint_count=2,
                wrong_attempts=1,
            ),
            metadata={"grade": 10},
        )
    )

    # Recursive re-entry used to repeat the entire retrieval/planning path.
    assert len(retrieval_requests) == 1
    retrieved = retrieval_requests[0]
    assert retrieved.grade == 10
    assert retrieved.subject == "Mathematics"
    assert retrieved.topic == "Linear Equations"
    assert retrieved.message == "2x + 10 = 20"

    # Retrieval output still reaches the completed public tutor response.
    assert response.session_id == "new-problem-reset-session"
    assert response.metadata["curriculum_context"]
    assert response.metadata["curriculum_context"][0]["grade"] == 10
    assert response.metadata["curriculum_context"][0]["topic"] == "Linear Equations"
