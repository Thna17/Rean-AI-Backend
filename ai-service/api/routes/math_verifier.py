"""Bounded deterministic verification for supported algebra expressions."""
from __future__ import annotations

import re
from typing import Any, Literal

import sympy
from fastapi import APIRouter
from pydantic import BaseModel, Field
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

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
    if re.search(r"\b(?:import|exec|eval|lambda|function|sin|cos|log)\b", cleaned, re.I):
        raise ValueError("unsupported notation")
    return parse_expr(
        cleaned,
        local_dict=_LOCALS,
        global_dict=_GLOBALS,
        transformations=_TRANSFORMS,
        evaluate=True,
    )

def _equation(value: str) -> tuple[sympy.Expr, sympy.Expr]:
    if value.count("=") != 1:
        raise ValueError("an equation needs one equals sign")
    left, right = value.split("=", 1)
    return _parse(left), _parse(right)

@router.post("/verify", response_model=MathResponse)
def verify_math(query: MathQuery) -> MathResponse:
    try:
        if "=" not in query.expression:
            expr = sympy.simplify(_parse(query.expression))
            return MathResponse(status="correct", verified=True, normalized_expression=str(expr).replace("**", "^"), student_message="This expression is mathematically valid.", evidence={"method": "sympy_simplify"})
        lhs, rhs = _equation(query.expression)
        difference = sympy.simplify(lhs - rhs)
        if query.previous_step:
            previous_lhs, previous_rhs = _equation(query.previous_step)
            previous_difference = sympy.simplify(previous_lhs - previous_rhs)
            if sympy.simplify(difference - previous_difference) == 0:
                return MathResponse(status="correct", verified=True, normalized_expression=f"{lhs} = {rhs}", student_message="This keeps the equation balanced.", evidence={"method": "equation_equivalence"})
            return MathResponse(status="invalid", verified=True, normalized_expression=f"{lhs} = {rhs}", student_message="This step does not preserve the previous equation.", evidence={"method": "equation_equivalence", "reason": "not_equivalent_to_previous_step"})
        symbols = sorted((lhs - rhs).free_symbols, key=lambda item: item.name)
        if not symbols:
            if difference != 0:
                return MathResponse(status="correct", verified=True, normalized_expression=f"{lhs} = {rhs}", solution="no solution", student_message="This equation has no solution.", evidence={"method": "constant_contradiction"})
            return MathResponse(status="correct", verified=True, normalized_expression=f"{lhs} = {rhs}", solution="all real numbers", student_message="This equation is true for every real number.", evidence={"method": "identity"})
        if len(symbols) != 1:
            return MathResponse(status="cannot_verify", verified=False, normalized_expression=f"{lhs} = {rhs}", student_message="I cannot verify this notation safely.", evidence={"reason": "unsupported_domain"})
        solutions = sympy.solve(sympy.Eq(lhs, rhs), symbols[0])
        if not solutions:
            return MathResponse(status="correct", verified=True, normalized_expression=f"{lhs} = {rhs}", solution="no solution", student_message="This equation has no solution.", evidence={"method": "sympy_solve"})
        return MathResponse(status="correct", verified=True, normalized_expression=f"{lhs} = {rhs}", solution=str(solutions).replace("**", "^"), student_message="This equation is solved correctly.", evidence={"method": "sympy_solve"})
    except (ValueError, TypeError, NameError, sympy.SympifyError, SyntaxError, ZeroDivisionError):
        return MathResponse(status="cannot_verify", verified=False, student_message="I cannot verify this notation safely.", evidence={"reason": "unsupported_or_malformed_input"})


def verify_student_work(
    *, problem: str, student_step: str, expected_step: str | None = None
) -> MathResponse:
    """Verify a learner's step separately from AI teaching text."""
    if not student_step.strip():
        return MathResponse(status="incomplete", verified=False, student_message="Enter one math step so I can check it.", evidence={"reason": "enter_a_math_step"})
    if any(word in problem.lower() for word in ("prove", "triangle", "geometry", "word problem")):
        return MathResponse(status="cannot_verify", verified=False, student_message="I can explain this, but I cannot verify this type of problem symbolically.", evidence={"reason": "unsupported_domain"})
    try:
        if re.search(r"/\s*0(?:\D|$)", student_step):
            return MathResponse(status="invalid", verified=True, student_message="Division by zero is not defined.", evidence={"reason": "division_by_zero"})
        student_lhs, student_rhs = _equation(student_step)
        problem_lhs, problem_rhs = _equation(problem)
        student_difference = sympy.simplify(student_lhs - student_rhs)
        problem_difference = sympy.simplify(problem_lhs - problem_rhs)
        symbols = sorted(problem_difference.free_symbols, key=lambda item: item.name)
        if not symbols:
            if problem_difference != 0:
                return MathResponse(
                    status="correct",
                    verified=True,
                    normalized_expression=f"{student_lhs} = {student_rhs}",
                    solution="no solution",
                    student_message="This equation has no solution.",
                    evidence={"method": "constant_contradiction"},
                )
            return MathResponse(
                status="correct",
                verified=True,
                normalized_expression=f"{student_lhs} = {student_rhs}",
                solution="all real numbers",
                student_message="This equation is true for every real number.",
                evidence={"method": "identity"},
            )
        if len(symbols) != 1:
            return MathResponse(status="cannot_verify", verified=False, student_message="I cannot verify this step because its variable or domain is ambiguous.", evidence={"reason": "ambiguous_or_unsupported_domain"})
        variable = symbols[0]
        original_solutions = sympy.solveset(sympy.Eq(problem_lhs, problem_rhs), variable, domain=sympy.S.Reals)
        step_solutions = sympy.solveset(sympy.Eq(student_lhs, student_rhs), variable, domain=sympy.S.Reals)
        if original_solutions != step_solutions:
            return MathResponse(status="invalid", verified=True, normalized_expression=f"{student_lhs} = {student_rhs}", student_message="This changes the solution set, so the step is not valid.", evidence={"reason": "not_equivalent_to_problem", "method": "solution_set"})
        status = "correct"
        if expected_step and student_step.replace(" ", "") != expected_step.replace(" ", ""):
            status = "mathematically_valid_but_inefficient"
        solution_text = str(original_solutions).replace("**", "^")
        if original_solutions is sympy.EmptySet:
            solution_text = "no solution"
        message = "This step is mathematically valid."
        if status == "mathematically_valid_but_inefficient":
            message = "This is mathematically valid, but try the requested smaller step first."
        return MathResponse(status=status, verified=True, normalized_expression=f"{student_lhs} = {student_rhs}", solution=solution_text, student_message=message, evidence={"method": "solution_set_equivalence", "variable": str(variable), "expected_step": expected_step})
    except (ValueError, TypeError, NameError, sympy.SympifyError, SyntaxError, ZeroDivisionError):
        return MathResponse(status="cannot_verify", verified=False, student_message="I cannot verify this notation safely. Try writing one equation step.", evidence={"reason": "malformed_or_unsupported_notation"})
