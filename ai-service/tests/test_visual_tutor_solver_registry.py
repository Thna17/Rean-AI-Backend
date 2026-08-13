from __future__ import annotations

from api.models.visual_tutor import VisualTutorProblemUnderstandingRequest
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)
from api.services.visual_tutor.solver_registry import VisualTutorSolverRegistry
from api.services.visual_tutor.solvers import (
    ArithmeticExpressionSolver,
    LineThroughPointsSolver,
    LinearEquationSolver,
    QuadraticEquationBasicSolver,
    SimplePercentageWordProblemSolver,
    SlopeFromTwoPointsSolver,
)


def test_solver_registry_resolves_linear_equation_solver() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="solve 2x + 5 = 15")
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert isinstance(solver, LinearEquationSolver)


def test_solver_registry_resolves_line_through_points_solver() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="Find the equation of the line through D(0,1) and E(1,3)"
        )
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert isinstance(solver, LineThroughPointsSolver)


def test_solver_registry_resolves_slope_from_two_points_solver() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="Find slope between A(0, 1) and B(1, 3)"
        )
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert isinstance(solver, SlopeFromTwoPointsSolver)


def test_solver_registry_resolves_quadratic_basic_solver() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="solve x^2 - 5x + 6 = 0")
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert isinstance(solver, QuadraticEquationBasicSolver)


def test_solver_registry_resolves_arithmetic_solver() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="calculate 12 + 7 * 3")
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert isinstance(solver, ArithmeticExpressionSolver)


def test_solver_registry_resolves_percentage_word_problem_solver() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="What is 20% of 50?")
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert isinstance(solver, SimplePercentageWordProblemSolver)


def test_solver_registry_returns_none_for_unsupported_problem() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="Explain why math is useful")
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert solver is None
