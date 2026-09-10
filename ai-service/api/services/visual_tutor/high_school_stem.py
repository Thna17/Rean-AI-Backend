"""Explicit, bounded Grade 8–10 Mathematics support for Visual Tutor.

This catalog is deliberately a product boundary, not a classifier fallback.
It tells orchestration, practice, and diagnostics exactly what the MVP can
teach and verify.  Anything outside these forms must remain transparent rather
than being redirected to a familiar linear-equation lesson.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HighSchoolStemTopic:
    key: str
    problem_types: tuple[str, ...]
    grades: tuple[int, ...]
    accepted_forms: tuple[str, ...]
    unsupported_boundary: str
    representations: tuple[str, ...]
    progressive_hints: tuple[str, ...]
    practice_problem_type: str


TOPICS: tuple[HighSchoolStemTopic, ...] = (
    HighSchoolStemTopic(
        key="one_variable_linear_equations",
        problem_types=("linear_equation_one_variable",),
        grades=(10, 11, 12),
        accepted_forms=("ax + b = c", "ax + b = dx + e", "fraction or decimal coefficients with one variable"),
        unsupported_boundary="Systems, inequalities, and equations with more than one variable need a separate lesson.",
        representations=("equation_transformation", "balance_scale", "worked_example", "error_analysis"),
        progressive_hints=("Identify the operation attached to the variable.", "Apply the inverse operation to both sides.", "Check the transformed equation before dividing."),
        practice_problem_type="linear_equation_one_variable",
    ),
    HighSchoolStemTopic(
        key="integer_arithmetic",
        problem_types=("integer_arithmetic", "arithmetic_expression"),
        grades=(10, 11, 12),
        accepted_forms=("integer addition, subtraction, multiplication, division", "parentheses with integer operations"),
        unsupported_boundary="Expressions with variables, exponents beyond basic order of operations, or undefined division need another lesson.",
        representations=("number_line", "conceptual_explanation", "worked_example", "error_analysis"),
        progressive_hints=("Find the operation with highest priority.", "Use sign rules for just that operation.", "Estimate the sign before calculating."),
        practice_problem_type="integer_arithmetic",
    ),
    HighSchoolStemTopic(
        key="fractions_and_decimals",
        problem_types=("fraction_decimal_arithmetic", "arithmetic_expression"),
        grades=(10, 11, 12),
        accepted_forms=("numeric fraction arithmetic", "finite decimal arithmetic", "mixed fraction/decimal expressions without variables"),
        unsupported_boundary="Repeating decimals, irrational numbers, and variable fractions are not deterministically taught in this MVP.",
        representations=("number_line", "table", "worked_example", "error_analysis"),
        progressive_hints=("Keep denominators visible or align decimal places.", "Simplify one operation at a time.", "Convert only when the conversion makes the next step clearer."),
        practice_problem_type="fraction_decimal_arithmetic",
    ),
    HighSchoolStemTopic(
        key="percentages",
        problem_types=("simple_percentage_word_problem",),
        grades=(10, 11, 12),
        accepted_forms=("p% of n", "finite-decimal percent of a numeric base"),
        unsupported_boundary="Percentage increase/decrease, discounts with multiple changes, and incomplete word problems require more information.",
        representations=("table", "number_line", "worked_example", "error_analysis"),
        progressive_hints=("Percent means out of 100.", "Write the percent as a decimal or fraction.", "Multiply the rate by the base."),
        practice_problem_type="simple_percentage_word_problem",
    ),
    HighSchoolStemTopic(
        key="slope_from_two_points",
        problem_types=("slope_from_two_points",),
        grades=(10, 11, 12),
        accepted_forms=("two distinct points with different x-values",),
        unsupported_boundary="Vertical lines have undefined slope; a graph image without readable coordinates needs student clarification.",
        representations=("coordinate_graph", "table", "worked_example", "error_analysis"),
        progressive_hints=("Find vertical change first.", "Find horizontal change in the same point order.", "Divide rise by run."),
        practice_problem_type="slope_from_points",
    ),
    HighSchoolStemTopic(
        key="straight_line_graphs",
        problem_types=("line_through_two_points", "straight_line_graph"),
        grades=(10, 11, 12),
        accepted_forms=("line through two distinct non-vertical points", "y = mx + b with numeric m and b"),
        unsupported_boundary="Vertical lines and nonlinear functions are outside the straight-line graph lesson.",
        representations=("coordinate_graph", "table", "equation_transformation", "worked_example"),
        progressive_hints=("Locate the intercept or a known point.", "Use slope as rise over run.", "Check a second point on the line."),
        practice_problem_type="line_through_two_points",
    ),
    HighSchoolStemTopic(
        key="basic_quadratic_graphs",
        problem_types=("basic_quadratic_graph", "quadratic_equation", "quadratic_equation_basic"),
        grades=(10, 11, 12),
        accepted_forms=("y = ax^2 + bx + c with numeric coefficients", "factorable ax^2 + bx + c = 0"),
        unsupported_boundary="Non-polynomial curves, complex roots, and quadratic transformations beyond numeric coefficients are outside this MVP.",
        representations=("coordinate_graph", "table", "worked_example", "error_analysis"),
        progressive_hints=("Find the vertex or a useful point.", "Use symmetry about the axis.", "Check intercepts only when they are real."),
        practice_problem_type="basic_quadratic_graph",
    ),
    HighSchoolStemTopic(
        key="physics_kinematics",
        problem_types=("physics_kinematics",),
        grades=(10, 11, 12),
        accepted_forms=("v = u + at", "s = ut + 1/2at^2", "v^2 = u^2 + 2as"),
        unsupported_boundary="Complex 2D motion and calculus-based kinematics are unsupported.",
        representations=("equation_transformation", "worked_example"),
        progressive_hints=("Identify the known variables.", "Identify the unknown variable.", "Choose the correct kinematic equation."),
        practice_problem_type="physics_kinematics",
    ),
    HighSchoolStemTopic(
        key="chemistry_balancing_equations",
        problem_types=("chemistry_balancing_equations",),
        grades=(10, 11, 12),
        accepted_forms=("Chemical equation with elements and molecules",),
        unsupported_boundary="Complex redox reactions and advanced stoichiometry are unsupported.",
        representations=("table", "worked_example", "balance_scale"),
        progressive_hints=("Count atoms on the left.", "Count atoms on the right.", "Balance one element at a time."),
        practice_problem_type="chemistry_balancing_equations",
    ),
)


def topic_for_problem_type(problem_type: str) -> HighSchoolStemTopic | None:
    normalized = problem_type.strip().lower()
    return next((topic for topic in TOPICS if normalized in topic.problem_types), None)


def topic_metadata(problem_type: str) -> dict[str, object]:
    topic = topic_for_problem_type(problem_type)
    if topic is None:
        return {"grade_math_mvp_supported": False}
    return {
        "grade_math_mvp_supported": True,
        "grade_math_topic": topic.key,
        "supported_grades": list(topic.grades),
        "accepted_problem_forms": list(topic.accepted_forms),
        "unsupported_boundary": topic.unsupported_boundary,
        "teaching_representations": list(topic.representations),
        "progressive_hints": list(topic.progressive_hints),
        "validated_practice_problem_type": topic.practice_problem_type,
    }


def supported_practice_problem_types() -> frozenset[str]:
    return frozenset(topic.practice_problem_type for topic in TOPICS)
