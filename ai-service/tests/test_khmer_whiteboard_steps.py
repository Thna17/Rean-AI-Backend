"""Tests ensuring that with language_mode: "khmer", all whiteboard text is Khmer.

Every write_text board action must contain Khmer script (U+1780-U+17FF) and
contain no English 'Step N ·' headings, covering both the limits path in
worked_solution.py and the generic path in dynamic_worked_solution.py.
"""

from __future__ import annotations

import re
import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorCanvasActionType,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.public_response import project_public_tutor_turn


def _has_khmer(text: str) -> bool:
    return any("\u1780" <= c <= "\u17ff" for c in text)


@pytest.mark.parametrize(
    "limit_message",
    [
        "រកលីមីតនៃ (x^2-4)/(x-2) ពេល x ខិតទៅ 2",
        "lim x->3 (x^2-9)/(x-3)",
        "lim x->2 (2x + 1)",
        "lim x->infinity (3x^2+1)/(2x^2-5)",
    ],
)
def test_worked_solution_limits_khmer_board_text(limit_message: str) -> None:
    req = VisualTutorTurnRequest(
        user_id="probe",
        subject="Mathematics",
        grade=12,
        message=limit_message,
        language_mode="khmer",
        action=VisualTutorAction.START,
    )
    turn_response = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(turn_response)
    teaching_plan = public_turn["teaching_plan"]
    visible_actions = teaching_plan.get("visible_board_actions", [])

    write_text_actions = [
        a for a in visible_actions if a.get("type") == "write_text"
    ]
    assert len(write_text_actions) > 0

    for action in write_text_actions:
        text = action.get("text") or ""
        # 1. Must contain Khmer script
        assert _has_khmer(text), f"Action text lacks Khmer script: {text!r}"
        # 2. Must NOT contain English 'Step N ·' heading
        assert not re.search(r"Step\s+\d+", text), f"Action text contains English Step heading: {text!r}"
        # 3. Answer line must not contain English "The limit is"
        assert "The limit is" not in text, f"Answer text contains English limit phrase: {text!r}"


def test_dynamic_worked_solution_khmer_board_text() -> None:
    req = VisualTutorTurnRequest(
        user_id="probe",
        subject="Physics",
        grade=12,
        topic="Kinematics",
        message="ឡានមួយចាប់ផ្តើមចេញពីភាពនៅស្ងៀម ហើយបង្កើនល្បឿនដោយសំទុះ 2 m/s^2 ក្នុងរយៈពេល 5 វិនាទី។ រកល្បឿនស្រេច។",
        language_mode="khmer",
        action=VisualTutorAction.START,
    )
    turn_response = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(turn_response)
    teaching_plan = public_turn["teaching_plan"]
    visible_actions = teaching_plan.get("visible_board_actions", [])

    write_text_actions = [
        a for a in visible_actions if a.get("type") == "write_text"
    ]
    assert len(write_text_actions) > 0

    for action in write_text_actions:
        text = action.get("text") or ""
        # 1. Must contain Khmer script
        assert _has_khmer(text), f"Action text lacks Khmer script: {text!r}"
        # 2. Must NOT contain English 'Step N ·' heading
        assert not re.search(r"Step\s+\d+", text), f"Action text contains English Step heading: {text!r}"
        # 3. Answer line must not contain untranslated English "Solution completed"
        assert "Solution completed" not in text, f"Answer text contains English fallback: {text!r}"


def test_worked_solution_limits_khmer_followup() -> None:
    from api.models.visual_tutor import VisualTutorTurnState

    req = VisualTutorTurnRequest(
        user_id="probe",
        subject="Mathematics",
        grade=12,
        message="ហេតុអ្វីបានជាយើងអាចសម្រួលកត្តានេះបាន?",
        language_mode="khmer",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text="lim x->2 (x^2-4)/(x-2)"),
    )
    turn_response = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(turn_response)
    teaching_plan = public_turn["teaching_plan"]
    visible_actions = teaching_plan.get("visible_board_actions", [])

    write_text_actions = [
        a for a in visible_actions if a.get("type") == "write_text"
    ]
    assert len(write_text_actions) > 0

    for action in write_text_actions:
        text = action.get("text") or ""
        assert _has_khmer(text), f"Action text lacks Khmer script: {text!r}"
        assert not re.search(r"Step\s+\d+", text), f"Action text contains English Step heading: {text!r}"
        assert not re.search(r"About\s+Step", text), f"Action text contains English About Step heading: {text!r}"
        assert "The limit is" not in text, f"Answer text contains English limit phrase: {text!r}"


def test_worked_solution_limits_khmer_tap_step() -> None:
    from api.models.visual_tutor import VisualTutorTurnState

    req = VisualTutorTurnRequest(
        user_id="probe",
        subject="Mathematics",
        grade=12,
        message="ពន្យល់ត្រង់នេះ",
        language_mode="khmer",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text="lim x->2 (x^2-4)/(x-2)"),
        metadata={"board_action_id": "ws-step-try-1"},
    )
    turn_response = handle_visual_tutor_turn(req)
    public_turn = project_public_tutor_turn(turn_response)
    teaching_plan = public_turn["teaching_plan"]
    visible_actions = teaching_plan.get("visible_board_actions", [])

    write_text_actions = [
        a for a in visible_actions if a.get("type") == "write_text"
    ]
    assert len(write_text_actions) > 0

    for action in write_text_actions:
        text = action.get("text") or ""
        assert _has_khmer(text), f"Action text lacks Khmer script: {text!r}"
        assert not re.search(r"Step\s+\d+", text), f"Action text contains English Step heading: {text!r}"
        assert not re.search(r"About\s+Step", text), f"Action text contains English About Step heading: {text!r}"
        assert "The limit is" not in text, f"Answer text contains English limit phrase: {text!r}"

