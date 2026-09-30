"""Derive a drawable graph from a problem, for the board to sketch.

Every deterministic solver wrote prose and algebra and nothing else, so a
student asking to sketch a parabola got ten lines of text. The client could
always draw graphs; nothing upstream ever sent one.

What the client can draw is specific, and this module is written against it
rather than against the contract's full generality. `board_element_renderer`
plots `function_expression` only when it parses as a quadratic or a line, in a
strict grammar: lowercase, no spaces, no `y=` prefix, `x^2` not `x**2`. It
plots `points` unconditionally. So a parabola is sent as an expression the
painter evaluates at 80 samples, and anything richer is sent as points the
painter can always draw. Sending a cubic as an expression would be silently
dropped, which is worse than sending samples.
"""

from __future__ import annotations

import math
import re
from typing import Any

import sympy

# The contract rejects coordinates beyond this, and a window this wide is
# unreadable on a phone anyway.
_MAX_COORDINATE = 1000.0

# Sampling density for curves the painter cannot parse. The painter itself
# draws 80 segments from an expression; matching that keeps a sampled curve
# looking like a drawn one rather than a dotted one.
_SAMPLE_COUNT = 48

# The board action's graph spec caps points at 80 where the teaching-plan
# contract allows 100. One payload has to satisfy both models, so the lower
# cap wins and `labels` -- which only the contract defines -- is left out.
_MAX_POINTS = 80

_X = sympy.Symbol("x")

# Only these reach sympy. Anything else is a sentence, not a function, and
# guessing at it is how a tutor ends up drawing something it did not mean.
_ALLOWED = re.compile(r"^[0-9xX\s+\-*/^().,]+$")


def graph_for_expression(
    expression: str, *, focus: float | None = None
) -> dict[str, Any] | None:
    """A graph payload for `expression`, or None if it is not worth drawing.

    `focus` is an x value the lesson is about -- the point a limit approaches,
    say. Without it the window is built from the curve's own features, which
    for (x^2-4)/(x-2) means centring on the root at x = -2 and cropping out
    the x = 2 the student is actually asking about.
    """
    parsed = _parse(expression)
    if parsed is None:
        return None
    if _X not in parsed.free_symbols:
        # A constant is a horizontal line; there is nothing to learn from it.
        return None

    window = _window_for(parsed, focus=focus)
    if window is None:
        return None
    x_min, x_max, y_min, y_max = window

    payload: dict[str, Any] = {
        "x_min": x_min,
        "x_max": x_max,
        "y_min": y_min,
        "y_max": y_max,
        "points": [],
    }

    drawable = _client_grammar(parsed)
    if drawable is not None:
        payload["function_expression"] = drawable
        payload["points"] = _real_roots(parsed, x_min, x_max)
    else:
        payload["points"] = _samples(parsed, x_min, x_max, y_min, y_max)
        if not payload["points"]:
            return None
    return payload


def graph_for_problem(problem_text: str) -> dict[str, Any] | None:
    """A graph for whatever a problem is about, if it is about something.

    An explicit function of x wins: "solve x^2 - 5x + 6 = 0" is a parabola,
    not a journey. Failing that, a constant-acceleration question is drawn as
    a velocity-time line, which is what makes the graph appear whether the
    physics solver or the generic one ends up answering it.
    """
    for candidate in _candidate_expressions(problem_text):
        graph = graph_for_expression(candidate)
        if graph is not None:
            return graph
    return _kinematics_graph(problem_text)


def _kinematics_graph(problem_text: str) -> dict[str, Any] | None:
    """A velocity-time line if this reads as constant-acceleration motion.

    The physics parser is imported here rather than at module scope: it
    imports the solver stack, which imports this module, and a cycle at import
    time would take the service down rather than lose a graph.
    """
    try:
        from api.services.visual_tutor.physics_kinematics import (
            parse_physics_kinematics_problem,
        )
    except ImportError:  # pragma: no cover - only if the module is removed
        return None
    try:
        problem = parse_physics_kinematics_problem(problem_text or "")
    except Exception:  # pragma: no cover - a parse failure is not a graph
        return None
    if problem is None:
        return None
    knowns = problem.knowns or {}
    return velocity_time_graph(
        initial_velocity=knowns.get("u", 0.0),
        acceleration=knowns.get("a", 0.0),
        duration=knowns.get("t", 0.0),
    )


def _parse(expression: str) -> sympy.Expr | None:
    text = (expression or "").strip()
    if not text or len(text) > 200:
        return None
    text = re.sub(r"(?i)^y\s*=\s*", "", text)
    if not _ALLOWED.match(text):
        return None
    # A student writes 5x and 3(x+1); sympy needs the multiplication spelled
    # out. This runs before ^ is rewritten so it cannot see the ** it creates.
    text = re.sub(r"(?<=[0-9])(?=[xX(])", "*", text)
    text = re.sub(r"(?<=[xX)])(?=[0-9(])", "*", text)
    # `^` means exponent to a student and xor to Python.
    text = text.replace("^", "**")
    try:
        parsed = sympy.sympify(text, locals={"x": _X}, evaluate=True)
    except (sympy.SympifyError, SyntaxError, TypeError, ValueError, AttributeError):
        return None
    if not isinstance(parsed, sympy.Expr):
        return None
    if parsed.free_symbols - {_X}:
        # Another letter means this is not a single-variable function of x.
        return None
    return parsed


def _client_grammar(parsed: sympy.Expr) -> str | None:
    """`parsed` written the way board_element_renderer parses it, or None.

    Only a polynomial of degree 1 or 2 qualifies. Anything else is returned as
    None so the caller sends points instead of an expression the painter would
    quietly refuse to draw.
    """
    try:
        poly = sympy.Poly(parsed, _X)
    except (sympy.PolynomialError, sympy.GeneratorsNeeded):
        return None
    degree = poly.degree()
    if degree not in (1, 2):
        return None

    coefficients = [float(c) for c in poly.all_coeffs()]
    if any(not math.isfinite(c) for c in coefficients):
        return None

    def term(coefficient: float, suffix: str, *, leading: bool) -> str:
        if coefficient == 0:
            return ""
        magnitude = abs(coefficient)
        # The grammar takes an integer or decimal, and an implicit 1 before x.
        if suffix and magnitude == 1:
            body = ""
        elif magnitude == int(magnitude):
            body = str(int(magnitude))
        else:
            body = f"{magnitude:g}"
        sign = "-" if coefficient < 0 else ("" if leading else "+")
        return f"{sign}{body}{suffix}"

    if degree == 2:
        a, b, c = coefficients
        text = term(a, "x^2", leading=True) + term(b, "x", leading=False) + term(
            c, "", leading=False
        )
    else:
        b, c = coefficients
        text = term(b, "x", leading=True) + term(c, "", leading=False)
    return text or None


def _real_roots(parsed: sympy.Expr, x_min: float, x_max: float) -> list[dict[str, float]]:
    """Where the curve crosses the axis, which is what the algebra just found."""
    try:
        roots = sympy.solve(sympy.Eq(parsed, 0), _X)
    except Exception:  # pragma: no cover - sympy raises many shapes here
        return []
    points: list[dict[str, float]] = []
    for root in roots:
        if not root.is_real:
            continue
        value = float(root)
        if x_min <= value <= x_max and abs(value) <= _MAX_COORDINATE:
            points.append({"x": round(value, 6), "y": 0.0})
    return points[:10]


def _samples(
    parsed: sympy.Expr, x_min: float, x_max: float, y_min: float, y_max: float
) -> list[dict[str, float]]:
    """The curve as points, for anything the painter cannot parse."""
    function = sympy.lambdify(_X, parsed, "math")
    points: list[dict[str, float]] = []
    for index in range(_SAMPLE_COUNT + 1):
        x = x_min + (x_max - x_min) * index / _SAMPLE_COUNT
        y = _evaluate(function, x)
        # A hole or an asymptote is skipped rather than drawn as a spike.
        if y is None or not (y_min <= y <= y_max):
            continue
        points.append({"x": round(x, 6), "y": round(y, 6)})
    return points[:_MAX_POINTS]


def _evaluate(function: Any, x: float) -> float | None:
    try:
        y = float(function(x))
    except (ArithmeticError, TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(y) or abs(y) > _MAX_COORDINATE:
        return None
    return y


def _window_for(
    parsed: sympy.Expr, *, focus: float | None = None
) -> tuple[float, float, float, float] | None:
    """An x/y window that actually contains the interesting part of the curve.

    A fixed window crops the roots off a parabola as often as not, so the
    window is built around the features the lesson is about -- the roots and
    the turning point -- and then padded.
    """
    interesting: list[float] = []
    try:
        for root in sympy.solve(sympy.Eq(parsed, 0), _X):
            if root.is_real and abs(float(root)) <= _MAX_COORDINATE:
                interesting.append(float(root))
    except Exception:  # pragma: no cover
        pass
    try:
        for critical in sympy.solve(sympy.diff(parsed, _X), _X):
            if critical.is_real and abs(float(critical)) <= _MAX_COORDINATE:
                interesting.append(float(critical))
    except Exception:  # pragma: no cover
        pass

    if focus is not None and math.isfinite(focus) and abs(focus) <= _MAX_COORDINATE:
        # Whatever else the curve does, the point under discussion has to be
        # on screen, with room either side to see the approach.
        interesting.append(focus)
    if interesting:
        low, high = min(interesting), max(interesting)
        span = max(high - low, 2.0)
        x_min, x_max = low - span * 0.6, high + span * 0.6
    else:
        x_min, x_max = -6.0, 6.0

    x_min = max(-_MAX_COORDINATE, round(x_min, 3))
    x_max = min(_MAX_COORDINATE, round(x_max, 3))
    if x_min >= x_max:
        return None

    function = sympy.lambdify(_X, parsed, "math")
    ys = [
        y
        for y in (
            _evaluate(function, x_min + (x_max - x_min) * i / 60) for i in range(61)
        )
        if y is not None
    ]
    if not ys:
        return None
    low_y, high_y = min(ys), max(ys)
    if high_y - low_y < 1e-6:
        low_y, high_y = low_y - 1.0, high_y + 1.0
    pad = (high_y - low_y) * 0.2
    y_min = max(-_MAX_COORDINATE, round(low_y - pad, 3))
    y_max = min(_MAX_COORDINATE, round(high_y + pad, 3))
    if y_min >= y_max:
        return None
    return x_min, x_max, y_min, y_max


def _candidate_expressions(problem_text: str) -> list[str]:
    """Expressions worth trying to draw, best first.

    A problem is a sentence, not an expression, so this pulls out the parts
    that look like one: the body of `y = ...`, either side of an equation, and
    any bracketed or algebraic run containing an x.
    """
    text = (problem_text or "").strip()
    if not text or len(text) > 500:
        return []
    candidates: list[str] = []

    def offer(value: str) -> None:
        value = value.strip().strip(".,;:")
        if value and value not in candidates and "x" in value.lower():
            candidates.append(value)

    # "y = x^2 - 4" and "f(x) = ..." state the function outright.
    for match in re.finditer(r"(?i)\b(?:y|f\s*\(\s*x\s*\))\s*=\s*([^,;.]+)", text):
        offer(match.group(1))

    # "x^2 - 5x + 6 = 0" is a function set to a value; the left side is the curve.
    for match in re.finditer(r"([0-9xX\s+\-*/^().]+?)\s*=\s*([0-9xX\s+\-*/^().]+)", text):
        left, right = match.group(1), match.group(2)
        if not left.strip() or not right.strip():
            continue
        if right.strip() in {"0", "0.0"}:
            offer(left)
        else:
            offer(f"({left})-({right})")

    # Otherwise the longest algebraic run is the best guess available.
    for run in sorted(
        re.findall(r"[0-9xX+\-*/^().]{3,}", text), key=len, reverse=True
    ):
        offer(run)

    return candidates[:6]


def velocity_time_graph(
    *, initial_velocity: float, acceleration: float, duration: float
) -> dict[str, Any] | None:
    """A velocity-time graph for constant acceleration, or None.

    v(t) = u + at is a straight line, which is one of the two shapes the
    client can evaluate from an expression, so kinematics gets a real drawn
    line rather than sampled points. Constant velocity is refused: a flat line
    tells a student nothing the number above it did not.
    """
    values = (initial_velocity, acceleration, duration)
    if any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
        return None
    if duration <= 0 or acceleration == 0:
        return None
    if any(abs(v) > _MAX_COORDINATE for v in values):
        return None

    # The window spans the motion described, with a little air either side so
    # the line does not start and stop flush against the axes.
    pad = duration * 0.15
    x_min, x_max = -pad, duration + pad
    end_velocity = initial_velocity + acceleration * duration
    low, high = sorted((initial_velocity, end_velocity))
    if high - low < 1e-6:
        low, high = low - 1.0, high + 1.0
    y_pad = (high - low) * 0.2
    # Zero is kept on screen: where the line crosses it is the moment the
    # object stops, which is usually the point of a braking question.
    y_min = min(low - y_pad, 0.0)
    y_max = max(high + y_pad, 0.0)
    if y_min >= y_max:
        return None

    expression = _client_grammar(
        sympy.sympify(initial_velocity) + sympy.sympify(acceleration) * _X
    )
    if expression is None:
        return None

    return {
        "x_min": round(x_min, 3),
        "x_max": round(x_max, 3),
        "y_min": round(y_min, 3),
        "y_max": round(y_max, 3),
        # x_label/y_label exist on the board spec but not on the teaching-plan
        # contract, and physics validates against both, so the axes keep their
        # default names rather than making the payload valid in only one place.
        "function_expression": expression,
        "points": [
            {"x": 0.0, "y": round(float(initial_velocity), 6)},
            {"x": round(float(duration), 6), "y": round(float(end_velocity), 6)},
        ],
    }
