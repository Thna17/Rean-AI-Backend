"""Release-gate coverage for reviewed Cambodian STEM lesson content.

These tests deliberately distinguish an outline (which is useful for saying
what is missing) from an approved lesson record (which is safe to teach).
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.models.curriculum import ReviewedLessonChunk
from api.services.curriculum.curriculum_release import (
    audit_curriculum_coverage,
    build_coverage_manifest,
    release_gate_for_scope,
)


def _reviewed_lesson(**overrides: object) -> dict[str, object]:
    lesson: dict[str, object] = {
        "id": "reviewed.math.g10.one-variable-equations",
        "grade": 10,
        "subject": "Mathematics",
        "topic": "Linear Equations",
        "lesson": "One-variable equations",
        "curriculum_version": "moeys-upper-secondary-2006.reviewed-v1",
        "learning_objectives": ["Solve a one-variable linear equation."],
        "formulas": [{"expression": "ax + b = c"}],
        "prerequisites": ["variables"],
        "dependent_concepts": ["systems of linear equations"],
        "common_misconceptions": [
            {"text": "Subtracting a term from only one side."},
        ],
        "visual_representations": ["equation_transformations", "balance_scale"],
        "khmer_terms": {"equation": "សមីការ"},
        "language": "bilingual",
        "source_ids": ["moeys-upper-secondary-2006:p10"],
        "review_status": "approved",
    }
    lesson.update(overrides)
    return lesson


def test_reviewed_lesson_requires_approved_evidence_and_rejects_unknown_fields() -> None:
    lesson = ReviewedLessonChunk.model_validate(_reviewed_lesson())

    assert lesson.review_status.value == "approved"
    assert lesson.curriculum_version == "moeys-upper-secondary-2006.reviewed-v1"
    assert lesson.khmer_terms == {"equation": "សមីការ"}

    with pytest.raises(ValidationError, match="only approved lesson chunks"):
        ReviewedLessonChunk.model_validate(_reviewed_lesson(review_status="draft"))
    with pytest.raises(ValidationError):
        ReviewedLessonChunk.model_validate(_reviewed_lesson(source_ids=[]))
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ReviewedLessonChunk.model_validate(_reviewed_lesson(unverified_translation="x"))


def test_default_audit_marks_legacy_and_missing_grade_subject_content_unsupported() -> None:
    manifest = audit_curriculum_coverage()

    assert manifest["schema_version"] == 1
    # This is the current official outline inventory (not a claim that these
    # lessons are teachable yet). Keep the count explicit so outline changes
    # require a conscious coverage review.
    assert len(manifest["lessons"]) == 48
    assert manifest["supported_lessons"] == 0
    assert manifest["missing_lessons"] == 48
    assert {lesson["grade"] for lesson in manifest["lessons"]} == {10, 11, 12}
    assert {lesson["subject"] for lesson in manifest["lessons"]} == {
        "Mathematics", "Physics", "Chemistry",
    }
    statuses = {lesson["status"] for lesson in manifest["lessons"]}
    assert statuses == {"missing_reviewed_lesson", "missing_official_outline"}
    assert sum(lesson["status"] == "missing_official_outline" for lesson in manifest["lessons"]) == 6

    for grade in (10, 11, 12):
        for subject in ("Mathematics", "Physics", "Chemistry"):
            gate = release_gate_for_scope(manifest, grade=grade, subject=subject)
            assert gate == {
                "passed": False,
                "grade": grade,
                "subject": subject,
                "reason": "approved_lesson_coverage_incomplete",
            }


def test_release_gate_passes_only_when_every_required_lesson_is_approved() -> None:
    manifest = build_coverage_manifest([
        {"grade": 10, "subject": "Mathematics", "lesson": "A", "supported": True},
        {"grade": 10, "subject": "Mathematics", "lesson": "B", "supported": True},
        {"grade": 10, "subject": "Physics", "lesson": "C", "supported": False},
    ])

    assert manifest["coverage"]["10:mathematics"] == {
        "required": 2, "supported": 2, "release_ready": True,
    }
    assert release_gate_for_scope(manifest, grade=10, subject="math")["passed"] is True
    assert release_gate_for_scope(manifest, grade=10, subject="physics")["passed"] is False
    # An absent Grade 11/12 entry must fail closed rather than be inferred from
    # Grade 10 coverage.
    assert release_gate_for_scope(manifest, grade=11, subject="Mathematics")["passed"] is False
