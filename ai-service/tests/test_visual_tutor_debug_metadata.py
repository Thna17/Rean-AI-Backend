from __future__ import annotations

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest

from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn

import pytest

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


DEBUG_METADATA_KEYS = {
    "response_source",
    "solver_name",
    "llm_called",
    "llm_provider",
    "fallback_reason",
    "current_step_index",
    "input_relevance",
    "validation_result",
    "tutor_move",
    "policy_decision",
    "board_action_ids",
}


def test_visual_tutor_response_includes_debug_metadata() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert DEBUG_METADATA_KEYS.issubset(response.metadata)
    assert response.metadata["response_source"] in {
        "deterministic_solver",
        "llm_planner",
        "template_fallback",
        "hybrid",
    }
    assert response.metadata["solver_name"] == "LinearEquationSolver"
    assert response.metadata["llm_called"] is False
    assert response.metadata["llm_provider"] is None
    assert response.metadata["current_step_index"] == 0
    assert isinstance(response.metadata["policy_decision"], dict)
    assert isinstance(response.metadata["board_action_ids"], list)
    assert response.metadata["board_action_ids"]
    assert response.metadata["adaptive_planner_generated_response"] is True


def test_supported_math_without_configured_llm_uses_deterministic_solver() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="5a - 8 = 2a + 7",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert response.metadata["response_source"] == "deterministic_solver"
    assert response.metadata["fallback_reason"] is None
    assert response.metadata["generation_path"] == "deterministic_solver"
    assert response.metadata["adaptive_planner_generated_response"] is True
    assert response.metadata["solver_facts"]["solver_name"] == "LinearEquationSolver"


def test_visual_tutor_greeting_response_includes_debug_metadata() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(user_id="student-1", message="")
    )

    assert DEBUG_METADATA_KEYS.issubset(response.metadata)
    assert response.metadata["response_source"] == "template_fallback"
    assert response.metadata["solver_name"] is None
    assert response.metadata["llm_called"] is False
    assert response.metadata["fallback_reason"] == "structured_template_response"
