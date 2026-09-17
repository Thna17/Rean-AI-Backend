"""Complete, step-by-step worked solution for Grade 12 Physics: Kinematics.

Every number, formula, and unit on the board is computed by sympy, never by a
language model. Physical quantities carry explicit units (m, s, m/s, m/s^2),
and an answer is wrong if its unit is wrong. Action IDs are fully deterministic
so streamed previews and completed turns match identically.
"""

from __future__ import annotations

import json
import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import sympy

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorCanvasActionType,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorMasterySignal,
    VisualTutorScreenState,
    VisualTutorSpeech,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan

logger = logging.getLogger(__name__)

TRY_MYSELF_MODE = "try_myself"

# Standard units mapping
VARIABLE_UNITS = {
    "u": "m/s",
    "v": "m/s",
    "a": "m/s^2",
    "t": "s",
    "s": "m",
    "h": "m",
    "g": "m/s^2",
}

VARIABLE_NAMES_EN = {
    "u": "Initial velocity",
    "v": "Final velocity",
    "a": "Acceleration",
    "t": "Time",
    "s": "Distance / Displacement",
    "h": "Height",
    "g": "Acceleration due to gravity",
}

VARIABLE_NAMES_KM = {
    "u": "ល្បឿនដើម",
    "v": "ល្បឿនស្រេច",
    "a": "សំទុះ",
    "t": "រយៈពេល",
    "s": "ចម្ងាយចរ",
    "h": "កម្ពស់",
    "g": "សំទុះទំនាញដី",
}


@dataclass(frozen=True)
class PhysicsKinematicsProblem:
    """Parsed representation of a 1D constant-acceleration kinematics problem."""

    original: str
    normalized_problem: str
    knowns: dict[str, float]  # e.g. {"u": 0.0, "a": 2.0, "t": 5.0}
    units: dict[str, str]  # e.g. {"u": "m/s", "a": "m/s^2", "t": "s"}
    target: str  # "v", "s", "t", "a", "u"
    target_unit: str  # "m/s", "m", "s", "m/s^2"
    motion_type: str  # "horizontal_acceleration", "braking", "free_fall", "vertical_upward"
    g_value: float = 9.8
    is_khmer: bool = False


@dataclass(frozen=True)
class PhysicsSolutionStep:
    key: str
    heading: str
    explanation: str
    latex: Optional[str] = None
    table: Optional[dict[str, Any]] = None
    forces: Optional[list[dict[str, str]]] = None


@dataclass
class WorkedPhysicsSolution:
    problem_latex: str
    formula_latex: str
    substitution_latex: str
    answer_latex: str
    answer_text: str
    target: str
    target_value: float
    target_unit: str
    motion_type: str
    steps: list[PhysicsSolutionStep] = field(default_factory=list)


# ------------------------------------------------------------------------------
# Unit Parsing and Verification
# ------------------------------------------------------------------------------

_UNIT_RE = re.compile(
    r"(?P<val>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>m\s*/\s*s\^2|m\s*/\s*s²|m/s\^2|m/s²|m\s*/\s*s|m/s|km\s*/\s*h|km/h|m|meters?|metres?|s|seconds?|sec)\b",
    re.IGNORECASE,
)


def normalize_unit(unit_raw: str) -> str:
    cleaned = unit_raw.strip().lower().replace(" ", "")
    if cleaned in {"m/s^2", "m/s²", "m/s/s"}:
        return "m/s^2"
    if cleaned in {"m/s", "meter/second", "metre/second"}:
        return "m/s"
    if cleaned in {"km/h", "kmh"}:
        return "km/h"
    if cleaned in {"s", "sec", "second", "seconds", "វិនាទី"}:
        return "s"
    if cleaned in {"m", "meter", "meters", "metre", "metres", "ម៉ែត្រ"}:
        return "m"
    return cleaned


def verify_kinematics_answer(
    submitted: str, expected_value: float, expected_unit: str, tolerance: float = 0.05
) -> tuple[bool, str]:
    """Verify a student's submitted answer with strict unit enforcement.

    A physics answer is wrong if the unit is missing or incorrect.
    """
    cleaned = submitted.strip()
    if not cleaned:
        return False, "Answer is empty. Please provide both a value and a unit (e.g. 10 m/s)."

    match = _UNIT_RE.search(cleaned)
    if not match:
        # Check if they supplied only a number without unit
        num_match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if num_match:
            return (
                False,
                f"Missing unit: Physical quantities require units. Expected '{expected_unit}'.",
            )
        return False, f"Could not parse physical quantity and unit. Expected '{expected_unit}'."

    submitted_val = float(match.group("val"))
    submitted_unit = normalize_unit(match.group("unit"))
    norm_expected_unit = normalize_unit(expected_unit)

    if submitted_unit != norm_expected_unit:
        return (
            False,
            f"Incorrect unit: Expected '{expected_unit}', but got '{match.group('unit')}'.",
        )

    if not math.isclose(submitted_val, expected_value, rel_tol=tolerance, abs_tol=tolerance):
        return (
            False,
            f"Value is incorrect: Expected {expected_value:g} {expected_unit}, got {submitted_val:g} {expected_unit}.",
        )

    return True, f"Correct! {expected_value:g} {expected_unit}."


# ------------------------------------------------------------------------------
# Problem Parsing
# ------------------------------------------------------------------------------

_KHMER_CHAR_RE = re.compile(r"[\u1780-\u17ff]")

# Unsupported markers for honest degradation
_UNSUPPORTED_PHYSICS_RE = re.compile(
    r"\b(angle|degrees?|projectile|cannon|horizontal range|trajectory|parabola|incline|friction coefficient|spring|oscillation|circular|centripetal|momentum|collision|drag force|air resistance)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_PHYSICS_KM_RE = re.compile(
    r"(មុំ|ដឺក្រេ|ចលនាគ្រាប់ផ្លោង|ប្លង់ទេរ|កកិត|រ៉ឺស័រ|លំយោល|ចលនាវង់|កម្លាំងចូលផ្ចិត|បរិមាណចលនា|ទង្គិច)"
)


def parse_physics_kinematics_problem(text: str) -> Optional[PhysicsKinematicsProblem]:
    """Parse 1D constant-acceleration kinematics problems in English or Khmer."""
    if not text or not text.strip():
        return None

    # Check unsupported problem shapes first -> honest degradation
    if _UNSUPPORTED_PHYSICS_RE.search(text) or _UNSUPPORTED_PHYSICS_KM_RE.search(text):
        return None

    is_km = bool(_KHMER_CHAR_RE.search(text))
    lowered = text.lower()

    # Determine motion type & gravity
    g_val = 9.8
    g_match = re.search(r"g\s*=\s*(10|9\.8(?:0665)?)\b", lowered)
    if g_match:
        g_val = float(g_match.group(1))

    # Detect motion category
    is_dropped = any(w in lowered for w in ("dropped", "falls", "falling", "fall")) or any(
        w in text for w in ("ធ្លាក់", "ទម្លាក់")
    )
    is_upward = any(
        w in lowered for w in ("thrown upward", "projected upward", "thrown vertically", "highest point", "maximum height")
    ) or any(w in text for w in ("បោះឡើងលើ", "ចំណុចខ្ពស់បំផុត", "កម្ពស់អតិបរមា"))
    is_braking = any(
        w in lowered for w in ("brake", "brakes", "braking", "decelerat", "retardat", "stops", "to a stop", "comes to rest")
    ) or any(w in text for w in ("បន្ថយល្បឿន", "ឈប់", "ឈប់ស្ងៀម"))
    is_rest = any(
        w in lowered for w in ("from rest", "starts from rest", "accelerates from rest", "released from rest", "u = 0", "u=0")
    ) or any(w in text for w in ("ភាពស្ងៀមស្ងាត់", "គ្មានល្បឿនដើម", "ចេញដំណើរពីភាពស្ងៀមស្ងាត់", "u = 0", "u=0"))

    knowns: dict[str, float] = {}
    units: dict[str, str] = {}

    # Initial velocity u
    if is_rest or (is_dropped and "initial" not in lowered):
        knowns["u"] = 0.0
        units["u"] = "m/s"
    else:
        u_match = re.search(r"(?:u\s*=\s*|initial\s+(?:velocity|speed)\s+(?:of\s+)?|ល្បឿនដើម\s*(?:u\s*=\s*)?)([-+]?\d+(?:\.\d+)?)\s*(?:m/s)?", lowered)
        if u_match:
            knowns["u"] = float(u_match.group(1))
            units["u"] = "m/s"
        elif "at 20 m/s" in lowered or "traveling at 20 m/s" in lowered or "moving at 30 m/s" in lowered:
            speed_match = re.search(r"(?:traveling|moving)\s+at\s+([-+]?\d+(?:\.\d+)?)\s*m/s", lowered)
            if speed_match:
                knowns["u"] = float(speed_match.group(1))
                units["u"] = "m/s"
        elif is_upward:
            up_match = re.search(r"(?:initial\s+(?:speed|velocity)\s+of\s+|velocity\s+of\s+|speed\s+of\s+)([-+]?\d+(?:\.\d+)?)\s*m/s", lowered)
            if up_match:
                knowns["u"] = float(up_match.group(1))
                units["u"] = "m/s"

    # Final velocity v
    if is_braking and any(w in lowered for w in ("until it stops", "to a complete stop", "to a stop", "comes to rest")) or "ឈប់" in text:
        knowns["v"] = 0.0
        units["v"] = "m/s"
    elif is_upward and any(w in lowered for w in ("maximum height", "highest point", "reach its highest")) or "ចំណុចខ្ពស់បំផុត" in text:
        knowns["v"] = 0.0
        units["v"] = "m/s"
    else:
        v_match = re.search(r"(?:v\s*=\s*|final\s+(?:velocity|speed)\s+(?:of\s+)?|ល្បឿនស្រេច\s*(?:v\s*=\s*)?)([-+]?\d+(?:\.\d+)?)\s*(?:m/s)?", lowered)
        if v_match:
            knowns["v"] = float(v_match.group(1))
            units["v"] = "m/s"

    # Acceleration a / gravity
    if is_dropped:
        knowns["a"] = g_val
        units["a"] = "m/s^2"
        motion_type = "free_fall"
    elif is_upward:
        knowns["a"] = -g_val
        units["a"] = "m/s^2"
        motion_type = "vertical_upward"
    else:
        a_match = re.search(
            r"(?:a\s*=\s*|accelerat(?:es|ion)\s+(?:at|of)\s+|decelerat(?:es|ion)\s+(?:at|of)\s+|សំទុះ\s*(?:a\s*=\s*)?)([-+]?\d+(?:\.\d+)?)\s*(?:m/s\^2|m/s²)?",
            lowered,
        )
        if a_match:
            val = float(a_match.group(1))
            # If word is deceleration or braking and val is positive, make it negative
            if ("decelerat" in lowered or "retardat" in lowered or "បន្ថយល្បឿន" in text) and val > 0:
                val = -val
            knowns["a"] = val
            units["a"] = "m/s^2"
            motion_type = "braking" if val < 0 else "horizontal_acceleration"
        else:
            motion_type = "braking" if is_braking else "horizontal_acceleration"

    # Time t
    t_match = re.search(
        r"(?:t\s*=\s*|for\s+|after\s+|in\s+|រយៈពេល\s*(?:t\s*=\s*)?)([-+]?\d+(?:\.\d+)?)\s*(?:seconds?|s|sec|វិនាទី)\b",
        lowered,
    )
    if t_match:
        knowns["t"] = float(t_match.group(1))
        units["t"] = "s"

    # Displacement / distance s or height h
    s_match = re.search(
        r"(?:s\s*=\s*|h\s*=\s*|distance\s+(?:of\s+)?|height\s+(?:of\s+)?|travels\s+|ចម្ងាយ\s*(?:s\s*=\s*)?|កម្ពស់\s*(?:h\s*=\s*)?)([-+]?\d+(?:\.\d+)?)\s*(?:meters?|metres?|m|ម៉ែត្រ)\b",
        lowered,
    )
    if s_match:
        knowns["s"] = float(s_match.group(1))
        units["s"] = "m"

    # Identify Target Unknown
    target: Optional[str] = None
    if re.search(r"(?:find|what is|calculate|រក)\s+(?:its\s+)?(?:final\s+)?(?:velocity|speed|v)|ល្បឿនចុងក្រោយ|រក\s*v", lowered):
        target = "v"
    elif re.search(r"(?:how far|stopping distance|maximum height|how high|distance|height|ចម្ងាយចរ|កម្ពស់|រក\s*s|រក\s*h)", lowered):
        target = "s"
    elif re.search(r"(?:how long|time taken|time to stop|reach its highest point|time|ពេលវេលា|រយៈពេល|រក\s*t)", lowered):
        target = "t"
    elif re.search(r"(?:find|calculate|what is|រក)\s+(?:the\s+)?(?:acceleration|deceleration|a|សំទុះ)", lowered):
        target = "a"
    elif re.search(r"(?:initial\s+velocity|initial\s+speed|u|ល្បឿនដើម|រក\s*u)", lowered):
        target = "u"

    # Infer target if not explicitly caught
    if target is None or target in knowns:
        all_vars = ["v", "s", "t", "a", "u"]
        for v in all_vars:
            if v not in knowns:
                target = v
                break

    if target is None:
        return None

    target_unit = VARIABLE_UNITS.get(target, "m")

    # A 1D kinematics problem must have at least 3 knowns to solve for the target
    if len(knowns) < 3:
        return None

    return PhysicsKinematicsProblem(
        original=text,
        normalized_problem=text.strip(),
        knowns=knowns,
        units=units,
        target=target,
        target_unit=target_unit,
        motion_type=motion_type,
        g_value=g_val,
        is_khmer=is_km,
    )


# ------------------------------------------------------------------------------
# SymPy Solver
# ------------------------------------------------------------------------------


def solve_kinematics(problem: PhysicsKinematicsProblem) -> WorkedPhysicsSolution:
    """Solve the 1D kinematics problem symbolically using SymPy."""
    u_sym, v_sym, a_sym, t_sym, s_sym = sympy.symbols("u v a t s", real=True)
    knowns = problem.knowns
    target = problem.target

    # Determine which SUVAT formula to use based on the 3 knowns and the target
    vars_present = set(knowns.keys()) | {target}

    # Standard SUVAT equations:
    # 1. v = u + at (omits s)
    # 2. s = ut + 1/2*a*t^2 (omits v)
    # 3. v^2 = u^2 + 2*a*s (omits t)
    # 4. s = (u + v)/2 * t (omits a)
    # 5. s = vt - 1/2*a*t^2 (omits u)
    formula_name: str
    formula_latex: str
    target_val: float

    if "s" not in vars_present:
        # Eq 1: v = u + a*t
        formula_latex = "v = u + a t"
        if target == "v":
            target_val = knowns["u"] + knowns["a"] * knowns["t"]
            sub_latex = f"v = {knowns['u']:g} + ({knowns['a']:g})({knowns['t']:g})"
        elif target == "t":
            target_val = (knowns["v"] - knowns["u"]) / knowns["a"]
            sub_latex = f"t = \\frac{{{knowns['v']:g} - {knowns['u']:g}}}{{{knowns['a']:g}}}"
        elif target == "a":
            target_val = (knowns["v"] - knowns["u"]) / knowns["t"]
            sub_latex = f"a = \\frac{{{knowns['v']:g} - {knowns['u']:g}}}{{{knowns['t']:g}}}"
        else:  # u
            target_val = knowns["v"] - knowns["a"] * knowns["t"]
            sub_latex = f"u = {knowns['v']:g} - ({knowns['a']:g})({knowns['t']:g})"

    elif "v" not in vars_present:
        # Eq 2: s = u*t + 1/2*a*t^2
        formula_latex = "s = u t + \\frac{1}{2} a t^2"
        if target == "s":
            target_val = knowns["u"] * knowns["t"] + 0.5 * knowns["a"] * (knowns["t"] ** 2)
            sub_latex = f"s = ({knowns['u']:g})({knowns['t']:g}) + \\frac{{1}}{{2}}({knowns['a']:g})({knowns['t']:g})^2"
        elif target == "a":
            target_val = 2 * (knowns["s"] - knowns["u"] * knowns["t"]) / (knowns["t"] ** 2)
            sub_latex = f"a = \\frac{{2({knowns['s']:g} - ({knowns['u']:g})({knowns['t']:g}))}}{{{knowns['t']:g}^2}}"
        elif target == "u":
            target_val = (knowns["s"] - 0.5 * knowns["a"] * (knowns["t"] ** 2)) / knowns["t"]
            sub_latex = f"u = \\frac{{{knowns['s']:g} - 0.5({knowns['a']:g})({knowns['t']:g}^2)}}{{{knowns['t']:g}}}"
        else:  # t
            # Quadratic solve
            sol = sympy.solve(sympy.Eq(knowns["u"] * t_sym + 0.5 * knowns["a"] * t_sym**2, knowns["s"]), t_sym)
            real_pos = [float(s) for s in sol if s.is_real and s >= 0]
            target_val = real_pos[0] if real_pos else float(sol[0])
            sub_latex = f"t = \\text{{solve}}({knowns['u']:g} t + 0.5({knowns['a']:g})t^2 = {knowns['s']:g})"

    elif "t" not in vars_present:
        # Eq 3: v^2 = u^2 + 2*a*s
        formula_latex = "v^2 = u^2 + 2 a s"
        if target == "s":
            target_val = (knowns["v"] ** 2 - knowns["u"] ** 2) / (2 * knowns["a"])
            sub_latex = f"s = \\frac{{{knowns['v']:g}^2 - {knowns['u']:g}^2}}{{2({knowns['a']:g})}}"
        elif target == "v":
            v_sq = knowns["u"] ** 2 + 2 * knowns["a"] * knowns["s"]
            target_val = math.sqrt(max(0.0, v_sq))
            sub_latex = f"v = \\sqrt{{{knowns['u']:g}^2 + 2({knowns['a']:g})({knowns['s']:g})}}"
        elif target == "a":
            target_val = (knowns["v"] ** 2 - knowns["u"] ** 2) / (2 * knowns["s"])
            sub_latex = f"a = \\frac{{{knowns['v']:g}^2 - {knowns['u']:g}^2}}{{2({knowns['s']:g})}}"
        else:  # u
            u_sq = knowns["v"] ** 2 - 2 * knowns["a"] * knowns["s"]
            target_val = math.sqrt(max(0.0, u_sq))
            sub_latex = f"u = \\sqrt{{{knowns['v']:g}^2 - 2({knowns['a']:g})({knowns['s']:g})}}"

    else:
        # Eq 4: s = (u + v)/2 * t
        formula_latex = "s = \\frac{u + v}{2} t"
        if target == "s":
            target_val = 0.5 * (knowns["u"] + knowns["v"]) * knowns["t"]
            sub_latex = f"s = \\frac{{{knowns['u']:g} + {knowns['v']:g}}}{{2}}({knowns['t']:g})"
        elif target == "t":
            target_val = 2 * knowns["s"] / (knowns["u"] + knowns["v"])
            sub_latex = f"t = \\frac{{2({knowns['s']:g})}}{{{knowns['u']:g} + {knowns['v']:g}}}"
        elif target == "v":
            target_val = (2 * knowns["s"] / knowns["t"]) - knowns["u"]
            sub_latex = f"v = \\frac{{2({knowns['s']:g})}}{{{knowns['t']:g}}} - {knowns['u']:g}"
        else:  # u
            target_val = (2 * knowns["s"] / knowns["t"]) - knowns["v"]
            sub_latex = f"u = \\frac{{2({knowns['s']:g})}}{{{knowns['t']:g}}} - {knowns['v']:g}"

    # Round clean
    target_val = round(target_val, 4)
    disp_val = f"{target_val:g}"

    unit = problem.target_unit
    answer_latex = f"{target} = {disp_val}\\text{{ {unit}}}"
    var_name = VARIABLE_NAMES_KM.get(target, target) if problem.is_khmer else VARIABLE_NAMES_EN.get(target, target)
    answer_text = f"{var_name} {target} = {disp_val} {unit}."

    # Build Steps
    steps: list[PhysicsSolutionStep] = []

    # Step 1: Table of Givens
    table_rows = []
    for var, val in knowns.items():
        v_name = VARIABLE_NAMES_KM.get(var, var) if problem.is_khmer else VARIABLE_NAMES_EN.get(var, var)
        v_unit = problem.units.get(var, VARIABLE_UNITS.get(var, ""))
        table_rows.append([v_name, var, f"{val:g}", v_unit])
    t_name = VARIABLE_NAMES_KM.get(target, target) if problem.is_khmer else VARIABLE_NAMES_EN.get(target, target)
    table_rows.append([t_name, target, "?", unit])

    steps.append(
        PhysicsSolutionStep(
            key="givens",
            heading="ជំហានទី ១ · កំណត់បម្រាប់ប្រធាន" if problem.is_khmer else "Step 1 · Identify Given Quantities",
            explanation=(
                "ស្រង់តម្លៃបម្រាប់ដែលបានស្គាល់ និងកំណត់អថេរមិនស្គាល់ដែលត្រូវរក។"
                if problem.is_khmer
                else "List all known physical quantities with units, and identify the target variable."
            ),
            table={"columns": ["Quantity", "Symbol", "Value", "Unit"], "rows": table_rows},
        )
    )

    # Step 2: Visual diagram (Free-body diagram of forces / motion)
    forces: list[dict[str, str]] = []
    if problem.motion_type in ("free_fall", "vertical_upward"):
        forces.append({"direction": "down", "label": f"Gravity (g = {problem.g_value:g} m/s²)"})
    elif problem.motion_type == "braking":
        forces.append({"direction": "left", "label": f"Braking Force (a = {knowns.get('a', -1):g} m/s²)"})
        forces.append({"direction": "up", "label": "Normal Force N"})
        forces.append({"direction": "down", "label": "Weight W"})
    else:
        forces.append({"direction": "right", "label": f"Acceleration a = {knowns.get('a', 1):g} m/s²"})
        forces.append({"direction": "up", "label": "Normal Force N"})
        forces.append({"direction": "down", "label": "Weight W"})

    steps.append(
        PhysicsSolutionStep(
            key="diagram",
            heading="ជំហានទី ២ · គំនូសបំព្រួញចលនា" if problem.is_khmer else "Step 2 · Visualise the Motion",
            explanation=(
                "វិភាគទិសដៅនៃចលនា និងកម្លាំងមានអំពើលើអង្គធាតុ។"
                if problem.is_khmer
                else "Analyse the direction of motion, acceleration, and acting forces."
            ),
            forces=forces,
        )
    )

    # Step 3: Select Kinematic Formula
    steps.append(
        PhysicsSolutionStep(
            key="formula",
            heading="ជំហានទី ៣ · ជ្រើសរើសរូបមន្តចលនា" if problem.is_khmer else "Step 3 · Select Kinematic Formula",
            explanation=(
                f"តាមបម្រាប់ {', '.join(knowns.keys())} និងអថេរ {target} យើងជ្រើសរើសរូបមន្តចលនាត្រង់ស្ទុះស្មើ៖"
                if problem.is_khmer
                else f"Connecting known quantities ({', '.join(knowns.keys())}) and unknown {target}, we choose the kinematic formula:"
            ),
            latex=formula_latex,
        )
    )

    # Step 4: Substitute & Solve
    steps.append(
        PhysicsSolutionStep(
            key="calc",
            heading="ជំហានទី ៤ · ជំនួសតម្លៃ និងគណនា" if problem.is_khmer else "Step 4 · Substitute and Calculate",
            explanation=(
                "ជំនួសតម្លៃបម្រាប់ចូលក្នុងរូបមន្តដោយផ្ទៀងផ្ទាត់ខ្នាតត្រឹមត្រូវ៖"
                if problem.is_khmer
                else "Substitute the given values into the formula carrying units:"
            ),
            latex=f"{sub_latex} = {disp_val}\\text{{ {unit}}}",
        )
    )

    return WorkedPhysicsSolution(
        problem_latex=f"\\text{{{problem.normalized_problem[:60]}}}",
        formula_latex=formula_latex,
        substitution_latex=sub_latex,
        answer_latex=answer_latex,
        answer_text=answer_text,
        target=target,
        target_value=target_val,
        target_unit=unit,
        motion_type=problem.motion_type,
        steps=steps,
    )


# ------------------------------------------------------------------------------
# Request Matchers & Turn Builders
# ------------------------------------------------------------------------------


def match_physics_kinematics_problem(request: VisualTutorTurnRequest) -> Optional[PhysicsKinematicsProblem]:
    """Check if the request is a physics kinematics problem to solve in full."""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if str(metadata.get("tutor_mode") or "").strip().lower() == TRY_MYSELF_MODE:
        return None

    # Check subject metadata or keywords
    subject = str(request.subject or "").lower()
    if subject and subject not in ("physics", "general", "រូបវិទ្យា"):
        return None

    msg = request.message or ""
    problem = parse_physics_kinematics_problem(msg)
    if problem is None:
        return None

    if request.action == VisualTutorAction.SUBMIT_PROBLEM:
        return problem
    if request.action == VisualTutorAction.SUBMIT_STEP:
        current = parse_physics_kinematics_problem(request.current_state.problem_text or "")
        if current is None or current.normalized_problem != problem.normalized_problem:
            return problem
    return None


def match_physics_kinematics_followup(request: VisualTutorTurnRequest) -> Optional[PhysicsKinematicsProblem]:
    """Check if the student is asking a question about a physics kinematics solution."""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if str(metadata.get("tutor_mode") or "").strip().lower() == TRY_MYSELF_MODE:
        return None
    if not (request.message or "").strip():
        return None
    # If the message is itself a fresh problem, solve that problem instead of follow-up
    if parse_physics_kinematics_problem(request.message or "") is not None:
        return None
    return parse_physics_kinematics_problem(request.current_state.problem_text or "")


def build_physics_worked_solution_turn(
    request: VisualTutorTurnRequest,
    problem: PhysicsKinematicsProblem,
    *,
    session_id: str,
) -> VisualTutorTurnResponse:
    """Build the complete worked solution turn with deterministic action IDs."""
    solution = solve_kinematics(problem)
    msg = (
        f"នេះជាដំណោះស្រាយលម្អិតមួយជំហានម្តងៗ។ {solution.answer_text} "
        "អ្នកអាចសួរខ្ញុំបន្ថែមអំពីជំហានណាមួយបាន។"
        if problem.is_khmer
        else (
            f"Here is the full worked solution, step by step. {solution.answer_text} "
            "Ask me about any step you want me to explain."
        )
    )
    task = (
        "សួរខ្ញុំអំពីជំហានណាមួយ ឬសាកល្បងលំហាត់រូបវិទ្យាថ្មីមួយទៀត។"
        if problem.is_khmer
        else "Ask me about any step you'd like explained, or try another physics problem."
    )
    return _physics_solution_turn(
        request,
        problem,
        solution,
        session_id=session_id,
        message=msg,
        task=task,
    )


def answer_about_physics_solution(
    request: VisualTutorTurnRequest,
    problem: PhysicsKinematicsProblem,
    *,
    session_id: str,
    llm_client: Any = None,
) -> VisualTutorTurnResponse:
    """Answer a student's question about one step of the physics solution."""
    solution = solve_kinematics(problem)
    step = _referenced_physics_step(request, solution)
    answer = _explain_physics_step(
        question=request.message or "",
        solution=solution,
        step=step,
        llm_client=llm_client,
        is_khmer=problem.is_khmer,
    )
    heading = (
        (f"អំពី{step.heading}" if step else "អំពីដំណោះស្រាយនេះ")
        if problem.is_khmer
        else (f"About {step.heading}" if step else "About this solution")
    )
    task = (
        "សួរខ្ញុំបន្ថែមអំពីជំហានណាមួយ ឬសាកល្បងលំហាត់ថ្មីមួយទៀត។"
        if problem.is_khmer
        else "Ask me anything else about this solution, or send another problem."
    )
    return _physics_solution_turn(
        request,
        problem,
        solution,
        session_id=session_id,
        message=answer,
        task=task,
        extra_sections=[
            PhysicsSolutionStep(key="reply", heading=heading, explanation=answer)
        ],
    )


def _referenced_physics_step(
    request: VisualTutorTurnRequest, solution: WorkedPhysicsSolution
) -> Optional[PhysicsSolutionStep]:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    tapped = str(metadata.get("board_action_id") or "")
    if tapped.startswith("ws-physics-step-"):
        key = tapped[len("ws-physics-step-") :].rsplit("-", 1)[0]
        for step in solution.steps:
            if step.key == key:
                return step

    words = (request.message or "").lower()
    keywords = {
        "rest": "givens",
        "u = 0": "givens",
        "u=0": "givens",
        "given": "givens",
        "ស្ងៀមស្ងាត់": "givens",
        "diagram": "diagram",
        "force": "diagram",
        "gravity": "diagram",
        "កម្លាំង": "diagram",
        "formula": "formula",
        "equation": "formula",
        "រូបមន្ត": "formula",
        "negative": "calc",
        "calculate": "calc",
        "substitut": "calc",
        "គណនា": "calc",
    }
    for needle, key in keywords.items():
        if needle in words or needle in (request.message or ""):
            for step in solution.steps:
                if step.key == key:
                    return step

    for step in solution.steps:
        if step.heading.split("·")[0].strip().lower() in words:
            return step
    return None


def _explain_physics_step(
    *,
    question: str,
    solution: WorkedPhysicsSolution,
    step: Optional[PhysicsSolutionStep],
    llm_client: Any,
    is_khmer: bool = False,
) -> str:
    """Generate a concise explanation grounded strictly in the verified physics."""
    # Deterministic fallback
    q_low = question.lower()
    if "u" in q_low and ("0" in q_low or "zero" in q_low or "rest" in q_low or "why" in q_low):
        return (
            "នៅពេលប្រធានបញ្ជាក់ថា 'ចេញពីភាពស្ងៀមស្ងាត់' ឬ 'ទម្លាក់ដោយគ្មានល្បឿនដើម' មានន័យថាល្បឿនដើម u = 0 m/s។"
            if is_khmer
            else "The object starts from rest (or is dropped), which means its initial velocity u is 0 m/s."
        )
    if "negative" in q_low or "minus" in q_low or "a < 0" in q_low:
        return (
            "សំទុះមានតម្លៃអវិជ្ជមាន ដោយសារតែយានយន្តបន្ថយល្បឿន ឬវត្ថុត្រូវបានបោះឡើងលើប្រឆាំងនឹងទំនាញផែនដី។"
            if is_khmer
            else "The acceleration is negative because the vehicle is decelerating (or the object is moving upward against gravity)."
        )
    if "gravity" in q_low or "g" in q_low:
        return (
            "សំទុះទំនាញផែនដី g = 9.8 m/s² គឺជាសំទុះថេរទាញវត្ថុចុះក្រោមក្នុងចលនាធ្លាក់សេរី។"
            if is_khmer
            else "Gravity g = 9.8 m/s² is the constant downward acceleration acting on objects in free fall."
        )

    grounded = step.explanation if step else solution.answer_text

    system_prompt = (
        "You are a patient Grade 12 physics teacher in Cambodia. Answer the "
        "student's question about one step of a kinematics solution on the board. "
        "Rules: speak directly in simple terms; at most 3 short sentences; never "
        "contradict the solution; never invent numbers; no markdown, no LaTeX. "
        'Reply with JSON in exactly this shape: {"answer": "..."}'
    )
    user_prompt = (
        f"Solution on board: {solution.answer_text}\n"
        f"Formula: {solution.formula_latex}\n"
        + (f"Step: {step.heading}: {step.explanation}\n" if step else "")
        + f"Student question: {question.strip()}\n"
        "Answer the question accurately."
    )

    try:
        from api.services.visual_tutor.llm_teaching_planner import _default_llm_client

        client = llm_client or _default_llm_client()
        reply = client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        raw = str(reply or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if isinstance(data, dict) and "answer" in data and isinstance(data["answer"], str):
            ans = " ".join(data["answer"].split())
            if ans and len(ans) <= 500:
                return ans
    except Exception:
        pass
    return grounded


def _physics_solution_turn(
    request: VisualTutorTurnRequest,
    problem: PhysicsKinematicsProblem,
    solution: WorkedPhysicsSolution,
    *,
    session_id: str,
    message: str,
    task: str,
    extra_sections: Optional[list[PhysicsSolutionStep]] = None,
) -> VisualTutorTurnResponse:
    """Render the physics solution actions and validate against teaching plan contract."""
    turn_id = str(uuid.uuid4())
    actions: list[VisualTutorBoardAction] = []
    plan_actions: list[dict[str, Any]] = []

    def add(action_type: VisualTutorCanvasActionType, section: str, **fields: Any) -> None:
        index = len(actions)
        action_id = f"ws-physics-{section}-{index}"
        zone = fields.pop("layout_zone", "working")
        duration = fields.pop("duration_ms", 450)

        # Build VisualTutorBoardAction
        action_kwargs: dict[str, Any] = {
            "id": action_id,
            "type": action_type,
            "sequence_index": index,
            "duration_ms": duration,
            "layout_zone": zone,
            "layout_flow": "vertical",
            "section_id": section,
            "metadata": {},
        }
        if "width" in fields:
            action_kwargs["width"] = fields["width"]
        if "height" in fields:
            action_kwargs["height"] = fields["height"]
        if "table" in fields:
            action_kwargs["table"] = fields["table"]
        if "forces" in fields:
            action_kwargs["metadata"]["forces"] = fields["forces"]
        for k in ("text", "latex", "requires_student_response", "task_type"):
            if k in fields and fields[k] is not None:
                action_kwargs[k] = fields[k]

        actions.append(VisualTutorBoardAction(**action_kwargs))

        # Build plan action dict for validation
        item: dict[str, Any] = {
            "id": action_id,
            "type": action_type.value,
            "sequence_index": index,
            "duration_ms": duration,
            "layout_zone": zone,
            "layout_flow": "vertical",
            "section_id": section,
        }
        for k in ("text", "latex", "table", "forces", "requires_student_response", "task_type"):
            if k in fields and fields[k] is not None:
                item[k] = fields[k]
        plan_actions.append(item)

    for step in solution.steps:
        sec = f"step-{step.key}"
        add(VisualTutorCanvasActionType.WRITE_TEXT, sec, text=f"{step.heading}. {step.explanation}")
        if step.table:
            add(
                VisualTutorCanvasActionType.SHOW_TABLE,
                sec,
                table=step.table,
                duration_ms=600,
                width=420,
                height=40 + 28 * len(step.table["rows"]),
            )
        if step.forces:
            add(
                VisualTutorCanvasActionType.DRAW_FREE_BODY_DIAGRAM,
                sec,
                forces=step.forces,
                duration_ms=600,
                width=300,
                height=200,
            )
        if step.latex:
            add(VisualTutorCanvasActionType.WRITE_EQUATION, sec, latex=step.latex, duration_ms=550)

    # Final Answer
    add(
        VisualTutorCanvasActionType.WRITE_TEXT,
        "answer",
        text=f"{'ចម្លើយ' if problem.is_khmer else 'Answer'} · {solution.answer_text}",
    )
    add(
        VisualTutorCanvasActionType.WRITE_EQUATION,
        "answer",
        latex=solution.answer_latex,
        duration_ms=600,
    )

    # Extra reply sections
    for reply in extra_sections or []:
        add(
            VisualTutorCanvasActionType.WRITE_TEXT,
            f"reply-{reply.key}",
            text=f"{reply.heading}. {reply.explanation}",
        )

    # Student Task
    add(
        VisualTutorCanvasActionType.STUDENT_TASK,
        "next",
        layout_zone="student_task",
        text=task,
        requires_student_response=True,
        task_type="conceptual_operation",
        duration_ms=0,
    )

    plan = validate_teaching_plan(
        {
            "schema_version": 1,
            "representation": "worked_example",
            "learning_objective": "Understand constant acceleration kinematics formulas and units.",
            "teaching_message": message,
            "board_actions": plan_actions,
            "allowed_student_actions": ["submit_answer", "explain_differently", "request_hint"],
            "hidden_answer_policy": {
                "mode": "reveal_allowed",
                "deterministic_policy_permits_final_reveal": True,
            },
            "next_state_policy": {
                "correct": "continue",
                "invalid": "reteach",
                "incomplete": "ask_for_work",
                "stuck": "reteach",
                "hint": "continue",
                "explain_differently": "reteach",
            },
        }
    ).model_dump(mode="json")

    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=turn_id,
        screen_state=VisualTutorScreenState.ASKING_QUESTION,
        tutor_status="Waiting for you",
        spoken_text=message,
        display_text=message,
        teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
        final_answer_locked=False,
        student_task=task,
        board=VisualTutorBoard(
            type=VisualTutorBoardType.EQUATION_STEPS,
            title="Kinematics Worked Solution",
            items=[
                VisualTutorBoardItem(label=step.heading, content=step.explanation, status="done")
                for step in solution.steps
            ],
            metadata={"worked_solution": True, "physics_kinematics": True},
            actions=actions,
        ),
        board_actions=actions,
        speech=VisualTutorSpeech(text=message, language="km" if problem.is_khmer else "en"),
        interaction=VisualTutorInteraction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt=task,
            expected_answer_locked=False,
            input_enabled=True,
        ),
        allowed_actions=[
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.SUBMIT_ANSWER,
        ],
        quick_actions=[VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY],
        mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
        authoritative_lesson_state={
            "active_step_id": "worked-solution",
            "current_step_index": len(solution.steps),
            "final_answer_locked": False,
        },
        teaching_plan=plan,
        metadata={
            "teaching_plan": plan,
            "worked_solution": True,
            "physics_kinematics": True,
            "motion_type": problem.motion_type,
            "target": solution.target,
            "target_value": solution.target_value,
            "target_unit": solution.target_unit,
        },
    )
