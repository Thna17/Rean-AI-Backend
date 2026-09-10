from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Protocol

import sympy
from sympy.parsing.sympy_parser import (
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from api.models.quiz import (
    QuizChoice,
    QuizGenerationRequest,
    QuizGenerationResponse,
    QuizQuestion,
)
from api.services.visual_tutor.llm_teaching_planner import _default_llm_client


QUIZ_GENERATOR_VERSION = "basic_verified_quiz_generator_v1"
_TRANSFORMATIONS = standard_transformations + (implicit_multiplication_application,)
SUPPORTED_PROBLEM_TYPES = frozenset({
    "linear_equation_one_variable",
    "integer_arithmetic",
    "fraction_decimal_arithmetic",
    "simple_percentage_word_problem",
    "slope_from_points",
    "line_through_two_points",
    "basic_quadratic_graph",
})


class QuizLLMClient(Protocol):
    def complete(self, *, system_prompt: str, user_prompt: str) -> str: ...


def clear_quiz_cache() -> None:
    """Backward-compatible no-op: generated quizzes are persisted by the API backend."""


def generate_topic_quiz(
    request: QuizGenerationRequest,
    *,
    llm_client: QuizLLMClient | None = None,
) -> QuizGenerationResponse:
    requested_type = request.problem_type or _problem_type_for_topic(request.topic)
    if requested_type not in SUPPORTED_PROBLEM_TYPES:
        raise ValueError(f"Unsupported targeted-practice problem type: {requested_type}")
    response: QuizGenerationResponse | None = None
    if request.use_llm:
        response = _try_generate_with_llm(request, llm_client=llm_client)

    if response is None:
        response = _deterministic_fallback_quiz(request)
        if request.use_llm:
            response.metadata = {**response.metadata, "source": "deterministic_fallback"}

    response.cache_hit = False
    response.metadata = {
        **response.metadata,
        "generator": QUIZ_GENERATOR_VERSION,
    }
    return response


def _try_generate_with_llm(
    request: QuizGenerationRequest,
    *,
    llm_client: QuizLLMClient | None,
) -> QuizGenerationResponse | None:
    client = llm_client or _default_llm_client()
    try:
        raw = client.complete(
            system_prompt=_quiz_system_prompt(),
            user_prompt=json.dumps(request.model_dump(mode="json"), ensure_ascii=False),
        )
        payload = _extract_json(raw)
        response = QuizGenerationResponse.model_validate(payload)
        if not _verify_quiz_response(response, requested_type=request.problem_type or _problem_type_for_topic(request.topic)):
            return None
        response.metadata = {
            **response.metadata,
            "source": "llm",
            "llm_verified": True,
        }
        return response
    except Exception:
        return None


def _deterministic_fallback_quiz(
    request: QuizGenerationRequest,
) -> QuizGenerationResponse:
    subject = request.subject or "Mathematics"
    topic = request.topic or "Linear Equations"
    problem_type = request.problem_type or _problem_type_for_topic(topic)
    difficulty = request.difficulty or "easy"

    if problem_type not in SUPPORTED_PROBLEM_TYPES:
        raise ValueError(
            "Targeted practice currently supports linear equations, integer arithmetic, and slope from points"
        )

    question_builders = {
        "linear_equation_one_variable": _linear_equation_questions,
        "integer_arithmetic": _integer_arithmetic_questions,
        "fraction_decimal_arithmetic": _fraction_decimal_questions,
        "simple_percentage_word_problem": _percentage_questions,
        "slope_from_points": _slope_questions,
        "line_through_two_points": _line_questions,
        "basic_quadratic_graph": _quadratic_graph_questions,
    }
    questions = question_builders[problem_type](request, topic, difficulty)
    response = QuizGenerationResponse(
        quiz_id=_quiz_id(subject, topic, problem_type, difficulty, request),
        subject=subject,
        topic=topic,
        problem_type=problem_type,
        difficulty=difficulty,
        questions=questions,
        verified=all(_verify_quiz_question(question) for question in questions),
        metadata={
            "source": "deterministic_verified",
            "supported_problem_type": problem_type,
            "personalization": _personalization_metadata(request),
        },
    )
    return response


def _verify_quiz_response(
    response: QuizGenerationResponse,
    *,
    requested_type: str | None,
) -> bool:
    """Reject a plausible quiz if it quietly changes the learner's topic."""
    return (
        response.verified
        and requested_type in SUPPORTED_PROBLEM_TYPES
        and response.problem_type == requested_type
        and 3 <= len(response.questions) <= 5
        and all(
            question.problem_type == requested_type and _verify_quiz_question(question)
            for question in response.questions
        )
    )


def _verify_quiz_question(question: QuizQuestion) -> bool:
    if question.problem_type not in SUPPORTED_PROBLEM_TYPES:
        return False
    equation = str(question.metadata.get("equation") or "")
    if not equation or "=" not in equation:
        return question.metadata.get("verified_by") in {"deterministic", "sympy"}
    solved = _solve_linear_equation(equation)
    expected_answer = question.expected_answer or _choice_text(question)
    return solved is not None and _normalize_answer(solved) == _normalize_answer(
        expected_answer
    )


def _choice_text(question: QuizQuestion) -> str:
    for choice in question.choices:
        if choice.id == question.correct_answer or choice.text == question.correct_answer:
            return choice.text
    return question.correct_answer


def _solve_linear_equation(equation: str) -> str | None:
    try:
        lhs_text, rhs_text = equation.split("=", 1)
        lhs = parse_expr(lhs_text.strip(), transformations=_TRANSFORMATIONS)
        rhs = parse_expr(rhs_text.strip(), transformations=_TRANSFORMATIONS)
        variables = sorted((lhs.free_symbols | rhs.free_symbols), key=lambda symbol: symbol.name)
        if len(variables) != 1:
            return None
        variable = variables[0]
        solutions = sympy.solve(sympy.Eq(lhs, rhs), variable)
        if len(solutions) != 1:
            return None
        return f"{variable} = {sympy.sstr(sympy.simplify(solutions[0]))}"
    except Exception:
        return None


def _normalize_answer(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().lower())


def _problem_type_for_topic(topic: str) -> str | None:
    normalized = topic.strip().lower().replace("-", " ")
    if "linear" in normalized and "equation" in normalized:
        return "linear_equation_one_variable"
    if any(word in normalized for word in ("integer", "addition", "subtraction")):
        return "integer_arithmetic"
    if any(word in normalized for word in ("fraction", "decimal")):
        return "fraction_decimal_arithmetic"
    if "percent" in normalized:
        return "simple_percentage_word_problem"
    if "straight" in normalized or "equation of a line" in normalized:
        return "line_through_two_points"
    if "quadratic" in normalized:
        return "basic_quadratic_graph"
    if "slope" in normalized or "coordinate" in normalized:
        return "slope_from_points"
    return None


def _quiz_id(subject: str, topic: str, problem_type: str, difficulty: str, request: QuizGenerationRequest) -> str:
    raw = f"{subject}:{topic}:{problem_type}:{difficulty}:{request.tutor_session_id}:{request.skill_tags}:{request.hint_count}".lower()
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"quiz-{digest}"


def _cache_key(request: QuizGenerationRequest) -> str:
    payload = request.model_dump(mode="json")
    payload.pop("user_id", None)
    payload["metadata"] = payload.get("metadata") or {}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _quiz_system_prompt() -> str:
    return (
        "Return only strict JSON matching QuizGenerationResponse. "
        "Generate 3 to 5 short questions using only supported types: linear_equation_one_variable, integer_arithmetic, fraction_decimal_arithmetic, simple_percentage_word_problem, slope_from_points, line_through_two_points, basic_quadratic_graph. "
        "Fields must include quiz_id, subject, topic, problem_type, difficulty, "
        "questions, verified, cache_hit, metadata. "
        "Each question must include id, type, question_text, choices or expected_answer, "
        "correct_answer, explanation, difficulty, topic, problem_type, metadata. "
        "For math equations, include metadata.equation and ensure correct_answer is verified."
    )


def _personalization_metadata(request: QuizGenerationRequest) -> dict[str, Any]:
    needs_support = request.hint_count >= 2 or request.stuck_count > 0 or bool(request.misconceptions) or any(
        result in {"invalid", "incomplete", "cannot_verify"}
        for result in request.verification_results
    )
    difficulty = "beginner" if needs_support or (request.prior_mastery or 0) < 0.4 else (
        "advanced" if (request.prior_mastery or 0) >= 0.8 and (request.prior_quiz_score or 0) >= 80 else "intermediate"
    )
    return {
        "recommended_difficulty": difficulty,
        "skill_tags": request.skill_tags[:8],
        "hint_count": request.hint_count,
        "stuck_count": request.stuck_count,
        "misconception_count": len(request.misconceptions),
    }


def _choice_question(*, question_id: str, text: str, choices: list[str], correct_index: int,
                     explanation: str, difficulty: str, topic: str, problem_type: str,
                     metadata: dict[str, Any]) -> QuizQuestion:
    option_ids = [chr(ord("A") + index) for index in range(len(choices))]
    return QuizQuestion(
        id=question_id, type="multiple_choice", question_text=text,
        choices=[QuizChoice(id=option_id, text=choice) for option_id, choice in zip(option_ids, choices)],
        correct_answer=option_ids[correct_index], expected_answer=choices[correct_index],
        explanation=explanation, difficulty=difficulty, topic=topic, problem_type=problem_type, metadata=metadata,
    )


def _linear_equation_questions(request: QuizGenerationRequest, topic: str, difficulty: str) -> list[QuizQuestion]:
    variants = [(2, 5, 15), (3, 4, 19), (4, -3, 17), (5, 7, 32), (6, -2, 22)]
    offset = (request.hint_count + len(request.misconceptions)) % len(variants)
    questions: list[QuizQuestion] = []
    for index in range(3):
        coefficient, constant, rhs = variants[(offset + index) % len(variants)]
        solution = sympy.Rational(rhs - constant, coefficient)
        answer = f"x = {sympy.sstr(solution)}"
        equation = f"{coefficient}*x {'+' if constant >= 0 else '-'} {abs(constant)} = {rhs}"
        choices = [answer, f"x = {sympy.sstr(solution + 1)}", f"x = {sympy.sstr(rhs - constant)}", f"x = {sympy.sstr(solution - 1)}"]
        questions.append(_choice_question(
            question_id=f"linear-{index + 1}", text=f"Solve: {equation.replace('*', '')}", choices=choices,
            correct_index=0, explanation=f"First isolate {coefficient}x, then divide both sides by {coefficient}.",
            difficulty=difficulty, topic=topic, problem_type="linear_equation_one_variable",
            metadata={"equation": equation, "sympy_solution": answer, "verified_by": "sympy", "skill_tags": request.skill_tags},
        ))
    return questions


def _integer_arithmetic_questions(request: QuizGenerationRequest, topic: str, difficulty: str) -> list[QuizQuestion]:
    values = [(7, -3), (-8, 5), (12, -7)]
    return [_choice_question(
        question_id=f"integer-{index + 1}", text=f"Calculate: {left} + ({right})", choices=[str(left + right), str(left - right), str(abs(left + right)), str(-left - right)], correct_index=0,
        explanation="Use the signs carefully and combine the two integers.", difficulty=difficulty, topic=topic,
        problem_type="integer_arithmetic", metadata={"verified_by": "deterministic", "skill_tags": request.skill_tags},
    ) for index, (left, right) in enumerate(values)]


def _fraction_decimal_questions(request: QuizGenerationRequest, topic: str, difficulty: str) -> list[QuizQuestion]:
    variants = [("1/2 + 1/4", "3/4"), ("0.6 + 0.25", "0.85"), ("3/5 - 1/10", "1/2")]
    return [
        _choice_question(
            question_id=f"fraction-decimal-{index + 1}", text=f"Calculate: {expression}",
            choices=[answer, "1/4", "1", "0"], correct_index=0,
            explanation="Keep the fraction or decimal form clear and simplify one operation at a time.",
            difficulty=difficulty, topic=topic, problem_type="fraction_decimal_arithmetic",
            metadata={"verified_by": "deterministic", "expression": expression, "skill_tags": request.skill_tags},
        ) for index, (expression, answer) in enumerate(variants)
    ]


def _percentage_questions(request: QuizGenerationRequest, topic: str, difficulty: str) -> list[QuizQuestion]:
    variants = [(20, 50), (15, 80), (12.5, 40)]
    return [
        _choice_question(
            question_id=f"percentage-{index + 1}", text=f"What is {percent}% of {base}?",
            choices=[sympy.sstr(sympy.Rational(str(percent)) * sympy.Rational(str(base)) / 100), "0", str(base), str(percent)],
            correct_index=0, explanation="Convert the percent to a rate out of 100, then multiply by the base.",
            difficulty=difficulty, topic=topic, problem_type="simple_percentage_word_problem",
            metadata={"verified_by": "deterministic", "percent": percent, "base": base, "skill_tags": request.skill_tags},
        ) for index, (percent, base) in enumerate(variants)
    ]


def _slope_questions(request: QuizGenerationRequest, topic: str, difficulty: str) -> list[QuizQuestion]:
    points = [((1, 2), (3, 6)), ((-1, 4), (2, 10)), ((0, -2), (4, 2))]
    questions: list[QuizQuestion] = []
    for index, ((x1, y1), (x2, y2)) in enumerate(points):
        slope = sympy.Rational(y2 - y1, x2 - x1)
        answer = sympy.sstr(slope)
        questions.append(_choice_question(
            question_id=f"slope-{index + 1}", text=f"What is the slope through ({x1}, {y1}) and ({x2}, {y2})?",
            choices=[answer, sympy.sstr(slope + 1), sympy.sstr(-slope), "0"], correct_index=0,
            explanation="Slope is rise divided by run: (y₂ − y₁) / (x₂ − x₁).", difficulty=difficulty, topic=topic,
            problem_type="slope_from_points", metadata={"points": [[x1, y1], [x2, y2]], "verified_by": "deterministic", "skill_tags": request.skill_tags},
        ))
    return questions


def _line_questions(request: QuizGenerationRequest, topic: str, difficulty: str) -> list[QuizQuestion]:
    variants = [((0, 1), (1, 3), "y = 2x + 1"), ((1, 2), (3, 6), "y = 2x"), ((0, -1), (2, 3), "y = 2x - 1")]
    return [
        _choice_question(
            question_id=f"line-{index + 1}", text=f"Which line goes through {first} and {second}?",
            choices=[answer, "y = x + 1", "y = -2x + 1", "y = 2x + 2"], correct_index=0,
            explanation="Use the two points to find slope, then find the intercept.", difficulty=difficulty,
            topic=topic, problem_type="line_through_two_points",
            metadata={"verified_by": "deterministic", "points": [first, second], "skill_tags": request.skill_tags},
        ) for index, (first, second, answer) in enumerate(variants)
    ]


def _quadratic_graph_questions(request: QuizGenerationRequest, topic: str, difficulty: str) -> list[QuizQuestion]:
    variants = [("y = x^2 - 4x + 3", "2"), ("y = x^2 + 2x - 3", "-1"), ("y = 2x^2 - 8x + 1", "2")]
    return [
        _choice_question(
            question_id=f"quadratic-graph-{index + 1}", text=f"What is the x-coordinate of the vertex of {equation}?",
            choices=[vertex_x, "0", "1", "-2"], correct_index=0,
            explanation="For y = ax² + bx + c, the vertex x-coordinate is -b/(2a).",
            difficulty=difficulty, topic=topic, problem_type="basic_quadratic_graph",
            metadata={"verified_by": "deterministic", "function": equation, "skill_tags": request.skill_tags},
        ) for index, (equation, vertex_x) in enumerate(variants)
    ]


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("LLM quiz output did not contain a JSON object")
        cleaned = cleaned[start : end + 1]
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("LLM quiz output must be a JSON object")
    return payload
