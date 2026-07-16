from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction


_MATH_PHYSICS_SUBJECTS = {"math", "mathematics", "physics", "physical", "physic"}
_ANSWER_REQUEST_RE = re.compile(
    r"\b(answer|solve|solution|final|what is|calculate|find|show final)\b",
    re.IGNORECASE,
)
_STEP_SUBMISSION_RE = re.compile(
    r"\b(my step|i tried|i got|next step|subtract|divide|multiply|add|therefore|=)\b",
    re.IGNORECASE,
)
_GUIDED_MODE_RE = re.compile(
    r"\b(guided practice|hint only|one hint|check my step|try myself|next hint)\b",
    re.IGNORECASE,
)
_LINE_EQUATION_RE = re.compile(
    r"\b(equation\s+(?:of\s+)?(?:the\s+)?line|line\s+equation|straight\s+line)\b",
    re.IGNORECASE,
)
_POINT_RE = re.compile(
    r"\b([A-Za-z])\s*\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SocraticContext:
    original_message: str
    enriched_message: str
    subject: str | None
    topic: str | None
    is_socratic: bool
    final_answer_allowed: bool
    verified_ground_truth: str | None = None


def _extract_prefixed_value(message: str, label: str) -> str | None:
    match = re.search(rf"{label}\s*:\s*([^\.\n]+)", message, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip()


def _normalise_subject(subject: str | None) -> str:
    return (subject or "").strip().lower()


def _standardise_digits(message: str) -> str:
    khmer_to_arabic = {
        "០": "0",
        "១": "1",
        "២": "2",
        "៣": "3",
        "៤": "4",
        "៥": "5",
        "៦": "6",
        "៧": "7",
        "៨": "8",
        "៩": "9",
    }
    result = message
    for khmer_digit, arabic_digit in khmer_to_arabic.items():
        result = result.replace(khmer_digit, arabic_digit)
    return result


def _extract_math_expression(message: str) -> str | None:
    standardised = _standardise_digits(message)
    candidates = re.findall(r"[-+*/^().= xX\d]+", standardised)
    candidates = [candidate.strip().replace("^", "**") for candidate in candidates]
    candidates = [
        candidate
        for candidate in candidates
        if any(char.isdigit() for char in candidate)
        and any(operator in candidate for operator in ("+", "-", "*", "/", "="))
    ]
    return max(candidates, key=len) if candidates else None


def _verified_ground_truth(message: str) -> str | None:
    expression = _extract_math_expression(message)
    if not expression:
        return None


def _fraction_from_text(value: str) -> Fraction:
    return Fraction(value)


def _format_number(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _format_signed_term(value: Fraction) -> str:
    if value == 0:
        return ""
    sign = "+" if value > 0 else "-"
    return f" {sign} {_format_number(abs(value))}"


def _format_slope_term(slope: Fraction) -> str:
    if slope == 1:
        return "x"
    if slope == -1:
        return "-x"
    return f"{_format_number(slope)}x"


def _format_point(label: str, x_value: Fraction, y_value: Fraction) -> str:
    return f"{label}({_format_number(x_value)},{_format_number(y_value)})"


def maybe_build_line_equation_response(message: str) -> str | None:
    """Return a deterministic worked solution for two-point line equations.

    This keeps common coordinate-geometry answers accurate and consistently
    formatted instead of relying on model prompt compliance.
    """
    if not _LINE_EQUATION_RE.search(message):
        return None

    points = _POINT_RE.findall(_standardise_digits(message))
    if len(points) < 2:
        return None

    first_label, first_x_raw, first_y_raw = points[0]
    second_label, second_x_raw, second_y_raw = points[1]
    x1 = _fraction_from_text(first_x_raw)
    y1 = _fraction_from_text(first_y_raw)
    x2 = _fraction_from_text(second_x_raw)
    y2 = _fraction_from_text(second_y_raw)

    if x1 == x2:
        return "\n".join(
            [
                "x = constant",
                "",
                "For your problem:",
                f"{_format_point(first_label, x1, y1)} and {_format_point(second_label, x2, y2)}",
                "",
                "Both points have the same x value.",
                "",
                "Final answer:",
                f"x = {_format_number(x1)}",
            ]
        )

    slope = (y1 - y2) / (x1 - x2)
    intercept = y2 - (slope * x2)
    equation = f"y = {_format_slope_term(slope)}{_format_signed_term(intercept)}"

    return "\n".join(
        [
            "y = ax + b",
            "",
            "Here is the equation line where:",
            "- a is the slope",
            "- b is the intercept",
            "- any point is c(x, y)",
            "",
            "Note:",
            "a = (y2 - y1) / (x2 - x1)",
            "",
            "Slope:",
            "It tells the trend of the line.",
            "Does it go downward or upward?",
            "",
            "For your problem:",
            f"{_format_point(first_label, x1, y1)} and {_format_point(second_label, x2, y2)}",
            "",
            "Step 1: Find the slope",
            "a = (y1 - y2) / (x1 - x2)",
            f"a = ({_format_number(y1)} - {_format_number(y2)}) / ({_format_number(x1)} - {_format_number(x2)})",
            f"a = {_format_number(y1 - y2)} / {_format_number(x1 - x2)}",
            f"a = {_format_number(slope)}",
            "",
            "Step 2: Substitute a point into the equation",
            "y = ax + b",
            "",
            "Where:",
            f"a = {_format_number(slope)}",
            f"{_format_point(second_label, x2, y2)} means x = {_format_number(x2)}, y = {_format_number(y2)}",
            "x is the horizontal axis",
            "y is the vertical axis",
            "",
            f"{_format_number(y2)} = {_format_number(slope)}({_format_number(x2)}) + b",
            f"{_format_number(y2)} = {_format_number(slope * x2)} + b",
            f"b = {_format_number(intercept)}",
            "",
            "Step 3: Write the equation",
            equation,
            "",
            "Final answer:",
            equation,
        ]
    )
    try:
        from api.routes.math_verifier import MathQuery, verify_math

        response = verify_math(MathQuery(expression=expression))
        if not response.is_valid:
            return None
        return response.solution or response.simplified
    except Exception:
        return None


def build_socratic_context(
    message: str,
    *,
    subject: str | None = None,
    topic: str | None = None,
    hint_count: int = 0,
    student_submitted_step: bool | None = None,
    allow_final_answer: bool = False,
    guided_mode: bool | None = None,
) -> SocraticContext:
    resolved_subject = subject or _extract_prefixed_value(message, "Subject")
    resolved_topic = topic or _extract_prefixed_value(message, "Topic")
    subject_key = _normalise_subject(resolved_subject)
    is_math_or_physics = subject_key in _MATH_PHYSICS_SUBJECTS
    if not is_math_or_physics:
        return SocraticContext(
            original_message=message,
            enriched_message=message,
            subject=resolved_subject,
            topic=resolved_topic,
            is_socratic=False,
            final_answer_allowed=True,
        )

    submitted_step = (
        bool(_STEP_SUBMISSION_RE.search(message))
        if student_submitted_step is None
        else student_submitted_step
    )
    asks_for_answer = bool(_ANSWER_REQUEST_RE.search(message))
    is_guided_mode = (
        bool(_GUIDED_MODE_RE.search(message)) if guided_mode is None else guided_mode
    )
    final_answer_allowed = (
        not is_guided_mode
        or allow_final_answer
        or submitted_step
        or hint_count >= 3
    )
    ground_truth = _verified_ground_truth(message)

    guard_lines = [
        "",
        "[SYSTEM AI TUTOR RESPONSE STYLE]",
        f"Subject: {resolved_subject or 'Mathematics/Physics'}",
        f"Topic: {resolved_topic or 'General problem solving'}",
        "Use a clear, direct, structured, student-friendly teaching style.",
        "If the student asks in Khmer, answer in natural Khmer.",
        "If the student asks in English but requests Khmer, answer in natural Khmer.",
        "Do not sound like Google Translate; use simple Khmer that students actually use.",
        "Keep math formulas in standard symbols such as x, y, +, -, =.",
        "Do not answer like a generic chatbot.",
        "Do not write long discovery paragraphs with many questions unless the user asks for hints.",
        "For calculation problems, start with the formula, define symbols, show given values, solve step by step, then show the final answer clearly.",
        "For normal math/physics worked solutions, use this exact section schema so the app can render a lesson card:",
        "FORMULA:",
        "[main formula or equation]",
        "SYMBOLS:",
        "- [symbol]: [simple meaning]",
        "GIVEN:",
        "- [value from the problem]",
        "STEPS:",
        "1. [short action]",
        "   equation: [calculation]",
        "2. [short action]",
        "   equation: [calculation]",
        "FINAL:",
        "[final answer only]",
        "If answering in Khmer, use this equivalent schema:",
        "រូបមន្ត:",
        "[រូបមន្ត ឬ សមីការ]",
        "អត្ថន័យនៃនិមិត្តសញ្ញា:",
        "- [និមិត្តសញ្ញា]: [អត្ថន័យខ្លីៗ]",
        "តម្លៃដែលបានផ្តល់:",
        "- [តម្លៃពីលំហាត់]",
        "ដំណោះស្រាយជាជំហានៗ:",
        "1. [ការពន្យល់ខ្លីៗ]",
        "   equation: [ការគណនា]",
        "ចម្លើយចុងក្រោយ:",
        "[ចម្លើយចុងក្រោយ]",
        "Keep lines short and readable on mobile.",
    ]
    if _LINE_EQUATION_RE.search(message):
        guard_lines.extend(
            [
                "",
                "[COORDINATE GEOMETRY LINE FORMAT]",
                "Always use this format for line equation problems:",
                "y = ax + b",
                "Here is the equation line where:",
                "- a is the slope",
                "- b is the intercept",
                "- any point is c(x, y)",
                "Note:",
                "a = (y2 - y1) / (x2 - x1)",
                "Slope:",
                "It tells the trend of the line.",
                "Does it go downward or upward?",
                "For your problem:",
                "[show the given points]",
                "Step 1: Find the slope",
                "a = (y1 - y2) / (x1 - x2)",
                "a = [calculation]",
                "a = [slope]",
                "Step 2: Substitute a point into the equation",
                "y = ax + b",
                "Where:",
                "a = [slope]",
                "point [chosen point] means x = [x value], y = [y value]",
                "[calculation to find b]",
                "Step 3: Write the equation",
                "y = [slope]x + [intercept]",
                "Final answer:",
                "y = [final equation]",
            ]
        )
    if ground_truth:
        guard_lines.append(
            f"Verified ground truth for internal checking only: {ground_truth}."
        )
    if is_guided_mode and asks_for_answer and not final_answer_allowed:
        guard_lines.extend(
            [
                "",
                "[GUIDED PRACTICE LOCK]",
                "The student appears to be asking for a direct/final answer.",
                "Do not reveal the final numerical answer yet.",
                "Give a short guiding hint, identify the operation/concept to try, and ask them to submit one intermediate step.",
            ]
        )
    elif final_answer_allowed:
        guard_lines.extend(
            [
                "",
                "[NORMAL EXPLANATION MODE]",
                "A full worked solution is allowed.",
                "Give the clean step-by-step explanation directly.",
                "End with the final answer clearly.",
            ]
        )

    return SocraticContext(
        original_message=message,
        enriched_message=message + "\n" + "\n".join(guard_lines),
        subject=resolved_subject,
        topic=resolved_topic,
        is_socratic=True,
        final_answer_allowed=final_answer_allowed,
        verified_ground_truth=ground_truth,
    )
