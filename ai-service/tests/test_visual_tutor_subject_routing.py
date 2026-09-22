from __future__ import annotations

import json

import json

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


class FakeVisualTutorLLMClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return json.dumps(self.payload, ensure_ascii=False)


@pytest.mark.parametrize(
    ("subject", "message", "expected_subject", "expected_topic", "problem_type"),
    [
        (
            "English",
            "Why is this sentence wrong: She go to school every day?",
            "English",
            "Grammar",
            "english_grammar_question",
        ),
        (
            "Khmer",
            "សូមពន្យល់ពាក្យ វេយ្យាករណ៍ ក្នុងភាសាខ្មែរ",
            "Khmer",
            "Khmer Language",
            "khmer_language_question",
        ),
        (
            "Physics",
            "How do I use the formula F = ma?",
            "Physics",
            "Forces and Motion",
            "physics_formula_question",
        ),
        (
            "Chemistry",
            "Explain why acids react with bases.",
            "Chemistry",
            "Acids and Bases",
            "chemistry_concept_question",
        ),
    ],
)
def test_visual_tutor_classifies_non_math_subjects(
    subject: str,
    message: str,
    expected_subject: str,
    expected_topic: str,
    problem_type: str,
) -> None:
    result = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(subject=subject, message=message)
    )

    assert result.subject == expected_subject
    assert result.topic == expected_topic
    assert result.problem_type == problem_type
    assert result.known_solver_available is False
    assert result.needs_clarification is True
    assert result.clarification_question


@pytest.mark.parametrize(
    ("subject", "message", "board_type", "expected_problem_type"),
    [
        (
            "English",
            "Why is this sentence wrong: She go to school every day?",
            "word_problem_breakdown",
            "english_grammar_question",
        ),
        (
            "Khmer",
            "សូមពន្យល់ពាក្យ វេយ្យាករណ៍ ក្នុងភាសាខ្មែរ",
            "word_problem_breakdown",
            "khmer_language_question",
        ),
        (
            "Physics",
            "How do I use the formula F = ma?",
            "formula_card",
            "physics_formula_question",
        ),
        (
            "Chemistry",
            "Explain why acids react with bases.",
            "word_problem_breakdown",
            "chemistry_concept_question",
        ),
    ],
)
def test_non_math_subjects_use_llm_planner_guided_and_locked(
    subject: str,
    message: str,
    board_type: str,
    expected_problem_type: str,
) -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            board_type=board_type,
            spoken_text="Let's inspect this like a teacher before giving an answer.",
            display_text="First, identify what the question is asking.",
            student_task="Tell me which part you want to try first.",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject=subject,
            message=message,
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    assert fake_llm.calls
    assert response.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert response.final_answer_locked is True
    assert response.board.type == board_type
    assert (
        response.metadata["problem_understanding"]["problem_type"]
        == expected_problem_type
    )
    assert response.metadata["problem_understanding"]["known_solver_available"] is False


def test_mathematics_solver_facts_still_preferred_when_llm_generates_turn() -> None:
    fake_llm = FakeVisualTutorLLMClient(_planner_payload())

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            message="solve 2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert fake_llm.calls
    assert response.final_answer_locked is True
    assert response.metadata["policy"]["problem_type"] == "linear_equation_one_variable"
    assert response.metadata["response_source"] == "llm_planner"
    assert user_prompt["solver_facts"]["solver_name"] == "LinearEquationSolver"
    assert user_prompt["solver_facts"]["sympy_verified"] is True


def _planner_payload(
    *,
    board_type: str = "word_problem_breakdown",
    spoken_text: str = "Let's inspect the question first.",
    display_text: str = "Start by identifying the target.",
    student_task: str = "Tell me what you notice first.",
) -> dict:
    return {
        "spoken_text": spoken_text,
        "display_text": display_text,
        "teaching_mode": "guided_question",
        "student_task": student_task,
        "board": {
            "type": board_type,
            "title": "Subject Board",
            "items": [
                {
                    "label": "Question",
                    "content": "We will break this down first.",
                    "status": "active",
                    "metadata": {},
                }
            ],
            "metadata": {},
        },
        "mastery_signal": "exploring",
        "metadata": {"source": "mock_llm"},
    }
