"""LimitOfFunctionSolver: sympy ground truth for Grade 12 limits-of-functions.

Covers the four cases solver_facts must classify correctly: a limit that
exists (continuous function), a jump discontinuity (limit does not exist),
a removable discontinuity (limit exists, function undefined there), and a
limit at infinity.
"""

from __future__ import annotations

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.problem_understanding import (
    VisualTutorProblemUnderstandingRequest,
    understand_visual_tutor_problem,
)
from api.services.visual_tutor.solver_registry import VisualTutorSolverRegistry
from api.services.visual_tutor.solvers import LimitOfFunctionSolver, parse_limit_of_function


def _submit(message: str) -> dict:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Limits of Functions",
            message=message,
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )
    return response.metadata


def test_solver_registry_resolves_limit_of_function_solver() -> None:
    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="Find the limit of f(x) = x^2 + 1 as x approaches 2"
        )
    )

    solver = VisualTutorSolverRegistry().get_solver(understanding)

    assert isinstance(solver, LimitOfFunctionSolver)
    assert understanding.problem_type == "limit_of_function"


def test_limit_exists_for_a_continuous_function() -> None:
    metadata = _submit("Find the limit of f(x) = x^2 + 1 as x approaches 2")

    facts = metadata["solver_facts"]
    assert facts["known_solution"] == "5"
    assert facts["board_context"]["classification"] == "exists"
    assert facts["board_context"]["left_value"] == "5"
    assert facts["board_context"]["right_value"] == "5"
    assert facts["board_context"]["function_value_at_point"] == "5"


def test_jump_discontinuity_has_no_two_sided_limit() -> None:
    metadata = _submit("Find the limit of |x|/x as x approaches 0")

    facts = metadata["solver_facts"]
    assert facts["known_solution"] == "does not exist"
    assert facts["board_context"]["classification"] == "does_not_exist"
    assert facts["board_context"]["left_value"] == "-1"
    assert facts["board_context"]["right_value"] == "1"


def test_removable_discontinuity_limit_exists_but_function_is_undefined() -> None:
    metadata = _submit("Find the limit of (x^2 - 1)/(x - 1) as x approaches 1")

    facts = metadata["solver_facts"]
    assert facts["known_solution"] == "2"
    assert facts["board_context"]["classification"] == "removable_discontinuity"
    assert facts["board_context"]["left_value"] == "2"
    assert facts["board_context"]["right_value"] == "2"
    assert facts["board_context"]["function_value_at_point"] is None


def test_limit_at_infinity() -> None:
    metadata = _submit("Find the limit of 1/x as x approaches infinity")

    facts = metadata["solver_facts"]
    assert facts["known_solution"] == "0"
    assert facts["board_context"]["target_point"] == "infinity"
    # There is only one direction of approach toward infinity -- left/right
    # are not meaningful and must not be reported as if they were.
    assert facts["board_context"]["left_value"] is None
    assert facts["board_context"]["right_value"] is None


def test_infinite_limit_at_a_vertical_asymptote() -> None:
    metadata = _submit("Find the limit of 1/x^2 as x approaches 0")

    facts = metadata["solver_facts"]
    assert facts["board_context"]["classification"] == "infinite"
    assert facts["known_solution"] == "oo"


def test_one_sided_limit_is_requested_and_reported_correctly() -> None:
    metadata = _submit(
        "Find the limit of |x|/x as x approaches 0 from the right"
    )

    facts = metadata["solver_facts"]
    assert facts["known_solution"] == "1"
    assert facts["metadata"]["requested_direction"] == "right"


def test_parser_rejects_a_message_with_no_limit_clause() -> None:
    assert parse_limit_of_function("Solve 2x + 5 = 15") is None
