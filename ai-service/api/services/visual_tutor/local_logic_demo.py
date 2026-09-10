"""Deterministic development-only moment for Grade 10 Logic lesson 1.1.

This fallback is intentionally narrow: it is selected only by the local demo
curriculum version and never turns the unpublished draft into a production
curriculum publication.  All Khmer STEM terms and the introductory explanation
are read from the supplied source draft.  The project owner's requested ``២``
check is a local exercise that reuses only those approved terms.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorCanvasActionType,
    VisualTutorInteraction,
    VisualTutorInteractionChoice,
    VisualTutorInteractionType,
    VisualTutorLessonState,
    VisualTutorMasterySignal,
    VisualTutorScreenState,
    VisualTutorSpeech,
    VisualTutorStageState,
    VisualTutorTeachingMode,
    VisualTutorTeachingStage,
    VisualTutorTtsStatus,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


_LESSON_ID = "math.g10.part1.logic.1.1.statements"
_CURRICULUM_VERSION_ID = "moeys-g10-math-part1.local-demo"
_SOURCE_ID = "moeys-math-g10-part1-2020-ch1-logic"
_SOURCE_PAGE = 9
# This is the project-owner-requested local exercise. Its technical Khmer terms
# are all listed in the official source draft's glossary.
_QUESTION_SUBJECT = "២ ជាចំនួនបឋម"
_QUESTION = f"“{_QUESTION_SUBJECT}” ជាសំណើពិត ឬមិនពិត?"


@lru_cache(maxsize=1)
def _source_moment() -> dict[str, Any]:
    path = (
        Path(__file__).resolve().parents[3]
        / "data"
        / "curriculum_drafts"
        / "grade_10_math_part1_logic_moment_01.json"
    )
    with path.open(encoding="utf-8") as file:
        moment = json.load(file)
    if (
        moment.get("lesson", {}).get("id") != _LESSON_ID
        or moment.get("source", {}).get("source_id") != _SOURCE_ID
        or moment.get("source", {}).get("pdf_page") != _SOURCE_PAGE
    ):
        raise ValueError("unexpected local Logic source draft")
    return moment


def matches_local_logic_demo(request: VisualTutorTurnRequest) -> bool:
    """Return true only for the explicitly selected development lesson."""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    return (
        metadata.get("entry_context") == "lesson"
        and metadata.get("is_curriculum_scoped") is True
        and metadata.get("grade") == 10
        and metadata.get("lesson_id") == _LESSON_ID
        and metadata.get("teaching_moment_id") == _LESSON_ID
        and metadata.get("curriculum_version_id") == _CURRICULUM_VERSION_ID
        and str(request.subject).strip().lower() == "mathematics"
        and str(request.topic or "").strip().lower() == "logic"
    )


def build_local_logic_demo_turn(
    request: VisualTutorTurnRequest,
    *,
    session_id: str,
) -> VisualTutorTurnResponse:
    """Build one source-linked, provider-independent local tutor turn.

    The answer key exists only in this server-side evaluator.  It is never
    included in a board action, teaching plan, or public metadata.
    """
    moment = _source_moment()
    if _is_opening_turn(request):
        return _opening_turn(moment, session_id=session_id)
    if request.action in {
        VisualTutorAction.REQUEST_HINT,
        VisualTutorAction.REQUEST_STUCK_HELP,
        VisualTutorAction.EXPLAIN_DIFFERENTLY,
        VisualTutorAction.REQUEST_FINAL_ANSWER,
    }:
        return _reteach_turn(moment, session_id=session_id, outcome="hint")
    if _is_correct_response(request.message):
        return _correct_turn(moment, session_id=session_id)
    return _reteach_turn(moment, session_id=session_id, outcome="incorrect")


def _is_opening_turn(request: VisualTutorTurnRequest) -> bool:
    return request.action in {
        VisualTutorAction.START,
        VisualTutorAction.SUBMIT_PROBLEM,
    }


def _is_correct_response(message: str) -> bool:
    normalized = " ".join((message or "").strip().casefold().split())
    if not normalized:
        return False
    # Check the negative phrase first because it contains the Khmer word for
    # true. English values are accepted for keyboard/voice accessibility.
    if "មិនពិត" in normalized or normalized in {"false", "f"}:
        return False
    return normalized in {"ពិត", "true", "t"}


def _opening_turn(moment: dict[str, Any], *, session_id: str) -> VisualTutorTurnResponse:
    explanation = _explanation(moment)
    spoken = f"{explanation} {_QUESTION}"
    return _response(
        moment=moment,
        session_id=session_id,
        turn_id="local-logic-moment-01",
        spoken_text=spoken,
        display_text=explanation,
        board_text=_title(moment),
        board_action_id="logic-moment-title",
        evaluation=None,
        current_step_index=0,
        lesson_state=VisualTutorLessonState.ASK,
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        task_prompt=_QUESTION,
    )


def _correct_turn(moment: dict[str, Any], *, session_id: str) -> VisualTutorTurnResponse:
    feedback = "ការឆ្លើយរបស់អ្នកត្រឹមត្រូវ។"
    return _response(
        moment=moment,
        session_id=session_id,
        turn_id="local-logic-moment-01-correct",
        spoken_text=feedback,
        display_text=feedback,
        board_text=feedback,
        board_action_id="logic-moment-correct-feedback",
        evaluation={"outcome": "correct"},
        current_step_index=1,
        lesson_state=VisualTutorLessonState.RETEACH_OR_CONTINUE,
        mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
        task_prompt="សូមបន្តទៅមេរៀនបន្ទាប់។",
        input_enabled=False,
    )


def _reteach_turn(
    moment: dict[str, Any],
    *,
    session_id: str,
    outcome: str,
) -> VisualTutorTurnResponse:
    explanation = _explanation(moment)
    return _response(
        moment=moment,
        session_id=session_id,
        turn_id=f"local-logic-moment-01-{outcome}",
        spoken_text=explanation,
        display_text=explanation,
        board_text=explanation,
        board_action_id=f"logic-moment-{outcome}-reteach",
        evaluation=(
            {"outcome": "incorrect", "misconception_category": "statement_truth_value"}
            if outcome == "incorrect"
            else {"outcome": "hint"}
        ),
        current_step_index=0,
        lesson_state=VisualTutorLessonState.RETEACH_OR_CONTINUE,
        mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
        task_prompt=_QUESTION,
    )


def _response(
    *,
    moment: dict[str, Any],
    session_id: str,
    turn_id: str,
    spoken_text: str,
    display_text: str,
    board_text: str,
    board_action_id: str,
    evaluation: dict[str, str] | None,
    current_step_index: int,
    lesson_state: VisualTutorLessonState,
    mastery_signal: VisualTutorMasterySignal,
    task_prompt: str,
    input_enabled: bool = True,
) -> VisualTutorTurnResponse:
    source = moment["source"]
    action = VisualTutorBoardAction(
        id=board_action_id,
        type=VisualTutorCanvasActionType.WRITE_TEXT,
        sequence_index=0,
        duration_ms=700,
        layout_zone="problem",
        layout_flow="vertical",
        text=board_text,
        section_id="logic-moment-01",
    )
    task_action = VisualTutorBoardAction(
        id="logic-moment-task",
        type=VisualTutorCanvasActionType.STUDENT_TASK,
        sequence_index=1,
        duration_ms=0,
        layout_zone="student_task",
        layout_flow="vertical",
        text=task_prompt,
        requires_student_response=input_enabled,
        section_id="logic-moment-01",
    )
    plan = validate_teaching_plan(
        {
            "schema_version": 1,
            "representation": "conceptual_explanation",
            "learning_objective": moment["learning_objectives"][0]["text"],
            "teaching_message": display_text,
            "board_actions": [
                {
                    "id": action.id,
                    "type": action.type.value,
                    "sequence_index": action.sequence_index,
                    "duration_ms": action.duration_ms,
                    "layout_zone": action.layout_zone.value,
                    "layout_flow": action.layout_flow.value,
                    "text": action.text,
                },
                {
                    "id": task_action.id,
                    "type": task_action.type.value,
                    "sequence_index": task_action.sequence_index,
                    "layout_zone": task_action.layout_zone.value,
                    "layout_flow": task_action.layout_flow.value,
                    "text": task_action.text,
                    "requires_student_response": True,
                    "task_type": "conceptual_operation",
                },
            ],
            "allowed_student_actions": ["submit_answer", "request_hint"],
            "hidden_answer_policy": {
                "mode": "hidden",
                "deterministic_policy_permits_final_reveal": False,
            },
            "next_state_policy": {
                "correct": "continue",
                "invalid": "reteach",
                "incomplete": "ask_for_work",
                "stuck": "reteach",
                "hint": "reteach",
                "explain_differently": "reteach",
            },
        }
    ).model_dump(mode="json")
    metadata: dict[str, Any] = {
        "local_curriculum_demo": True,
        "local_demo_label": "Local curriculum demo",
        "lesson_id": _LESSON_ID,
        "curriculum_version_id": _CURRICULUM_VERSION_ID,
        "source_id": source["source_id"],
        "source_page": source["pdf_page"],
        "waiting_for_student_input": input_enabled,
        "teaching_plan": plan,
        "evaluation": evaluation,
        "board_update_mode": "replace",
    }
    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=turn_id,
        screen_state=(
            VisualTutorScreenState.ASKING_QUESTION
            if input_enabled
            else VisualTutorScreenState.SPEAKING_WRITING
        ),
        tutor_status="Waiting for you" if input_enabled else "Ready",
        spoken_text=spoken_text,
        display_text=display_text,
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task=task_prompt,
        board=VisualTutorBoard(
            type=VisualTutorBoardType.FORMULA_CARD,
            title=_title(moment),
            items=[
                VisualTutorBoardItem(
                    label="Local curriculum demo",
                    content=_title(moment),
                    status="active",
                )
            ],
            metadata={"local_curriculum_demo": True},
        ),
        board_actions=[action, task_action],
        speech=VisualTutorSpeech(
            text=spoken_text,
            language="km",
            tts_status=VisualTutorTtsStatus.NOT_REQUESTED,
            speak_after_action_id=action.id,
            pause_after_ms=500 if input_enabled else 0,
        ),
        teaching_stage=VisualTutorTeachingStage(
            stage_state=(
                VisualTutorStageState.WAITING_FOR_STUDENT
                if input_enabled
                else VisualTutorStageState.ADAPTING
            ),
            lesson_state=lesson_state,
            current_focus=action.id,
            turn_goal=task_prompt,
            max_actions_before_wait=1,
        ),
        interaction=VisualTutorInteraction(
            type=(
                VisualTutorInteractionType.MULTIPLE_CHOICE
                if input_enabled
                else VisualTutorInteractionType.TEXT_RESPONSE
            ),
            prompt=task_prompt,
            expected_answer_locked=True,
            input_enabled=input_enabled,
            submit_label="បញ្ជូន",
            choices=(
                [
                    VisualTutorInteractionChoice(id="statement-true", label="ពិត", value="ពិត"),
                    VisualTutorInteractionChoice(id="statement-false", label="មិនពិត", value="មិនពិត"),
                ]
                if input_enabled
                else []
            ),
        ),
        allowed_actions=[
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.REQUEST_HINT,
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.STUCK,
        ],
        quick_actions=[
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.REQUEST_HINT,
        ],
        mastery_signal=mastery_signal,
        authoritative_lesson_state={
            "lesson_id": _LESSON_ID,
            "active_step_id": "logic-moment-01",
            "current_step_index": current_step_index,
            "final_answer_locked": True,
        },
        metadata=metadata,
    )


def _title(moment: dict[str, Any]) -> str:
    return str(moment["teaching_plan"]["board_actions"][0]["text"])


def _explanation(moment: dict[str, Any]) -> str:
    return str(moment["teaching_plan"]["spoken_explanation"]["text"])
