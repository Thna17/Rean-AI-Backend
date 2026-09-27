"""Tests for mathematical equivalence of a student's quiz answer.

Marking a correct answer wrong is the most damaging thing a maths app can do, so
these tests pin both directions: every notation a student legitimately writes is
accepted, and a genuinely wrong answer is still rejected.
"""

from __future__ import annotations

import pytest

from api.services.visual_tutor.answer_equivalence import answers_equivalent


@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        # Same value, different notation.
        ("1/2", "0.5"),
        ("0.50", "0.5"),
        (".5", "0.5"),
        ("0.5", "1/2"),
        # A solution set the student wrote in another order or separator.
        ("x=2 or x=3", "x = 3 or x = 2"),
        ("x = 3, x = 2", "x = 3 or x = 2"),
        ("2 or 3", "x = 3 or x = 2"),
        ("x = 2; x = 3", "x = 3 or x = 2"),
        # The student gave the value without restating the variable.
        ("2", "x = 2"),
        ("x = 2", "2"),
        ("5", "x = 5"),
        # Algebraically identical expressions.
        ("2x+2", "2(x+1)"),
        ("2(x+1)", "2x+2"),
        ("x^2-4", "(x-2)(x+2)"),
        # Radicals, including the symbol a student types.
        ("sqrt(39)", "√39"),
        ("√39", "sqrt(39)"),
        # Whitespace and unicode minus.
        ("  x  =  -3 ", "x=-3"),
        ("x = −3", "x = -3"),
    ],
)
def test_equivalent_answers_are_accepted(submitted: str, expected: str) -> None:
    result = answers_equivalent(submitted, expected)
    assert result.equivalent is True, f"{submitted!r} should match {expected!r}: {result.detail}"
    assert result.status == "equivalent"


@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        ("x = 4", "x = 3 or x = 2"),
        ("0.6", "0.5"),
        ("2/3", "0.5"),
        # A subset of the solution set is incomplete, not correct.
        ("x = 2", "x = 3 or x = 2"),
        # More solutions than the key has.
        ("x = 2 or x = 3", "x = 2"),
        ("2x+3", "2(x+1)"),
        ("-3", "3"),
    ],
)
def test_wrong_answers_are_still_rejected(submitted: str, expected: str) -> None:
    result = answers_equivalent(submitted, expected)
    assert result.equivalent is False, f"{submitted!r} must not match {expected!r}"


@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        ("", "0.5"),
        ("0.5", ""),
        ("import os", "0.5"),
        ("__class__", "0.5"),
        ("50%", "0.5"),
        ("a" * 400, "0.5"),
        ("1/0", "0.5"),
    ],
)
def test_unparseable_input_reports_cannot_verify_rather_than_wrong(
    submitted: str, expected: str
) -> None:
    """The caller must be able to tell 'not equivalent' from 'could not check'."""
    result = answers_equivalent(submitted, expected)
    assert result.equivalent is False
    assert result.status == "cannot_verify", result.detail


def test_equivalence_is_symmetric() -> None:
    for left, right in (("1/2", "0.5"), ("2x+2", "2(x+1)"), ("x = 4", "x = 5")):
        assert (
            answers_equivalent(left, right).equivalent
            == answers_equivalent(right, left).equivalent
        )
