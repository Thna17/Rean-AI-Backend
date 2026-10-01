from __future__ import annotations

from api.models.curriculum import CurriculumRetrievalResult
from api.models.visual_tutor import (
    VisualTutorCanvasActionType,
    VisualTutorAction,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor import orchestrator

from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn

import pytest

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


def test_solver_board_includes_retrieved_curriculum_formula() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    formula_items = [
        item
        for item in response.board.items
        if item.label == "Formula" and item.metadata.get("source") == "curriculum"
    ]

    assert formula_items
    assert "ax + b = c" in formula_items[0].content
    assert response.board.items[-1].label == "Final"
    assert response.board.items[-1].content == "Final answer is locked."
    assert response.metadata["problem_understanding"]["problem_type"] == (
        "linear_equation_one_variable"
    )


def test_linear_equation_canvas_includes_curriculum_formula() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    formula_actions = [
        action
        for action in response.canvas_actions
        if action.metadata.get("canvas_card_type") == "formula_card"
    ]
    canvas_text = " ".join(
        value
        for action in response.canvas_actions
        for value in (action.text, action.latex)
        if value
    )

    assert formula_actions
    assert formula_actions[0].type == VisualTutorCanvasActionType.WRITE_EQUATION
    assert "ax + b = c" in canvas_text
    assert "x = 5" not in canvas_text


def test_line_through_points_canvas_uses_slope_formula() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Coordinate Geometry",
            message="Find the equation of the line through D(0,1) and E(1,3)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    canvas_text = " ".join(
        value
        for action in response.canvas_actions
        for value in (action.text, action.latex)
        if value
    )

    assert "m = (y2 - y1) / (x2 - x1)" in canvas_text
    assert "y = 2x + 1" not in canvas_text


def test_khmer_terms_render_in_canvas_metadata() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="ដោះស្រាយ 2x + 5 = 15",
            locale="km-KH",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    term_actions = [
        action
        for action in response.canvas_actions
        if action.metadata.get("canvas_card_type") == "khmer_terms"
    ]

    assert term_actions
    assert term_actions[0].metadata["khmer_terms"]["variable"] == "អថេរ"
    assert "អថេរ" in (term_actions[0].text or "")


def test_curriculum_example_answer_is_hidden_while_locked() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="Solve 2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    combined_canvas = " ".join(
        str(value)
        for action in response.canvas_actions
        for value in (action.text, action.latex)
        if value
    )
    hidden_actions = [
        action
        for action in response.canvas_actions
        if action.metadata.get("is_final_answer") is True
    ]

    assert response.final_answer_locked is True
    assert "x = 5" not in combined_canvas
    assert hidden_actions
    assert all(action.locked for action in hidden_actions)


def test_misconception_response_references_curriculum_misconception() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="50",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                normalized_problem="2*x + 5 = 15",
            ),
            metadata={"grade": 10},
        )
    )

    assert response.teaching_mode.value == "misconception_fix"
    assert "Common misconception:" in response.display_text
    assert "Changing only one side" in response.display_text
    assert response.final_answer_locked is True


def test_common_misconception_generates_canvas_card() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="50",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state=VisualTutorTurnState(
                problem_text="2x + 5 = 15",
                normalized_problem="2*x + 5 = 15",
            ),
            metadata={"grade": 10},
        )
    )

    misconception_actions = [
        action
        for action in response.canvas_actions
        if action.metadata.get("canvas_card_type") == "misconception_card"
    ]

    assert misconception_actions
    assert "Changing only one side" in (misconception_actions[0].text or "")


def test_khmer_locale_adds_curriculum_khmer_terms_to_board() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="ដោះស្រាយ 2x + 5 = 15",
            locale="km-KH",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    khmer_items = [item for item in response.board.items if item.label == "Khmer Terms"]

    assert khmer_items
    assert "សមីការលីនេអ៊ែរ" in khmer_items[0].content
    assert response.board.metadata["curriculum_khmer_terms"]["variable"] == "អថេរ"


def test_orchestrator_passes_grade_hint_to_curriculum_retriever(monkeypatch) -> None:
    seen = {}

    def fake_retrieve(request):
        seen["grade"] = request.grade
        seen["subject"] = request.subject
        seen["problem_type"] = request.problem_type
        return CurriculumRetrievalResult()

    monkeypatch.setattr(orchestrator, "retrieve_curriculum_context", fake_retrieve)

    handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Functions",
            message="Find the domain of f(x) = 1/(x - 2)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade_level_hint": "Grade 11"},
        )
    )

    assert seen["grade"] == 11
    assert seen["subject"] == "Mathematics"
    assert seen["problem_type"] in {"function_domain", "unsupported"}


def test_solver_behavior_remains_plain_when_no_curriculum_context(monkeypatch) -> None:
    monkeypatch.setattr(
        orchestrator,
        "retrieve_curriculum_context",
        lambda *args, **kwargs: CurriculumRetrievalResult(),
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        )
    )

    assert [item.label for item in response.board.items] == [
        "Problem",
        "Step 1",
        "Final",
    ]
    assert "Curriculum focus:" not in response.student_task
    assert "curriculum_enriched" not in response.board.metadata
