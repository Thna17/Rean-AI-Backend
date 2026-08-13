from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.models.curriculum import (
    CurriculumChunk,
    CurriculumConcept,
    CurriculumExample,
    CurriculumExercise,
    CurriculumFormula,
    CurriculumMisconception,
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
    CurriculumSource,
)

CURRICULUM_DATA_DIR = (
    Path(__file__).resolve().parents[1] / "data" / "curriculum"
)


def test_curriculum_source_serializes_pdf_page_metadata() -> None:
    source = CurriculumSource(
        type="pdf",
        file_name="grade_12_math.pdf",
        pdf_path="/data/books/grade_12_math.pdf",
        page=14,
        page_start=14,
        page_end=16,
        title="Grade 12 Mathematics",
        publisher="Ministry of Education",
        section="Functions",
        metadata={"ocr_confidence": 0.93},
    )

    payload = source.model_dump(mode="json")

    assert payload["type"] == "pdf"
    assert payload["page"] == 14
    assert payload["page_start"] == 14
    assert payload["page_end"] == 16
    assert payload["metadata"]["ocr_confidence"] == 0.93


def test_curriculum_source_rejects_invalid_page_range() -> None:
    with pytest.raises(ValidationError):
        CurriculumSource(type="pdf", page_start=10, page_end=9)


def test_curriculum_chunk_serializes_structured_curriculum_content() -> None:
    source = CurriculumSource(
        type="pdf",
        file_name="grade_10_math.pdf",
        page=22,
        title="Grade 10 Mathematics",
    )
    formula = CurriculumFormula(
        id="formula.slope",
        expression="m = (y2 - y1) / (x2 - x1)",
        variables={"m": "slope"},
        source=source,
    )
    misconception = CurriculumMisconception(
        id="mis.slope.reverse",
        text="Students may reverse rise and run.",
        correction="Use change in y over change in x.",
        diagnostic_cues=["uses x-change as numerator"],
    )
    chunk = CurriculumChunk(
        id="math.g10.coordinate_geometry.slope",
        grade=10,
        subject="Mathematics",
        chapter="Coordinate Geometry",
        topic="Coordinate Geometry",
        subtopic="Slope from two points",
        content_type="lesson_chunk",
        text="Find slope by comparing vertical change to horizontal change.",
        concepts=[
            CurriculumConcept(
                id="concept.slope",
                grade=10,
                subject="Mathematics",
                topic="Coordinate Geometry",
                text="Slope measures steepness.",
            )
        ],
        formulas=[formula],
        examples=[
            CurriculumExample(
                problem="Find the slope between A(0, 1) and B(1, 3).",
                answer="2",
                solution_steps=["Compute change in y.", "Compute change in x."],
            )
        ],
        exercises=[
            CurriculumExercise(
                prompt="Find the slope between C(2, 4) and D(5, 10).",
                hints=["Label x1, y1, x2, y2."],
            )
        ],
        solution_steps=["label points", "compute rise", "compute run"],
        prerequisites=["ordered pairs"],
        common_misconceptions=[misconception],
        khmer_terms={"slope": "ជម្រាល"},
        language="en",
        difficulty="medium",
        source=source,
        tags=["slope", "points"],
        metadata={"import_batch": "manual-test"},
    )

    payload = chunk.model_dump(mode="json")

    assert payload["id"] == "math.g10.coordinate_geometry.slope"
    assert payload["formulas"][0]["expression"] == "m = (y2 - y1) / (x2 - x1)"
    assert payload["examples"][0]["answer"] == "2"
    assert payload["exercises"][0]["hints"] == ["Label x1, y1, x2, y2."]
    assert payload["common_misconceptions"][0]["correction"] == (
        "Use change in y over change in x."
    )
    assert payload["source"]["file_name"] == "grade_10_math.pdf"


def test_curriculum_chunk_keeps_backward_compatible_string_formulas() -> None:
    chunk = CurriculumChunk(
        id="math.g10.linear_equations.one_variable",
        grade=10,
        subject="Mathematics",
        topic="Linear Equations",
        text="Remove the constant term first.",
        formulas=["ax + b = c", "x = (c - b) / a"],
        common_misconceptions=["changing only one side"],
        source=CurriculumSource(type="manual_seed"),
    )

    assert chunk.formulas == ["ax + b = c", "x = (c - b) / a"]
    assert chunk.common_misconceptions == ["changing only one side"]


def test_curriculum_models_validate_required_fields() -> None:
    with pytest.raises(ValidationError):
        CurriculumChunk(
            id="",
            subject="Mathematics",
            topic="Functions",
            text="Domain and range",
            source=CurriculumSource(type="pdf"),
        )

    with pytest.raises(ValidationError):
        CurriculumFormula(expression="")

    with pytest.raises(ValidationError):
        CurriculumRetrievalRequest(grade=13)


def test_curriculum_retrieval_result_serializes_structured_chunks() -> None:
    chunk = CurriculumChunk(
        id="math.g11.functions.domain_range",
        grade=11,
        subject="Mathematics",
        topic="Functions",
        text="A function maps inputs to outputs.",
        formulas=[CurriculumFormula(expression="f: X -> Y")],
        prerequisites=["sets"],
        common_misconceptions=[
            CurriculumMisconception(text="Confusing domain and range.")
        ],
        khmer_terms={"function": "អនុគមន៍"},
        source=CurriculumSource(type="pdf", page=5),
    )
    result = CurriculumRetrievalResult(
        chunks=[chunk],
        formulas=["f: X -> Y"],
        prerequisites=["sets"],
        common_misconceptions=["Confusing domain and range."],
        curriculum_chunk_ids=[chunk.id],
        confidence=0.8,
    )

    payload = result.model_dump(mode="json")

    assert payload["chunks"][0]["formulas"][0]["expression"] == "f: X -> Y"
    assert payload["curriculum_chunk_ids"] == ["math.g11.functions.domain_range"]
    assert payload["confidence"] == 0.8


def test_manual_seed_curriculum_jsonl_records_match_model() -> None:
    paths = sorted(CURRICULUM_DATA_DIR.glob("grade_*_math.jsonl"))

    assert paths

    seen_ids: set[str] = set()
    for path in paths:
        rows = [
            line.strip()
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows, f"{path.name} should contain at least one curriculum row"

        for line_number, row in enumerate(rows, start=1):
            payload = json.loads(row)
            chunk = CurriculumChunk.model_validate(payload)

            assert chunk.id not in seen_ids, f"duplicate chunk id {chunk.id}"
            seen_ids.add(chunk.id)
            assert chunk.source.type == "manual_seed", (
                f"{path.name}:{line_number} must use source.type manual_seed"
            )
            assert chunk.formulas, f"{chunk.id} must include formulas"
            assert chunk.prerequisites, f"{chunk.id} must include prerequisites"
            assert chunk.teaching_sequence, (
                f"{chunk.id} must include teaching_sequence"
            )
            assert chunk.common_misconceptions, (
                f"{chunk.id} must include common_misconceptions"
            )
            assert chunk.khmer_terms, f"{chunk.id} must include Khmer terms"
            assert chunk.examples, f"{chunk.id} must include a worked example"
            assert chunk.exercises, f"{chunk.id} must include an exercise example"

    assert {
        "math.g10.linear_equations.one_variable",
        "math.g10.coordinate_plane.basics",
        "math.g10.coordinate_geometry.slope",
        "math.g10.coordinate_geometry.line_equation",
        "math.g11.functions.introduction",
        "math.g11.linear_functions.basic",
        "math.g11.quadratic_functions.basic",
        "math.g11.functions.domain_range",
        "math.g12.functions.advanced",
        "math.g12.functions.transformations",
        "math.g12.exponential_log.functions",
    }.issubset(seen_ids)
