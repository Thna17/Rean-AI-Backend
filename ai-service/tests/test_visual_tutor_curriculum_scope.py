"""Curriculum scope tests for Grade 10-12 Mathematics, Physics, and Chemistry.

Visual Tutor is scoped to Grade 10-12 Mathematics, Physics, and Chemistry in
English and Khmer. In-scope topics without a deterministic solver get a worked
solution labelled ``curriculum_status: ai_unverified`` so it is never passed
off as verified. Out-of-scope requests (e.g., Grade 9, Biology) receive helpful
bilingual refusals.
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
from api.services.visual_tutor.scope import check_scope


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


def test_grade_12_physics_topic_without_solver_is_answered_as_unverified() -> None:
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

    # In scope, answered, and honestly labelled as not verified by a solver.
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    assert response.metadata.get("worked_solution") is True
    assert response.metadata.get("verified") is False
    assert response.metadata.get("curriculum_status") == "ai_unverified"


def test_grade_12_chemistry_stoichiometry_proceeds_to_worked_solution() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Chemistry",
            topic="Stoichiometry",
            message="Given the reaction 2H2 + O2 -> 2H2O, how many moles of H2O are produced from 4.0 moles of H2?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("generation_path") != "scope_locked"
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    assert response.metadata.get("worked_solution") is True or "ws-chem" in str(response.board_actions)


def test_grade_12_chemistry_topic_without_solver_is_answered_as_unverified() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Chemistry",
            topic="Titration",
            message="Calculate the concentration of acid in a neutralization titration with 0.1 M NaOH.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    # In scope, answered, and honestly labelled as not verified by a solver.
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    assert response.metadata.get("worked_solution") is True
    assert response.metadata.get("verified") is False
    assert response.metadata.get("curriculum_status") == "ai_unverified"


def test_grade_12_math_topic_without_solver_is_answered_as_unverified() -> None:
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
    assert response.metadata.get("worked_solution") is True
    assert response.metadata.get("curriculum_status") == "ai_unverified"


# ==============================================================================
# 2. Out-of-Scope Tests with Helpful Bilingual Refusals
# ==============================================================================


def test_grade_10_mathematics_is_in_scope() -> None:
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

    assert response.metadata.get("generation_path") != "scope_locked"
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"


def test_grade_10_physics_is_in_scope() -> None:
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

    assert response.metadata.get("generation_path") != "scope_locked"
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"


def test_grade_10_chemistry_is_in_scope() -> None:
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

    assert response.metadata.get("generation_path") != "scope_locked"
    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"


def test_grade_9_mathematics_is_refused_with_helpful_message() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="Solve 2x + 3 = 7",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 9},
        )
    )

    assert response.metadata["generation_path"] == "scope_locked"
    assert response.metadata["fallback_reason"] == "out_of_scope_lock"
    assert response.final_answer_locked is True
    # Refusal must explain what IS supported: Grade 10-12 Math, Physics, Chemistry
    text = response.spoken_text
    assert "Grade 10–12" in text or "ថ្នាក់ទី១០" in text
    assert "Physics" in text or "រូបវិទ្យា" in text
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
    assert "Grade 10–12" in text or "ថ្នាក់ទី១០" in text
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
    assert "ថ្នាក់ទី១០" in response.spoken_text
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


def test_pilot_scope_permits_grade_10_physics(monkeypatch) -> None:
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
    # Must NOT raise HTTPException 403
    enforce_pilot_scope(req)


def test_pilot_scope_refuses_grade_9_with_helpful_403(monkeypatch) -> None:
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_PILOT_ENABLED", True)

    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Kinematics",
        message="Find speed.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 9},
    )
    with pytest.raises(HTTPException) as exc_info:
        enforce_pilot_scope(req)
    assert exc_info.value.status_code == 403
    assert "Grade 10–12" in exc_info.value.detail or "ថ្នាក់ទី១០" in exc_info.value.detail


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
    assert "Grade 10–12" in exc_info.value.detail or "ថ្នាក់ទី១០" in exc_info.value.detail


def test_the_out_of_scope_refusal_speaks_one_language() -> None:
    """A single-language turn must not be answered in two languages.

    build_out_of_scope_message paired the English and Khmer copies
    unconditionally, so a student in either mode was handed a paragraph they
    could not read. The same defect was already fixed in
    build_not_a_problem_message and build_off_topic_message; this builder was
    missed.
    """
    import re as _re

    from api.services.visual_tutor.scope import build_out_of_scope_message

    khmer = _re.compile(r"[ក-៿]")

    english = build_out_of_scope_message("english")
    assert not khmer.search(english["display_text"])
    assert not khmer.search(english["spoken_text"])

    khmer_copy = build_out_of_scope_message("khmer")
    assert khmer.search(khmer_copy["display_text"])
    assert "This tutor is currently available" not in khmer_copy["display_text"]
    assert "This tutor is currently available" not in khmer_copy["spoken_text"]

    both = build_out_of_scope_message("bilingual")
    assert khmer.search(both["display_text"])
    assert "This tutor is currently available" in both["display_text"]


class TestAGeneralLessonStillAcceptsMathematics:
    """A lesson whose subject is "General" refused its own starter problem.

    The student app ships a "General" lesson whose starter is "3x + 4 = 19".
    check_scope only rescued an undetermined subject when the message parsed as
    a limit, so every other Grade 10-12 maths problem -- linear equations,
    derivatives, anything -- fell through to "unsupported_subject" and the
    student was told the tutor does not cover their subject while sitting in
    the tutor's own lesson.
    """

    def test_the_general_lesson_starter_problem_is_in_scope(self) -> None:
        decision = check_scope(grade=12, subject="General", message="3x + 4 = 19")

        assert decision.is_in_scope
        assert decision.subject == "mathematics"

    def test_other_general_maths_problems_are_in_scope(self) -> None:
        for message in ("solve 2x - 5 = 11", "differentiate x^2 + 3x", "factor x^2 - 9"):
            decision = check_scope(grade=12, subject="General", message=message)
            assert decision.is_in_scope, message
            assert decision.subject == "mathematics", message

    def test_khmer_maths_under_a_general_lesson_is_in_scope(self) -> None:
        decision = check_scope(grade=12, subject="General", message="ដោះស្រាយសមីការ 3x + 4 = 19")

        assert decision.is_in_scope
        assert decision.subject == "mathematics"

    def test_physics_and_chemistry_keep_their_own_subject(self) -> None:
        """Widening the maths fallback must not steal the other two subjects."""
        physics = check_scope(
            grade=12, subject="General", message="a car accelerates from rest at 2 m/s^2 for 5 s"
        )
        chemistry = check_scope(
            grade=12, subject="General", message="balance the reaction 2H2 + O2 -> 2H2O"
        )

        assert physics.subject == "physics"
        assert chemistry.subject == "chemistry"

    def test_a_genuinely_unsupported_subject_is_still_refused(self) -> None:
        biology = check_scope(grade=12, subject="General", message="what is a cell?")

        assert not biology.is_in_scope
        assert biology.refusal_reason == "unsupported_subject"
