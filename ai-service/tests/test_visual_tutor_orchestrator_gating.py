from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn

def test_orchestrator_gating_empty_message_nudges() -> None:
    # An empty message while waiting should trigger a nudge
    request = VisualTutorTurnRequest(
        user_id="test",
        action=VisualTutorAction.START,
        message="",
        current_state=VisualTutorTurnState(problem_text="x+1=2"),
        metadata={
            "pending_interaction": {
                "type": "text_response",
                "prompt": "What is the unknown?",
                "input_enabled": True
            }
        }
    )
    response = handle_visual_tutor_turn(request)
    assert "Try answering the question" in response.spoken_text or "សូមព្យាយាមឆ្លើយសំណួរនោះជាមុនសិន" in response.spoken_text

def test_orchestrator_gating_substantive_message_bypasses() -> None:
    # Substantive message bypasses the gate
    request = VisualTutorTurnRequest(
        user_id="test",
        action=VisualTutorAction.START,
        message="This is substantive",
        current_state=VisualTutorTurnState(problem_text="x+1=2"),
        metadata={
            "pending_interaction": {
                "type": "text_response",
                "input_enabled": True
            }
        }
    )
    # The actual LLM/fallback logic takes over and should not return the nudge text
    response = handle_visual_tutor_turn(request)
    assert "Try answering the question" not in response.spoken_text

def test_orchestrator_gating_quick_action_bypasses() -> None:
    # Quick action bypasses the gate even with an empty message
    request = VisualTutorTurnRequest(
        user_id="test",
        action=VisualTutorAction.REQUEST_HINT,
        message="",
        current_state=VisualTutorTurnState(problem_text="x+1=2"),
        metadata={
            "pending_interaction": {
                "type": "text_response",
                "input_enabled": True
            }
        }
    )
    response = handle_visual_tutor_turn(request)
    assert "Try answering the question" not in response.spoken_text

def test_orchestrator_gating_tampered_metadata() -> None:
    # Tampered metadata should not crash and should bypass the gate safely
    request = VisualTutorTurnRequest(
        user_id="test",
        action=VisualTutorAction.START,
        message="",
        current_state=VisualTutorTurnState(problem_text="x+1=2"),
        metadata={
            "pending_interaction": "tampered_string" # Invalid, not a dict
        }
    )
    response = handle_visual_tutor_turn(request)
    assert "Try answering the question" not in response.spoken_text
