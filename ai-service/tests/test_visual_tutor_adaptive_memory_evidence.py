"""Evidence-based adaptation and privacy regression tests.

These tests deliberately exercise the deterministic planner with only the
bounded learner-memory projection that routes attach for an authenticated
student.  They do not require an LLM or a database.
"""
from __future__ import annotations

import json

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardType,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorMasterySignal,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorStudentIntent,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.adaptive_tutor_planner import (
    VisualTutorExplanationMode,
    VisualTutorMove,
    plan_adaptive_tutor_move,
)
from api.services.visual_tutor.learner_memory import LearnerMemoryProfile
from api.services.visual_tutor.problem_understanding import understand_visual_tutor_problem
from api.services.visual_tutor.public_response import project_public_tutor_turn


def _problem(*, locale: str | None = None):
    return understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            locale=locale,
        )
    )


def _input(intent: VisualTutorStudentIntent, *, validation: str | None = None):
    metadata = {"validation_result": validation} if validation else {}
    relevance = (
        VisualTutorInputRelevance.STUCK
        if intent == VisualTutorStudentIntent.STUCK
        else VisualTutorInputRelevance.CLARIFICATION
        if intent == VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY
        else VisualTutorInputRelevance.RELEVANT_STEP
    )
    return VisualTutorInputUnderstandingResult(
        student_intent=intent,
        input_relevance=relevance,
        confidence=0.9,
        explanation="test",
        metadata=metadata,
    )


def _student_model(*, memory: dict | None = None, **values: object) -> dict:
    return {
        "understanding": "exploring",
        "recent_mistakes": [],
        "hint_level": 0,
        "wrong_attempt_streak": 0,
        "preferred_language": "en",
        "recommended_depth": "standard",
        "metadata": {"learner_memory": memory or {}},
        **values,
    }


def test_new_beginner_gets_one_small_visual_guiding_task_and_locked_answer() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
        student_model=_student_model(),
    )

    assert decision.tutor_move == VisualTutorMove.ASK_GUIDING_QUESTION
    assert decision.metadata["representation"] in {
        "balance_scale",
        "conceptual_explanation",
        "worked_example",
    }
    assert decision.board_action_budget == 1
    assert decision.final_answer_locked is True
    assert decision.metadata["learner_level"] == "beginner"
    assert decision.metadata["task_profile"] == "conceptual_micro_task"
    assert decision.metadata["concise_challenge"] is False


def test_confident_learner_uses_evidence_based_concise_challenge_mode() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
        student_model=_student_model(
            memory={
                "readiness": "ready_for_challenge",
                "verified_attempt_count": 3,
                "representations_used": ["equation_transformation"],
                "misconceptions": [],
            }
        ),
    )

    assert decision.metadata["adaptive_memory_applied"] is True
    assert decision.metadata["concise_challenge"] is True
    assert decision.metadata["learner_level"] == "confident"
    assert decision.metadata["task_profile"] == "concise_transformation_challenge"
    assert decision.metadata["representation"] == "equation_transformation"
    assert decision.final_answer_locked is True


def test_repeated_exact_misconception_selects_error_analysis_not_generic_reteach() -> None:
    misconception = "wrong_inverse_operation"
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            VisualTutorStudentIntent.SUBMITTED_STEP, validation="incorrect"
        ),
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
        student_model=_student_model(
            memory={
                "misconceptions": [misconception, misconception],
                "representations_used": ["equation_transformation"],
            },
            recent_mistakes=[misconception, misconception],
        ),
    )

    assert decision.tutor_move == VisualTutorMove.DIAGNOSE_WRONG_INPUT
    assert decision.metadata["representation"] == "error_analysis"
    assert decision.metadata["recent_mistakes"] == [misconception, misconception]
    assert decision.final_answer_locked is True


def test_stuck_learner_changes_representation_and_uses_a_smaller_reteach_strategy() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(VisualTutorStudentIntent.STUCK),
        student_intent=VisualTutorStudentIntent.STUCK,
        student_model=_student_model(
            memory={"representations_used": ["equation_transformation"]}
        ),
    )

    assert decision.tutor_move == VisualTutorMove.RETEACH_DIFFERENTLY
    assert decision.metadata["representation"] != "equation_transformation"
    assert decision.metadata["representation"] in {"balance_scale", "worked_example"}
    assert decision.metadata["must_change_explanation_strategy"] is True
    assert decision.final_answer_locked is True


def test_explain_differently_selects_a_genuinely_new_representation() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY
        ),
        student_intent=VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
        student_model=_student_model(
            memory={"representations_used": ["equation_transformation"]}
        ),
    )

    assert decision.metadata["explain_differently_requires_representation_change"] is True
    assert decision.metadata["representation"] != "equation_transformation"
    assert decision.metadata["alternate_representation"] == "equation_transformation"


def test_khmer_memory_and_problem_select_khmer_without_changing_math_strategy() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(locale="km-KH"),
        student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
        student_model=_student_model(memory={"preferred_language": "km"}),
    )

    assert decision.explanation_mode == VisualTutorExplanationMode.KHMER
    assert decision.metadata["representation"] in {
        "balance_scale",
        "conceptual_explanation",
        "worked_example",
    }


def test_returning_profile_retains_evidence_but_isolated_profiles_have_no_shared_state() -> None:
    first = LearnerMemoryProfile(
        user_id="student-a",
        subject="Mathematics",
        topic="Linear Equations",
        topic_key="linear equations",
        misconceptions=["sign_error"],
        representations_used=["balance_scale"],
        recent_session_summaries=[{"session_id": "session-a", "turn_id": "turn-a"}],
    )
    second = LearnerMemoryProfile(
        user_id="student-b",
        subject="Mathematics",
        topic="Linear Equations",
        topic_key="linear equations",
    )

    assert first.orchestrator_context()["misconceptions"] == ["sign_error"]
    assert first.recent_session_summaries[-1]["session_id"] == "session-a"
    assert second.orchestrator_context()["misconceptions"] == []
    assert second.representations_used == []
    assert first.user_id != second.user_id


def test_public_turn_projection_never_exposes_private_memory_rag_or_solver_facts() -> None:
    secret = "PRIVATE-LEARNER-EVIDENCE"
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Try one small step.",
        display_text="Try one small step.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="What operation removes 5?",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata={
            "learner_memory": {"misconceptions": [secret]},
            "curriculum_context": {"chunks": [{"content": secret}]},
            "solver_facts": {"solution_set": secret},
            "teaching_plan": {
                "schema_version": 1,
                "representation": "equation_transformation",
                "learning_objective": "Use inverse operations.",
                "teaching_message": "Remove 5 from both sides.",
                "board_actions": [
                    {
                        "id": "text-1",
                        "type": "write_text",
                        "text": "Keep both sides balanced.",
                        # Board actions are persisted server-side and can carry
                        # internal planner hints.  The public projection must
                        # never forward these fields to Flutter.
                        "expected_step": secret,
                        "expected_operation": secret,
                        "metadata": {
                            "learner_memory": secret,
                            "curriculum_chunk": secret,
                            "solver_facts": secret,
                        },
                    },
                    {
                        "id": "task-1",
                        "type": "student_task",
                        "text": "What operation removes 5?",
                        "requires_student_response": True,
                        "task_type": "conceptual_operation",
                    },
                ],
                "allowed_student_actions": ["submit_step"],
            },
            "verification": {
                "status": "cannot_verify",
                "verified": False,
                "student_message": "Write one equation step.",
                "concise_evidence": "No submitted step yet.",
                "solution_set": secret,
            },
        },
    )

    projected = project_public_tutor_turn(response)
    serialized = json.dumps(projected)
    assert secret not in serialized
    assert "learner_memory" not in serialized
    assert "solver_facts" not in serialized
    assert "curriculum_context" not in serialized
