from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardType,
    VisualTutorMasterySignal,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.learner_memory import (
    LearnerMemoryProfile,
    LearnerMemoryStore,
    build_learner_memory_update,
    choose_memory_aware_representation,
)


def _request(
    *,
    user_id: str = "student-1",
    action: VisualTutorAction = VisualTutorAction.SUBMIT_STEP,
    locale: str | None = None,
    hint_count: int | None = 0,
) -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id=user_id,
        session_id="session-1",
        subject="Mathematics",
        topic="Linear Equations",
        message="2x = 10",
        action=action,
        locale=locale,
        hint_count=hint_count,
    )


def _response(
    *,
    verification: dict,
    representation: str = "equation_transformation",
    strategy: str = "guided_step",
    teaching_mode: VisualTutorTeachingMode = VisualTutorTeachingMode.STEP_CHECK,
    misconception: str | None = None,
) -> VisualTutorTurnResponse:
    metadata = {
        "verification": verification,
        "teaching_plan": {"representation": representation},
        "explanation_strategy": strategy,
    }
    if misconception:
        metadata["misconception_type"] = misconception
    return VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Try the next small step.",
        display_text="Try the next small step.",
        teaching_mode=teaching_mode,
        final_answer_locked=True,
        student_task="Write the next equation.",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata=metadata,
    )


def test_beginner_memory_records_only_verified_evidence_and_is_not_ready_yet() -> None:
    memory = build_learner_memory_update(
        previous=None,
        request=_request(),
        response=_response(
            verification={"verified": True, "status": "correct", "reason": "equivalent step"}
        ),
    )

    assert memory.user_id == "student-1"
    assert memory.topic_key == "linear equations"
    assert len(memory.verified_successful_steps) == 1
    assert memory.verified_unsuccessful_steps == []
    assert memory.mastery_evidence == {
        "verified_success_count": 1,
        "verified_unsuccess_count": 0,
        "verified_attempt_count": 1,
        "verified_success_rate": 1.0,
        "readiness": None,
    }


def test_repeated_mistakes_choose_targeted_error_analysis() -> None:
    previous = LearnerMemoryProfile(
        user_id="student-1",
        topic="Linear Equations",
        topic_key="linear equations",
        misconceptions=["wrong_inverse_operation", "wrong_inverse_operation"],
        representations_used=["equation_transformation"],
    )
    chosen = choose_memory_aware_representation(
        memory=previous,
        candidate="equation_transformation",
        alternatives=["balance_scale", "error_analysis"],
    )

    assert chosen == "error_analysis"


def test_stuck_student_does_not_repeat_current_representation() -> None:
    memory = LearnerMemoryProfile(
        user_id="student-1",
        topic="Linear Equations",
        topic_key="linear equations",
        representations_used=["equation_transformation"],
    )

    chosen = choose_memory_aware_representation(
        memory=memory,
        candidate="equation_transformation",
        alternatives=["balance_scale", "worked_example"],
        stuck=True,
    )

    assert chosen == "balance_scale"


def test_advanced_student_becomes_ready_only_from_three_verified_successes() -> None:
    memory: LearnerMemoryProfile | None = None
    for turn in range(3):
        memory = build_learner_memory_update(
            previous=memory,
            request=_request(),
            response=_response(
                verification={"verified": True, "status": "correct"},
                representation="equation_transformation",
                strategy="concise_challenge",
            ).model_copy(update={"turn_id": f"turn-{turn}"}),
        )

    assert memory is not None
    assert memory.mastery_evidence["verified_success_count"] == 3
    assert memory.mastery_evidence["verified_success_rate"] == 1.0
    assert memory.mastery_evidence["readiness"] == "ready_for_challenge"
    assert memory.explanation_strategies_used[-1] == "concise_challenge"


def test_khmer_preference_is_remembered_while_math_evidence_remains_language_neutral() -> None:
    memory = build_learner_memory_update(
        previous=None,
        request=_request(locale="km-KH"),
        response=_response(verification={"verified": True, "status": "correct"}),
    )

    assert memory.preferred_language == "km"
    assert memory.verified_successful_steps[0]["status"] == "correct"
    assert "2x = 10" not in memory.verified_successful_steps[0].values()


def test_returning_student_keeps_recent_strategy_and_safe_session_summary() -> None:
    previous = LearnerMemoryProfile(
        user_id="student-1",
        topic="Linear Equations",
        topic_key="linear equations",
        representations_used=["balance_scale"],
        explanation_strategies_used=["worked_example"],
    )
    memory = build_learner_memory_update(
        previous=previous,
        request=_request(),
        response=_response(
            verification={"verified": True, "status": "mathematically_valid_but_inefficient"},
            representation="equation_transformation",
            strategy="concise_challenge",
        ),
        session_summary={
            "session_id": "session-1",
            "status": "active",
            "representation": "equation_transformation",
            "raw_student_text": "this must never persist",
            "internal_reasoning": "this must never persist",
        },
    )

    assert memory.representations_used == ["balance_scale", "equation_transformation"]
    assert memory.explanation_strategies_used == ["worked_example", "concise_challenge"]
    assert memory.recent_session_summaries == [
        {
            "session_id": "session-1",
            "status": "active",
            "representation": "equation_transformation",
        }
    ]


@pytest.mark.asyncio
async def test_memory_store_scopes_reads_to_authenticated_student_and_topic() -> None:
    profiles = AsyncMock()
    profiles.find_one = AsyncMock(return_value=None)
    database = {"visual_tutor_learner_memory": profiles}
    store = LearnerMemoryStore(database)  # type: ignore[arg-type]

    result = await store.get_for_authenticated_user(
        user_id="student-1",
        subject="Mathematics",
        topic="Linear Equations",
    )

    assert result is None
    profiles.find_one.assert_awaited_once_with(
        {
            "user_id": "student-1",
            "subject_key": "mathematics",
            "topic_key": "linear equations",
        }
    )
