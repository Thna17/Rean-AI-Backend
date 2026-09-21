from __future__ import annotations

import json

from api.models.visual_tutor import (
    BoardHistoryEntry,
    CanvasElement,
    TeachingBoardAction,
    TeachingBoardActionType,
    TeachingBoardElement,
    TeachingBoardElementType,
    TeachingBoardState,
    VisualTutorAllowedAction,
    VisualTutorBoardAction,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorCanvasState,
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorInteraction,
    VisualTutorInteractionChoice,
    VisualTutorInteractionType,
    VisualTutorMasterySignal,
    VisualTutorSpeech,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
    VisualTutorTurnState,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.response_sanitizer import (
    sanitize_visual_tutor_response,
)

import pytest

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


class FakeVisualTutorLLMClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        return json.dumps(self.payload, ensure_ascii=False)


def _llm_payload_with_leak() -> dict:
    return {
        "spoken_text": "Final answer is a = 10 - b.",
        "display_text": "Answer: a = 10 - b",
        "teaching_mode": "full_solution",
        "student_task": "Copy a = 10 - b.",
        "board": {
            "type": "formula_card",
            "title": "Problem setup",
            "items": [
                {
                    "label": "Given",
                    "content": "a = 10 - b",
                    "status": "active",
                    "metadata": {},
                }
            ],
            "metadata": {},
        },
        "canvas_actions": [
            {
                "id": "mock-llm-leak",
                "type": "write_text",
                "x": 40,
                "y": 80,
                "width": 520,
                "height": 48,
                "text": "a = 10 - b",
                "metadata": {"is_final_answer": True},
            }
        ],
        "mastery_signal": "exploring",
        "metadata": {"source": "mock_llm"},
    }


def test_llm_final_answer_leak_is_removed_while_locked() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="English",
            message="Fix this sentence grammar",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=FakeVisualTutorLLMClient(_llm_payload_with_leak()),
    )

    combined = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(item.content for item in response.board.items),
        ]
    )
    assert response.final_answer_locked is True
    assert "10 - b" not in combined
    assert response.metadata["sanitization"]["applied"] is True
    assert "spoken_text" in response.metadata["sanitization"]["fields"]
    assert "display_text" in response.metadata["sanitization"]["fields"]


def test_board_final_answer_is_hidden_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try the next step first.",
            display_text="Try the next step first.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="What operation should happen first?",
            board=VisualTutorBoard(
                type=VisualTutorBoardType.EQUATION_STEPS,
                title="Linear equation",
                items=[
                    VisualTutorBoardItem(
                        label="Problem",
                        content="2x + 5 = 15",
                    ),
                    VisualTutorBoardItem(
                        label="Final",
                        content="x = 5",
                        status="complete",
                    ),
                ],
            ),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.board.items[-1].content == "Final answer is locked."
    assert response.board.items[-1].status == "locked"
    assert response.metadata["sanitization"]["board_item_indices"] == [1]


def test_board_title_final_answer_is_hidden_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try the next step first.",
            display_text="Try the next step first.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="What operation should happen first?",
            board=VisualTutorBoard(
                type=VisualTutorBoardType.EQUATION_STEPS,
                title="Final answer is x = 5",
            ),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.board.title == "Final answer is locked for now."
    assert response.metadata["sanitization"]["applied"] is True
    assert "board" in response.metadata["sanitization"]["fields"]


def test_student_task_does_not_contain_final_answer_while_locked() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="English",
            message="Fix this sentence grammar",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=FakeVisualTutorLLMClient(_llm_payload_with_leak()),
    )

    assert "10 - b" not in response.student_task
    assert "Copy" not in response.student_task
    assert "student_task" in response.metadata["sanitization"]["fields"]


def test_final_answer_appears_when_unlocked() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="show answer",
            action=VisualTutorAction.REQUEST_FINAL_ANSWER,
            allow_final_answer=True,
            current_state=VisualTutorTurnState(problem_text="Solve 2x + 5 = 15"),
        )
    )

    combined = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(item.content for item in response.board.items),
        ]
    )
    assert response.final_answer_locked is False
    assert "x = 5" in combined
    assert "sanitization" not in response.metadata


def test_final_answer_in_canvas_text_is_redacted_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try the current step first.",
            display_text="Try the current step first.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Remove the constant term.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            canvas_actions=[
                VisualTutorCanvasAction(
                    id="canvas-action-final-text",
                    type=VisualTutorCanvasActionType.WRITE_TEXT,
                    x=40,
                    y=120,
                    text="Final answer is x = 5",
                    metadata={"is_final_answer": True},
                )
            ],
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    action = response.canvas_actions[0]
    assert action.type == VisualTutorCanvasActionType.HIDE
    assert action.text == "Final answer is locked."
    assert action.locked is True
    assert action.metadata["hidden"] is True
    assert response.metadata["sanitization"]["canvas_action_ids"] == [
        "canvas-action-final-text"
    ]


def test_final_answer_in_canvas_latex_is_redacted_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try the current step first.",
            display_text="Try the current step first.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Remove the constant term.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            canvas=VisualTutorCanvasState(
                elements=[
                    CanvasElement(
                        id="canvas-final-latex",
                        type="equation",
                        x=40,
                        y=160,
                        latex="x = 5",
                    )
                ]
            ),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    element = response.canvas.elements[0]  # type: ignore[union-attr]
    assert element.latex == r"\text{Final answer is locked.}"
    assert element.locked is True
    assert element.metadata["hidden"] is True
    assert response.canvas.locked_element_ids == ["canvas-final-latex"]  # type: ignore[union-attr]
    assert response.metadata["sanitization"]["canvas_element_ids"] == [
        "canvas-final-latex"
    ]


def test_future_canvas_step_is_hidden_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Focus on step one.",
            display_text="Focus on step one.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Subtract 5 from both sides.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            canvas_actions=[
                VisualTutorCanvasAction(
                    id="future-step",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    x=40,
                    y=220,
                    latex="x = 5",
                    reveal_policy="final_answer_unlocked",
                    metadata={"future_step": True},
                )
            ],
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    action = response.canvas_actions[0]
    assert action.type == VisualTutorCanvasActionType.HIDE
    assert action.locked is True
    assert action.reveal_policy == "final_answer_unlocked"
    assert action.metadata["hidden"] is True


def test_current_canvas_hint_remains_visible_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Look at the constant term.",
            display_text="Look at the constant term.",
            teaching_mode=VisualTutorTeachingMode.HINT,
            final_answer_locked=True,
            student_task="What removes +5?",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            canvas_actions=[
                VisualTutorCanvasAction(
                    id="current-hint",
                    type=VisualTutorCanvasActionType.WRITE_TEXT,
                    x=40,
                    y=100,
                    text="Hint: subtract 5 from both sides.",
                    metadata={"current_step": True},
                ),
                VisualTutorCanvasAction(
                    id="current-step",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    x=40,
                    y=150,
                    latex="2x = 10",
                    metadata={"current_step": True},
                ),
            ],
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
        )
    )

    assert response.canvas_actions[0].type == VisualTutorCanvasActionType.WRITE_TEXT
    assert response.canvas_actions[0].text == "Hint: subtract 5 from both sides."
    assert response.canvas_actions[1].type == VisualTutorCanvasActionType.WRITE_EQUATION
    assert response.canvas_actions[1].latex == "2x = 10"
    assert "sanitization" not in response.metadata


def test_canvas_final_answer_appears_when_unlocked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Now we can show the full solution.",
            display_text="Now we can show the full solution.",
            teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
            final_answer_locked=False,
            student_task="Check the answer in the original equation.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            canvas_actions=[
                VisualTutorCanvasAction(
                    id="final-answer",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    x=40,
                    y=220,
                    latex="x = 5",
                    metadata={"is_final_answer": True},
                )
            ],
            mastery_signal=VisualTutorMasterySignal.MASTERED,
        )
    )

    assert response.canvas_actions[0].type == VisualTutorCanvasActionType.WRITE_EQUATION
    assert response.canvas_actions[0].latex == "x = 5"
    assert "sanitization" not in response.metadata


def test_live_stage_visible_fields_are_sanitized_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try the current step first.",
            display_text="Try the current step first.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Remove the constant term.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            speech=VisualTutorSpeech(text="Final answer is x = 5"),
            board_actions=[
                VisualTutorBoardAction(
                    id="live-final-answer",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    sequence_index=1,
                    latex="x = 5",
                    metadata={"is_final_answer": True},
                )
            ],
            interaction=VisualTutorInteraction(
                type=VisualTutorInteractionType.MULTIPLE_CHOICE,
                prompt="Which choice gives the final answer?",
                choices=[
                    VisualTutorInteractionChoice(
                        id="choice-final",
                        label="Answer is x = 5",
                        value="x = 5",
                    )
                ],
                expected_answer_locked=True,
            ),
            allowed_actions=[VisualTutorAllowedAction.REQUEST_HINT],
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.speech is not None
    assert response.speech.text == "Final answer is locked for now."
    assert response.board_actions[0].type == VisualTutorCanvasActionType.HIDE
    assert response.board_actions[0].latex == r"\text{Final answer is locked.}"
    assert response.interaction is not None
    assert response.interaction.choices[0].label == "Final answer is locked for now."
    assert response.interaction.choices[0].value == "Final answer is locked for now."
    assert response.metadata["sanitization"]["fields"] == [
        "board_actions",
        "interaction",
        "speech",
    ]
    assert response.metadata["sanitization"]["board_action_ids"] == [
        "live-final-answer"
    ]


def test_final_answer_in_board_action_text_is_hidden_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try one step first.",
            display_text="Try one step first.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Write the reasoning step.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            board_actions=[
                VisualTutorBoardAction(
                    id="board-action-final-text",
                    type=VisualTutorCanvasActionType.WRITE_TEXT,
                    text="Final answer is x = 5",
                )
            ],
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.board_actions[0].type == VisualTutorCanvasActionType.HIDE
    assert response.board_actions[0].text == "Final answer is locked."
    assert response.board_actions[0].locked is True
    assert response.metadata["sanitization"]["board_action_ids"] == [
        "board-action-final-text"
    ]


def test_final_answer_in_board_action_latex_is_hidden_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try one step first.",
            display_text="Try one step first.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Write the reasoning step.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            board_actions=[
                VisualTutorBoardAction(
                    id="board-action-final-latex",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    latex="x = 5",
                )
            ],
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.board_actions[0].type == VisualTutorCanvasActionType.HIDE
    assert response.board_actions[0].latex == r"\text{Final answer is locked.}"
    assert response.board_actions[0].locked is True


def test_final_answer_in_interaction_choice_is_hidden_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Choose the next reasoning step.",
            display_text="Choose the next reasoning step.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Choose the next step.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            interaction=VisualTutorInteraction(
                type=VisualTutorInteractionType.MULTIPLE_CHOICE,
                prompt="Which one should we avoid copying?",
                choices=[
                    VisualTutorInteractionChoice(
                        id="leaked-answer",
                        label="The answer is x = 5",
                        value="x = 5",
                    )
                ],
            ),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.interaction is not None
    assert response.interaction.choices[0].label == "Final answer is locked for now."
    assert response.interaction.choices[0].value == "Final answer is locked for now."
    assert "interaction" in response.metadata["sanitization"]["fields"]


def test_formula_cards_are_not_removed_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Use the formula card.",
            display_text="Use the formula card.",
            teaching_mode=VisualTutorTeachingMode.HINT,
            final_answer_locked=True,
            student_task="Choose the values for m and b.",
            board=VisualTutorBoard(
                type=VisualTutorBoardType.FORMULA_CARD,
                items=[
                    VisualTutorBoardItem(
                        label="Formula",
                        content="y = mx + b",
                        metadata={"content_type": "formula"},
                    )
                ],
            ),
            board_actions=[
                VisualTutorBoardAction(
                    id="formula-action",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    latex="y = mx + b",
                    metadata={"canvas_card_type": "formula_card"},
                )
            ],
            metadata={"formulas": ["y = mx + b"]},
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
        )
    )

    assert response.board.items[0].content == "y = mx + b"
    assert response.board_actions[0].type == VisualTutorCanvasActionType.WRITE_EQUATION
    assert response.board_actions[0].latex == "y = mx + b"
    assert response.metadata["formulas"] == ["y = mx + b"]
    assert "sanitization" not in response.metadata


def test_slope_formula_is_not_removed_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Use the slope formula.",
            display_text="Use the slope formula.",
            teaching_mode=VisualTutorTeachingMode.HINT,
            final_answer_locked=True,
            student_task="Substitute the point values.",
            board=VisualTutorBoard(type=VisualTutorBoardType.FORMULA_CARD),
            board_actions=[
                VisualTutorBoardAction(
                    id="slope-formula-action",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    latex="m = (y2 - y1) / (x2 - x1)",
                    metadata={"canvas_card_type": "formula_card"},
                )
            ],
            metadata={"formulas": ["m = (y2 - y1) / (x2 - x1)"]},
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
        )
    )

    assert response.board_actions[0].type == VisualTutorCanvasActionType.WRITE_EQUATION
    assert response.board_actions[0].latex == "m = (y2 - y1) / (x2 - x1)"
    assert response.metadata["formulas"] == ["m = (y2 - y1) / (x2 - x1)"]
    assert "sanitization" not in response.metadata


def test_regression_formula_is_not_removed_while_locked() -> None:
    formula = "m = Σ((x - x̄)(y - ȳ)) / Σ((x - x̄)^2)"
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Use the regression slope formula.",
            display_text="Use the regression slope formula.",
            teaching_mode=VisualTutorTeachingMode.HINT,
            final_answer_locked=True,
            student_task="Start by making a table of x, y, and xy.",
            board=VisualTutorBoard(type=VisualTutorBoardType.FORMULA_CARD),
            board_actions=[
                VisualTutorBoardAction(
                    id="regression-formula",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    latex=formula,
                    metadata={"canvas_card_type": "formula_card"},
                )
            ],
            metadata={"formulas": [formula]},
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
        )
    )

    assert response.board_actions[0].latex == formula
    assert response.metadata["formulas"] == [formula]
    assert "sanitization" not in response.metadata


def test_interaction_choice_final_answer_is_hidden_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Choose the next operation.",
            display_text="Choose the next operation.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Which choice is a next step?",
            board=VisualTutorBoard(type=VisualTutorBoardType.FORMULA_CARD),
            interaction=VisualTutorInteraction(
                type=VisualTutorInteractionType.MULTIPLE_CHOICE,
                prompt="Do not choose the final answer yet.",
                choices=[
                    VisualTutorInteractionChoice(
                        id="a",
                        label="x = 5",
                        value="x = 5",
                    ),
                    VisualTutorInteractionChoice(
                        id="b",
                        label="subtract 5",
                        value="subtract 5",
                    ),
                ],
            ),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.interaction is not None
    assert response.interaction.choices[0].label == "Final answer is locked for now."
    assert response.interaction.choices[0].value == "Final answer is locked for now."
    assert response.interaction.choices[1].label == "subtract 5"
    assert "interaction" in response.metadata["sanitization"]["fields"]


def test_teaching_board_final_answer_and_metadata_are_sanitized_while_locked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try the current step.",
            display_text="Try the current step.",
            teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
            final_answer_locked=True,
            student_task="Write the next step.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            teaching_board=TeachingBoardState(
                elements=[
                    TeachingBoardElement(
                        id="teaching-final",
                        type=TeachingBoardElementType.EQUATION,
                        latex="x = 5",
                        metadata={
                            "source": "curriculum_worked_example",
                            "worked_example_final_answer": True,
                        },
                    )
                ],
                actions=[
                    TeachingBoardAction(
                        id="reveal-final",
                        type=TeachingBoardActionType.REVEAL,
                        target_id="teaching-final",
                        metadata={"solution_level": "final"},
                    )
                ],
            ),
            teaching_board_history=[
                BoardHistoryEntry(
                    id="history-final",
                    turn_id="turn-1",
                    action=TeachingBoardAction(
                        id="create-history-final",
                        type=TeachingBoardActionType.CREATE,
                        element=TeachingBoardElement(
                            id="history-final-element",
                            type=TeachingBoardElementType.EQUATION,
                            latex="x = 5",
                            metadata={"is_final_answer": True},
                        ),
                    ),
                    metadata={"summary": "Final answer is x = 5"},
                )
            ],
            metadata={
                "summary": "The final answer is x = 5",
                "curriculum_context": {
                    "worked_example": {"final_answer": "x = 5"},
                    "formula": "y = mx + b",
                },
            },
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )
    )

    assert response.teaching_board is not None
    element = response.teaching_board.elements[0]
    assert element.locked is True
    assert element.hidden is True
    assert element.latex == r"\text{Final answer is locked.}"
    assert response.teaching_board.actions[0].type == TeachingBoardActionType.HIDE
    assert response.teaching_board.actions[0].locked is True
    assert (
        response.teaching_board_history[0].action.type == TeachingBoardActionType.HIDE
    )
    assert response.metadata["summary"] == "Final answer is locked for now."
    assert (
        response.metadata["curriculum_context"]["worked_example"]["final_answer"]
        == "Final answer is locked for now."
    )
    assert response.metadata["curriculum_context"]["formula"] == "y = mx + b"
    assert response.metadata["sanitization"]["teaching_board_element_ids"] == [
        "teaching-final"
    ]


def test_final_answer_in_live_fields_appears_when_unlocked() -> None:
    response = sanitize_visual_tutor_response(
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Now the final answer is x = 5.",
            display_text="Final answer: x = 5",
            teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
            final_answer_locked=False,
            student_task="Check it.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
            speech=VisualTutorSpeech(text="The answer is x = 5"),
            board_actions=[
                VisualTutorBoardAction(
                    id="unlocked-final",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    latex="x = 5",
                )
            ],
            interaction=VisualTutorInteraction(
                type=VisualTutorInteractionType.MULTIPLE_CHOICE,
                prompt="What is the answer?",
                choices=[
                    VisualTutorInteractionChoice(
                        id="answer-choice",
                        label="x = 5",
                        value="x = 5",
                    )
                ],
            ),
            teaching_board=TeachingBoardState(
                elements=[
                    TeachingBoardElement(
                        id="unlocked-final-element",
                        type=TeachingBoardElementType.EQUATION,
                        latex="x = 5",
                    )
                ]
            ),
            metadata={"summary": "Final answer is x = 5"},
            mastery_signal=VisualTutorMasterySignal.MASTERED,
        )
    )

    assert response.speech is not None
    assert response.speech.text == "The answer is x = 5"
    assert response.board_actions[0].latex == "x = 5"
    assert response.interaction is not None
    assert response.interaction.choices[0].value == "x = 5"
    assert response.teaching_board is not None
    assert response.teaching_board.elements[0].latex == "x = 5"
    assert response.metadata["summary"] == "Final answer is x = 5"
    assert "sanitization" not in response.metadata
