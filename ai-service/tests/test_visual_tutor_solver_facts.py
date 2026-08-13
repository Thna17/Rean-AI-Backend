from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.input_understanding import (
    understand_visual_tutor_student_input,
)
from api.services.visual_tutor.policy import decide_visual_tutor_policy
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)
from api.services.visual_tutor.solver_registry import VisualTutorSolverRegistry


def _solver_facts(
    *,
    problem: str,
    message: str | None = None,
    current_step_index: int = 0,
    action: VisualTutorAction = VisualTutorAction.SUBMIT_PROBLEM,
):
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message=problem,
        )
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        topic="Linear Equations",
        message=message or problem,
        action=action,
        student_submitted_step=action == VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text=problem if message is not None else None,
            normalized_problem=understanding.extracted_problem,
            current_step_index=current_step_index,
        ),
    )
    input_understanding = (
        understand_visual_tutor_student_input(request, understanding)
        if message is not None
        else None
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type=understanding.problem_type,
        known_solver_available=understanding.known_solver_available,
        input_understanding=input_understanding,
    )
    solver = VisualTutorSolverRegistry().get_solver(understanding)
    assert solver is not None
    return solver.solver_facts(request, understanding, policy)


@pytest.mark.parametrize(
    ("problem", "variable", "first_step", "final_answer"),
    [
        ("2x + 5 = 15", "x", "2x = 10", "x = 5"),
        ("5a - 8 = 2a + 7", "a", "3a = 15", "a = 5"),
        ("x/2 + 3 = 7", "x", "x/2 = 4", "x = 8"),
        ("0.5x + 2 = 6", "x", "x/2 = 4", "x = 8"),
        ("3n - 4 = n + 8", "n", "2n = 12", "n = 6"),
        ("6b + 3 = 3b + 12", "b", "3b = 9", "b = 3"),
    ],
)
def test_linear_equation_solver_facts_for_supported_forms(
    problem: str,
    variable: str,
    first_step: str,
    final_answer: str,
) -> None:
    facts = _solver_facts(problem=problem)

    assert facts.solver_name == "LinearEquationSolver"
    assert facts.problem_type == "linear_equation_one_variable"
    assert facts.variable == variable
    assert facts.expected_equation == first_step
    assert facts.known_solution == final_answer
    assert facts.verified_answer == final_answer
    assert facts.sympy_verified is True
    assert facts.student_validation.is_valid is False
    assert facts.safe_formulas
    assert facts.board_context["final_equation"] == final_answer


def test_linear_equation_valid_step_facts() -> None:
    facts = _solver_facts(
        problem="2x + 5 = 15",
        message="2x = 10",
        action=VisualTutorAction.SUBMIT_STEP,
    )

    assert facts.student_validation.is_valid is True
    assert facts.student_validation.is_correct is True
    assert facts.student_validation.is_relevant is True
    assert facts.student_validation.mistake_type is None
    assert facts.student_validation.metadata["validation_result"] == "correct_step"


def test_linear_equation_wrong_step_facts() -> None:
    facts = _solver_facts(
        problem="2x + 5 = 15",
        message="50",
        action=VisualTutorAction.SUBMIT_STEP,
    )

    assert facts.student_validation.is_valid is True
    assert facts.student_validation.is_correct is False
    assert facts.student_validation.is_relevant is False
    assert facts.student_validation.mistake_type is not None
    assert "expected" in facts.student_validation.explanation.lower()


def test_linear_equation_final_answer_facts() -> None:
    facts = _solver_facts(
        problem="2x + 5 = 15",
        message="x = 5",
        current_step_index=1,
        action=VisualTutorAction.SUBMIT_STEP,
    )

    assert facts.student_validation.is_valid is True
    assert facts.student_validation.is_correct is True
    assert facts.student_validation.is_possible_final_answer is True
    assert facts.student_validation.metadata["validation_result"] == (
        "correct_final_step"
    )
    assert facts.verified_answer == "x = 5"


def test_linear_equation_wrong_final_numeric_facts() -> None:
    facts = _solver_facts(
        problem="2x + 5 = 15",
        message="4",
        current_step_index=1,
        action=VisualTutorAction.SUBMIT_STEP,
    )

    assert facts.student_validation.is_valid is True
    assert facts.student_validation.is_correct is False
    assert facts.student_validation.is_relevant is True
    assert facts.student_validation.is_possible_final_answer is True
    assert facts.student_validation.mistake_type == "incorrect_final_answer"
    assert facts.verified_answer == "x = 5"


@pytest.mark.parametrize(
    "problem",
    [
        "Find the equation of the line through D(0,1) and E(1,3)",
        "What is the slope between A(2,4) and B(5,10)?",
        "Solve x^2 - 5x + 6 = 0",
        "2 + 3 * 4",
        "What is 20% of 50?",
    ],
)
def test_all_registered_math_solvers_return_structured_facts(problem: str) -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            message=problem,
        )
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message=problem,
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type=understanding.problem_type,
        known_solver_available=understanding.known_solver_available,
    )
    solver = VisualTutorSolverRegistry().get_solver(understanding)
    assert solver is not None

    facts = solver.solver_facts(request, understanding, policy)

    assert facts.solver_name
    assert facts.problem_type
    assert facts.current_step_index == 0
    assert facts.student_validation is not None
    assert facts.safe_formulas or facts.board_context
