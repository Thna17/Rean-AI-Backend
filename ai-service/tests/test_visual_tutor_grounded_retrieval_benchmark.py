"""Offline acceptance benchmark for scoped Cambodian high-school retrieval.

The fixture is intentionally small and deterministic.  It must stay runnable
without hosted embeddings or a populated production knowledge graph, so that
scope/grounding regressions fail before a deployment can mask them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.models.curriculum import CurriculumRetrievalRequest
from api.services.curriculum.curriculum_retriever import retrieve_curriculum_context
from api.services.curriculum.curriculum_store import CurriculumStore


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "visual_tutor_cambodian_retrieval_benchmark.json"


@pytest.fixture()
def cambodian_retrieval_benchmark(tmp_path: Path) -> tuple[dict, CurriculumStore]:
    payload = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    (tmp_path / "cambodian_high_school.jsonl").write_text(
        "\n".join(json.dumps(chunk, ensure_ascii=False) for chunk in payload["chunks"]),
        encoding="utf-8",
    )
    return payload, CurriculumStore(data_dir=tmp_path)


@pytest.mark.parametrize("case_index", range(9))
def test_cambodian_high_school_benchmark_retrieves_the_exact_lesson(
    cambodian_retrieval_benchmark: tuple[dict, CurriculumStore], case_index: int
) -> None:
    """Math, Physics, and Chemistry each remain grade-scoped across 10–12."""
    payload, store = cambodian_retrieval_benchmark
    case = payload["cases"][case_index]
    result = retrieve_curriculum_context(CurriculumRetrievalRequest(**case), store=store)

    assert result.curriculum_chunk_ids[0] == case["expected_chunk_id"]
    assert result.confidence >= 0.8
    assert result.curriculum_sources == [
        {
            "curriculum_version_id": payload["curriculum_version"],
            "curriculum_chunk_id": case["expected_chunk_id"],
            "grade_level_id": str(case["grade"]),
            "subject_id": case["subject"].lower(),
            "topic_id": next(
                chunk["source"]["metadata"]["topic_id"]
                for chunk in payload["chunks"]
                if chunk["id"] == case["expected_chunk_id"]
            ),
        }
    ]
    # Grounded context carries identifiers, formula/prerequisite material, and
    # a score.  It must never substitute an untraceable text-only response.
    assert result.formulas
    assert result.prerequisites
    assert result.metadata["selected_scores"][0]["chunk_id"] == case["expected_chunk_id"]


@pytest.mark.parametrize(
    ("grade", "subject", "topic", "problem_type", "message"),
    [
        (10, "Physics", "Electric Circuits", "ohms_law", "Find voltage"),
        (11, "Chemistry", "Chemical Equilibrium", "equilibrium_constant", "Find Kc"),
        (12, "Mathematics", "Linear Equations", "linear_equation_one_variable", "Solve 2x + 5 = 15"),
    ],
)
def test_wrong_grade_isolation_never_borrows_a_lesson(
    cambodian_retrieval_benchmark: tuple[dict, CurriculumStore],
    grade: int,
    subject: str,
    topic: str,
    problem_type: str,
    message: str,
) -> None:
    _, store = cambodian_retrieval_benchmark
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=grade,
            subject=subject,
            topic=topic,
            problem_type=problem_type,
            message=message,
        ),
        store=store,
    )

    assert result.chunks == []
    assert result.curriculum_chunk_ids == []
    assert result.confidence == 0.0


@pytest.mark.parametrize(
    ("subject", "topic", "problem_type"),
    [
        ("Mathematics", "Atomic Structure", "atomic_structure"),
        ("Physics", "Quadratic Functions", "quadratic_equation"),
        ("Chemistry", "Electric Circuits", "ohms_law"),
    ],
)
def test_wrong_subject_isolation_never_crosses_boundaries(
    cambodian_retrieval_benchmark: tuple[dict, CurriculumStore],
    subject: str,
    topic: str,
    problem_type: str,
) -> None:
    _, store = cambodian_retrieval_benchmark
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=10,
            subject=subject,
            topic=topic,
            problem_type=problem_type,
            message="Please explain this lesson.",
        ),
        store=store,
    )

    assert result.chunks == []
    assert result.confidence == 0.0


def test_unsupported_scope_has_no_grounding_and_can_trigger_clarification(
    cambodian_retrieval_benchmark: tuple[dict, CurriculumStore]
) -> None:
    """The retrieval seam exposes low confidence; orchestration must clarify."""
    _, store = cambodian_retrieval_benchmark
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=12,
            subject="Physics",
            topic="Quantum Chromodynamics",
            problem_type="unsupported",
            message="Explain color charge.",
        ),
        store=store,
    )

    assert result.curriculum_chunk_ids == []
    assert result.curriculum_sources == []
    assert result.confidence < 0.4
