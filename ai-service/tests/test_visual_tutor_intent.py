from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.intent import detect_visual_tutor_student_intent


def _detect(
    message: str,
    *,
    action: VisualTutorAction = VisualTutorAction.START,
    has_problem: bool = False,
) -> tuple[VisualTutorStudentIntent, str | None]:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message=message,
        action=action,
        current_state={
            "problem_text": "2x + 5 = 15" if has_problem else None,
        },
    )
    result = detect_visual_tutor_student_intent(request)
    return result.intent, result.reason


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        ("I am stuck", "stuck_phrase"),
        ("I'm stuck on this", "stuck_phrase"),
        ("I don't understand", "does_not_understand"),
        ("I do not understand this step", "does_not_understand"),
        ("help me", "help_request"),
        ("I can't solve this", "cannot_solve"),
        ("I cannot solve this one", "cannot_solve"),
        ("I am confused", "confused"),
        ("ខ្ញុំមិនយល់", "khmer_does_not_understand"),
        ("មិនយល់", "khmer_does_not_understand"),
        ("ជួយខ្ញុំ", "khmer_help_request"),
        ("ជួយខ្ញុំផង", "khmer_help_request"),
    ],
)
def test_detects_english_and_khmer_stuck_confusion_phrases(
    message: str,
    reason: str,
) -> None:
    intent, detected_reason = _detect(
        message,
        action=VisualTutorAction.SUBMIT_STEP,
        has_problem=True,
    )

    assert intent == VisualTutorStudentIntent.STUCK
    assert detected_reason == reason


@pytest.mark.parametrize(
    "message",
    [
        "explain again",
        "explain differently",
        "Can you explain this another way?",
        "ពន្យល់ម្ដងទៀត",
    ],
)
def test_detects_explain_differently_requests(message: str) -> None:
    intent, reason = _detect(message, has_problem=True)

    assert intent == VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY
    assert reason == "explain_differently_phrase"


@pytest.mark.parametrize(
    "message",
    [
        "hint",
        "give me a hint",
        "small help please",
        "គន្លឹះ",
    ],
)
def test_detects_hint_requests(message: str) -> None:
    intent, reason = _detect(message, has_problem=True)

    assert intent == VisualTutorStudentIntent.REQUEST_HINT
    assert reason == "hint_phrase"


@pytest.mark.parametrize(
    "message",
    [
        "show answer",
        "give me the final answer",
        "answer please",
        "ចម្លើយ",
    ],
)
def test_detects_show_answer_requests(message: str) -> None:
    intent, reason = _detect(message, has_problem=True)

    assert intent == VisualTutorStudentIntent.REQUEST_ANSWER
    assert reason == "answer_request_phrase"


@pytest.mark.parametrize(
    "message",
    [
        "Solve 2x + 5 = 15",
        "Find the equation through D(0,1) and E(1,3)",
        "ដោះស្រាយ 2x + 5 = 15",
    ],
)
def test_detects_new_math_problems(message: str) -> None:
    intent, reason = _detect(message, has_problem=True)

    assert intent == VisualTutorStudentIntent.NEW_PROBLEM
    assert reason == "new_problem_command"


@pytest.mark.parametrize(
    "message",
    [
        "2x = 10",
        "m = 2",
        "I tried subtracting 5",
        "check this step",
    ],
)
def test_detects_submitted_student_steps_when_problem_exists(message: str) -> None:
    intent, reason = _detect(message, has_problem=True)

    assert intent == VisualTutorStudentIntent.SUBMITTED_STEP
    assert reason == "step_pattern"


def test_explicit_action_mapping_still_works() -> None:
    assert _detect("next", action=VisualTutorAction.SUBMIT_PROBLEM)[0] == (
        VisualTutorStudentIntent.NEW_PROBLEM
    )
    assert _detect("next", action=VisualTutorAction.SUBMIT_STEP)[0] == (
        VisualTutorStudentIntent.SUBMITTED_STEP
    )
    assert _detect("next", action=VisualTutorAction.REQUEST_HINT)[0] == (
        VisualTutorStudentIntent.REQUEST_HINT
    )
    assert _detect("next", action=VisualTutorAction.EXPLAIN_DIFFERENTLY)[0] == (
        VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY
    )
    assert _detect("next", action=VisualTutorAction.REQUEST_FINAL_ANSWER)[0] == (
        VisualTutorStudentIntent.REQUEST_ANSWER
    )


def test_unknown_message_remains_unknown() -> None:
    intent, reason = _detect("okay")

    assert intent == VisualTutorStudentIntent.UNKNOWN
    assert reason == "no_match"
