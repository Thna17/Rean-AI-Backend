"""VISUAL_TUTOR_SCOPE_LOCK restricts traffic to Grade 12 limits-of-functions
while the rest of the dynamic pipeline is being stabilized (see
api.core.config.Settings.VISUAL_TUTOR_SCOPE_LOCK and orchestrator.py's
_is_grade12_math_limits_request). Physics/chemistry/other grades stay
implemented -- these tests only check that they're gated off, not gone.
"""

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorStepTurnRequest,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import (
    handle_visual_tutor_step_turn,
    handle_visual_tutor_turn,
)


@pytest.fixture(autouse=True)
def _scope_lock_enabled(monkeypatch):
    # tests/conftest.py disables the lock by default for the rest of the
    # suite (see visual_tutor_scope_lock_disabled_by_default) since it's
    # unrelated to what most tests exercise. This file's whole purpose is
    # testing the lock itself, so re-enable it here.
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_SCOPE_LOCK", "grade12_math_limits")


def test_grade_9_physics_request_is_scoped_out() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Physics",
            topic="Kinematics",
            message="A ball is thrown upward at 20 m/s. Find its max height.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 9},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"
    assert response.metadata["fallback_reason"] == "out_of_scope_lock"
    assert "Grade 10–12" in response.spoken_text
    assert "Mathematics" in response.spoken_text


def test_grade_12_limits_request_proceeds_normally() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Limits of Functions",
            message="Find the limit of f(x) = 2x + 1 as x approaches 3",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("generation_path") != "scope_locked"
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"


def test_other_grade_12_math_topic_is_still_scoped_out() -> None:
    # Grade 12 and Mathematics alone aren't enough -- the topic must resolve
    # to limits-of-functions specifically.
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Exponential and Logarithmic Functions",
            message="Solve log(x) = 2",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"


def test_step_turn_grade_10_physics_is_scoped_out() -> None:
    import asyncio

    response = asyncio.run(
        handle_visual_tutor_step_turn(
            VisualTutorStepTurnRequest(
                user_id="student-1",
                session_id="session-1",
                subject="physics",
                message="",
                action="submit",
            ),
            problem_text="A ball is thrown upward at 20 m/s. Find its max height.",
            grade=10,
        )
    )

    assert response.expert_metadata["scope_locked"] is True
    assert response.recommended_action == "out_of_scope"
