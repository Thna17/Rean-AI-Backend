from __future__ import annotations

import json
from pathlib import Path

from api.models.curriculum import CurriculumChunk
from scripts.build_curriculum_chunks import build_curriculum_chunks, main


def _raw_row(
    *,
    row_id: str,
    text: str,
    page: int = 1,
    topic: str = "Unclassified",
) -> dict:
    return {
        "id": row_id,
        "grade": 10,
        "subject": "Mathematics",
        "chapter": None,
        "topic": topic,
        "subtopic": None,
        "content_type": "pdf_page_extract",
        "text": text,
        "language": "km" if any("\u1780" <= char <= "\u17ff" for char in text) else "en",
        "tags": ["grade 10", "mathematics", "pdf_extract"],
        "source": {
            "type": "pdf_extract",
            "file_name": "grade_10_math.pdf",
            "page": page,
            "title": "grade_10_math",
            "metadata": {"ingestion_stage": "raw_page_extract"},
        },
        "metadata": {
            "production_retrieval_enabled": False,
            "requires_chunk_review": True,
        },
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _read_chunks(path: Path) -> list[CurriculumChunk]:
    return [
        CurriculumChunk.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_formula_page_becomes_formula_chunk(tmp_path) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "chunks.jsonl"
    _write_jsonl(
        input_path,
        [
            _raw_row(
                row_id="pdf.mathematics.g10.book.p1",
                topic="Slope",
                text=(
                    "Slope\n"
                    "Formula: m = (y2 - y1) / (x2 - x1)\n"
                    "Use the same order for both points."
                ),
            )
        ],
    )

    build_curriculum_chunks(input_path=input_path, output_path=output_path)
    chunks = _read_chunks(output_path)

    assert len(chunks) == 1
    assert chunks[0].content_type == "formula"
    assert chunks[0].topic == "Slope"
    assert chunks[0].formulas
    assert chunks[0].formulas[0].expression == "m = (y2 - y1) / (x2 - x1)"
    assert chunks[0].source.type == "pdf_extract"
    assert chunks[0].source.page == 1
    assert chunks[0].metadata["classification_confidence"] > 0
    assert chunks[0].metadata["requires_manual_review"] is True


def test_exercise_page_becomes_exercise_chunk(tmp_path) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "chunks.jsonl"
    _write_jsonl(
        input_path,
        [
            _raw_row(
                row_id="pdf.mathematics.g10.book.p2",
                topic="Linear Equations",
                page=2,
                text=(
                    "Exercises\n"
                    "1. Solve 2x + 5 = 15\n"
                    "2. Solve 3x + 4 = 19"
                ),
            )
        ],
    )

    build_curriculum_chunks(input_path=input_path, output_path=output_path)
    chunks = _read_chunks(output_path)

    assert len(chunks) == 1
    assert chunks[0].content_type == "exercise"
    assert chunks[0].exercises
    assert chunks[0].exercises[0].prompt == "1. Solve 2x + 5 = 15"
    assert "linear_equation_one_variable" in chunks[0].problem_types


def test_khmer_text_is_preserved(tmp_path) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "chunks.jsonl"
    khmer_text = "សមីការលីនេអ៊ែរ\nគោលគំនិត៖ ដោះស្រាយដោយរក្សាទាំងសងខាងស្មើគ្នា។"
    _write_jsonl(
        input_path,
        [
            _raw_row(
                row_id="pdf.mathematics.g10.khmer.p3",
                topic="Linear Equations",
                page=3,
                text=khmer_text,
            )
        ],
    )

    build_curriculum_chunks(input_path=input_path, output_path=output_path)
    chunks = _read_chunks(output_path)

    assert len(chunks) == 1
    assert chunks[0].language == "km"
    assert "សមីការលីនេអ៊ែរ" in chunks[0].text
    assert chunks[0].source.page == 3


def test_invalid_or_empty_pages_are_skipped(tmp_path) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "chunks.jsonl"
    _write_jsonl(
        input_path,
        [
            _raw_row(row_id="pdf.empty", text="   "),
            _raw_row(row_id="pdf.too_short", text="x"),
            _raw_row(
                row_id="pdf.valid",
                text="Concept\nA linear equation keeps both sides balanced.",
            ),
        ],
    )

    build_curriculum_chunks(input_path=input_path, output_path=output_path)
    chunks = _read_chunks(output_path)

    assert [chunk.id for chunk in chunks] == ["pdf.valid.chunk.concept"]


def test_build_curriculum_chunks_cli_writes_output(tmp_path, capsys) -> None:
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "cli_chunks.jsonl"
    _write_jsonl(
        input_path,
        [
            _raw_row(
                row_id="pdf.cli",
                text="Glossary\nslope means steepness",
            )
        ],
    )

    exit_code = main([str(input_path), "--output", str(output_path)])

    assert exit_code == 0
    assert str(output_path) in capsys.readouterr().out
    chunks = _read_chunks(output_path)
    assert chunks[0].content_type == "glossary"
