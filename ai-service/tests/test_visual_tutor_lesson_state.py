from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardType,
    VisualTutorCanvasActionType,
    VisualTutorMasterySignal,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.lesson_state import bind_authoritative_lesson_state


def _response() -> VisualTutorTurnResponse:
    return VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Do the requested operation.",
        display_text="Do the requested operation.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="Write the next equation.",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION, metadata={"current_step_index": 1}),
        board_actions=[VisualTutorBoardAction(id="task-1", type=VisualTutorCanvasActionType.STUDENT_TASK, text="Write the next equation.", requires_student_response=True)],
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata={"teaching_plan": {"board_actions": [{"id": "task-1", "requires_student_response": True}]}, "expected_step": "2x = 10"},
    )


def test_authoritative_lesson_state_binds_task_and_actions_to_one_step() -> None:
    request = VisualTutorTurnRequest(user_id="student-1", message="2x + 5 = 15", action=VisualTutorAction.SUBMIT_PROBLEM)
    bound = bind_authoritative_lesson_state(_response(), request)
    state = bound.authoritative_lesson_state

    assert state["problem_instance_id"].startswith("problem-")
    assert state["active_step_id"].endswith(":step-1:task-1")
    assert state["expected_student_action_id"] == "task-1"
    assert bound.board_actions[0].metadata["step_id"] == state["active_step_id"]
    assert bound.board_actions[0].metadata["problem_instance_id"] == state["problem_instance_id"]


def test_continuation_keeps_problem_identity_but_uses_new_step_identity() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="2x = 10",
        action=VisualTutorAction.SUBMIT_STEP,
    )
    request.current_state.problem_instance_id = "problem-existing"
    request.current_state.lesson_id = "lesson-problem-existing"
    response = _response().model_copy(update={"board": VisualTutorBoard(type=VisualTutorBoardType.EQUATION, metadata={"current_step_index": 2})})
    bound = bind_authoritative_lesson_state(response, request)

    assert bound.authoritative_lesson_state["problem_instance_id"] == "problem-existing"
    assert bound.authoritative_lesson_state["active_step_id"].endswith(":step-2:task-1")
