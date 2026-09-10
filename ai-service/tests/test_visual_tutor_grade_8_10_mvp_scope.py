"""Regression contract for the Grade 8–10 Mathematics Visual Tutor MVP."""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorScreenState,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
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


# This is the deliberately small, supported MVP.  New classifications must not
# silently expand the production promise without a deterministic solver and a
# board/test contract.
DETERMINISTIC_MVP_CASES = [
    (8, "Integer, Fraction & Decimal Arithmetic", "Calculate 1/2 + 1/4", "fraction_decimal_arithmetic", ArithmeticExpressionSolver),
    (8, "Percentages", "What is 20% of 50?", "simple_percentage_word_problem", SimplePercentageWordProblemSolver),
    (8, "Linear Equations", "Solve 2x + 5 = 15", "linear_equation_one_variable", LinearEquationSolver),
    (9, "Linear Equations", "Solve 3x - 6 = 12", "linear_equation_one_variable", LinearEquationSolver),
    (9, "Slope from Two Points", "Find slope between A(0, 1) and B(1, 3)", "slope_from_two_points", SlopeFromTwoPointsSolver),
    (9, "Straight-Line Graphs", "Find the equation of the line through D(0,1) and E(1,3)", "line_through_two_points", LineThroughPointsSolver),
    (10, "Linear Equations", "Solve 4x + 8 = 24", "linear_equation_one_variable", LinearEquationSolver),
    (10, "Basic Quadratic Graphs", "Solve x^2 - 5x + 6 = 0", "quadratic_equation", QuadraticEquationBasicSolver),
]


@pytest.mark.parametrize(
    ("grade", "topic", "message", "problem_type", "solver_type"),
    DETERMINISTIC_MVP_CASES,
)
def test_grade_8_10_mvp_deterministic_topics_have_a_safe_first_turn(
    grade: int,
    topic: str,
    message: str,
    problem_type: str,
    solver_type: type,
) -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic=topic,
            message=message,
            grade_level_hint=str(grade),
        )
    )
    solver = VisualTutorSolverRegistry().get_solver(understanding)
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-grade-scope",
            subject="Mathematics",
            topic=topic,
            message=message,
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade_level_hint": str(grade)},
        )
    )

    assert understanding.problem_type == problem_type
    assert isinstance(solver, solver_type)
    assert turn.final_answer_locked is True
    assert turn.interaction is not None
    assert turn.board_actions
    assert turn.screen_state != VisualTutorScreenState.UNSUPPORTED_PROBLEM


@pytest.mark.parametrize(
    ("grade", "topic", "message"),
    [
        (9, "Straight-Line Graphs", "Graph y = 2x + 1"),
        (10, "Basic Quadratic Graphs", "Graph y = x^2 - 5x + 6"),
    ],
)
def test_grade_9_10_graph_forms_render_a_real_graph_board(
    grade: int, topic: str, message: str
) -> None:
    turn = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-grade-scope",
            subject="Mathematics",
            topic=topic,
            message=message,
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade_level_hint": str(grade)},
        )
    )

    assert turn.final_answer_locked is True
    graph_actions = [action for action in turn.board_actions if action.type.value == "show_graph"]
    assert len(graph_actions) == 1
    assert graph_actions[0].graph is not None
    assert graph_actions[0].graph.x_min < graph_actions[0].graph.x_max
    assert graph_actions[0].graph.y_min < graph_actions[0].graph.y_max


@pytest.mark.parametrize(
    ("topic", "message", "problem_type"),
    [
        ("Integer, Fraction & Decimal Arithmetic", "គណនា 12 + 7 * 3", "integer_arithmetic"),
        ("Percentages", "20% នៃ 50 ស្មើប៉ុន្មាន?", "simple_percentage_word_problem"),
        ("Linear Equations", "ដោះស្រាយ 2x + 5 = 15", "linear_equation_one_variable"),
        ("Slope from Two Points", "រកជម្រាលរវាង A(0, 1) និង B(1, 3)", "slope_from_two_points"),
        ("Straight-Line Graphs", "គូសក្រាប y = 2x + 1", "straight_line_graph"),
        ("Basic Quadratic Graphs", "គូសក្រាប y = x^2 - 5x + 6", "basic_quadratic_graph"),
    ],
)
def test_grade_8_10_mvp_accepts_khmer_math_prompts(
    topic: str, message: str, problem_type: str
) -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics", topic=topic, message=message, locale="km-KH"
        )
    )

    assert understanding.language == "km"
    assert understanding.problem_type == problem_type
    assert VisualTutorSolverRegistry().get_solver(understanding) is not None or problem_type.endswith("_graph")
