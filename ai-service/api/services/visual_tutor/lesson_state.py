"""Server-owned, safe-to-project identity for the active tutor lesson step."""
from __future__ import annotations

import uuid
from typing import Any

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest, VisualTutorTurnResponse


def hydrate_request_lesson_state(request: VisualTutorTurnRequest, session: Any) -> None:
    """Use persisted state for continuation; never let a client rewind it."""
    state = dict(getattr(session, "authoritative_lesson_state", {}) or {})
    if not state:
        return
    if not request.current_state.problem_instance_id:
        request.current_state.problem_instance_id = state.get("problem_instance_id")
    if not request.current_state.lesson_id:
        request.current_state.lesson_id = state.get("lesson_id")
    if not request.current_state.active_step_id:
        request.current_state.active_step_id = state.get("active_step_id")
    if not request.current_state.expected_student_action_id:
        request.current_state.expected_student_action_id = state.get("expected_student_action_id")


def bind_authoritative_lesson_state(
    response: VisualTutorTurnResponse, request: VisualTutorTurnRequest
) -> VisualTutorTurnResponse:
    """Bind every active action to one server-owned problem and lesson step.

    IDs are presentation-safe; expected answers remain in private metadata only.
    """
    is_new_problem = request.action == VisualTutorAction.SUBMIT_PROBLEM and bool(request.message.strip())
    problem_id = request.current_state.problem_instance_id
    if is_new_problem or not problem_id:
        problem_id = f"problem-{uuid.uuid4().hex}"
    lesson_id = request.current_state.lesson_id or f"lesson-{problem_id}"
    step_index = int(response.board.metadata.get("current_step_index", request.current_state.current_step_index) or 0)
    plan = response.metadata.get("teaching_plan") if isinstance(response.metadata, dict) else None
    task_id = None
    if isinstance(plan, dict):
        for action in plan.get("board_actions", []):
            if isinstance(action, dict) and action.get("requires_student_response") is True:
                task_id = str(action.get("id") or "") or None
                break
    task_id = task_id or next((action.id for action in response.board_actions if action.requires_student_response), None)
    active_step_id = f"{lesson_id}:step-{step_index}:{task_id or 'teach'}"
    state = {
        "problem_instance_id": problem_id,
        "lesson_id": lesson_id,
        "active_step_id": active_step_id,
        "current_step_index": step_index,
        "expected_student_action_id": task_id,
        "teaching_stage": response.teaching_stage.stage_state.value if response.teaching_stage else None,
        "lesson_state": response.teaching_stage.lesson_state.value if response.teaching_stage else None,
        "final_answer_locked": response.final_answer_locked,
    }
    actions = []
    for action in response.board_actions:
        actions.append(action.model_copy(update={"metadata": {**action.metadata, "problem_instance_id": problem_id, "step_id": active_step_id, "action_id": action.id}}))
    return response.model_copy(update={
        "board_actions": actions,
        "authoritative_lesson_state": state,
        "metadata": {**response.metadata, "authoritative_lesson_state": state},
    })
