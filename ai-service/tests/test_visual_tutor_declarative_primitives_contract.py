"""Safety and compatibility coverage for the declarative teaching board schema."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


def _plan_with_primitives() -> dict:
    return {
        "schema_version": 1,
        "representation": "coordinate_graph",
        "learning_objective": "Read a coordinate graph and record each transformation.",
        "teaching_message": "Use the labelled visual clues one step at a time.",
        "board_actions": [
            {
                "id": "box", "type": "draw_rectangle", "sequence_index": 0,
                "x": 12, "y": 16, "width": 110, "height": 58,
            },
            {
                "id": "circle", "type": "circle", "sequence_index": 1,
                "x": 136, "y": 16, "width": 54, "height": 54,
            },
            {
                "id": "arrow", "type": "draw_arrow", "sequence_index": 2,
                "x": 12, "y": 88, "width": 160, "height": 32,
                "label": "Move to the next step",
            },
            {
                "id": "axes", "type": "draw_axes", "sequence_index": 3,
                "x": 208, "y": 16, "width": 180, "height": 118,
            },
            {
                "id": "point", "type": "draw_point", "sequence_index": 4,
                "x": 250, "y": 56, "width": 20, "height": 20,
                "label": "A (2, 3)",
            },
            {
                "id": "line", "type": "show_number_line", "sequence_index": 5,
                "x": 12, "y": 144, "width": 376, "height": 62,
                "number_line": {"min": -3, "max": 3, "step": 1, "labels": ["-3", "0", "3"]},
            },
            {
                "id": "table", "type": "show_table", "sequence_index": 6,
                "x": 12, "y": 224, "width": 190, "height": 94,
                "table": {"columns": ["x", "y"], "rows": [[0, 1], [1, 3]]},
            },
            {
                "id": "annotation", "type": "graph_annotation", "sequence_index": 7,
                "x": 214, "y": 230, "width": 174, "height": 36,
                "text": "The point is above the x-axis.",
            },
            {
                "id": "source-equation", "type": "write_equation", "sequence_index": 8,
                "x": 12, "y": 334, "width": 376, "height": 48,
                "latex": "2x - 5 = 10",
            },
            {
                "id": "equation", "type": "transform_equation", "sequence_index": 9,
                "x": 12, "y": 392, "width": 376, "height": 48,
                "latex": "2x - 5 + 5 = 10 + 5",
                "target_id": "source-equation",
            },
            {
                "id": "task", "type": "student_task", "sequence_index": 10,
                "text": "Which operation keeps the equation balanced?",
                "requires_student_response": True,
            },
        ],
        "allowed_student_actions": ["submit_answer", "request_hint"],
        "hidden_answer_policy": {
            "mode": "hidden", "deterministic_policy_permits_final_reveal": False,
        },
        "next_state_policy": {
            "correct": "continue", "invalid": "reteach", "incomplete": "ask_for_work",
            "stuck": "reteach", "hint": "ask_for_work", "explain_differently": "reteach",
        },
    }


def test_accepts_bounded_declarative_visual_primitives_without_ui_code() -> None:
    plan = validate_teaching_plan(_plan_with_primitives())

    assert [action.type.value for action in plan.board_actions[:10]] == [
        "draw_rectangle", "circle", "draw_arrow", "draw_axes", "draw_point",
        "show_number_line", "show_table", "graph_annotation", "write_equation",
        "transform_equation",
    ]
    assert plan.board_actions[2].label == "Move to the next step"
    assert plan.board_actions[5].number_line.min == -3
    assert plan.board_actions[6].table.columns == ["x", "y"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda plan: plan["board_actions"][0].update(width=0),
        lambda plan: plan["board_actions"][2].update(label="<script>alert(1)</script>"),
        lambda plan: plan["board_actions"][5].update(number_line={"min": 3, "max": -3, "step": 1}),
        lambda plan: plan["board_actions"][5].update(number_line={"min": -3, "max": 3, "step": 0}),
        lambda plan: plan["board_actions"][6].update(table={"columns": ["x"], "rows": [["<svg onload=alert(1)>"]]}),
    ],
)
def test_rejects_unbounded_or_unsafe_primitive_data(mutate) -> None:
    payload = deepcopy(_plan_with_primitives())
    mutate(payload)

    with pytest.raises(ValidationError):
        validate_teaching_plan(payload)


def test_rejects_unknown_primitive_fields_instead_of_passing_them_to_flutter() -> None:
    payload = _plan_with_primitives()
    payload["board_actions"][0]["widget"] = "EvilWidget()"

    with pytest.raises(ValidationError):
        validate_teaching_plan(payload)


def test_legacy_board_actions_remain_backward_compatible() -> None:
    payload = _plan_with_primitives()
    payload["board_actions"] = [
        {"id": "legacy-equation", "type": "write_equation", "sequence_index": 0, "latex": "2x + 5 = 15"},
        {"id": "legacy-task", "type": "student_task", "sequence_index": 1, "text": "What operation removes +5?", "requires_student_response": True},
    ]

    assert validate_teaching_plan(payload).board_actions[0].type.value == "write_equation"
