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
