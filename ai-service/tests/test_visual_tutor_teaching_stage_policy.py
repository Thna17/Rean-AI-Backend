from __future__ import annotations

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorInteractionType,
    VisualTutorLessonState,
    VisualTutorStageState,
    VisualTutorStudentIntent,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
    VisualTutorTurnState,
    VisualTutorBoardType,
    VisualTutorMasterySignal,
    VisualTutorNextStudentAction,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.policy import decide_visual_tutor_policy
from api.services.visual_tutor.response_sanitizer import sanitize_visual_tutor_response
from api.services.visual_tutor.teaching_stage_policy import (
    apply_live_teaching_stage_policy,
    decide_live_teaching_stage_policy,
)

import pytest

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


def test_first_problem_gives_one_focused_visual_action_group() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert response.teaching_stage is not None
    assert response.teaching_stage.stage_state == VisualTutorStageState.WAITING_FOR_STUDENT
    assert response.teaching_stage.lesson_state == VisualTutorLessonState.ASK
    assert response.teaching_stage.max_actions_before_wait == 1
    assert response.board_actions
    assert len({action.group_id for action in response.board_actions}) == 1
    assert response.interaction is not None
    assert response.interaction.input_enabled is True
    assert response.interaction.expected_answer_locked is True
    assert response.visual_focus is not None
    assert response.visual_focus.element_id is not None
    assert response.next_student_action is not None
    assert response.next_student_action.prompt
    assert response.tutor_behavior is not None
    assert response.tutor_behavior.max_actions_before_wait == 1
    assert response.tutor_behavior.answer_reveal_strategy == "guided_learning_locked"


def test_direct_solve_request_does_not_reveal_full_solution() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Please solve this fully: 2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert response.final_answer_locked is True
    assert response.teaching_stage is not None
    assert response.teaching_stage.lesson_state == VisualTutorLessonState.ASK
    assert response.teaching_stage.metadata["full_solution_allowed"] is False
    assert all("x = 5" not in (action.text or "") for action in response.board_actions)
    assert all("x = 5" not in (action.latex or "") for action in response.board_actions)


def test_stuck_request_gives_current_step_support() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                normalized_problem="2*x + 5 = 15",
            ),
            student_submitted_step=True,
        )
    )

    assert response.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert response.teaching_stage is not None
    assert response.teaching_stage.stage_state == VisualTutorStageState.ADAPTING
    assert response.teaching_stage.lesson_state == VisualTutorLessonState.RETEACH_OR_CONTINUE
    assert response.teaching_stage.turn_goal is not None
    assert "current step simpler" in response.teaching_stage.turn_goal
    assert response.final_answer_locked is True


def test_wrong_answer_triggers_evaluate_and_reteach() -> None:
    input_understanding = VisualTutorInputUnderstandingResult(
        student_intent=VisualTutorStudentIntent.SUBMITTED_STEP,
        input_relevance=VisualTutorInputRelevance.RELEVANT_STEP,
        confidence=0.9,
        explanation="The input is a relevant but incorrect step.",
        metadata={"validation_result": "incorrect", "misconception_type": "operation"},
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="2x = 20",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text="2x + 5 = 15",
            normalized_problem="2*x + 5 = 15",
        ),
        student_submitted_step=True,
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        is_correct_step=False,
        problem_type="linear_equation_one_variable",
        input_understanding=input_understanding,
    )
    live_policy = decide_live_teaching_stage_policy(
        request,
        policy,
        input_understanding=input_understanding,
    )

    assert live_policy.stage_state == VisualTutorStageState.EVALUATING
    assert live_policy.lesson_state == VisualTutorLessonState.RETEACH_OR_CONTINUE
    assert live_policy.should_evaluate is True
    assert live_policy.should_reteach is True
    assert live_policy.final_answer_locked is True


def test_show_answer_request_unlocks_progressive_reveal() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="show answer",
        action=VisualTutorAction.REQUEST_FINAL_ANSWER,
        current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )
    live = decide_live_teaching_stage_policy(request, policy)

    assert live.final_answer_locked is False
    assert live.full_solution_allowed is True
    assert live.lesson_state == VisualTutorLessonState.VERIFY


def test_active_turn_with_legacy_board_gets_required_live_contract_fields() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="Explain photosynthesis",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type="biology_concept",
        known_solver_available=False,
    )
    legacy_response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Let's start with the main idea.",
        display_text="Plants use light to make food.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="What energy source do plants use?",
        board=VisualTutorBoard(
            type=VisualTutorBoardType.FORMULA_CARD,
            title="Photosynthesis",
            items=[],
        ),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
    )

    response = apply_live_teaching_stage_policy(request, legacy_response, policy)

    assert response.board_actions
    assert response.interaction is not None
    assert response.interaction.prompt == "What energy source do plants use?"
    assert response.visual_focus is not None
    assert response.next_student_action is not None
    assert response.next_student_action.prompt == "What energy source do plants use?"
    assert response.tutor_behavior is not None
    assert response.tutor_behavior.should_draw is True


def test_live_policy_limits_response_to_next_teaching_moment() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="2x + 5 = 15",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )
    response = handle_visual_tutor_turn(request).model_copy(
        update={
            "board_actions": [],
            "canvas_actions": [
                VisualTutorCanvasAction(
                    id="group-1-action",
                    type=VisualTutorCanvasActionType.WRITE_TEXT,
                    text="Current step",
                    metadata={"current_step": True, "group_id": "current-step"},
                ),
                VisualTutorCanvasAction(
                    id="group-2-action",
                    type=VisualTutorCanvasActionType.WRITE_TEXT,
                    text="Future step",
                    metadata={"group_id": "future-step"},
                ),
            ]
        }
    )

    live_response = apply_live_teaching_stage_policy(request, response, policy)

    assert live_response.teaching_stage is not None
    assert live_response.teaching_stage.max_actions_before_wait == 1
    assert len({action.group_id for action in live_response.board_actions}) == 1
    assert all("Future step" not in (action.text or "") for action in live_response.board_actions)


def test_final_answer_unlocked_by_policy_in_response_contract() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                normalized_problem="2*x + 5 = 15",
            ),
        )
    )

    assert response.final_answer_locked is False
    assert response.teaching_stage is not None
    assert response.tutor_behavior is not None
    assert response.tutor_behavior.answer_reveal_strategy == "progressive_full_solution"
    assert response.next_student_action is not None
    assert response.next_student_action.expected_answer_locked is False


def test_sanitizer_scans_next_student_action_while_locked() -> None:
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Try one step first.",
        display_text="Try one step first.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="Try one step.",
        board=VisualTutorBoard(
            type=VisualTutorBoardType.FORMULA_CARD,
            title="Check",
            items=[],
        ),
        next_student_action=VisualTutorNextStudentAction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt="Is the answer x = 5?",
        ),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
    )

    sanitized = sanitize_visual_tutor_response(response)

    assert sanitized.next_student_action is not None
    assert "x = 5" not in sanitized.next_student_action.prompt
    assert sanitized.next_student_action.expected_answer_locked is True
    assert sanitized.metadata["sanitization"]["applied"] is True
    assert "next_student_action" in sanitized.metadata["sanitization"]["fields"]


def test_locked_policy_hides_final_answer_board_actions() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="2x + 5 = 15",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        current_state=VisualTutorTurnState(problem_text="2x + 5 = 15"),
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    ).model_copy(
        update={
            "board_actions": [],
            "canvas_actions": [
                VisualTutorCanvasAction(
                    id="final-answer",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    latex="x = 5",
                    metadata={"is_final_answer": True},
                )
            ]
        }
    )

    live_response = apply_live_teaching_stage_policy(request, response, policy)

    assert live_response.board_actions[0].type == VisualTutorCanvasActionType.HIDE
    assert live_response.board_actions[0].locked is True
    assert live_response.board_actions[0].metadata["final_answer_locked"] is True


def test_khmer_phrase_chooses_khmer_friendly_mode() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="ខ្ញុំមិនយល់",
            locale="km-KH",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                normalized_problem="2*x + 5 = 15",
            ),
            student_submitted_step=True,
        )
    )

    assert response.speech is not None
    assert response.speech.language == "km"
    assert response.interaction is not None
    assert response.interaction.submit_label == "ឆ្លើយ"
    assert VisualTutorAllowedAction.STUCK in response.allowed_actions
    assert response.teaching_stage is not None
    assert response.teaching_stage.metadata["use_khmer_teaching"] is True
    assert response.interaction.type in {
        VisualTutorInteractionType.TEXT_RESPONSE,
        VisualTutorInteractionType.NUMERIC_INPUT,
    }
