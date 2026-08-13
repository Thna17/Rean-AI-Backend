from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import DESCENDING

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorSession,
    VisualTutorSessionCreateRequest,
    VisualTutorSessionSummary,
    VisualTutorStudentModel,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)

# Keep a resumed board useful without allowing a long-running session to grow a
# Mongo document indefinitely. The newest snapshot is always the authoritative
# resume state; the retained history is for recent replay and troubleshooting.
MAX_SESSION_TURNS = 120
MAX_BOARD_STATES = 60
MAX_CANVAS_STATES = 60
MAX_CANVAS_ACTIONS = 400
MAX_MESSAGES = 240
MAX_STUDENT_RESPONSES = 120
MAX_VALIDATION_HISTORY = 120
MAX_RESPONSE_SOURCE_HISTORY = 120
MAX_BOARD_ACTION_HISTORY = 120
MAX_REPLAY_SNAPSHOTS = 40


def _bounded_push(value: Any, limit: int) -> Dict[str, Any]:
    """Return the MongoDB form that appends one value and retains recent data."""
    return {"$each": [value], "$slice": -limit}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = dict(doc)
    cleaned.pop("_id", None)
    return cleaned


def _is_stuck_turn(response: VisualTutorTurnResponse) -> bool:
    policy = response.metadata.get("policy")
    if isinstance(policy, dict) and policy.get("detected_intent") == "stuck":
        return True
    return response.teaching_mode.value == "stuck_help"


class BoardVersionConflictError(Exception):
    def __init__(
        self,
        message: str,
        expected_version: int,
        client_version: Optional[int] = None,
    ):
        super().__init__(message)
        self.message = message
        self.expected_version = expected_version
        self.client_version = client_version


def _safe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _idempotency_key_from_request(request: VisualTutorTurnRequest) -> Optional[str]:
    key = (
        getattr(request, "idempotency_key", None)
        or request.metadata.get("idempotency_key")
        or request.metadata.get("client_turn_id")
    )
    if key is None:
        return None
    key = str(key).strip()
    return key or None


def _is_non_evaluated_turn(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
) -> bool:
    if request.action in {
        VisualTutorAction.REQUEST_HINT,
        VisualTutorAction.REQUEST_STUCK_HELP,
        VisualTutorAction.EXPLAIN_DIFFERENTLY,
        VisualTutorAction.REQUEST_FINAL_ANSWER,
        VisualTutorAction.START,
    }:
        return True
    if _is_stuck_turn(response):
        return True
    if request.student_intent in {
        VisualTutorStudentIntent.REQUEST_HINT,
        VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
        VisualTutorStudentIntent.REQUEST_ANSWER,
        VisualTutorStudentIntent.STUCK,
        VisualTutorStudentIntent.CLARIFICATION,
        VisualTutorStudentIntent.NEW_PROBLEM,
    }:
        return True
    val_res = response.metadata.get("validation_result")
    input_relevance = response.metadata.get("input_relevance")
    if input_relevance in {"unrelated", "off_topic", "unknown", "clarification"}:
        return True
    if val_res in {
        "unrelated_numeric_input",
        "off_topic",
        "needs_solver_check",
        "unknown",
        "clarification",
        "incorrect_final_answer",
        "correct_final_answer_too_early",
        None,
    }:
        return True
    if str(val_res).startswith("understanding_check_"):
        return True
    return False


def _is_correct_step(response: VisualTutorTurnResponse) -> bool:
    val_res = str(response.metadata.get("validation_result", "")).lower()
    mastery = getattr(response.mastery_signal, "value", response.mastery_signal)
    if val_res.startswith("correct") or val_res in {
        "correct",
        "correct_step",
        "correct_operation",
        "correct_final_step",
        "correct_final_answer",
        "correct_delta_y",
        "correct_delta_x",
        "correct_slope",
        "correct_intercept",
        "correct_step_equation",
    }:
        return True
    if mastery in {"mastered", "ready_for_next_step", "improving"}:
        return True
    return False


def evaluate_attempt_counters(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    *,
    is_new_problem: bool,
    current_attempts: int,
    current_wrong_attempts: int,
) -> tuple[int, int]:
    if is_new_problem:
        return 0, 0

    if _is_non_evaluated_turn(request, response):
        return current_attempts, current_wrong_attempts

    attempts = current_attempts + 1
    if _is_correct_step(response):
        wrong_attempts = 0
    else:
        wrong_attempts = current_wrong_attempts + 1

    return attempts, wrong_attempts


def derive_student_model(
    *,
    response: VisualTutorTurnResponse,
    request: VisualTutorTurnRequest,
    hint_count: int,
    attempts: int,
    wrong_attempts: int,
    validation_history: list[dict[str, Any]],
    last_mastery_signal: Optional[Any],
) -> VisualTutorStudentModel:
    mastery_signal = response.mastery_signal.value
    understanding = {
        "mastered": "mastered",
        "ready_for_next_step": "solid",
        "improving": "partial",
    }.get(mastery_signal, "exploring")

    recent_mistakes: list[str] = []
    for entry in reversed(validation_history):
        if not isinstance(entry, dict):
            continue
        mistake = entry.get("mistake_category") or entry.get("misconception_type")
        if mistake is not None and str(mistake).strip() and str(mistake) != "None":
            if str(mistake) not in recent_mistakes:
                recent_mistakes.append(str(mistake))
        if len(recent_mistakes) == 3:
            break

    if hint_count >= 3 or wrong_attempts >= 3:
        recommended_depth = "simple"
    elif hint_count == 0 and wrong_attempts == 0 and attempts >= 1:
        recommended_depth = "detailed"
    else:
        recommended_depth = "standard"

    if last_mastery_signal is not None:
        last_mastery_signal = getattr(last_mastery_signal, "value", last_mastery_signal)
    return VisualTutorStudentModel(
        understanding=understanding,
        recent_mistakes=recent_mistakes,
        hint_level=hint_count,
        wrong_attempt_streak=wrong_attempts,
        preferred_language=(
            "km" if (request.locale or "").lower().startswith("km") else "en"
        ),
        preferred_explanation_level="standard",
        recommended_depth=recommended_depth,
        last_mastery_signal=last_mastery_signal,
    )


def _derive_student_model(
    session,
    response: VisualTutorTurnResponse,
    request: VisualTutorTurnRequest,
) -> VisualTutorStudentModel:
    return derive_student_model(
        response=response,
        request=request,
        hint_count=int(getattr(session, "hint_count", 0) or 0),
        attempts=int(getattr(session, "attempts", 0) or 0),
        wrong_attempts=int(getattr(session, "wrong_attempts", 0) or 0),
        validation_history=list(getattr(session, "validation_history", []) or []),
        last_mastery_signal=response.mastery_signal,
    )


class VisualTutorSessionStore:
    def __init__(self, db: AsyncIOMotorDatabase):
        self._sessions = db["visual_tutor_sessions"]

    async def create_session(
        self,
        request: VisualTutorSessionCreateRequest,
        *,
        session_id: Optional[str] = None,
    ) -> VisualTutorSession:
        now = _now_iso()
        doc = {
            "session_id": session_id or str(uuid.uuid4()),
            "user_id": request.user_id,
            "session_mode": request.session_mode,
            "subject": request.subject,
            # Flutter sends the selected grade as an integer in metadata; session
            # models store grade levels as strings for consistent API replay.
            "grade_level": _optional_text(
                request.grade_level
                or request.metadata.get("grade_level")
                or request.metadata.get("grade")
            ),
            "topic": request.topic,
            "skill_tags": _string_list(request.skill_tags or request.metadata.get("skill_tags")),
            "difficulty": request.difficulty or request.metadata.get("difficulty"),
            "problem_text": request.problem_text,
            "normalized_problem": None,
            "problem_type": None,
            "solver_facts": None,
            "current_step_index": 0,
            "expected_step": None,
            "solved_variables": {},
            "validation_history": [],
            "last_verification": None,
            "hint_count": 0,
            "wrong_attempts": 0,
            "stuck_count": 0,
            "attempts": 0,
            "final_answer_revealed": False,
            "board_version": 0,
            "board_schema_version": 1,
            "student_model": VisualTutorStudentModel().model_dump(mode="json"),
            "messages": [],
            "turns": [],
            "board_states": [],
            "canvas_state": None,
            "canvas_actions": [],
            "canvas_states": [],
            "locked_canvas_element_ids": [],
            "revealed_canvas_element_ids": [],
            "current_focus_element_id": None,
            "teaching_stage": None,
            "stage_state": None,
            "lesson_state": None,
            "teaching_board_state": None,
            "teaching_board_states": [],
            "visible_board_elements": [],
            "hidden_element_ids": [],
            "locked_element_ids": [],
            "played_action_ids": [],
            "previous_board_action_ids": [],
            "board_action_history": [],
            "replay_snapshots": [],
            "strategy_history": [],
            "pending_interaction": None,
            "allowed_actions": [],
            "student_responses": [],
            "voice_tts_metadata": {},
            "curriculum_chunk_ids": [],
            "response_source_history": [],
            "mastery_signal": None,
            "status": "active",
            "completed_at": None,
            "targeted_practice": {},
            "created_at": now,
            "updated_at": now,
            "metadata": request.metadata,
        }
        await self._sessions.update_one(
            {"session_id": doc["session_id"]},
            {"$setOnInsert": doc},
            upsert=True,
        )
        return VisualTutorSession(**doc)

    async def get_session(self, session_id: str) -> Optional[VisualTutorSession]:
        doc = await self._sessions.find_one({"session_id": session_id})
        if not doc:
            return None
        return VisualTutorSession(**_clean_doc(doc))

    async def list_user_sessions(self, user_id: str) -> List[VisualTutorSessionSummary]:
        docs = await (
            self._sessions.find({"user_id": user_id})
            .sort("updated_at", DESCENDING)
            .to_list(length=100)
        )
        return [VisualTutorSessionSummary(**_clean_doc(doc)) for doc in docs]

    async def get_persisted_turn_response(
        self,
        *,
        session_id: str,
        idempotency_key: str,
    ) -> Optional[VisualTutorTurnResponse]:
        session = await self.get_session(session_id)
        if session is None:
            return None
        for turn in reversed(getattr(session, "turns", []) or []):
            if not isinstance(turn, dict):
                continue
            request_doc = turn.get("request") or {}
            metadata = (
                request_doc.get("metadata") if isinstance(request_doc, dict) else {}
            )
            if not isinstance(metadata, dict):
                metadata = {}
            turn_key = (
                turn.get("idempotency_key")
                or metadata.get("idempotency_key")
                or metadata.get("client_turn_id")
            )
            if str(turn_key or "") != idempotency_key:
                continue
            response_doc = turn.get("response")
            if isinstance(response_doc, dict):
                return VisualTutorTurnResponse.model_validate(response_doc)
        return None

    async def persist_turn(
        self,
        *,
        request: VisualTutorTurnRequest,
        response: VisualTutorTurnResponse,
    ) -> VisualTutorSession:
        now = _now_iso()
        session = await self.get_session(response.session_id)
        existed_before = session is not None
        if existed_before:
            idempotency_key = _idempotency_key_from_request(request)
            if idempotency_key and getattr(session, "turns", None):
                for t in reversed(session.turns):
                    if not isinstance(t, dict):
                        continue
                    t_key = (
                        t.get("idempotency_key")
                        or (t.get("request") or {})
                        .get("metadata", {})
                        .get("idempotency_key")
                        or (t.get("request") or {})
                        .get("metadata", {})
                        .get("client_turn_id")
                    )
                    if t_key == idempotency_key:
                        return session

            current_board_version: int = getattr(session, "board_version", None) or 0
            client_ver = _safe_int(
                getattr(request, "client_board_version", None)
                or request.metadata.get("client_board_version")
            )
            if client_ver is not None and client_ver != current_board_version:
                raise BoardVersionConflictError(
                    "Stale client board version. Please refresh or retry.",
                    expected_version=current_board_version,
                    client_version=client_ver,
                )
        else:
            current_board_version = 0

        next_board_version: int = current_board_version + 1
        response_for_storage = response.model_copy(
            update={
                "board_version": next_board_version,
                "board_schema_version": int(
                    response.metadata.get("board_schema_version", 1)
                ),
                "base_board_version": current_board_version,
                "metadata": {
                    **response.metadata,
                    "board_version": next_board_version,
                    "base_board_version": current_board_version,
                },
            }
        )
        if session is None:
            session = await self.create_session(
                VisualTutorSessionCreateRequest(
                    user_id=request.user_id,
                    subject=request.subject,
                    topic=request.topic,
                    grade_level=str(request.metadata.get("grade_level") or request.metadata.get("grade") or "") or None,
                    skill_tags=_string_list(request.metadata.get("skill_tags")),
                    difficulty=str(request.metadata.get("difficulty") or "") or None,
                    problem_text=request.current_state.problem_text,
                ),
                session_id=response.session_id,
            )

        is_new_problem = (
            bool(request.message.strip())
            and (
                request.student_intent == VisualTutorStudentIntent.NEW_PROBLEM
                or response.metadata.get("student_intent") == "new_problem"
                or not request.current_state.problem_text
            )
            and (
                request.action == VisualTutorAction.SUBMIT_PROBLEM
                or response.metadata.get("student_intent") == "new_problem"
            )
        )
        problem_text = (
            (_problem_from_board(response) or request.message.strip())
            if is_new_problem
            else (
                request.current_state.problem_text
                or session.problem_text
                or _problem_from_board(response)
            )
        )
        normalized_problem = (
            response.board.metadata.get("normalized_problem")
            or (None if is_new_problem else request.current_state.normalized_problem)
            or (None if is_new_problem else session.normalized_problem)
        )
        problem_type = _problem_type_from_response(response) or (
            None if is_new_problem else session.problem_type
        )
        expected_step = _expected_step_from_response(response) or (
            None if is_new_problem else session.expected_step
        )
        solver_facts = response.metadata.get("solver_facts") or (
            None if is_new_problem else session.solver_facts
        )
        solved_variables = (
            _solved_variables_from_response(response)
            or ({} if is_new_problem else session.solved_variables)
            or {}
        )
        current_step_index = int(
            response.board.metadata.get(
                "current_step_index",
                request.current_state.current_step_index,
            )
        )
        hint_count = 0 if is_new_problem else session.hint_count
        if not is_new_problem and request.hint_count is not None:
            hint_count = request.hint_count
        elif not is_new_problem and request.current_state.hint_count:
            hint_count = request.current_state.hint_count
        if request.action == VisualTutorAction.REQUEST_HINT or _is_stuck_turn(response):
            hint_count += 1

        stuck_count = 0 if is_new_problem else session.stuck_count
        if _is_stuck_turn(response):
            stuck_count += 1

        attempts, wrong_attempts = evaluate_attempt_counters(
            request,
            response,
            is_new_problem=is_new_problem,
            current_attempts=getattr(session, "attempts", 0) or 0,
            current_wrong_attempts=getattr(session, "wrong_attempts", 0) or 0,
        )

        final_answer_revealed = (
            not response.final_answer_locked
            if is_new_problem
            else (
                session.final_answer_revealed
                or request.current_state.final_answer_revealed
                or not response.final_answer_locked
            )
        )
        turn_doc = {
            "turn_id": response.turn_id,
            "timestamp": now,
            "request": request.model_dump(mode="json"),
            "response": response_for_storage.model_dump(mode="json"),
        }
        idemp_key = _idempotency_key_from_request(request)
        if idemp_key:
            turn_doc["idempotency_key"] = idemp_key
        messages = [
            {
                "role": "user",
                "content": request.message,
                "timestamp": now,
                "action": request.action.value,
            },
            {
                "role": "assistant",
                "content": response.display_text,
                "spoken_text": response.spoken_text,
                "timestamp": now,
                "teaching_mode": response.teaching_mode.value,
            },
        ]
        board_state = response.board.model_dump(mode="json")
        canvas_snapshot = _canvas_snapshot_from_response(response)
        live_snapshot = _live_stage_snapshot_from_response(
            response=response,
            previous_session=session,
            reset_board=is_new_problem,
        )
        student_response = _student_response_from_request(
            request=request, timestamp=now
        )
        validation_entry = _validation_history_entry(
            request=request,
            response=response,
            timestamp=now,
        )
        response_source_entry = _response_source_history_entry(
            response=response,
            timestamp=now,
        )
        board_action_history_entry = _board_action_history_entry(
            response=response,
            timestamp=now,
        )
        strategy_history = _next_strategy_history(
            previous_history=list(getattr(session, "strategy_history", []) or []),
            response=response,
            validation_entry=validation_entry,
            timestamp=now,
        )
        grade_level = (
            request.metadata.get("grade_level")
            or request.metadata.get("grade")
            or getattr(session, "grade_level", None)
        )
        skill_tags = _string_list(
            response.metadata.get("skill_tags")
            or request.metadata.get("skill_tags")
            or getattr(session, "skill_tags", [])
        )
        difficulty = (
            response.metadata.get("difficulty")
            or request.metadata.get("difficulty")
            or getattr(session, "difficulty", None)
        )
        verification = _verification_record(validation_entry, response)
        status = _session_status(response)
        targeted_practice = _targeted_practice_state(request, response, session)
        replay_snapshot = _replay_snapshot(
            response=response_for_storage,
            board_version=next_board_version,
            live_snapshot=live_snapshot,
            timestamp=now,
        )

        update = {
            "$set": {
                "user_id": request.user_id,
                "session_mode": (
                    "confirmed_problem" if problem_text else session.session_mode
                ),
                "subject": request.subject,
                "grade_level": str(grade_level) if grade_level is not None else None,
                "topic": request.topic,
                "skill_tags": skill_tags,
                "difficulty": str(difficulty) if difficulty is not None else None,
                "problem_text": problem_text,
                "normalized_problem": normalized_problem,
                "problem_type": problem_type,
                "solver_facts": solver_facts,
                "current_step_index": current_step_index,
                "expected_step": expected_step,
                "solved_variables": solved_variables,
                "hint_count": hint_count,
                "wrong_attempts": wrong_attempts,
                "stuck_count": stuck_count,
                "attempts": attempts,
                "final_answer_revealed": final_answer_revealed,
                "last_verification": verification,
                "mastery_signal": response.mastery_signal.value,
                "status": status,
                "completed_at": now if status == "completed" else getattr(session, "completed_at", None),
                "targeted_practice": targeted_practice,
                "canvas_state": canvas_snapshot,
                "locked_canvas_element_ids": canvas_snapshot[
                    "locked_canvas_element_ids"
                ],
                "revealed_canvas_element_ids": canvas_snapshot[
                    "revealed_canvas_element_ids"
                ],
                "current_focus_element_id": canvas_snapshot["current_focus_element_id"],
                "teaching_stage": live_snapshot["teaching_stage"],
                "stage_state": live_snapshot["stage_state"],
                "lesson_state": live_snapshot["lesson_state"],
                "teaching_board_state": live_snapshot["teaching_board_state"],
                "visible_board_elements": live_snapshot["visible_board_elements"],
                "hidden_element_ids": live_snapshot["hidden_element_ids"],
                "locked_element_ids": live_snapshot["locked_element_ids"],
                "played_action_ids": live_snapshot["played_action_ids"],
                "previous_board_action_ids": live_snapshot["previous_board_action_ids"],
                "strategy_history": strategy_history,
                "pending_interaction": live_snapshot["pending_interaction"],
                "allowed_actions": live_snapshot["allowed_actions"],
                "voice_tts_metadata": live_snapshot["voice_tts_metadata"],
                "curriculum_chunk_ids": live_snapshot["curriculum_chunk_ids"],
                "updated_at": now,
                "board_version": next_board_version,
            },
            "$push": {
                "turns": _bounded_push(turn_doc, MAX_SESSION_TURNS),
                "board_states": _bounded_push(board_state, MAX_BOARD_STATES),
                "canvas_states": _bounded_push(canvas_snapshot, MAX_CANVAS_STATES),
                "teaching_board_states": _bounded_push(
                    live_snapshot["teaching_board_state"], MAX_BOARD_STATES
                ),
                "canvas_actions": {
                    "$each": response.model_dump(mode="json").get("canvas_actions", []),
                    "$slice": -MAX_CANVAS_ACTIONS,
                },
                "messages": {"$each": messages, "$slice": -MAX_MESSAGES},
                "replay_snapshots": {
                    "$each": [replay_snapshot],
                    "$slice": -MAX_REPLAY_SNAPSHOTS,
                },
            },
            "$setOnInsert": {
                "session_id": response.session_id,
                "created_at": now,
                "metadata": {},
            },
        }
        if student_response is not None:
            update["$push"]["student_responses"] = _bounded_push(
                student_response, MAX_STUDENT_RESPONSES
            )
        if validation_entry is not None:
            update["$push"]["validation_history"] = _bounded_push(
                validation_entry, MAX_VALIDATION_HISTORY
            )
        if response_source_entry is not None:
            update["$push"]["response_source_history"] = _bounded_push(
                response_source_entry, MAX_RESPONSE_SOURCE_HISTORY
            )
        if board_action_history_entry is not None:
            update["$push"]["board_action_history"] = _bounded_push(
                board_action_history_entry, MAX_BOARD_ACTION_HISTORY
            )

        current_val_history = list(getattr(session, "validation_history", []) or [])
        if validation_entry is not None:
            current_val_history.append(validation_entry)

        student_model = derive_student_model(
            response=response,
            request=request,
            hint_count=hint_count,
            attempts=attempts,
            wrong_attempts=wrong_attempts,
            validation_history=current_val_history,
            last_mastery_signal=response.mastery_signal,
        )
        student_model.metadata["strategy_history"] = strategy_history
        student_model.metadata["last_addressed_mistake_category"] = (
            strategy_history[-1].get("mistake_category_addressed")
            if strategy_history
            else None
        )
        update["$set"]["student_model"] = student_model.model_dump(mode="json")

        filter_query: Dict[str, Any] = {"session_id": response.session_id}
        if existed_before:
            board_version_matches: list[dict[str, Any]] = [
                {"board_version": current_board_version}
            ]
            if current_board_version == 0:
                board_version_matches.extend(
                    [{"board_version": {"$exists": False}}, {"board_version": None}]
                )
            filter_query["$or"] = board_version_matches
            result = await self._sessions.update_one(filter_query, update)
            if result.matched_count == 0:
                raise BoardVersionConflictError(
                    "Concurrent board version modification detected.",
                    expected_version=current_board_version,
                )
        else:
            await self._sessions.update_one(filter_query, update, upsert=True)

        persisted = await self.get_session(response.session_id)
        if persisted is None:
            raise RuntimeError("Visual Tutor session persistence failed")
        return persisted


def _problem_from_board(response: VisualTutorTurnResponse) -> Optional[str]:
    for item in response.board.items:
        if item.label.lower() == "problem":
            return item.content
    return None


def _problem_type_from_response(response: VisualTutorTurnResponse) -> Optional[str]:
    understanding = response.metadata.get("problem_understanding")
    if isinstance(understanding, dict) and understanding.get("problem_type"):
        return str(understanding["problem_type"])
    if response.metadata.get("problem_type"):
        return str(response.metadata["problem_type"])
    if response.board.metadata.get("problem_type"):
        return str(response.board.metadata["problem_type"])
    return None


def _expected_step_from_response(response: VisualTutorTurnResponse) -> Optional[str]:
    for source in (response.metadata, response.board.metadata):
        expected = source.get("expected_step")
        if expected:
            return str(expected)
    if response.interaction and response.interaction.prompt:
        return response.interaction.prompt
    if response.student_task:
        return response.student_task
    return None


def _solved_variables_from_response(
    response: VisualTutorTurnResponse,
) -> Dict[str, Any]:
    final_answer = (
        response.metadata.get("final_answer")
        or response.board.metadata.get("final_answer")
        or ""
    )
    if not final_answer or "=" not in str(final_answer):
        return {}
    variable, value = str(final_answer).split("=", 1)
    variable = variable.strip()
    value = value.strip()
    if not variable:
        return {}
    return {variable: value}


def _canvas_snapshot_from_response(
    response: VisualTutorTurnResponse,
) -> Dict[str, Any]:
    payload = response.model_dump(mode="json")
    canvas = payload.get("canvas")
    actions = payload.get("canvas_actions") or []
    locked_ids = _locked_canvas_element_ids(canvas=canvas, actions=actions)
    revealed_ids = _revealed_canvas_element_ids(canvas=canvas, actions=actions)
    focus_id = _current_focus_element_id(canvas=canvas, actions=actions)
    return {
        "turn_id": response.turn_id,
        "canvas": canvas,
        "canvas_actions": actions,
        "locked_canvas_element_ids": locked_ids,
        "revealed_canvas_element_ids": revealed_ids,
        "current_focus_element_id": focus_id,
        "metadata": {
            "final_answer_locked": response.final_answer_locked,
            "teaching_mode": response.teaching_mode.value,
            "mastery_signal": response.mastery_signal.value,
            "canvas_action_count": len(actions),
        },
    }


def _live_stage_snapshot_from_response(
    *,
    response: VisualTutorTurnResponse,
    previous_session: VisualTutorSession,
    reset_board: bool = False,
) -> Dict[str, Any]:
    payload = response.model_dump(mode="json")
    teaching_stage = payload.get("teaching_stage")
    stage_state = (
        _enum_or_value(teaching_stage.get("stage_state")) if teaching_stage else None
    )
    lesson_state = (
        _enum_or_value(teaching_stage.get("lesson_state")) if teaching_stage else None
    )
    board_actions = payload.get("board_actions") or []
    canvas_actions = payload.get("canvas_actions") or []
    all_actions = _sort_actions(board_actions + canvas_actions)
    teaching_board = payload.get("teaching_board")
    board_state = _teaching_board_snapshot(
        response=response,
        teaching_board=teaching_board,
        actions=all_actions,
        previous_session=previous_session,
        reset_board=reset_board,
    )
    locked_ids = _merge_ids(
        [] if reset_board else list(previous_session.locked_element_ids),
        board_state.get("locked_element_ids") or [],
        _locked_canvas_element_ids(
            canvas=payload.get("canvas"), actions=canvas_actions
        ),
    )
    hidden_ids = _merge_ids(
        [] if reset_board else list(previous_session.hidden_element_ids),
        board_state.get("hidden_element_ids") or [],
    )
    if response.final_answer_locked:
        hidden_ids = _merge_ids(hidden_ids, locked_ids)
    visible_elements = [
        element
        for element in board_state.get("elements") or []
        if isinstance(element, dict)
        and element.get("hidden") is not True
        and str(element.get("id") or "") not in hidden_ids
    ]
    played_action_ids = _merge_ids(
        [] if reset_board else list(previous_session.played_action_ids),
        [
            str(action.get("id"))
            for action in all_actions
            if isinstance(action, dict)
            and action.get("id")
            and _is_durable_board_action(action)
        ],
    )
    previous_board_action_ids = _merge_ids(
        [] if reset_board else list(previous_session.previous_board_action_ids),
        [
            str(action.get("id"))
            for action in board_actions
            if isinstance(action, dict)
            and action.get("id")
            and _is_durable_board_action(action)
        ],
    )
    pending_interaction = payload.get("interaction")
    allowed_actions = [
        _enum_or_value(action)
        for action in payload.get("allowed_actions") or []
        if _enum_or_value(action)
    ]
    speech = payload.get("speech") or {}
    voice_tts_metadata = {
        "speech_text": speech.get("text") or response.spoken_text,
        "language": speech.get("language"),
        "voice_id": speech.get("voice_id"),
        "tts_status": _enum_or_value(speech.get("tts_status")),
        "speak_after_action_id": speech.get("speak_after_action_id"),
        "pause_after_ms": speech.get("pause_after_ms", 0),
    }
    curriculum_chunk_ids = _merge_ids(
        [] if reset_board else list(previous_session.curriculum_chunk_ids),
        response.metadata.get("curriculum_chunk_ids") or [],
        (
            response.metadata.get("curriculum_context", {}).get("chunk_ids", [])
            if isinstance(response.metadata.get("curriculum_context"), dict)
            else []
        ),
    )
    return {
        "teaching_stage": teaching_stage,
        "stage_state": stage_state,
        "lesson_state": lesson_state,
        "teaching_board_state": board_state,
        "visible_board_elements": visible_elements,
        "hidden_element_ids": hidden_ids,
        "locked_element_ids": locked_ids,
        "played_action_ids": played_action_ids,
        "previous_board_action_ids": previous_board_action_ids,
        "pending_interaction": pending_interaction,
        "allowed_actions": allowed_actions,
        "voice_tts_metadata": voice_tts_metadata,
        "curriculum_chunk_ids": curriculum_chunk_ids,
    }


def _teaching_board_snapshot(
    *,
    response: VisualTutorTurnResponse,
    teaching_board: Optional[Dict[str, Any]],
    actions: list[dict],
    previous_session: VisualTutorSession,
    reset_board: bool = False,
) -> Dict[str, Any]:
    base = (
        dict(teaching_board)
        if isinstance(teaching_board, dict)
        else ({} if reset_board else dict(previous_session.teaching_board_state or {}))
    )
    elements = list(
        base.get("elements")
        or ([] if reset_board else previous_session.visible_board_elements)
    )
    by_id: Dict[str, Dict[str, Any]] = {
        str(element.get("id")): dict(element)
        for element in elements
        if isinstance(element, dict) and element.get("id")
    }
    order = list(by_id.keys())
    for action in actions:
        if not isinstance(action, dict):
            continue
        op = _patch_op(action)
        target_id = _target_or_id(action)
        action_metadata = (
            action.get("metadata") if isinstance(action.get("metadata"), dict) else {}
        )
        if op in {"highlight", "fade", "focus", "hide", "reveal", "remove"}:
            if not target_id or target_id not in by_id:
                continue
            existing = by_id[target_id]
            metadata = dict(existing.get("metadata") or {})
            if op == "highlight":
                metadata["highlighted"] = True
            elif op == "fade":
                metadata["faded"] = True
            elif op == "focus":
                if action_metadata.get("multi_focus") is not True:
                    for element in by_id.values():
                        element_metadata = dict(element.get("metadata") or {})
                        element_metadata["focused"] = False
                        element["metadata"] = element_metadata
                metadata["focused"] = True
                existing["focus"] = True
            elif op == "hide":
                existing["hidden"] = True
            elif op == "reveal":
                existing["hidden"] = False
                if action_metadata.get("preserve_faded") is not True:
                    metadata["faded"] = False
                if action_metadata.get("preserve_highlighted") is not True:
                    metadata["highlighted"] = False
            elif op == "remove":
                by_id.pop(target_id, None)
                if target_id in order:
                    order.remove(target_id)
                continue
            existing["metadata"] = metadata
            by_id[target_id] = existing
            continue
        element = _element_from_action(action)
        if not element:
            continue
        if op == "update":
            target_id = target_id or element["id"]
            if target_id in by_id:
                merged = {
                    **by_id[target_id],
                    **{
                        key: value
                        for key, value in element.items()
                        if value is not None
                    },
                }
                merged["metadata"] = {
                    **(by_id[target_id].get("metadata") or {}),
                    **(element.get("metadata") or {}),
                }
                by_id[target_id] = merged
                continue
        if element["id"] not in by_id:
            order.append(element["id"])
        by_id[element["id"]] = element

    elements = [by_id[element_id] for element_id in order if element_id in by_id]

    locked_ids = _merge_ids(
        base.get("locked_element_ids") or [],
        [
            str(element.get("id"))
            for element in elements
            if isinstance(element, dict) and element.get("locked") is True
        ],
        [
            str(action.get("target_id") or action.get("id"))
            for action in actions
            if isinstance(action, dict)
            and (
                action.get("locked") is True
                or action.get("type") == "hide"
                or action.get("metadata", {}).get("hidden") is True
            )
            and (action.get("target_id") or action.get("id"))
        ],
    )
    hidden_ids = _merge_ids(
        base.get("hidden_element_ids") or [],
        [
            str(element.get("id"))
            for element in elements
            if isinstance(element, dict) and element.get("hidden") is True
        ],
        [
            str(action.get("target_id") or action.get("id"))
            for action in actions
            if isinstance(action, dict)
            and (
                action.get("type") == "hide"
                or action.get("metadata", {}).get("hidden") is True
            )
            and (action.get("target_id") or action.get("id"))
        ],
    )
    existing_element_ids = {
        str(element.get("id"))
        for element in elements
        if isinstance(element, dict) and element.get("id")
    }
    hidden_ids = [
        element_id for element_id in hidden_ids if element_id in existing_element_ids
    ]
    locked_ids = [
        element_id for element_id in locked_ids if element_id in existing_element_ids
    ]
    if response.final_answer_locked:
        hidden_ids = _merge_ids(hidden_ids, locked_ids)
    focus_id = (
        base.get("focus_element_id")
        or _current_focus_element_id(canvas=None, actions=actions)
        or (None if reset_board else previous_session.current_focus_element_id)
    )
    if focus_id not in existing_element_ids:
        focus_id = None
    return {
        "id": base.get("id") or "teaching-board",
        "viewport": base.get("viewport"),
        "elements": elements,
        "groups": base.get("groups") or [],
        "sections": base.get("sections") or [],
        "actions": actions,
        "history": base.get("history") or [],
        "focus_element_id": focus_id,
        "active_section_id": base.get("active_section_id"),
        "locked_element_ids": locked_ids,
        "hidden_element_ids": hidden_ids,
        "faded_element_ids": base.get("faded_element_ids") or [],
        "turn_id": response.turn_id,
        "metadata": {
            **(base.get("metadata") or {}),
            "final_answer_locked": response.final_answer_locked,
            "teaching_mode": response.teaching_mode.value,
            "mastery_signal": response.mastery_signal.value,
        },
    }


def _element_from_action(action: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    action_type = _enum_or_value(action.get("type"))
    element_type_by_action = {
        "write_text": "text",
        "write_equation": "equation",
        "draw_point": "point",
        "draw_line": "line",
        "draw_arrow": "arrow",
        "draw_axes": "axes",
        "draw_graph_hint": "graph",
        "highlight": "highlight",
    }
    element_type = element_type_by_action.get(action_type)
    if not element_type or not action.get("id"):
        return None
    metadata = dict(action.get("metadata") or {})
    locked = action.get("locked") is True
    hidden = metadata.get("hidden") is True or action_type == "hide"
    return {
        "id": str(action["id"]),
        "type": element_type,
        "x": action.get("x"),
        "y": action.get("y"),
        "width": action.get("width"),
        "height": action.get("height"),
        "content": action.get("text") or action.get("latex"),
        "text": action.get("text"),
        "latex": action.get("latex"),
        "points": action.get("points") or [],
        "style": action.get("style") or {},
        "opacity": 0.0 if hidden else 1.0,
        "group_id": action.get("group_id"),
        "section_id": action.get("section_id"),
        "z_index": metadata.get("z_index", 0),
        "locked": locked,
        "hidden": hidden or locked,
        "focus": metadata.get("current_step") is True,
        "faded": metadata.get("faded") is True,
        "created_turn_id": metadata.get("turn_id"),
        "metadata": metadata,
    }


def _student_response_from_request(
    *,
    request: VisualTutorTurnRequest,
    timestamp: str,
) -> Optional[Dict[str, Any]]:
    if not request.message.strip():
        return None
    return {
        "content": request.message,
        "action": request.action.value,
        "student_intent": (
            request.student_intent.value if request.student_intent is not None else None
        ),
        "input_type": request.input_type.value,
        "timestamp": timestamp,
        "metadata": request.metadata,
    }


def _validation_history_entry(
    *,
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    timestamp: str,
) -> Optional[Dict[str, Any]]:
    verification = response.metadata.get("verification")
    verification = verification if isinstance(verification, dict) else None
    validation_result = (
        verification.get("status") if verification else None
    ) or response.metadata.get("verification_result") or response.metadata.get("validation_result")
    input_relevance = response.metadata.get("input_relevance")
    if validation_result is None and input_relevance is None:
        return None
    return {
        "turn_id": response.turn_id,
        "timestamp": timestamp,
        "student_message": request.message,
        "action": request.action.value,
        "input_relevance": input_relevance,
        "validation_result": validation_result,
        "misconception_type": response.metadata.get("misconception_type")
        or response.metadata.get("mistake_category"),
        "mistake_category": response.metadata.get("mistake_category")
        or response.metadata.get("misconception_type"),
        "current_step_index": response.board.metadata.get(
            "current_step_index",
            request.current_state.current_step_index,
        ),
        "expected_step": response.metadata.get("expected_step")
        or response.board.metadata.get("expected_step"),
        "mastery_signal": response.mastery_signal.value,
        "verification": verification,
        "evidence": (verification or response.metadata.get("verification_evidence"))
        or response.metadata.get("solver_facts"),
    }


def _verification_record(
    entry: Optional[Dict[str, Any]], response: VisualTutorTurnResponse
) -> Optional[Dict[str, Any]]:
    if entry is None:
        return None
    contract = response.metadata.get("verification")
    if isinstance(contract, dict):
        return {"turn_id": entry["turn_id"], "timestamp": entry["timestamp"], **contract}
    return {
        "turn_id": entry["turn_id"],
        "status": entry.get("validation_result") or "cannot_verify",
        "input_relevance": entry.get("input_relevance"),
        "evidence": entry.get("evidence"),
        "timestamp": entry["timestamp"],
        "verified": bool(
            isinstance(response.metadata.get("solver_facts"), dict)
            and response.metadata["solver_facts"].get("sympy_verified")
        ),
    }


def _session_status(response: VisualTutorTurnResponse) -> str:
    stage = response.teaching_stage.lesson_state.value if response.teaching_stage else None
    if stage == "complete" or response.mastery_signal.value == "mastered":
        return "completed"
    return "active"


def _targeted_practice_state(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    session: VisualTutorSession,
) -> Dict[str, Any]:
    for source in (response.metadata, request.metadata):
        value = source.get("targeted_practice")
        if isinstance(value, dict):
            return value
    existing = getattr(session, "targeted_practice", None)
    return dict(existing) if isinstance(existing, dict) else {}


def _replay_snapshot(
    *,
    response: VisualTutorTurnResponse,
    board_version: int,
    live_snapshot: Dict[str, Any],
    timestamp: str,
) -> Dict[str, Any]:
    return {
        "board_version": board_version,
        "board_schema_version": int(response.metadata.get("board_schema_version", 1)),
        "turn_id": response.turn_id,
        "timestamp": timestamp,
        "teaching_board_state": live_snapshot["teaching_board_state"],
        "played_action_ids": live_snapshot["played_action_ids"],
        "hidden_element_ids": live_snapshot["hidden_element_ids"],
        "locked_element_ids": live_snapshot["locked_element_ids"],
        "final_answer_locked": response.final_answer_locked,
    }


def _response_source_history_entry(
    *,
    response: VisualTutorTurnResponse,
    timestamp: str,
) -> Dict[str, Any]:
    return {
        "turn_id": response.turn_id,
        "timestamp": timestamp,
        "response_source": response.metadata.get("response_source"),
        "solver_name": response.metadata.get("solver_name"),
        "llm_called": response.metadata.get("llm_called"),
        "llm_provider": response.metadata.get("llm_provider"),
        "fallback_reason": response.metadata.get("fallback_reason"),
    }


def _board_action_history_entry(
    *,
    response: VisualTutorTurnResponse,
    timestamp: str,
) -> Optional[Dict[str, Any]]:
    action_ids = [
        str(action.id)
        for action in response.board_actions
        if getattr(action, "id", None)
        and _is_durable_board_action(action.model_dump(mode="json"))
    ]
    patch_action_ids = [
        str(action.id)
        for action in response.board_actions
        if getattr(action, "id", None)
        and not _is_durable_board_action(action.model_dump(mode="json"))
    ]
    if not action_ids and not patch_action_ids:
        return None
    return {
        "turn_id": response.turn_id,
        "timestamp": timestamp,
        "action_ids": action_ids,
        "scoped_action_ids": [
            f"{response.turn_id}:{action_id}" for action_id in action_ids
        ],
        "action_count": len(action_ids),
        "patch_action_ids": patch_action_ids,
        "patch_action_count": len(patch_action_ids),
    }


def _next_strategy_history(
    *,
    previous_history: list[dict[str, Any]],
    response: VisualTutorTurnResponse,
    validation_entry: Optional[Dict[str, Any]],
    timestamp: str,
    limit: int = 12,
) -> list[dict[str, Any]]:
    history = [entry for entry in previous_history if isinstance(entry, dict)]
    interaction_type = (
        response.interaction.type.value
        if response.interaction is not None
        else None
    )
    mistake_category = None
    if validation_entry is not None:
        mistake_category = (
            validation_entry.get("mistake_category")
            or validation_entry.get("misconception_type")
        )
    if not mistake_category:
        mistake_category = (
            response.metadata.get("mistake_category")
            or response.metadata.get("misconception_type")
        )
    adaptive_decision = response.metadata.get("adaptive_tutor_decision")
    if not isinstance(adaptive_decision, dict):
        adaptive_decision = {}
    entry = {
        "turn_id": response.turn_id,
        "timestamp": timestamp,
        "tutor_move": response.metadata.get("tutor_move")
        or response.metadata.get("teaching_strategy")
        or adaptive_decision.get("tutor_move"),
        "interaction_type": interaction_type,
        "mistake_category_addressed": mistake_category,
        "board_update_mode": response.metadata.get("board_update_mode", "replace"),
        "asked_for_student_attempt": _response_asked_for_student_attempt(response),
        "explanation_strategy": response.metadata.get("explanation_strategy")
        or adaptive_decision.get("explanation_strategy"),
        "mastery_signal": response.mastery_signal.value,
    }
    history.append(entry)
    return history[-limit:]


def _response_asked_for_student_attempt(response: VisualTutorTurnResponse) -> bool:
    if response.interaction is None:
        return bool(response.student_task)
    if response.interaction.input_enabled is False:
        return False
    return True


def _locked_canvas_element_ids(*, canvas: Any, actions: list[dict]) -> list[str]:
    ids: list[str] = []
    if isinstance(canvas, dict):
        for element in canvas.get("elements") or []:
            if isinstance(element, dict) and (
                element.get("locked") is True
                or element.get("metadata", {}).get("hidden") is True
            ):
                _append_unique(ids, str(element.get("id") or ""))
        for element_id in canvas.get("locked_element_ids") or []:
            _append_unique(ids, str(element_id))
    for action in actions:
        if isinstance(action, dict) and (
            action.get("locked") is True
            or action.get("type") == "hide"
            or action.get("metadata", {}).get("hidden") is True
        ):
            _append_unique(ids, str(action.get("target_id") or action.get("id") or ""))
    return ids


def _revealed_canvas_element_ids(*, canvas: Any, actions: list[dict]) -> list[str]:
    ids: list[str] = []
    if isinstance(canvas, dict):
        for element_id in canvas.get("revealed_element_ids") or []:
            _append_unique(ids, str(element_id))
        for element in canvas.get("elements") or []:
            if isinstance(element, dict) and not element.get("locked"):
                _append_unique(ids, str(element.get("id") or ""))
    for action in actions:
        if not isinstance(action, dict):
            continue
        if (
            action.get("type") in {"write_text", "write_equation", "draw_point"}
            and action.get("locked") is not True
            and action.get("metadata", {}).get("hidden") is not True
        ):
            _append_unique(ids, str(action.get("id") or ""))
    return ids


def _current_focus_element_id(*, canvas: Any, actions: list[dict]) -> Optional[str]:
    if isinstance(canvas, dict) and canvas.get("focus_element_id"):
        return str(canvas["focus_element_id"])
    for action in reversed(actions):
        if not isinstance(action, dict):
            continue
        if action.get("type") in {"focus", "highlight"} and (
            action.get("target_id") or action.get("id")
        ):
            return str(action.get("target_id") or action.get("id"))
        if action.get("metadata", {}).get("current_step") is True and action.get("id"):
            return str(action["id"])
    return None


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _merge_ids(*groups: Any) -> list[str]:
    values: list[str] = []
    for group in groups:
        if not group:
            continue
        for value in group:
            _append_unique(values, str(value))
    return values


def _sort_actions(actions: list[dict]) -> list[dict]:
    return sorted(
        [action for action in actions if isinstance(action, dict)],
        key=lambda action: int(action.get("sequence_index") or 0),
    )


def _patch_op(action: Dict[str, Any]) -> Optional[str]:
    metadata = action.get("metadata")
    if isinstance(metadata, dict) and metadata.get("patch_op") is not None:
        return str(metadata["patch_op"])
    action_type = (_enum_or_value(action.get("type")) or "").lower()
    if action_type == "erase":
        return "remove"
    if action_type == "fade_previous":
        return "fade"
    return None


def _is_durable_board_action(action: Dict[str, Any]) -> bool:
    op = _patch_op(action)
    return op is None or op in {"add", "update"}


def _target_or_id(action: Dict[str, Any]) -> Optional[str]:
    target = action.get("target_id") or action.get("targetId") or action.get("id")
    if target is None:
        return None
    target = str(target).strip()
    return target or None


def _enum_or_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(getattr(value, "value", value))
