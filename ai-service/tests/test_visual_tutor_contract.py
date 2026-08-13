import pytest
from pydantic import ValidationError

from api.models.visual_tutor import (
    BoardHistoryEntry,
    CanvasElement,
    CanvasElementStyle,
    CanvasViewport,
    TeachingBoardAction,
    TeachingBoardActionType,
    TeachingBoardElement,
    TeachingBoardElementType,
    TeachingBoardGroup,
    TeachingBoardSection,
    TeachingBoardState,
    TeachingViewport,
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorCanvasState,
    VisualTutorInteraction,
    VisualTutorInteractionChoice,
    VisualTutorInteractionType,
    VisualTutorInputType,
    VisualTutorLessonState,
    VisualTutorMasterySignal,
    VisualTutorNextStudentAction,
    VisualTutorScreenState,
    VisualTutorSpeech,
    VisualTutorStageState,
    VisualTutorStudentIntent,
    VisualTutorTeachingMode,
    VisualTutorTeachingStage,
    VisualTutorTtsStatus,
    VisualTutorBehavior,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
    VisualTutorVisualFocus,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn


def test_orchestrator_enforces_one_active_student_task_and_loop_metadata() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            session_id="session-1",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    active = [
        action for action in response.board_actions if action.requires_student_response
    ]
    assert len(active) == 1
    assert response.metadata["teaching_loop"]["one_student_task"] is True
    assert response.metadata["teaching_loop"]["active_student_task_id"] == active[0].id
    assert response.metadata["teaching_loop"]["final_answer_policy"] == "hidden"


def test_visual_tutor_turn_response_serializes_contract_enums() -> None:
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        screen_state=VisualTutorScreenState.SPEAKING_WRITING,
        tutor_status="Writing...",
        spoken_text="Before solving, what should we remove first?",
        display_text="Let's isolate x one step at a time.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
        final_answer_locked=True,
        student_task="Tell me the first operation.",
        board=VisualTutorBoard(
            type=VisualTutorBoardType.EQUATION_STEPS,
            title="Linear Equation",
            items=[
                VisualTutorBoardItem(
                    label="Problem",
                    content="2x + 5 = 15",
                    status="active",
                ),
                VisualTutorBoardItem(
                    label="Step 1",
                    content="Subtract 5 from both sides",
                    status="locked",
                ),
            ],
            metadata={"concept": "linear_equation_one_variable"},
        ),
        interaction=VisualTutorInteraction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt="What should we do first?",
        ),
        allowed_actions=[
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.REQUEST_HINT,
        ],
        quick_actions=[
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.REQUEST_HINT,
        ],
        visual_focus=VisualTutorVisualFocus(
            element_id="action-1",
            group_id="group-1",
            section_id="main-board",
            description="Focus on the current equation.",
            reason="current_board_action",
        ),
        next_student_action=VisualTutorNextStudentAction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt="What should we do first?",
            input_enabled=True,
            submit_label="Submit",
            expected_answer_locked=True,
        ),
        tutor_behavior=VisualTutorBehavior(
            should_speak=True,
            should_draw=True,
            should_ask=True,
            should_wait=True,
            explanation_language="en",
            max_actions_before_wait=1,
            answer_reveal_strategy="guided_learning_locked",
        ),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata={"hint_count": 0, "current_step_index": 0},
    )

    payload = response.model_dump(mode="json")

    assert payload["teaching_mode"] == "guided_question"
    assert payload["screen_state"] == "speaking_writing"
    assert payload["tutor_status"] == "Writing..."
    assert payload["student_intent"] == "new_problem"
    assert payload["final_answer_locked"] is True
    assert payload["board"]["type"] == "equation_steps"
    assert payload["board"]["items"][1]["status"] == "locked"
    assert payload["mastery_signal"] == "exploring"
    assert payload["allowed_actions"] == ["submit_answer", "request_hint"]
    assert payload["quick_actions"] == ["submit_answer", "request_hint"]
    assert payload["visual_focus"]["element_id"] == "action-1"
    assert payload["next_student_action"]["prompt"] == "What should we do first?"
    assert (
        payload["tutor_behavior"]["answer_reveal_strategy"] == "guided_learning_locked"
    )
    assert payload["metadata"]["hint_count"] == 0


@pytest.mark.parametrize("screen_state", [state for state in VisualTutorScreenState])
def test_visual_tutor_target_screen_states_validate(
    screen_state: VisualTutorScreenState,
) -> None:
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id=f"turn-{screen_state.value}",
        screen_state=screen_state,
        tutor_status="Waiting",
        spoken_text="Let us work one step at a time.",
        display_text="Let us work one step at a time.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="Try the next step.",
        board=VisualTutorBoard(
            type=VisualTutorBoardType.FORMULA_CARD,
            title="Tutor board",
            metadata={"screen_state": screen_state.value},
        ),
        speech=VisualTutorSpeech(text="Let us work one step at a time."),
        interaction=VisualTutorInteraction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt="What should we try next?",
        ),
        allowed_actions=[VisualTutorAllowedAction.SUBMIT_ANSWER],
        quick_actions=[VisualTutorAllowedAction.SUBMIT_ANSWER],
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata={"screen_state": screen_state.value},
    )

    payload = response.model_dump(mode="json")

    assert payload["screen_state"] == screen_state.value
    assert payload["tutor_status"] == "Waiting"
    assert payload["speech"]["text"] == "Let us work one step at a time."
    assert payload["board"]["metadata"]["screen_state"] == screen_state.value
    assert payload["interaction"]["type"] == "text_response"
    assert payload["quick_actions"] == ["submit_answer"]
    assert payload["metadata"]["screen_state"] == screen_state.value


def test_visual_tutor_canvas_action_serializes_contract() -> None:
    action = VisualTutorCanvasAction(
        id="action-1",
        type=VisualTutorCanvasActionType.WRITE_EQUATION,
        x=40,
        y=72,
        width=320,
        height=48,
        text="Step 1",
        latex="2x = 10",
        points=[{"x": 40, "y": 72}, {"x": 220, "y": 72}],
        target_id="step-1",
        style=CanvasElementStyle(
            color="#FFFFFF",
            stroke_color="#22D3EE",
            stroke_width=2,
            font_size=22,
            font_weight="700",
            opacity=0.95,
            dashed=True,
        ),
        locked=True,
        reveal_policy="after_current_step",
        metadata={"source": "solver"},
    )

    payload = action.model_dump(mode="json")

    assert payload["id"] == "action-1"
    assert payload["type"] == "write_equation"
    assert payload["latex"] == "2x = 10"
    assert payload["points"][1]["x"] == 220
    assert payload["style"]["stroke_width"] == 2
    assert payload["locked"] is True
    assert payload["reveal_policy"] == "after_current_step"


def test_visual_tutor_canvas_state_serializes_locked_element() -> None:
    state = VisualTutorCanvasState(
        viewport=CanvasViewport(width=900, height=560, x=0, y=0, scale=1),
        elements=[
            CanvasElement(
                id="problem",
                type="equation",
                x=40,
                y=40,
                latex="2x + 5 = 15",
                style=CanvasElementStyle(font_size=24),
            ),
            CanvasElement(
                id="final-answer",
                type="equation",
                x=40,
                y=180,
                latex="x = 5",
                locked=True,
                reveal_policy="final_answer_unlocked",
                metadata={"is_final_answer": True},
            ),
        ],
        focus_element_id="problem",
        locked_element_ids=["final-answer"],
        metadata={"canvas_version": "visual_tutor_canvas_v1"},
    )

    payload = state.model_dump(mode="json")

    assert payload["viewport"]["width"] == 900
    assert payload["elements"][1]["locked"] is True
    assert payload["elements"][1]["reveal_policy"] == "final_answer_unlocked"
    assert payload["locked_element_ids"] == ["final-answer"]


def test_visual_tutor_response_serializes_canvas_fields() -> None:
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="First, look at the constant term.",
        display_text="Focus on +5 first.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="What operation removes +5?",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
        canvas=VisualTutorCanvasState(
            elements=[
                CanvasElement(
                    id="equation-1",
                    type="equation",
                    x=32,
                    y=40,
                    latex="2x + 5 = 15",
                )
            ],
            focus_element_id="equation-1",
        ),
        canvas_actions=[
            VisualTutorCanvasAction(
                id="action-1",
                type=VisualTutorCanvasActionType.WRITE_EQUATION,
                x=32,
                y=40,
                latex="2x + 5 = 15",
            ),
            VisualTutorCanvasAction(
                id="action-2",
                type=VisualTutorCanvasActionType.HIGHLIGHT,
                target_id="+5",
                metadata={"reason": "remove_constant"},
            ),
        ],
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
    )

    payload = response.model_dump(mode="json")

    assert payload["canvas"]["focus_element_id"] == "equation-1"
    assert payload["canvas_actions"][0]["type"] == "write_equation"
    assert payload["canvas_actions"][1]["type"] == "highlight"


def test_visual_tutor_canvas_action_rejects_unknown_action_type() -> None:
    with pytest.raises(ValidationError):
        VisualTutorCanvasAction(id="action-1", type="teleport")


def test_visual_tutor_response_remains_compatible_without_canvas() -> None:
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Let's work on this together.",
        display_text="Let's work on this together.",
        teaching_mode=VisualTutorTeachingMode.HINT,
        final_answer_locked=True,
        student_task="Try one step.",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION),
        mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
    )

    payload = response.model_dump(mode="json")

    assert payload["canvas"] is None
    assert payload["canvas_actions"] == []
    assert payload["speech"] is None
    assert payload["teaching_stage"] is None
    assert payload["board_actions"] == []
    assert payload["teaching_board"] is None
    assert payload["teaching_board_history"] == []
    assert payload["interaction"] is None
    assert payload["allowed_actions"] == []


def test_teaching_board_state_serializes_spatial_elements() -> None:
    action = TeachingBoardAction(
        id="create-delta-y",
        type=TeachingBoardActionType.CREATE,
        sequence_index=0,
        duration_ms=700,
        element=TeachingBoardElement(
            id="delta-y-equation",
            type=TeachingBoardElementType.EQUATION,
            x=460,
            y=150,
            width=360,
            height=56,
            content={"role": "fill_blank"},
            text="Delta y = 3 - 1 = ?",
            latex=r"\Delta y = 3 - 1 = ?",
            group_id="delta-y",
            section_id="main-board",
            z_index=4,
            focus=True,
            created_turn_id="turn-1",
            metadata={"expected_response": "2"},
        ),
    )
    state = TeachingBoardState(
        id="board-session-1",
        viewport=TeachingViewport(width=1200, height=800, x=-100, y=40, scale=0.8),
        sections=[
            TeachingBoardSection(
                id="main-board",
                label="Main board",
                width=900,
                height=600,
                group_ids=["delta-y"],
            )
        ],
        groups=[
            TeachingBoardGroup(
                id="delta-y",
                label="Vertical change",
                element_ids=["delta-y-equation"],
            )
        ],
        elements=[action.element],
        actions=[action],
        history=[
            BoardHistoryEntry(
                id="history-1",
                turn_id="turn-1",
                action=action,
                snapshot_element_ids=["delta-y-equation"],
            )
        ],
        active_section_id="main-board",
    )

    payload = state.model_dump(mode="json")

    assert payload["viewport"]["scale"] == 0.8
    assert payload["elements"][0]["type"] == "equation"
    assert payload["elements"][0]["focus"] is True
    assert payload["groups"][0]["element_ids"] == ["delta-y-equation"]
    assert payload["sections"][0]["group_ids"] == ["delta-y"]
    assert payload["actions"][0]["type"] == "create"
    assert payload["history"][0]["snapshot_element_ids"] == ["delta-y-equation"]
    assert payload["focus_element_id"] == "delta-y-equation"


def test_teaching_board_locked_hidden_elements_are_indexed() -> None:
    state = TeachingBoardState(
        elements=[
            TeachingBoardElement(
                id="future-final-answer",
                type=TeachingBoardElementType.EQUATION,
                x=40,
                y=260,
                latex="x = 5",
                locked=True,
                hidden=True,
                faded=True,
                metadata={"is_final_answer": True},
            )
        ]
    )

    payload = state.model_dump(mode="json")

    assert payload["elements"][0]["locked"] is True
    assert payload["elements"][0]["hidden"] is True
    assert payload["locked_element_ids"] == ["future-final-answer"]
    assert payload["hidden_element_ids"] == ["future-final-answer"]
    assert payload["faded_element_ids"] == ["future-final-answer"]


def test_teaching_board_rejects_unknown_element_type() -> None:
    with pytest.raises(ValidationError):
        TeachingBoardElement(id="bad-element", type="flutter_widget")


def test_teaching_board_rejects_unknown_action_type() -> None:
    with pytest.raises(ValidationError):
        TeachingBoardAction(id="bad-action", type="run_code")


def test_teaching_board_action_validation_requires_targets() -> None:
    with pytest.raises(ValidationError):
        TeachingBoardAction(
            id="create-without-element",
            type=TeachingBoardActionType.CREATE,
        )

    with pytest.raises(ValidationError):
        TeachingBoardAction(
            id="update-without-target",
            type=TeachingBoardActionType.UPDATE,
            updates={"text": "New text"},
        )

    with pytest.raises(ValidationError):
        TeachingBoardAction(
            id="clear-without-section",
            type=TeachingBoardActionType.CLEAR_SECTION,
        )


def test_visual_tutor_response_serializes_teaching_board_without_breaking_canvas() -> (
    None
):
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Let's look at the point.",
        display_text="Point D is on the board.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="What is the y-value?",
        board=VisualTutorBoard(type=VisualTutorBoardType.COORDINATE_POINTS),
        canvas=VisualTutorCanvasState(
            elements=[
                CanvasElement(
                    id="legacy-point-d",
                    type="point",
                    points=[{"label": "D", "x": 0, "y": 1}],
                )
            ]
        ),
        canvas_actions=[
            VisualTutorCanvasAction(
                id="legacy-draw-point",
                type=VisualTutorCanvasActionType.DRAW_POINT,
                points=[{"label": "D", "x": 0, "y": 1}],
            )
        ],
        teaching_board=TeachingBoardState(
            elements=[
                TeachingBoardElement(
                    id="point-d",
                    type=TeachingBoardElementType.POINT,
                    points=[{"label": "D", "x": 0, "y": 1}],
                    focus=True,
                )
            ]
        ),
        teaching_board_history=[
            BoardHistoryEntry(
                id="history-1",
                turn_id="turn-1",
                action=TeachingBoardAction(
                    id="create-point-d",
                    type=TeachingBoardActionType.CREATE,
                    element=TeachingBoardElement(
                        id="point-d",
                        type=TeachingBoardElementType.POINT,
                        points=[{"label": "D", "x": 0, "y": 1}],
                    ),
                ),
            )
        ],
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
    )

    payload = response.model_dump(mode="json")

    assert payload["canvas_actions"][0]["type"] == "draw_point"
    assert payload["teaching_board"]["elements"][0]["type"] == "point"
    assert payload["teaching_board"]["focus_element_id"] == "point-d"
    assert payload["teaching_board_history"][0]["action"]["type"] == "create"


def test_visual_tutor_live_teaching_stage_response_serializes() -> None:
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="From D to E, how much does y increase?",
        display_text="Find the vertical change first.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="Type the value of delta y.",
        board=VisualTutorBoard(type=VisualTutorBoardType.COORDINATE_POINTS),
        speech=VisualTutorSpeech(
            text="From D to E, how much does y increase?",
            language="en",
            voice_id="math-tutor",
            tts_status=VisualTutorTtsStatus.PENDING,
            speak_after_action_id="draw-points",
            pause_after_ms=600,
        ),
        teaching_stage=VisualTutorTeachingStage(
            stage_state=VisualTutorStageState.WAITING_FOR_STUDENT,
            lesson_state=VisualTutorLessonState.ASK,
            current_focus="delta_y",
            turn_goal="Check whether the student can identify vertical change.",
            max_actions_before_wait=2,
        ),
        board_actions=[
            VisualTutorBoardAction(
                id="draw-points",
                type=VisualTutorCanvasActionType.DRAW_POINT,
                sequence_index=0,
                duration_ms=400,
                points=[
                    {"label": "D", "x": 0, "y": 1},
                    {"label": "E", "x": 1, "y": 3},
                ],
                group_id="points",
                section_id="main-board",
            ),
            VisualTutorBoardAction(
                id="write-dy",
                type=VisualTutorCanvasActionType.WRITE_EQUATION,
                sequence_index=1,
                duration_ms=700,
                wait_for_speech_marker=True,
                requires_student_response=True,
                latex=r"\Delta y = 3 - 1 = ?",
                target_id="delta_y",
            ),
        ],
        interaction=VisualTutorInteraction(
            type=VisualTutorInteractionType.NUMERIC_INPUT,
            prompt="What is 3 - 1?",
            expected_answer_locked=True,
            validation_strategy="numeric_exact",
            input_enabled=True,
            submit_label="Check",
        ),
        allowed_actions=[
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.REQUEST_HINT,
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.STUCK,
        ],
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
    )

    payload = response.model_dump(mode="json")

    assert payload["speech"]["tts_status"] == "pending"
    assert payload["teaching_stage"]["stage_state"] == "waiting_for_student"
    assert payload["teaching_stage"]["lesson_state"] == "ask"
    assert payload["board_actions"][0]["type"] == "draw_point"
    assert payload["board_actions"][1]["sequence_index"] == 1
    assert payload["board_actions"][1]["requires_student_response"] is True
    assert payload["interaction"]["type"] == "numeric_input"
    assert payload["interaction"]["expected_answer_locked"] is True
    assert payload["allowed_actions"] == [
        "submit_answer",
        "request_hint",
        "explain_differently",
        "stuck",
    ]


def test_visual_tutor_board_action_rejects_unknown_action_type() -> None:
    with pytest.raises(ValidationError):
        VisualTutorBoardAction(id="action-1", type="draw_everything")


def test_visual_tutor_interaction_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        VisualTutorInteraction(type="free_draw", prompt="Draw your answer.")


def test_visual_tutor_multiple_choice_interaction_requires_choices() -> None:
    with pytest.raises(ValidationError):
        VisualTutorInteraction(
            type=VisualTutorInteractionType.MULTIPLE_CHOICE,
            prompt="Which operation removes +5?",
        )

    interaction = VisualTutorInteraction(
        type=VisualTutorInteractionType.MULTIPLE_CHOICE,
        prompt="Which operation removes +5?",
        choices=[
            VisualTutorInteractionChoice(
                id="subtract-5",
                label="Subtract 5",
                value="subtract_5",
            )
        ],
    )

    assert interaction.choices[0].value == "subtract_5"


def test_live_stage_locked_canvas_element_serializes_without_unlocking_answer() -> None:
    action = VisualTutorBoardAction(
        id="future-final-answer",
        type=VisualTutorCanvasActionType.WRITE_EQUATION,
        sequence_index=3,
        latex="x = 5",
        locked=True,
        reveal_policy="final_answer_unlocked",
        metadata={"is_final_answer": True},
    )

    payload = action.model_dump(mode="json")

    assert payload["locked"] is True
    assert payload["reveal_policy"] == "final_answer_unlocked"
    assert payload["metadata"]["is_final_answer"] is True


def test_visual_tutor_turn_request_serializes_defaults_and_state() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
        message="2x + 5 = 15",
        input_type=VisualTutorInputType.TEXT,
        locale="km-KH",
    )

    payload = request.model_dump(mode="json")

    assert payload["subject"] == "Mathematics"
    assert payload["action"] == "submit_problem"
    assert payload["student_intent"] == "new_problem"
    assert payload["input_type"] == "text"
    assert payload["current_state"]["current_step_index"] == 0
    assert payload["current_state"]["hint_count"] == 0
    assert payload["current_state"]["final_answer_revealed"] is False


@pytest.mark.parametrize(
    "teaching_mode",
    [
        VisualTutorTeachingMode.GREETING,
        VisualTutorTeachingMode.DIAGNOSE_PROBLEM,
        VisualTutorTeachingMode.GUIDED_QUESTION,
        VisualTutorTeachingMode.HINT,
        VisualTutorTeachingMode.STEP_CHECK,
        VisualTutorTeachingMode.PARTIAL_SOLUTION,
        VisualTutorTeachingMode.FULL_SOLUTION,
        VisualTutorTeachingMode.MISCONCEPTION_FIX,
        VisualTutorTeachingMode.STUCK_HELP,
    ],
)
def test_visual_tutor_response_allows_required_teaching_modes(
    teaching_mode: VisualTutorTeachingMode,
) -> None:
    response = VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Let's work on this together.",
        display_text="Let's work on this together.",
        teaching_mode=teaching_mode,
        final_answer_locked=True,
        student_task="Try one step.",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
    )

    assert response.teaching_mode == teaching_mode


@pytest.mark.parametrize(
    "board_type",
    [
        VisualTutorBoardType.EQUATION,
        VisualTutorBoardType.EQUATION_STEPS,
        VisualTutorBoardType.FORMULA_CARD,
        VisualTutorBoardType.GRAPH_HINT,
        VisualTutorBoardType.TABLE,
        VisualTutorBoardType.COORDINATE_POINTS,
        VisualTutorBoardType.WORD_PROBLEM_BREAKDOWN,
        VisualTutorBoardType.MISCONCEPTION_CARD,
    ],
)
def test_visual_tutor_board_allows_required_board_types(
    board_type: VisualTutorBoardType,
) -> None:
    board = VisualTutorBoard(type=board_type)

    assert board.model_dump(mode="json")["type"] == board_type.value


def test_visual_tutor_response_rejects_unknown_teaching_mode() -> None:
    with pytest.raises(ValidationError):
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="Try again.",
            display_text="Try again.",
            teaching_mode="direct_answer",
            final_answer_locked=True,
            student_task="Try one step.",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
        )


@pytest.mark.parametrize(
    "student_intent",
    [
        VisualTutorStudentIntent.NEW_PROBLEM,
        VisualTutorStudentIntent.SUBMITTED_STEP,
        VisualTutorStudentIntent.REQUEST_HINT,
        VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
        VisualTutorStudentIntent.REQUEST_ANSWER,
        VisualTutorStudentIntent.STUCK,
        VisualTutorStudentIntent.CLARIFICATION,
        VisualTutorStudentIntent.UNKNOWN,
    ],
)
def test_visual_tutor_request_allows_required_student_intents(
    student_intent: VisualTutorStudentIntent,
) -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        message="I am stuck",
        student_intent=student_intent,
    )

    assert request.model_dump(mode="json")["student_intent"] == student_intent.value


def test_visual_tutor_request_rejects_unknown_student_intent() -> None:
    with pytest.raises(ValidationError):
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            student_intent="lost",
        )


def test_visual_tutor_stuck_turn_response_exposes_intent_metadata() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            action=VisualTutorAction.SUBMIT_STEP,
            student_submitted_step=True,
            current_state={
                "problem_text": "2x + 5 = 15",
                "normalized_problem": "2*x + 5 = 15",
            },
        )
    )
    payload = response.model_dump(mode="json")

    assert payload["student_intent"] == "stuck"
    assert payload["teaching_mode"] == "stuck_help"
    assert payload["metadata"]["detected_intent"] == "stuck"
    assert payload["metadata"]["student_intent"] == "stuck"
    assert payload["metadata"]["stuck_reason"] == "stuck_phrase"
    assert payload["metadata"]["policy"]["detected_intent"] == "stuck"


def test_off_topic_unsupported_prompt_returns_friendly_unsupported_screen() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="draw a dragon riding a bicycle",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
        )
    )

    assert response.screen_state.value == "unsupported_problem"
    assert response.board.metadata["screen_state"] == "unsupported_problem"
    assert response.board.metadata["raw_error_hidden"] is True
    assert response.interaction is not None
    assert response.interaction.input_enabled is False
    assert "technical" not in response.spoken_text.lower()


def test_unsupported_math_still_uses_teaching_fallback() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            student_intent=VisualTutorStudentIntent.NEW_PROBLEM,
        )
    )

    assert response.screen_state.value != "unsupported_problem"
    assert response.metadata["planner"] == "visual_tutor_llm_teaching_planner_v1"
    assert response.board_actions
    assert response.interaction is not None


def test_visual_tutor_board_rejects_unknown_board_type() -> None:
    with pytest.raises(ValidationError):
        VisualTutorBoard(type="animation")


def test_visual_tutor_response_requires_student_visible_text() -> None:
    with pytest.raises(ValidationError):
        VisualTutorTurnResponse(
            session_id="session-1",
            turn_id="turn-1",
            spoken_text="",
            display_text="",
            teaching_mode=VisualTutorTeachingMode.HINT,
            final_answer_locked=True,
            student_task="",
            board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
        )
