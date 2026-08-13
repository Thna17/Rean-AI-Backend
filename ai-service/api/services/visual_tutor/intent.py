from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
)


@dataclass(frozen=True)
class VisualTutorIntentDetection:
    intent: VisualTutorStudentIntent
    reason: Optional[str] = None


_STUCK_PATTERNS: list[tuple[str, str]] = [
    ("stuck_phrase", r"\bi\s*(?:am|'m)\s+stuck\b"),
    ("stuck_phrase", r"\bstuck\b"),
    ("does_not_understand", r"\bi\s+(?:do\s+not|don't)\s+understand\b"),
    ("help_request", r"\bhelp\s+me\b"),
    ("cannot_solve", r"\bi\s+(?:can\s*not|can't|cannot)\s+solve\b"),
    ("confused", r"\bconfused\b"),
    ("khmer_does_not_understand", r"មិនយល់"),
    ("khmer_help_request", r"ជួយខ្ញុំ"),
    ("khmer_help_request", r"ជួយខ្ញុំផង"),
]

_STUCK_RES = [
    (reason, re.compile(pattern, re.IGNORECASE))
    for reason, pattern in _STUCK_PATTERNS
]
_CLARIFICATION_RE = re.compile(
    r"(?i)\b(?:what\s+does|what\s+is|why|clarify|explain\s+this)\b|តើ|អ្វី"
)
_EXPLAIN_DIFFERENTLY_RE = re.compile(
    r"(?i)\b(?:explain\s+(?:again|differently)|another\s+way|different\s+way)\b"
    r"|ពន្យល់ម្ដងទៀត|ពន្យល់ម្តងទៀត"
)
_HINT_RE = re.compile(r"(?i)\b(?:hint|clue|small\s+help)\b|គន្លឹះ")
_ANSWER_RE = re.compile(
    r"(?i)\b(?:show|give|tell)\s+(?:me\s+)?(?:the\s+)?(?:final\s+)?answer\b"
    r"|\b(?:final\s+answer|answer\s+please)\b|ចម្លើយ"
)
_STEP_RE = re.compile(
    r"(?i)\b(?:i\s+tried|i\s+try|my\s+step|check|is\s+this|i\s+got|i\s+did)\b"
    r"|[-+*/^().\s\dxX]+=[-+*/^().\s\dxX]+"
    r"|(?:m|slope)\s*=?\s*[-+]?\d+(?:/\d+)?(?:\.\d+)?"
)
_MATH_PROBLEM_RE = re.compile(
    r"(?i)\b(?:solve|find|calculate|simplify|equation|slope|through|percent|"
    r"percentage)\b|x\s*(?:\^|\*\*)\s*2|[-+*/^().\s\dxX]+=[-+*/^().\s\dxX]+"
    r"|[A-Z]?\s*\(\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*\)"
    r"|ដោះស្រាយ|រក|គណនា|សមីការ"
)
_NEW_PROBLEM_COMMAND_RE = re.compile(
    r"(?i)\b(?:solve|find|calculate|simplify)\b|ដោះស្រាយ|រក|គណនា"
)

_ACTION_TO_INTENT = {
    VisualTutorAction.SUBMIT_PROBLEM: VisualTutorStudentIntent.NEW_PROBLEM,
    VisualTutorAction.SUBMIT_STEP: VisualTutorStudentIntent.SUBMITTED_STEP,
    VisualTutorAction.REQUEST_HINT: VisualTutorStudentIntent.REQUEST_HINT,
    VisualTutorAction.EXPLAIN_DIFFERENTLY: (
        VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY
    ),
    VisualTutorAction.REQUEST_FINAL_ANSWER: VisualTutorStudentIntent.REQUEST_ANSWER,
    VisualTutorAction.REQUEST_STUCK_HELP: VisualTutorStudentIntent.STUCK,
}


def detect_visual_tutor_student_intent(
    request: VisualTutorTurnRequest,
) -> VisualTutorIntentDetection:
    if request.student_intent is not None:
        if request.student_intent == VisualTutorStudentIntent.STUCK:
            return VisualTutorIntentDetection(
                VisualTutorStudentIntent.STUCK,
                _stuck_reason(request.message) or "client_student_intent",
            )
        return VisualTutorIntentDetection(
            request.student_intent,
            "client_student_intent",
        )

    stuck_reason = _stuck_reason(request.message)
    if request.action == VisualTutorAction.REQUEST_STUCK_HELP or stuck_reason:
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.STUCK,
            stuck_reason or "request_stuck_help_action",
        )

    message = request.message.strip()
    if _EXPLAIN_DIFFERENTLY_RE.search(message):
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
            "explain_differently_phrase",
        )
    if _HINT_RE.search(message):
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.REQUEST_HINT,
            "hint_phrase",
        )
    if _ANSWER_RE.search(message):
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.REQUEST_ANSWER,
            "answer_request_phrase",
        )

    mapped = _ACTION_TO_INTENT.get(request.action)
    if mapped is not None:
        return VisualTutorIntentDetection(mapped, f"action:{request.action.value}")

    if _CLARIFICATION_RE.search(message):
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.CLARIFICATION,
            "clarification_phrase",
        )
    if _NEW_PROBLEM_COMMAND_RE.search(message) and _MATH_PROBLEM_RE.search(message):
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.NEW_PROBLEM,
            "new_problem_command",
        )
    if request.current_state.problem_text and _STEP_RE.search(message):
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.SUBMITTED_STEP,
            "step_pattern",
        )
    if _MATH_PROBLEM_RE.search(message):
        return VisualTutorIntentDetection(
            VisualTutorStudentIntent.NEW_PROBLEM,
            "math_problem_pattern",
        )

    return VisualTutorIntentDetection(VisualTutorStudentIntent.UNKNOWN, "no_match")


def is_stuck_message(message: str) -> bool:
    return _stuck_reason(message) is not None


def is_stuck_help_request(request: VisualTutorTurnRequest) -> bool:
    return (
        detect_visual_tutor_student_intent(request).intent
        == VisualTutorStudentIntent.STUCK
    )


def _stuck_reason(message: str) -> Optional[str]:
    stripped = message.strip()
    for reason, pattern in _STUCK_RES:
        if pattern.search(stripped):
            return reason
    return None
