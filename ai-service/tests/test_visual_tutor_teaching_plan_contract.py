import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


@pytest.fixture
def fixtures():
    path = Path(__file__).parent / "fixtures" / "visual_tutor_teaching_plans.json"
    return json.loads(path.read_text())


def test_teaching_plan_fixtures_are_safe_and_versioned(fixtures):
    assert set(fixtures) == {
        "linear_equation", "quadratic_graph", "wrong_step", "stuck_student",
        "explain_differently", "unsupported_problem",
    }
    for payload in fixtures.values():
        plan = validate_teaching_plan(payload)
        assert plan.schema_version == 1
        assert sum(action.type.value == "student_task" for action in plan.board_actions) == 1


def test_teaching_plan_rejects_ui_code_unknown_actions_and_unapproved_reveal(fixtures):
    invalid = {**fixtures["linear_equation"], "teaching_message": "<script>alert(1)</script>"}
    with pytest.raises(ValidationError):
        validate_teaching_plan(invalid)


def test_teaching_plan_rejects_overlapping_explicit_visual_bounds(fixtures):
    invalid = json.loads(json.dumps(fixtures["linear_equation"]))
    invalid["board_actions"].insert(1, {
        "id": "overlap", "type": "write_text", "sequence_index": 1,
        "x": 100, "y": 70, "width": 280, "height": 80, "text": "Overlapping note"
    })
    with pytest.raises(ValidationError, match="overlaps"):
        validate_teaching_plan(invalid)

    invalid = {**fixtures["linear_equation"], "board_actions": [
        {"id": "unsafe", "type": "arbitrary_widget", "sequence_index": 0, "text": "No"},
        *fixtures["linear_equation"]["board_actions"],
    ]}
    with pytest.raises(ValidationError):
        validate_teaching_plan(invalid)

    invalid = json.loads(json.dumps(fixtures["linear_equation"]))
    invalid["board_actions"][0]["type"] = "final_answer_reveal"
    invalid["hidden_answer_policy"] = {"mode": "hidden", "deterministic_policy_permits_final_reveal": False}
    with pytest.raises(ValidationError):
        validate_teaching_plan(invalid)
