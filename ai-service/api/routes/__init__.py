"""Routes module initialization — export all active routers."""

from api.routes.health import router as health_router
from api.routes.ai import router as ai_router
from api.routes.chat import router as chat_router
from api.routes.stt import router as stt_router
from api.routes.tts import router as tts_router
from api.routes.topic_chat import router as topic_chat_router
from api.routes import ai_tutor_chat

# Backward-compatible module alias for tests and older internal imports.
lexi_chat = ai_tutor_chat

__all__ = [
    "health_router",
    "ai_router",
    "chat_router",
    "stt_router",
    "tts_router",
    "topic_chat_router",
    "ai_tutor_chat",
    "lexi_chat",
]
