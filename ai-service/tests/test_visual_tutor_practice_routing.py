"""A student's own question must never be swapped for a practice problem.

The client sends client_intent_hint="new_problem" whenever a student starts a
problem, including one they typed into "Ask anything". The route treated that
hint alone as a request for targeted practice, so it called the practice
generator, overwrote request.message with a canned problem, and solved that
instead. With no topic on an ask-anything turn the generator falls back to
"Linear Equations", so every question a student typed came back as
"3x + 4 = 19" -- the app's main entry point answered the wrong question every
time.
"""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
)
from api.routes.visual_tutor import should_generate_practice


def _request(**overrides) -> VisualTutorTurnRequest:
    values = {
        "user_id": "student-1",
        "subject": "General",
        "message": "",
        "action": VisualTutorAction.SUBMIT_PROBLEM,
        "metadata": {},
    }
    values.update(overrides)
    return VisualTutorTurnRequest(**values)


class TestAStudentsOwnQuestionIsKept:
    def test_a_typed_question_is_not_a_practice_request(self):
        request = _request(
            message="A car starts from rest and accelerates at 2 m/s^2 for 5 s. Find its final velocity.",
            student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
            metadata={"client_intent_hint": "new_problem"},
        )

        assert should_generate_practice(request) is False

    def test_a_typed_question_is_kept_even_with_a_topic(self):
        request = _request(
            message="lim (x^2-4)/(x-2) as x approaches 2",
            topic="Linear Equations",
            metadata={"client_intent_hint": "new_problem"},
        )

        assert should_generate_practice(request) is False


class TestRealPracticeRequestsStillWork:
    def test_the_explicit_practice_action_generates(self):
        request = _request(
            action=VisualTutorAction.GENERATE_PRACTICE,
            topic="Linear Equations",
        )

        assert should_generate_practice(request) is True

    def test_the_next_practice_mode_generates(self):
        request = _request(topic="Linear Equations", metadata={"mode": "next_practice"})

        assert should_generate_practice(request) is True

    def test_a_new_problem_hint_with_nothing_typed_generates(self):
        """Nothing to honour, so choosing a problem is the only useful answer."""
        request = _request(
            topic="Linear Equations",
            metadata={"client_intent_hint": "new_problem"},
        )

        assert should_generate_practice(request) is True

    def test_whitespace_is_not_a_question(self):
        request = _request(
            message="   ",
            topic="Linear Equations",
            metadata={"client_intent_hint": "new_problem"},
        )

        assert should_generate_practice(request) is True
