from __future__ import annotations

from fastapi import APIRouter, Header

from api.models.quiz import QuizGenerationRequest
from api.services.quiz_generator import generate_topic_quiz
from api.core.visual_tutor_gateway_auth import (
    emit_visual_tutor_audit_event,
    require_visual_tutor_gateway,
)


router = APIRouter(prefix="/api/v1/quiz", tags=["Quiz"])


@router.post("/generate")
async def generate_quiz(
    request: QuizGenerationRequest,
    x_visual_tutor_user_id: str | None = Header(default=None),
    x_visual_tutor_internal_token: str | None = Header(default=None),
) -> dict:
    """Return validated private quiz data to the authenticated application backend only."""
    user_id = require_visual_tutor_gateway(x_visual_tutor_internal_token, x_visual_tutor_user_id)
    quiz = generate_topic_quiz(request)
    emit_visual_tutor_audit_event(
        "visual_tutor_quiz_generated",
        user_id=user_id,
        quiz_id=quiz.quiz_id,
        verified=quiz.verified,
        question_count=len(quiz.questions),
    )
    # This endpoint is internal-token protected.  The TypeScript backend persists
    # this private representation and removes keys before responding to Flutter.
    return quiz.model_dump(mode="json")
