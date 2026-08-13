from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.core.config import settings
from api.models.curriculum import CurriculumRetrievalRequest, CurriculumRetrievalResult
from api.services.curriculum.curriculum_retriever import retrieve_curriculum_context


router = APIRouter(prefix="/api/v1/curriculum", tags=["Curriculum Debug"])


def _assert_debug_enabled() -> None:
    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not found")


@router.get("/retrieve", response_model=CurriculumRetrievalResult)
async def retrieve_curriculum_get(
    grade: Optional[int] = Query(default=None, ge=1, le=12),
    subject: str = Query(default="Mathematics", min_length=1),
    topic: Optional[str] = None,
    problem_type: Optional[str] = None,
    message: str = "",
    language: Optional[str] = None,
    max_results: int = Query(default=5, ge=1, le=20),
) -> CurriculumRetrievalResult:
    """Debug endpoint for inspecting deterministic curriculum retrieval."""
    _assert_debug_enabled()
    return retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=grade,
            subject=subject,
            topic=topic,
            problem_type=problem_type,
            message=message,
            language=language,
            max_results=max_results,
        )
    )


@router.post("/retrieve", response_model=CurriculumRetrievalResult)
async def retrieve_curriculum_post(
    request: CurriculumRetrievalRequest,
) -> CurriculumRetrievalResult:
    """Debug endpoint for inspecting deterministic curriculum retrieval."""
    _assert_debug_enabled()
    return retrieve_curriculum_context(request)
