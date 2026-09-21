from __future__ import annotations

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.core.config import get_settings
from api.services.curriculum.published_curriculum_store import PublishedCurriculumStore
from api.services.curriculum.curriculum_store import get_default_curriculum_store
from api.services.visual_tutor.rag_curriculum_gate import (
    classify_student_query,
    ClassificationResult,
)


@pytest.fixture
def clean_published_store(tmp_path, monkeypatch):
    """Isolate published curriculum store to a temp directory."""
    temp_store_path = tmp_path / "admin-published.jsonl"
    monkeypatch.setenv("ADMIN_PUBLISHED_CURRICULUM_PATH", str(temp_store_path))
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-internal-token-123")
    get_default_curriculum_store().reload()
    yield temp_store_path
    if temp_store_path.exists():
        temp_store_path.unlink()
    manifest_path = temp_store_path.with_suffix(".manifest.json")
    if manifest_path.exists():
        manifest_path.unlink()
    lock_path = temp_store_path.with_suffix(".lock")
    if lock_path.exists():
        lock_path.unlink()
    get_default_curriculum_store().reload()


def test_admin_curriculum_publish_sync_and_unpublish(clean_published_store):
    client = TestClient(app)
    token = "test-internal-token-123"
    version_id = "cv-chem-electrochem-v1"

    # 1. Before publishing, query is Tier 2 (out of curriculum store / unverified)
    query = "Calculate the standard electromotive force emf of a galvanic cell"
    pre_result = classify_student_query(
        message=query,
        grade=12,
        subject="Chemistry",
        topic=None,
    )
    assert pre_result.tier == "unverified"
    assert len(pre_result.matching_chunks) == 0

    # 2. Publish new topic and formulas from Admin
    payload = {
        "curriculum_version_id": version_id,
        "chunks": [
            {
                "id": f"admin.{version_id}.content-electrochem-1",
                "grade": 12,
                "subject": "Chemistry",
                "topic": "Electrochemistry",
                "subtopic": "Galvanic Cells and Electromotive Force",
                "content_type": "concept",
                "text": "Electrochemistry studies the relationship between electricity and chemical reactions. The electromotive force emf of a galvanic cell drives electron flow.",
                "language": "en",
                "tags": ["chemistry", "electrochemistry", "galvanic", "emf", "cell"],
                "khmer_terms": {
                    "electromotive force": "កម្លាំងអេឡិចត្រូចលករ",
                    "galvanic cell": "ពិលកាល់វ៉ានិច",
                    "reduction potential": "សក្តានុពលរេដុកម្ម",
                },
                "prerequisites": ["Redox Reactions", "Oxidation Numbers"],
                "formulas": [
                    "E_cell = E0_cell - (0.0592 / n) * log(Q)",
                    "E0_cell = E0_cathode - E0_anode",
                ],
                "solution_steps": [
                    "Identify oxidation and reduction half-reactions",
                    "Look up standard reduction potentials E0",
                    "Compute standard electromotive force E0_cell = E0_cathode - E0_anode",
                ],
                "source": {
                    "type": "admin_published",
                    "metadata": {
                        "curriculum_version_id": version_id,
                        "curriculum_chunk_id": f"admin.{version_id}.content-electrochem-1",
                        "source_content_id": "content-electrochem-1",
                        "grade_level_id": "grade-12",
                        "subject_id": "chemistry",
                        "topic_id": "topic-electrochemistry",
                        "published_at": "2026-09-19T10:00:00Z",
                    },
                },
            }
        ],
    }

    # PUT request to internal endpoint
    response = client.put(
        f"/api/v1/internal/curriculum/versions/{version_id}",
        headers={"x-visual-tutor-internal-token": token},
        json=payload,
    )
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["curriculum_version_id"] == version_id
    assert res_data["count"] == 1
    assert res_data["generation"] >= 1

    # 3. Immediately verified in memory without server restarts
    post_result = classify_student_query(
        message=query,
        grade=12,
        subject="Chemistry",
        topic=None,
    )
    assert post_result.tier == "verified"
    assert len(post_result.matching_chunks) >= 1
    matched = post_result.matching_chunks[0]
    assert matched.topic == "Electrochemistry"
    assert "E0_cell = E0_cathode - E0_anode" in matched.formulas
    assert len(matched.solution_steps) == 3
    assert matched.khmer_terms["electromotive force"] == "កម្លាំងអេឡិចត្រូចលករ"

    # Also check Khmer query matching
    khmer_result = classify_student_query(
        message="ចូរគណនាកម្លាំងអេឡិចត្រូចលករ",
        grade=12,
        subject="Chemistry",
        topic=None,
    )
    assert khmer_result.tier == "verified"

    # 4. Unpublish removes the version
    del_response = client.delete(
        f"/api/v1/internal/curriculum/versions/{version_id}",
        headers={"x-visual-tutor-internal-token": token},
    )
    assert del_response.status_code == 200
    del_data = del_response.json()
    assert del_data["removed"] == 1

    # 5. After unpublish, drops back to Tier 2 (Unverified)
    unpub_result = classify_student_query(
        message=query,
        grade=12,
        subject="Chemistry",
        topic=None,
    )
    assert unpub_result.tier == "unverified"
    assert len(unpub_result.matching_chunks) == 0
