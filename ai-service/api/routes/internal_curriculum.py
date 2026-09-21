from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from api.core.visual_tutor_gateway_auth import require_visual_tutor_service
from api.services.curriculum.published_curriculum_store import PublishedCurriculumStore
from api.services.curriculum.curriculum_store import get_default_curriculum_store

router = APIRouter(prefix="/api/v1/internal/curriculum", tags=["Internal Curriculum"])

class PublishVersionRequest(BaseModel):
    curriculum_version_id: str = Field(min_length=1, max_length=160)
    chunks: list[dict[str, Any]] = Field(min_length=1, max_length=5000)

def _safe_chunks(version_id: str, chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    allowed = {
        "id", "grade", "subject", "chapter", "topic", "subtopic",
        "content_type", "text", "language", "tags", "khmer_terms",
        "prerequisites", "formulas", "examples", "exercises",
        "solution_steps", "common_misconceptions", "problem_types", "difficulty"
    }
    output: list[dict[str, Any]] = []
    for raw in chunks:
        item = {key: raw[key] for key in allowed if key in raw and raw[key] is not None}
        source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
        metadata = source.get("metadata") if isinstance(source.get("metadata"), dict) else {}
        safe_metadata = {key: metadata.get(key) for key in ("curriculum_version_id", "curriculum_chunk_id", "source_content_id", "grade_level_id", "subject_id", "topic_id", "published_at")}
        if safe_metadata.get("curriculum_version_id") != version_id:
            raise ValueError("Version id mismatch")
        item["source"] = {"type": "admin_published", "metadata": safe_metadata}
        output.append(item)
    return output

@router.put("/versions/{curriculum_version_id}")
async def publish_version(curriculum_version_id: str, request: PublishVersionRequest, x_visual_tutor_internal_token: str | None = Header(default=None)):
    require_visual_tutor_service(x_visual_tutor_internal_token)
    if request.curriculum_version_id != curriculum_version_id:
        raise HTTPException(status_code=400, detail="Version id mismatch")
    try:
        chunks = PublishedCurriculumStore().replace_version(curriculum_version_id, _safe_chunks(curriculum_version_id, request.chunks))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid published curriculum payload") from exc
    get_default_curriculum_store().reload()
    status = PublishedCurriculumStore().status()
    return {"curriculum_version_id": curriculum_version_id, "curriculum_chunk_ids": [chunk.id for chunk in chunks], "count": len(chunks), "generation": status["generation"], "checksum": status["checksum"]}

@router.delete("/versions/{curriculum_version_id}")
async def unpublish_version(curriculum_version_id: str, x_visual_tutor_internal_token: str | None = Header(default=None)):
    require_visual_tutor_service(x_visual_tutor_internal_token)
    removed = PublishedCurriculumStore().remove_version(curriculum_version_id)
    get_default_curriculum_store().reload()
    return {"curriculum_version_id": curriculum_version_id, "removed": removed, "generation": PublishedCurriculumStore().generation()}
