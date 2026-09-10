"""Safety matrix for the deterministic Visual Tutor math verifier.

These tests deliberately exercise the boundary between a valid algebraic step
and a statement that only *looks* plausible.  The AI teaching layer must use
this contract rather than infer verification from its own explanation.
"""
from __future__ import annotations

import pytest

from api.routes.math_verifier import MathQuery, verify_math, verify_student_work


@pytest.mark.parametrize(
    ("problem", "student_step", "expected_step", "status"),
    [
        ("2x + 5 = 15", "2x = 10", "2x = 10", "correct"),
        # A correct solution that skips the requested intermediate step is
        # useful evidence, but must not be labelled as the requested step.
        (
            "2x + 5 = 15",
            "x = 5",
            "2x = 10",
            "mathematically_valid_but_inefficient",
        ),
        ("2x + 5 = 15", "2x = 20", "2x = 10", "invalid"),
        ("x / 2 = 3 / 4", "x = 3 / 2", "x = 3 / 2", "correct"),
        ("0.5x = 1.25", "x = 2.5", "x = 2.5", "correct"),
        ("x^2 = 1", "x^2 = 1", "x^2 = 1", "correct"),
        # One root is not equivalent to a two-root original equation.
        ("x^2 = 1", "x = 1", "x^2 = 1", "invalid"),
        # A contradictory original can only be preserved by another
        # contradictory equation, never by inventing a single solution.
        ("x = x + 1", "x = x + 1", "x = x + 1", "correct"),
        ("x = x + 1", "x = 1", "x = x + 1", "invalid"),
    ],
)
def test_student_step_statuses_are_exact_and_solution_set_safe(
    problem: str,
    student_step: str,
    expected_step: str,
    status: str,
) -> None:
    result = verify_student_work(
        problem=problem,
        student_step=student_step,
        expected_step=expected_step,
    )

    assert result.status == status
    assert result.verified is True
    assert result.normalized_expression
    assert result.evidence


@pytest.mark.parametrize(
    ("problem", "student_step", "status", "verified", "reason"),
    [
        ("2x + 5 = 15", "", "incomplete", False, "enter_a_math_step"),
        ("2x + 5 = 15", "x / 0 = 2", "invalid", True, "division_by_zero"),
        (
            "2x + 5 = 15",
            "2x =",
            "cannot_verify",
            False,
            "malformed_or_unsupported_notation",
        ),
        (
            "Prove this triangle is congruent",
            "x = 1",
            "cannot_verify",
            False,
            "unsupported_domain",
        ),
        (
            "A train travels 30 km in 2 hours; what is its speed?",
            "x = 15",
            "cannot_verify",
            False,
            None,
        ),
    ],
)
def test_unverifiable_or_unsafe_work_never_claims_verification(
    problem: str,
    student_step: str,
    status: str,
    verified: bool,
    reason: str | None,
) -> None:
    result = verify_student_work(problem=problem, student_step=student_step)

    assert result.status == status
    assert result.verified is verified
    if reason is not None:
        assert result.evidence["reason"] == reason


@pytest.mark.parametrize(
    "expression",
    [
        "1 / 0 = 2",
        "__import__('os')",
        "2x =",
        "sin(x) = 0",
    ],
)
def test_unsafe_or_malformed_direct_queries_are_not_verified(expression: str) -> None:
    result = verify_math(MathQuery(expression=expression))

    assert result.status == "cannot_verify"
    assert result.verified is False
    assert result.evidence["reason"] == "unsupported_or_malformed_input"


def test_multiple_and_no_solution_claims_return_deterministic_evidence() -> None:
    multiple = verify_math(MathQuery(expression="x^2 = 1"))
    none = verify_math(MathQuery(expression="x = x + 1"))

    assert multiple.status == "correct"
    assert multiple.verified is True
    assert multiple.solution is not None
    assert "-1" in multiple.solution and "1" in multiple.solution
    assert multiple.evidence["method"] in {"sympy_solve", "sympy_solveset"}

    assert none.status == "correct"
    assert none.verified is True
    assert none.solution == "no solution"
    assert none.evidence["method"] == "constant_contradiction"
