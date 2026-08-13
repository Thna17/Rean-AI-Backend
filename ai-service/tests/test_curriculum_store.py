from __future__ import annotations

import json

import pytest

from api.services.curriculum.curriculum_store import CurriculumStore


def test_curriculum_store_loads_seed_data_as_chunks() -> None:
    store = CurriculumStore()

    chunks = store.load_chunks()

    assert chunks
    assert all(chunk.id for chunk in chunks)
    assert "mathematics" in store.indexes["subject"]
    assert "10" in store.indexes["grade"]
    assert "linear equations" in store.indexes["topic"]
    assert "lesson chunk" in store.indexes["content_type"]
    assert "grade 10" in store.indexes["tags"]


def test_curriculum_store_filters_by_grade_subject_topic() -> None:
    store = CurriculumStore()

    results = store.query(
        grade=10,
        subject="Mathematics",
        topic="Linear Equations",
        max_results=2,
    )

    assert [chunk.id for chunk in results] == [
        "math.g10.linear_equations.one_variable"
    ]
    assert all(chunk.grade == 10 for chunk in results)
    assert all(chunk.subject == "Mathematics" for chunk in results)


def test_curriculum_store_filters_by_problem_type_language_and_max_results() -> None:
    store = CurriculumStore()

    results = store.query(
        subject="Mathematics",
        problem_type="line_through_two_points",
        language="en",
        max_results=1,
    )

    assert len(results) == 1
    assert results[0].id == "math.g10.coordinate_geometry.line_equation"
    assert "line_through_two_points" in results[0].problem_types


def test_curriculum_store_returns_empty_list_for_unknown_topic() -> None:
    store = CurriculumStore()

    results = store.query(
        grade=12,
        subject="Mathematics",
        topic="Unknown Topic",
        problem_type="unknown_problem",
    )

    assert results == []


def test_curriculum_store_fails_gracefully_when_data_folder_missing(tmp_path) -> None:
    store = CurriculumStore(data_dir=tmp_path / "missing")

    assert store.load_chunks() == []
    assert store.query(subject="Mathematics", topic="Linear Equations") == []
    assert store.indexes["topic"] == {}


def test_curriculum_store_handles_invalid_jsonl_row(tmp_path) -> None:
    data_dir = tmp_path / "curriculum"
    data_dir.mkdir()
    (data_dir / "broken.jsonl").write_text("{not-json}\n", encoding="utf-8")

    store = CurriculumStore(data_dir=data_dir)

    with pytest.raises(ValueError, match="Invalid curriculum row"):
        store.load_chunks()


def test_curriculum_store_handles_model_invalid_jsonl_row(tmp_path) -> None:
    data_dir = tmp_path / "curriculum"
    data_dir.mkdir()
    (data_dir / "broken.jsonl").write_text(
        json.dumps(
            {
                "id": "",
                "grade": 10,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "text": "Broken row",
                "source": {"type": "manual_seed"},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    store = CurriculumStore(data_dir=data_dir)

    with pytest.raises(ValueError, match="Invalid curriculum row"):
        store.load_chunks()
