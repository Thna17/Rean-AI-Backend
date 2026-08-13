from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardType,
    VisualTutorCanvasActionType,
    VisualTutorInteractionType,
    VisualTutorLessonState,
    VisualTutorMasterySignal,
    VisualTutorScreenState,
    VisualTutorStageState,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
    VisualTutorTurnState,
)
from api.services.visual_tutor.adaptive_tutor_planner import (
    AdaptiveTutorDecision,
    VisualTutorAnswerLockDecision,
    VisualTutorExplanationMode,
    VisualTutorMove,
)
from api.services.visual_tutor.orchestrator import _build_board_patch
from api.services.visual_tutor.session_store import _live_stage_snapshot_from_response


class _Session:
    hidden_element_ids = []
    locked_element_ids = []
    visible_board_elements = [
        {
            "id": "step-1",
            "type": "equation",
            "latex": "3x - 9 = 12",
            "sequence_index": 0,
            "metadata": {},
        },
        {
            "id": "step-2",
            "type": "equation",
            "latex": "3x = 21",
            "sequence_index": 1,
            "metadata": {},
        },
    ]
    played_action_ids = ["step-1", "step-2"]
    previous_board_action_ids = ["step-1", "step-2"]
    teaching_board_state = {"elements": visible_board_elements}
    current_focus_element_id = None
    curriculum_chunk_ids = []


def _decision(move: VisualTutorMove) -> AdaptiveTutorDecision:
    return AdaptiveTutorDecision(
        tutor_move=move,
        screen_state=VisualTutorScreenState.SPEAKING_WRITING,
        tutor_status="Writing...",
        stage_state=VisualTutorStageState.WAITING_FOR_STUDENT,
        lesson_state=VisualTutorLessonState.ASK,
        board_action_budget=2,
        interaction_type=VisualTutorInteractionType.TEXT_RESPONSE,
        quick_actions=(VisualTutorAllowedAction.REQUEST_HINT,),
        answer_lock_decision=VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER,
        explanation_mode=VisualTutorExplanationMode.ENGLISH,
    )


def _request(*, move_history: bool = True, step: int = 1) -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id="student-1",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text="3x - 9 = 12",
            current_step_index=step,
        ),
        metadata={
            "played_action_ids": ["step-1", "step-2"] if move_history else [],
            "previous_board_action_ids": ["step-1", "step-2"] if move_history else [],
        },
    )


def _response(*, final_answer_locked: bool = True) -> VisualTutorTurnResponse:
    return VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="What changed on the board?",
        display_text="What changed on the board?",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=final_answer_locked,
        student_task="Try the next step.",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
        board_actions=[
            VisualTutorBoardAction(
                id="new-step",
                type=VisualTutorCanvasActionType.WRITE_EQUATION,
                latex="x = 7",
                sequence_index=2,
            )
        ],
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
    )


def test_first_turn_returns_replace_mode() -> None:
    patched = _build_board_patch(
        response=_response(),
        request=_request(step=0),
        adaptive_decision=_decision(VisualTutorMove.CHECK_STUDENT_ANSWER),
    )

    assert patched.metadata["board_update_mode"] == "replace"
    assert patched.metadata["patch_generated"] is False
    assert patched.metadata["patch_ops"] == []


def test_check_student_answer_generates_highlight_patch() -> None:
    patched = _build_board_patch(
        response=_response(),
        request=_request(),
        adaptive_decision=_decision(VisualTutorMove.CHECK_STUDENT_ANSWER),
    )

    assert patched.metadata["board_update_mode"] == "patch"
    assert patched.metadata["patch_generated"] is True
    assert patched.board_actions[0].metadata["patch_op"] == "highlight"
    assert patched.board_actions[0].target_id == "step-2"
    assert patched.metadata["patch_ops"][0]["op"] == "highlight"


def test_visual_hint_fades_previous_durable_actions() -> None:
    patched = _build_board_patch(
        response=_response(),
        request=_request(),
        adaptive_decision=_decision(VisualTutorMove.SHOW_VISUAL_HINT),
    )

    assert patched.metadata["board_update_mode"] == "patch"
    assert [
        action.metadata.get("patch_op") for action in patched.board_actions[:2]
    ] == [
        "fade",
        "fade",
    ]
    assert [action.target_id for action in patched.board_actions[:2]] == [
        "step-1",
        "step-2",
    ]


def test_missing_history_falls_back_to_replace() -> None:
    patched = _build_board_patch(
        response=_response(),
        request=_request(move_history=False),
        adaptive_decision=_decision(VisualTutorMove.RETEACH_DIFFERENTLY),
    )

    assert patched.metadata["board_update_mode"] == "replace"
    assert patched.metadata["patch_generated"] is False


def test_patch_ids_do_not_poison_previous_board_action_ids() -> None:
    patched = _build_board_patch(
        response=_response(),
        request=_request(),
        adaptive_decision=_decision(VisualTutorMove.CHECK_STUDENT_ANSWER),
    )
    snapshot = _live_stage_snapshot_from_response(
        response=patched,
        previous_session=_Session(),
        reset_board=False,
    )

    assert all(
        not action_id.startswith("patch-")
        for action_id in snapshot["previous_board_action_ids"]
    )
    assert snapshot["previous_board_action_ids"][-1] == "new-step"
    highlighted = next(
        element
        for element in snapshot["teaching_board_state"]["elements"]
        if element["id"] == "step-2"
    )
    assert highlighted["metadata"]["highlighted"] is True
