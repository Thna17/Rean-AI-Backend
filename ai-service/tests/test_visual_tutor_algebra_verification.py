"""Tests for SymPy-verified algebra worked solutions (linear, quadratic, simultaneous systems)."""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.public_response import project_public_tutor_turn


def test_algebra_verification_linear_equation():
    """Verify linear equation 3x + 7 = 22 returns verified: True and status: correct/verified."""
    req = VisualTutorTurnRequest(
        user_id="student-algebra-1",
        subject="Mathematics",
        grade=11,
        message="3x + 7 = 22",
        action=VisualTutorAction.START,
    )
    res = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(res)
    verification = public_turn.get("verification", {})

    assert verification.get("verified") is True, f"Expected verified True, got {verification}"
    # "verified" is not in the public contract; the gateway 502s on it.
    assert verification.get("status") == "correct"
    assert res.metadata.get("verified") is True


def test_algebra_verification_quadratic_equation():
    """Verify quadratic equation x^2 - 5x + 6 = 0 returns verified: True and status: correct/verified."""
    req = VisualTutorTurnRequest(
        user_id="student-algebra-2",
        subject="Mathematics",
        grade=11,
        message="x^2 - 5x + 6 = 0",
        action=VisualTutorAction.START,
    )
    res = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(res)
    verification = public_turn.get("verification", {})

    assert verification.get("verified") is True, f"Expected verified True, got {verification}"
    # "verified" is not in the public contract; the gateway 502s on it.
    assert verification.get("status") == "correct"
    assert res.metadata.get("verified") is True


def test_algebra_verification_simultaneous_equations():
    """Verify simultaneous equations 2x + 3y = 12, x - y = 1 returns verified: True and status: correct/verified."""
    req = VisualTutorTurnRequest(
        user_id="student-algebra-3",
        subject="Mathematics",
        grade=11,
        message="2x + 3y = 12, x - y = 1",
        action=VisualTutorAction.START,
    )
    res = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(res)
    verification = public_turn.get("verification", {})

    assert verification.get("verified") is True, f"Expected verified True, got {verification}"
    # "verified" is not in the public contract; the gateway 502s on it.
    assert verification.get("status") == "correct"
    assert res.metadata.get("verified") is True


def test_unsupported_algebra_remains_cannot_verify():
    """Verify that unsolvable or non-algebra problems remain cannot_verify."""
    req = VisualTutorTurnRequest(
        user_id="student-algebra-4",
        subject="Mathematics",
        grade=11,
        topic="Logarithms",
        message="Solve log(x) + log(x - 3) = 1",
        action=VisualTutorAction.START,
    )
    res = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(res)
    verification = public_turn.get("verification", {})

    assert verification.get("verified") is False
    assert verification.get("status") == "cannot_verify"
    assert res.metadata.get("verified") is False


def _algebra_attempt(message: str):
    """Run only the deterministic algebra matcher for `message`."""
    from api.models.visual_tutor import VisualTutorTurnState
    from api.services.visual_tutor.algebra_worked_solution import (
        try_solve_algebra_problem,
    )

    request = VisualTutorTurnRequest(
        user_id="student-algebra-guard",
        subject="Mathematics",
        grade=11,
        message=message,
        action=VisualTutorAction.START,
        current_state=VisualTutorTurnState(problem_text=message),
    )
    return try_solve_algebra_problem(request, is_khmer=False)


@pytest.mark.parametrize(
    "message",
    [
        # Word problems state their givens as assignments. The algebra solver must
        # not treat those givens as the equations to solve: doing so answers with
        # the question's own data instead of the unknown that was asked for.
        "In triangle ABC, a = 5, b = 7, and angle C = 60 degrees. Find side c.",
        "A rectangle has width w = 4 and height h = 9. Find its area.",
        "Given p = 3 and q = 8, find the value of p*q + 1.",
    ],
)
def test_algebra_solver_declines_problems_whose_equations_are_only_givens(message: str):
    assert _algebra_attempt(message) is None


@pytest.mark.parametrize(
    "message",
    [
        "Solve 3x + 7 = 22",
        "Solve x^2 - 5x + 6 = 0",
        "Solve 2x + 3y = 12 and x - y = 1",
    ],
)
def test_algebra_solver_still_handles_real_algebra(message: str):
    solution = _algebra_attempt(message)
    assert solution is not None, f"expected a deterministic solution for {message!r}"
    assert solution.is_verified is True
