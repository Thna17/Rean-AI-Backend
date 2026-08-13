#!/usr/bin/env python3
"""Extract curriculum PDF pages into raw JSONL rows.

This is an offline ingestion skeleton. It writes raw page-level rows to
data/curriculum_extracted/ and does not connect those rows to production
Visual Tutor retrieval.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = AI_SERVICE_ROOT / "data" / "curriculum_extracted"


@dataclass(frozen=True)
class ExtractedPdfPage:
    page: int
    text: str


def extract_pdf_pages(pdf_path: Path) -> list[ExtractedPdfPage]:
    """Extract text page by page using the best available local PDF tooling."""
    path = pdf_path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a .pdf file: {path}")

    extractors = (
        _extract_with_pdfplumber,
        _extract_with_pypdf,
        _extract_with_pdftotext,
        _extract_uncompressed_pdf_text,
    )
    errors: list[str] = []
    for extractor in extractors:
        try:
            pages = extractor(path)
            if pages:
                return pages
        except Exception as exc:
            errors.append(f"{extractor.__name__}: {exc}")
    raise RuntimeError(
        "No PDF text extractor succeeded. Install pdfplumber or pypdf, "
        f"or provide a text-based PDF. Details: {'; '.join(errors)}"
    )


def ingest_pdf(
    *,
    pdf_path: Path,
    grade: int,
    subject: str,
    topic: Optional[str] = None,
    output_path: Optional[Path] = None,
) -> Path:
    pages = extract_pdf_pages(pdf_path)
    output = output_path or _default_output_path(pdf_path, grade, subject)
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as handle:
        for page in pages:
            row = _page_to_curriculum_row(
                pdf_path=pdf_path,
                page=page,
                grade=grade,
                subject=subject,
                topic=topic,
            )
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return output


def _page_to_curriculum_row(
    *,
    pdf_path: Path,
    page: ExtractedPdfPage,
    grade: int,
    subject: str,
    topic: Optional[str],
) -> dict:
    file_stem = _slugify(pdf_path.stem)
    subject_slug = _slugify(subject)
    topic_text = topic or "Unclassified"
    topic_slug = _slugify(topic_text)
    return {
        "id": f"pdf.{subject_slug}.g{grade}.{file_stem}.p{page.page}",
        "grade": grade,
        "subject": subject,
        "chapter": None,
        "topic": topic_text,
        "subtopic": None,
        "problem_types": [],
        "content_type": "pdf_page_extract",
        "text": page.text.strip(),
        "concepts": [],
        "formulas": [],
        "examples": [],
        "exercises": [],
        "solution_steps": [],
        "prerequisites": [],
        "common_misconceptions": [],
        "teaching_sequence": [],
        "khmer_terms": {},
        "language": _detect_language(page.text),
        "difficulty": None,
        "tags": [
            f"grade {grade}",
            subject_slug,
            topic_slug,
            "pdf_extract",
        ],
        "source": {
            "type": "pdf_extract",
            "file_name": pdf_path.name,
            "page": page.page,
            "title": pdf_path.stem,
            "metadata": {
                "ingestion_stage": "raw_page_extract",
                "ocr_used": False,
            },
        },
        "metadata": {
            "production_retrieval_enabled": False,
            "requires_chunk_review": True,
        },
    }


def _extract_with_pdfplumber(path: Path) -> list[ExtractedPdfPage]:
    import pdfplumber  # type: ignore

    pages: list[ExtractedPdfPage] = []
    with pdfplumber.open(str(path)) as pdf:
        for index, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(ExtractedPdfPage(page=index, text=text))
    return pages


def _extract_with_pypdf(path: Path) -> list[ExtractedPdfPage]:
    from pypdf import PdfReader  # type: ignore

    reader = PdfReader(str(path))
    pages: list[ExtractedPdfPage] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(ExtractedPdfPage(page=index, text=text))
    return pages


def _extract_with_pdftotext(path: Path) -> list[ExtractedPdfPage]:
    binary = shutil.which("pdftotext")
    if not binary:
        raise RuntimeError("pdftotext is not installed")
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_prefix = Path(tmp_dir) / "page"
        subprocess.run(
            [binary, "-f", "1", "-l", "999999", "-layout", str(path), str(output_prefix)],
            check=True,
            capture_output=True,
            text=True,
        )
        text = output_prefix.read_text(encoding="utf-8", errors="replace")
    return [
        ExtractedPdfPage(page=index, text=page_text.strip())
        for index, page_text in enumerate(text.split("\f"), start=1)
        if page_text.strip()
    ]


def _extract_uncompressed_pdf_text(path: Path) -> list[ExtractedPdfPage]:
    """Tiny fallback for simple uncompressed PDFs used by tests.

    This is not OCR and not a full PDF parser. Real textbook extraction should
    use pdfplumber, pypdf, or pdftotext.
    """
    raw = path.read_bytes().decode("latin-1", errors="ignore")
    stream_texts = re.findall(r"stream\r?\n(.*?)\r?\nendstream", raw, re.DOTALL)
    pages: list[ExtractedPdfPage] = []
    for index, stream in enumerate(stream_texts, start=1):
        text = " ".join(_decode_pdf_literal(match) for match in _literal_texts(stream))
        text = re.sub(r"\s+", " ", text).strip()
        if text:
            pages.append(ExtractedPdfPage(page=index, text=text))
    return pages


def _literal_texts(stream: str) -> Iterable[str]:
    for match in re.finditer(r"\(((?:\\.|[^\\()])*)\)\s*Tj", stream):
        yield match.group(1)
    for array in re.findall(r"\[((?:.|\n)*?)\]\s*TJ", stream):
        for match in re.finditer(r"\(((?:\\.|[^\\()])*)\)", array):
            yield match.group(1)


def _decode_pdf_literal(value: str) -> str:
    return (
        value.replace(r"\(", "(")
        .replace(r"\)", ")")
        .replace(r"\\", "\\")
        .replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
    )


def _default_output_path(pdf_path: Path, grade: int, subject: str) -> Path:
    name = f"grade_{grade}_{_slugify(subject)}_{_slugify(pdf_path.stem)}_raw.jsonl"
    return DEFAULT_OUTPUT_DIR / name


def _detect_language(text: str) -> str:
    return "km" if re.search(r"[\u1780-\u17ff]", text) else "en"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "untitled"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract a curriculum PDF into raw page-level JSONL rows."
    )
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("--grade", type=int, required=True, choices=range(1, 13))
    parser.add_argument("--subject", required=True)
    parser.add_argument("--topic")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    output_path = ingest_pdf(
        pdf_path=args.pdf_path,
        grade=args.grade,
        subject=args.subject,
        topic=args.topic,
        output_path=args.output,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
