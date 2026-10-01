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
    version_id = "cv-chem-electrokinetics-v1"

    # 1. Before publishing, query is Tier 2 (out of curriculum store / unverified)
    query = (
        "Electrokinetic Zeta Potential: calculate the Stern-layer potential "
        "of a colloidal suspension"
    )
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
                "id": f"admin.{version_id}.content-electrokinetics-1",
                "grade": 12,
                "subject": "Chemistry",
                "topic": "Electrokinetic Zeta Potential",
                "subtopic": "Stern-layer potential in colloidal suspensions",
                "content_type": "concept",
                "text": "Electrokinetic zeta potential describes the electrical potential at the slipping plane around a colloidal particle in suspension.",
                "language": "en",
                "tags": ["chemistry", "electrokinetics", "zeta potential", "colloid", "Stern layer"],
                "khmer_terms": {
                    "zeta potential": "សក្តានុពលហ្សេតា",
                    "colloidal suspension": "សូលុយស្យុងកូឡូអ៊ីត",
                    "slipping plane": "ប្លង់រអិល",
                },
                "prerequisites": ["Electric potential", "Colloidal mixtures"],
                "formulas": [
                    "zeta = (4 * eta * u) / epsilon",
                ],
                "solution_steps": [
                    "Identify the electrophoretic mobility u",
                    "Identify viscosity eta and permittivity epsilon",
                    "Substitute into the electrokinetic relation and compute zeta",
                ],
                "source": {
                    "type": "admin_published",
                    "metadata": {
                        "curriculum_version_id": version_id,
                        "curriculum_chunk_id": f"admin.{version_id}.content-electrokinetics-1",
                        "source_content_id": "content-electrokinetics-1",
                        "grade_level_id": "grade-12",
                        "subject_id": "chemistry",
                        "topic_id": "topic-electrokinetics",
                        "published_at": "2026-09-19T10:00:00Z",
                        "review_status": "approved",
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
    assert matched.topic == "Electrokinetic Zeta Potential"
    assert "zeta = (4 * eta * u) / epsilon" in matched.formulas
    assert len(matched.solution_steps) == 3
    assert matched.khmer_terms["zeta potential"] == "សក្តានុពលហ្សេតា"
    assert matched.source.metadata["review_status"] == "approved"

    # Also check Khmer query matching
    khmer_result = classify_student_query(
        message="Electrokinetic Zeta Potential ចូរគណនាសក្តានុពលហ្សេតា",
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


def test_unreviewed_published_content_is_rejected_and_never_verified(
    clean_published_store,
) -> None:
    client = TestClient(app)
    token = "test-internal-token-123"
    version_id = "cv-chem-unreviewed-actinometry-v1"
    query = "Ferrioxalate Actinometry: determine the incident photon flux"
    payload = {
        "curriculum_version_id": version_id,
        "chunks": [
            {
                "id": f"admin.{version_id}.content-actinometry-1",
                "grade": 12,
                "subject": "Chemistry",
                "topic": "Ferrioxalate Actinometry",
                "content_type": "concept",
                "text": "Ferrioxalate actinometry estimates incident photon flux from a photochemical reaction.",
                "language": "en",
                "tags": ["photochemistry", "actinometry", "photon flux"],
                "khmer_terms": {"photon flux": "លំហូរផូតុង"},
                "source": {
                    "type": "admin_published",
                    "metadata": {
                        "curriculum_version_id": version_id,
                        "curriculum_chunk_id": f"admin.{version_id}.content-actinometry-1",
                        "source_content_id": "content-actinometry-1",
                        "grade_level_id": "grade-12",
                        "subject_id": "chemistry",
                        "topic_id": "topic-actinometry",
                        "published_at": "2026-09-19T10:00:00Z",
                        "review_status": "draft",
                    },
                },
            }
        ],
    }

    response = client.put(
        f"/api/v1/internal/curriculum/versions/{version_id}",
        headers={"x-visual-tutor-internal-token": token},
        json=payload,
    )

    assert response.status_code == 400
    result = classify_student_query(
        message=query,
        grade=12,
        subject="Chemistry",
        topic=None,
    )
    assert result.tier == "unverified"
    assert result.matching_chunks == []


def test_published_content_cannot_replace_a_static_curriculum_chunk(
    clean_published_store,
) -> None:
    client = TestClient(app)
    version_id = "cv-colliding-static-id-v1"
    response = client.put(
        f"/api/v1/internal/curriculum/versions/{version_id}",
        headers={"x-visual-tutor-internal-token": "test-internal-token-123"},
        json={
            "curriculum_version_id": version_id,
            "chunks": [
                {
                    "id": "math.g11.functions.domain_range",
                    "grade": 11,
                    "subject": "Mathematics",
                    "topic": "Collision Attempt",
                    "text": "This must never shadow the static lesson.",
                    "source": {
                        "type": "admin_published",
                        "metadata": {
                            "curriculum_version_id": version_id,
                            "review_status": "approved",
                        },
                    },
                }
            ],
        },
    )

    assert response.status_code == 400
    assert not clean_published_store.exists()
