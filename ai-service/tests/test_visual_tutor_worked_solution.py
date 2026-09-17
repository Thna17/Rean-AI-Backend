"""The tutor shows a whole limit solution and answers questions about it.

Nothing here calls a language model: the steps are sympy's and the follow-up
answer falls back to the written step, so these assertions describe what a
student is guaranteed to get even with no provider configured.
"""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.solvers import parse_limit_of_function
from api.services.visual_tutor.worked_solution import solve_limit


def _request(message: str, *, problem_text: str | None = None, **metadata) -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id="student-1",
        subject="General",
        message=message,
        action=(
            VisualTutorAction.SUBMIT_STEP
            if problem_text
            else VisualTutorAction.SUBMIT_PROBLEM
        ),
        current_state=VisualTutorTurnState(problem_text=problem_text),
        metadata={"entry_context": "ask_question", **metadata},
    )


def _plan(response) -> dict:
    return response.metadata["teaching_plan"]


def _texts(response) -> str:
    return " ".join(
        str(action.get("text") or action.get("latex") or "")
        for action in _plan(response)["board_actions"]
    )


@pytest.mark.parametrize(
    "problem, answer",
    [
        ("lim x->3 (x^2-9)/(x-3)", "The limit is 6."),
        ("Find the limit of f(x) = 2x + 1 as x approaches 4", "The limit is 9."),
        ("lim x->2 (x^2-5x+6)/(x-2)", "The limit is −1."),
        ("lim x->infinity (3x^2+1)/(2x^2-5)", "The limit is 3/2."),
        ("lim x->0 sin(x)/x", "The limit is 1."),
        ("lim x->0 1/x", "The limit does not exist."),
    ],
)
def test_every_supported_limit_is_solved_correctly(problem: str, answer: str) -> None:
    solution = solve_limit(parse_limit_of_function(problem))

    assert solution.answer_text == answer


def test_a_new_limit_is_answered_in_full_with_the_answer_shown() -> None:
    response = handle_visual_tutor_turn(_request("lim x->3 (x^2-9)/(x-3)"))

    assert response.final_answer_locked is False
    plan = _plan(response)
    assert plan["representation"] == "worked_example"
    # The reasoning a student needs, not just the result.
    text = _texts(response)
    assert "indeterminate form" in text
    assert "never equals" in text
    assert "The limit is 6." in text


def test_each_step_is_its_own_section_so_boards_never_split_one() -> None:
    response = handle_visual_tutor_turn(_request("lim x->3 (x^2-9)/(x-3)"))

    sections = [
        action.get("section_id") for action in _plan(response)["board_actions"]
    ]
    assert all(sections)
    # Sections stay contiguous; a step is one unbroken run of actions.
    ordered = [section for index, section in enumerate(sections) if index == 0 or section != sections[index - 1]]
    assert len(ordered) == len(set(ordered))


def test_a_question_is_answered_against_the_step_it_is_about() -> None:
    response = handle_visual_tutor_turn(
        _request("why can we cancel (x-3)?", problem_text="lim x->3 (x^2-9)/(x-3)")
    )

    text = _texts(response)
    assert "About Step 4 · Cancel the common factor" in text
    # The solution stays on the board so the student can see the step.
    assert "The limit is 6." in text


def test_tapping_a_step_asks_about_that_step() -> None:
    response = handle_visual_tutor_turn(
        _request(
            "explain this please",
            problem_text="lim x->3 (x^2-9)/(x-3)",
            board_action_id="ws-step-try-3",
        )
    )

    assert "About Step 2 · Try substituting first" in _texts(response)


def test_a_question_about_an_in_scope_problem_is_not_refused() -> None:
    response = handle_visual_tutor_turn(
        _request("i don't understand", problem_text="lim x->3 (x^2-9)/(x-3)")
    )

    assert "currently focused on Grade 12 limits" not in _texts(response)


def test_try_it_myself_keeps_the_guided_flow() -> None:
    response = handle_visual_tutor_turn(
        _request("lim x->3 (x^2-9)/(x-3)", tutor_mode="try_myself")
    )

    assert response.metadata.get("worked_solution") is None
