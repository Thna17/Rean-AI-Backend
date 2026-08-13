from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.models.curriculum import CurriculumChunk
from scripts.ingest_curriculum_pdf import (
    ExtractedPdfPage,
    extract_pdf_pages,
    ingest_pdf,
    main,
)


def _write_tiny_pdf(path: Path, text: str = "Linear equations page one") -> None:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length {len(stream)} >>
stream
{stream}
endstream
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""
    path.write_text(pdf, encoding="latin-1")


def test_extract_pdf_pages_with_tiny_generated_pdf_fixture(tmp_path) -> None:
    pdf_path = tmp_path / "grade_10_math.pdf"
    _write_tiny_pdf(pdf_path, "Linear equations page one")

    pages = extract_pdf_pages(pdf_path)

    assert pages == [ExtractedPdfPage(page=1, text="Linear equations page one")]


def test_ingest_pdf_writes_raw_page_jsonl_with_source_metadata(tmp_path) -> None:
    pdf_path = tmp_path / "grade_10_math.pdf"
    output_path = tmp_path / "raw.jsonl"
    _write_tiny_pdf(pdf_path, "Solve linear equations by balancing both sides")

    written = ingest_pdf(
        pdf_path=pdf_path,
        grade=10,
        subject="Mathematics",
        topic="Linear Equations",
        output_path=output_path,
    )

    assert written == output_path
    rows = [
        json.loads(line)
        for line in output_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1
    row = rows[0]
    chunk = CurriculumChunk.model_validate(row)
    assert chunk.grade == 10
    assert chunk.subject == "Mathematics"
    assert chunk.topic == "Linear Equations"
    assert chunk.source.type == "pdf_extract"
    assert chunk.source.file_name == "grade_10_math.pdf"
    assert chunk.source.page == 1
    assert chunk.metadata["production_retrieval_enabled"] is False
    assert "pdf_extract" in chunk.tags


def test_ingest_pdf_cli_writes_output_path(tmp_path, capsys) -> None:
    pdf_path = tmp_path / "grade_11_math.pdf"
    output_path = tmp_path / "cli_raw.jsonl"
    _write_tiny_pdf(pdf_path, "Functions domain and range")

    exit_code = main(
        [
            str(pdf_path),
            "--grade",
            "11",
            "--subject",
            "Mathematics",
            "--topic",
            "Functions",
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    assert str(output_path) in capsys.readouterr().out
    row = json.loads(output_path.read_text(encoding="utf-8").strip())
    assert row["source"]["type"] == "pdf_extract"
    assert row["source"]["page"] == 1


def test_extract_pdf_pages_requires_pdf_extension(tmp_path) -> None:
    text_path = tmp_path / "notes.txt"
    text_path.write_text("not a pdf", encoding="utf-8")

    with pytest.raises(ValueError, match="Expected a .pdf file"):
        extract_pdf_pages(text_path)
