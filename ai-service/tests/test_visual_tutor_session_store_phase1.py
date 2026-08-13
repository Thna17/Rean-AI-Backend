from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardType,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorMasterySignal,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.session_store import (
    MAX_REPLAY_SNAPSHOTS,
    _bounded_push,
    _optional_text,
    _replay_snapshot,
    _next_strategy_history,
    derive_student_model,
    evaluate_attempt_counters,
)


def test_persisted_history_uses_bounded_mongo_pushes() -> None:
    assert MAX_REPLAY_SNAPSHOTS == 40
    assert _bounded_push({"turn_id": "turn-1"}, 3) == {
        "$each": [{"turn_id": "turn-1"}],
        "$slice": -3,
    }


def test_optional_text_normalizes_flutter_numeric_grade_metadata() -> None:
    assert _optional_text(10) == "10"
    assert _optional_text(" grade-10 ") == "grade-10"
    assert _optional_text(None) is None


def _response(
    *,
    mastery_signal: VisualTutorMasterySignal,
    metadata: dict,
) -> VisualTutorTurnResponse:
    return VisualTutorTurnResponse(
        session_id="session-1",
        turn_id="turn-1",
        spoken_text="Try the next step.",
        display_text="Try the next step.",
        teaching_mode=VisualTutorTeachingMode.STEP_CHECK,
        final_answer_locked=True,
        student_task="Try the next step.",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION_STEPS),
        mastery_signal=mastery_signal,
        metadata=metadata,
    )


def test_attempt_counters_count_correct_steps_and_reset_wrong_streak() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        action=VisualTutorAction.SUBMIT_STEP,
        message="2x = 10",
    )
    response = _response(
        mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
        metadata={"validation_result": "correct_step", "input_relevance": "valid_step"},
    )

    attempts, wrong_attempts = evaluate_attempt_counters(
        request,
        response,
        is_new_problem=False,
        current_attempts=3,
        current_wrong_attempts=2,
    )

    assert attempts == 4
    assert wrong_attempts == 0


def test_attempt_counters_ignore_unrelated_and_final_answer_guesses() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        action=VisualTutorAction.SUBMIT_STEP,
        message="4",
    )

    for validation_result, input_relevance in (
        ("unrelated_numeric_input", "unrelated"),
        ("incorrect_final_answer", "possible_final_answer"),
        ("correct_final_answer_too_early", "possible_final_answer"),
    ):
        response = _response(
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata={
                "validation_result": validation_result,
                "input_relevance": input_relevance,
            },
        )
        attempts, wrong_attempts = evaluate_attempt_counters(
            request,
            response,
            is_new_problem=False,
            current_attempts=3,
            current_wrong_attempts=2,
        )

        assert attempts == 3
        assert wrong_attempts == 2


def test_student_model_uses_current_turn_mistake_history_first() -> None:
    request = VisualTutorTurnRequest(
        user_id="student-1",
        action=VisualTutorAction.SUBMIT_STEP,
        message="2x = 20",
        locale="km-KH",
    )
    response = _response(
        mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
        metadata={
            "validation_result": "wrong_step",
            "input_relevance": "valid_step",
            "misconception_type": "wrong_inverse_operation",
        },
    )
    validation_history = [
        {"mistake_category": "arithmetic_error"},
        {"misconception_type": "wrong_inverse_operation"},
    ]

    student_model = derive_student_model(
        response=response,
        request=request,
        hint_count=3,
        attempts=2,
        wrong_attempts=2,
        validation_history=validation_history,
        last_mastery_signal=response.mastery_signal,
    )

    assert student_model.understanding == "exploring"
    assert student_model.recent_mistakes == [
        "wrong_inverse_operation",
        "arithmetic_error",
    ]
    assert student_model.preferred_language == "km"
    assert student_model.recommended_depth == "simple"
    assert student_model.last_mastery_signal == "misconception"


def test_strategy_history_is_bounded_and_tracks_adaptive_fields() -> None:
    response = _response(
        mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
        metadata={
            "tutor_move": "reteach_differently",
            "board_update_mode": "patch",
            "explanation_strategy": "misconception_correction",
        },
    ).model_copy(
        update={
            "interaction": VisualTutorInteraction(
                type=VisualTutorInteractionType.TEXT_RESPONSE,
                prompt="Try describing the balance rule.",
            )
        }
    )
    previous = [
        {"turn_id": f"old-{index}", "tutor_move": "show_visual_hint"}
        for index in range(12)
    ]

    history = _next_strategy_history(
        previous_history=previous,
        response=response,
        validation_entry={"mistake_category": "sign_error"},
        timestamp="2026-07-29T00:00:00+00:00",
    )

    assert len(history) == 12
    assert history[0]["turn_id"] == "old-1"
    assert history[-1]["tutor_move"] == "reteach_differently"
    assert history[-1]["interaction_type"] == "text_response"
    assert history[-1]["mistake_category_addressed"] == "sign_error"
    assert history[-1]["board_update_mode"] == "patch"
    assert history[-1]["asked_for_student_attempt"] is True


def test_replay_snapshot_preserves_versioned_board_recovery_state() -> None:
    response = _response(
        mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
        metadata={},
    )
    snapshot = _replay_snapshot(
        response=response,
        board_version=3,
        timestamp="2026-08-09T00:00:00+00:00",
        live_snapshot={
            "teaching_board_state": {"id": "board-1", "elements": []},
            "played_action_ids": ["equation-1"],
            "hidden_element_ids": ["answer"],
            "locked_element_ids": ["answer"],
        },
    )

    assert snapshot["board_version"] == 3
    assert snapshot["turn_id"] == "turn-1"
    assert snapshot["hidden_element_ids"] == ["answer"]
