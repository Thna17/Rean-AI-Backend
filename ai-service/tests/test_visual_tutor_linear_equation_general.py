from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorInputRelevance,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.input_understanding import (
    understand_visual_tutor_student_input,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)
from api.services.visual_tutor.solvers import parse_linear_equation

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


@pytest.mark.parametrize(
    ("problem", "variable", "first_step", "final_answer"),
    [
        ("2x + 5 = 15", "x", "2x = 10", "x = 5"),
        ("5a - 8 = 2a + 7", "a", "3a = 15", "a = 5"),
        ("-3x + 4 = 10", "x", "-3x = 6", "x = -2"),
        ("x/2 + 3 = 7", "x", "x/2 = 4", "x = 8"),
        ("0.5x + 2 = 6", "x", "x/2 = 4", "x = 8"),
        ("3n - 4 = n + 8", "n", "2n = 12", "n = 6"),
        ("4y - 9 = 7", "y", "4y = 16", "y = 4"),
        ("6b + 3 = 3b + 12", "b", "3b = 9", "b = 3"),
    ],
)
def test_parse_general_linear_equations(
    problem: str,
    variable: str,
    first_step: str,
    final_answer: str,
) -> None:
    equation = parse_linear_equation(problem)

    assert equation is not None
    assert equation.variable == variable
    assert equation.first_step_equation == first_step
    assert equation.final_equation == final_answer


@pytest.mark.parametrize(
    ("problem", "step"),
    [
        ("2x + 5 = 15", "2x = 10"),
        ("5a - 8 = 2a + 7", "3a = 15"),
        ("-3x + 4 = 10", "-3x = 6"),
        ("x/2 + 3 = 7", "x/2 = 4"),
        ("0.5x + 2 = 6", "x/2 = 4"),
        ("3n - 4 = n + 8", "2n = 12"),
    ],
)
def test_correct_first_step_is_relevant_for_general_linear_equations(
    problem: str,
    step: str,
) -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message=problem,
        )
    )
    result = understand_visual_tutor_student_input(
        VisualTutorTurnRequest(
            user_id="student-1",
            message=step,
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(problem_text=problem),
        ),
        understanding,
    )

    assert result.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert result.metadata["validation_result"] == "correct_step"


@pytest.mark.parametrize(
    ("problem", "answer"),
    [
        ("2x + 5 = 15", "x = 5"),
        ("5a - 8 = 2a + 7", "a = 5"),
        ("-3x + 4 = 10", "x = -2"),
        ("x/2 + 3 = 7", "x = 8"),
        ("0.5x + 2 = 6", "x = 8"),
        ("3n - 4 = n + 8", "n = 6"),
    ],
)
def test_correct_final_answer_is_recognized_after_first_step(
    problem: str,
    answer: str,
) -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message=problem,
        )
    )
    result = understand_visual_tutor_student_input(
        VisualTutorTurnRequest(
            user_id="student-1",
            message=answer,
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                current_step_index=1,
            ),
        ),
        understanding,
    )

    assert result.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert result.metadata["validation_result"] == "correct_final_step"


def test_correct_final_answer_returns_verified_final_screen() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="x = 5",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                current_step_index=1,
            ),
        )
    )

    assert response.final_answer_locked is False
    assert response.mastery_signal == "mastered"
    assert response.board.metadata["screen_state"] == "final_verified_answer"
    assert response.board.metadata["board_type"] == "final_verified_answer"
    assert response.board.metadata["verified_by"] == "sympy"
    assert response.board.metadata["final_answer"] == "x = 5"
    assert "2x = 10" in response.board.metadata["worked_solution"]
    assert (
        response.board.metadata["summary"]["key_formula"]
        == "Keep both sides of the equation balanced."
    )
    assert response.metadata["verified_by"] == "sympy"
    assert response.metadata["sympy_verified"] is True
    assert response.metadata["final_answer"] == "x = 5"
    assert response.metadata["next_practice"]["action"] == "next_practice"


def test_random_input_does_not_advance_general_linear_board() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="banana movie sentence",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text="5a - 8 = 2a + 7",
                current_step_index=0,
            ),
        )
    )

    assert response.board.metadata["current_step_index"] == 0
    assert response.metadata["input_relevance"] == "off_topic"
    assert response.metadata["validation_result"] == "off_topic"


def test_stuck_gives_current_step_help_for_general_linear_equation() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="I am stuck",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            current_state=VisualTutorTurnState(
                problem_text="5a - 8 = 2a + 7",
                current_step_index=0,
            ),
        )
    )

    board_action_text = " ".join(
        str(action.text or action.latex or "") for action in response.board_actions
    )

    assert response.final_answer_locked is True
    assert response.board.metadata["current_step_index"] == 0
    assert "a = 5" not in board_action_text
    assert response.board_actions


@pytest.mark.parametrize(
    (
        "problem",
        "natural_step",
        "equation_step",
        "final_answer",
        "expected_divisor",
    ),
    [
        (
            "2x + 5 = 15",
            "subtract 5 from both sides",
            "2x = 10",
            "x = 5",
            "2",
        ),
        (
            "5a - 8 = 2a + 7",
            "move 2a to the left",
            "3a = 15",
            "a = 5",
            "3",
        ),
        (
            "x/2 + 3 = 7",
            "subtract 3 from both sides",
            "x/2 = 4",
            "x = 8",
            "1/2",
        ),
        (
            "0.5x + 2 = 6",
            "subtract 2 from both sides",
            "x/2 = 4",
            "x = 8",
            "1/2",
        ),
        (
            "3n - 4 = n + 8",
            "move n to the left",
            "2n = 12",
            "n = 6",
            "2",
        ),
    ],
)
def test_general_linear_equation_full_flow_advances_dynamically(
    problem: str,
    natural_step: str,
    equation_step: str,
    final_answer: str,
    expected_divisor: str,
) -> None:
    first = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message=problem,
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert first.final_answer_locked is True
    assert first.board.metadata["current_step_index"] == 0
    assert problem in _board_action_text(first)
    assert final_answer not in _board_action_text(first)

    natural = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message=natural_step,
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                current_step_index=0,
            ),
        )
    )

    assert natural.metadata["validation_result"] == "correct_operation"
    assert natural.board.metadata["current_step_index"] == 1
    assert equation_step in _board_action_text(natural)
    assert f"divide both sides by {expected_divisor}" in _board_action_text(natural)
    assert natural.metadata["adaptive_tutor_decision"]["board_should_advance"] is True

    equation_response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message=equation_step,
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                current_step_index=0,
            ),
        )
    )

    assert equation_response.metadata["validation_result"] == "correct_step"
    assert equation_response.board.metadata["current_step_index"] == 1
    assert equation_step in _board_action_text(equation_response)

    final = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message=final_answer,
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text=problem,
                current_step_index=1,
            ),
        )
    )

    assert final.final_answer_locked is False
    assert final.mastery_signal == "mastered"
    assert final.metadata["validation_result"] == "correct_final_step"
    assert final.metadata["sympy_verified"] is True
    assert final.metadata["final_answer"] == final_answer
    assert final_answer in _board_action_text(final)


def test_both_side_linear_equation_accepts_add_constant_operation() -> None:
    result = understand_visual_tutor_student_input(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="add 8 to both sides",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(problem_text="5a - 8 = 2a + 7"),
        ),
        understand_visual_tutor_problem(
            VisualTutorProblemUnderstandingRequest(
                subject="Mathematics",
                topic="Linear Equations",
                message="5a - 8 = 2a + 7",
            )
        ),
    )

    assert result.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert result.metadata["validation_result"] == "correct_operation"
    assert result.metadata["matched_operation"] == "add 8"


@pytest.mark.parametrize(
    ("problem", "message", "matched_operation"),
    [
        ("5a - 8 = 2a + 7", "move 2a to the left", "subtract 2a"),
        ("3n - 4 = n + 8", "move n to the left", "subtract n"),
        ("0.5x + 2 = 6", "subtract 2 from both sides", "subtract 2"),
    ],
)
def test_natural_language_operations_validate_for_linear_equations(
    problem: str,
    message: str,
    matched_operation: str,
) -> None:
    result = understand_visual_tutor_student_input(
        VisualTutorTurnRequest(
            user_id="student-1",
            message=message,
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(problem_text=problem),
        ),
        understand_visual_tutor_problem(
            VisualTutorProblemUnderstandingRequest(
                subject="Mathematics",
                topic="Linear Equations",
                message=problem,
            )
        ),
    )

    assert result.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert result.metadata["validation_result"] == "correct_operation"
    assert result.metadata["matched_operation"] == matched_operation


def test_wrong_final_numeric_answer_is_diagnosed_without_completing() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="4",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                current_step_index=1,
            ),
        )
    )

    assert response.final_answer_locked is True
    assert response.mastery_signal != "mastered"
    assert response.board.metadata["current_step_index"] == 1
    assert response.metadata["validation_result"] == "incorrect_final_answer"
    assert response.metadata["input_relevance"] == "possible_final_answer"


def test_wrong_linear_step_does_not_advance_board() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="a = 4",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text="5a - 8 = 2a + 7",
                current_step_index=1,
            ),
        )
    )

    assert response.final_answer_locked is True
    assert response.board.metadata["current_step_index"] == 1
    assert response.metadata["validation_result"] == "incorrect_relevant_step"
    assert (
        response.metadata["adaptive_tutor_decision"]["wrong_input_does_not_advance_board"]
        is True
    )
    assert "a = 5" not in _board_action_text(response)


def _board_action_text(response) -> str:
    return " ".join(
        str(action.text or action.latex or action.target_id or "")
        for action in response.board_actions
    )
