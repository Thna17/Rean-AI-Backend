"""
AI Tutor AI Service

Main entry point for the AI Service. 
Initializes resources and includes modular routers.
"""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from contextlib import asynccontextmanager
import logging
import os
import sys
import httpx
import time
import uuid
from datetime import datetime, timezone
from typing import Optional
from pymongo import ASCENDING, DESCENDING
from pymongo.errors import OperationFailure

# Core imports
from api.core.database import mongodb_manager
from api.core.redis_client import RedisClient, get_redis
from api.core.groq_key_pool import build_groq_key_pool, GroqKeyPool
from api.core.config import get_settings
from api.routes import internal_curriculum

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv

# Importing api.main (directly or transitively, e.g. via a FastAPI test
# client fixture) must never leak real .env secrets -- API keys included --
# into a pytest process. Tests that need a specific value set it explicitly
# (monkeypatch.setenv / monkeypatch.setattr(settings, ...)); anything else
# should see only the real shell environment, not the developer's .env file.
if "pytest" not in sys.modules:
    load_dotenv()

# Settings (loaded after dotenv so env vars are available)
settings = get_settings()

# Sentry — only active when DSN is configured
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=settings.ENVIRONMENT,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.2,
        send_default_pii=False,
    )
    logger.info("Sentry error tracking enabled")

# Environment Configuration
GEMINI_API_KEY = settings.GEMINI_API_KEY
USE_GATEWAY = os.getenv("USE_GATEWAY", "true").lower() == "true"
MONGODB_URI = settings.MONGODB_URI
MONGODB_DATABASE = settings.MONGODB_DATABASE

# Global clients
_gateway_initialized = False
_http_client: Optional[httpx.AsyncClient] = None
_groq_pool: Optional[GroqKeyPool] = None


async def _ensure_mongo_indexes() -> None:
    """Create indexes for fast session/message lookup without risking migrated data loss."""
    db = mongodb_manager.db

    async def _create_index_safe(collection: str, keys, **kwargs) -> None:
        try:
            await db[collection].create_index(keys, **kwargs)
        except Exception as exc:
            logger.warning(
                "Skip index %s on %s due to error: %s",
                kwargs.get("name", "<unnamed>"),
                collection,
                exc,
            )

    async def _has_duplicate_string_values(collection: str, field: str, include_empty: bool = True) -> bool:
        match_filter = {field: {"$exists": True, "$type": "string"}}
        if not include_empty:
            match_filter = {field: {"$exists": True, "$type": "string", "$ne": ""}}

        pipeline = [
            {"$match": match_filter},
            {"$group": {"_id": f"${field}", "count": {"$sum": 1}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$limit": 1},
        ]
        docs = await db[collection].aggregate(pipeline).to_list(length=1)
        return bool(docs)

    async def _ensure_session_unique_index(collection: str, field: str, name: str) -> None:
        # Keep query performance regardless of uniqueness enforceability.
        await _create_index_safe(
            collection,
            [(field, ASCENDING)],
            name=f"{collection}_{field}_idx",
        )

        # We keep the unique index scoped to string values. Since some Mongo-compatible
        # providers reject $ne inside partialFilterExpression, include empty strings in
        # duplicate checks and avoid using $ne in the index expression itself.
        if await _has_duplicate_string_values(collection, field, include_empty=True):
            logger.info(
                "Skip unique index %s on %s: duplicate string %s values detected in migrated data",
                name,
                collection,
                field,
            )
            return

        try:
            await db[collection].create_index(
                [(field, ASCENDING)],
                unique=True,
                name=name,
                partialFilterExpression={
                    field: {"$exists": True, "$type": "string"}
                },
            )
        except OperationFailure as exc:
            # Do not block startup when existing migrated data/index options conflict.
            logger.info("Skip unique index %s on %s: %s", name, collection, exc)

    await _ensure_session_unique_index(
        collection="chat_sessions",
        field="session_id",
        name="chat_sessions_session_id_uq",
    )
    await _create_index_safe(
        "chat_sessions",
        [("user_id", ASCENDING), ("last_activity", DESCENDING)],
        name="chat_sessions_user_last_activity_idx",
    )
    await _create_index_safe(
        "chat_messages",
        [("session_id", ASCENDING), ("timestamp", ASCENDING)],
        name="chat_messages_session_timestamp_idx",
    )

    await _ensure_session_unique_index(
        collection="ai_tutor_sessions",
        field="session_id",
        name="ai_tutor_sessions_session_id_uq",
    )
    await _create_index_safe(
        "ai_tutor_sessions",
        [("user_id", ASCENDING), ("updated_at", DESCENDING)],
        name="ai_tutor_sessions_user_updated_at_idx",
    )
    await _create_index_safe(
        "ai_tutor_messages",
        [("session_id", ASCENDING), ("timestamp", ASCENDING)],
        name="ai_tutor_messages_session_timestamp_idx",
    )

    await _ensure_session_unique_index(
        collection="visual_tutor_sessions",
        field="session_id",
        name="visual_tutor_sessions_session_id_uq",
    )
    await _create_index_safe(
        "visual_tutor_sessions",
        [("user_id", ASCENDING), ("updated_at", DESCENDING)],
        name="visual_tutor_sessions_user_updated_at_idx",
    )
    await _create_index_safe(
        "visual_tutor_sessions",
        [("user_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
        name="visual_tutor_sessions_user_status_updated_at_idx",
    )
    await _create_index_safe(
        "visual_tutor_learner_memory",
        [("user_id", ASCENDING), ("subject_key", ASCENDING), ("topic_key", ASCENDING)],
        name="visual_tutor_learner_memory_owner_topic_uq",
        unique=True,
    )
    await _create_index_safe(
        "visual_tutor_learner_memory",
        [("user_id", ASCENDING), ("updated_at", DESCENDING)],
        name="visual_tutor_learner_memory_owner_updated_at_idx",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    global _gateway_initialized, _http_client, _groq_pool

    # Startup
    try:
        await mongodb_manager.connect()
        await _ensure_mongo_indexes()
        logger.info(" MongoDB connected")
    except Exception as e:
        logger.error(f"MongoDB connection failed (critical): {e}")
        raise

    try:
        redis_conn = await get_redis()
        _groq_pool = build_groq_key_pool(redis_conn)
        if _groq_pool:
            logger.info(" Groq key pool initialized with %d key(s)", _groq_pool.count)
        else:
            logger.warning("No Groq API keys configured")
        logger.info(" Redis & Rate Limiter initialized")
    except Exception as e:
        _groq_pool = None
        logger.warning(f"Redis initialization failed; continuing without cache/rate pool: {e}")

    _http_client = httpx.AsyncClient(timeout=30.0)
    
    if USE_GATEWAY:
        try:
            from api.services.gateway_setup import setup_gateway
            await setup_gateway(
                max_memory_mb=int(os.getenv("MAX_MEMORY_MB", "8000")),
                enable_auto_unload=True,
                use_gemini_fallback=bool(GEMINI_API_KEY),
            )
            _gateway_initialized = True
            logger.info(" ModelGateway initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize gateway: {e}")

    try:
        from api.services.stt.runtime import start_stt_runtime

        await start_stt_runtime()
        logger.info(" Streaming STT runtime initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize streaming STT runtime: {e}")
    
    yield
    
    # Shutdown
    if _http_client:
        await _http_client.aclose()
    await mongodb_manager.disconnect()
    await RedisClient.close()
    if _gateway_initialized:
        from api.services.gateway_setup import shutdown_gateway
        await shutdown_gateway()
    try:
        from api.services.stt.runtime import stop_stt_runtime

        await stop_stt_runtime()
    except Exception as e:
        logger.warning(f"Failed to stop streaming STT runtime cleanly: {e}")


# FastAPI App
app = FastAPI(
    title="AI Tutor AI Service",
    description="AI Service for Chat, STT, TTS with ModelGateway",
    version="2.1.0",
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
    openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
    lifespan=lifespan,
)


@app.middleware("http")
async def correlation_logging(request, call_next):
    """Echo a bounded correlation ID without logging bodies or credentials."""
    supplied = request.headers.get("x-request-id", "").strip()
    request_id = supplied if supplied and len(supplied) <= 128 and all(ch.isalnum() or ch in "._:-" for ch in supplied) else str(uuid.uuid4())
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("http_request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        raise
    response.headers["X-Request-Id"] = request_id
    logger.info("http_request_completed request_id=%s method=%s path=%s status=%s duration_ms=%d", request_id, request.method, request.url.path, response.status_code, int((time.perf_counter() - started) * 1000))
    return response

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Admin-Key",
        "X-Request-Id",
        "X-Api-Key",
        "X-Idempotency-Key",
    ],
    allow_private_network=True,
)


# Include Routers
from api.routes import (
    admin,
    ai,
    chat,
    curriculum,
    ai_tutor_chat,
    math_verifier,
    notification_agent as notification_agent_router,
    ollama_router,
    pronunciation,
    problems,
    quiz,
    stt,
    step_sequencing,
    translate,
    tts,
    visual_tutor,
    visual_tutor_voice,
)

app.include_router(chat.router, prefix="/api/v1/chat", tags=["Chat"])
app.include_router(math_verifier.router, prefix="/api/v1/math", tags=["Math Verifier"])
app.include_router(stt.router, prefix="/api/v1/stt", tags=["STT"])
app.include_router(pronunciation.router, prefix="/api/v1/stt", tags=["STT"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["TTS"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["Admin"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI Analytics"])
app.include_router(translate.router, prefix="/api/v1/ai", tags=["Translate"])
app.include_router(ai_tutor_chat.router, tags=["AI Tutor Chat"])
app.include_router(visual_tutor.router)
app.include_router(visual_tutor_voice.router)
app.include_router(curriculum.router)
app.include_router(internal_curriculum.router)
app.include_router(problems.router)
app.include_router(step_sequencing.router)  # Phase 2: Step Sequencing Routes
app.include_router(quiz.router)
app.include_router(ollama_router.router, prefix="/api/v1", tags=["Ollama"])
app.include_router(notification_agent_router.router, tags=["Notification Agent"])

# Initialize Step Sequencing Services (Phase 2)
try:
    from api.services.step_sequencing_service import StepSequencingService
    _step_seq_service = StepSequencingService()
    _problem_repo = problems.problem_repo  # Reuse from problems router
    _spaced_rep_service = problems.spaced_rep_service  # Reuse from problems router
    step_sequencing.initialize_services(_step_seq_service, _problem_repo, _spaced_rep_service)
    logger.info("Step Sequencing services initialized")
except Exception as e:
    logger.warning(f"Failed to initialize Step Sequencing services: {e}")

# Static files (dev tools / visualizers)
_static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(_static_dir):
    app.mount("/static", StaticFiles(directory=_static_dir), name="static")


@app.get("/visualizer", include_in_schema=False)
async def visualizer_redirect():
    """Redirect to the TraceCAG Node Visualizer HTML tool."""
    return RedirectResponse(url="/static/trace-cag-node-viz.html")


@app.get("/health")
async def health_check():
    # Process liveness is not enough for a Visual Tutor deployment. This public
    # response intentionally reports dependency states but never configuration
    # values, credentials, prompts, or student data.
    mongo_ok = False
    try:
        if mongodb_manager._client is not None:
            await mongodb_manager._client.admin.command("ping")
            mongo_ok = True
    except Exception:
        mongo_ok = False
    ai_ok = await visual_tutor._llm_provider_ready()
    optional = {
        "ocr": "healthy" if settings.VISUAL_TUTOR_OCR_ENABLED and bool(settings.GEMINI_API_KEY) else "degraded",
        "stt": "healthy" if settings.VISUAL_TUTOR_STT_ENABLED and bool(settings.STT_MODEL_NAME) else "degraded",
        "tts": "healthy" if settings.VISUAL_TUTOR_TTS_ENABLED and bool(settings.TTS_MODEL_PATH) else "degraded",
    }
    status_value = "unavailable" if not mongo_ok or not ai_ok else (
        "degraded" if "degraded" in optional.values() else "healthy"
    )
    return {
        "status": status_value,
        "dependencies": {
            "durable_session_store": "healthy" if mongo_ok else "unavailable",
            "visual_tutor_ai": "healthy" if ai_ok else "unavailable",
            **optional,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _run_model_warmup() -> None:
    """Best-effort warmup for AI models; errors are non-fatal."""
    try:
        from api.services.model_gateway import get_model_gateway
        gateway = get_model_gateway()
        await gateway.preload_models()
        logger.info("Warmup: model preload complete")
    except Exception as exc:
        logger.warning(f"Warmup: preload error (non-fatal): {exc}")


@app.post("/warmup")
@app.get("/warmup")
@app.post("/api/v1/warmup")
@app.get("/api/v1/warmup")
async def warmup(background_tasks: BackgroundTasks):
    """
    Trigger background model warmup.

    Supports legacy and versioned paths/methods for compatibility.
    """
    background_tasks.add_task(_run_model_warmup)
    return {"status": "warming_up", "message": "Model preload started in background"}

@app.get("/")
async def root():
    return {"message": "AI Tutor AI Service API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
