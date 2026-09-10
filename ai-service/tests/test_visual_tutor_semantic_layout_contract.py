import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


def _semantic_plan() -> dict:
    fixtures = json.loads(
        (Path(__file__).parent / "fixtures" / "visual_tutor_teaching_plans.json").read_text()
    )
    payload = fixtures["linear_equation"]
    for action in payload["board_actions"]:
        action.pop("x", None)
        action.pop("y", None)
        action.pop("width", None)
        action.pop("height", None)
        action["layout_zone"] = (
            "student_task" if action["type"] == "student_task" else "working"
        )
        action["layout_flow"] = "vertical"
        action["section_id"] = "step-1"
    return payload


def test_semantic_layout_plan_is_strict_and_geometry_free() -> None:
    plan = validate_teaching_plan(_semantic_plan())
    assert all(action.layout_zone is not None for action in plan.board_actions)
    assert all(action.layout_flow is not None for action in plan.board_actions)


@pytest.mark.parametrize(
    ("field", "value"),
    [("layout_zone", "arbitrary_widget"), ("layout_flow", "render_html")],
)
def test_semantic_layout_rejects_unknown_values(field: str, value: str) -> None:
    payload = _semantic_plan()
    payload["board_actions"][0][field] = value
    with pytest.raises(ValidationError):
        validate_teaching_plan(payload)
