from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from api.models.visual_tutor import (
    VisualTutorBoardType,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorProblemUnderstandingResult,
)
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)


def test_problem_understanding_result_serializes_contract() -> None:
    result = VisualTutorProblemUnderstandingResult(
        subject="Mathematics",
        topic="Linear Equations",
        problem_type="linear_equation_one_variable",
        confidence=0.95,
        extracted_problem="2x + 5 = 15",
        extracted_entities={"variable": "x"},
        language="en",
        grade_level_hint="high_school",
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
        needs_clarification=False,
        metadata={"classifier": "test"},
    )

    payload = json.loads(result.model_dump_json())

    assert payload["subject"] == "Mathematics"
    assert payload["problem_type"] == "linear_equation_one_variable"
    assert payload["confidence"] == 0.95
    assert payload["recommended_board_type"] == "equation_steps"
    assert payload["known_solver_available"] is True


def test_problem_understanding_request_requires_message() -> None:
    with pytest.raises(ValidationError):
        VisualTutorProblemUnderstandingRequest(message="")


def test_problem_understanding_result_rejects_invalid_confidence() -> None:
    with pytest.raises(ValidationError):
        VisualTutorProblemUnderstandingResult(
            subject="Mathematics",
            problem_type="linear_equation_one_variable",
            confidence=1.2,
            extracted_problem="2x + 5 = 15",
            language="en",
            recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
        )


def test_problem_understanding_requires_clarification_question_when_needed() -> None:
    with pytest.raises(ValidationError):
        VisualTutorProblemUnderstandingResult(
            subject="Mathematics",
            problem_type="unsupported_open_ended",
            confidence=0.35,
            extracted_problem="What should I learn?",
            language="en",
            recommended_board_type=VisualTutorBoardType.FORMULA_CARD,
            needs_clarification=True,
        )


def test_understands_linear_equation_problem() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="solve 2x + 5 = 15")
    )

    assert result.problem_type == "linear_equation_one_variable"
    assert result.topic == "Linear Equations"
    assert result.extracted_problem == "2x + 5 = 15"
    assert result.extracted_entities["variable"] == "x"
    assert result.extracted_entities["coefficient"] == "2"
    assert result.known_solver_available is True
    assert result.recommended_board_type == VisualTutorBoardType.EQUATION_STEPS
    assert result.needs_clarification is False


def test_understands_linear_equation_with_non_x_variable_on_both_sides() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="5a - 8 = 2a + 7")
    )

    assert result.problem_type == "linear_equation_one_variable"
    assert result.extracted_problem == "5a - 8 = 2a + 7"
    assert result.extracted_entities["variable"] == "a"
    assert result.extracted_entities["coefficient"] == "3"
    assert result.extracted_entities["first_step_rhs"] == "15"
    assert result.known_solver_available is True
    assert result.needs_clarification is False


def test_understands_line_through_two_points_problem() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="Find the equation of the line through D(0,1) and E(1,3)"
        )
    )

    assert result.problem_type == "line_through_two_points"
    assert result.topic == "Coordinate Geometry"
    assert result.extracted_problem == "D(0,1) and E(1,3)"
    assert result.extracted_entities["points"] == [
        {"label": "D", "x": "0", "y": "1"},
        {"label": "E", "x": "1", "y": "3"},
    ]
    assert result.extracted_entities["slope"] == "2"
    assert result.extracted_entities["intercept"] == "1"
    assert result.known_solver_available is True
    assert result.needs_clarification is False


def test_understands_khmer_math_question_language() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="សូមដោះស្រាយ 2x + 5 = 15",
            grade_level_hint="grade_9",
        )
    )

    assert result.problem_type == "linear_equation_one_variable"
    assert result.language == "km"
    assert result.grade_level_hint == "grade_9"
    assert result.known_solver_available is True


def test_unsupported_open_ended_question_needs_clarification() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="Can you explain why math is useful?"
        )
    )

    assert result.problem_type == "unsupported"
    assert result.confidence < 0.5
    assert result.known_solver_available is False
    assert result.recommended_board_type == VisualTutorBoardType.FORMULA_CARD
    assert result.needs_clarification is True
    assert result.clarification_question


@pytest.mark.parametrize(
    ("message", "expected_type", "expected_action", "expected_language"),
    [
        ("solve 2x + 5 = 15", "linear_equation_one_variable", "solve", "en"),
        ("5a - 8 = 2a + 7", "linear_equation_one_variable", "unknown", "en"),
        ("Solve -3x + 4 = 10", "linear_equation_one_variable", "solve", "en"),
        ("x/2 + 3 = 7", "linear_equation_one_variable", "unknown", "en"),
        ("0.5n + 2 = 6", "linear_equation_one_variable", "unknown", "en"),
        ("7b = 21", "linear_equation_one_variable", "unknown", "en"),
        ("y - 4 = 9", "linear_equation_one_variable", "unknown", "en"),
        (
            "  SOLVE:   3 x - 9 = 0 please",
            "linear_equation_one_variable",
            "solve",
            "en",
        ),
        ("x + 7 = 12", "linear_equation_one_variable", "unknown", "en"),
        ("ដោះស្រាយ 4x - 8 = 0", "linear_equation_one_variable", "solve", "km"),
        (
            "Find the equation of the line through D(0,1) and E(1,3)",
            "line_through_two_points",
            "find_equation",
            "en",
        ),
        (
            "Find the line through A(-2, 4) and B(3, -1)",
            "line_through_two_points",
            "find_equation",
            "en",
        ),
        (
            "line equation passes through (2, 5) and (4, 9)",
            "line_through_two_points",
            "find_equation",
            "en",
        ),
        (
            "រកសមីការបន្ទាត់តាមកាត់ A(0,1) និង B(1,3)",
            "line_through_two_points",
            "find_equation",
            "km",
        ),
        (
            "Find slope between A(0, 1) and B(1, 3)",
            "slope_from_two_points",
            "find_slope",
            "en",
        ),
        (
            "What is the slope of points P(2,4), Q(5,10)?",
            "slope_from_two_points",
            "find_slope",
            "en",
        ),
        (
            "what is the gradient from ( -1 , 2 ) to (3, 10)?",
            "slope_from_two_points",
            "find_slope",
            "en",
        ),
        (
            "slope m for D(0,1), E(1,3)",
            "slope_from_two_points",
            "find_slope",
            "en",
        ),
        ("solve x^2 - 5x + 6 = 0", "quadratic_equation", "solve", "en"),
        ("x**2 + 4*x + 4 = 0", "quadratic_equation", "unknown", "en"),
        ("Solve n^2 - 9 = 0", "quadratic_equation", "solve", "en"),
        ("a^2 + 2a + 1 = 0", "quadratic_equation", "unknown", "en"),
        ("ដោះស្រាយ x^2 - 4 = 0", "quadratic_equation", "solve", "km"),
        ("calculate 12 + 7 * 3", "arithmetic_expression", "calculate", "en"),
        ("what is (8 + 4) / 2?", "arithmetic_expression", "calculate", "en"),
        ("evaluate 3^2 + 4^2", "arithmetic_expression", "calculate", "en"),
        ("គណនា 45 - 12 + 3", "arithmetic_expression", "calculate", "km"),
        ("What is 20% of 50?", "simple_percentage_word_problem", "calculate", "en"),
        ("Find 15 percent of 80", "simple_percentage_word_problem", "find", "en"),
        (
            "Find the domain of f(x) = 1/(x - 2)",
            "function_domain",
            "find",
            "en",
        ),
        (
            "Find the range of f(x) = x^2",
            "function_range",
            "find",
            "en",
        ),
        (
            "Describe the transformation of y = (x - 2)^2 + 3",
            "function_transformation",
            "explain",
            "en",
        ),
        ("Graph f(x)=sin(x)", "function_graph", "draw", "en"),
        ("Draw y = 2x + 1", "function_graph", "draw", "en"),
        ("គូរ f(x)=x^2", "function_graph", "draw", "km"),
        (
            "Find the linear regression for points (1,2), (2,4), (3,5)",
            "linear_regression",
            "find_regression",
            "en",
        ),
        ("Draw the best fit line", "best_fit_line", "find_regression", "en"),
        (
            "Find equation of trend line",
            "best_fit_line",
            "find_regression",
            "en",
        ),
        (
            "រកបន្ទាត់តម្រែតម្រង់សម្រាប់ចំណុច (1,2), (2,4), (3,5)",
            "linear_regression",
            "find_regression",
            "km",
        ),
        (
            "Solve the system x + y = 5 and x - y = 1",
            "systems_of_equations",
            "solve",
            "en",
        ),
        ("Solve 2x + 3 < 9", "inequality", "solve", "en"),
        (
            "Write 2x + y = 3 in slope-intercept form",
            "slope_intercept_form",
            "convert_form",
            "en",
        ),
        (
            "Factor x^2 - 5x + 6 = 0",
            "quadratic_factorization",
            "unknown",
            "en",
        ),
        (
            "Use the quadratic formula for x^2 - 5x + 6 = 0",
            "quadratic_formula",
            "unknown",
            "en",
        ),
        (
            "A book costs 5 dollars and a pen costs 2 dollars. What is total?",
            "word_problem_unknown",
            "calculate",
            "en",
        ),
        (
            "សុខមានផ្លែប៉ោម 5 ហើយទិញ 3 បន្ថែម តើសរុបប៉ុន្មាន?",
            "word_problem_unknown",
            "find",
            "km",
        ),
        (
            "Explain the history of Angkor Wat",
            "unsupported",
            "explain",
            "en",
        ),
        ("hello teacher", "unsupported", "unknown", "en"),
    ],
)
def test_deterministic_classifier_student_message_examples(
    message: str,
    expected_type: str,
    expected_action: str,
    expected_language: str,
) -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message=message)
    )

    assert result.problem_type == expected_type
    assert result.language == expected_language
    assert result.extracted_entities["language"] == expected_language
    assert result.extracted_entities["requested_action"] == expected_action
    assert set(result.extracted_entities).issuperset(
        {"equations", "points", "variables", "numbers", "requested_action", "language"}
    )


def test_classifier_extracts_common_entities_for_equation() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="Please solve 2x + 5 = 15")
    )

    assert result.extracted_entities["equations"] == ["2x + 5 = 15"]
    assert result.extracted_entities["variables"] == ["x"]
    assert result.extracted_entities["numbers"] == ["2", "5", "15"]
    assert result.extracted_entities["requested_action"] == "solve"


def test_classifier_extracts_points_for_geometry() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="Find slope between A(-1, 2) and B(3, 10)"
        )
    )

    assert result.problem_type == "slope_from_two_points"
    assert result.extracted_entities["points"] == [
        {"label": "A", "x": "-1", "y": "2"},
        {"label": "B", "x": "3", "y": "10"},
    ]
    assert result.extracted_entities["numbers"] == ["-1", "2", "3", "10"]


def test_classifier_extracts_quadratic_coefficients() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message="solve x^2 - 5x + 6 = 0")
    )

    assert result.problem_type == "quadratic_equation"
    assert result.extracted_entities["variable"] == "x"
    assert result.extracted_entities["degree"] == 2
    assert result.extracted_entities["coefficients"] == ["1", "-5", "6"]


def test_classifier_extracts_linear_regression_facts() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="Find the linear regression for points (1,2), (2,4), (3,5)"
        )
    )

    assert result.problem_type == "linear_regression"
    assert result.topic == "Linear Regression"
    assert result.known_solver_available is True
    assert result.recommended_board_type.value == "graph_hint"
    assert result.extracted_entities["point_count"] == 3
    assert result.extracted_entities["slope"] == "3/2"
    assert result.extracted_entities["intercept"] == "2/3"
    assert result.extracted_entities["equation"] == "y = 3/2x + 2/3"
    assert result.extracted_entities["regression_method"] == "least_squares"
    assert result.extracted_entities["table"] == [
        {"x": "1", "y": "2"},
        {"x": "2", "y": "4"},
        {"x": "3", "y": "5"},
    ]


@pytest.mark.parametrize(
    ("message", "expected_type"),
    [
        ("Draw the best fit line", "best_fit_line"),
        ("Find equation of trend line", "best_fit_line"),
    ],
)
def test_classifier_detects_regression_without_points_for_llm_planner(
    message: str, expected_type: str
) -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(message=message)
    )

    assert result.problem_type == expected_type
    assert result.known_solver_available is False
    assert result.extracted_entities["visualization"] == "scatter_plot"
    assert result.extracted_entities["deterministic_regression_available"] is False


def test_classifier_detects_khmer_regression_prompt() -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            message="រកបន្ទាត់តម្រែតម្រង់សម្រាប់ចំណុច (1,2), (2,4), (3,5)"
        )
    )

    assert result.problem_type == "linear_regression"
    assert result.language == "km"
    assert result.extracted_entities["requested_action"] == "find_regression"
    assert result.extracted_entities["slope"] == "3/2"
