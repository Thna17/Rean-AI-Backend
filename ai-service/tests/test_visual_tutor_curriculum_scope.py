"""Curriculum scope tests for Grade 12 Mathematics, Physics, and Chemistry.

Visual Tutor is scoped to Grade 12 Mathematics, Physics, and Chemistry in
English and Khmer. Topics without a verified solver return an honest "not ready yet"
turn response, preventing unchecked LLM arithmetic. Out-of-scope requests
(e.g., Grade 10, Grade 12 Biology) receive helpful bilingual refusals.
"""

import pytest
from fastapi import HTTPException

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorLanguageMode,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.pilot import enforce_pilot_scope


@pytest.fixture(autouse=True)
def _scope_lock_grade12_stem(monkeypatch):
    """Enable the Grade 12 STEM scope lock for these tests."""
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_SCOPE_LOCK", "grade12_stem")


# ==============================================================================
# 1. In-Scope Tests: Grade 12 Math, Physics, Chemistry
# ==============================================================================


def test_grade_12_math_limits_proceeds_to_worked_solution() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Limits of Functions",
            message="Find the limit of (x^2 - 4)/(x - 2) as x approaches 2",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("generation_path") != "scope_locked"
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    # Should resolve with worked solution
    assert response.metadata.get("worked_solution") is True or "ws-step" in str(response.board_actions)


def test_grade_12_physics_kinematics_proceeds_to_worked_solution() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Physics",
            topic="Kinematics",
            message="A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("generation_path") != "scope_locked"
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    assert response.metadata.get("worked_solution") is True or "ws-physics" in str(response.board_actions)


def test_grade_12_physics_unsupported_topic_returns_solver_not_ready() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Physics",
            topic="Thermodynamics",
            message="Calculate the heat transfer in an isothermal expansion of 1 mole of ideal gas.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    # Must NOT be refused as out_of_scope_lock
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    # Must be in-scope and return honest solver_not_ready response
    assert response.metadata.get("generation_path") == "solver_not_ready"
    assert response.metadata.get("solver_ready") is False
    assert "not ready yet" in response.spoken_text.lower() or "មិនទាន់រួចរាល់" in response.spoken_text


def test_grade_12_chemistry_balancing_returns_solver_not_ready() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Chemistry",
            topic="Chemical Equations",
            message="Balance the equation: H2 + O2 -> H2O",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    # Must NOT be refused as out_of_scope_lock
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    # Must be in-scope and return honest solver_not_ready response
    assert response.metadata.get("generation_path") == "solver_not_ready"
    assert response.metadata.get("solver_ready") is False
    assert "not ready yet" in response.spoken_text.lower() or "មិនទាន់រួចរាល់" in response.spoken_text


def test_grade_12_math_other_topic_returns_solver_not_ready() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Logarithms",
            message="Solve log(x) = 2",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    assert response.metadata.get("generation_path") == "solver_not_ready"
    assert response.metadata.get("solver_ready") is False


# ==============================================================================
# 2. Out-of-Scope Tests with Helpful Bilingual Refusals
# ==============================================================================


def test_grade_10_mathematics_is_refused_with_helpful_message() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="Solve 2x + 3 = 7",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"
    assert response.metadata["fallback_reason"] == "out_of_scope_lock"
    assert response.final_answer_locked is True
    # Refusal must explain what IS supported: Grade 12 Math, Physics, Chemistry
    text = response.spoken_text
    assert "Grade 12" in text or "ថ្នាក់ទី១២" in text
    assert "Physics" in text or "រូបវិទ្យា" in text
    assert "Chemistry" in text or "គីមីវិទ្យា" in text


def test_grade_10_physics_is_refused_with_helpful_message() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Physics",
            topic="Motion",
            message="A ball falls under gravity.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"
    assert response.metadata["fallback_reason"] == "out_of_scope_lock"
    text = response.spoken_text
    assert "Grade 12" in text or "ថ្នាក់ទី១២" in text
    assert "Physics" in text or "រូបវិទ្យា" in text


def test_grade_10_chemistry_is_refused_with_helpful_message() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Chemistry",
            topic="Acids and Bases",
            message="What is the pH of water?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"
    assert response.metadata["fallback_reason"] == "out_of_scope_lock"
    text = response.spoken_text
    assert "Grade 12" in text or "ថ្នាក់ទី១២" in text
    assert "Chemistry" in text or "គីមីវិទ្យា" in text


def test_grade_12_biology_is_refused_with_helpful_message() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Biology",
            topic="Photosynthesis",
            message="Explain the light reactions of photosynthesis.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"
    assert response.metadata["fallback_reason"] == "out_of_scope_lock"
    text = response.spoken_text
    assert "Grade 12" in text or "ថ្នាក់ទី១២" in text
    assert "Mathematics" in text or "គណិតវិទ្យា" in text
    assert "Physics" in text or "រូបវិទ្យា" in text
    assert "Chemistry" in text or "គីមីវិទ្យា" in text


def test_khmer_language_mode_refusal_is_bilingual_or_khmer() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Biology",
            topic="កោសិកា",
            message="តើកោសិកាជាអ្វី?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            language_mode=VisualTutorLanguageMode.KHMER,
            metadata={"grade": 12, "language_mode": "khmer"},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"
    assert "ថ្នាក់ទី១២" in response.spoken_text
    assert ("គណិតវិទ្យា" in response.spoken_text or "រូបវិទ្យា" in response.spoken_text or "គីមីវិទ្យា" in response.spoken_text)


# ==============================================================================
# 3. Supervised Pilot Scope Gate Tests
# ==============================================================================


def test_pilot_scope_permits_grade_12_physics(monkeypatch) -> None:
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_PILOT_ENABLED", True)

    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Kinematics",
        message="A ball is dropped from 20m.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    # Must NOT raise HTTPException 403
    enforce_pilot_scope(req)


def test_pilot_scope_permits_grade_12_chemistry(monkeypatch) -> None:
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_PILOT_ENABLED", True)

    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Chemistry",
        topic="Stoichiometry",
        message="Calculate moles of NaCl.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    # Must NOT raise HTTPException 403
    enforce_pilot_scope(req)


def test_pilot_scope_refuses_grade_10_with_helpful_403(monkeypatch) -> None:
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_PILOT_ENABLED", True)

    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Kinematics",
        message="Find speed.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 10},
    )
    with pytest.raises(HTTPException) as exc_info:
        enforce_pilot_scope(req)
    assert exc_info.value.status_code == 403
    assert "Grade 12" in exc_info.value.detail or "ថ្នាក់ទី១២" in exc_info.value.detail


def test_pilot_scope_refuses_biology_with_helpful_403(monkeypatch) -> None:
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_PILOT_ENABLED", True)

    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Biology",
        topic="Genetics",
        message="What is a gene?",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    with pytest.raises(HTTPException) as exc_info:
        enforce_pilot_scope(req)
    assert exc_info.value.status_code == 403
    assert "Grade 12" in exc_info.value.detail or "ថ្នាក់ទី១២" in exc_info.value.detail
