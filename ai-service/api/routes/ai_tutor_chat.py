"""
AI Tutor Chat Route — Story-driven conversational AI with the parrot mascot.

Pipeline:
  1. STT (if voice input) → Whisper transcription
  2. TraceCAG pipeline → KG expansion + diagnosis + retrieval
    3. TraceCAG generation (internal model fallback handled by TraceCAG)
  4. TTS synthesis → gTTS / Piper for AI Tutor's voice
  5. Return structured response with audio, story context, corrections

Integrates with the existing TraceCAG system for document retrieval
and knowledge graph expansion to make conversations contextually rich.
"""

import asyncio
import logging
import os
import json
import uuid
import time
import base64
import hashlib
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, Query, Header, Request
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId
from pymongo.errors import OperationFailure
from pydantic import BaseModel, Field
from api.core.auth import AuthenticatedUser, enforce_user_scope, get_current_user
from api.core.audit_emitter import emit_ai_audit_event
from api.core.quota_guard import default_token_cost_for_endpoint, enforce_user_quota
from api.core.database import get_database
from api.utils.cursor import (
    build_pagination,
    decode_cursor_str,
    encode_cursor,
    load_full_cursor,
    to_iso_timestamp,
)
from api.services.ai_tutor_session_store import AiTutorSessionStore, get_ai_tutor_store
from api.services.ai_tutor_idempotency_store import AiTutorIdempotencyStore, get_ai_tutor_idempotency_store
from api.services.ai_tutor_pipeline_helpers import (
    sanitize_ai_tutor_response as _sanitize_ai_tutor_response,
    synthesize_tts as _synthesize_tts,
    transcribe_audio as _transcribe_audio,
)
from api.services.socratic_guard import (
    build_socratic_context,
    maybe_build_line_equation_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai_tutor", tags=["ai_tutor-chat"])

_store: AiTutorSessionStore = get_ai_tutor_store()
_idempotency_store: AiTutorIdempotencyStore = get_ai_tutor_idempotency_store()

SAFE_FIXED_RESPONSE = (
    "Squawk! I'm temporarily unavailable right now. "
    "Please try again in a moment."
)

# SSE stream settings
_STREAM_PIPELINE_TIMEOUT_S = 50   # cancel and error if pipeline exceeds this
_HEARTBEAT_INTERVAL_S = 2.5       # how often to send ": ping" keep-alive comments


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return max(minimum, float(raw))
    except ValueError:
        return default


def _idempotency_request_hash(request: "AiTutorChatRequest") -> str:
    payload = {
        "user_id": request.user_id,
        "session_id": request.session_id,
        "message": request.message,
        "input_type": request.input_type,
        "audio_base64": request.audio_base64,
        "enable_tts": request.enable_tts,
        "learner_level": request.learner_level,
        "story_context": request.story_context,
        "subject": request.subject,
        "topic": request.topic,
        "hint_count": request.hint_count,
        "student_submitted_step": request.student_submitted_step,
        "allow_final_answer": request.allow_final_answer,
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _serialize_ai_tutor_message(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id") or doc.get("message_id") or str(doc.get("_id", "")),
        "session_id": doc.get("session_id", ""),
        "role": doc.get("role", "user"),
        "content": doc.get("content", ""),
        "timestamp": to_iso_timestamp(doc.get("timestamp")),
    }


async def _ensure_session_owner(
    session_id: str,
    current_user: AuthenticatedUser,
    db: AsyncIOMotorDatabase,
) -> Dict[str, Any]:
    session_doc = await db["ai_tutor_sessions"].find_one({"session_id": session_id})
    if not session_doc:
        raise HTTPException(status_code=404, detail="Session not found")

    owner_user_id = str(session_doc.get("user_id") or "")
    if owner_user_id and owner_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: session ownership mismatch")
    return session_doc


def _assert_cached_session_owner(
    cached_session: Dict[str, Any] | None,
    current_user: AuthenticatedUser,
) -> None:
    if not cached_session:
        return
    owner_user_id = str(cached_session.get("user_id") or "")
    if owner_user_id and owner_user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: session ownership mismatch")


async def _get_cached_session_with_messages(
    session_id: str,
) -> tuple[Dict[str, Any] | None, List[Dict[str, Any]]]:
    if callable(getattr(type(_store), "get_session_with_messages", None)):
        return await _store.get_session_with_messages(session_id)

    cached_session, cached_messages = await asyncio.gather(
        _store.get_session(session_id),
        _store.get_messages(session_id),
    )
    return cached_session, cached_messages


async def _prepare_existing_ai_tutor_session(
    session_id: str,
    current_user: AuthenticatedUser,
    db: AsyncIOMotorDatabase,
) -> List[Dict[str, Any]]:
    cached_session, cached_messages = await _get_cached_session_with_messages(session_id)
    cached_owner = str((cached_session or {}).get("user_id") or "")
    if cached_session and cached_owner:
        _assert_cached_session_owner(cached_session, current_user)
        return cached_messages

    try:
        await _ensure_session_owner(session_id, current_user, db)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
        _assert_cached_session_owner(cached_session, current_user)
        if not cached_session:
            raise
        return cached_messages

    _assert_cached_session_owner(cached_session, current_user)
    if cached_session:
        return cached_messages

    docs = await (
        db["ai_tutor_messages"]
        .find({"session_id": session_id})
        .sort("timestamp", -1)
        .limit(10)
        .to_list(length=10)
    )
    docs.reverse()
    return [
        {
            "id": doc.get("id") or doc.get("message_id") or str(doc.get("_id", "")),
            "role": doc.get("role", "user"),
            "content": doc.get("content", ""),
            "timestamp": to_iso_timestamp(doc.get("timestamp")),
        }
        for doc in docs
    ]


async def _create_ai_tutor_session_for_user(
    session_id: str,
    user_id: str,
    story_context: Optional[str],
    db: AsyncIOMotorDatabase,
) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    await asyncio.gather(
        _store.set_session(session_id, {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": now_iso,
            "updated_at": now_iso,
            "title": "AI Tutor Chat",
            "message_count": 0,
            "persona": "ai_tutor",
            "story_context": story_context,
        }),
        _store.init_messages(session_id),
        db["ai_tutor_sessions"].update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "session_id": session_id,
                    "user_id": user_id,
                    "title": "AI Tutor Chat",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "message_count": 0,
                    "persona": "ai_tutor",
                }
            },
            upsert=True,
        ),
    )


async def _append_ai_tutor_messages(
    session_id: str,
    messages: List[Dict[str, Any]],
) -> None:
    if callable(getattr(type(_store), "append_messages", None)):
        await _store.append_messages(session_id, messages)
        return

    await asyncio.gather(
        *(_store.append_message(session_id, message) for message in messages)
    )


# ─── AI Tutor Persona System Prompt ─────────────────────────────────────────────
LEXI_PERSONA = """You are AI Tutor, a cheerful, witty parrot who is an expert English tutor.
You speak in a warm, encouraging tone — like a fun game character guiding an adventure.

Personality traits:
- Playful and humorous, but always educational
- Uses short, clear sentences appropriate to the learner's level
- Celebrates small victories with enthusiasm ("Squawk! Great job! ")
- Gently corrects mistakes with encouraging context
- Occasionally drops parrot-themed phrases ("Polly wants proper grammar!")
- Adapts difficulty based on learner's CEFR level
- Keeps conversations flowing like a story / adventure

Story context rules:
- Each conversation is an "adventure" with AI Tutor
- Reference previous topics to build continuity
- Use the knowledge graph context to teach related concepts
- When the learner makes errors, weave corrections into the story naturally

Response format:
- Keep responses concise (2-4 sentences for dialogue)
- Use markdown for emphasis when helpful
- Include a gentle correction if errors are found
- Always end with something that invites the learner to continue
"""


# ─── Request / Response Models ───────────────────────────────────────────────
class AiTutorChatRequest(BaseModel):
    """Request to chat with AI Tutor."""
    user_id: str = Field(default="demo_user", description="User identifier")
    session_id: Optional[str] = Field(default=None, description="Existing session ID")
    message: str = Field(..., min_length=1, description="User message text")
    input_type: str = Field(default="text", description="'text' or 'voice'")
    audio_base64: Optional[str] = Field(default=None, description="Base64 audio for STT")
    enable_tts: bool = Field(default=True, description="Generate TTS audio response")
    learner_level: str = Field(default="B1", description="CEFR level: A1-C2")
    story_context: Optional[str] = Field(default=None, description="Story/adventure context")
    subject: Optional[str] = Field(default=None, description="Tutor subject context")
    topic: Optional[str] = Field(default=None, description="Tutor topic context")
    hint_count: int = Field(default=0, ge=0, description="Hints already unlocked")
    student_submitted_step: Optional[bool] = Field(
        default=None,
        description="Whether the learner submitted intermediate work",
    )
    allow_final_answer: bool = Field(default=False, description="Final answer reveal gate")


class AiTutorCorrection(BaseModel):
    """A grammar/vocabulary correction."""
    error_span: str = ""
    correction: str = ""
    error_type: str = ""
    explanation: str = ""


class AiTutorChatResponse(BaseModel):
    """Structured response from AI Tutor."""
    success: bool = True
    session_id: str
    message_id: str
    ai_tutor_response: str
    audio_base64: Optional[str] = None
    corrections: List[AiTutorCorrection] = []
    linked_concepts: List[str] = []
    vietnamese_hint: Optional[str] = None
    scores: Optional[Dict[str, Any]] = None
    story_context: Optional[str] = None
    metadata: Dict[str, Any] = {}


class AiTutorSessionResponse(BaseModel):
    """Response for session creation."""
    success: bool = True
    session_id: str
    created_at: str
    persona: str = "ai_tutor"


class AiTutorSessionRequest(BaseModel):
    """Request to create a AI Tutor session."""
    user_id: str = Field(default="demo_user", description="User identifier")


class AiTutorSessionRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)


class AiTutorSessionSummary(BaseModel):
    session_id: str
    user_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class AiTutorSessionListResponse(BaseModel):
    success: bool = True
    sessions: List[AiTutorSessionSummary] = []


# ─── Pipeline result ─────────────────────────────────────────────────────────

@dataclass
class _PipelineResult:
    ai_tutor_response: str
    user_text: str
    message_id: str
    session_id: str
    corrections: List["AiTutorCorrection"] = field(default_factory=list)
    linked_concepts: List[str] = field(default_factory=list)
    vietnamese_hint: Optional[str] = None
    scores: Optional[Dict[str, Any]] = None
    model_used: str = "trace-cag"
    story_ctx: Optional[str] = None
    audio_b64: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


async def _run_ai_tutor_pipeline(
    request: "AiTutorChatRequest",
    session_id: str,
    history: List[Dict[str, Any]],
    db: AsyncIOMotorDatabase,
    quota: Any,
    start_time: float,
    skip_tts: bool = False,
) -> _PipelineResult:
    """Execute the full AI Tutor pipeline (STT → TraceCAG → TTS → persist) and return results.

    Extracted so both the regular /chat and the streaming /stream endpoints
    can share the same logic without duplication.
    """
    metadata: Dict[str, Any] = {"pipeline_steps": ["session_ready"]}

    # ── STT ──
    user_text = request.message
    if request.input_type == "voice" and request.audio_base64:
        transcript = await _transcribe_audio(request.audio_base64)
        if transcript:
            user_text = transcript
            metadata["pipeline_steps"].append("stt_complete")
            metadata["stt_transcript"] = transcript
        else:
            metadata["pipeline_steps"].append("stt_failed")

    # ── TraceCAG pipeline ──
    ai_tutor_response = ""
    corrections: List[AiTutorCorrection] = []
    linked_concepts: List[str] = []
    vietnamese_hint: Optional[str] = None
    scores: Optional[Dict[str, Any]] = None
    model_used = "trace-cag"
    socratic_context = build_socratic_context(
        user_text,
        subject=request.subject,
        topic=request.topic,
        hint_count=request.hint_count,
        student_submitted_step=request.student_submitted_step,
        allow_final_answer=request.allow_final_answer,
    )
    metadata["socratic"] = {
        "enabled": socratic_context.is_socratic,
        "final_answer_allowed": socratic_context.final_answer_allowed,
        "subject": socratic_context.subject,
        "topic": socratic_context.topic,
        "verified_ground_truth": bool(socratic_context.verified_ground_truth),
    }
    deterministic_response = maybe_build_line_equation_response(user_text)

    try:
        if deterministic_response:
            ai_tutor_response = deterministic_response
            metadata["pipeline_steps"].append("deterministic_line_equation_complete")
            model_used = "deterministic_line_equation_solver"
        else:
            from api.services.orchestrator import get_orchestrator

            orchestrator = await get_orchestrator()
            graph_result = await orchestrator.process(
                user_input=socratic_context.enriched_message,
                session_id=session_id,
                user_id=request.user_id,
                learner_profile={"level": request.learner_level},
                conversation_history=history,
            )
            ai_tutor_response = graph_result.get("tutor_response", "")
            for c in graph_result.get("corrections", []):
                corrections.append(AiTutorCorrection(
                    error_span=c.get("error", ""),
                    correction=c.get("correction", ""),
                    error_type=c.get("type", ""),
                    explanation=c.get("explanation", ""),
                ))
            linked_concepts = graph_result.get("linked_concepts", [])
            vietnamese_hint = graph_result.get("vietnamese_hint")
            scores = graph_result.get("scores")
            metadata["pipeline_steps"].append("trace-cag_complete")
            metadata["trace-cag_metadata"] = graph_result.get("metadata", {})
            model_used = ", ".join(graph_result.get("metadata", {}).get("models_used", ["trace-cag"]))

    except Exception as e:
        logger.error("TraceCAG hard failure in AI Tutor pipeline (primary): %s", e)
        metadata["pipeline_steps"].append("trace-cag_failed_primary")
        try:
            from api.services.orchestrator import get_orchestrator

            orchestrator = await get_orchestrator()
            retry_result = await orchestrator.process(
                user_input=socratic_context.enriched_message,
                session_id=session_id,
                user_id=request.user_id,
                learner_profile={"level": request.learner_level},
                conversation_history=[],
                cache_policy="off",
                retrieval_policy="rapid",
                diagnosis_policy="rules",
                generation_policy="auto",
            )
            ai_tutor_response = str(retry_result.get("tutor_response") or "").strip()
            if not ai_tutor_response:
                raise RuntimeError("TraceCAG degraded retry returned empty tutor_response")
            retry_meta = retry_result.get("metadata", {}) or {}
            metadata["pipeline_steps"].append("trace-cag_retry_complete")
            metadata["trace-cag_metadata"] = {
                **retry_meta,
                "fallback_used": True,
                "retry_mode": "trace-cag_degraded",
                "primary_error": str(e),
            }
            model_used = ", ".join(retry_meta.get("models_used", ["trace-cag_retry"]))
        except Exception as retry_err:
            logger.error("TraceCAG hard failure in AI Tutor pipeline (degraded retry): %s", retry_err)
            metadata["pipeline_steps"].append("trace-cag_failed_hard")
            metadata["trace-cag_metadata"] = {
                "fallback_used": True,
                "primary_error": str(e),
                "retry_error": str(retry_err),
            }
            ai_tutor_response = SAFE_FIXED_RESPONSE
            model_used = "trace-cag_safe_response"

    # ── Guards ──
    story_ctx = request.story_context
    if not story_ctx:
        _pre_sess = await _store.get_session(session_id)
        if _pre_sess:
            story_ctx = _pre_sess.get("story_context")

    if not ai_tutor_response:
        ai_tutor_response = SAFE_FIXED_RESPONSE
        model_used = "trace-cag_safe_response"
        metadata["pipeline_steps"].append("trace-cag_empty_response_guard")

    ai_tutor_response = _sanitize_ai_tutor_response(ai_tutor_response)
    metadata["model_used"] = model_used

    # ── TTS ──
    audio_b64: Optional[str] = None
    if request.enable_tts and not skip_tts:
        tts_timeout_s = _env_float("LEXI_TTS_TIMEOUT_SECONDS", 8.0, minimum=0.5)
        try:
            audio_b64 = await asyncio.wait_for(
                _synthesize_tts(ai_tutor_response),
                timeout=tts_timeout_s,
            )
            metadata["pipeline_steps"].append("tts_complete" if audio_b64 else "tts_skipped")
        except asyncio.TimeoutError:
            logger.warning("AI Tutor TTS timed out after %.1fs", tts_timeout_s)
            metadata["pipeline_steps"].append("tts_timeout")

    # ── Persist messages ──
    message_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    user_message = {
        "id": str(uuid.uuid4()),
        "role": "user",
        "content": user_text,
        "timestamp": timestamp,
    }
    assistant_message = {
        "id": message_id,
        "role": "assistant",
        "content": ai_tutor_response,
        "timestamp": timestamp,
    }

    # Fire all independent writes concurrently: cache append + MongoDB writes.
    await asyncio.gather(
        _append_ai_tutor_messages(session_id, [user_message, assistant_message]),
        db["ai_tutor_messages"].insert_many([
            {
                **user_message,
                "session_id": session_id,
                "user_id": request.user_id,
            },
            {
                **assistant_message,
                "session_id": session_id,
                "user_id": request.user_id,
            },
        ]),
        db["ai_tutor_sessions"].update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "updated_at": timestamp,
                    "user_id": request.user_id,
                },
                "$inc": {"message_count": 2},
                "$setOnInsert": {
                    "created_at": timestamp,
                    "title": "AI Tutor Chat",
                    "persona": "ai_tutor",
                },
            },
            upsert=True,
        ),
    )

    # Read session (needed for message_count), then fire session update + conv cache concurrently
    cached_session = await _store.get_session(session_id) or {}
    if not story_ctx:
        story_ctx = cached_session.get("story_context")
    cached_count = int(cached_session.get("message_count") or 0)

    async def _write_conv_cache():
        try:
            from api.core.redis_client import ConversationCache, RedisClient
            _redis_inst = await RedisClient.get_instance()
            _conv_cache = ConversationCache(_redis_inst)
            await _conv_cache.add_turn(
                session_id=session_id,
                user_message=user_text,
                ai_response=ai_tutor_response,
                metadata={
                    "model": model_used,
                    "scores": scores,
                    "latency_ms": int((time.time() - start_time) * 1000),
                },
            )
        except Exception as _cc_err:
            logger.debug(f"ConversationCache write skipped: {_cc_err}")

    await asyncio.gather(
        _store.set_session(session_id, {
            "session_id": session_id,
            "user_id": request.user_id,
            "created_at": cached_session.get("created_at", timestamp),
            "updated_at": timestamp,
            "title": cached_session.get("title", "AI Tutor Chat"),
            "message_count": cached_count + 2,
            "persona": cached_session.get("persona", "ai_tutor"),
            "story_context": story_ctx,
        }),
        _write_conv_cache(),
    )

    total_ms = int((time.time() - start_time) * 1000)
    metadata["latency_ms"] = total_ms
    metadata["quota"] = {
        "rpm_used": quota.rpm_used,
        "rpm_limit": quota.rpm_limit,
        "rpd_used": quota.rpd_used,
        "rpd_limit": quota.rpd_limit,
        "tpm_used": quota.tpm_used,
        "tpm_limit": quota.tpm_limit,
        "tpd_used": quota.tpd_used,
        "tpd_limit": quota.tpd_limit,
    }
    logger.info(
        f"AI Tutor pipeline complete — {total_ms}ms, model: {model_used}, "
        f"steps: {metadata['pipeline_steps']}"
    )

    return _PipelineResult(
        ai_tutor_response=ai_tutor_response,
        user_text=user_text,
        message_id=message_id,
        session_id=session_id,
        corrections=corrections,
        linked_concepts=linked_concepts,
        vietnamese_hint=vietnamese_hint,
        scores=scores,
        model_used=model_used,
        story_ctx=story_ctx,
        audio_b64=audio_b64,
        metadata=metadata,
    )


# ─── Routes ──────────────────────────────────────────────────────────────────
@router.post("/sessions", response_model=AiTutorSessionResponse)
async def create_ai_tutor_session(
    request: AiTutorSessionRequest = AiTutorSessionRequest(),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AiTutorSessionResponse:
    """Create a new conversation session with AI Tutor."""
    auth_user_id = enforce_user_scope(current_user, request.user_id)
    request = request.model_copy(update={"user_id": auth_user_id})

    session_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    await _store.set_session(session_id, {
        "session_id": session_id,
        "user_id": request.user_id,
        "created_at": now,
        "updated_at": now,
        "title": "AI Tutor Chat",
        "message_count": 0,
        "persona": "ai_tutor",
        "story_context": None,
    })
    await _store.init_messages(session_id)

    await db["ai_tutor_sessions"].update_one(
        {"session_id": session_id},
        {
            "$set": {
                "session_id": session_id,
                "user_id": request.user_id,
                "title": "AI Tutor Chat",
                "created_at": now,
                "updated_at": now,
                "message_count": 0,
                "persona": "ai_tutor",
            }
        },
        upsert=True,
    )
    
    logger.info(f" AI Tutor session created: {session_id[:8]}... for user: {request.user_id}")
    return AiTutorSessionResponse(session_id=session_id, created_at=now)


@router.post("/chat", response_model=AiTutorChatResponse)
async def ai_tutor_chat(
    request_context: Request,
    request: AiTutorChatRequest,
    x_idempotency_key: Optional[str] = Header(
        default=None,
        alias="X-Idempotency-Key",
    ),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AiTutorChatResponse:
    """
    Chat with AI Tutor — the full AI pipeline.

    Pipeline flow:
      1. Session management (create if needed)
      2. STT transcription (if voice input)
      3. TraceCAG pipeline (KG expansion + retrieval)
      4. LLM generation with AI Tutor persona (Groq → Gemini → Ollama)
      5. TTS synthesis (if enabled)
      6. Return structured response
    """
    start_time = time.time()
    request_id = request_context.headers.get("X-Request-Id") or str(uuid.uuid4())
    auth_user_id = enforce_user_scope(current_user, request.user_id)
    request = request.model_copy(update={"user_id": auth_user_id})

    quota = await enforce_user_quota(
        current_user.user_id,
        "ai_tutor.chat",
        token_cost=default_token_cost_for_endpoint("ai_tutor.chat", text=request.message),
        fail_closed=True,
    )

    # ── 1. Session management ──
    if request.session_id:
        session_id = request.session_id
        history = await _prepare_existing_ai_tutor_session(session_id, current_user, db)
    else:
        session_id = str(uuid.uuid4())
        history = []
        await _create_ai_tutor_session_for_user(
            session_id=session_id,
            user_id=request.user_id,
            story_context=request.story_context,
            db=db,
        )

    request_hash = _idempotency_request_hash(request)
    if x_idempotency_key:
        cached_response = await _idempotency_store.get(
            user_id=request.user_id,
            session_id=session_id,
            idempotency_key=x_idempotency_key,
            request_hash=request_hash,
        )
        if cached_response:
            return AiTutorChatResponse(**cached_response)

    # ── 2–6. Execute shared pipeline (STT → TraceCAG → TTS → persist) ──
    result = await _run_ai_tutor_pipeline(
        request=request,
        session_id=session_id,
        history=history,
        db=db,
        quota=quota,
        start_time=start_time,
    )

    # ── 7. Build response ──
    logger.info(
        f" AI Tutor chat complete — {result.metadata['latency_ms']}ms, "
        f"model: {result.model_used}, steps: {result.metadata['pipeline_steps']}"
    )

    await emit_ai_audit_event(
        {
            "request_id": request_id,
            "user_id": current_user.user_id,
            "endpoint": "ai_tutor.chat",
            "status": "success",
            "session_id": result.session_id,
            "model_used": result.model_used,
            "latency_ms": result.metadata["latency_ms"],
            "quota": result.metadata["quota"],
        }
    )

    response = AiTutorChatResponse(
        session_id=result.session_id,
        message_id=result.message_id,
        ai_tutor_response=result.ai_tutor_response,
        audio_base64=result.audio_b64,
        corrections=result.corrections,
        linked_concepts=result.linked_concepts,
        vietnamese_hint=result.vietnamese_hint,
        scores=result.scores,
        story_context=result.story_ctx,
        metadata=result.metadata,
    )

    if x_idempotency_key:
        await _idempotency_store.set(
            user_id=request.user_id,
            session_id=session_id,
            idempotency_key=x_idempotency_key,
            request_hash=request_hash,
            response=response.model_dump(),
        )

    return response


@router.post("/stream")
async def ai_tutor_stream_chat(
    request_context: Request,
    request: AiTutorChatRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> StreamingResponse:
    """
    Chat with AI Tutor — streaming SSE variant.

    Returns a text/event-stream response. Events:
      • ``thinking``  — sent immediately to signal the pipeline has started
      • ``heartbeat`` — SSE data event sent every 2.5 s to keep proxies alive
      • ``chunk``     — one word at a time as the response is "typed out"
      • ``done``      — final event carrying message_id, corrections, audio, etc.
      • ``error``     — sent if the pipeline raises an unrecoverable error

    The TraceCAG pipeline runs first (text only, TTS skipped); text chunks
    begin streaming as soon as the LLM response is ready.  TTS audio is
    synthesised after the last chunk and delivered in the ``done`` event.
    """
    start_time = time.time()
    request_id = request_context.headers.get("X-Request-Id") or str(uuid.uuid4())
    auth_user_id = enforce_user_scope(current_user, request.user_id)
    request = request.model_copy(update={"user_id": auth_user_id})

    quota_timeout_s = _env_float("LEXI_STREAM_QUOTA_TIMEOUT_SECONDS", 5.0, minimum=0.5)
    try:
        quota = await asyncio.wait_for(
            enforce_user_quota(
                current_user.user_id,
                "ai_tutor.chat",
                token_cost=default_token_cost_for_endpoint(
                    "ai_tutor.chat",
                    text=request.message,
                ),
                fail_closed=True,
            ),
            timeout=quota_timeout_s,
        )
    except asyncio.TimeoutError as exc:
        logger.error(
            "AI Tutor /stream quota check timed out after %.1fs",
            quota_timeout_s,
        )
        raise HTTPException(
            status_code=503,
            detail="AI quota service is temporarily unavailable",
        ) from exc

    session_id = request.session_id or str(uuid.uuid4())
    prechecked_history: Optional[List[Dict[str, Any]]] = None
    if request.session_id:
        session_timeout_s = _env_float(
            "LEXI_STREAM_SESSION_TIMEOUT_SECONDS",
            15.0,
            minimum=_HEARTBEAT_INTERVAL_S,
        )
        try:
            prechecked_history = await asyncio.wait_for(
                _prepare_existing_ai_tutor_session(session_id, current_user, db),
                timeout=session_timeout_s,
            )
        except asyncio.TimeoutError as exc:
            logger.error(
                "AI Tutor /stream session ownership check timed out after %.1fs",
                session_timeout_s,
            )
            raise HTTPException(
                status_code=503,
                detail="Chat session service is temporarily unavailable",
            ) from exc

    async def _sse_generator() -> AsyncGenerator[str, None]:
        from api.services.orchestrator import get_orchestrator
        from api.services.trace_cag.nodes_v2 import build_generation_prompt, stream_llm_tokens
        from api.services.trace_cag.evaluation_agent import EvaluationAgent

        user_text = request.message

        # 1. Open the SSE response before touching Redis/Mongo. This prevents a
        # degraded session store from holding the HTTP response until the edge
        # proxy returns a 504.
        yield "event: thinking\ndata: {}\n\n"

        # 2. Session management. Keep sending data events while Redis/Mongo is
        # slow so Cloudflare and nginx do not treat the stream as idle.
        if prechecked_history is not None:
            history = prechecked_history
        else:
            async def _prepare_session() -> List[Dict[str, Any]]:
                await _create_ai_tutor_session_for_user(
                    session_id=session_id,
                    user_id=request.user_id,
                    story_context=request.story_context,
                    db=db,
                )
                return []

            session_task = asyncio.create_task(_prepare_session())
            loop = asyncio.get_running_loop()
            session_timeout_s = _env_float(
                "LEXI_STREAM_SESSION_TIMEOUT_SECONDS",
                15.0,
                minimum=_HEARTBEAT_INTERVAL_S,
            )
            session_deadline = loop.time() + session_timeout_s
            while not session_task.done():
                if loop.time() >= session_deadline:
                    session_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await session_task
                    logger.error(
                        "AI Tutor /stream session preparation timed out after %.1fs",
                        session_timeout_s,
                    )
                    yield (
                        f"event: error\ndata: "
                        f"{json.dumps({'error': 'Chat session service is temporarily unavailable.'})}\n\n"
                    )
                    return
                try:
                    await asyncio.wait_for(
                        asyncio.shield(session_task),
                        timeout=_HEARTBEAT_INTERVAL_S,
                    )
                except asyncio.TimeoutError:
                    yield "event: heartbeat\ndata: {}\n\n"
                except Exception:
                    break

            try:
                history = await session_task
            except Exception as exc:
                logger.error("AI Tutor /stream session preparation error: %s", exc)
                yield (
                    f"event: error\ndata: "
                    f"{json.dumps({'error': 'Chat session service is temporarily unavailable.'})}\n\n"
                )
                return

        import httpx

        # 3. Direct response path. Use deterministic math formatters for common
        # high-risk problems before falling back to model generation.
        socratic_context = build_socratic_context(
            user_text,
            subject=request.subject,
            topic=request.topic,
            hint_count=request.hint_count,
            student_submitted_step=request.student_submitted_step,
            allow_final_answer=request.allow_final_answer,
        )
        deterministic_response = maybe_build_line_equation_response(user_text)
        if deterministic_response:
            ai_tutor_response = _sanitize_ai_tutor_response(deterministic_response)
            model_used = "deterministic_line_equation_solver"
            cache_hit = False
            yield f"event: chunk\ndata: {json.dumps({'text': ai_tutor_response})}\n\n"
        else:
            ai_tutor_response = ""
            model_used = "openrouter/free"
            cache_hit = False

        system_prompt = (
            "You are AI Tutor, an AI Tutor for Mathematics, Physics, and English. "
            "Use clear, direct, structured, student-friendly explanations. "
            "When the student asks in Khmer, answer in natural Khmer. "
            "When the student asks in English but requests Khmer, answer in natural Khmer. "
            "Do not sound like Google Translate; use simple student-friendly Khmer. "
            "Keep math formulas in standard symbols such as x, y, +, -, =. "
            "For normal math and physics explanation requests, give the worked solution: "
            "formula first, symbol definitions, given values, step-by-step calculation, and final answer. "
            "For those worked solutions, use exact labels FORMULA:, SYMBOLS:, GIVEN:, STEPS:, and FINAL: "
            "so the mobile app can render a lesson card. If answering in Khmer, use exact labels "
            "រូបមន្ត:, អត្ថន័យនៃនិមិត្តសញ្ញា:, តម្លៃដែលបានផ្តល់:, "
            "ដំណោះស្រាយជាជំហានៗ:, and ចម្លើយចុងក្រោយ:. "
            "Do not write long Socratic discovery paragraphs unless the user asks for hints or is in Guided Practice mode. "
            "If the user asks for hint only, give one hint only. "
            "If the user asks to check a step, check only that step. "
            "Keep lines short and readable on mobile."
        )
        llm_messages = [{"role": "system", "content": system_prompt}]
        for msg in history[-10:]:
            llm_messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        llm_messages.append({"role": "user", "content": socratic_context.enriched_message})

        try:
            tokens: list[str] = []
            api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
            if not api_key:
                raise RuntimeError("OPENROUTER_API_KEY is not configured")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": "https://ai_tutor.app",
                "X-Title": "AI Tutor AI Tutor",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "openrouter/free",
                "messages": llm_messages,
                "stream": True,
                "temperature": 0.7,
            }
            
            if not ai_tutor_response:
                async with httpx.AsyncClient() as client:
                    async with client.stream("POST", "https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=60.0) as response:
                        if response.status_code != 200:
                            logger.error(f"OpenRouter stream error: {response.status_code}")
                        else:
                            async for line in response.aiter_lines():
                                if line.startswith("data: ") and line != "data: [DONE]":
                                    try:
                                        data = json.loads(line[6:])
                                        chunk = data["choices"][0]["delta"].get("content", "")
                                        if chunk:
                                            tokens.append(chunk)
                                            yield f"event: chunk\ndata: {json.dumps({'text': chunk})}\n\n"
                                    except Exception:
                                        pass

                    ai_tutor_response = _sanitize_ai_tutor_response("".join(tokens))
        except Exception as gen_err:
            logger.error("AI Tutor /stream LLM generation error: %s", gen_err)
                
        diag_errors = []
        corrections = []
        linked_concepts = []
        vietnamese_hint = ""
        grammar_score = 1.0
        fluency_score = 1.0
        vocab_level = "B1"


        if not ai_tutor_response:
            ai_tutor_response = SAFE_FIXED_RESPONSE

        # 4. TTS synthesis — after all chunks so TTFB is unaffected
        audio_b64: Optional[str] = None
        if request.enable_tts:
            try:
                audio_b64 = await asyncio.wait_for(
                    _synthesize_tts(ai_tutor_response), timeout=8.0
                )
            except Exception as tts_err:
                logger.warning("AI Tutor stream TTS failed: %s", tts_err)

        # 5. Persist messages (parallelised)
        message_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        user_message = {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": user_text,
            "timestamp": timestamp,
        }
        assistant_message = {
            "id": message_id,
            "role": "assistant",
            "content": ai_tutor_response,
            "timestamp": timestamp,
        }

        async def _stream_persist():
            await asyncio.gather(
                _append_ai_tutor_messages(session_id, [user_message, assistant_message]),
                db["ai_tutor_messages"].insert_many([
                    {**user_message, "session_id": session_id, "user_id": request.user_id},
                    {**assistant_message, "session_id": session_id, "user_id": request.user_id},
                ]),
                db["ai_tutor_sessions"].update_one(
                    {"session_id": session_id},
                    {
                        "$set": {"updated_at": timestamp, "user_id": request.user_id},
                        "$inc": {"message_count": 2},
                        "$setOnInsert": {
                            "created_at": timestamp,
                            "title": "AI Tutor Chat",
                            "persona": "ai_tutor",
                        },
                    },
                    upsert=True,
                ),
            )
            cached_sess = await _store.get_session(session_id) or {}
            cached_count = int(cached_sess.get("message_count") or 0)
            await _store.set_session(session_id, {
                "session_id": session_id,
                "user_id": request.user_id,
                "created_at": cached_sess.get("created_at", timestamp),
                "updated_at": timestamp,
                "title": cached_sess.get("title", "AI Tutor Chat"),
                "message_count": cached_count + 2,
                "persona": cached_sess.get("persona", "ai_tutor"),
                "story_context": request.story_context,
            })

        try:
            await asyncio.wait_for(_stream_persist(), timeout=5.0)
        except Exception as persist_err:
            logger.warning("AI Tutor stream persist error: %s", persist_err)

        # 6. Done event
        overall_score = EvaluationAgent.compute_overall_score(
            grammar_score, fluency_score, vocab_level
        )
        scores = {
            "fluency": fluency_score,
            "grammar": grammar_score,
            "overall": overall_score,
            "vocabulary_level": vocab_level,
        }
        total_ms = int((time.time() - start_time) * 1000)
        done_payload = json.dumps({
            "message_id": message_id,
            "session_id": session_id,
            "ai_tutor_response": ai_tutor_response,
            "corrections": [
                {
                    "error_span": c.error_span,
                    "correction": c.correction,
                    "error_type": c.error_type,
                    "explanation": c.explanation,
                }
                for c in corrections
            ],
            "linked_concepts": linked_concepts,
            "vietnamese_hint": vietnamese_hint,
            "scores": scores,
            "story_context": request.story_context,
            "audio_base64": audio_b64,
            "metadata": {
                "latency_ms": total_ms,
                "model_used": model_used,
                "cache_hit": cache_hit,
                "quota": {
                    "rpm_used": quota.rpm_used,
                    "rpm_limit": quota.rpm_limit,
                    "rpd_used": quota.rpd_used,
                    "rpd_limit": quota.rpd_limit,
                },
            },
        })
        yield f"event: done\ndata: {done_payload}\n\n"

        logger.info(
            "AI Tutor /stream complete — %dms, model: %s, cache_hit: %s",
            total_ms, model_used, cache_hit,
        )
        await emit_ai_audit_event({
            "request_id": request_id,
            "user_id": current_user.user_id,
            "endpoint": "ai_tutor.stream",
            "status": "success",
            "session_id": session_id,
            "model_used": model_used,
            "latency_ms": total_ms,
            "quota": {"rpm_used": quota.rpm_used, "rpm_limit": quota.rpm_limit},
        })

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/sessions/{session_id}/messages")
async def get_ai_tutor_messages(
    session_id: str,
    limit: int = Query(100, ge=1, le=200),
    cursor: str | None = None,
    full: bool = Query(False, description="Set true to force full session history load"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Get messages in a AI Tutor session.

    By default this endpoint returns a bounded page to avoid heavy full-session scans.
    Set `full=true` only for maintenance/legacy flows that require the entire history.
    """
    is_full = full if isinstance(full, bool) else False
    if not is_full:
        return await get_ai_tutor_messages_paged(
            session_id=session_id,
            limit=limit,
            cursor=cursor,
            db=db,
            current_user=current_user,
        )

    session_doc = None
    try:
        session_doc = await _ensure_session_owner(session_id, current_user, db)
        cached_session = await _store.get_session(session_id)
    except HTTPException as e:
        cached_session = await _store.get_session(session_id)
        if e.status_code == 404 and cached_session:
            owner_user_id = str(cached_session.get("user_id") or "")
            if owner_user_id and hasattr(current_user, "user_id") and owner_user_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="Forbidden: session ownership mismatch")
        else:
            raise
    cached_messages = await _store.get_messages(session_id) if cached_session else []

    expected_count = int((session_doc or {}).get("message_count") or 0)
    cache_is_complete = cached_session is not None and (
        expected_count == 0 or len(cached_messages) >= expected_count
    )

    if cache_is_complete:
        return {
            "success": True,
            "session_id": session_id,
            "messages": cached_messages,
        }

    if not session_doc:
        if cached_session is not None:
            return {
                "success": True,
                "session_id": session_id,
                "messages": cached_messages,
            }
        raise HTTPException(status_code=404, detail="Session not found")

    cursor = db["ai_tutor_messages"].find({"session_id": session_id}).sort("timestamp", 1)
    messages = await load_full_cursor(cursor)
    payload = [
        {
            "id": m.get("id", str(uuid.uuid4())),
            "role": m.get("role", "user"),
            "content": m.get("content", ""),
            "timestamp": m.get("timestamp", datetime.now(timezone.utc).isoformat()),
        }
        for m in messages
    ]

    # Rehydrate cache for faster next reads.
    await _store.set_session(session_id, {
        "session_id": session_doc.get("session_id"),
        "user_id": session_doc.get("user_id", "demo_user"),
        "created_at": session_doc.get("created_at", datetime.now(timezone.utc).isoformat()),
        "updated_at": session_doc.get("updated_at", datetime.now(timezone.utc).isoformat()),
        "title": session_doc.get("title", "AI Tutor Chat"),
        "message_count": session_doc.get("message_count", len(payload)),
        "persona": session_doc.get("persona", "ai_tutor"),
        "story_context": session_doc.get("story_context"),
    })
    await _store.delete_messages(session_id)
    for item in payload:
        await _store.append_message(session_id, item)

    return {
        "success": True,
        "session_id": session_id,
        "messages": payload,
    }


@router.get("/sessions/{session_id}/messages/paged")
async def get_ai_tutor_messages_paged(
    session_id: str,
    limit: int = 50,
    cursor: str | None = None,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    await _ensure_session_owner(session_id, current_user, db)

    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be >= 1")

    safe_limit = min(limit, 200)
    base_query: Dict[str, Any] = {"session_id": session_id}
    query: Dict[str, Any] = dict(base_query)

    if cursor:
        cursor_ts, cursor_oid = decode_cursor_str(cursor)
        query = {
            "session_id": session_id,
            "$or": [
                {"timestamp": {"$lt": cursor_ts}},
                {"timestamp": cursor_ts, "_id": {"$lt": cursor_oid}},
            ],
        }

    docs_desc = await (
        db["ai_tutor_messages"]
        .find(query)
        .sort([("timestamp", -1), ("_id", -1)])
        .limit(safe_limit + 1)
        .to_list(length=safe_limit + 1)
    )

    has_more = len(docs_desc) > safe_limit
    docs_desc = docs_desc[:safe_limit]
    docs = list(reversed(docs_desc))
    messages = [_serialize_ai_tutor_message(doc) for doc in docs]

    total_count = await db["ai_tutor_messages"].count_documents(base_query)
    next_cursor = encode_cursor(docs[0]) if has_more and docs else None
    prev_cursor = encode_cursor(docs[-1]) if docs else None
    window_start_ts = to_iso_timestamp(docs[0].get("timestamp")) if docs else None
    window_end_ts = to_iso_timestamp(docs[-1].get("timestamp")) if docs else None

    return {
        "success": True,
        "session_id": session_id,
        "messages": messages,
        "pagination": build_pagination(
            total_count=total_count,
            returned=len(messages),
            has_more=has_more,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            window_start_ts=window_start_ts,
            window_end_ts=window_end_ts,
        ),
    }


@router.get("/sessions/{session_id}/messages/metadata")
async def get_ai_tutor_messages_metadata(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    await _ensure_session_owner(session_id, current_user, db)

    base_query: Dict[str, Any] = {"session_id": session_id}
    total_count = await db["ai_tutor_messages"].count_documents(base_query)

    if total_count == 0:
        return {
            "success": True,
            "session_id": session_id,
            "metadata": {
                "total_count": 0,
                "has_messages": False,
                "latest_cursor": None,
                "oldest_cursor": None,
                "latest_ts": None,
                "oldest_ts": None,
                "has_more": False,
                "next_cursor": None,
                "prev_cursor": None,
                "window_start_ts": None,
                "window_end_ts": None,
            },
        }

    latest_docs = await (
        db["ai_tutor_messages"]
        .find(base_query)
        .sort([("timestamp", -1), ("_id", -1)])
        .limit(1)
        .to_list(length=1)
    )
    oldest_docs = await (
        db["ai_tutor_messages"]
        .find(base_query)
        .sort([("timestamp", 1), ("_id", 1)])
        .limit(1)
        .to_list(length=1)
    )

    latest = latest_docs[0]
    oldest = oldest_docs[0]
    latest_cursor = encode_cursor(latest)
    oldest_cursor = encode_cursor(oldest)
    latest_ts = to_iso_timestamp(latest.get("timestamp"))
    oldest_ts = to_iso_timestamp(oldest.get("timestamp"))

    return {
        "success": True,
        "session_id": session_id,
        "metadata": {
            "total_count": total_count,
            "has_messages": True,
            "latest_cursor": latest_cursor,
            "oldest_cursor": oldest_cursor,
            "latest_ts": latest_ts,
            "oldest_ts": oldest_ts,
            "has_more": total_count > 0,
            "next_cursor": oldest_cursor,
            "prev_cursor": latest_cursor,
            "window_start_ts": oldest_ts,
            "window_end_ts": latest_ts,
        },
    }


@router.get("/sessions/user/{user_id}", response_model=AiTutorSessionListResponse)
async def list_ai_tutor_sessions(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AiTutorSessionListResponse:
    enforce_user_scope(current_user, user_id)
    try:
        cursor = db["ai_tutor_sessions"].find({"user_id": user_id}).sort("updated_at", -1)
        rows = await cursor.to_list(length=100)
    except Exception as exc:
        msg = str(exc).lower()
        if not (isinstance(exc, OperationFailure) and ("order-by item is excluded" in msg or "index path corresponding" in msg)):
            raise
        rows = await db["ai_tutor_sessions"].find({"user_id": user_id}).limit(100).to_list(length=100)
        rows.sort(key=lambda row: row.get("updated_at") or row.get("created_at") or "", reverse=True)
    sessions = [
        AiTutorSessionSummary(
            session_id=row.get("session_id", ""),
            user_id=row.get("user_id", user_id),
            title=row.get("title", "AI Tutor Chat"),
            created_at=row.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=row.get("updated_at", row.get("created_at", datetime.now(timezone.utc).isoformat())),
            message_count=int(row.get("message_count", 0)),
        )
        for row in rows
        if row.get("session_id")
    ]
    return AiTutorSessionListResponse(sessions=sessions)


@router.post("/sessions/{session_id}/rename")
async def rename_ai_tutor_session(
    session_id: str,
    request: AiTutorSessionRenameRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    await _ensure_session_owner(session_id, current_user, db)

    title = request.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")

    now = datetime.now(timezone.utc).isoformat()
    result = await db["ai_tutor_sessions"].update_one(
        {"session_id": session_id},
        {"$set": {"title": title, "updated_at": now}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")

    sess = await _store.get_session(session_id)
    if sess:
        sess["title"] = title
        sess["updated_at"] = now
        await _store.set_session(session_id, sess)

    return {"success": True, "session_id": session_id, "title": title}


@router.post("/sessions/{session_id}/delete")
async def delete_ai_tutor_session(
    session_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    await _ensure_session_owner(session_id, current_user, db)

    await db["ai_tutor_sessions"].delete_one({"session_id": session_id})
    await db["ai_tutor_messages"].delete_many({"session_id": session_id})
    await _store.delete_session(session_id)
    await _store.delete_messages(session_id)
    return {"success": True, "session_id": session_id}


@router.get("/health")
async def ai_tutor_health() -> Dict[str, Any]:
    """Health check for AI Tutor chat service."""
    return {
        "status": "ok",
        "service": "ai-tutor-chat",
        "persona": "ai_tutor-the-parrot",
        "capabilities": ["text-chat", "voice-input", "tts-output", "trace-cag-retrieval"],
    }
