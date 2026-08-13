import pytest

from api.models.visual_tutor import (
    VisualTutorBoard,
    VisualTutorBoardType,
    VisualTutorMasterySignal,
    VisualTutorTeachingMode,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.board_contract import BOARD_SCHEMA_VERSION, validate_board_response


@pytest.mark.parametrize(
    ("fixture_name", "action_type"),
    [
        ("linear_equation", "transform_equation"),
        ("quadratic_graph", "plot_function"),
        ("slope_question", "show_number_line"),
        ("wrong_step", "show_feedback"),
        ("stuck_request", "show_hint"),
        ("unsupported_question", "write_text"),
        ("final_answer_reveal", "reveal_answer"),
    ],
)
def test_board_contract_accepts_supported_teaching_fixtures(fixture_name, action_type):
    response = VisualTutorTurnResponse(
        session_id="session-1", turn_id=fixture_name, spoken_text="Try one step.",
        display_text="Try one step.", teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True, student_task="What is the next step?",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        board_actions=[{
            "id": "a1", "type": action_type, "text": "Visual cue",
            **({"graph": {
                "x_min": -5, "x_max": 5, "y_min": -5, "y_max": 10,
                "x_label": "x", "y_label": "y", "function_expression": "x^2",
                "domain": [-5, 5], "points": [], "annotations": [],
            }} if action_type == "plot_function" else {}),
        }],
    )
    validated = validate_board_response(response)
    assert validated.metadata["board_schema_version"] == BOARD_SCHEMA_VERSION
    assert validated.board_actions[0].type.value == action_type


def test_board_contract_rejects_duplicate_actions_and_multiple_student_tasks():
    response = VisualTutorTurnResponse(
        session_id="session-1", turn_id="turn-1", spoken_text="Try one step.",
        display_text="Try one step.", teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True, student_task="What is the next step?",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        board_actions=[
            {"id": "task", "type": "student_task", "text": "First task", "requires_student_response": True},
            {"id": "task", "type": "student_task", "text": "Second task", "requires_student_response": True},
        ],
    )
    validated = validate_board_response(response)
    assert len(validated.board_actions) == 1
    assert validated.metadata["rejected_board_action_ids"] == ["task"]


def test_graph_action_requires_explicit_mathematical_payload():
    with pytest.raises(ValueError, match="complete graph payload"):
        VisualTutorTurnResponse(
            session_id="session-1", turn_id="graph", spoken_text="Look at the graph.",
            display_text="Look at the graph.", teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True, student_task="What is the slope?",
            board=VisualTutorBoard(type=VisualTutorBoardType.GRAPH_HINT),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            board_actions=[{"id": "graph", "type": "show_graph", "width": 300, "height": 200}],
        )
