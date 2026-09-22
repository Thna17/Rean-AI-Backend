"""Tests for dynamic RAG curriculum gate and universal worked solution builder."""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.dynamic_worked_solution import (
    answer_dynamic_followup,
    build_dynamic_worked_solution_turn,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.rag_curriculum_gate import classify_student_query


def test_classify_tier_1_verified_limit():
    result = classify_student_query("Find the limit of (x^2 - 9)/(x - 3) as x approaches 3")
    assert result.is_in_scope is True
    assert result.is_verified is True
    assert result.subject in ("mathematics", "general_stem")


def test_classify_tier_1_verified_physics():
    result = classify_student_query("A car accelerates from rest at 2 m/s^2 for 10 seconds. Find its final velocity.")
    assert result.is_in_scope is True
    assert result.subject == "physics"


def test_classify_tier_1_verified_chemistry():
    result = classify_student_query("2H2 + O2 -> 2H2O. If we have 4 grams of H2, what is the mass of H2O produced?")
    assert result.is_in_scope is True
    assert result.subject == "chemistry"


def test_classify_tier_2_unverified_stem():
    result = classify_student_query("Find the eigenvalues of a 2x2 matrix [[1, 2], [3, 4]]")
    assert result.is_in_scope is True
    # Advanced STEM topic not in high school curriculum -> Tier 2 (Unverified AI Guidance)
    assert result.tier == "unverified"
    assert result.is_verified is False
    assert result.subject in ("mathematics", "general_stem")


def test_classify_tier_3_out_of_scope():
    result = classify_student_query("Who was George Washington?")
    assert result.tier == "out_of_scope"
    assert result.is_in_scope is False
    assert result.refusal_message_en is not None
    assert "Grade 10–12" in result.refusal_message_en


def test_classify_tier_3_out_of_scope_khmer():
    result = classify_student_query("តើអ្នកណាជាប្រធានាធិបតីអាមេរិកដំបូង?")
    assert result.tier == "out_of_scope"
    assert result.is_in_scope is False
    assert result.refusal_message_km is not None
    assert "ថ្នាក់ទី១០-១២" in result.refusal_message_km


def test_dynamic_worked_solution_limits():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Find the limit of (x^2 - 9)/(x - 3) as x approaches 3",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert len(res.board_actions) >= 4
    # Check that deterministic limit steps were produced
    texts = " ".join(a.text or a.latex or "" for a in res.board_actions)
    assert "6" in texts or "x + 3" in texts
    assert res.metadata.get("verified") is True
    assert res.metadata.get("curriculum_status") == "verified_curriculum"


def test_dynamic_worked_solution_unverified_stem():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Solve the quadratic equation x^2 - 5x + 6 = 0",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert len(res.board_actions) >= 3
    # Check that actions and student task were built
    assert res.student_task is not None
    assert res.metadata.get("worked_solution") is True


def test_dynamic_worked_solution_followup():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Why can we cancel x - 3?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text="Find the limit of (x^2 - 9)/(x - 3) as x approaches 3",
            board_version=1,
        ),
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    # Follow-up keeps original solution on board and appends a reply
    action_ids = [a.id for a in res.board_actions]
    assert any("reply" in a_id for a_id in action_ids)


def test_out_of_scope_rejection_turn():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="General",
        message="Tell me a recipe for cooking pizza",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    assert res.final_answer_locked is True
    assert "Grade 12" in res.spoken_text or "Grade 10–12" in res.spoken_text


def test_dynamic_worked_solution_physics_kinematics():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Kinematics",
        message="A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert res.metadata.get("worked_solution") is True
    assert res.metadata.get("verified") is True
    assert res.teaching_mode == VisualTutorTeachingMode.FULL_SOLUTION
    assert any("10" in (a.text or a.latex or "") for a in res.board_actions)


def test_dynamic_worked_solution_chemistry_stoichiometry():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Chemistry",
        topic="Stoichiometry",
        message="Given the reaction 2H2 + O2 -> 2H2O, how many moles of H2O are produced from 4.0 moles of H2?",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert res.metadata.get("worked_solution") is True
    assert res.metadata.get("verified") is True
    assert res.teaching_mode == VisualTutorTeachingMode.FULL_SOLUTION
    assert any("4" in (a.text or a.latex or "") for a in res.board_actions)


def test_dynamic_worked_solution_deterministic_ids_contract():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Find lim x->3 (x^2 - 9)/(x - 3)",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    actions = res.board_actions
    assert len(actions) > 0
    # All IDs must follow deterministic format
    for idx, a in enumerate(actions):
        assert a.sequence_index == idx
        assert a.id.startswith("ws-")
        assert a.duration_ms >= 0


def test_dynamic_worked_solution_honest_degradation_when_required():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Electromagnetism",
        message="Calculate the magnetic field at the center of a circular loop carrying 5A current.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12, "require_verified_solver": True},
    )
    res = handle_visual_tutor_turn(req)
    assert res.metadata.get("generation_path") == "solver_not_ready"
    assert res.metadata.get("solver_ready") is False
    assert "not ready yet" in res.spoken_text.lower() or "មិនទាន់រួចរាល់" in res.spoken_text

