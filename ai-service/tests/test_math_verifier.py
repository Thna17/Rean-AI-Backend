from api.routes.math_verifier import MathQuery, verify_math, verify_student_work

def test_verifies_equivalent_and_wrong_student_steps():
    correct = verify_math(MathQuery(expression="2x = 10", previous_step="2x + 5 = 15"))
    wrong = verify_math(MathQuery(expression="2x = 20", previous_step="2x + 5 = 15"))
    assert correct.status == "correct" and correct.verified
    assert wrong.status == "invalid" and wrong.verified

def test_handles_multiple_no_solution_and_unsafe_input():
    assert verify_math(MathQuery(expression="x^2 = 1")).solution == "[-1, 1]"
    assert verify_math(MathQuery(expression="x = x + 1")).solution == "no solution"
    assert verify_math(MathQuery(expression="__import__('os')")).status == "cannot_verify"


def test_verifies_student_steps_and_safe_fallbacks():
    assert verify_student_work(problem="2x + 5 = 15", student_step="2x = 10").status == "correct"
    assert verify_student_work(problem="2x + 5 = 15", student_step="x = 5", expected_step="2x = 10").status == "mathematically_valid_but_inefficient"
    assert verify_student_work(problem="2x + 5 = 15", student_step="2x = 20").status == "invalid"
    assert verify_student_work(problem="2x + 5 = 15", student_step="x/0 = 2").status == "invalid"
    assert verify_student_work(problem="Prove this triangle geometry statement", student_step="x = 1").status == "cannot_verify"
    assert verify_student_work(problem="2x + 5 = 15", student_step="").status == "incomplete"


def test_verification_contract_has_student_message_and_machine_evidence():
    result = verify_student_work(
        problem="2x + 5 = 15",
        student_step="x = 5",
        expected_step="2x = 10",
    )

    assert result.status == "mathematically_valid_but_inefficient"
    assert result.verified is True
    assert result.normalized_expression == "x = 5"
    assert result.student_message
    assert result.evidence["method"] == "solution_set_equivalence"


def test_answer_equivalence_endpoint_requires_the_internal_token():
    import pytest
    from fastapi import HTTPException

    from api.routes.math_verifier import (
        AnswerEquivalenceQuery,
        verify_answer_equivalence_endpoint,
    )

    query = AnswerEquivalenceQuery(submitted_answer="1/2", expected_answer="0.5")
    with pytest.raises(HTTPException) as excinfo:
        verify_answer_equivalence_endpoint(query, x_visual_tutor_internal_token="wrong-token")
    assert excinfo.value.status_code in (403, 503)


def test_answer_equivalence_endpoint_grades_notation_differences(monkeypatch):
    import os

    from api.routes.math_verifier import (
        AnswerEquivalenceQuery,
        verify_answer_equivalence_endpoint,
    )

    token = "a" * 40
    monkeypatch.setitem(os.environ, "VISUAL_TUTOR_INTERNAL_TOKEN", token)

    def grade(submitted: str, expected: str):
        return verify_answer_equivalence_endpoint(
            AnswerEquivalenceQuery(submitted_answer=submitted, expected_answer=expected),
            x_visual_tutor_internal_token=token,
        )

    assert grade("1/2", "0.5").equivalent is True
    assert grade("x=2 or x=3", "x = 3 or x = 2").equivalent is True
    assert grade("0.6", "0.5").equivalent is False
    assert grade("0.6", "0.5").status == "different"
    assert grade("50%", "0.5").status == "cannot_verify"
