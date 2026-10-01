from __future__ import annotations

import pytest

from api.models.curriculum import CurriculumRetrievalRequest
from api.services.curriculum.curriculum_retriever import retrieve_curriculum_context


def test_retrieves_linear_equation_curriculum_context() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=10,
            subject="Mathematics",
            topic="Linear Equations",
            problem_type="linear_equation_one_variable",
            message="Solve 2x + 5 = 15",
        )
    )

    assert result.curriculum_chunk_ids
    assert "math.g10.linear_equations.one_variable" in result.curriculum_chunk_ids
    assert "ax + b = c" in result.formulas
    assert result.confidence > 0


def test_retrieves_line_through_points_curriculum_context() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=10,
            subject="Mathematics",
            topic="Coordinate Geometry",
            problem_type="line_through_two_points",
            message="Find the equation of the line through D(0,1) and E(1,3)",
        )
    )

    assert "math.g10.coordinate_geometry.slope" in result.curriculum_chunk_ids
    assert "m = (y2 - y1) / (x2 - x1)" in result.formulas
    assert "slope" in result.khmer_terms
    assert result.curriculum_sources
    assert result.metadata["selected_scores"]


def test_grade_10_line_through_points_prefers_equation_of_line_context() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=10,
            subject="Mathematics",
            topic="Equation of a Line",
            problem_type="line_through_two_points",
            message="Find the equation of the line through D(0,1) and E(1,3)",
        )
    )

    assert result.curriculum_chunk_ids[0] == (
        "math.g10.coordinate_geometry.line_equation"
    )
    assert "y = mx + b" in result.formulas
    assert "point-slope form" in result.khmer_terms


def test_grade_10_slope_from_two_points_retrieves_slope_context() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=10,
            subject="Mathematics",
            topic="Slope",
            problem_type="slope_from_two_points",
            message="What is the slope between A(2,4) and B(5,10)?",
        )
    )

    assert result.curriculum_chunk_ids[0] == "math.g10.coordinate_geometry.slope"
    assert "change in y" in result.khmer_terms


def test_retrieves_grade_11_function_context() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=11,
            subject="Mathematics",
            topic="Functions",
            problem_type="function_domain",
            message="Find the domain of f(x) = 1 / (x - 2)",
        )
    )

    assert "math.g11.functions.domain_range" in result.curriculum_chunk_ids
    assert any("domain" in formula for formula in result.formulas)
    assert result.khmer_terms["function"] == "អនុគមន៍"
    assert result.curriculum_sources[0]["source_type"] == "manual_seed"


def test_grade_11_quadratic_retrieval_uses_problem_type_mapping() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=11,
            subject="Mathematics",
            topic="Quadratic Functions",
            problem_type="quadratic_equation",
            message="Solve x^2 - 5x + 6 = 0",
        )
    )

    assert result.curriculum_chunk_ids[0] == "math.g11.quadratic_functions.basic"
    assert "ax^2 + bx + c = 0" in result.formulas
    assert "zero product property" in result.khmer_terms


def test_problem_type_never_crosses_grade_boundary_from_stale_context() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=10,
            subject="Mathematics",
            topic="Linear Equations",
            problem_type="quadratic_equation",
            message="Solve x^2 - 5x + 6 = 0",
        )
    )

    assert result.curriculum_chunk_ids
    assert "math.g11.quadratic_functions.basic" not in result.curriculum_chunk_ids
    assert all(chunk.grade == 10 for chunk in result.chunks)
    assert all(chunk.subject == "Mathematics" for chunk in result.chunks)


def test_retrieval_never_crosses_subject_boundary() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=11,
            subject="Physics",
            topic="Functions",
            problem_type="function_domain",
            message="Find the domain of f(x) = 1 / (x - 2)",
        )
    )

    assert result.curriculum_chunk_ids == []
    assert result.chunks == []
    assert result.confidence == 0.0


@pytest.mark.parametrize(
    ("message", "language"),
    [
        ("Find the domain of f(x) = 1 / (x - 2)", "en"),
        ("សូមរកដែនកំណត់នៃ f(x) = 1 / (x - 2)", "km"),
    ],
)
def test_grade_11_function_retrieval_supports_english_and_khmer_queries(
    message: str,
    language: str,
) -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=11,
            subject="Mathematics",
            topic="Domain and Range",
            problem_type="function_domain",
            message=message,
            language=language,
        )
    )

    assert result.curriculum_chunk_ids[0] == "math.g11.functions.domain_range"
    assert result.chunks[0].chapter == "Functions"
    assert result.chunks[0].topic == "Domain and Range"
    assert result.chunks[0].subtopic == "Domain and range of functions"


def test_grade_12_function_transformation_retrieval() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=12,
            subject="Mathematics",
            topic="Function Transformations",
            problem_type="function_transformation",
            message="Describe g(x) = (x - 3)^2 + 2 from f(x) = x^2",
        )
    )

    assert result.curriculum_chunk_ids[0] == "math.g12.functions.transformations"
    assert any("shifts" in formula for formula in result.formulas)
    assert "transformation" in result.khmer_terms


def test_grade_12_exponential_log_retrieval_by_keyword_overlap() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=12,
            subject="Mathematics",
            topic="Exponential and Logarithmic Functions",
            problem_type="logarithmic_function",
            message="Rewrite log_2(8) = 3 in exponential form",
            language="en",
        )
    )

    assert result.curriculum_chunk_ids[0] == "math.g12.exponential_log.functions"
    assert "log_a(b) = x means a^x = b" in result.formulas
    assert result.confidence > 0
    assert result.metadata["ranking"]["message"] == "keyword_overlap"


def test_expanded_syllabus_retrieval_preserves_moeys_provenance() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=11,
            subject="Mathematics",
            topic="Sequences and Progressions",
            problem_type="arithmetic_progression",
            message="Find the common difference of an arithmetic progression",
        )
    )

    assert result.curriculum_chunk_ids[0] == "math.g11.sequences.complete"
    assert result.curriculum_sources[0]["source_type"] == "moeys_syllabus"
    assert result.curriculum_sources[0]["section"]


def test_unknown_topic_returns_empty_without_crashing() -> None:
    result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=12,
            subject="Mathematics",
            topic="Unknown Topic",
            problem_type="unknown_problem",
            message="This is not covered yet",
        )
    )

    assert result.chunks == []
    assert result.curriculum_chunk_ids == []
    assert result.confidence == 0
