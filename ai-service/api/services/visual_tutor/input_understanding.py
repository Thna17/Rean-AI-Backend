from __future__ import annotations

import re
from typing import Any, Optional

import sympy

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorProblemUnderstandingResult,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.intent import detect_visual_tutor_student_intent
from api.services.visual_tutor.solvers import (
    parse_linear_equation,
    parse_line_through_points,
)

_NUMBER_RE = re.compile(r"[-+]?\d+(?:/\d+)?(?:\.\d+)?")
_EQUATION_RE = re.compile(r"[-+*/^().\s\da-zA-Z]+=[-+*/^().\s\da-zA-Z]+")
_OFF_TOPIC_WORDS_RE = re.compile(
    r"(?i)\b(?:hello|hi|food|movie|game|football|song|weather|joke)\b"
)
_UNCERTAINTY_STUCK_RE = re.compile(
    r"(?i)\b(?:i\s+do\s+not\s+know|i\s+don't\s+know|dont\s+know|don't\s+know|"
    r"not\s+sure|no\s+idea|idk)\b|មិនដឹង"
)
_SHOW_VISUALLY_RE = re.compile(
    r"(?i)\b(?:show\s+(?:me\s+)?(?:it\s+)?visually|show\s+visual|visualize|"
    r"draw\s+(?:it|this)|on\s+the\s+board)\b|បង្ហាញ"
)
_EQUATION_LEADING_DISCOURSE_RE = re.compile(
    r"(?i)^\s*(?:so\s+then|so|then|therefore|thus|hence|next|finally|and)\s+"
)


def understand_visual_tutor_student_input(
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
) -> VisualTutorInputUnderstandingResult:
    message = request.message.strip()
    intent_detection = detect_visual_tutor_student_intent(request)
    intent = intent_detection.intent
    extracted_equations = _extract_equations(message)
    extracted_numbers = _NUMBER_RE.findall(message.replace("−", "-"))
    base_metadata: dict[str, Any] = {
        "detected_intent_reason": intent_detection.reason,
        "client_action": request.action.value,
        "client_student_intent": (
            request.student_intent.value if request.student_intent else None
        ),
        "problem_type": understanding.problem_type,
        "current_step_index": request.current_state.current_step_index,
    }

    if not message:
        return _result(
            intent=VisualTutorStudentIntent.UNKNOWN,
            relevance=VisualTutorInputRelevance.UNKNOWN,
            confidence=0.4,
            explanation="No student message was provided.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata=base_metadata,
        )

    has_active_problem = bool(request.current_state.problem_text)
    if not has_active_problem and _looks_like_math_problem(message):
        return _result(
            intent=VisualTutorStudentIntent.NEW_PROBLEM,
            relevance=VisualTutorInputRelevance.NEW_PROBLEM,
            confidence=0.93,
            explanation="The student provided a new math problem to start.",
            extracted_math=extracted_equations[0] if extracted_equations else message,
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={**base_metadata, "input_role": "new_problem_at_start"},
        )

    if _UNCERTAINTY_STUCK_RE.search(message):
        return _result(
            intent=VisualTutorStudentIntent.STUCK,
            relevance=VisualTutorInputRelevance.STUCK,
            confidence=0.96,
            explanation="The student is expressing uncertainty and needs help.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={**base_metadata, "stuck_reason": "uncertainty_phrase"},
        )

    if intent == VisualTutorStudentIntent.STUCK:
        return _result(
            intent=intent,
            relevance=VisualTutorInputRelevance.STUCK,
            confidence=0.98,
            explanation="The student is asking for help with the current step.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={**base_metadata, "stuck_reason": intent_detection.reason},
        )

    if _SHOW_VISUALLY_RE.search(message):
        return _result(
            intent=VisualTutorStudentIntent.REQUEST_HINT,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            confidence=0.96,
            explanation="The student requested a visual explanation of the active step.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={**base_metadata, "requested_visual_hint": True},
        )

    if intent == VisualTutorStudentIntent.REQUEST_HINT:
        return _result(
            intent=intent,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            confidence=0.95,
            explanation="The student requested a hint for the active problem.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata=base_metadata,
        )

    if intent == VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY:
        return _result(
            intent=intent,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            confidence=0.95,
            explanation="The student asked for a different explanation.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata=base_metadata,
        )

    if intent == VisualTutorStudentIntent.REQUEST_ANSWER:
        return _result(
            intent=intent,
            relevance=VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER,
            confidence=0.92,
            explanation="The student requested the final answer.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata=base_metadata,
        )

    understanding_check_answer = _understanding_check_answer(message)
    if (
        has_active_problem
        and understanding_check_answer
        and (
            request.current_state.current_step_index >= 2
            or request.current_state.final_answer_revealed
        )
    ):
        return _result(
            intent=VisualTutorStudentIntent.CLARIFICATION,
            relevance=VisualTutorInputRelevance.CLARIFICATION,
            confidence=0.94,
            explanation="The student answered the tutor's verification question.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={
                **base_metadata,
                "validation_result": f"understanding_check_{understanding_check_answer}",
                "interaction_response": understanding_check_answer,
                "expected_step": "Check whether the solution satisfies the original equation.",
            },
        )

    if has_active_problem and _looks_like_new_problem(message, understanding):
        return _result(
            intent=VisualTutorStudentIntent.NEW_PROBLEM,
            relevance=VisualTutorInputRelevance.NEW_PROBLEM,
            confidence=0.9,
            explanation="The message looks like a new problem, not a step for the current one.",
            extracted_math=extracted_equations[0] if extracted_equations else None,
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata=base_metadata,
        )

    if intent == VisualTutorStudentIntent.CLARIFICATION or _looks_like_clarification(
        message
    ):
        return _result(
            intent=VisualTutorStudentIntent.CLARIFICATION,
            relevance=VisualTutorInputRelevance.CLARIFICATION,
            confidence=0.82,
            explanation="The student is asking a clarification question.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata=base_metadata,
        )

    solver_result = _understand_with_solver_rules(
        request,
        understanding,
        message,
        extracted_numbers,
        extracted_equations,
        base_metadata,
        fallback_intent=intent,
    )
    if solver_result is not None:
        return solver_result

    if _OFF_TOPIC_WORDS_RE.search(message) or not (
        extracted_numbers or extracted_equations
    ):
        return _result(
            intent=VisualTutorStudentIntent.UNKNOWN,
            relevance=VisualTutorInputRelevance.OFF_TOPIC,
            confidence=0.75,
            explanation="The message does not look like a math step for the current problem.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata=base_metadata,
        )

    return _result(
        intent=(
            VisualTutorStudentIntent.SUBMITTED_STEP
            if has_active_problem
            else VisualTutorStudentIntent.UNKNOWN
        ),
        relevance=VisualTutorInputRelevance.UNKNOWN,
        confidence=0.45,
        explanation="The message has math content, but it does not clearly match the expected step.",
        extracted_numbers=extracted_numbers,
        extracted_equations=extracted_equations,
        metadata=base_metadata,
    )


def _understand_with_solver_rules(
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
    message: str,
    extracted_numbers: list[str],
    extracted_equations: list[str],
    metadata: dict[str, Any],
    *,
    fallback_intent: VisualTutorStudentIntent,
) -> Optional[VisualTutorInputUnderstandingResult]:
    if understanding.problem_type == "linear_equation_one_variable":
        return _understand_linear_equation_input(
            request,
            message,
            extracted_numbers,
            extracted_equations,
            metadata,
            fallback_intent=fallback_intent,
        )

    if understanding.problem_type in {
        "line_through_two_points",
        "slope_from_two_points",
    }:
        return _understand_slope_like_input(
            request,
            understanding,
            message,
            extracted_numbers,
            extracted_equations,
            metadata,
            fallback_intent=fallback_intent,
        )

    if understanding.problem_type == "quadratic_equation":
        if extracted_equations or _mentions_operation(
            message, ["factor", "root", "zero"]
        ):
            return _result(
                intent=VisualTutorStudentIntent.SUBMITTED_STEP,
                relevance=VisualTutorInputRelevance.RELEVANT_STEP,
                confidence=0.76,
                explanation="The input is relevant to solving the quadratic.",
                extracted_math=extracted_equations[0] if extracted_equations else None,
                extracted_numbers=extracted_numbers,
                extracted_equations=extracted_equations,
                metadata={**metadata, "validation_result": "needs_solver_check"},
            )
        if len(extracted_numbers) >= 1 and _message_is_mostly_numbers(message):
            return _result(
                intent=VisualTutorStudentIntent.SUBMITTED_STEP,
                relevance=VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER,
                confidence=0.7,
                explanation="The input looks like a possible root or final answer.",
                extracted_numbers=extracted_numbers,
                extracted_equations=extracted_equations,
                metadata={**metadata, "validation_result": "possible_final_answer"},
            )

    if understanding.problem_type in {
        "arithmetic_expression",
        "simple_percentage_word_problem",
    }:
        if extracted_numbers or extracted_equations:
            return _result(
                intent=VisualTutorStudentIntent.SUBMITTED_STEP,
                relevance=VisualTutorInputRelevance.RELEVANT_STEP,
                confidence=0.68,
                explanation="The input contains numbers that may be part of the current calculation.",
                extracted_math=extracted_equations[0] if extracted_equations else None,
                extracted_numbers=extracted_numbers,
                extracted_equations=extracted_equations,
                metadata={**metadata, "validation_result": "needs_solver_check"},
            )

    return None


def _understand_linear_equation_input(
    request: VisualTutorTurnRequest,
    message: str,
    extracted_numbers: list[str],
    extracted_equations: list[str],
    metadata: dict[str, Any],
    *,
    fallback_intent: VisualTutorStudentIntent,
) -> VisualTutorInputUnderstandingResult:
    equation = parse_linear_equation(request.current_state.problem_text or "")
    if equation is None:
        return _generic_unknown_step(
            extracted_numbers, extracted_equations, metadata, fallback_intent
        )

    expected_step = equation.first_step_equation
    expected_operation = equation.operation_text
    enriched_metadata = {
        **metadata,
        "expected_step": expected_step,
        "expected_operation": expected_operation,
        "variable": equation.variable,
        "final_answer": _format_expr(equation.solution),
    }

    if extracted_equations:
        submitted_equation = extracted_equations[0]
        if request.current_state.current_step_index >= 1 and _equations_equivalent(
            submitted_equation, equation.final_equation
        ):
            return _result(
                intent=VisualTutorStudentIntent.SUBMITTED_STEP,
                relevance=VisualTutorInputRelevance.RELEVANT_STEP,
                confidence=0.95,
                explanation="The equation matches the expected final isolation step.",
                extracted_math=submitted_equation,
                extracted_numbers=extracted_numbers,
                extracted_equations=extracted_equations,
                metadata={
                    **enriched_metadata,
                    "expected_step": equation.final_equation,
                    "validation_result": "correct_final_step",
                },
            )
        if _equations_equivalent(submitted_equation, expected_step):
            return _result(
                intent=VisualTutorStudentIntent.SUBMITTED_STEP,
                relevance=VisualTutorInputRelevance.RELEVANT_STEP,
                confidence=0.95,
                explanation="The equation matches the expected first step.",
                extracted_math=submitted_equation,
                extracted_numbers=extracted_numbers,
                extracted_equations=extracted_equations,
                metadata={**enriched_metadata, "validation_result": "correct_step"},
            )
        if equation.variable.lower() in submitted_equation.lower():
            misconception_type = _linear_first_step_misconception(
                submitted_equation,
                equation=equation,
                current_step_index=request.current_state.current_step_index,
            )
            return _result(
                intent=VisualTutorStudentIntent.SUBMITTED_STEP,
                relevance=VisualTutorInputRelevance.RELEVANT_STEP,
                confidence=0.82,
                explanation="The equation is related to the current problem but not the expected step.",
                extracted_math=submitted_equation,
                extracted_numbers=extracted_numbers,
                extracted_equations=extracted_equations,
                metadata={
                    **enriched_metadata,
                    "validation_result": "incorrect_relevant_step",
                    "misconception_type": misconception_type,
                    "mistake_category": misconception_type,
                },
            )

    operation_mentions = _mentions_operation(
        message,
        [
            "add",
            "adding",
            "move",
            "moving",
            "bring",
            "shift",
            "subtract",
            "subtracting",
            "substract",
            "substracting",
            "substrac",
            "subsctract",
            "subsctracting",
            "minus",
            "take away",
            "remove",
            "ដក",
            "យក",
            "បន្ថែម",
        ],
    )
    if operation_mentions:
        operation_validation = _validate_linear_natural_language_operation(
            message,
            extracted_numbers,
            equation,
        )
        return _result(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            confidence=operation_validation["confidence"],
            explanation=(
                "The student named a valid balancing operation for the current equation."
                if operation_validation["is_correct"]
                else "The operation is relevant, but it does not match the current balancing move."
            ),
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={
                **enriched_metadata,
                "validation_result": (
                    "correct_operation"
                    if operation_validation["is_correct"]
                    else "incorrect_relevant_step"
                ),
                "misconception_type": (
                    None
                    if operation_validation["is_correct"]
                    else "wrong_constant_operation"
                ),
                "matched_operation": operation_validation["matched_operation"],
                "expected_operations": operation_validation["expected_operations"],
            },
        )

    if len(extracted_numbers) == 1 and _message_is_mostly_numbers(message):
        number = _parse_number(extracted_numbers[0])
        validation = "incorrect_final_answer"
        relevance = VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER
        explanation = (
            f"The input looks like an attempted final value for {equation.variable}."
        )
        confidence = 0.82
        if number is not None and sympy.simplify(number - equation.solution) == 0:
            validation = (
                "correct_final_step"
                if request.current_state.current_step_index >= 1
                else "correct_final_answer_too_early"
            )
            explanation = (
                "The input completes the current isolation step."
                if request.current_state.current_step_index >= 1
                else "The input is the final value, but the reasoning steps are still locked."
            )
            relevance = VisualTutorInputRelevance.RELEVANT_STEP
            confidence = 0.92
        elif number is not None and not _number_is_plausible_final(
            number, equation.solution
        ):
            relevance = VisualTutorInputRelevance.UNRELATED
            validation = "unrelated_numeric_input"
            explanation = "The number does not match the expected current step or a plausible final value."
            confidence = 0.84
        return _result(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=relevance,
            confidence=confidence,
            explanation=explanation,
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={**enriched_metadata, "validation_result": validation},
        )

    if extracted_numbers:
        return _result(
            intent=VisualTutorStudentIntent.UNKNOWN,
            relevance=VisualTutorInputRelevance.UNRELATED,
            confidence=0.74,
            explanation="The numbers do not form a current equation step.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={
                **enriched_metadata,
                "validation_result": "unrelated_numeric_input",
            },
        )

    return _result(
        intent=VisualTutorStudentIntent.UNKNOWN,
        relevance=VisualTutorInputRelevance.OFF_TOPIC,
        confidence=0.78,
        explanation="The message is not a math step for this linear equation.",
        extracted_numbers=extracted_numbers,
        extracted_equations=extracted_equations,
        metadata={**enriched_metadata, "validation_result": "off_topic"},
    )


def _understand_slope_like_input(
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
    message: str,
    extracted_numbers: list[str],
    extracted_equations: list[str],
    metadata: dict[str, Any],
    *,
    fallback_intent: VisualTutorStudentIntent,
) -> VisualTutorInputUnderstandingResult:
    current_problem = (
        request.current_state.problem_text or understanding.extracted_problem
    )
    line = parse_line_through_points(current_problem)
    expected_step = "Find the slope m = (y2 - y1) / (x2 - x1)."
    enriched_metadata = {**metadata, "expected_step": expected_step}
    if line is not None:
        enriched_metadata["final_answer"] = _format_expr(line.slope)

    if re.search(r"(?i)\b(?:m|slope|ជម្រាល)\b", message) or extracted_equations:
        return _result(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            confidence=0.84,
            explanation="The input is related to the slope step.",
            extracted_math=extracted_equations[0] if extracted_equations else None,
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={**enriched_metadata, "validation_result": "needs_solver_check"},
        )
    if (
        understanding.problem_type == "line_through_two_points"
        and request.current_state.current_step_index <= 1
        and len(extracted_numbers) == 1
        and _message_is_mostly_numbers(message)
    ):
        return _result(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.RELEVANT_STEP,
            confidence=0.78,
            explanation="The number is a response to the current point-change question.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={**enriched_metadata, "validation_result": "needs_solver_check"},
        )
    if len(extracted_numbers) == 1 and _message_is_mostly_numbers(message):
        return _result(
            intent=VisualTutorStudentIntent.SUBMITTED_STEP,
            relevance=VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER,
            confidence=0.72,
            explanation="The number looks like a possible slope or final answer.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={
                **enriched_metadata,
                "validation_result": "possible_final_answer",
            },
        )
    if extracted_numbers:
        return _result(
            intent=VisualTutorStudentIntent.UNKNOWN,
            relevance=VisualTutorInputRelevance.UNRELATED,
            confidence=0.72,
            explanation="The numbers do not clearly match the slope setup.",
            extracted_numbers=extracted_numbers,
            extracted_equations=extracted_equations,
            metadata={
                **enriched_metadata,
                "validation_result": "unrelated_numeric_input",
            },
        )
    return _generic_unknown_step(
        extracted_numbers, extracted_equations, enriched_metadata, fallback_intent
    )


def _generic_unknown_step(
    extracted_numbers: list[str],
    extracted_equations: list[str],
    metadata: dict[str, Any],
    fallback_intent: VisualTutorStudentIntent,
) -> VisualTutorInputUnderstandingResult:
    return _result(
        intent=(
            fallback_intent
            if fallback_intent != VisualTutorStudentIntent.UNKNOWN
            else VisualTutorStudentIntent.UNKNOWN
        ),
        relevance=VisualTutorInputRelevance.UNKNOWN,
        confidence=0.45,
        explanation="The input could not be matched to the expected current step.",
        extracted_numbers=extracted_numbers,
        extracted_equations=extracted_equations,
        metadata={**metadata, "validation_result": "unknown"},
    )


def _result(
    *,
    intent: VisualTutorStudentIntent,
    relevance: VisualTutorInputRelevance,
    confidence: float,
    explanation: str,
    extracted_numbers: list[str],
    extracted_equations: list[str],
    metadata: dict[str, Any],
    extracted_math: Optional[str] = None,
) -> VisualTutorInputUnderstandingResult:
    return VisualTutorInputUnderstandingResult(
        student_intent=intent,
        input_relevance=relevance,
        confidence=confidence,
        extracted_math=extracted_math,
        extracted_numbers=extracted_numbers,
        extracted_equations=extracted_equations,
        explanation=explanation,
        metadata={
            **metadata,
            "input_relevance": relevance.value,
            "validation_result": metadata.get("validation_result"),
        },
    )


def _extract_equations(message: str) -> list[str]:
    equations: list[str] = []
    for match in _EQUATION_RE.findall(message):
        cleaned = _clean_extracted_equation(match)
        if cleaned:
            equations.append(cleaned)
    return equations


def _clean_extracted_equation(candidate: str) -> str:
    cleaned = candidate.strip().rstrip(".,;:?!")
    while True:
        normalized = _EQUATION_LEADING_DISCOURSE_RE.sub("", cleaned).strip()
        if normalized == cleaned:
            return normalized
        cleaned = normalized


def _looks_like_new_problem(
    message: str,
    understanding: VisualTutorProblemUnderstandingResult,
) -> bool:
    has_new_problem_command = bool(
        re.search(
            r"(?i)\b(?:solve|find|calculate|simplify|ដោះស្រាយ|រក|គណនា)\b", message
        )
    )
    if not has_new_problem_command:
        return False
    return (
        parse_linear_equation(message) is not None
        or parse_line_through_points(message) is not None
        or understanding.extracted_problem.strip().lower()
        not in message.strip().lower()
    )


def _looks_like_math_problem(message: str) -> bool:
    return (
        parse_linear_equation(message) is not None
        or parse_line_through_points(message) is not None
        or bool(_extract_equations(message))
    )


def _looks_like_clarification(message: str) -> bool:
    return bool(
        re.search(r"(?i)\b(?:why|what|how|does that mean|can you explain)\b", message)
        or re.search(r"តើ|អ្វី|ហេតុអ្វី", message)
    )


def _understanding_check_answer(message: str) -> Optional[str]:
    normalized = re.sub(r"[^\w\s\u1780-\u17ff]", " ", message.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if normalized in {
        "yes",
        "y",
        "yeah",
        "yep",
        "correct",
        "true",
        "right",
        "it is true",
        "that is true",
        "បាទ",
        "ចាស",
        "ត្រូវ",
        "មែន",
    }:
        return "yes"
    if normalized in {
        "no",
        "n",
        "nope",
        "false",
        "not true",
        "incorrect",
        "wrong",
        "ទេ",
        "មិនមែន",
        "ខុស",
    }:
        return "no"
    return None


def _validate_linear_natural_language_operation(
    message: str,
    extracted_numbers: list[str],
    equation,
) -> dict[str, Any]:
    lowered = _normalized_operation_text(message)
    action = _operation_action(lowered)
    mentions_variable = equation.variable.lower() in lowered
    expected_operations = _linear_expected_operations(equation)

    for expected in expected_operations:
        action_matches = (
            action is None
            or expected["action"] == action
            or (expected["kind"] == "variable" and _mentions_move(lowered))
        )
        if not action_matches:
            continue
        if expected["kind"] == "variable":
            if not mentions_variable:
                continue
            if _operation_value_matches(extracted_numbers, expected["value"]):
                return {
                    "is_correct": True,
                    "confidence": 0.94,
                    "matched_operation": expected["label"],
                    "expected_operations": [
                        item["label"] for item in expected_operations
                    ],
                }
            if sympy.simplify(expected["value"]) == 1:
                return {
                    "is_correct": True,
                    "confidence": 0.88,
                    "matched_operation": expected["label"],
                    "expected_operations": [
                        item["label"] for item in expected_operations
                    ],
                }
            continue
        if _operation_value_matches(extracted_numbers, expected["value"]):
            return {
                "is_correct": True,
                "confidence": 0.94,
                "matched_operation": expected["label"],
                "expected_operations": [item["label"] for item in expected_operations],
            }

    relevant = mentions_variable or any(
        _operation_value_matches(extracted_numbers, expected["value"])
        for expected in expected_operations
    )
    return {
        "is_correct": False,
        "confidence": 0.78 if relevant else 0.68,
        "matched_operation": None,
        "expected_operations": [item["label"] for item in expected_operations],
    }


def _linear_expected_operations(equation) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    rhs_coefficient = sympy.simplify(equation.rhs_coefficient)
    lhs_constant = sympy.simplify(equation.lhs_constant)
    if rhs_coefficient != 0:
        if rhs_coefficient > 0:
            operations.append(
                {
                    "kind": "variable",
                    "action": "subtract",
                    "value": rhs_coefficient,
                    "label": f"subtract {_format_variable_operation_term(rhs_coefficient, equation.variable)}",
                }
            )
        else:
            operations.append(
                {
                    "kind": "variable",
                    "action": "add",
                    "value": abs(rhs_coefficient),
                    "label": f"add {_format_variable_operation_term(abs(rhs_coefficient), equation.variable)}",
                }
            )
    if lhs_constant != 0:
        if lhs_constant > 0:
            operations.append(
                {
                    "kind": "constant",
                    "action": "subtract",
                    "value": lhs_constant,
                    "label": f"subtract {_format_expr(lhs_constant)}",
                }
            )
        else:
            operations.append(
                {
                    "kind": "constant",
                    "action": "add",
                    "value": abs(lhs_constant),
                    "label": f"add {_format_expr(abs(lhs_constant))}",
                }
            )
    if not operations:
        operations.append(
            {
                "kind": "simplify",
                "action": "simplify",
                "value": sympy.Integer(0),
                "label": "simplify both sides",
            }
        )
    return operations


def _format_variable_operation_term(coefficient: Any, variable: str) -> str:
    simplified = sympy.simplify(coefficient)
    if simplified == 1:
        return variable
    if simplified == -1:
        return f"-{variable}"
    return f"{_format_expr(simplified)}{variable}"


def _operation_action(lowered: str) -> Optional[str]:
    if re.search(r"\b(?:add|adding|plus)\b|បន្ថែម", lowered):
        return "add"
    if re.search(
        r"\b(?:subtract|subtracting|minus|remove|take away)\b|ដក|យក",
        lowered,
    ):
        return "subtract"
    if _mentions_move(lowered):
        return None
    return None


def _mentions_move(lowered: str) -> bool:
    return bool(re.search(r"\b(?:move|moving|bring|shift)\b", lowered))


def _operation_value_matches(
    extracted_numbers: list[str],
    expected_value: sympy.Expr,
) -> bool:
    return any(
        _contains_sympy_value(extracted_numbers, value)
        for value in {expected_value, abs(sympy.simplify(expected_value))}
    )


def _normalized_operation_text(message: str) -> str:
    return (
        message.lower()
        .replace("−", "-")
        .replace("substract", "subtract")
        .replace("subsctract", "subtract")
        .replace("substrac", "subtract")
    )


def _mentions_operation(message: str, words: list[str]) -> bool:
    lowered = _normalized_operation_text(message)
    return any(word.lower() in lowered for word in words)


def _message_is_mostly_numbers(message: str) -> bool:
    stripped = message.strip().replace(" ", "")
    return bool(re.fullmatch(r"[-+]?\d+(?:/\d+)?(?:\.\d+)?", stripped))


def _parse_number(text: str) -> Optional[sympy.Expr]:
    try:
        return sympy.Rational(text)
    except Exception:
        return None


def _contains_sympy_value(candidates: list[str], value: sympy.Expr) -> bool:
    for candidate in candidates:
        parsed = _parse_number(candidate)
        if parsed is not None and sympy.simplify(parsed - value) == 0:
            return True
    return False


def _number_is_plausible_final(number: sympy.Expr, solution: sympy.Expr) -> bool:
    try:
        distance = abs(float(sympy.N(number - solution)))
        scale = max(10.0, abs(float(sympy.N(solution))) * 5.0)
        return distance <= scale
    except Exception:
        return True


def _equations_equivalent(left: str, right: str) -> bool:
    try:
        left_eq = parse_linear_equation(left)
        right_eq = parse_linear_equation(right)
        if left_eq and right_eq:
            return (
                sympy.simplify(left_eq.coefficient - right_eq.coefficient) == 0
                and sympy.simplify(left_eq.first_step_rhs - right_eq.first_step_rhs)
                == 0
            )
    except Exception:
        return False
    return False


def _linear_first_step_misconception(
    submitted_equation: str,
    *,
    equation,
    current_step_index: int,
) -> str:
    if current_step_index != 0:
        return "equation_step_mismatch"
    try:
        submitted = parse_linear_equation(submitted_equation)
        if submitted is None:
            return "equation_step_mismatch"
        same_variable_term = (
            submitted.variable == equation.variable
            and sympy.simplify(submitted.coefficient - equation.coefficient) == 0
        )
        wrong_sign_rhs = sympy.simplify(
            submitted.first_step_rhs - (equation.rhs + equation.constant)
        )
        if same_variable_term and equation.constant != 0 and wrong_sign_rhs == 0:
            return "sign_error"
    except Exception:
        return "equation_step_mismatch"
    return "equation_step_mismatch"


def _format_expr(value: sympy.Expr) -> str:
    return str(sympy.simplify(value)).replace("**", "^")
