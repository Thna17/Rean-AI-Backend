#!/usr/bin/env python3
"""Convert raw PDF page extracts into reviewable curriculum chunks.

This script reads JSONL rows produced by ingest_curriculum_pdf.py and writes
CurriculumChunk-compatible JSONL for manual review. Output is intentionally
kept under data/curriculum_chunks/ and is not loaded by production retrieval.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Optional

from api.models.curriculum import CurriculumChunk


AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = AI_SERVICE_ROOT / "data" / "curriculum_chunks"

CONTENT_TYPES = {
    "concept",
    "formula",
    "worked_example",
    "exercise",
    "answer_key",
    "glossary",
    "unknown",
}


def build_curriculum_chunks(
    *,
    input_path: Path,
    output_path: Optional[Path] = None,
) -> Path:
    rows = _load_jsonl(input_path)
    chunks = []
    for row in rows:
        chunk = _row_to_chunk(row)
        if chunk is not None:
            chunks.append(chunk)

    output = output_path or _default_output_path(input_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(
                json.dumps(
                    chunk.model_dump(mode="json"),
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    return output


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    input_file = path.expanduser().resolve()
    if not input_file.is_file():
        raise FileNotFoundError(f"Extracted JSONL not found: {input_file}")
    rows: list[dict[str, Any]] = []
    with input_file.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid extracted JSONL row {input_file}:{line_number}: {exc}"
                ) from exc
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _row_to_chunk(row: dict[str, Any]) -> Optional[CurriculumChunk]:
    text = _clean_text(str(row.get("text") or ""))
    if not _is_useful_text(text):
        return None

    heading = _infer_heading(text)
    content_type, confidence = _classify_content(text)
    formulas = _extract_formulas(text) if content_type in {"formula", "concept"} else []
    source = dict(row.get("source") or {})
    source_metadata = dict(source.get("metadata") or {})
    source["metadata"] = {
        **source_metadata,
        "ingestion_stage": "review_chunk",
        "raw_chunk_id": row.get("id"),
    }

    grade = row.get("grade")
    subject = str(row.get("subject") or "Mathematics")
    topic = heading.get("topic") or row.get("topic") or "Unclassified"
    subtopic = heading.get("subtopic") or row.get("subtopic")
    chunk_id = _chunk_id(row, content_type)
    base_payload: dict[str, Any] = {
        "id": chunk_id,
        "grade": grade,
        "subject": subject,
        "chapter": heading.get("chapter") or row.get("chapter"),
        "topic": topic,
        "subtopic": subtopic,
        "problem_types": _infer_problem_types(text),
        "content_type": content_type,
        "text": text,
        "concepts": [],
        "formulas": formulas,
        "examples": [],
        "exercises": [],
        "solution_steps": _extract_solution_steps(text),
        "prerequisites": [],
        "common_misconceptions": [],
        "teaching_sequence": [],
        "khmer_terms": {},
        "language": _detect_language(text),
        "difficulty": None,
        "tags": _tags(row, content_type, topic),
        "source": source,
        "metadata": {
            **dict(row.get("metadata") or {}),
            "chunk_builder": "build_curriculum_chunks_v1",
            "classification_confidence": confidence,
            "requires_manual_review": True,
            "production_retrieval_enabled": False,
        },
    }

    if content_type == "worked_example":
        base_payload["examples"] = [
            {
                "id": f"{chunk_id}.example",
                "problem": _first_non_heading_line(text),
                "solution_steps": _extract_solution_steps(text),
                "language": base_payload["language"],
                "source": source,
                "metadata": {"requires_manual_review": True},
            }
        ]
    elif content_type == "exercise":
        base_payload["exercises"] = [
            {
                "id": f"{chunk_id}.exercise",
                "prompt": _first_non_heading_line(text),
                "hints": [],
                "solution_steps": [],
                "language": base_payload["language"],
                "source": source,
                "metadata": {"requires_manual_review": True},
            }
        ]

    return CurriculumChunk.model_validate(base_payload)


def _classify_content(text: str) -> tuple[str, float]:
    lowered = text.lower()
    if re.search(r"\b(answer key|answers|solutions)\b", lowered):
        return "answer_key", 0.86
    if re.search(r"\b(glossary|vocabulary|terms)\b", lowered):
        return "glossary", 0.82
    if re.search(r"\b(exercise|practice|problem set|try)\b", lowered) or re.search(
        r"(^|\n)\s*\d+[.)]\s+", text
    ):
        return "exercise", 0.84
    if re.search(r"\b(example|worked example|solution)\b", lowered):
        return "worked_example", 0.84
    if _extract_formulas(text):
        return "formula", 0.78
    if len(text.split()) >= 8:
        return "concept", 0.62
    return "unknown", 0.35


def _extract_formulas(text: str) -> list[dict[str, Any]]:
    formulas: list[dict[str, Any]] = []
    seen: set[str] = set()
    patterns = [
        r"[A-Za-z]\([^)]*\)\s*=\s*[^.\n]+",
        r"[A-Za-z]\s*=\s*[^.\n]+",
        r"[^.\n]*=[^.\n]*",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            expression = match.group(0).strip(" :;,.")
            if len(expression) < 3 or expression in seen:
                continue
            seen.add(expression)
            formulas.append(
                {
                    "expression": expression,
                    "metadata": {"requires_manual_review": True},
                }
            )
    return formulas[:5]


def _extract_solution_steps(text: str) -> list[str]:
    steps: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip(" -\t")
        if re.match(r"(?i)^(step\s*)?\d+[.)]\s+", cleaned):
            steps.append(cleaned)
        elif re.match(r"(?i)^(therefore|so|then|next)\b", cleaned):
            steps.append(cleaned)
    return steps[:8]


def _infer_heading(text: str) -> dict[str, Optional[str]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return {"chapter": None, "topic": None, "subtopic": None}
    chapter = None
    topic = None
    subtopic = None
    for line in lines[:5]:
        if re.match(r"(?i)^chapter\s+\d+", line):
            chapter = line
            continue
        if _looks_like_heading(line):
            if topic is None:
                topic = line
            elif subtopic is None:
                subtopic = line
                break
    return {"chapter": chapter, "topic": topic, "subtopic": subtopic}


def _looks_like_heading(line: str) -> bool:
    words = line.split()
    if len(words) > 8:
        return False
    if re.search(r"[.=]", line):
        return False
    return line.istitle() or line.isupper() or re.match(r"^\d+(\.\d+)*\s+", line) is not None


def _infer_problem_types(text: str) -> list[str]:
    lowered = text.lower()
    problem_types: list[str] = []
    if "slope" in lowered:
        problem_types.append("slope_from_two_points")
    if "line" in lowered and "equation" in lowered:
        problem_types.append("line_through_two_points")
    if "quadratic" in lowered or re.search(r"x\^2|x²", lowered):
        problem_types.append("quadratic_equation")
    if "domain" in lowered:
        problem_types.append("function_domain")
    if "range" in lowered:
        problem_types.append("function_range")
    if "percent" in lowered or "%" in text:
        problem_types.append("simple_percentage_word_problem")
    if "linear equation" in lowered or re.search(r"\d*x\s*[+-]\s*\d+\s*=", lowered):
        problem_types.append("linear_equation_one_variable")
    return list(dict.fromkeys(problem_types))


def _tags(row: dict[str, Any], content_type: str, topic: str) -> list[str]:
    tags = [str(tag) for tag in row.get("tags") or [] if str(tag).strip()]
    tags.extend([content_type, "review_required", _slugify(topic)])
    return list(dict.fromkeys(tags))


def _chunk_id(row: dict[str, Any], content_type: str) -> str:
    source_id = str(row.get("id") or "pdf.unknown")
    return f"{source_id}.chunk.{content_type}"


def _first_non_heading_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip()
        if cleaned and not _looks_like_heading(cleaned):
            return cleaned
    return text.strip()


def _clean_text(text: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _is_useful_text(text: str) -> bool:
    if not text:
        return False
    compact = re.sub(r"\s+", "", text)
    return len(compact) >= 8


def _detect_language(text: str) -> str:
    return "km" if re.search(r"[\u1780-\u17ff]", text) else "en"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "untitled"


def _default_output_path(input_path: Path) -> Path:
    return DEFAULT_OUTPUT_DIR / f"{input_path.stem}_chunks.jsonl"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build reviewable curriculum chunks from raw PDF extract JSONL."
    )
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    output_path = build_curriculum_chunks(
        input_path=args.input_path,
        output_path=args.output,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
