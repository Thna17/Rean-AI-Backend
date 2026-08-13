"""Versioned, renderer-safe board action contract for Visual Tutor."""
from __future__ import annotations

from typing import Any

from api.models.visual_tutor import (
    VisualTutorBoardAction,
    VisualTutorCanvasAction,
    VisualTutorTurnResponse,
)


BOARD_SCHEMA_VERSION = 1
MAX_ACTIONS_PER_TURN = 24


def validate_board_response(response: VisualTutorTurnResponse) -> VisualTutorTurnResponse:
    """Drop invalid actions and annotate the response; never emit executable UI."""
    accepted: list[VisualTutorBoardAction] = []
    rejected_ids: list[str] = []
    seen_ids: set[str] = set()
    student_task_actions = 0

    for action in response.board_actions[:MAX_ACTIONS_PER_TURN]:
        action_id = action.id.strip()
        if not action_id or action_id in seen_ids:
            rejected_ids.append(action.id)
            continue
        try:
            # Re-validation makes the generated payload pass the Pydantic schema
            # immediately before it leaves the AI service.
            validated = VisualTutorBoardAction.model_validate(action.model_dump())
        except Exception:
            rejected_ids.append(action.id)
            continue
        if validated.requires_student_response:
            student_task_actions += 1
            if student_task_actions > 1:
                rejected_ids.append(action.id)
                continue
        seen_ids.add(action_id)
        accepted.append(validated)

    canvas_actions: list[VisualTutorCanvasAction] = []
    for action in response.canvas_actions[:MAX_ACTIONS_PER_TURN]:
        try:
            validated = VisualTutorCanvasAction.model_validate(action.model_dump())
            if not validated.id.strip():
                raise ValueError("empty action id")
            canvas_actions.append(validated)
        except Exception:
            rejected_ids.append(getattr(action, "id", "unknown"))

    metadata: dict[str, Any] = {
        **response.metadata,
        "board_schema_version": BOARD_SCHEMA_VERSION,
        "board_action_count": len(accepted),
    }
    if rejected_ids:
        metadata["rejected_board_action_ids"] = rejected_ids
    return response.model_copy(
        update={"board_actions": accepted, "canvas_actions": canvas_actions, "metadata": metadata}
    )
