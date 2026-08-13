from __future__ import annotations

import uuid
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from api.core.database import get_database, mongodb_manager
from api.core.config import settings
from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorSession,
    VisualTutorSessionCreateRequest,
    VisualTutorSessionListResponse,
    VisualTutorStudentIntent,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.session_store import (
    BoardVersionConflictError,
    VisualTutorSessionStore,
)
from api.services.visual_tutor.practice_generator import generate_practice_problem
from api.core.visual_tutor_gateway_auth import (
    emit_visual_tutor_audit_event,
    enforce_gateway_user,
    require_visual_tutor_service,
    require_visual_tutor_gateway,
)

router = APIRouter(prefix="/api/v1/visual_tutor", tags=["Visual Tutor"])


async def _llm_provider_ready() -> bool:
    """Perform a bounded, credential-aware provider probe without generating text."""
    provider = settings.VISUAL_TUTOR_LLM_PROVIDER.strip().lower()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            if provider in {"openrouter", "auto"}:
                if not settings.OPENROUTER_API_KEY:
                    return False
                response = await client.get(
                    "https://openrouter.ai/api/v1/auth/key",
                    headers={"Authorization": f"Bearer {settings.OPENROUTER_API_KEY}"},
                )
                return response.status_code == 200
            if provider == "ollama":
                response = await client.get(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
                )
                return response.status_code == 200
    except (httpx.HTTPError, ValueError):
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
    optional = {
        "ocr": "healthy" if settings.VISUAL_TUTOR_OCR_ENABLED and bool(settings.GEMINI_API_KEY) else "degraded",
        "stt": "healthy" if settings.VISUAL_TUTOR_STT_ENABLED and bool(settings.STT_MODEL_NAME) else "degraded",
        "tts": "healthy" if settings.VISUAL_TUTOR_TTS_ENABLED and bool(settings.TTS_MODEL_PATH) else "degraded",
    }
    status_value = "unavailable" if not mongo_ok or not llm_ok else (
        "degraded" if "degraded" in optional.values() else "healthy"
    )
    return JSONResponse(
        status_code=200 if status_value != "unavailable" else 503,
        content={
            "status": status_value,
            "dependencies": {
                "durable_session_store": "healthy" if mongo_ok else "unavailable",
                "visual_tutor_ai": "healthy" if llm_ok else "unavailable",
                **optional,
            },
        },
    )


async def get_visual_tutor_store(
    db: AsyncIOMotorDatabase = Depends(get_database),
) -> VisualTutorSessionStore:
    return VisualTutorSessionStore(db)


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


@router.post("/sessions", response_model=VisualTutorSession)
async def create_visual_tutor_session(
    request: VisualTutorSessionCreateRequest,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> VisualTutorSession:
    user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    enforce_gateway_user(user_id, request.user_id)
    request.user_id = user_id
    session = await store.create_session(request)
    emit_visual_tutor_audit_event(
        "visual_tutor_session_created", user_id=user_id, session_id=session.session_id
    )
    return session


@router.get("/sessions/{session_id}", response_model=VisualTutorSession)
async def get_visual_tutor_session(
    session_id: str,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> VisualTutorSession:
    user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    session = await store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Visual Tutor session not found")
    _assert_owner(session, user_id)
    emit_visual_tutor_audit_event(
        "visual_tutor_session_read", user_id=user_id, session_id=session_id
    )
    return session


@router.get("/sessions/user/{user_id}", response_model=VisualTutorSessionListResponse)
async def list_visual_tutor_sessions(
    user_id: str,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> VisualTutorSessionListResponse:
    gateway_user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    enforce_gateway_user(gateway_user_id, user_id)
    sessions = await store.list_user_sessions(gateway_user_id)
    emit_visual_tutor_audit_event(
        "visual_tutor_sessions_listed", user_id=gateway_user_id, count=len(sessions)
    )
    return VisualTutorSessionListResponse(sessions=sessions, total=len(sessions))


@router.post("/turn", response_model=VisualTutorTurnResponse)
async def visual_tutor_turn(
    request: VisualTutorTurnRequest,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
    store: VisualTutorSessionStore = Depends(get_visual_tutor_store),
) -> VisualTutorTurnResponse:
    user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    enforce_gateway_user(user_id, request.user_id)
    request.user_id = user_id
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
                return persisted_response
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
        if request.action == VisualTutorAction.GENERATE_PRACTICE or request.metadata.get("mode") == "next_practice" or request.metadata.get("client_intent_hint") == "new_problem":
            problem = generate_practice_problem(
                topic=request.topic or "Linear Equations",
                metadata=request.metadata,
            )
            request.action = VisualTutorAction.SUBMIT_PROBLEM
            request.student_intent = VisualTutorStudentIntent.NEW_PROBLEM
            request.message = problem["problem_text"]
            request.current_state = VisualTutorTurnState(
                problem_instance_id=f"practice-{uuid.uuid4().hex[:8]}",
                problem_text=problem["problem_text"]
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

    response = handle_visual_tutor_turn(request)
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
        }
    )
    emit_visual_tutor_audit_event(
        "visual_tutor_turn_completed",
        user_id=user_id,
        session_id=response.session_id,
        turn_id=response.turn_id,
        board_version=next_board_version,
        action=request.action.value,
    )
    return response
