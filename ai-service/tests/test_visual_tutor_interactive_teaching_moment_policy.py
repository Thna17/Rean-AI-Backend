"""Acceptance coverage for the one-interactive-moment tutor policy.

These tests deliberately use the public orchestrator for response shaping and
the deterministic planner for input-outcome choices.  They protect the
student-facing learning contract rather than implementation details of an LLM
prompt or a particular board renderer.
"""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.adaptive_tutor_planner import (
    VisualTutorMove,
    plan_adaptive_tutor_move,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)


def _linear_problem():
    return understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
        )
    )


def _input(
    *,
    intent: VisualTutorStudentIntent,
    relevance: VisualTutorInputRelevance,
    validation_result: str | None = None,
) -> VisualTutorInputUnderstandingResult:
    metadata = {}
    if validation_result is not None:
        metadata["validation_result"] = validation_result
    return VisualTutorInputUnderstandingResult(
        student_intent=intent,
        input_relevance=relevance,
        confidence=0.95,
        explanation="policy-test input",
        metadata=metadata,
    )


def _moment(response):
    moment = response.metadata.get("interactive_teaching_moment")
    assert isinstance(moment, dict), "normal responses must explicitly publish the moment"
    return moment


def test_normal_turn_has_one_bounded_interactive_teaching_moment_and_waits() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="interactive-policy-student",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            message="2x + 5 = 15",
        )
    )

    moment = _moment(response)
    assert moment["objective_count"] == 1
    assert 1 <= moment["visible_instructional_actions"] <= 3
    assert moment["student_task_count"] == 1
    assert moment["waiting_for_student_input"] is True
    assert response.teaching_stage is not None
    assert response.teaching_stage.max_actions_before_wait <= 3
    assert response.interaction is not None and response.interaction.input_enabled is True
    assert response.tutor_behavior is not None and response.tutor_behavior.should_wait is True


def test_correct_relevant_response_advances_exactly_one_step() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_linear_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            validation_result="correct_step",
        ),
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
        current_step_index=2,
    )

    assert decision.tutor_move == VisualTutorMove.TEACH_NEXT_VISUAL_STEP
    assert decision.board_action_budget <= 3
    assert decision.metadata["step_advance_count"] == 1
    assert decision.metadata["board_should_advance"] is True


def test_wrong_response_diagnoses_one_misconception_and_reteaches_only_it() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_linear_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            validation_result="incorrect",
        ),
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
        current_step_index=2,
        wrong_attempts=0,
    )

    assert decision.tutor_move == VisualTutorMove.DIAGNOSE_WRONG_INPUT
    assert decision.board_action_budget == 1
    assert decision.metadata["board_should_advance"] is False
    assert decision.metadata["misconception_count"] == 1
    assert decision.metadata["reteach_scope"] == "current_misconception_only"


@pytest.mark.parametrize(
    ("intent", "relevance"),
    [
        (VisualTutorStudentIntent.REQUEST_HINT, VisualTutorInputRelevance.CLARIFICATION),
        (
            VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
            VisualTutorInputRelevance.CLARIFICATION,
        ),
        (VisualTutorStudentIntent.STUCK, VisualTutorInputRelevance.STUCK),
    ],
)
def test_support_requests_change_representation_before_repeating_words(
    intent: VisualTutorStudentIntent,
    relevance: VisualTutorInputRelevance,
) -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_linear_problem(),
        student_input_understanding=_input(intent=intent, relevance=relevance),
        student_intent=intent,
        strategy_history=[{"representation": "equation_transformation"}],
    )

    assert decision.metadata["representation"] != "equation_transformation"
    assert decision.metadata["representation_changed"] is True
    assert decision.metadata["must_change_representation_before_rewording"] is True
    assert decision.board_action_budget <= 3


def test_show_answer_reveals_only_the_next_progressive_moment() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="interactive-policy-student",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            message="show answer",
            allow_final_answer=True,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                normalized_problem="2*x + 5 = 15",
                current_step_index=0,
            ),
        )
    )

    moment = _moment(response)
    assert moment["objective_count"] == 1
    assert 1 <= moment["visible_instructional_actions"] <= 3
    assert moment["student_task_count"] == 1
    assert moment["progressive_reveal"] is True
    assert moment["revealed_step_count"] == 1
    assert response.tutor_behavior is not None
    assert response.tutor_behavior.answer_reveal_strategy == "progressive_full_solution"
