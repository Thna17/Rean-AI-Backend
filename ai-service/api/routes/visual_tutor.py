from __future__ import annotations

import uuid
import asyncio
import httpx
import json
import logging
import re
import shlex
import subprocess
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from api.core.database import get_database, mongodb_manager
from api.core.config import settings
from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorSession,
    PublicVisualTutorSession,
    VisualTutorSessionCreateRequest,
    VisualTutorSessionListResponse,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
    VisualTutorTurnResponse,
    VisualTutorClientTelemetryBatch,
    VisualTutorStepTurnRequest,
    VisualTutorStepTurnResponse,
)
from api.services.visual_tutor.orchestrator import (
    handle_visual_tutor_step_turn,
    handle_visual_tutor_turn,
)
from api.services.visual_tutor.session_store import (
    BoardVersionConflictError,
    ExpertStepConflictError,
    VisualTutorSessionStore,
)
from api.services.visual_tutor.lesson_state import (
    bind_authoritative_lesson_state,
    hydrate_request_lesson_state,
)
from api.services.visual_tutor.learner_memory import LearnerMemoryStore
from api.services.visual_tutor.practice_generator import generate_practice_problem
from api.services.visual_tutor.local_logic_demo import matches_local_logic_demo
from api.services.visual_tutor.local_limits_demo import matches_local_limits_demo
from api.services.visual_tutor.public_response import (
    project_public_session,
    project_public_tutor_turn,
)
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan
from api.services.curriculum.curriculum_store import get_default_curriculum_store
from api.services.visual_tutor.client_telemetry import get_client_telemetry_ingestor
from api.services.visual_tutor.pilot import enforce_pilot_scope
from api.core.visual_tutor_gateway_auth import (
    emit_visual_tutor_audit_event,
    enforce_gateway_user,
    require_visual_tutor_service,
    require_visual_tutor_gateway,
)

router = APIRouter(prefix="/api/v1/visual_tutor", tags=["Visual Tutor"])
logger = logging.getLogger(__name__)

_STREAM_SCHEMA_VERSION = 1
_STREAM_TIMEOUT_SECONDS = 45
_STREAM_EVENT_TYPES = {
    "status",
    "speech_ready",
    "board_action",
    "board_patch",
    "turn_complete",
    "error",
}
_SAFE_STREAM_ID = re.compile(r"^[A-Za-z0-9_-]{1,120}$")


@router.post("/telemetry", status_code=202)
async def ingest_visual_tutor_client_telemetry(
    batch: VisualTutorClientTelemetryBatch,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
) -> dict[str, str]:
    """Accept only bounded operational aggregates; never lesson content."""
    user_id = require_visual_tutor_gateway(
        x_visual_tutor_internal_token, x_visual_tutor_user_id
    )
    # Deliberately do not log the user or body on this high-volume endpoint.
    return {"status": get_client_telemetry_ingestor().ingest(
        authenticated_user=user_id, batch=batch
    )}


def _provisional_intro_action(
    *,
    stream_id: str,
    request: VisualTutorTurnRequest,
    board_version: int,
    base_board_version: int,
) -> dict[str, object]:
    """Return one renderer-safe visual unit before the full lesson is ready.

    This is deliberately server-authored rather than model-authored: it gives
    the learner immediate, truthful feedback without streaming partial model
    JSON or revealing an answer before the final policy has been applied.
    The final persisted turn remains the sole lesson authority and replaces
    this provisional unit on ``turn_complete``.
    """
    problem_instance_id = (
        request.current_state.problem_instance_id or f"stream-{stream_id[:16]}"
    )
    active_step_id = request.current_state.active_step_id or "stream-preview"
    action = {
        "id": f"stream-preview-{stream_id[:16]}",
        "action_id": f"stream-preview-{stream_id[:16]}",
        "type": "write_text",
        "sequence_index": 0,
        "duration_ms": 520,
        # Laid out by Flutter in the normal reading flow. With fixed
        # coordinates this preview was painted on top of the turn's real first
        # line, so the two overlapped while the board was being written.
        "layout_zone": "problem",
        "layout_flow": "vertical",
        "section_id": "stream-preview",
        "text": "Let’s identify the important information first.",
        # No "locked": the Flutter contract rejects any action carrying a key
        # it does not know, so this preview showed as "One board item could
        # not be shown" at the start of every single streamed turn.
        "hidden": False,
        "problem_instance_id": problem_instance_id,
        "active_step_id": active_step_id,
        "board_version": board_version,
        "base_board_version": base_board_version,
        "metadata": {"provisional": True, "source": "server_live_preview"},
    }
    # Keep the streamed first unit covered by the same renderer-safe action
    # validation as planner output.  Identity/version fields are transport-only.
    validate_teaching_plan(
        {
            "schema_version": 1,
            "representation": "conceptual_explanation",
            "learning_objective": "Identify the information needed for the next step.",
            "teaching_message": "Start by identifying the important information.",
            "board_actions": [
                {
                    key: value
                    for key, value in action.items()
                    if key
                    not in {
                        "problem_instance_id",
                        "active_step_id",
                        "action_id",
                        "board_version",
                        "base_board_version",
                        "metadata",
                        "locked",
                    }
                },
                {
                    "id": f"stream-preview-task-{stream_id[:16]}",
                    "type": "student_task",
                    "sequence_index": 1,
                    "x": 40,
                    "y": 124,
                    "width": 620,
                    "height": 56,
                    "text": "Which information looks important?",
                    "requires_student_response": True,
                    "task_type": "conceptual_operation",
                },
            ],
            "allowed_student_actions": ["submit_answer"],
            "hidden_answer_policy": {
                "mode": "hidden",
                "deterministic_policy_permits_final_reveal": False,
            },
            "next_state_policy": {
                "correct": "continue",
                "invalid": "reteach",
                "incomplete": "ask_for_work",
                "stuck": "ask_for_work",
                "hint": "continue",
                "explain_differently": "reteach",
            },
        }
    )
    return action


def _sse_frame(event: dict[str, object]) -> bytes:
    """Encode one bounded student-safe event; event data is never raw state."""
    return (
        f"id: {event['event_id']}\n"
        "event: visual_tutor\n"
        f"data: {json.dumps(event, separators=(',', ':'), ensure_ascii=False)}\n\n"
    ).encode("utf-8")


def _stream_id_for(request: VisualTutorTurnRequest) -> str:
    """Use a conservative SSE identifier; request idempotency stays unchanged."""
    candidate = (request.idempotency_key or "").strip()
    return candidate if _SAFE_STREAM_ID.fullmatch(candidate) else uuid.uuid4().hex


def _stream_event(
    *,
    stream_id: str,
    sequence: int,
    event_type: str,
    session_id: str,
    turn_id: str | None,
    board_version: int | None,
    base_board_version: int | None,
    data: dict[str, object],
) -> dict[str, object]:
    if event_type not in _STREAM_EVENT_TYPES:
        raise ValueError("unsupported Visual Tutor stream event")
    return {
        "schema_version": _STREAM_SCHEMA_VERSION,
        "stream_id": stream_id,
        "event_id": f"{stream_id}:{sequence}",
        "sequence": sequence,
        "type": event_type,
        "session_id": session_id,
        "turn_id": turn_id,
        "board_version": board_version,
        "base_board_version": base_board_version,
        "emitted_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


async def _llm_provider_ready() -> bool:
    """Perform a bounded, credential-aware provider probe without generating text."""
    provider = settings.VISUAL_TUTOR_LLM_PROVIDER.strip().lower()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            if provider in {"openrouter", "auto"}:
                if not settings.OPENROUTER_API_KEY:
                    return False
                response = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                )
                return response.status_code == 200
            if provider == "deepseek":
                if not settings.DEEPSEEK_API_KEY:
                    return False
                try:
                    response = await client.get(
                        "https://api.deepseek.com/models",
                        headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"},
                    )
                    return response.status_code == 200
                except Exception:
                    if settings.ALLOW_DEVELOPMENT_FALLBACKS and settings.DEEPSEEK_API_KEY:
                        return True
                    return False
            if provider == "ollama":
                response = await client.get(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
                )
                return response.status_code == 200
        if provider in {"codex", "codex_cli"}:
            # Codex CLI is supported only for host-local development. Probe the
            # executable itself; generating a lesson here would spend tokens on
            # every health check. The planner still performs the real OAuth
            # backed invocation and fails closed if it cannot authenticate.
            command = shlex.split(settings.VISUAL_TUTOR_CODEX_CLI_COMMAND)
            if not command:
                return False
            result = await asyncio.to_thread(
                subprocess.run,
                [command[0], "--version"],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
            return result.returncode == 0
    except (httpx.HTTPError, ValueError):
        return False
    except (OSError, subprocess.SubprocessError):
        return False
    return False


@router.get("/readiness")
async def visual_tutor_readiness(
    x_visual_tutor_internal_token: str | None = Header(default=None),
):
    """Private, secret-free dependency readiness for the TypeScript gateway."""
    require_visual_tutor_service(x_visual_tutor_internal_token)
    mongo_ok = False
    try:
        if mongodb_manager._client is not None:
            await mongodb_manager._client.admin.command("ping")
            mongo_ok = True
    except Exception:
        mongo_ok = False

    llm_ok = await _llm_provider_ready()
    curriculum_ok = True
    curriculum_count = 0
    try:
        curriculum_count = len(get_default_curriculum_store().load_chunks())
    except Exception:
        curriculum_ok = False
    optional = {
        "ocr": (
            "healthy"
            if settings.VISUAL_TUTOR_OCR_ENABLED and bool(settings.GEMINI_API_KEY)
            else "degraded"
        ),
        "stt": (
            "healthy"
            if settings.VISUAL_TUTOR_STT_ENABLED and bool(settings.STT_MODEL_NAME)
            else "degraded"
        ),
        "tts": (
            "healthy"
            if settings.VISUAL_TUTOR_TTS_ENABLED and bool(settings.TTS_MODEL_PATH)
            else "degraded"
        ),
    }
    status_value = (
        "unavailable"
        if not mongo_ok or not llm_ok or not curriculum_ok
        else ("degraded" if "degraded" in optional.values() else "healthy")
    )
    return JSONResponse(
        status_code=200 if status_value != "unavailable" else 503,
        content={
            "status": status_value,
            "dependencies": {
                "durable_session_store": "healthy" if mongo_ok else "unavailable",
                "visual_tutor_ai": "healthy" if llm_ok else "unavailable",
                "curriculum_retrieval": "healthy" if curriculum_ok else "unavailable",
                **optional,
            },
            "curriculum_index": {
                "status": "ready" if curriculum_ok else "unavailable",
                "chunk_count": curriculum_count,
            },
        },
    )


async def get_visual_tutor_store(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> VisualTutorSessionStore:
    return VisualTutorSessionStore(db)


async def get_learner_memory_store(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> LearnerMemoryStore:
    return LearnerMemoryStore(db)


def _assert_owner(session: VisualTutorSession, user_id: str) -> None:
    if session.user_id != user_id:
        raise HTTPException(
            status_code=403, detail="Forbidden: session ownership mismatch"
        )


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _idempotency_key_from_request(request: VisualTutorTurnRequest) -> str | None:
    key = (
        request.idempotency_key
        or request.metadata.get("idempotency_key")
        or request.metadata.get("client_turn_id")
    )
    if key is None:
        return None
    key = str(key).strip()
    return key or None


@router.post("/sessions", response_model=PublicVisualTutorSession)
async def create_visual_tutor_session(
    request: VisualTutorSessionCreateRequest,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> PublicVisualTutorSession:
    user_id = require_visual_tutor_gateway(
        x_visual_tutor_internal_token, x_visual_tutor_user_id
    )
    enforce_gateway_user(user_id, request.user_id)
    request.user_id = user_id
    enforce_pilot_scope(request)
    session = await store.create_session(request)
    emit_visual_tutor_audit_event(
        "visual_tutor_session_created", user_id=user_id, session_id=session.session_id
    )
    return project_public_session(session)


@router.get("/sessions/{session_id}", response_model=PublicVisualTutorSession)
async def get_visual_tutor_session(
    session_id: str,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> PublicVisualTutorSession:
    user_id = require_visual_tutor_gateway(
        x_visual_tutor_internal_token, x_visual_tutor_user_id
    )
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Visual Tutor session not found")
    _assert_owner(session, user_id)
    emit_visual_tutor_audit_event(
        "visual_tutor_session_read", user_id=user_id, session_id=session_id
    )
    return project_public_session(session)


@router.get("/sessions/user/{user_id}", response_model=VisualTutorSessionListResponse)
async def list_visual_tutor_sessions(
    user_id: str,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> VisualTutorSessionListResponse:
    gateway_user_id = require_visual_tutor_gateway(
        x_visual_tutor_internal_token, x_visual_tutor_user_id
    )
    enforce_gateway_user(gateway_user_id, user_id)
    sessions = await store.list_user_sessions(gateway_user_id)
    emit_visual_tutor_audit_event(
        "visual_tutor_sessions_listed", user_id=gateway_user_id, count=len(sessions)
    )
    return VisualTutorSessionListResponse(sessions=sessions, total=len(sessions))


@router.post("/turn", response_model=None)
async def visual_tutor_turn(
    request: VisualTutorTurnRequest,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    x_visual_tutor_api_compatibility_version: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
    learner_memory_store: LearnerMemoryStore = Depends(get_learner_memory_store),
) -> JSONResponse:
    user_id = require_visual_tutor_gateway(
        x_visual_tutor_internal_token, x_visual_tutor_user_id
    )
    enforce_gateway_user(user_id, request.user_id)
    request.user_id = user_id
    enforce_pilot_scope(request)
    # The full historical response remains available only to an authenticated
    # development gateway that explicitly asks for compatibility version zero.
    # Production and staging ignore this header and can only emit the compact
    # student-safe contract.
    if (
        settings.ENVIRONMENT == "development"
        and x_visual_tutor_api_compatibility_version == "0"
        and request.metadata.get("public_contract_version") != 1
    ):
        request.metadata = {
            **request.metadata,
            "api_compatibility_version": 0,
        }
    if request.session_id:
        session = await store.get_session(request.session_id)
        if session is None:
            raise HTTPException(
                status_code=404, detail="Visual Tutor session not found"
            )
        _assert_owner(session, request.user_id)
        idempotency_key = _idempotency_key_from_request(request)
        if idempotency_key and hasattr(store, "get_persisted_turn_response"):
            persisted_response = await store.get_persisted_turn_response(
                session_id=request.session_id,
                idempotency_key=idempotency_key,
            )
            if persisted_response is not None:
                await _record_learner_memory(
                    learner_memory_store,
                    request=request,
                    response=persisted_response,
                    topic=request.topic or session.topic,
                    session=session,
                )
                return _turn_http_response(request, persisted_response)
        server_board_version = getattr(session, "board_version", None) or 0
        client_board_version = _safe_int(
            request.client_board_version
            if request.client_board_version is not None
            else request.metadata.get("client_board_version")
        )
        if (
            client_board_version is not None
            and client_board_version != server_board_version
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Stale client board version. Please refresh or retry.",
                    "expected_board_version": server_board_version,
                    "client_board_version": client_board_version,
                },
            )
        # The explicit Grade 10 Logic local demo uses a `new_problem` client
        # intent only to start its deterministic first teaching moment. It is
        # not targeted practice and must reach the provider-independent demo
        # handler instead of the unsupported-practice recovery branch.
        if (
            not matches_local_logic_demo(request)
            and not matches_local_limits_demo(request)
            and (
            request.action == VisualTutorAction.GENERATE_PRACTICE
            or request.metadata.get("mode") == "next_practice"
            or request.metadata.get("client_intent_hint") == "new_problem"
            )
        ):
            problem = generate_practice_problem(
                topic=request.topic or "Linear Equations",
                metadata=request.metadata,
            )
            if problem is None:
                raise HTTPException(
                    status_code=422,
                    detail="Targeted practice is not available for this topic yet. Choose one of the supported Grade 8–10 Math topics.",
                )
            request.action = VisualTutorAction.SUBMIT_PROBLEM
            request.student_intent = VisualTutorStudentIntent.NEW_PROBLEM
            request.message = problem["problem_text"]
            request.current_state = VisualTutorTurnState(
                problem_instance_id=f"practice-{uuid.uuid4().hex[:8]}",
                problem_text=problem["problem_text"],
            )
        elif (
            request.action == VisualTutorAction.SUBMIT_PROBLEM
            and request.message.strip()
            and (
                request.student_intent == VisualTutorStudentIntent.NEW_PROBLEM
                or not request.current_state.problem_text
            )
        ):
            request.current_state = VisualTutorTurnState()
        else:
            hydrate_request_lesson_state(request, session)
            if not request.current_state.problem_text and session.problem_text:
                request.current_state.problem_text = session.problem_text
            if (
                not request.current_state.normalized_problem
                and session.normalized_problem
            ):
                request.current_state.normalized_problem = session.normalized_problem
            request.current_state.current_step_index = max(
                request.current_state.current_step_index,
                session.current_step_index,
            )
            request.current_state.hint_count = max(
                request.current_state.hint_count,
                session.hint_count,
            )
            request.current_state.wrong_attempts = max(
                request.current_state.wrong_attempts,
                getattr(session, "wrong_attempts", 0) or 0,
            )
            request.current_state.final_answer_revealed = (
                request.current_state.final_answer_revealed
                or session.final_answer_revealed
            )
            request.metadata = {
                **request.metadata,
                "problem_type": request.metadata.get("problem_type")
                or session.problem_type,
                "expected_step": request.metadata.get("expected_step")
                or session.expected_step,
                "solved_variables": request.metadata.get("solved_variables")
                or session.solved_variables,
                "solver_facts": request.metadata.get("solver_facts")
                or session.solver_facts,
                "validation_history": request.metadata.get("validation_history")
                or session.validation_history,
                "stuck_count": max(
                    int(request.metadata.get("stuck_count") or 0),
                    session.stuck_count,
                ),
                "teaching_board_state": request.metadata.get("teaching_board_state")
                or session.teaching_board_state,
                "visible_board_elements": request.metadata.get("visible_board_elements")
                or session.visible_board_elements,
                "played_action_ids": request.metadata.get("played_action_ids")
                or session.played_action_ids,
                "previous_board_action_ids": request.metadata.get(
                    "previous_board_action_ids"
                )
                or session.previous_board_action_ids,
                "board_action_history": request.metadata.get("board_action_history")
                or session.board_action_history,
                "strategy_history": request.metadata.get("strategy_history")
                or session.strategy_history,
                "pending_interaction": request.metadata.get("pending_interaction")
                or session.pending_interaction,
                "response_source_history": request.metadata.get(
                    "response_source_history"
                )
                or session.response_source_history,
                "student_model": (
                    session.student_model.model_dump(mode="json")
                    if session.student_model is not None
                    else None
                ),
            }

    # Local curriculum progression is owned by the persisted session. A client
    # may report playback state, but cannot skip approved teaching moments or
    # unlock the answer by sending a larger step index.
    if request.session_id and matches_local_limits_demo(request):
        request.current_state.current_step_index = session.current_step_index
        request.current_state.wrong_attempts = session.wrong_attempts
        request.current_state.final_answer_revealed = session.final_answer_revealed

    # The expected step is retrieved from the owned, persisted session above.
    # Mark it as trusted so the orchestrator never uses a newly generated task
    # to evaluate the student's previous work.
    if request.metadata.get("expected_step"):
        request.metadata = {
            **request.metadata,
            "persisted_expected_step": request.metadata.get("expected_step"),
        }

    topic_for_memory = request.topic or (session.topic if request.session_id else None)
    await _apply_learner_memory(
        learner_memory_store,
        request=request,
        topic=topic_for_memory,
    )
    response = await asyncio.to_thread(handle_visual_tutor_turn, request)
    response = bind_authoritative_lesson_state(response, request)
    response_metadata = response.metadata if isinstance(response.metadata, dict) else {}
    sanitization = response_metadata.get("sanitization")
    if isinstance(sanitization, dict) and sanitization.get("applied") is True:
        emit_visual_tutor_audit_event(
            "answer_reveal_attempt_blocked",
            user_id=user_id,
            session_id=response.session_id,
            turn_id=response.turn_id,
        )
    if response_metadata.get("planner_fallback") is True:
        emit_visual_tutor_audit_event(
            "provider_fallback",
            user_id=user_id,
            session_id=response.session_id,
            turn_id=response.turn_id,
            fallback_reason=str(
                response_metadata.get("fallback_reason") or "planner_unavailable"
            )[:80],
        )
    verification = response_metadata.get("verification")
    if (
        isinstance(verification, dict)
        and verification.get("verified") is not True
        and response_metadata.get("verification_verified") is True
    ):
        emit_visual_tutor_audit_event(
            "verification_disagreement",
            user_id=user_id,
            session_id=response.session_id,
            turn_id=response.turn_id,
        )
    try:
        persisted_session = await store.persist_turn(request=request, response=response)
    except BoardVersionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": exc.message,
                "expected_board_version": exc.expected_version,
                "client_board_version": exc.client_version,
                "recovery": "Refresh the tutor session and retry the same idempotency key.",
            },
        )
    base_board_version: int = (getattr(persisted_session, "board_version", 1) or 1) - 1
    next_board_version: int = getattr(persisted_session, "board_version", 1) or 1
    response = response.model_copy(
        update={
            "board_version": next_board_version,
            "base_board_version": base_board_version,
            "metadata": {
                **response.metadata,
                "board_version": next_board_version,
                "base_board_version": base_board_version,
            },
            "authoritative_lesson_state": {
                **response.authoritative_lesson_state,
                "board_version": next_board_version,
                "base_board_version": base_board_version,
            },
        }
    )
    await _record_learner_memory(
        learner_memory_store,
        request=request,
        response=response,
        topic=topic_for_memory or persisted_session.topic,
        session=persisted_session,
    )
    emit_visual_tutor_audit_event(
        "visual_tutor_turn_completed",
        user_id=user_id,
        session_id=response.session_id,
        turn_id=response.turn_id,
        board_version=next_board_version,
        action=request.action.value,
    )
    return _turn_http_response(request, response)


@router.post("/turn/step", response_model=VisualTutorStepTurnResponse)
async def submit_visual_tutor_step_turn(
    request: VisualTutorStepTurnRequest,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> VisualTutorStepTurnResponse:
    """Advance one persisted, expert-authored visual teaching step.

    This endpoint is intentionally separate from ``/turn``.  It preserves the
    established planner contract while giving rich-media lessons a small,
    renderer-ready state machine that can be resumed on another device.
    """
    user_id = require_visual_tutor_gateway(
        x_visual_tutor_internal_token,
        x_visual_tutor_user_id,
    )
    enforce_gateway_user(user_id, request.user_id)
    request.user_id = user_id

    session = await store.get_session(request.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Visual Tutor session not found")
    _assert_owner(session, user_id)

    session_subject = _expert_subject(getattr(session, "subject", ""))
    if session_subject is None:
        raise HTTPException(
            status_code=422,
            detail="This session has an unsupported subject for expert teaching",
        )
    if session_subject != request.subject:
        raise HTTPException(
            status_code=422,
            detail="The requested subject does not match this tutor session",
        )
    existing_expert = getattr(session, "expert_metadata", {}) or {}
    if (
        getattr(session, "teaching_sequence", None)
        and isinstance(existing_expert, dict)
        and existing_expert.get("subject") not in {None, request.subject}
    ):
        raise HTTPException(
            status_code=409,
            detail="This session is already pinned to another expert subject",
        )

    problem_text = (getattr(session, "problem_text", None) or "").strip()
    if not problem_text:
        raise HTTPException(
            status_code=422,
            detail="A confirmed session problem is required for expert teaching",
        )

    grade = _session_grade(getattr(session, "grade_level", None))
    try:
        response = await handle_visual_tutor_step_turn(
            request,
            problem_text=problem_text,
            grade=grade,
            existing_sequence=getattr(session, "teaching_sequence", None),
            current_step_index=getattr(session, "current_step_index", 0),
        )
        evaluation_record = _expert_evaluation_record(request, response.evaluation)
        persisted_session = await store.persist_expert_step_state(
            session_id=session.session_id,
            teaching_sequence=response.teaching_sequence,
            current_step_index=response.current_step_index,
            evaluation=evaluation_record,
            expert_metadata=response.expert_metadata,
            user_id=user_id,
            expected_expert_step_version=getattr(session, "expert_step_version", 0),
        )
    except ValueError as exc:
        logger.info(
            "Rejected visual tutor expert step",
            extra={"session_id": session.session_id, "subject": request.subject},
        )
        raise HTTPException(
            status_code=422,
            detail="The submitted step is invalid. Refresh the lesson and try again.",
        ) from exc
    except ExpertStepConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="This lesson changed in another request. Refresh and retry.",
        ) from exc
    except LookupError as exc:
        raise HTTPException(
            status_code=404, detail="Visual Tutor session not found"
        ) from exc
    except Exception as exc:
        logger.exception(
            "Visual tutor expert step failed",
            extra={"session_id": session.session_id, "subject": request.subject},
        )
        raise HTTPException(
            status_code=503,
            detail="The expert tutor is temporarily unavailable. Please retry.",
        ) from exc

    emit_visual_tutor_audit_event(
        "visual_tutor_expert_step_completed",
        user_id=user_id,
        session_id=session.session_id,
        subject=request.subject,
        recommended_action=response.recommended_action,
    )
    return _public_expert_step_response(
        response.model_copy(
            update={"expert_step_version": persisted_session.expert_step_version}
        )
    )


def _expert_subject(value: str) -> str | None:
    """Map persisted display subjects to the expert factory identifiers."""
    normalized = value.strip().casefold()
    return {
        "math": "math",
        "maths": "math",
        "mathematics": "math",
        "physics": "physics",
        "chemistry": "chemistry",
    }.get(normalized)


def _session_grade(value: str | None) -> int:
    """Extract supported grade values without trusting arbitrary metadata."""
    match = re.search(r"\b(10|11|12)\b", value or "")
    return int(match.group(0)) if match else 10


def _expert_evaluation_record(
    request: VisualTutorStepTurnRequest,
    evaluation: dict[str, object] | None,
) -> dict[str, object] | None:
    """Add replay evidence without persisting the client-controlled rubric."""
    if evaluation is None:
        return None
    return {
        **evaluation,
        "step_id": request.step_id,
        "student_answer": request.message,
        "action": request.action,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def _public_expert_step_response(
    response: VisualTutorStepTurnResponse,
) -> VisualTutorStepTurnResponse:
    """Remove server-only rubrics before an expert plan reaches the learner."""
    sequence = [_strip_expert_rubrics(step) for step in response.teaching_sequence]
    current_step = sequence[response.current_step_index]
    return response.model_copy(
        update={"teaching_sequence": sequence, "current_step": current_step}
    )


def _strip_expert_rubrics(value: object) -> object:
    """Recursively remove answer keys and validation controls from a DTO."""
    private_keys = {
        "expected_answer",
        "expected_answers",
        "validation_strategy",
        "rubric",
        "server_rubric",
    }
    if isinstance(value, dict):
        return {
            str(key): _strip_expert_rubrics(item)
            for key, item in value.items()
            if str(key) not in private_keys
        }
    if isinstance(value, list):
        return [_strip_expert_rubrics(item) for item in value]
    return value


@router.post("/turn/stream", response_model=None)
async def visual_tutor_turn_stream(
    request: VisualTutorTurnRequest,
    http_request: Request,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    x_visual_tutor_api_compatibility_version: str | None = Header(default=None),
    last_event_id: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
    learner_memory_store: LearnerMemoryStore = Depends(get_learner_memory_store),
) -> StreamingResponse:
    """Stream safe visual progress while retaining ``/turn`` as the authority.

    Events before ``turn_complete`` are provisional presentation hints. Only the
    final, already-persisted public turn may advance client lesson state.
    Reconnection repeats this request with the same idempotency key; the normal
    turn route then returns its persisted response rather than advancing again.
    """
    # Authenticate before opening an SSE response.  The authoritative turn
    # repeats these checks defensively, but a stream must never reveal even the
    # generic preview to an unauthenticated caller.
    user_id = require_visual_tutor_gateway(
        x_visual_tutor_internal_token, x_visual_tutor_user_id
    )
    enforce_gateway_user(user_id, request.user_id)
    request.user_id = user_id
    # Reject a stale/foreign session before the HTTP status turns into an SSE
    # 200 response.  ``visual_tutor_turn`` repeats this immediately before
    # persistence as the authoritative race-safe check.
    if request.session_id:
        stream_session = await store.get_session(request.session_id)
        if stream_session is None:
            raise HTTPException(
                status_code=404, detail="Visual Tutor session not found"
            )
        _assert_owner(stream_session, user_id)
        expected_version = getattr(stream_session, "board_version", None) or 0
        supplied_version = _safe_int(
            request.client_board_version
            if request.client_board_version is not None
            else request.metadata.get("client_board_version")
        )
        if supplied_version is not None and supplied_version != expected_version:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Stale client board version. Please refresh or retry.",
                    "expected_board_version": expected_version,
                    "client_board_version": supplied_version,
                },
            )
    stream_id = _stream_id_for(request)
    session_id = request.session_id or ""
    resume_after = -1
    if last_event_id and last_event_id.startswith(f"{stream_id}:"):
        try:
            resume_after = max(-1, int(last_event_id.rsplit(":", 1)[1]))
        except ValueError:
            resume_after = -1

    async def emit(
        sequence: int,
        event_type: str,
        *,
        turn_id: str | None = None,
        board_version: int | None = None,
        base_board_version: int | None = None,
        data: dict[str, object],
    ) -> bytes | None:
        if sequence <= resume_after:
            return None
        return _sse_frame(
            _stream_event(
                stream_id=stream_id,
                sequence=sequence,
                event_type=event_type,
                session_id=session_id,
                turn_id=turn_id,
                board_version=board_version,
                base_board_version=base_board_version,
                data=data,
            )
        )

    async def generate():
        first = await emit(0, "status", data={"state": "planning"})
        if first is not None:
            yield first
        if await http_request.is_disconnected():
            return

        preview_base_version = (
            _safe_int(
                request.client_board_version
                if request.client_board_version is not None
                else request.metadata.get("client_board_version")
            )
            or 0
        )
        preview_board_version = preview_base_version + 1
        # The authenticated, version-checked turn can now begin in parallel
        # with delivery of the first visual unit.  The preview is precomputed
        # before this task so request-state hydration cannot affect it.
        completed_task = asyncio.create_task(
            visual_tutor_turn(
                request=request,
                x_visual_tutor_user_id=x_visual_tutor_user_id,
                x_visual_tutor_internal_token=x_visual_tutor_internal_token,
                # Streams are always the compact public contract; never let a
                # development-only legacy response into an SSE frame.
                x_visual_tutor_api_compatibility_version=None,
                store=store,
                learner_memory_store=learner_memory_store,
            )
        )
        try:
            preview = _provisional_intro_action(
                stream_id=stream_id,
                request=request,
                board_version=preview_board_version,
                base_board_version=preview_base_version,
            )
            frame = await emit(
                1,
                "board_action",
                board_version=preview_board_version,
                base_board_version=preview_base_version,
                data={"action": preview, "provisional": True},
            )
            if frame is not None:
                yield frame
            planning = await emit(2, "status", data={"state": "reasoning"})
            if planning is not None:
                yield planning
        except Exception:
            # The preview is an enhancement only.  The complete, validated
            # response below remains usable if this local unit cannot be made.
            pass
        try:
            # Reuse the non-streaming implementation: it owns authorization,
            # board-version checks, idempotency, persistence, and projection.
            elapsed = 0.0
            while not completed_task.done():
                if await http_request.is_disconnected():
                    completed_task.cancel()
                    try:
                        await completed_task
                    except asyncio.CancelledError:
                        pass
                    return
                await asyncio.sleep(0.1)
                elapsed += 0.1
                if elapsed >= _STREAM_TIMEOUT_SECONDS:
                    raise asyncio.TimeoutError
            completed = completed_task.result()
            payload = json.loads(completed.body.decode("utf-8"))
        except asyncio.TimeoutError:
            completed_task.cancel()
            try:
                await completed_task
            except asyncio.CancelledError:
                pass
            frame = await emit(
                3,
                "error",
                data={
                    "code": "TIMEOUT",
                    "message": "The tutor is taking too long. Please retry.",
                    "recoverable": True,
                },
            )
            if frame is not None:
                yield frame
            return
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            frame = await emit(
                3,
                "error",
                data={
                    "code": (
                        "STALE_BOARD"
                        if exc.status_code == 409
                        else "STREAM_UNAVAILABLE"
                    ),
                    "message": str(
                        detail.get("message") or "The tutor stream could not start."
                    ),
                    "recoverable": True,
                    **(
                        {"expected_board_version": detail["expected_board_version"]}
                        if isinstance(detail.get("expected_board_version"), int)
                        else {}
                    ),
                },
            )
            if frame is not None:
                yield frame
            return
        except Exception:
            frame = await emit(
                3,
                "error",
                data={
                    "code": "STREAM_UNAVAILABLE",
                    "message": "The tutor stream could not start.",
                    "recoverable": True,
                },
            )
            if frame is not None:
                yield frame
            return
        finally:
            if await http_request.is_disconnected() and not completed_task.done():
                completed_task.cancel()

        if not isinstance(payload, dict) or "teaching_plan" not in payload:
            frame = await emit(
                3,
                "error",
                data={
                    "code": "STREAM_UNAVAILABLE",
                    "message": "The tutor response could not be streamed safely.",
                    "recoverable": True,
                },
            )
            if frame is not None:
                yield frame
            return
        turn_id = str(payload.get("turn_id") or "")
        board_version = (
            payload.get("board_version")
            if isinstance(payload.get("board_version"), int)
            else None
        )
        base_board_version = (
            payload.get("base_board_version")
            if isinstance(payload.get("base_board_version"), int)
            else None
        )
        plan = (
            payload.get("teaching_plan")
            if isinstance(payload.get("teaching_plan"), dict)
            else {}
        )
        actions = list(plan.get("visible_board_actions") or [])
        task = plan.get("active_student_task")
        if isinstance(task, dict):
            actions.append(task)
        # Revalidate the exact visible plan before emitting any incremental
        # action. Identity fields are transport-only and are removed before
        # the strict planner schema check.
        try:
            validate_teaching_plan(
                {
                    "schema_version": plan.get("schema_version"),
                    "representation": plan.get("representation"),
                    "learning_objective": plan.get("learning_objective"),
                    "teaching_message": plan.get("teaching_message"),
                    "board_actions": [
                        {
                            key: value
                            for key, value in action.items()
                            if key
                            not in {
                                "problem_instance_id",
                                "active_step_id",
                                "action_id",
                                "board_version",
                                "base_board_version",
                            }
                        }
                        for action in actions
                        if isinstance(action, dict)
                    ],
                    "allowed_student_actions": plan.get("allowed_student_actions"),
                    "hidden_answer_policy": plan.get("hidden_answer_policy"),
                    "next_state_policy": plan.get("next_state_policy"),
                }
            )
        except (TypeError, ValueError):
            frame = await emit(
                4,
                "error",
                turn_id=turn_id,
                board_version=board_version,
                base_board_version=base_board_version,
                data={
                    "code": "STREAM_UNAVAILABLE",
                    "message": "The tutor board could not be streamed safely.",
                    "recoverable": True,
                },
            )
            if frame is not None:
                yield frame
            return
        # Teaching text is covered by the strict plan validation above.  Do
        # not expose speech before that check, even though it is not a board
        # action itself.
        message = plan.get("teaching_message")
        if isinstance(message, str) and message.strip():
            frame = await emit(
                3,
                "speech_ready",
                turn_id=turn_id,
                board_version=board_version,
                base_board_version=base_board_version,
                data={
                    "text": message,
                    "language": "km" if request.locale == "km" else "en",
                },
            )
            if frame is not None:
                yield frame
        for index, action in enumerate(actions, start=4):
            if not isinstance(action, dict):
                continue
            frame = await emit(
                index,
                "board_action",
                turn_id=turn_id,
                board_version=board_version,
                base_board_version=base_board_version,
                data={"action": action, "provisional": False},
            )
            if frame is not None:
                yield frame
        complete = await emit(
            len(actions) + 4,
            "turn_complete",
            turn_id=turn_id,
            board_version=board_version,
            base_board_version=base_board_version,
            data={"response": payload},
        )
        if complete is not None:
            yield complete

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-store",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


def _turn_http_response(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
) -> JSONResponse:
    """Serve the compact contract only to clients that explicitly opt in.

    Legacy API consumers and old replay fixtures remain compatible during the
    migration; Flutter opts in on every production request.
    """
    # Flutter and the TypeScript gateway always request this version. Legacy
    # full responses are a temporary development-only compatibility path and
    # require an explicit opt-in, so no production student can receive board,
    # solver, RAG, replay, or persistence internals by accident.
    if request.metadata.get("public_contract_version") == 1:
        return JSONResponse(content=project_public_tutor_turn(response))
    if settings.ENVIRONMENT in {"staging", "production"}:
        return JSONResponse(content=project_public_tutor_turn(response))
    if request.metadata.get("api_compatibility_version") == 0:
        return JSONResponse(content=response.model_dump(mode="json"))
    return JSONResponse(content=project_public_tutor_turn(response))


async def _apply_learner_memory(
    learner_memory_store: LearnerMemoryStore,
    *,
    request: VisualTutorTurnRequest,
    topic: str | None,
) -> None:
    """Attach only bounded factual evidence for the server-side planner."""
    memory = await learner_memory_store.get_for_authenticated_user(
        user_id=request.user_id,
        subject=request.subject,
        topic=topic or request.topic,
    )
    if memory is None:
        return
    existing = request.metadata.get("student_model")
    student_model = dict(existing) if isinstance(existing, dict) else {}
    student_metadata = student_model.get("metadata")
    student_metadata = (
        dict(student_metadata) if isinstance(student_metadata, dict) else {}
    )
    student_metadata["learner_memory"] = memory.orchestrator_context()
    student_model["metadata"] = student_metadata
    student_model["recent_mistakes"] = memory.misconceptions[-3:]
    student_model["hint_level"] = (
        memory.hint_levels_used[-1] if memory.hint_levels_used else 0
    )
    # Session state owns the current streak. Topic memory owns long-term
    # evidence, so never convert all historical misses into a current streak.
    student_model.setdefault("wrong_attempt_streak", 0)
    student_model["preferred_language"] = memory.preferred_language
    student_model["recommended_depth"] = (
        "concise"
        if memory.mastery_evidence.get("readiness") == "ready_for_challenge"
        else "standard"
    )
    if memory.mastery_evidence.get("readiness") == "ready_for_challenge":
        student_model["understanding"] = "solid"
    request.metadata = {**request.metadata, "student_model": student_model}


async def _record_learner_memory(
    learner_memory_store: LearnerMemoryStore,
    *,
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    topic: str | None,
    session: VisualTutorSession,
) -> None:
    # The profile remains private to the AI service.  The response only contains
    # the ordinary teaching plan, never these internal evidence records.
    await learner_memory_store.record_turn(
        request=request,
        response=response,
        topic=topic,
        session_summary={
            "session_id": session.session_id,
            "turn_id": response.turn_id,
            "timestamp": session.updated_at,
            "status": session.status,
            "completed": session.status == "completed",
            "representation": (
                (response.metadata.get("teaching_plan") or {}).get("representation")
                if isinstance(response.metadata.get("teaching_plan"), dict)
                else None
            ),
            "verified_status": (
                (response.metadata.get("verification") or {}).get("status")
                if isinstance(response.metadata.get("verification"), dict)
                else None
            ),
            "active_task": _safe_active_task(response),
            "board_history": _safe_board_history(response),
        },
    )


def _safe_active_task(response: VisualTutorTurnResponse) -> dict[str, str]:
    plan = response.metadata.get("teaching_plan")
    if not isinstance(plan, dict):
        return {}
    actions = plan.get("board_actions")
    if not isinstance(actions, list):
        return {}
    for action in actions:
        if isinstance(action, dict) and action.get("requires_student_response") is True:
            return {
                key: str(action[key])[:120]
                for key in ("id", "type", "task_type")
                if action.get(key) is not None
            }
    return {}


def _safe_board_history(response: VisualTutorTurnResponse) -> dict[str, object]:
    plan = response.metadata.get("teaching_plan")
    plan = plan if isinstance(plan, dict) else {}
    actions = plan.get("board_actions")
    return {
        "board_version": response.board_version or 0,
        "representation": str(plan.get("representation") or "")[:80],
        "action_types": (
            [
                str(action.get("type"))[:80]
                for action in actions
                if isinstance(action, dict) and action.get("type")
            ][:24]
            if isinstance(actions, list)
            else []
        ),
    }
