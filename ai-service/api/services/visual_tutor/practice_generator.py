from __future__ import annotations

from typing import Any, Dict, Optional

from api.services.visual_tutor.high_school_stem import TOPICS, topic_for_problem_type


_TOPIC_ALIASES = {
    "linear equations": "one_variable_linear_equations",
    "linear equation": "one_variable_linear_equations",
    "integer arithmetic": "integer_arithmetic",
    "fractions and decimals": "fractions_and_decimals",
    "percentages": "percentages",
    "slope": "slope_from_two_points",
    "slope from points": "slope_from_two_points",
    "slope from two points": "slope_from_two_points",
    "straight line graphs": "straight_line_graphs",
    "basic quadratic graphs": "basic_quadratic_graphs",
}

_PRACTICE_PROBLEMS = {
    "one_variable_linear_equations": {
        "problem_text": "3x + 4 = 19", "problem_type": "linear_equation_one_variable"
    },
    "integer_arithmetic": {
        "problem_text": "-8 + 13 - 4", "problem_type": "integer_arithmetic"
    },
    "fractions_and_decimals": {
        "problem_text": "3/4 - 1/2", "problem_type": "fraction_decimal_arithmetic"
    },
    "percentages": {
        "problem_text": "What is 15% of 80?", "problem_type": "simple_percentage_word_problem"
    },
    "slope_from_two_points": {
        "problem_text": "Find the slope between A(1, 2) and B(3, 6)", "problem_type": "slope_from_two_points"
    },
    "straight_line_graphs": {
        "problem_text": "Graph y = 2x - 1", "problem_type": "straight_line_graph"
    },
    "basic_quadratic_graphs": {
        "problem_text": "Graph y = x^2 - 4x + 3", "problem_type": "basic_quadratic_graph"
    },
}


def generate_practice_problem(
    topic: str,
    metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Generates a new practice problem for the Visual Tutor based on the topic.
    Returns a dict with 'problem_text' and 'problem_type'.
    """
    requested_type = str(metadata.get("problem_type") or "").strip()
    catalog_topic = topic_for_problem_type(requested_type)
    if catalog_topic is not None:
        return _PRACTICE_PROBLEMS[catalog_topic.key].copy()

    topic_normalized = " ".join(topic.lower().strip().replace("-", " ").split())
    catalog_key = _TOPIC_ALIASES.get(topic_normalized)
    if catalog_key is None:
        catalog_key = next(
            (item.key for item in TOPICS if item.key.replace("_", " ") == topic_normalized),
            None,
        )
    if catalog_key is not None:
        return _PRACTICE_PROBLEMS[catalog_key].copy()
    # Never substitute a different topic. The caller can return a transparent
    # unavailable state and keep the learner's progress accurate.
    return None
