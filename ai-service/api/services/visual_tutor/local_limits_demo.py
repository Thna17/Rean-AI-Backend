"""Deterministic, source-linked Grade 12 Limits local MVP flow."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.models.visual_tutor import (VisualTutorAction, VisualTutorAllowedAction, VisualTutorBoard, VisualTutorBoardAction, VisualTutorBoardItem, VisualTutorBoardType, VisualTutorCanvasActionType, VisualTutorInteraction, VisualTutorInteractionType, VisualTutorLessonState, VisualTutorMasterySignal, VisualTutorScreenState, VisualTutorSpeech, VisualTutorStageState, VisualTutorTeachingMode, VisualTutorTeachingStage, VisualTutorTtsStatus, VisualTutorTurnRequest, VisualTutorTurnResponse)
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan

_LESSON_ID = "math.g12.lesson1.limits-of-functions"
_CURRICULUM_VERSION_ID = "local-g12-math-limits-2025-10-01-v1"
_MOMENT_ID = "math.g12.lesson1.limits-of-functions.finite-at-point.01"
_SOURCE_ID = "provided-pdf-2025-10-01-00007213"


@lru_cache(maxsize=1)
def _source_moment() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[3] / "data" / "curriculum_drafts" / "grade_12_math_limits_moment_01.json"
    with path.open(encoding="utf-8") as file:
        moment = json.load(file)
    if (moment.get("lesson", {}).get("id"), moment.get("teaching_moment_id"), moment.get("curriculum_version"), moment.get("source", {}).get("source_id")) != (_LESSON_ID, _MOMENT_ID, _CURRICULUM_VERSION_ID, _SOURCE_ID):
        raise ValueError("unexpected local Limits source draft")
    return moment


def matches_local_limits_demo(request: VisualTutorTurnRequest) -> bool:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    return (metadata.get("entry_context") == "lesson" and metadata.get("is_curriculum_scoped") is True and metadata.get("grade") == 12 and metadata.get("subject_id") == "math" and metadata.get("topic_id") == "math-g12-limits-of-functions" and metadata.get("lesson_id") == _LESSON_ID and metadata.get("teaching_moment_id") == _MOMENT_ID and metadata.get("curriculum_version_id") == _CURRICULUM_VERSION_ID and str(request.subject).strip().lower() == "mathematics" and str(request.topic or "").strip() == "Limits of Functions")


def build_local_limits_demo_turn(request: VisualTutorTurnRequest, *, session_id: str) -> VisualTutorTurnResponse:
    """Return one renderer-safe teaching moment; private answer forms stay here."""
    moment = _source_moment()
    step = max(0, int(request.current_state.current_step_index or 0))
    if request.action == VisualTutorAction.SUBMIT_PROBLEM:
        return _moment(moment, session_id, "observe-table", 0)
    if request.action == VisualTutorAction.START:
        if step >= 3:
            return _final(moment, session_id, reveal=request.current_state.final_answer_revealed)
        step_id = ("observe-table", "simplify-expression", "evaluate-nearby")[step]
        return _moment(moment, session_id, step_id, step)
    if request.action in {VisualTutorAction.REQUEST_HINT, VisualTutorAction.EXPLAIN_DIFFERENTLY}:
        outcome = "hint" if request.action == VisualTutorAction.REQUEST_HINT else "explain_differently"
        if step == 0:
            return _moment(moment, session_id, "simplify-expression", 1, outcome)
        return _moment(
            moment,
            session_id,
            "observe-table",
            step,
            outcome,
            task_override=_task_for_step(moment, step),
        )
    if request.action == VisualTutorAction.REQUEST_FINAL_ANSWER:
        if step <= 0:
            return _moment(moment, session_id, "simplify-expression", 1, "answer_progress_1")
        if step == 1:
            return _moment(moment, session_id, "evaluate-nearby", 2, "answer_progress_2")
        return _final(moment, session_id, reveal=True)
    if step == 0:
        return _moment(moment, session_id, "simplify-expression", 1, "correct") if _number(request.message) else _moment(moment, session_id, "observe-table", 0, _wrong(request))
    if step == 1:
        return _moment(moment, session_id, "evaluate-nearby", 2, "correct") if _expression(request.message) else _moment(moment, session_id, "simplify-expression", 1, _wrong(request))
    if step == 2:
        return _final(moment, session_id, reveal=True) if _number(request.message) else _moment(moment, session_id, "evaluate-nearby", 2, _wrong(request))
    return _final(moment, session_id)


def _wrong(request: VisualTutorTurnRequest) -> str:
    return "repeated_wrong" if (request.current_state.wrong_attempts or 0) >= 1 else "incorrect"


def _number(message: str) -> bool:
    return " ".join((message or "").strip().casefold().split()) in {"5", "៥", "five"}


def _expression(message: str) -> bool:
    return (message or "").replace(" ", "").lower() in {"2x+3", "3+2x"}


def _task_for_step(moment: dict[str, Any], step_index: int) -> str:
    step_id = ("observe-table", "simplify-expression", "evaluate-nearby")[min(step_index, 2)]
    return str(next(item for item in moment["interactive_progression"]["steps"] if item["id"] == step_id)["task"])


def _moment(moment: dict[str, Any], session_id: str, step_id: str, step_index: int, outcome: str | None = None, task_override: str | None = None) -> VisualTutorTurnResponse:
    step = next(item for item in moment["interactive_progression"]["steps"] if item["id"] == step_id)
    opening = step_id == "observe-table"
    formula = str(step.get("formula") or moment["source_formulas"][0]["expression"])
    task = task_override or str(step["task"])
    message = str(moment["teaching_plan"]["spoken_explanation"]["text"]) if opening else ""
    if outcome == "correct": message = "ត្រឹមត្រូវ។ យើងបន្តមួយជំហានទៀត។"
    if outcome == "incorrect": message = "សូមសង្កេតតែចំណុចនេះម្ដងទៀត។"
    if outcome == "repeated_wrong": message = "សូមមើលតម្លៃដែលនៅជិត 1 ជាងមុន។"
    if outcome in {"hint", "explain_differently", "answer_progress_1"}: message = "ចំពោះ x ≠ 1 អាចសម្រួលកន្សោមនេះបាន។" if step_index == 1 and not opening else "សង្កេតតារាងនៅពេល x ខិតជិត 1។"
    if outcome == "answer_progress_2": message = "ឥឡូវសង្កេតកន្សោមដែលសម្រួលរួច។"
    table = moment["teaching_plan"]["board_actions"][1]
    actions: list[VisualTutorBoardAction] = []
    if opening:
        actions = [VisualTutorBoardAction(id="limits-equation", type=VisualTutorCanvasActionType.WRITE_EQUATION, sequence_index=0, duration_ms=500, layout_zone="problem", layout_flow="vertical", latex=formula, section_id="limits-moment-01"), VisualTutorBoardAction(id="limits-source-table", type=VisualTutorCanvasActionType.SHOW_TABLE, sequence_index=1, duration_ms=700, layout_zone="visual", layout_flow="vertical", width=420, height=160, table={"columns": table["columns"], "rows": table["rows"]}, section_id="limits-moment-01")]
    else:
        actions = [VisualTutorBoardAction(id=f"limits-{step_id}-equation", type=VisualTutorCanvasActionType.TRANSFORM_EQUATION, sequence_index=0, duration_ms=650, layout_zone="working", layout_flow="vertical", latex=formula, section_id=f"limits-{step_id}")]
    actions.append(VisualTutorBoardAction(id=f"limits-{step_id}-task", type=VisualTutorCanvasActionType.STUDENT_TASK, sequence_index=len(actions), layout_zone="student_task", layout_flow="vertical", text=task, requires_student_response=True, section_id=f"limits-{step_id}"))
    return _response(moment, session_id, f"local-limits-{step_id}", message or task, task, actions, step_index, outcome)


def _final(moment: dict[str, Any], session_id: str, reveal: bool = False) -> VisualTutorTurnResponse:
    message = "ត្រឹមត្រូវ។ លីមីតនៃអនុគមន៍នេះគឺ 5។" if reveal else "ការសង្កេតរបស់អ្នកត្រឹមត្រូវ។"
    kind = VisualTutorCanvasActionType.FINAL_ANSWER_REVEAL if reveal else VisualTutorCanvasActionType.SHOW_FEEDBACK
    action = VisualTutorBoardAction(id="limits-final-feedback", type=kind, sequence_index=0, duration_ms=500, layout_zone="feedback", layout_flow="vertical", text=message, section_id="limits-final")
    return _response(moment, session_id, "local-limits-final", message, "សូមសរសេរអ្វីដែលអ្នកសង្កេតឃើញ។", [action], 3, "answer_revealed" if reveal else "correct", waiting=False, locked=not reveal)


def _response(moment: dict[str, Any], session_id: str, turn_id: str, message: str, task: str, actions: list[VisualTutorBoardAction], step: int, outcome: str | None, waiting: bool = True, locked: bool = True) -> VisualTutorTurnResponse:
    table = moment["teaching_plan"]["board_actions"][1]
    plan_actions: list[dict[str, Any]] = []
    for action in actions:
        item: dict[str, Any] = {"id": action.id, "type": action.type.value, "sequence_index": action.sequence_index, "duration_ms": action.duration_ms, "layout_zone": action.layout_zone.value, "layout_flow": action.layout_flow.value}
        if action.text: item["text"] = action.text
        if action.latex: item["latex"] = action.latex
        if action.type == VisualTutorCanvasActionType.SHOW_TABLE: item["table"] = {"columns": table["columns"], "rows": table["rows"]}
        if action.type == VisualTutorCanvasActionType.STUDENT_TASK: item.update({"requires_student_response": True, "task_type": "algebra_expression"})
        plan_actions.append(item)
    reveal = not locked
    plan = validate_teaching_plan({"schema_version": 1, "representation": "table", "learning_objective": moment["learning_objectives"][0]["text"], "teaching_message": message, "board_actions": plan_actions, "allowed_student_actions": ["submit_answer", "request_hint", "explain_differently", "request_final_answer"], "hidden_answer_policy": {"mode": "reveal_allowed" if reveal else "hidden", "deterministic_policy_permits_final_reveal": reveal}, "next_state_policy": {"correct": "continue", "invalid": "reteach", "incomplete": "ask_for_work", "stuck": "reteach", "hint": "reteach", "explain_differently": "reteach"}}).model_dump(mode="json")
    source = moment["source"]
    return VisualTutorTurnResponse(session_id=session_id, turn_id=turn_id, screen_state=VisualTutorScreenState.ASKING_QUESTION if waiting else VisualTutorScreenState.SPEAKING_WRITING, tutor_status="Waiting for you" if waiting else "Ready", spoken_text=f"{message} {task}" if waiting else message, display_text=message, teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION, final_answer_locked=locked, student_task=task, board=VisualTutorBoard(type=VisualTutorBoardType.FORMULA_CARD, title=str(moment["lesson"]["khmer_source_label"]), items=[VisualTutorBoardItem(label="Local curriculum demo", content=str(moment["lesson"]["khmer_source_label"]), status="active")], metadata={"local_curriculum_demo": True, "current_step_index": step}), board_actions=actions, speech=VisualTutorSpeech(text=f"{message} {task}" if waiting else message, language="km", tts_status=VisualTutorTtsStatus.NOT_REQUESTED, speak_after_action_id=actions[0].id, pause_after_ms=500 if waiting else 0), teaching_stage=VisualTutorTeachingStage(stage_state=VisualTutorStageState.WAITING_FOR_STUDENT if waiting else VisualTutorStageState.ADAPTING, lesson_state=VisualTutorLessonState.ASK if waiting else VisualTutorLessonState.RETEACH_OR_CONTINUE, current_focus=actions[0].id, turn_goal=task, max_actions_before_wait=len(actions)), interaction=VisualTutorInteraction(type=VisualTutorInteractionType.TEXT_RESPONSE, prompt=task, expected_answer_locked=locked, input_enabled=waiting, submit_label="បញ្ជូន"), allowed_actions=[VisualTutorAllowedAction.SUBMIT_ANSWER, VisualTutorAllowedAction.REQUEST_HINT, VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY, VisualTutorAllowedAction.STUCK, VisualTutorAllowedAction.REQUEST_ANSWER], quick_actions=[VisualTutorAllowedAction.SUBMIT_ANSWER, VisualTutorAllowedAction.REQUEST_HINT], mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP if outcome in {"correct", "answer_revealed"} else VisualTutorMasterySignal.EXPLORING, authoritative_lesson_state={"lesson_id": _LESSON_ID, "active_step_id": f"limits-moment-{step}", "current_step_index": step, "final_answer_locked": locked}, metadata={"local_curriculum_demo": True, "local_demo_label": "Local curriculum demo", "lesson_id": _LESSON_ID, "curriculum_version_id": _CURRICULUM_VERSION_ID, "source_id": source["source_id"], "source_page": source["pdf_pages"][0], "waiting_for_student_input": waiting, "teaching_plan": plan, "evaluation": {"outcome": outcome} if outcome else None, "validation_result": "correct_step" if outcome in {"correct", "answer_revealed"} else "incorrect_step" if outcome in {"incorrect", "repeated_wrong"} else None, "board_update_mode": "replace"})
