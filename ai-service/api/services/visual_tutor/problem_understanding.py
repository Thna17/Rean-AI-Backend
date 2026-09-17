from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import sympy

from api.services.visual_tutor.high_school_stem import topic_metadata

from api.models.visual_tutor import (
    VisualTutorBoardType,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorProblemUnderstandingResult,
)
from api.services.visual_tutor.solvers import (
    LimitOfFunctionProblem,
    LineThroughPoints,
    LinearEquation,
    parse_limit_of_function,
    parse_line_through_points,
    parse_linear_equation,
)

CLASSIFIER_VERSION = "visual_tutor_problem_classifier_v2"
_KHMER_RE = re.compile(r"[\u1780-\u17ff]")
_POINT_RE = re.compile(
    r"([A-Za-z])?\s*\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)"
)
_NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
_VARIABLE_RE = re.compile(r"\b[a-zA-Z]\b")
_EQUATION_RE = re.compile(r"[-+*/^().\s\da-zA-Z]+=[-+*/^().\s\da-zA-Z]+")
_ARITHMETIC_RE = re.compile(r"^\s*[-+*/^().\s\d]+(?:=|\?)?\s*$")

_KHMER_ACTIONS = {
    "ដោះស្រាយ": "solve",
    "រក": "find",
    "គណនា": "calculate",
    "គូរ": "draw",
    "សមីការ": "find_equation",
    "ចំណោទ": "solve_word_problem",
    "ពន្យល់": "explain",
}


def understand_visual_tutor_problem(
    request: VisualTutorProblemUnderstandingRequest,
) -> VisualTutorProblemUnderstandingResult:
    message = request.message.strip()
    language = _detect_language(message, request.locale)
    entities = _base_entities(message, language)
    requested_action = entities["requested_action"]
    subject_route = _subject_route(request.subject, message, language)

    if subject_route not in ("mathematics", "physics", "chemistry"):
        return _non_math_subject_result(
            request, message, language, entities, subject_route
        )

    if subject_route == "physics":
        kinematics = _parse_kinematics_problem(message)
        if kinematics:
            return _physics_kinematics_result(request, kinematics, language, entities)
        return _unsupported_result(request, message, language, entities)

    if subject_route == "chemistry":
        chemistry = _parse_chemistry_balancing_problem(message)
        if chemistry:
            return _chemistry_balancing_result(request, chemistry, language, entities)
        return _unsupported_result(request, message, language, entities)

    regression = _parse_regression_problem(message, entities)
    if regression:
        return _regression_result(request, regression, language, entities)

    system = _parse_systems_problem(message, entities)
    if system:
        return _systems_result(request, system, language, entities)

    inequality = _parse_inequality_problem(message, entities)
    if inequality:
        return _inequality_result(request, inequality, language, entities)

    slope_intercept = _parse_slope_intercept_problem(request, message, entities)
    if slope_intercept:
        return _slope_intercept_result(request, slope_intercept, language, entities)

    line_problem = parse_line_through_points(message)
    if line_problem and requested_action != "find_slope":
        return _line_through_points_result(request, line_problem, language, entities)

    points = entities["points"]
    inferred_line_problem = _line_from_points(message, points, requested_action)
    if inferred_line_problem:
        return _line_through_points_result(
            request, inferred_line_problem, language, entities
        )

    if len(points) >= 2 and (
        requested_action == "find_slope" or "slope" in message.lower() or "ជម្រាល" in message
    ):
        return _slope_from_two_points_result(request, message, language, entities)

    linear_equation = parse_linear_equation(message)
    if linear_equation:
        return _linear_equation_result(request, linear_equation, language, entities)

    quadratic = _parse_quadratic_equation(message)
    if quadratic:
        return _quadratic_equation_result(request, quadratic, language, entities)

    limit_of_function = parse_limit_of_function(message)
    if limit_of_function:
        return _limit_of_function_result(request, limit_of_function, language, entities)

    quadratic_graph = _parse_basic_quadratic_graph(message)
    if quadratic_graph:
        return _basic_quadratic_graph_result(request, quadratic_graph, language, entities)

    straight_line_graph = _parse_straight_line_graph(message)
    if straight_line_graph:
        return _straight_line_graph_result(request, straight_line_graph, language, entities)

    percentage = _parse_simple_percentage_word_problem(message)
    if percentage:
        return _simple_percentage_word_problem_result(
            request, percentage, language, entities
        )

    function_problem = _parse_function_problem(request, message)
    if function_problem:
        return _function_problem_result(request, function_problem, language, entities)

    arithmetic = _extract_arithmetic_expression(message)
    if arithmetic:
        return _arithmetic_expression_result(request, arithmetic, language, entities)

    if _looks_like_unknown_word_problem(message, entities):
        return _word_problem_unknown_result(request, message, language, entities)

    return _unsupported_result(request, message, language, entities)


def _parse_kinematics_problem(message: str) -> Optional[str]:
    # Placeholder: detect simple kinematic equations
    if re.search(r"\b(v\s*=\s*u\s*\+\s*at|s\s*=\s*ut|v\^?2\s*=\s*u\^?2)\b", message, re.IGNORECASE):
        return message
    # Or just if it has typical kinematics variables/words and numbers
    if re.search(r"\b(velocity|acceleration|time|distance|speed)\b", message, re.IGNORECASE):
        return message
    return None

def _parse_chemistry_balancing_problem(message: str) -> Optional[str]:
    # Placeholder: look for something that resembles a chemical reaction A + B -> C
    if re.search(r"([A-Z][a-z]?\d*.*?\+.*?->|=>|=)", message):
        return message
    if re.search(r"\b(balance|chemical equation|reaction)\b", message, re.IGNORECASE):
        return message
    return None

def _physics_kinematics_result(
    request: VisualTutorProblemUnderstandingRequest,
    problem: str,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        subject="physics",
        topic="physics_kinematics",
        problem_type="physics_kinematics",
        confidence=0.90,
        extracted_problem=problem,
        extracted_entities={**entities, "normalized_problem": problem},
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )

def _chemistry_balancing_result(
    request: VisualTutorProblemUnderstandingRequest,
    problem: str,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        subject="chemistry",
        topic="chemistry_balancing_equations",
        problem_type="chemistry_balancing_equations",
        confidence=0.90,
        extracted_problem=problem,
        extracted_entities={**entities, "normalized_problem": problem},
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )

def _linear_equation_result(
    request: VisualTutorProblemUnderstandingRequest,
    equation: LinearEquation,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    extracted_entities = {
        **entities,
        "equation": equation.original,
        "normalized_problem": equation.normalized,
        "variable": equation.variable,
        "coefficient": _format_sympy(equation.coefficient),
        "constant": _format_sympy(equation.constant),
        "rhs": _format_sympy(equation.rhs),
        "first_step_rhs": _format_sympy(equation.first_step_rhs),
    }
    return _result(
        request,
        topic=request.topic or "Linear Equations",
        problem_type="linear_equation_one_variable",
        confidence=0.95,
        extracted_problem=equation.original,
        extracted_entities=extracted_entities,
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )


def _line_through_points_result(
    request: VisualTutorProblemUnderstandingRequest,
    problem: LineThroughPoints,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    extracted_entities = {
        **entities,
        "normalized_problem": problem.normalized,
        "points": [
            {
                "label": problem.first_label,
                "x": _format_sympy(problem.x1),
                "y": _format_sympy(problem.y1),
            },
            {
                "label": problem.second_label,
                "x": _format_sympy(problem.x2),
                "y": _format_sympy(problem.y2),
            },
        ],
        "slope": _format_sympy(problem.slope),
        "intercept": _format_sympy(problem.intercept),
    }
    return _result(
        request,
        topic=request.topic or "Coordinate Geometry",
        problem_type="line_through_two_points",
        confidence=0.93,
        extracted_problem=problem.original,
        extracted_entities=extracted_entities,
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )


def _slope_from_two_points_result(
    request: VisualTutorProblemUnderstandingRequest,
    message: str,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Coordinate Geometry",
        problem_type="slope_from_two_points",
        confidence=0.9,
        extracted_problem=_points_problem_text(entities["points"]),
        extracted_entities=entities,
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )


def _quadratic_equation_result(
    request: VisualTutorProblemUnderstandingRequest,
    quadratic: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    problem_type = quadratic.get("problem_type", "quadratic_equation")
    return _result(
        request,
        topic=request.topic or quadratic.get("topic", "Quadratic Equations"),
        problem_type=problem_type,
        confidence=0.88,
        extracted_problem=quadratic["equation"],
        extracted_entities={**entities, **quadratic},
        language=language,
        known_solver_available=problem_type == "quadratic_equation",
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )


def _basic_quadratic_graph_result(
    request: VisualTutorProblemUnderstandingRequest,
    graph: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Basic Quadratic Graphs",
        problem_type="basic_quadratic_graph",
        confidence=0.9,
        extracted_problem=graph["equation"],
        extracted_entities={**entities, **graph},
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.GRAPH_HINT,
    )


def _limit_of_function_result(
    request: VisualTutorProblemUnderstandingRequest,
    problem: LimitOfFunctionProblem,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Limits of Functions",
        problem_type="limit_of_function",
        confidence=0.9,
        extracted_problem=problem.normalized_problem,
        extracted_entities={
            **entities,
            "function_expression": problem.function_expression,
            "target_point_display": problem.target_point_display,
            "requested_direction": problem.requested_direction,
            "variable": problem.variable,
            "normalized_problem": problem.normalized_problem,
        },
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.TABLE,
    )


def _straight_line_graph_result(
    request: VisualTutorProblemUnderstandingRequest,
    graph: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Straight-Line Graphs",
        problem_type="straight_line_graph",
        confidence=0.9,
        extracted_problem=graph["equation"],
        extracted_entities={**entities, **graph},
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.GRAPH_HINT,
    )


def _regression_result(
    request: VisualTutorProblemUnderstandingRequest,
    regression: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Linear Regression",
        problem_type=regression["problem_type"],
        confidence=regression["confidence"],
        extracted_problem=regression["problem"],
        extracted_entities={**entities, **regression},
        language=language,
        known_solver_available=bool(regression.get("deterministic_regression_available")),
        recommended_board_type=VisualTutorBoardType.GRAPH_HINT,
    )


def _systems_result(
    request: VisualTutorProblemUnderstandingRequest,
    system: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Systems of Equations",
        problem_type="systems_of_equations",
        confidence=system["confidence"],
        extracted_problem=system["problem"],
        extracted_entities={**entities, **system},
        language=language,
        known_solver_available=False,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )


def _inequality_result(
    request: VisualTutorProblemUnderstandingRequest,
    inequality: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Inequalities",
        problem_type="inequality",
        confidence=inequality["confidence"],
        extracted_problem=inequality["problem"],
        extracted_entities={**entities, **inequality},
        language=language,
        known_solver_available=False,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )


def _slope_intercept_result(
    request: VisualTutorProblemUnderstandingRequest,
    slope_intercept: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Slope-Intercept Form",
        problem_type="slope_intercept_form",
        confidence=slope_intercept["confidence"],
        extracted_problem=slope_intercept["problem"],
        extracted_entities={**entities, **slope_intercept},
        language=language,
        known_solver_available=False,
        recommended_board_type=VisualTutorBoardType.FORMULA_CARD,
    )


def _arithmetic_expression_result(
    request: VisualTutorProblemUnderstandingRequest,
    expression: str,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Arithmetic",
        problem_type=(
            "fraction_decimal_arithmetic"
            if "/" in expression or "." in expression
            else "integer_arithmetic"
        ),
        confidence=0.82,
        extracted_problem=expression,
        extracted_entities={
            **entities,
            "expression": expression,
            "arithmetic_kind": (
                "fraction_decimal" if "/" in expression or "." in expression else "integer"
            ),
        },
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.FORMULA_CARD,
    )


def _simple_percentage_word_problem_result(
    request: VisualTutorProblemUnderstandingRequest,
    percentage: Dict[str, str],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic or "Percentages",
        problem_type="simple_percentage_word_problem",
        confidence=0.86,
        extracted_problem=percentage["problem"],
        extracted_entities={**entities, **percentage},
        language=language,
        known_solver_available=True,
        recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
    )


def _function_problem_result(
    request: VisualTutorProblemUnderstandingRequest,
    function_problem: Dict[str, Any],
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    problem_type = function_problem["problem_type"]
    topic = {
        "function_domain": "Functions",
        "function_range": "Functions",
        "function_transformation": "Function Transformations",
        "function_graph": "Functions and Graphs",
    }.get(problem_type, "Functions")
    return _result(
        request,
        topic=request.topic or topic,
        problem_type=problem_type,
        confidence=function_problem["confidence"],
        extracted_problem=function_problem["problem"],
        extracted_entities={**entities, **function_problem},
        language=language,
        known_solver_available=False,
        recommended_board_type=(
            VisualTutorBoardType.GRAPH_HINT
            if problem_type == "function_graph"
            else VisualTutorBoardType.FORMULA_CARD
        ),
    )


def _word_problem_unknown_result(
    request: VisualTutorProblemUnderstandingRequest,
    message: str,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic,
        problem_type="word_problem_unknown",
        confidence=0.55,
        extracted_problem=message,
        extracted_entities=entities,
        language=language,
        known_solver_available=False,
        recommended_board_type=VisualTutorBoardType.FORMULA_CARD,
        needs_clarification=True,
        clarification_question=_word_problem_clarification(language),
    )


def _unsupported_result(
    request: VisualTutorProblemUnderstandingRequest,
    message: str,
    language: str,
    entities: Dict[str, Any],
) -> VisualTutorProblemUnderstandingResult:
    return _result(
        request,
        topic=request.topic,
        problem_type="unsupported",
        confidence=0.25,
        extracted_problem=message,
        extracted_entities=entities,
        language=language,
        known_solver_available=False,
        recommended_board_type=VisualTutorBoardType.FORMULA_CARD,
        needs_clarification=True,
        clarification_question=_clarification_question(language),
    )


def _non_math_subject_result(
    request: VisualTutorProblemUnderstandingRequest,
    message: str,
    language: str,
    entities: Dict[str, Any],
    subject_route: str,
) -> VisualTutorProblemUnderstandingResult:
    config = {
        "physics": {
            "subject": "Physics",
            "topic": request.topic or _physics_topic(message),
            "problem_type": "physics_formula_question",
            "board_type": VisualTutorBoardType.FORMULA_CARD,
            "clarification": "Which quantity are we solving for, and what values are given?",
        },
        "chemistry": {
            "subject": "Chemistry",
            "topic": request.topic or _chemistry_topic(message),
            "problem_type": "chemistry_concept_question",
            "board_type": VisualTutorBoardType.WORD_PROBLEM_BREAKDOWN,
            "clarification": "Which part of the concept should we explain first?",
        },
        "english": {
            "subject": "English",
            "topic": request.topic or _english_topic(message),
            "problem_type": "english_grammar_question",
            "board_type": VisualTutorBoardType.WORD_PROBLEM_BREAKDOWN,
            "clarification": "Which sentence or grammar choice should we inspect first?",
        },
        "khmer": {
            "subject": "Khmer",
            "topic": request.topic or "Khmer Language",
            "problem_type": "khmer_language_question",
            "board_type": VisualTutorBoardType.WORD_PROBLEM_BREAKDOWN,
            "clarification": "តើអ្នកចង់ឱ្យពន្យល់ពាក្យ ឃ្លា ឬវេយ្យាករណ៍មួយណាមុន?",
        },
        "biology": {
            "subject": "Biology",
            "topic": request.topic or "Biology Concepts",
            "problem_type": "biology_concept_question",
            "board_type": VisualTutorBoardType.WORD_PROBLEM_BREAKDOWN,
            "clarification": "Biology is not currently in scope for this tutor.",
        },
    }[subject_route]
    return _result(
        request,
        subject=config["subject"],
        topic=config["topic"],
        problem_type=config["problem_type"],
        confidence=0.78,
        extracted_problem=message,
        extracted_entities={
            **entities,
            "subject_route": subject_route,
            "requested_action": (
                entities["requested_action"]
                if entities["requested_action"] != "unknown"
                else "explain"
            ),
        },
        language="km" if subject_route == "khmer" else language,
        known_solver_available=False,
        recommended_board_type=config["board_type"],
        needs_clarification=True,
        clarification_question=config["clarification"],
    )


def _result(
    request: VisualTutorProblemUnderstandingRequest,
    *,
    subject: Optional[str] = None,
    topic: Optional[str],
    problem_type: str,
    confidence: float,
    extracted_problem: str,
    extracted_entities: Dict[str, Any],
    language: str,
    known_solver_available: bool,
    recommended_board_type: VisualTutorBoardType,
    needs_clarification: bool = False,
    clarification_question: Optional[str] = None,
) -> VisualTutorProblemUnderstandingResult:
    mvp_metadata = topic_metadata(problem_type)
    if (
        problem_type in {"arithmetic_expression", "fraction_decimal_arithmetic"}
        and extracted_entities.get("arithmetic_kind") == "fraction_decimal"
    ):
        mvp_metadata = topic_metadata("fraction_decimal_arithmetic")
    return VisualTutorProblemUnderstandingResult(
        subject=subject or request.subject,
        topic=topic,
        problem_type=problem_type,
        confidence=confidence,
        extracted_problem=extracted_problem,
        extracted_entities=extracted_entities,
        language=language,
        grade_level_hint=request.grade_level_hint,
        known_solver_available=known_solver_available,
        recommended_board_type=recommended_board_type,
        needs_clarification=needs_clarification,
        clarification_question=clarification_question,
        metadata={**_metadata(request), **mvp_metadata},
    )


def _base_entities(message: str, language: str) -> Dict[str, Any]:
    equations = _extract_equations(message)
    points = _extract_points(message)
    variables = _extract_variables(message, equations)
    return {
        "equations": equations,
        "points": points,
        "variables": variables,
        "numbers": _NUMBER_RE.findall(message),
        "requested_action": _requested_action(message, language),
        "language": language,
    }


def _subject_route(subject: str, message: str, language: str) -> str:
    normalized = subject.strip().lower()
    if normalized in {"mathematics", "math", "maths"}:
        return "mathematics"
    if normalized in {"physics"}:
        return "physics"
    if normalized in {"chemistry"}:
        return "chemistry"
    if normalized in {"biology"}:
        return "biology"
    if normalized in {"english", "english language"}:
        return "english"
    if normalized in {"khmer", "khmer language"}:
        return "khmer"

    lowered = message.lower()
    if re.search(r"\b(cell|cells|photosynthesis|mitosis|meiosis|dna|rna|genetics|organism|ecosystem|species|biology)\b", lowered):
        return "biology"
    if re.search(r"(ជីវវិទ្យា|កោសិកា|រស្មីសំយោគ|ហ្សែន)", message):
        return "biology"
    if language == "km" and re.search(r"(អក្សរ|ភាសាខ្មែរ|វេយ្យាករណ៍|ពាក្យ)", message):
        return "khmer"
    if re.search(r"\b(grammar|sentence|verb|noun|adjective|tense|essay)\b", lowered):
        return "english"
    if re.search(
        r"\b(force|velocity|acceleration|energy|mass|gravity|formula)\b", lowered
    ):
        return "physics"
    if re.search(r"\b(atom|molecule|reaction|acid|base|bond|periodic)\b", lowered):
        return "chemistry"
    return "mathematics"


def _english_topic(message: str) -> str:
    lowered = message.lower()
    if re.search(r"\b(tense|verb|noun|adjective|sentence|grammar)\b", lowered):
        return "Grammar"
    if "essay" in lowered:
        return "Writing"
    return "English Language"


def _physics_topic(message: str) -> str:
    lowered = message.lower()
    if re.search(r"\b(force|mass|acceleration|f\s*=|ma\b)\b", lowered):
        return "Forces and Motion"
    if re.search(r"\b(energy|work|power)\b", lowered):
        return "Energy"
    return "Physics Concepts"


def _chemistry_topic(message: str) -> str:
    lowered = message.lower()
    if re.search(r"\b(acids?|bases?|ph)\b", lowered):
        return "Acids and Bases"
    if re.search(r"\b(atom|molecule|bond)\b", lowered):
        return "Atoms and Bonding"
    return "Chemistry Concepts"


def _extract_equations(message: str) -> List[str]:
    return [
        cleaned
        for candidate in _EQUATION_RE.findall(message)
        if (cleaned := _clean_equation_candidate(candidate))
    ]


def _extract_points(message: str) -> List[Dict[str, str]]:
    points: List[Dict[str, str]] = []
    for index, match in enumerate(_POINT_RE.findall(message)):
        label, x_raw, y_raw = match
        points.append(
            {
                "label": label or chr(ord("A") + index),
                "x": _normalize_number(x_raw),
                "y": _normalize_number(y_raw),
            }
        )
    return points


def _extract_variables(message: str, equations: List[str]) -> List[str]:
    if equations:
        return sorted(set(re.findall(r"[a-zA-Z]", " ".join(equations))))
    return sorted(set(_VARIABLE_RE.findall(_strip_khmer(message))))


def _requested_action(message: str, language: str) -> str:
    lowered = message.lower()
    for khmer_word, action in _KHMER_ACTIONS.items():
        if khmer_word in message:
            if action == "find" and _has_line_equation_terms(lowered, message):
                return "find_equation"
            return action
    if re.search(
        r"\b(linear\s+regression|regression|best[-\s]?fit|best\s+fit\s+line|"
        r"trend\s+line|line\s+of\s+best\s+fit|scatter\s+plot|scatterplot)\b",
        lowered,
    ) or any(
        cue in message
        for cue in ("តម្រែតម្រង់", "បន្ទាត់ល្អបំផុត", "បន្ទាត់និន្នាការ")
    ):
        return "find_regression"
    if re.search(r"\bslope[-\s]?intercept\b", lowered) or "y = mx + b" in lowered:
        return "convert_form"
    if re.search(r"\b(solve|roots?|zeroes?)\b", lowered):
        return "solve"
    if re.search(r"\b(graph|draw|sketch|plot|visuali[sz]e)\b", lowered):
        return "draw"
    if re.search(r"\b(slope|gradient)\b", lowered):
        return "find_slope"
    if re.search(r"\b(equation of (the )?line|line equation)\b", lowered):
        return "find_equation"
    if re.search(r"\b(find|determine)\b", lowered):
        if _has_line_equation_terms(lowered, message):
            return "find_equation"
        return "find"
    if re.search(r"\b(calculate|compute|evaluate|what is)\b", lowered):
        return "calculate"
    if re.search(r"\b(explain|describe|why|how)\b", lowered) or (
        language == "km" and "ពន្យល់" in message
    ):
        return "explain"
    if language == "km" and ("តើ" in message or "ប៉ុន្មាន" in message):
        return "find"
    return "unknown"


def _has_line_equation_terms(lowered: str, message: str) -> bool:
    return (
        "line" in lowered
        or "through" in lowered
        or "passes" in lowered
        or "បន្ទាត់" in message
        or "សមីការ" in message
    )


def _parse_regression_problem(
    message: str,
    entities: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    lowered = message.lower()
    regression_cues = bool(
        re.search(
            r"\b(linear\s+regression|regression|best[-\s]?fit|best\s+fit\s+line|"
            r"trend\s+line|line\s+of\s+best\s+fit|scatter\s+plot|scatterplot)\b",
            lowered,
        )
        or any(
            cue in message
            for cue in ("តម្រែតម្រង់", "បន្ទាត់ល្អបំផុត", "បន្ទាត់និន្នាការ")
        )
    )
    if not regression_cues:
        return None

    points = entities["points"]
    problem_type = "linear_regression"
    if re.search(r"\b(best[-\s]?fit|best\s+fit|trend\s+line|line\s+of\s+best\s+fit)\b", lowered):
        problem_type = "best_fit_line"
    elif re.search(r"\b(scatter\s+plot|scatterplot|trend)\b", lowered):
        problem_type = "scatter_plot_trend"

    regression: Dict[str, Any] = {
        "problem": message.strip(),
        "problem_type": problem_type,
        "points": points,
        "point_count": len(points),
        "requested_action": "find_regression",
        "visualization": "scatter_plot",
        "confidence": 0.86 if points else 0.68,
        "deterministic_regression_available": False,
    }
    if len(points) >= 2:
        facts = _least_squares_line(points)
        if facts:
            regression.update(facts)
            regression["deterministic_regression_available"] = True
            regression["confidence"] = 0.92
    return regression


def _least_squares_line(points: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    try:
        parsed = [
            (sympy.Rational(point["x"]), sympy.Rational(point["y"]))
            for point in points
        ]
    except Exception:
        return None
    if len(parsed) < 2:
        return None
    n = sympy.Integer(len(parsed))
    sum_x = sympy.simplify(sum(x for x, _ in parsed))
    sum_y = sympy.simplify(sum(y for _, y in parsed))
    sum_xy = sympy.simplify(sum(x * y for x, y in parsed))
    sum_x2 = sympy.simplify(sum(x * x for x, _ in parsed))
    denominator = sympy.simplify(n * sum_x2 - sum_x * sum_x)
    if denominator == 0:
        return None
    slope = sympy.simplify((n * sum_xy - sum_x * sum_y) / denominator)
    intercept = sympy.simplify((sum_y - slope * sum_x) / n)
    predicted = [
        {
            "x": _format_sympy(x),
            "y": _format_sympy(y),
            "y_hat": _format_sympy(sympy.simplify(slope * x + intercept)),
        }
        for x, y in parsed
    ]
    return {
        "slope": _format_sympy(slope),
        "intercept": _format_sympy(intercept),
        "equation": f"y = {_format_slope_intercept(slope, intercept)}",
        "regression_method": "least_squares",
        "table": [
            {"x": _format_sympy(x), "y": _format_sympy(y)} for x, y in parsed
        ],
        "predicted_points": predicted,
    }


def _format_slope_intercept(slope: sympy.Expr, intercept: sympy.Expr) -> str:
    slope_text = _format_linear_x_term(slope)
    intercept = sympy.simplify(intercept)
    if intercept == 0:
        return slope_text
    sign = "+" if intercept > 0 else "-"
    return f"{slope_text} {sign} {_format_sympy(abs(intercept))}"


def _format_linear_x_term(slope: sympy.Expr) -> str:
    slope = sympy.simplify(slope)
    if slope == 1:
        return "x"
    if slope == -1:
        return "-x"
    return f"{_format_sympy(slope)}x"


def _parse_systems_problem(
    message: str,
    entities: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    lowered = message.lower()
    has_system_cue = re.search(
        r"\b(system|simultaneous equations|solve both equations)\b", lowered
    ) or any(cue in message for cue in ("ប្រព័ន្ធសមីការ", "សមីការពីរ"))
    equations = _extract_system_equations(message) or entities["equations"]
    if not has_system_cue and len(equations) < 2:
        return None
    if len(equations) < 2:
        return None
    return {
        "problem": message.strip(),
        "equations": equations,
        "equation_count": len(equations),
        "confidence": 0.84,
    }


def _extract_system_equations(message: str) -> List[str]:
    equations: List[str] = []
    for part in re.split(r"\b(?:and|with)\b|[,;\n]", message, flags=re.IGNORECASE):
        equations.extend(_extract_equations(part))
    return equations


def _parse_inequality_problem(
    message: str,
    entities: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    lowered = message.lower()
    inequality_match = re.search(r"[^<>=](<=|>=|<|>)[^<>=]", f" {message} ")
    if not inequality_match and not re.search(r"\binequalit(?:y|ies)\b", lowered):
        return None
    return {
        "problem": message.strip(),
        "inequality_symbol": inequality_match.group(1) if inequality_match else None,
        "variables": entities["variables"],
        "confidence": 0.82 if inequality_match else 0.68,
    }


def _parse_slope_intercept_problem(
    request: VisualTutorProblemUnderstandingRequest,
    message: str,
    entities: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    lowered = message.lower()
    topic = (request.topic or "").lower()
    if not (
        re.search(r"\bslope[-\s]?intercept\b", lowered)
        or "y = mx + b" in lowered
        or "slope intercept" in topic
    ):
        return None
    return {
        "problem": message.strip(),
        "equations": entities["equations"],
        "formula": "y = mx + b",
        "confidence": 0.82,
    }


def _parse_quadratic_equation(message: str) -> Optional[Dict[str, Any]]:
    lowered = message.lower()
    for equation in _extract_equations(message):
        normalized = _normalize_math_text(equation)
        try:
            lhs_raw, rhs_raw = normalized.split("=", 1)
            lhs = sympy.sympify(lhs_raw.strip())
            rhs = sympy.sympify(rhs_raw.strip())
            variables = sorted(lhs.free_symbols.union(rhs.free_symbols), key=str)
            if len(variables) != 1:
                continue
            variable = variables[0]
            polynomial = sympy.Poly(sympy.expand(lhs - rhs), variable)
        except Exception:
            continue
        if polynomial.degree() != 2:
            continue
        return {
            "equation": equation,
            "normalized_problem": normalized,
            "variable": str(variable),
            "degree": 2,
            "coefficients": [_format_sympy(value) for value in polynomial.all_coeffs()],
            "problem_type": _quadratic_problem_type(lowered),
            "topic": _quadratic_topic(lowered),
        }
    return None


def _parse_basic_quadratic_graph(message: str) -> Optional[Dict[str, Any]]:
    """Accept only numeric y = ax² + bx + c graph forms for the MVP."""
    lowered = message.lower()
    if not (re.search(r"\b(graph|draw|sketch|plot)\b", lowered) or "ក្រាប" in message or "គូរ" in message):
        return None
    equation_match = re.search(r"\by\s*=\s*([^,;?]+)", message, re.IGNORECASE)
    if not equation_match:
        return None
    expression_text = _normalize_math_text(equation_match.group(1))
    try:
        x = sympy.Symbol("x")
        expression = sympy.expand(sympy.sympify(expression_text))
        if expression.free_symbols - {x}:
            return None
        polynomial = sympy.Poly(expression, x)
        if polynomial.degree() != 2:
            return None
        a, b, c = (sympy.simplify(value) for value in polynomial.all_coeffs())
        if a == 0:
            return None
        vertex_x = sympy.simplify(-b / (2 * a))
        vertex_y = sympy.simplify(expression.subs(x, vertex_x))
        roots = [sympy.simplify(value) for value in sympy.solve(expression, x) if value.is_real is not False]
    except Exception:
        return None
    return {
        "equation": f"y = {equation_match.group(1).strip()}",
        "normalized_problem": f"y = {expression}",
        "function_expression": str(expression).replace("**", "^"),
        "a": _format_sympy(a), "b": _format_sympy(b), "c": _format_sympy(c),
        "vertex": {"x": _format_sympy(vertex_x), "y": _format_sympy(vertex_y)},
        "roots": [_format_sympy(root) for root in roots],
    }


def _parse_straight_line_graph(message: str) -> Optional[Dict[str, Any]]:
    """Accept only a numeric slope-intercept line for deterministic graphing."""
    lowered = message.lower()
    if not (re.search(r"\b(graph|draw|sketch|plot)\b", lowered) or "ក្រាប" in message or "គូរ" in message):
        return None
    equation_match = re.search(r"\by\s*=\s*([^,;?]+)", message, re.IGNORECASE)
    if not equation_match:
        return None
    expression_text = _normalize_math_text(equation_match.group(1))
    try:
        x = sympy.Symbol("x")
        expression = sympy.expand(sympy.sympify(expression_text))
        if expression.free_symbols - {x}:
            return None
        polynomial = sympy.Poly(expression, x)
        if polynomial.degree() != 1:
            return None
        slope = sympy.simplify(polynomial.coeff_monomial(x))
        intercept = sympy.simplify(polynomial.coeff_monomial(1))
    except Exception:
        return None
    return {
        "equation": f"y = {equation_match.group(1).strip()}",
        "normalized_problem": f"y = {expression}",
        "function_expression": str(expression).replace("**", "^"),
        "slope": _format_sympy(slope),
        "intercept": _format_sympy(intercept),
    }


def _quadratic_problem_type(lowered: str) -> str:
    if re.search(r"\b(factor|factorise|factorize|factoring|factorization)\b", lowered):
        return "quadratic_factorization"
    if "quadratic formula" in lowered:
        return "quadratic_formula"
    return "quadratic_equation"


def _quadratic_topic(lowered: str) -> str:
    if re.search(r"\b(factor|factorise|factorize|factoring|factorization)\b", lowered):
        return "Quadratic Factorization"
    if "quadratic formula" in lowered:
        return "Quadratic Formula"
    return "Quadratic Equations"



def _parse_function_problem(
    request: VisualTutorProblemUnderstandingRequest,
    message: str,
) -> Optional[Dict[str, Any]]:
    lowered = message.lower()
    topic = (request.topic or "").lower()
    expression = _extract_function_expression(message)
    function_cues = bool(
        expression
        or re.search(r"\bf\s*\(\s*x\s*\)", lowered)
        or re.search(r"\by\s*=", lowered)
        or "function" in lowered
        or "អនុគមន៍" in message
    )
    if not function_cues:
        return None

    if re.search(r"\b(graph|draw|sketch|plot|visuali[sz]e|curve)\b", lowered) or (
        "ក្រាប" in message or "គូរ" in message
    ):
        problem_type = "function_graph"
        confidence = 0.82
    elif re.search(r"\bdomain\b", lowered) or "ដែនកំណត់" in message:
        problem_type = "function_domain"
        confidence = 0.78
    elif re.search(r"\brange\b", lowered) or "តម្លៃ" in message:
        problem_type = "function_range"
        confidence = 0.74
    elif (
        "transform" in lowered
        or "transformation" in lowered
        or "translation" in lowered
        or "shift" in lowered
        or "reflection" in lowered
        or "stretch" in lowered
        or "transform" in topic
        or "បម្លែង" in message
    ):
        problem_type = "function_transformation"
        confidence = 0.76
    else:
        return None

    return {
        "problem_type": problem_type,
        "problem": message,
        "function_expression": expression,
        "confidence": confidence,
    }


def _extract_function_expression(message: str) -> Optional[str]:
    match = re.search(
        r"((?:f\s*\(\s*x\s*\)|y)\s*=\s*[^,.;?]+)",
        message,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip()


def _line_from_points(
    message: str,
    points: List[Dict[str, str]],
    requested_action: str,
) -> Optional[LineThroughPoints]:
    if len(points) < 2 or requested_action != "find_equation":
        return None
    if not _has_line_equation_terms(message.lower(), message):
        return None
    try:
        x1 = sympy.Rational(points[0]["x"])
        y1 = sympy.Rational(points[0]["y"])
        x2 = sympy.Rational(points[1]["x"])
        y2 = sympy.Rational(points[1]["y"])
    except Exception:
        return None
    if x1 == x2:
        return None
    slope = sympy.simplify((y2 - y1) / (x2 - x1))
    intercept = sympy.simplify(y1 - slope * x1)
    return LineThroughPoints(
        original=_points_problem_text(points),
        normalized=(
            "line_through_points:"
            f"({_format_sympy(x1)},{_format_sympy(y1)}),"
            f"({_format_sympy(x2)},{_format_sympy(y2)})"
        ),
        first_label=points[0]["label"],
        second_label=points[1]["label"],
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        slope=slope,
        intercept=intercept,
    )


def _extract_arithmetic_expression(message: str) -> Optional[str]:
    candidate = message.strip().rstrip("?=")
    lowered = candidate.lower()
    for prefix in (
        "calculate",
        "compute",
        "evaluate",
        "what is",
        "find",
        "គណនា",
        "រក",
    ):
        if lowered.startswith(prefix):
            candidate = candidate[len(prefix) :].strip()
            lowered = candidate.lower()
            break
    candidate = candidate.rstrip("?=")
    if not candidate or re.search(r"[a-zA-Z]", candidate):
        return None
    if not _ARITHMETIC_RE.match(candidate):
        return None
    if not re.search(r"[-+*/^]", candidate):
        return None
    return candidate


def _parse_simple_percentage_word_problem(message: str) -> Optional[Dict[str, str]]:
    lowered = message.lower()
    match = re.search(
        r"([-+]?\d+(?:\.\d+)?)\s*%\s*(?:of|from|នៃ)?\s*([-+]?\d+(?:\.\d+)?)",
        lowered,
    )
    if not match:
        match = re.search(
            r"(?:what\s+is|find|calculate|រក|គណនា)?\s*"
            r"([-+]?\d+(?:\.\d+)?)\s*(?:percent|ភាគរយ)\s*(?:of|នៃ)\s*"
            r"([-+]?\d+(?:\.\d+)?)",
            lowered,
        )
    if not match:
        return None
    percent, base = match.groups()
    return {
        "problem": message.strip(),
        "percent": _format_sympy(sympy.Rational(percent)),
        "base": _format_sympy(sympy.Rational(base)),
    }


def _looks_like_unknown_word_problem(message: str, entities: Dict[str, Any]) -> bool:
    lowered = message.lower()
    if entities["equations"] or entities["points"]:
        return False
    if not entities["numbers"]:
        return False
    word_problem_terms = (
        "word problem",
        "age",
        "older",
        "younger",
        "cost",
        "price",
        "total",
        "altogether",
        "perimeter",
        "area",
        "distance",
        "speed",
        "មាន",
        "ទិញ",
        "តម្លៃ",
        "សរុប",
        "អាយុ",
        "ចម្ងាយ",
        "ផ្ទៃ",
    )
    return any(term in lowered or term in message for term in word_problem_terms)


def _detect_language(message: str, locale: Optional[str]) -> str:
    if locale and locale.lower().startswith("km"):
        return "km"
    if _KHMER_RE.search(message):
        return "km"
    return "en"


def _clarification_question(language: str) -> str:
    if language == "km":
        return "តើអ្នកចង់ឱ្យយើងរៀនមេរៀន ឬដោះស្រាយលំហាត់ណាមួយ?"
    return "What exact lesson or problem should we work on first?"


def _word_problem_clarification(language: str) -> str:
    if language == "km":
        return "តើអ្នកអាចបញ្ជាក់ថាត្រូវរកតម្លៃអ្វី និងផ្តល់លក្ខខណ្ឌទាំងអស់បានទេ?"
    return "What value are we solving for, and what relationships are given?"


def _points_problem_text(points: List[Dict[str, str]]) -> str:
    return " and ".join(
        f"{point['label']}({point['x']},{point['y']})" for point in points[:2]
    )


def _normalize_number(value: str) -> str:
    number = sympy.Rational(value)
    return _format_sympy(number)


def _normalize_math_text(text: str) -> str:
    # Gracefully strip out Khmer text or Unicode characters mixed into math
    normalized = _strip_khmer(text).strip()
    
    normalized = normalized.replace("^", "**")
    normalized = normalized.replace("−", "-")
    
    # Handle ambiguous fractions: 1/2x -> (1/2)*x
    normalized = re.sub(r"(\d+)/(\d+)\s*([a-zA-Z])", r"(\1/\2)*\3", normalized)
    
    # Handle implicit multiplication: 2(x+3) -> 2*(x+3)
    normalized = re.sub(r"(\d)\s*\(", r"\1*(", normalized)
    normalized = re.sub(r"\)\s*(\d)", r")*\1", normalized)
    # x(y+1) -> x*(y+1)
    normalized = re.sub(r"([a-zA-Z])\s*\(", r"\1*(", normalized)
    normalized = re.sub(r"\)\s*([a-zA-Z])", r")*\1", normalized)
    
    normalized = re.sub(r"(\d)\s*([a-zA-Z])", r"\1*\2", normalized)
    normalized = re.sub(r"([a-zA-Z])\s*(\d)", r"\1*\2", normalized)
    return normalized


def _clean_equation_candidate(candidate: str) -> Optional[str]:
    cleaned = candidate.strip().rstrip(".,;:?!")
    lhs, separator, rhs = cleaned.partition("=")
    if not separator:
        return None
    lhs = lhs.strip()
    rhs = rhs.strip()
    action_prefix_re = re.compile(
        r"^\s*(?:please\s+)?(?:solve(?:\s+the\s+system)?|the\s+system|find|"
        r"calculate|compute|evaluate|what\s+is|factor|factorise|factorize|"
        r"use\s+the\s+quadratic\s+formula\s+for|write|convert|"
        r"ដោះស្រាយ|រក|គណនា)[:\s]*",
        re.IGNORECASE,
    )
    previous = None
    while previous != lhs:
        previous = lhs
        lhs = action_prefix_re.sub("", lhs).strip()
    if not lhs or not rhs:
        return None
    return f"{lhs} = {rhs}"


def _strip_khmer(message: str) -> str:
    return _KHMER_RE.sub(" ", message)


def _format_sympy(value: sympy.Expr) -> str:
    return str(sympy.simplify(value)).replace("**", "^")


def _metadata(request: VisualTutorProblemUnderstandingRequest) -> Dict[str, Any]:
    return {
        "classifier": CLASSIFIER_VERSION,
        "source_metadata": request.metadata,
    }
