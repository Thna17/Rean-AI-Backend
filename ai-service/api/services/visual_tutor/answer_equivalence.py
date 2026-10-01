"""Mathematical equivalence for a student's submitted answer.

Quiz grading used to compare answer strings, so a student who wrote `1/2` where
the key said `0.5`, or `x=2 or x=3` where the key said `x = 3 or x = 2`, was
marked wrong. This module decides equivalence with SymPy instead.

It answers three states, and the caller must distinguish them: the answers are
equivalent, they are genuinely different, or the submission could not be checked
at all. Treating the third as "wrong" is what this exists to prevent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Optional

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

# `sqrt` is allowed because real answers contain radicals; everything else that
# could reach code execution or an unbounded computation stays out.
_ALLOWED = re.compile(r"^[0-9a-zA-Z+\-*/^=().,;\s]+$")
_BLOCKED_WORDS = re.compile(
    r"\b(?:import|exec|eval|lambda|def|class|open|file|input|print"
    r"|limit|integrate|diff|solve|series|nan|zoo|oo|inf|infinity)\b",
    re.I,
)
_TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)
_LOCALS = {name: sympy.Symbol(name) for name in "abcdefghijklmnopqrstuvwxyz"}
_LOCALS["sqrt"] = sympy.sqrt
_LOCALS["pi"] = sympy.pi
_GLOBALS = {
    "__builtins__": {},
    "Integer": sympy.Integer,
    "Float": sympy.Float,
    "Rational": sympy.Rational,
    "Symbol": sympy.Symbol,
    "sqrt": sympy.sqrt,
}

_MAX_LENGTH = 300
_MAX_NODES = 200
_MAX_CLAIMS = 8
_CLAIM_SEPARATOR = re.compile(r"\bor\b|\band\b|[,;]", re.I)

Status = Literal["equivalent", "different", "cannot_verify"]


@dataclass(frozen=True)
class EquivalenceResult:
    """Outcome of comparing a submitted answer with the expected one."""

    equivalent: bool
    status: Status
    detail: str


def _normalize(raw: str) -> str:
    text = (raw or "").strip()
    text = text.replace("−", "-").replace("—", "-").replace("–", "-")
    text = text.replace("×", "*").replace("÷", "/")
    # A student types the radical sign; SymPy needs the function name. `√39`
    # and `√(x+1)` both become `sqrt(...)`.
    text = re.sub(r"√\s*\(", "sqrt(", text)
    text = re.sub(r"√\s*([0-9a-zA-Z.]+)", r"sqrt(\1)", text)
    return text


def _parse_value(raw: str) -> sympy.Expr:
    cleaned = raw.strip()
    if not cleaned:
        raise ValueError("empty value")
    if len(cleaned) > _MAX_LENGTH or "__" in cleaned:
        raise ValueError("unsupported notation")
    if not _ALLOWED.fullmatch(cleaned) or _BLOCKED_WORDS.search(cleaned):
        raise ValueError("unsupported notation")
    expression = parse_expr(
        cleaned,
        local_dict=_LOCALS,
        global_dict=_GLOBALS,
        transformations=_TRANSFORMS,
        evaluate=True,
    )
    if not isinstance(expression, sympy.Basic):
        raise ValueError("unsupported notation")
    if expression.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo):
        raise ValueError("undefined or non-finite value")
    if sum(1 for _ in sympy.preorder_traversal(expression)) > _MAX_NODES:
        raise ValueError("value is too complex to check safely")
    return expression


def _strip_variable_prefix(claim: str) -> str:
    """`x = 3` carries the same value as `3`; compare the value either way."""
    if claim.count("=") == 1:
        left, right = claim.split("=", 1)
        if re.fullmatch(r"\s*[a-zA-Z][a-zA-Z0-9_]{0,2}\s*", left):
            return right
        if re.fullmatch(r"\s*[a-zA-Z][a-zA-Z0-9_]{0,2}\s*", right):
            return left
    return claim


def _parse_claims(raw: str) -> list[sympy.Expr]:
    """Split an answer into the values it asserts, as an unordered collection."""
    normalized = _normalize(raw)
    if not normalized:
        raise ValueError("empty answer")
    pieces = [piece for piece in _CLAIM_SEPARATOR.split(normalized) if piece.strip()]
    if not pieces:
        raise ValueError("empty answer")
    if len(pieces) > _MAX_CLAIMS:
        raise ValueError("too many values to check safely")
    return [_parse_value(_strip_variable_prefix(piece)) for piece in pieces]


def _values_equal(left: sympy.Expr, right: sympy.Expr) -> bool:
    difference = sympy.simplify(left - right)
    if difference == 0:
        return True
    # `simplify` leaves some equal radicals and rationals in a non-zero form.
    try:
        numeric = complex(sympy.N(difference, 30))
    except (TypeError, ValueError):
        return False
    return abs(numeric) < 1e-12


def _matches_as_set(submitted: list[sympy.Expr], expected: list[sympy.Expr]) -> bool:
    """Every expected value is claimed exactly once, and nothing extra is."""
    if len(submitted) != len(expected):
        return False
    remaining = list(submitted)
    for value in expected:
        for index, candidate in enumerate(remaining):
            if _values_equal(candidate, value):
                remaining.pop(index)
                break
        else:
            return False
    return not remaining


def answers_equivalent(submitted: str, expected: str) -> EquivalenceResult:
    """Compare a student's answer with the expected one.

    A `cannot_verify` status means the comparison could not be made and the
    caller must not read it as a wrong answer.
    """
    try:
        expected_values = _parse_claims(expected)
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError, AttributeError) as exc:
        return EquivalenceResult(False, "cannot_verify", f"expected answer unreadable: {exc}")
    except Exception as exc:  # SymPy raises assorted parser errors
        return EquivalenceResult(False, "cannot_verify", f"expected answer unreadable: {exc}")

    try:
        submitted_values = _parse_claims(submitted)
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError, AttributeError) as exc:
        return EquivalenceResult(False, "cannot_verify", f"submitted answer unreadable: {exc}")
    except Exception as exc:
        return EquivalenceResult(False, "cannot_verify", f"submitted answer unreadable: {exc}")

    try:
        if _matches_as_set(submitted_values, expected_values):
            return EquivalenceResult(True, "equivalent", "values match after simplification")
    except Exception as exc:
        return EquivalenceResult(False, "cannot_verify", f"comparison failed: {exc}")

    return EquivalenceResult(False, "different", "values are not mathematically equal")


def describe_for_audit(result: EquivalenceResult) -> dict[str, Optional[str]]:
    """Content-free record for the admin review queue."""
    return {
        "method": "sympy_answer_equivalence",
        "status": result.status,
        "detail": result.detail,
    }
