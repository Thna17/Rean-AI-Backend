from __future__ import annotations

from api.models.visual_tutor import (
    VisualTutorAllowedAction,
    TeachingBoardElement,
    TeachingBoardElementType,
    TeachingBoardState,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorInteractionType,
    VisualTutorLessonState,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorStageState,
    VisualTutorStudentIntent,
)
from api.services.visual_tutor.adaptive_tutor_planner import (
    ADAPTIVE_TUTOR_PLANNER_VERSION,
    VisualTutorAnswerLockDecision,
    VisualTutorExplanationMode,
    VisualTutorMove,
    plan_adaptive_tutor_move,
)
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)


def _problem(message: str = "2x + 5 = 15", *, locale: str | None = None):
    return understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message=message,
            locale=locale,
        )
    )


def _input(
    *,
    intent: VisualTutorStudentIntent,
    relevance: VisualTutorInputRelevance,
    validation_result: str | None = None,
):
    metadata = {}
    if validation_result:
        metadata["validation_result"] = validation_result
    return VisualTutorInputUnderstandingResult(
        student_intent=intent,
        input_relevance=relevance,
        confidence=0.9,
        explanation="test input",
        metadata=metadata,
    )


def test_explain_differently_switches_to_a_real_alternate_representation() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
            relevance=VisualTutorInputRelevance.CLARIFICATION,
        ),
        student_intent=VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
        strategy_history=[{"representation": "equation_transformation"}],
    )

    assert decision.metadata["representation"] == "balance_scale"
    assert decision.metadata["alternate_representation"] == "equation_transformation"
    assert decision.metadata["explain_differently_requires_representation_change"] is True


def test_stuck_reteaches_current_visual_step_without_final_answer() -> None:
    board_state = TeachingBoardState(
        focus_element_id="step-1",
        elements=[
            TeachingBoardElement(
                id="step-1",
                type=TeachingBoardElementType.EQUATION,
                latex="2x + 5 = 15",
                focus=True,
            )
        ],
    )

    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.STUCK,
            relevance=VisualTutorInputRelevance.STUCK,
        ),
        teaching_board_state=board_state,
        current_step_index=0,
        stuck_count=0,
        student_intent=VisualTutorStudentIntent.STUCK,
    )

    assert decision.tutor_move == VisualTutorMove.RETEACH_DIFFERENTLY
    assert decision.stage_state == VisualTutorStageState.ADAPTING
    assert decision.lesson_state == VisualTutorLessonState.RETEACH_OR_CONTINUE
    assert decision.screen_state.value == "speaking_writing"
    assert decision.tutor_status == "Writing..."
    assert VisualTutorAllowedAction.STUCK in decision.quick_actions
    assert decision.board_action_budget == 1
    assert (
        decision.answer_lock_decision == VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER
    )
    assert decision.final_answer_locked is True
    assert decision.metadata["current_focus_element_id"] == "step-1"
    assert decision.metadata["reason"] == "student_is_stuck_reteach_current_step"
    assert decision.metadata["one_teaching_moment_per_turn"] is True
    assert decision.metadata["one_short_speech"] is True
    assert decision.metadata["one_focused_visual_update"] is True
    assert decision.metadata["one_student_task_or_question"] is True
    assert decision.metadata["llm_cannot_bypass_policy"] is True


def test_wrong_relevant_answer_highlights_first_mistake_only() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            validation_result="incorrect",
        ),
        current_step_index=0,
        wrong_attempts=0,
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
    )

    assert decision.tutor_move == VisualTutorMove.DIAGNOSE_WRONG_INPUT
    assert decision.screen_state.value == "check_my_work"
    assert decision.tutor_status == "Checking"
    assert decision.stage_state == VisualTutorStageState.EVALUATING
    assert decision.lesson_state == VisualTutorLessonState.RETEACH_OR_CONTINUE
    assert decision.board_action_budget == 1
    assert decision.metadata["highlight_first_mistake_only"] is True
    assert (
        decision.metadata["reason"]
        == "wrong_relevant_step_highlight_first_mistake_only"
    )
    assert decision.metadata["board_should_advance"] is False
    assert decision.metadata["wrong_input_does_not_advance_board"] is True


def test_off_topic_input_is_not_treated_as_submitted_step() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.UNKNOWN,
            relevance=VisualTutorInputRelevance.OFF_TOPIC,
        ),
        current_step_index=1,
        wrong_attempts=1,
    )

    assert decision.tutor_move == VisualTutorMove.DIAGNOSE_WRONG_INPUT
    assert decision.screen_state.value == "check_my_work"
    assert decision.stage_state == VisualTutorStageState.ADAPTING
    assert decision.interaction_type == VisualTutorInteractionType.TEXT_RESPONSE
    assert (
        decision.answer_lock_decision == VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER
    )
    assert decision.metadata["do_not_count_as_submitted_step"] is True
    assert decision.metadata["board_should_advance"] is False


def test_direct_answer_request_reveals_progressively_when_allowed() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.REQUEST_ANSWER,
            relevance=VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER,
        ),
        student_intent=VisualTutorStudentIntent.REQUEST_ANSWER,
        allow_final_answer=True,
        hint_count=1,
    )

    assert decision.tutor_move == VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY
    assert decision.screen_state.value == "final_verified_answer"
    assert decision.tutor_status == "Verified"
    assert decision.stage_state == VisualTutorStageState.DRAWING
    assert decision.lesson_state == VisualTutorLessonState.VERIFY
    assert decision.board_action_budget == 3
    assert decision.interaction_type == VisualTutorInteractionType.YES_NO
    assert (
        decision.answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL
    )
    assert decision.final_answer_locked is False
    assert decision.metadata["answer_reveal_progressive"] is True


def test_direct_answer_request_before_threshold_reveals_progressively() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.REQUEST_ANSWER,
            relevance=VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER,
        ),
        student_intent=VisualTutorStudentIntent.REQUEST_ANSWER,
    )

    assert decision.tutor_move == VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY
    assert decision.lesson_state == VisualTutorLessonState.VERIFY
    assert decision.board_action_budget == 3
    assert decision.final_answer_locked is False
    assert decision.answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL
    assert decision.metadata["answer_reveal_progressive"] is True


def test_valid_step_advances_one_visual_step() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            validation_result="correct_step",
        ),
        current_step_index=1,
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
        curriculum_context={"chunk_ids": ["math.g10.linear_equations"]},
    )

    assert decision.tutor_move == VisualTutorMove.TEACH_NEXT_VISUAL_STEP
    assert decision.screen_state.value == "speaking_writing"
    assert decision.stage_state == VisualTutorStageState.WAITING_FOR_STUDENT
    assert decision.lesson_state == VisualTutorLessonState.ASK
    assert decision.board_action_budget == 1
    assert decision.interaction_type == VisualTutorInteractionType.NUMERIC_INPUT
    assert decision.metadata["curriculum_context_available"] is True
    assert decision.metadata["planner"] == ADAPTIVE_TUTOR_PLANNER_VERSION
    assert decision.metadata["board_should_advance"] is True
    assert decision.metadata["valid_answer_advances_board"] is True


def test_repeated_stuck_unlocks_partial_solution() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.STUCK,
            relevance=VisualTutorInputRelevance.STUCK,
        ),
        stuck_count=1,
        student_intent=VisualTutorStudentIntent.STUCK,
    )

    assert decision.tutor_move == VisualTutorMove.REVEAL_PARTIAL_SOLUTION
    assert (
        decision.answer_lock_decision
        == VisualTutorAnswerLockDecision.ALLOW_PARTIAL_REVEAL
    )
    assert decision.partial_solution_allowed is True
    assert decision.final_answer_locked is True


def test_khmer_problem_uses_khmer_explanation_mode() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem("ខ្ញុំមិនយល់ 2x + 5 = 15", locale="km-KH"),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.STUCK,
            relevance=VisualTutorInputRelevance.STUCK,
        ),
        student_intent=VisualTutorStudentIntent.STUCK,
    )

    assert decision.explanation_mode == VisualTutorExplanationMode.KHMER


def test_student_model_wrong_streak_forces_simpler_reteach() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            validation_result="incorrect",
        ),
        current_step_index=1,
        wrong_attempts=0,
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
        student_model={
            "wrong_attempt_streak": 3,
            "recent_mistakes": ["wrong_inverse_operation"],
            "recommended_depth": "simple",
            "metadata": {},
        },
        strategy_history=[
            {
                "tutor_move": "check_student_answer",
                "asked_for_student_attempt": True,
            }
        ],
    )

    assert decision.tutor_move == VisualTutorMove.RETEACH_DIFFERENTLY
    assert decision.interaction_type == VisualTutorInteractionType.TEXT_RESPONSE
    assert decision.answer_lock_decision == VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER
    assert decision.metadata["adaptation_override"] == (
        "wrong_attempt_streak_requires_simpler_reteach"
    )
    assert decision.metadata["must_change_explanation_strategy"] is True


def test_repeated_pedagogy_switches_to_visual_hint() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            validation_result="incorrect",
        ),
        current_step_index=1,
        wrong_attempts=2,
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
        student_model={
            "wrong_attempt_streak": 2,
            "recent_mistakes": ["sign_error", "sign_error"],
            "metadata": {},
        },
        strategy_history=[
            {"tutor_move": "diagnose_wrong_input"},
            {"tutor_move": "diagnose_wrong_input"},
        ],
    )

    assert decision.tutor_move == VisualTutorMove.SHOW_VISUAL_HINT
    assert decision.board_action_budget >= 2
    assert decision.metadata["visual_hint_required"] is True
    assert decision.metadata["adaptation_override"] == (
        "repeated_mistake_prefers_visual_before_reveal"
    )


def test_visual_hint_after_stuck_switches_to_different_reteach() -> None:
    decision = plan_adaptive_tutor_move(
        problem_understanding=_problem(),
        student_input_understanding=_input(
            intent=VisualTutorStudentIntent.STUCK,
            relevance=VisualTutorInputRelevance.STUCK,
        ),
        current_step_index=1,
        wrong_attempts=1,
        student_intent=VisualTutorStudentIntent.STUCK,
        strategy_history=[{"tutor_move": "show_visual_hint"}],
    )

    assert decision.tutor_move == VisualTutorMove.RETEACH_DIFFERENTLY
    assert decision.metadata["adaptation_override"] == (
        "visual_hint_did_not_unstick_student"
    )
    assert decision.metadata["must_change_explanation_strategy"] is True
