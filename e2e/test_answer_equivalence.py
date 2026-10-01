"""Answer grading must judge what a student meant, not how they typed it.

Being marked wrong for correct work is the fastest way to lose a student, so these
go straight at the verifier the gateway grades with.
"""

from __future__ import annotations

import pytest

EQUIVALENT = [
    ("a fraction against a decimal", "1/2", "0.5"),
    ("a decimal against a fraction", "0.5", "1/2"),
    ("a trailing zero", "0.50", "0.5"),
    ("a bare leading dot", ".5", "0.5"),
    ("an unreduced fraction", "10/2", "5"),
    ("the variable restated", "x = 5", "5"),
    ("the variable dropped", "5", "x = 5"),
    ("a solution set reordered", "x=2 or x=3", "x = 3 or x = 2"),
    ("a comma instead of 'or'", "x = 3, x = 2", "x = 3 or x = 2"),
    ("values without the variable", "2 or 3", "x = 3 or x = 2"),
    ("an expanded product", "2x+2", "2(x+1)"),
    ("a factored expression", "2(x+1)", "2x+2"),
    ("a difference of squares", "x^2-4", "(x-2)(x+2)"),
    ("the radical symbol", "√39", "sqrt(39)"),
]

DIFFERENT = [
    ("a wrong value", "x = 4", "x = 3 or x = 2"),
    ("a near miss", "0.6", "0.5"),
    ("a different fraction", "2/3", "0.5"),
    ("an incomplete solution set", "x = 2", "x = 3 or x = 2"),
    ("an extra root", "x = 2 or x = 3", "x = 2"),
    ("a sign error", "-3", "3"),
]

UNCHECKABLE = [
    ("a percent sign", "50%", "0.5"),
    ("an injection attempt", "__import__('os')", "0.5"),
    ("prose", "I think it is five", "5"),
]


def _verify(ai_service, submitted: str, expected: str) -> dict:
    response = ai_service.post(
        "/api/v1/math/verify/answer",
        {"submitted_answer": submitted, "expected_answer": expected},
        timeout=60.0,
    )
    assert response.status_code == 200, (
        f"the verifier refused the request: {response.status_code} "
        f"{response.text[:200]}"
    )
    return response.json()


@pytest.mark.parametrize(
    ("label", "submitted", "expected"), EQUIVALENT, ids=[c[0] for c in EQUIVALENT]
)
def test_a_notation_variant_is_accepted(ai_service, label, submitted, expected):
    result = _verify(ai_service, submitted, expected)
    assert result["equivalent"] is True, (
        f"{label}: {submitted!r} was judged different from {expected!r}, so a "
        f"student writing it would be marked wrong — {result}"
    )
    assert result["status"] == "equivalent"


@pytest.mark.parametrize(
    ("label", "submitted", "expected"), DIFFERENT, ids=[c[0] for c in DIFFERENT]
)
def test_a_wrong_answer_is_still_rejected(ai_service, label, submitted, expected):
    result = _verify(ai_service, submitted, expected)
    assert result["equivalent"] is False, (
        f"{label}: {submitted!r} was accepted for {expected!r} — {result}"
    )
    assert result["status"] == "different"


@pytest.mark.parametrize(
    ("label", "submitted", "expected"), UNCHECKABLE, ids=[c[0] for c in UNCHECKABLE]
)
def test_what_cannot_be_checked_says_so_rather_than_wrong(
    ai_service, label, submitted, expected
):
    """The gateway treats cannot_verify as 'unproven', never as 'wrong'.

    Collapsing it to `different` would mark a possibly-correct student wrong.
    """
    result = _verify(ai_service, submitted, expected)
    assert result["status"] == "cannot_verify", (
        f"{label}: an uncheckable answer was reported as {result['status']!r}, "
        "which the gateway would read as a wrong answer"
    )
    assert result["equivalent"] is False


def test_the_verifier_is_internal_only(ai_service):
    response = ai_service.post(
        "/api/v1/math/verify/answer",
        {"submitted_answer": "1/2", "expected_answer": "0.5"},
        token="",
        timeout=30.0,
    )
    assert response.status_code in (401, 403, 503), (
        "the answer verifier answered without the internal token, which makes it a "
        "public compute API"
    )


def test_equivalence_is_symmetric(ai_service):
    for left, right in (("1/2", "0.5"), ("2x+2", "2(x+1)"), ("x = 4", "x = 5")):
        forward = _verify(ai_service, left, right)["equivalent"]
        backward = _verify(ai_service, right, left)["equivalent"]
        assert forward == backward, (
            f"{left!r} vs {right!r} judged differently depending on order"
        )
