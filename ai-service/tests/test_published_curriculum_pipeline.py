"""Integration coverage for the controlled Admin-to-AI curriculum overlay.

These tests deliberately use the same persistent published store that the
internal service route updates.  A draft is represented by content that was
never accepted by ``replace_version``: draft content must not be discoverable
just because it exists elsewhere in the Admin system.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from api.models.curriculum import CurriculumRetrievalRequest
from api.services.curriculum import curriculum_store as curriculum_store_module
from api.services.curriculum.curriculum_retriever import (
    curriculum_metadata,
    retrieve_curriculum_context,
)
from api.services.curriculum.curriculum_store import CurriculumStore
from api.services.curriculum.published_curriculum_store import PublishedCurriculumStore


def _chunk(
    *,
    version_id: str = "cv-g10-math-v1",
    chunk_id: str = "content-linear-1",
    grade: int = 10,
    subject: str = "Mathematics",
    topic: str = "Admin Linear Equations",
    topic_id: str = "topic-linear",
) -> dict:
    return {
        "id": f"admin.{version_id}.{chunk_id}",
        "grade": grade,
        "subject": subject,
        "topic": topic,
        "content_type": "concept",
        "text": "Use the inverse operation on both sides of an equation.",
        "language": "en",
        "tags": [topic_id],
        "khmer_terms": {"inverse operation": "ប្រមាណវិធីបញ្ច្រាស"},
        "source": {
            "type": "admin_published",
            "metadata": {
                "curriculum_version_id": version_id,
                "curriculum_chunk_id": f"admin.{version_id}.{chunk_id}",
                "source_content_id": chunk_id,
                "grade_level_id": f"grade-{grade}",
                "subject_id": subject.lower(),
                "topic_id": topic_id,
                "published_at": "2026-08-24T00:00:00+00:00",
                # This deliberately sensitive value must never be returned as
                # a source reference to a student or planner response.
                "internal_admin_note": "reviewer-only note",
            },
        },
    }


def _retrieval_store(monkeypatch, published_path, tmp_path) -> CurriculumStore:
    monkeypatch.setattr(
        curriculum_store_module,
        "PublishedCurriculumStore",
        lambda: PublishedCurriculumStore(published_path),
    )
    data_dir = tmp_path / "seed-curriculum"
    data_dir.mkdir()
    return CurriculumStore(data_dir=data_dir)


def _retrieve(store: CurriculumStore, *, grade: int, subject: str, topic: str):
    return retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=grade,
            subject=subject,
            topic=topic,
            message="Explain this lesson",
        ),
        store=store,
    )


def test_draft_content_is_not_retrieved_until_its_version_is_published(monkeypatch, tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    store = _retrieval_store(monkeypatch, published_path, tmp_path)
    draft = _chunk()

    # A draft may exist in Firestore, but the AI store receives nothing until
    # the publish operation explicitly replaces this version.
    assert _retrieve(
        store,
        grade=draft["grade"],
        subject=draft["subject"],
        topic=draft["topic"],
    ).curriculum_chunk_ids == []


def test_published_content_is_retrieved_with_safe_source_references(monkeypatch, tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    published = PublishedCurriculumStore(published_path)
    chunk = _chunk()
    published.replace_version("cv-g10-math-v1", [chunk])
    store = _retrieval_store(monkeypatch, published_path, tmp_path)

    result = _retrieve(store, grade=10, subject="Mathematics", topic="Admin Linear Equations")

    assert result.curriculum_chunk_ids == [chunk["id"]]
    assert len(result.curriculum_sources) == 1
    reference = result.curriculum_sources[0]
    assert {
        "curriculum_version_id": "cv-g10-math-v1",
        "curriculum_chunk_id": chunk["id"],
        "grade_level_id": "grade-10",
        "subject_id": "mathematics",
        "topic_id": "topic-linear",
    }.items() <= reference.items()
    serialized_metadata = str(curriculum_metadata(result))
    assert "internal_admin_note" not in serialized_metadata
    assert "reviewer-only note" not in serialized_metadata


def test_archiving_a_published_version_removes_it_after_store_reload(monkeypatch, tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    published = PublishedCurriculumStore(published_path)
    chunk = _chunk()
    published.replace_version("cv-g10-math-v1", [chunk])
    store = _retrieval_store(monkeypatch, published_path, tmp_path)
    assert _retrieve(store, grade=10, subject="Mathematics", topic=chunk["topic"]).curriculum_chunk_ids

    assert published.remove_version("cv-g10-math-v1") == 1
    store.reload()

    assert _retrieve(store, grade=10, subject="Mathematics", topic=chunk["topic"]).curriculum_chunk_ids == []


def test_published_chunks_are_isolated_by_grade_subject_and_topic(monkeypatch, tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    published = PublishedCurriculumStore(published_path)
    math_10 = _chunk()
    math_11 = _chunk(
        version_id="cv-g11-math-v1",
        chunk_id="content-functions-1",
        grade=11,
        topic="Admin Functions",
        topic_id="topic-functions",
    )
    chemistry_10 = _chunk(
        version_id="cv-g10-chem-v1",
        chunk_id="content-atoms-1",
        subject="Chemistry",
        topic="Admin Atoms",
        topic_id="topic-atoms",
    )
    published.replace_version("cv-g10-math-v1", [math_10])
    published.replace_version("cv-g11-math-v1", [math_11])
    published.replace_version("cv-g10-chem-v1", [chemistry_10])
    store = _retrieval_store(monkeypatch, published_path, tmp_path)

    assert _retrieve(store, grade=10, subject="Mathematics", topic="Admin Linear Equations").curriculum_chunk_ids == [math_10["id"]]
    assert _retrieve(store, grade=11, subject="Mathematics", topic="Admin Functions").curriculum_chunk_ids == [math_11["id"]]
    assert _retrieve(store, grade=10, subject="Chemistry", topic="Admin Atoms").curriculum_chunk_ids == [chemistry_10["id"]]


def test_same_payload_retry_is_idempotent_and_does_not_advance_generation(tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    published = PublishedCurriculumStore(published_path)
    original = _chunk()

    published.replace_version("cv-g10-math-v1", [original])
    first_generation = published.generation()

    published.replace_version("cv-g10-math-v1", [deepcopy(original)])

    assert [chunk.id for chunk in published.load()] == [original["id"]]
    assert published.generation() == first_generation


def test_conflicting_payload_retry_is_rejected_without_changing_active_generation(tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    published = PublishedCurriculumStore(published_path)
    original = _chunk()
    conflicting_retry = deepcopy(original)
    conflicting_retry["text"] = "A different payload must not overwrite an immutable published version."

    published.replace_version("cv-g10-math-v1", [original])
    generation = published.generation()

    with pytest.raises(ValueError, match="different payload"):
        published.replace_version("cv-g10-math-v1", [conflicting_retry])

    assert published.generation() == generation
    assert published.load()[0].text == original["text"]


def test_generation_change_invalidates_an_existing_retrieval_cache(monkeypatch, tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    publisher = PublishedCurriculumStore(published_path)
    store = _retrieval_store(monkeypatch, published_path, tmp_path)
    first = _chunk()

    assert store.load_chunks() == []
    publisher.replace_version("cv-g10-math-v1", [first])

    # A separate replica's cached store detects the durable manifest generation
    # and reloads on its next retrieval without a process-local notification.
    assert [chunk.id for chunk in store.load_chunks()] == [first["id"]]
    publisher.remove_version("cv-g10-math-v1")
    assert store.load_chunks() == []


def test_concurrent_publishers_keep_both_distinct_versions(tmp_path) -> None:
    published_path = tmp_path / "admin-published.jsonl"
    first = _chunk()
    second = _chunk(
        version_id="cv-g11-math-v1",
        chunk_id="content-functions-1",
        grade=11,
        topic="Admin Functions",
        topic_id="topic-functions",
    )

    def publish(version_id: str, chunk: dict) -> list[str]:
        # Separate store instances model separate publisher workers sharing a
        # durable volume, rather than one process-local lock owner.
        return [item.id for item in PublishedCurriculumStore(published_path).replace_version(version_id, [chunk])]

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda args: publish(*args), (("cv-g10-math-v1", first), ("cv-g11-math-v1", second))))

    assert results == [[first["id"]], [second["id"]]]
    stored = PublishedCurriculumStore(published_path)
    assert {chunk.id for chunk in stored.load()} == {first["id"], second["id"]}
    assert stored.status()["versions"] == 2
    assert stored.generation() == 2
