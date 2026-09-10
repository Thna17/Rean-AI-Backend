"""Fail-closed production coverage gate for Cambodian high-school lessons."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from api.models.curriculum import ReviewedLessonChunk
from api.services.curriculum.curriculum_store import CurriculumStore, default_curriculum_data_dir
from api.services.curriculum.khmer_glossary import audit_reviewed_glossary_coverage

SUPPORTED_SUBJECTS = ("Mathematics", "Physics", "Chemistry")
SUPPORTED_GRADES = (10, 11, 12)


def audit_curriculum_coverage(
    *, store: CurriculumStore | None = None, outline_path: Path | None = None,
) -> dict[str, Any]:
    """Inventory outline lessons and approved, evidence-backed lesson chunks."""
    outline = json.loads((outline_path or _outline_path()).read_text(encoding="utf-8"))
    active_store = store or CurriculumStore()
    chunks = active_store.load_chunks()
    approved = _approved_lessons(active_store)
    lessons: list[dict[str, Any]] = []
    for unit in outline.get("units", []):
        subject = _canonical_subject(unit.get("subject", ""))
        grade = unit.get("grade")
        for topic in unit.get("topics", []):
            lesson_id, lesson_name, khmer_name = topic
            key = (grade, subject.lower(), _norm(lesson_name))
            match = approved.get(key)
            lessons.append({
                "lesson_id": lesson_id, "grade": grade, "subject": subject,
                "topic": unit.get("name"), "lesson": lesson_name,
                "language": "en", "khmer_label": khmer_name,
                "supported": match is not None,
                "status": "supported" if match else "missing_reviewed_lesson",
                "curriculum_version": match.curriculum_version if match else None,
                "source_ids": match.source_ids if match else [],
                "review_status": match.review_status.value if match else None,
            })
    present_scopes = {(item["grade"], item["subject"]) for item in lessons}
    # The source outline currently has no Grade 11/12 entries. Record that as
    # missing scope evidence instead of implying an empty scope is ready.
    for grade in SUPPORTED_GRADES:
        for subject in SUPPORTED_SUBJECTS:
            if (grade, subject) not in present_scopes:
                lessons.append({
                    "lesson_id": f"scope-{grade}-{subject.lower()}",
                    "grade": grade, "subject": subject, "topic": None,
                    "lesson": None, "language": "en", "khmer_label": None,
                    "supported": False, "status": "missing_official_outline",
                    "curriculum_version": None, "source_ids": [], "review_status": None,
                })
    manifest = build_coverage_manifest(lessons)
    glossary_coverage = audit_reviewed_glossary_coverage(chunks)
    for grade in SUPPORTED_GRADES:
        for subject in SUPPORTED_SUBJECTS:
            glossary_coverage.setdefault(
                f"{grade}:{subject.lower()}",
                {"reviewed_sets": 0, "approved_terms": 0},
            )
    manifest["glossary_coverage"] = dict(sorted(glossary_coverage.items()))
    return manifest


def build_coverage_manifest(lessons: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: {"required": 0, "supported": 0})
    for lesson in lessons:
        key = f"{lesson.get('grade')}:{str(lesson.get('subject')).lower()}"
        grouped[key]["required"] += 1
        grouped[key]["supported"] += int(lesson.get("supported") is True)
    coverage = {
        key: {**counts, "release_ready": counts["required"] > 0 and counts["supported"] == counts["required"]}
        for key, counts in sorted(grouped.items())
    }
    return {"schema_version": 1, "lessons": lessons, "coverage": coverage,
            "supported_lessons": sum(item["supported"] for item in lessons),
            "missing_lessons": sum(not item["supported"] for item in lessons)}


def release_gate_for_scope(manifest: dict[str, Any], *, grade: int, subject: str) -> dict[str, Any]:
    key = f"{grade}:{_canonical_subject(subject).lower()}"
    record = manifest.get("coverage", {}).get(key)
    passed = bool(record and record.get("release_ready"))
    return {"passed": passed, "grade": grade, "subject": _canonical_subject(subject),
            "reason": "approved_lesson_coverage_complete" if passed else "approved_lesson_coverage_incomplete"}


def _approved_lessons(store: CurriculumStore) -> dict[tuple[int, str, str], ReviewedLessonChunk]:
    results: dict[tuple[int, str, str], ReviewedLessonChunk] = {}
    for chunk in store.load_chunks():
        payload = chunk.model_dump(mode="json")
        metadata = payload.pop("metadata", {})
        reviewed_payload = {
            "id": chunk.id, "grade": chunk.grade, "subject": chunk.subject,
            "topic": chunk.topic, "lesson": metadata.get("lesson") or chunk.subtopic or chunk.topic,
            "curriculum_version": metadata.get("curriculum_version"),
            "learning_objectives": metadata.get("learning_objectives") or [],
            "formulas": [item for item in payload.get("formulas", []) if isinstance(item, dict)],
            "prerequisites": chunk.prerequisites,
            "dependent_concepts": metadata.get("dependent_concepts") or [],
            "common_misconceptions": [item for item in payload.get("common_misconceptions", []) if isinstance(item, dict)],
            "visual_representations": metadata.get("visual_representations") or [],
            "khmer_terms": chunk.khmer_terms, "language": chunk.language,
            "source_ids": metadata.get("source_ids") or [],
            "review_status": metadata.get("review_status"),
        }
        try:
            lesson = ReviewedLessonChunk.model_validate(reviewed_payload)
        except Exception:
            continue
        results[(lesson.grade, lesson.subject.lower(), _norm(lesson.lesson))] = lesson
    return results


def _outline_path() -> Path:
    return default_curriculum_data_dir().parent / "cambodia_curriculum.json"


def _canonical_subject(value: str) -> str:
    return {"math": "Mathematics", "mathematics": "Mathematics", "physics": "Physics", "chemistry": "Chemistry"}.get(str(value).lower(), str(value))


def _norm(value: str) -> str:
    return " ".join(str(value).lower().replace("_", " ").split())
