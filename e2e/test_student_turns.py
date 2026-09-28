"""A student asks a question and gets a worked solution, through the real gateway.

Every expected value here comes from a deterministic SymPy-backed solver, so these
tests never call DeepSeek: they are free to run and stable.
"""

from __future__ import annotations

import pytest

from conftest import (
    assert_contract_shape,
    assert_no_secret_leak,
    board_text,
    teaching_message,
)

# (label, problem, subject, fragments that must appear in the answer)
SOLVED_PROBLEMS = [
    ("linear", "Solve 3x + 7 = 22", "Mathematics", ["x = 5"]),
    ("quadratic", "Solve x^2 - 5x + 6 = 0", "Mathematics", ["x = 2", "x = 3"]),
    (
        "system",
        "Solve 2x + 3y = 12 and x - y = 1",
        "Mathematics",
        ["x = 3", "y = 2"],
    ),
    (
        "limit",
        "Find the limit of (x^2-4)/(x-2) as x approaches 2",
        "Mathematics",
        ["4"],
    ),
    (
        "derivative",
        "Find the derivative of x^3 - 4x^2 + 5x",
        "Mathematics",
        ["3x^2 - 8x + 5"],
    ),
    (
        "kinematics",
        "A car starts from rest and accelerates at 2 m/s^2 for 5 s. "
        "Find its velocity and the distance travelled.",
        "Physics",
        ["10"],
    ),
    (
        "stoichiometry",
        "How many grams of water are produced when 4 g of hydrogen reacts "
        "completely with oxygen?",
        "Chemistry",
        ["35.7"],
    ),
    (
        "molarity",
        "What is the molarity of 5.85 g of NaCl dissolved in 500 mL of water?",
        "Chemistry",
        ["0.200"],
    ),
]


@pytest.mark.parametrize(
    ("label", "problem", "subject", "fragments"),
    SOLVED_PROBLEMS,
    ids=[case[0] for case in SOLVED_PROBLEMS],
)
def test_the_gateway_returns_a_worked_solution(
    gateway, internal_token, label, problem, subject, fragments
):
    turn = gateway.solve(problem, subject=subject)

    assert_contract_shape(turn)
    assert_no_secret_leak(teaching_message(turn) + board_text(turn), internal_token)

    whole = f"{teaching_message(turn)}\n{board_text(turn)}"
    for fragment in fragments:
        assert fragment in whole, (
            f"{label}: expected {fragment!r} somewhere in the answer, got "
            f"{teaching_message(turn)!r}"
        )


@pytest.mark.parametrize(
    ("label", "problem", "subject", "fragments"),
    SOLVED_PROBLEMS,
    ids=[case[0] for case in SOLVED_PROBLEMS],
)
def test_a_solved_turn_reports_a_contract_legal_status(
    gateway, label, problem, subject, fragments
):
    """Guards the defect that made every kinematics turn a 502.

    The AI service used to default this field to "verified", which the public
    contract does not allow, so the gateway threw the turn away.
    """
    verification = gateway.solve(problem, subject=subject)["verification"]
    assert verification["status"] != "verified", (
        "'verified' is not a public status; the gateway rejects a turn reporting it"
    )
    if verification["verified"]:
        assert verification["status"] == "correct"


def test_the_board_draws_the_solution_rather_than_only_stating_it(gateway):
    turn = gateway.solve("Solve 3x + 7 = 22")
    actions = (turn["teaching_plan"] or {}).get("visible_board_actions") or []

    assert len(actions) >= 4, (
        "a worked solution should reach the board as several steps, not one line"
    )
    assert any(action.get("type") == "write_equation" for action in actions), (
        "no equation was written on the board"
    )
    assert any(action.get("type") == "write_text" for action in actions)


def test_a_turn_opens_a_session_the_student_can_come_back_to(gateway):
    turn = gateway.solve("Solve 3x + 7 = 22")

    assert turn["session_id"], "a turn must belong to a session"
    assert turn["board_version"] >= 1
    assert turn["base_board_version"] < turn["board_version"], (
        "a new board must advance past the version it was based on"
    )
    assert turn["lesson_state"]["problem_instance_id"], (
        "without a problem instance the client cannot tie actions to a problem"
    )


@pytest.mark.xfail(
    strict=True,
    reason="The kinematics solver answers only the first quantity asked. This "
    "question asks for velocity and distance; it returns v = 10 m/s and never "
    "computes s = ut + at^2/2 = 25 m, so a standard two-part Grade 11 question "
    "gets half an answer.",
)
def test_kinematics_answers_every_quantity_the_question_asks_for(gateway):
    turn = gateway.solve(
        "A car starts from rest and accelerates at 2 m/s^2 for 5 s. "
        "Find its velocity and the distance travelled.",
        subject="Physics",
    )
    whole = f"{teaching_message(turn)}\n{board_text(turn)}"
    assert "10" in whole, "velocity is missing"
    assert "25" in whole, "distance travelled is missing"
