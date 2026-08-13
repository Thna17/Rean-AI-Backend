from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorInputRelevance,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.input_understanding import (
    understand_visual_tutor_student_input,
)
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)


def _understand(message: str, *, current_problem: str = "2x + 5 = 15"):
    problem = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message=current_problem,
        )
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message=message,
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(problem_text=current_problem),
    )
    return understand_visual_tutor_student_input(request, problem)


@pytest.mark.parametrize(
    ("message", "relevance", "validation_result"),
    [
        ("50", VisualTutorInputRelevance.UNRELATED, "unrelated_numeric_input"),
        ("4", VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER, "incorrect_final_answer"),
        ("2x = 10", VisualTutorInputRelevance.RELEVANT_STEP, "correct_step"),
        ("subtract 5", VisualTutorInputRelevance.RELEVANT_STEP, "correct_operation"),
        (
            "substract 5 from both side",
            VisualTutorInputRelevance.RELEVANT_STEP,
            "correct_operation",
        ),
        ("I am stuck", VisualTutorInputRelevance.STUCK, None),
        ("ខ្ញុំមិនយល់", VisualTutorInputRelevance.STUCK, None),
    ],
)
def test_linear_equation_input_relevance(
    message: str,
    relevance: VisualTutorInputRelevance,
    validation_result: str | None,
) -> None:
    result = _understand(message)

    assert result.input_relevance == relevance
    if validation_result is not None:
        assert result.metadata["validation_result"] == validation_result


def test_random_text_is_off_topic_for_active_problem() -> None:
    result = _understand("banana movie sentence")

    assert result.student_intent == VisualTutorStudentIntent.UNKNOWN
    assert result.input_relevance == VisualTutorInputRelevance.OFF_TOPIC


def test_linear_equation_final_step_is_relevant_after_first_step() -> None:
    problem = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
        )
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="x = 5",
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(
            problem_text="2x + 5 = 15",
            current_step_index=1,
        ),
    )

    result = understand_visual_tutor_student_input(request, problem)

    assert result.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert result.metadata["validation_result"] == "correct_final_step"


@pytest.mark.parametrize("message", ["so x = 7", "then x = 7", "therefore x = 7"])
def test_linear_equation_final_step_accepts_natural_lead_in_words(
    message: str,
) -> None:
    problem = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message="3x - 9 = 12",
        )
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message=message,
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(
            problem_text="3x - 9 = 12",
            current_step_index=1,
        ),
    )

    result = understand_visual_tutor_student_input(request, problem)

    assert result.extracted_equations == ["x = 7"]
    assert result.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert result.metadata["validation_result"] == "correct_final_step"


@pytest.mark.parametrize(
    ("message", "validation_result"),
    [
        ("Yes", "understanding_check_yes"),
        ("No", "understanding_check_no"),
        ("ត្រូវ", "understanding_check_yes"),
        ("ទេ", "understanding_check_no"),
    ],
)
def test_linear_equation_verification_answer_is_not_treated_as_step(
    message: str,
    validation_result: str,
) -> None:
    problem = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
        )
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message=message,
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(
            problem_text="2x + 5 = 15",
            current_step_index=2,
            final_answer_revealed=True,
        ),
    )

    result = understand_visual_tutor_student_input(request, problem)

    assert result.student_intent == VisualTutorStudentIntent.CLARIFICATION
    assert result.input_relevance == VisualTutorInputRelevance.CLARIFICATION
    assert result.metadata["validation_result"] == validation_result


def test_linear_equation_non_x_variable_steps_are_relevant() -> None:
    problem = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message="5a - 8 = 2a + 7",
        )
    )
    first_step_request = VisualTutorTurnRequest(
        user_id="student-1",
        message="3a = 15",
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(problem_text="5a - 8 = 2a + 7"),
    )
    final_step_request = VisualTutorTurnRequest(
        user_id="student-1",
        message="a = 5",
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(
            problem_text="5a - 8 = 2a + 7",
            current_step_index=1,
        ),
    )

    first_step = understand_visual_tutor_student_input(first_step_request, problem)
    final_step = understand_visual_tutor_student_input(final_step_request, problem)

    assert first_step.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert first_step.metadata["validation_result"] == "correct_step"
    assert final_step.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert final_step.metadata["validation_result"] == "correct_final_step"


def test_new_equation_during_old_problem_is_new_problem() -> None:
    result = _understand("Solve 3x - 2 = 10")

    assert result.student_intent == VisualTutorStudentIntent.NEW_PROBLEM
    assert result.input_relevance == VisualTutorInputRelevance.NEW_PROBLEM


def test_uncertainty_phrase_is_stuck_help_intent() -> None:
    result = _understand("i dont know")

    assert result.student_intent == VisualTutorStudentIntent.STUCK
    assert result.input_relevance == VisualTutorInputRelevance.STUCK
    assert result.metadata["stuck_reason"] == "uncertainty_phrase"


def test_equation_at_start_is_new_problem_even_with_step_action() -> None:
    problem = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject="Mathematics",
            topic="Linear Equations",
            message="3x - 9 = 12",
        )
    )
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="3x - 9 = 12",
        action=VisualTutorAction.SUBMIT_STEP,
        student_submitted_step=True,
        current_state=VisualTutorTurnState(),
    )

    result = understand_visual_tutor_student_input(request, problem)

    assert result.student_intent == VisualTutorStudentIntent.NEW_PROBLEM
    assert result.input_relevance == VisualTutorInputRelevance.NEW_PROBLEM


def test_visual_request_is_visual_hint_intent() -> None:
    result = _understand("show me visually")

    assert result.student_intent == VisualTutorStudentIntent.REQUEST_HINT
    assert result.input_relevance == VisualTutorInputRelevance.RELEVANT_STEP
    assert result.metadata["requested_visual_hint"] is True
