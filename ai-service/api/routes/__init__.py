"""Routes module initialization — export all active routers."""

from api.routes.health import router as health_router
from api.routes.ai import router as ai_router
from api.routes.chat import router as chat_router
from api.routes.stt import router as stt_router
from api.routes.tts import router as tts_router
from api.routes import curriculum
from api.routes import ai_tutor_chat
from api.routes import visual_tutor
from api.routes import quiz

# Backward-compatible module alias for tests and older internal imports.
lexi_chat = ai_tutor_chat

__all__ = [
    "health_router",
    "ai_router",
    "chat_router",
    "stt_router",
    "tts_router",
    "curriculum",
    "ai_tutor_chat",
    "visual_tutor",
    "quiz",
    "lexi_chat",
]
