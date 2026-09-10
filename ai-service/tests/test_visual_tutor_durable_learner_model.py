"""Acceptance tests for durable, concept-scoped Visual Tutor adaptation.

These tests use the deterministic memory update and planner boundary directly.
They deliberately avoid an LLM, MongoDB, and raw learner input so the privacy
and idempotency guarantees remain regression-testable.
"""
from __future__ import annotations

import json

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
    build_learner_memory_update,
    choose_memory_aware_representation,
)
from api.services.visual_tutor.public_response import project_public_tutor_turn


def _request(
    *,
    action: VisualTutorAction = VisualTutorAction.SUBMIT_STEP,
    locale: str | None = "en-US",
    hint_count: int = 0,
) -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id="learner-1",
        session_id="session-1",
        subject="Mathematics",
        topic="Linear Equations",
        message="student work must not be retained here",
        action=action,
        locale=locale,
        hint_count=hint_count,
    )


def _response(
    *,
    turn_id: str,
    status: str = "correct",
    verified: bool = True,
    representation: str = "equation_transformation",
    misconception: str | None = None,
    mode: VisualTutorTeachingMode = VisualTutorTeachingMode.STEP_CHECK,
    summary: dict[str, str] | None = None,
) -> VisualTutorTurnResponse:
    metadata: dict[str, object] = {
        "verification": {
            "status": status,
            "verified": verified,
            "reason_code": "wrong_inverse_operation" if misconception else "equivalent_step",
        },
        "teaching_plan": {
            "representation": representation,
            "learning_objective": "Use an inverse operation.",
            "teaching_message": "Do one operation on both sides.",
            "board_actions": [
                {
                    "id": "write-1",
                    "type": "write_text",
                    "sequence_index": 0,
                    "text": "Keep both sides balanced.",
                },
                {
                    "id": "task-1",
                    "type": "student_task",
                    "sequence_index": 1,
                    "text": "Which operation removes 5?",
                    "requires_student_response": True,
                    "task_type": "conceptual_operation",
                },
            ],
            "allowed_student_actions": ["submit_step", "request_hint"],
        },
        "learner_model_summary": summary
        or {
            "selected_concept": "linear_equation.inverse_operations",
            "evidence_category": "verified_correct",
            "next_step_reason": "advance_one_verified_step",
            "confidence_band": "high",
        },
    }
    if misconception:
        metadata["misconception_type"] = misconception
    return VisualTutorTurnResponse(
        session_id="session-1",
        turn_id=turn_id,
        spoken_text="Try one small step.",
        display_text="Try one small step.",
        teaching_mode=mode,
        final_answer_locked=True,
        student_task="Which operation removes 5?",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata=metadata,
    )


def _summary(turn_id: str, *, board_version: int = 1) -> dict[str, object]:
    return {
        "session_id": "session-1",
        "turn_id": turn_id,
        "status": "active",
        "representation": "equation_transformation",
        "board_history": {
            "board_version": board_version,
            "representation": "equation_transformation",
            "action_types": ["write_text", "student_task"],
        },
    }


def test_correct_response_records_concept_mastery_and_one_step_advance_evidence() -> None:
    memory = build_learner_memory_update(
        previous=None,
        request=_request(),
        response=_response(turn_id="turn-correct"),
        session_summary=_summary("turn-correct"),
    )

    concept = memory.concept_mastery["linear_equation.inverse_operations"]
    assert concept["attempts"] == 1
    assert concept["correct_attempts"] == 1
    assert concept["confidence_band"] == "high"
    assert memory.recorded_turn_ids == ["turn-correct"]


def test_wrong_then_repeated_wrong_records_one_recurring_misconception_and_targeted_evidence() -> None:
    first = build_learner_memory_update(
        previous=None,
        request=_request(),
        response=_response(
            turn_id="turn-wrong-1",
            status="invalid",
            verified=False,
            misconception="wrong_inverse_operation",
            summary={
                "selected_concept": "linear_equation.inverse_operations",
                "evidence_category": "wrong_attempt",
                "next_step_reason": "reteach_one_misconception",
                "confidence_band": "low",
            },
        ),
        session_summary=_summary("turn-wrong-1"),
    )
    second = build_learner_memory_update(
        previous=first,
        request=_request(),
        response=_response(
            turn_id="turn-wrong-2",
            status="invalid",
            verified=False,
            misconception="wrong_inverse_operation",
            summary={
                "selected_concept": "linear_equation.inverse_operations",
                "evidence_category": "repeated_misconception",
                "next_step_reason": "targeted_error_analysis",
                "confidence_band": "low",
            },
        ),
        session_summary=_summary("turn-wrong-2", board_version=2),
    )

    concept = second.concept_mastery["linear_equation.inverse_operations"]
    assert concept["attempts"] == 2
    assert concept["incorrect_attempts"] == 2
    assert concept["recurring_misconceptions"] == ["wrong_inverse_operation"]
    assert second.misconceptions[-2:] == [
        "wrong_inverse_operation",
        "wrong_inverse_operation",
    ]


def test_hint_stuck_and_explain_differently_keep_evidence_but_change_representation() -> None:
    memory = LearnerMemoryProfile(
        user_id="learner-1",
        subject="Mathematics",
        topic="Linear Equations",
        topic_key="linear equations",
        representations_used=["equation_transformation"],
    )
    hinted = build_learner_memory_update(
        previous=memory,
        request=_request(action=VisualTutorAction.REQUEST_HINT, hint_count=1),
        response=_response(turn_id="turn-hint"),
        session_summary=_summary("turn-hint"),
    )
    stuck = build_learner_memory_update(
        previous=hinted,
        request=_request(action=VisualTutorAction.REQUEST_STUCK_HELP),
        response=_response(
            turn_id="turn-stuck",
            representation="balance_scale",
            mode=VisualTutorTeachingMode.STUCK_HELP,
        ),
        session_summary=_summary("turn-stuck", board_version=2),
    )
    changed = choose_memory_aware_representation(
        memory=stuck,
        candidate="equation_transformation",
        alternatives=["balance_scale", "worked_example"],
        intent="request_explain_differently",
    )

    assert hinted.hint_levels_used[-1] >= 2
    assert stuck.stuck_events == 1
    assert changed != "equation_transformation"
    assert changed in {"balance_scale", "worked_example"}


def test_resumed_session_reuses_concept_profile_and_language_without_leaking_raw_evidence() -> None:
    previous = LearnerMemoryProfile(
        user_id="learner-1",
        subject="Mathematics",
        topic="Linear Equations",
        topic_key="linear equations",
        preferred_language="km",
        concept_mastery={
            "linear_equation.inverse_operations": {
                "attempts": 2,
                "correct_attempts": 1,
                "incorrect_attempts": 1,
                "confidence_band": "developing",
            }
        },
        recorded_turn_ids=["previous-turn"],
    )
    resumed = build_learner_memory_update(
        previous=previous,
        request=_request(locale="km-KH"),
        response=_response(turn_id="resumed-turn"),
        session_summary=_summary("resumed-turn", board_version=4),
    )

    assert resumed.preferred_language == "km"
    assert resumed.concept_mastery["linear_equation.inverse_operations"]["attempts"] == 3
    assert resumed.recorded_turn_ids[-2:] == ["previous-turn", "resumed-turn"]
    context = resumed.orchestrator_context()
    assert "student work must not be retained here" not in json.dumps(context)
    assert "concept_mastery" not in context


def test_duplicate_or_stale_turn_does_not_double_count_attempts_or_mastery() -> None:
    response = _response(turn_id="turn-idempotent")
    first = build_learner_memory_update(
        previous=None,
        request=_request(),
        response=response,
        session_summary=_summary("turn-idempotent", board_version=1),
    )
    retry = build_learner_memory_update(
        previous=first,
        request=_request(),
        response=response,
        # A delayed board event may carry an obsolete version, but it has the
        # same server turn identity and must be ignored for learner evidence.
        session_summary=_summary("turn-idempotent", board_version=0),
    )

    assert retry.model_dump() == first.model_dump()
    assert retry.concept_mastery["linear_equation.inverse_operations"]["attempts"] == 1
    assert retry.mastery_evidence["verified_attempt_count"] == 1


def test_stored_summary_is_allowlisted_and_public_projection_discloses_no_private_evidence_or_answers() -> None:
    secret = "PRIVATE-ANSWER-AND-EVIDENCE"
    response = _response(
        turn_id="turn-public",
        summary={
            "selected_concept": "linear_equation.inverse_operations",
            "evidence_category": "wrong_attempt",
            "next_step_reason": "reteach_one_misconception",
            "confidence_band": "developing",
            "raw_evidence": secret,
            "hidden_answer": secret,
            "internal_reasoning": secret,
        },
    )
    response = response.model_copy(
        update={
            "metadata": {
                **response.metadata,
                "learner_memory": {"raw_student_text": secret},
                "solver_facts": {"solution": secret},
            }
        }
    )

    stored_summary = response.metadata["learner_model_summary"]
    assert {
        key: stored_summary[key]
        for key in (
            "selected_concept",
            "evidence_category",
            "next_step_reason",
            "confidence_band",
        )
    } == {
        "selected_concept": "linear_equation.inverse_operations",
        "evidence_category": "wrong_attempt",
        "next_step_reason": "reteach_one_misconception",
        "confidence_band": "developing",
    }
    public = project_public_tutor_turn(response)
    serialized = json.dumps(public)
    assert secret not in serialized
    assert "learner_model_summary" not in public
