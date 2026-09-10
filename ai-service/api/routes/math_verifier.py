"""Bounded deterministic verification for supported algebra expressions."""
from __future__ import annotations

import re
from typing import Any, Literal

import sympy
from fastapi import APIRouter, Header
from pydantic import BaseModel, Field
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)
from api.core.visual_tutor_gateway_auth import require_visual_tutor_service

router = APIRouter()
_ALLOWED = re.compile(r"^[0-9a-zA-Z+\-*/^=().,\s]+$")
_TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)
_LOCALS = {name: sympy.Symbol(name) for name in "abcdefghijklmnopqrstuvwxyz"}
# `parse_expr` transformations emit these SymPy constructors. Keep the global
# namespace narrowly allow-listed rather than evaluating against Python globals.
_GLOBALS = {
    "__builtins__": {},
    "Integer": sympy.Integer,
    "Float": sympy.Float,
    "Rational": sympy.Rational,
    "Symbol": sympy.Symbol,
}
_VERIFICATION_STATUSES = {
    "correct",
    "mathematically_valid_but_inefficient",
    "invalid",
    "incomplete",
    "cannot_verify",
}
_UNSUPPORTED_WORDS = re.compile(
    r"\b(?:import|exec|eval|lambda|function|sin|cos|tan|log|sqrt|limit|integral|nan|zoo|oo)\b",
    re.I,
)

class MathQuery(BaseModel):
    expression: str = Field(min_length=1, max_length=300)
    previous_step: str | None = Field(default=None, max_length=300)

class MathResponse(BaseModel):
    status: Literal["correct", "mathematically_valid_but_inefficient", "invalid", "incomplete", "cannot_verify"]
    verified: bool
    normalized_expression: str | None = None
    solution: str | None = None
    student_message: str
    evidence: dict[str, Any] = Field(default_factory=dict)

    @property
    def normalized(self) -> str | None:
        """Compatibility accessor for internal callers; API output uses the contract name."""
        return self.normalized_expression

def _parse(value: str) -> sympy.Expr:
    cleaned = value.strip().replace("−", "-")
    if not _ALLOWED.fullmatch(cleaned) or "__" in cleaned or len(cleaned) > 300:
        raise ValueError("unsupported notation")
    if _UNSUPPORTED_WORDS.search(cleaned):
        raise ValueError("unsupported notation")
    expression = parse_expr(
        cleaned,
        local_dict=_LOCALS,
        global_dict=_GLOBALS,
        transformations=_TRANSFORMS,
        evaluate=True,
    )
    _ensure_safe_expression(expression)
    return expression


def _ensure_safe_expression(expression: sympy.Expr) -> None:
    """Reject undefined/non-finite constructs before SymPy can reason with them."""
    if expression.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo):
        raise ValueError("undefined or non-finite expression")
    if sum(1 for _ in sympy.preorder_traversal(expression)) > 120:
        raise ValueError("expression is too complex to verify safely")
    denominator = sympy.denom(sympy.cancel(expression))
    if denominator == 0:
        raise ZeroDivisionError("division by zero")

def _equation(value: str) -> tuple[sympy.Expr, sympy.Expr]:
    if value.count("=") != 1:
        raise ValueError("an equation needs one equals sign")
    left, right = value.split("=", 1)
    return _parse(left), _parse(right)


def _normalized_equation(lhs: sympy.Expr, rhs: sympy.Expr) -> str:
    return f"{lhs} = {rhs}".replace("**", "^")


def _solution_set(lhs: sympy.Expr, rhs: sympy.Expr, variable: sympy.Symbol) -> sympy.Set:
    solutions = sympy.solveset(sympy.Eq(lhs, rhs), variable, domain=sympy.S.Reals)
    # ConditionSet and other symbolic sets cannot be represented truthfully to
    # a student as a deterministic verification result.
    if isinstance(solutions, sympy.ConditionSet):
        raise ValueError("unsupported solution set")
    return solutions


def _solution_text(solutions: sympy.Set) -> str:
    if solutions is sympy.EmptySet:
        return "no solution"
    if isinstance(solutions, sympy.FiniteSet):
        return str(sorted(solutions, key=sympy.default_sort_key)).replace("**", "^")
    return str(solutions).replace("**", "^")


def _single_supported_variable(lhs: sympy.Expr, rhs: sympy.Expr) -> sympy.Symbol:
    symbols = sorted((lhs - rhs).free_symbols, key=lambda item: item.name)
    if len(symbols) != 1:
        raise ValueError("ambiguous or unsupported variables")
    return symbols[0]

@router.post("/verify", response_model=MathResponse)
def verify_math_endpoint(
    query: MathQuery,
    x_visual_tutor_internal_token: str | None = Header(default=None),
) -> MathResponse:
    """Internal gateway endpoint; verification is never a public compute API."""
    require_visual_tutor_service(x_visual_tutor_internal_token)
    return verify_math(query)


def verify_math(query: MathQuery) -> MathResponse:
    try:
        if "=" not in query.expression:
            expr = sympy.simplify(_parse(query.expression))
            return MathResponse(status="cannot_verify", verified=False, normalized_expression=str(expr).replace("**", "^"), student_message="This is an expression, not a checkable equation or student step.", evidence={"reason": "expression_has_no_verifiable_claim"})
        lhs, rhs = _equation(query.expression)
        difference = sympy.simplify(lhs - rhs)
        _ensure_safe_expression(difference)
        if query.previous_step:
            previous_lhs, previous_rhs = _equation(query.previous_step)
            previous_difference = sympy.simplify(previous_lhs - previous_rhs)
            if sympy.simplify(difference - previous_difference) == 0:
                return MathResponse(status="correct", verified=True, normalized_expression=_normalized_equation(lhs, rhs), student_message="This keeps the equation balanced.", evidence={"method": "equation_equivalence"})
            return MathResponse(status="invalid", verified=True, normalized_expression=_normalized_equation(lhs, rhs), student_message="This step does not preserve the previous equation.", evidence={"method": "equation_equivalence", "reason": "not_equivalent_to_previous_step"})
        symbols = sorted((lhs - rhs).free_symbols, key=lambda item: item.name)
        if not symbols:
            if difference != 0:
                return MathResponse(status="correct", verified=True, normalized_expression=f"{lhs} = {rhs}", solution="no solution", student_message="This equation has no solution.", evidence={"method": "constant_contradiction"})
            return MathResponse(status="correct", verified=True, normalized_expression=f"{lhs} = {rhs}", solution="all real numbers", student_message="This equation is true for every real number.", evidence={"method": "identity"})
        if len(symbols) != 1:
            return MathResponse(status="cannot_verify", verified=False, normalized_expression=_normalized_equation(lhs, rhs), student_message="I cannot verify this notation safely.", evidence={"reason": "unsupported_domain"})
        solutions = _solution_set(lhs, rhs, symbols[0])
        solution_text = _solution_text(solutions)
        return MathResponse(status="correct", verified=True, normalized_expression=_normalized_equation(lhs, rhs), solution=solution_text, student_message="This equation and its solution set were verified.", evidence={"method": "sympy_solveset", "variable": str(symbols[0])})
    except Exception as exc:
        # SymPy uses several exception types for unsupported algebra. They all
        # mean the same safe student-facing result, never a 500 or a claim.
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return MathResponse(status="cannot_verify", verified=False, student_message="I cannot verify this notation safely.", evidence={"reason": "unsupported_or_malformed_input"})


def verify_student_work(
    *, problem: str, student_step: str, expected_step: str | None = None
) -> MathResponse:
    """Verify a learner's step separately from AI teaching text."""
    if not student_step.strip():
        return MathResponse(status="incomplete", verified=False, student_message="Enter one math step so I can check it.", evidence={"reason": "enter_a_math_step"})
    if any(word in problem.lower() for word in ("prove", "triangle", "geometry", "word problem", " travels ", "hours", "speed")):
        return MathResponse(status="cannot_verify", verified=False, student_message="I can explain this, but I cannot verify this type of problem symbolically.", evidence={"reason": "unsupported_domain"})
    try:
        if re.search(r"/\s*0(?:\D|$)", student_step) or re.search(r"/\s*0(?:\D|$)", problem):
            return MathResponse(status="invalid", verified=True, student_message="Division by zero is not defined.", evidence={"reason": "division_by_zero"})
        student_lhs, student_rhs = _equation(student_step)
        problem_lhs, problem_rhs = _equation(problem)
        student_difference = sympy.simplify(student_lhs - student_rhs)
        problem_difference = sympy.simplify(problem_lhs - problem_rhs)
        _ensure_safe_expression(student_difference)
        _ensure_safe_expression(problem_difference)
        symbols = sorted(problem_difference.free_symbols, key=lambda item: item.name)
        if not symbols:
            # A constant problem only validates a constant-equivalent statement.
            if sympy.simplify(student_difference - problem_difference) != 0:
                return MathResponse(status="invalid", verified=True, normalized_expression=_normalized_equation(student_lhs, student_rhs), student_message="This does not preserve the original statement.", evidence={"reason": "not_equivalent_to_problem", "method": "constant_equivalence"})
            solution = "no solution" if problem_difference != 0 else "all real numbers"
            return MathResponse(status="correct", verified=True, normalized_expression=_normalized_equation(student_lhs, student_rhs), solution=solution, student_message="This statement is equivalent to the original.", evidence={"method": "constant_equivalence"})
        if len(symbols) != 1 or student_difference.free_symbols - set(symbols):
            return MathResponse(status="cannot_verify", verified=False, student_message="I cannot verify this step because its variable or domain is ambiguous.", evidence={"reason": "ambiguous_or_unsupported_domain"})
        variable = symbols[0]
        original_solutions = _solution_set(problem_lhs, problem_rhs, variable)
        step_solutions = _solution_set(student_lhs, student_rhs, variable)
        if original_solutions != step_solutions:
            return MathResponse(status="invalid", verified=True, normalized_expression=_normalized_equation(student_lhs, student_rhs), student_message="This changes the solution set, so the step is not valid.", evidence={"reason": "not_equivalent_to_problem", "method": "solution_set"})
        status = "correct"
        if expected_step:
            expected_lhs, expected_rhs = _equation(expected_step)
            expected_solutions = _solution_set(expected_lhs, expected_rhs, variable)
            if expected_solutions != original_solutions:
                raise ValueError("unsafe expected teaching step")
            if sympy.simplify((student_lhs - student_rhs) - (expected_lhs - expected_rhs)) != 0:
                status = "mathematically_valid_but_inefficient"
        solution_text = _solution_text(original_solutions)
        message = "This step is mathematically valid."
        if status == "mathematically_valid_but_inefficient":
            message = "This is mathematically valid, but try the requested smaller step first."
        return MathResponse(status=status, verified=True, normalized_expression=_normalized_equation(student_lhs, student_rhs), solution=solution_text, student_message=message, evidence={"method": "solution_set_equivalence", "variable": str(variable), "expected_step": expected_step, "verified_against": ["original_problem", "current_teaching_step"] if expected_step else ["original_problem"]})
    except Exception as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        return MathResponse(status="cannot_verify", verified=False, student_message="I cannot verify this notation safely. Try writing one equation step.", evidence={"reason": "malformed_or_unsupported_notation"})
