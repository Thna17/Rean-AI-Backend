"""Deterministic quality benchmark for the production Visual Tutor loop."""
from __future__ import annotations

import pytest

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest
from api.routes.math_verifier import verify_student_work
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn


@pytest.mark.parametrize(
    ("problem", "student_step", "expected_step", "status", "verified"),
    [
        ("2x + 5 = 15", "2x = 10", "2x = 10", "correct", True),
        ("x/2 + 1 = 3", "x/2 = 2", "x/2 = 2", "correct", True),
        ("0.5x + 1 = 3", "0.5x = 2", "0.5x = 2", "correct", True),
        ("2x + 5 = 15", "x = 5", "2x = 10", "mathematically_valid_but_inefficient", True),
        ("2x + 5 = 15", "2x = 20", "2x = 10", "invalid", True),
        ("2x + 5 = 15", "", "2x = 10", "incomplete", False),
        ("2x + 5 = 15", "x/0 = 2", "2x = 10", "invalid", True),
        ("x^2 = 1", "x = 1", None, "invalid", True),
        ("x = x + 1", "x = x + 1", None, "correct", True),
        ("2x + 5 = 15", "2x =", "2x = 10", "cannot_verify", False),
        ("Prove this triangle is congruent", "x = 1", None, "cannot_verify", False),
    ],
)
def test_verification_benchmark(problem, student_step, expected_step, status, verified) -> None:
    result = verify_student_work(
        problem=problem, student_step=student_step, expected_step=expected_step
    )
    assert result.status == status
    assert result.verified is verified
    assert bool(result.evidence)


@pytest.mark.parametrize(
    ("problem", "must_have_action", "khmer"),
    [
        ("2x + 5 = 15", "write_equation", False),
        ("x^2 - 5x + 6 = 0", "write_equation", False),
        ("Find the slope through (1,2) and (3,6)", "write_equation", False),
        ("ដោះស្រាយ 2x + 5 = 15", "write_equation", True),
    ],
)
def test_teaching_benchmark_has_one_small_hidden_answer_task(problem, must_have_action, khmer) -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="benchmark-student", session_id=f"benchmark-{abs(hash(problem))}",
            message=problem, action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    active = [action for action in response.board_actions if action.requires_student_response]
    assert len(active) == 1
    assert active[0].type.value == "student_task"
    assert must_have_action in [action.type.value for action in response.board_actions]
    assert response.final_answer_locked is True
    assert "Curriculum focus:" not in response.student_task
    if khmer:
        assert any("ក" <= char <= "៿" for char in response.student_task)


def test_unsupported_benchmark_is_transparent_and_does_not_invent_math() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="benchmark-student", session_id="benchmark-unsupported",
            message="Prove this triangle is congruent", action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )
    assert response.metadata["screen_state"] == "unsupported_problem"
    assert response.final_answer_locked is True
    assert response.metadata["known_solver_available"] is False


def test_explain_differently_benchmark_requires_an_alternate_representation() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="benchmark-student", session_id="benchmark-different",
            message="explain differently", action=VisualTutorAction.EXPLAIN_DIFFERENTLY,
            current_state={"problem_text": "2x + 5 = 15", "current_step_index": 0},
        )
    )
    assert response.metadata["policy"]["explain_differently"] is True
    assert response.metadata["teaching_loop"]["one_student_task"] is True
