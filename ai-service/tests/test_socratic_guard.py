from api.services.socratic_guard import (
    build_socratic_context,
    maybe_build_line_equation_response,
)


def test_direct_math_answer_request_is_gated() -> None:
    context = build_socratic_context(
        "Subject: Mathematics. Topic: Linear Equations. Student message: Guided Practice: Solve 2*x + 5 = 15",
    )

    assert context.is_socratic is True
    assert context.final_answer_allowed is False
    assert "Do not reveal the final numerical answer yet" in context.enriched_message


def test_student_step_unlocks_direct_feedback() -> None:
    context = build_socratic_context(
        "Subject: Mathematics. Student message: I tried subtract 5 from both sides: 2*x = 10",
    )

    assert context.is_socratic is True
    assert context.final_answer_allowed is True
    assert "A full worked solution is allowed" in context.enriched_message


def test_english_requests_are_not_socratic_gated() -> None:
    context = build_socratic_context(
        "Subject: English. Topic: Grammar. Student message: Fix my sentence.",
    )

    assert context.is_socratic is False
    assert context.enriched_message == context.original_message


def test_normal_math_explanation_allows_worked_solution() -> None:
    context = build_socratic_context(
        "Subject: Mathematics. Topic: Linear Equations. Student message: Solve 2*x + 5 = 15",
    )

    assert context.is_socratic is True
    assert context.final_answer_allowed is True
    assert "A full worked solution is allowed" in context.enriched_message
    assert "Do not reveal the final numerical answer yet" not in context.enriched_message


def test_line_equation_problem_uses_required_format() -> None:
    context = build_socratic_context(
        "Subject: Mathematics. Topic: Coordinate Geometry. Student message: Find the equation line where d(0,1) and e(1,3)",
    )

    assert context.final_answer_allowed is True
    assert "y = ax + b" in context.enriched_message
    assert "Step 1: Find the slope" in context.enriched_message
    assert "Final answer:" in context.enriched_message


def test_line_equation_problem_has_deterministic_mobile_response() -> None:
    response = maybe_build_line_equation_response(
        "Subject: Mathematics. Topic: Linear Equations. Student message: "
        "Find the equation line where d(0,1) and e(1,3)"
    )

    assert response is not None
    assert response.startswith("y = ax + b")
    assert "Step 1: Find the slope" in response
    assert "a = (1 - 3) / (0 - 1)" in response
    assert "a = 2" in response
    assert "e(1,3) means x = 1, y = 3" in response
    assert "b = 1" in response
    assert response.endswith("y = 2x + 1")
