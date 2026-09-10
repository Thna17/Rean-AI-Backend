"""Fail-closed Khmer STEM terminology resolution.

Only a ``ReviewedKhmerGlossarySet`` embedded in an approved curriculum chunk
is allowed to reach a learner.  This module intentionally treats historical
``khmer_terms`` seed dictionaries as authoring hints, never as terminology.
"""
from __future__ import annotations

from typing import Any, Iterable

from api.models.curriculum import CurriculumChunk, ReviewedKhmerGlossarySet


def reviewed_glossary_metadata(
    chunks: Iterable[CurriculumChunk],
    *,
    required_terms: Iterable[object] = (),
) -> dict[str, Any]:
    """Return safe, lesson-scoped terms and deduplicated review queue items."""
    glossary_sets = _approved_sets(chunks)
    terms: dict[str, str] = {}
    provenance: dict[str, dict[str, str]] = {}
    # Chunks are already ranked.  The first reviewed set wins, so one session
    # never swaps a technical word half way through a lesson.
    for glossary_set in glossary_sets:
        for term in glossary_set.terms:
            key = _key(term.english)
            if key and key not in terms:
                terms[key] = term.khmer
                provenance[key] = {
                    "glossary_version": glossary_set.glossary_version,
                    "curriculum_version": glossary_set.curriculum_version,
                    "source_id": term.source_id,
                    "reviewer_status": term.reviewer_status.value,
                }

    requested = _unique_terms(required_terms)
    gaps = [term for term in requested if _key(term) not in terms]
    scope = _scope_for(glossary_sets, chunks)
    queue_items = [
        {
            "kind": "glossary_gap",
            "term": term,
            "grade": scope.get("grade"),
            "subject": scope.get("subject"),
            "lesson": scope.get("lesson"),
            "reason": "no_approved_khmer_term",
        }
        for term in gaps
    ]
    return {
        "approved_glossary_terms": terms,
        "glossary_term_provenance": provenance,
        "glossary_sets": [
            {
                "id": item.id,
                "glossary_version": item.glossary_version,
                "curriculum_version": item.curriculum_version,
                "source_id": item.source_id,
                "reviewer_status": item.reviewer_status.value,
            }
            for item in glossary_sets
        ],
        "glossary_gaps": gaps,
        # This is deliberately scope-only: never include student text or
        # private learner evidence in a curriculum review item.
        "curriculum_review_queue_items": queue_items,
    }


def audit_reviewed_glossary_coverage(
    chunks: Iterable[CurriculumChunk],
) -> dict[str, dict[str, int]]:
    """Count reviewed terminology by exact grade/subject without exposing text."""
    records = list(chunks)
    approved = _approved_sets(records)
    counts: dict[str, dict[str, int]] = {}
    for chunk in records:
        if chunk.grade is None:
            continue
        key = f"{chunk.grade}:{_key(chunk.subject)}"
        counts.setdefault(key, {"reviewed_sets": 0, "approved_terms": 0})
    seen_sets: set[str] = set()
    for glossary_set in approved:
        key = f"{glossary_set.grade}:{_key(glossary_set.subject)}"
        counts.setdefault(key, {"reviewed_sets": 0, "approved_terms": 0})
        if glossary_set.id not in seen_sets:
            counts[key]["reviewed_sets"] += 1
            counts[key]["approved_terms"] += len(glossary_set.terms)
            seen_sets.add(glossary_set.id)
    return dict(sorted(counts.items()))


def glossary_metadata_from_context(
    context: object,
    *,
    required_terms: Iterable[object] = (),
) -> dict[str, Any]:
    """Resolve only already-validated serialized glossary sets.

    This is useful at the policy boundary, where request metadata is not
    trusted.  Plain user-provided ``khmer_terms`` dictionaries are ignored.
    """
    records = context if isinstance(context, list) else [context]
    glossary_sets: list[ReviewedKhmerGlossarySet] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        raw = record.get("reviewed_khmer_glossary")
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            try:
                glossary_sets.append(ReviewedKhmerGlossarySet.model_validate(value))
            except Exception:
                continue
    return _metadata_from_sets(glossary_sets, required_terms=required_terms)


def _approved_sets(chunks: Iterable[CurriculumChunk]) -> list[ReviewedKhmerGlossarySet]:
    sets: list[ReviewedKhmerGlossarySet] = []
    for chunk in chunks:
        raw = chunk.metadata.get("reviewed_khmer_glossary")
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            try:
                glossary_set = ReviewedKhmerGlossarySet.model_validate(value)
            except Exception:
                continue
            if (
                glossary_set.grade == chunk.grade
                and _key(glossary_set.subject) == _key(chunk.subject)
            ):
                sets.append(glossary_set)
    return sets


def _metadata_from_sets(
    glossary_sets: list[ReviewedKhmerGlossarySet], *, required_terms: Iterable[object]
) -> dict[str, Any]:
    # Build tiny synthetic chunks only to share the exact term/provenance path.
    # It would be misleading to rebuild raw authoring chunks at this boundary,
    # so serialize the set directly instead.
    terms: dict[str, str] = {}
    provenance: dict[str, dict[str, str]] = {}
    for glossary_set in glossary_sets:
        for term in glossary_set.terms:
            key = _key(term.english)
            if key and key not in terms:
                terms[key] = term.khmer
                provenance[key] = {
                    "glossary_version": glossary_set.glossary_version,
                    "curriculum_version": glossary_set.curriculum_version,
                    "source_id": term.source_id,
                    "reviewer_status": term.reviewer_status.value,
                }
    requested = _unique_terms(required_terms)
    gaps = [term for term in requested if _key(term) not in terms]
    scope = glossary_sets[0] if glossary_sets else None
    return {
        "approved_glossary_terms": terms,
        "glossary_term_provenance": provenance,
        "glossary_sets": [
            {"id": item.id, "glossary_version": item.glossary_version,
             "curriculum_version": item.curriculum_version, "source_id": item.source_id,
             "reviewer_status": item.reviewer_status.value}
            for item in glossary_sets
        ],
        "glossary_gaps": gaps,
        "curriculum_review_queue_items": [
            {"kind": "glossary_gap", "term": term,
             "grade": scope.grade if scope else None,
             "subject": scope.subject if scope else None,
             "lesson": scope.lesson if scope else None,
             "reason": "no_approved_khmer_term"}
            for term in gaps
        ],
    }


def _scope_for(
    glossary_sets: list[ReviewedKhmerGlossarySet], chunks: Iterable[CurriculumChunk]
) -> dict[str, object]:
    if glossary_sets:
        item = glossary_sets[0]
        return {"grade": item.grade, "subject": item.subject, "lesson": item.lesson}
    first = next(iter(chunks), None)
    if first is None:
        return {"grade": None, "subject": None, "lesson": None}
    return {"grade": first.grade, "subject": first.subject,
            "lesson": first.subtopic or first.topic}


def _unique_terms(values: Iterable[object]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = str(value).strip()
        key = _key(term)
        if key and key not in seen:
            result.append(term)
            seen.add(key)
    return result


def _key(value: object) -> str:
    return " ".join(str(value).lower().replace("_", " ").split())
