"""Strictly scoped curriculum + KG grounding for Visual Tutor turns."""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any, Protocol

from api.models.curriculum import CurriculumRetrievalRequest
from api.services.curriculum.curriculum_retriever import retrieve_curriculum_context
from api.services.curriculum.curriculum_store import CurriculumStore
from api.services.curriculum.curriculum_release import audit_curriculum_coverage, release_gate_for_scope


class ConceptQueryService(Protocol):
    def query_concepts(self, query: str, learner_level: str = "B1", top_k: int = 8) -> list[dict[str, Any]]: ...


@dataclass(frozen=True)
class GroundedTeachingContext:
    scope: dict[str, Any]
    lesson: dict[str, Any] | None
    chunks: list[dict[str, Any]]
    knowledge_graph: dict[str, list[Any]]
    source_ids: list[str]
    confidence: float
    clarification_required: bool

    def server_metadata(self) -> dict[str, Any]:
        return {
            "grounded_teaching_context": {
                "scope": self.scope,
                "lesson": self.lesson,
                "chunks": self.chunks,
                "knowledge_graph": self.knowledge_graph,
                "source_ids": self.source_ids,
                "confidence": self.confidence,
                "clarification_required": self.clarification_required,
            },
            # Only source labels are suitable for a student-facing projection.
            "safe_curriculum_citations": self.source_ids[:3],
        }


def retrieve_grounded_visual_tutor_context(
    request: CurriculumRetrievalRequest,
    *,
    store: CurriculumStore,
    kg_service: ConceptQueryService | None = None,
) -> GroundedTeachingContext:
    """Retrieve exact lesson first, then bounded hybrid curriculum evidence.

    Grade and subject are hard filters here even if the underlying store permits
    generic chunks. This prevents a useful-looking chunk from another Khmer
    high-school grade or STEM subject being used as teaching evidence.
    """
    grade = request.grade
    subject = _norm(request.subject)
    if grade not in {10, 11, 12} or not subject or not request.topic:
        return _empty_context(request, reason="unsupported_or_incomplete_scope")
    if _release_gate_enforced() and not release_gate_for_scope(
        audit_curriculum_coverage(store=store), grade=grade, subject=request.subject
    )["passed"]:
        return _empty_context(request, reason="reviewed_lesson_coverage_incomplete")
    exact = [
        chunk for chunk in store.query(
            grade=grade, subject=request.subject, topic=request.topic,
            language=request.language,
        )
        if chunk.grade == grade and _norm(chunk.subject) == subject
    ]
    lesson_chunk = next(
        (chunk for chunk in exact if _norm(chunk.content_type) == "lesson"),
        exact[0] if exact else None,
    )
    hybrid = retrieve_curriculum_context(request, store=store)
    selected = []
    for chunk in ([lesson_chunk] if lesson_chunk else []) + hybrid.chunks:
        if chunk is None or chunk.grade != grade or _norm(chunk.subject) != subject:
            continue
        if all(existing.id != chunk.id for existing in selected):
            selected.append(chunk)
        if len(selected) == min(5, request.max_results):
            break
    kg_hits = _kg_hits(kg_service, request, selected)
    sources = [chunk.id for chunk in selected]
    confidence = min(1.0, hybrid.confidence + (.18 if lesson_chunk else 0) + (.08 if kg_hits["concepts"] else 0))
    return GroundedTeachingContext(
        scope={"grade": grade, "subject": request.subject, "topic": request.topic, "language": request.language or "en", "curriculum_version": _version(lesson_chunk)},
        lesson=_chunk_summary(lesson_chunk) if lesson_chunk else None,
        chunks=[_chunk_summary(chunk) for chunk in selected],
        knowledge_graph=kg_hits,
        source_ids=sources,
        confidence=round(confidence, 3),
        clarification_required=lesson_chunk is None or confidence < .45,
    )


def _kg_hits(service: ConceptQueryService | None, request: CurriculumRetrievalRequest, chunks: list[Any]) -> dict[str, list[Any]]:
    query = " ".join(filter(None, [request.subject, request.topic, request.problem_type, request.message]))
    concepts = service.query_concepts(query, top_k=5) if service is not None else []
    # Curriculum supplies subject/grade-scoped instructional KG facts; global
    # graph search augments labels only and never bypasses scope filtering.
    prerequisites = _unique(value for chunk in chunks for value in chunk.prerequisites)
    misconceptions = _unique(
        str(item.text if hasattr(item, "text") else item)
        for chunk in chunks for item in chunk.common_misconceptions
    )
    formulas = _unique(
        str(item.expression if hasattr(item, "expression") else item)
        for chunk in chunks for item in chunk.formulas
    )
    visuals = _unique(
        tag for chunk in chunks for tag in chunk.tags
        if tag in {"graph", "number_line", "table", "diagram", "balance_scale"}
    )
    return {"concepts": concepts, "prerequisites": prerequisites, "dependent_concepts": [], "common_misconceptions": misconceptions, "formulas": formulas, "visual_representations": visuals}


def _chunk_summary(chunk: Any) -> dict[str, Any]:
    return {"id": chunk.id, "grade": chunk.grade, "subject": chunk.subject, "topic": chunk.topic, "content_type": chunk.content_type, "text": chunk.text[:1200], "source_id": chunk.id}


def _empty_context(request: CurriculumRetrievalRequest, *, reason: str) -> GroundedTeachingContext:
    return GroundedTeachingContext(scope={"grade": request.grade, "subject": request.subject, "topic": request.topic, "language": request.language or "en", "curriculum_version": None}, lesson=None, chunks=[], knowledge_graph={"concepts": [], "prerequisites": [], "dependent_concepts": [], "common_misconceptions": [], "formulas": [], "visual_representations": []}, source_ids=[], confidence=0.0, clarification_required=True)


def _version(chunk: Any | None) -> str | None:
    if chunk is None:
        return None
    return str(chunk.source.metadata.get("curriculum_version_id") or chunk.source.metadata.get("version") or "default")


def _unique(values: Any) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if isinstance(value, str) and value.strip()))[:12]


def _norm(value: str) -> str:
    return " ".join(value.strip().lower().replace("_", " ").split())


def _release_gate_enforced() -> bool:
    return os.getenv("CURRICULUM_RELEASE_GATE_ENFORCED", "").lower() == "true" or os.getenv("ENVIRONMENT", "").lower() == "production"
