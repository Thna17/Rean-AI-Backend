"""attach_validated_teaching_plan must never crash a turn.

A real DeepSeek session hit this: the LLM's own proposed teaching_plan was
rejected by _plan_matches_server_policy, and the deterministic fallback --
reconciling the response's legacy board_actions -- produced a show_table
action with no real table data, which teaching_plan_contract.py correctly
rejects. That exception used to propagate all the way to a 500; a student
must always get their turn back instead.
"""
from __future__ import annotations

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardType,
    VisualTutorCanvasActionType,
    VisualTutorMasterySignal,
    VisualTutorScreenState,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.teaching_plan_builder import attach_validated_teaching_plan


def _response_with_broken_table_action() -> VisualTutorTurnResponse:
    broken_table_action = VisualTutorBoardAction(
        id="hint-table",
        type=VisualTutorCanvasActionType.SHOW_TABLE,
        sequence_index=1,
        width=360,
        height=160,
        layout_zone="visual",
        layout_flow="diagram",
        # No `table` data -- this is exactly what teaching_plan_contract.py's
        # "table action needs strict table data" check rejects.
    )
    return VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        screen_state=VisualTutorScreenState.SPEAKING_WRITING,
        spoken_text="Compare the left and right approach values.",
        display_text="Compare the left and right approach values.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="What do the left and right values approach?",
        board=VisualTutorBoard(type=VisualTutorBoardType.TABLE),
        board_actions=[broken_table_action],
        mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
        metadata={},
    )


def test_broken_legacy_table_action_falls_back_instead_of_raising() -> None:
    response = _response_with_broken_table_action()
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="",
        action=VisualTutorAction.REQUEST_HINT,
    )

    finalized = attach_validated_teaching_plan(
        response=response,
        request=request,
        policy=None,
        understanding=None,
        adaptive_decision=None,
    )

    plan = finalized.metadata["teaching_plan"]
    assert plan["board_actions"], "fallback plan must still carry visible content"
    assert any(
        action["type"] == "student_task" for action in plan["board_actions"]
    )
    assert finalized.metadata["teaching_plan_source"] == "server_reconciled"
