from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional

from api.models.curriculum import CurriculumChunk


def default_curriculum_data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "curriculum"


class CurriculumStore:
    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or default_curriculum_data_dir()
        self._chunks: Optional[list[CurriculumChunk]] = None
        self._indexes: dict[str, dict[str, list[CurriculumChunk]]] = {}

    def load_chunks(self) -> list[CurriculumChunk]:
        if self._chunks is None:
            self._chunks = list(_load_jsonl_chunks(self.data_dir))
            self._indexes = _build_indexes(self._chunks)
        return list(self._chunks)

    @property
    def indexes(self) -> dict[str, dict[str, list[CurriculumChunk]]]:
        self.load_chunks()
        return {
            index_name: {
                key: list(chunks)
                for key, chunks in values.items()
            }
            for index_name, values in self._indexes.items()
        }

    def query(
        self,
        *,
        grade: Optional[int] = None,
        subject: Optional[str] = None,
        topic: Optional[str] = None,
        subtopic: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[list[str]] = None,
        problem_type: Optional[str] = None,
        language: Optional[str] = None,
        max_results: Optional[int] = None,
    ) -> list[CurriculumChunk]:
        chunks = self.load_chunks()
        filtered = []
        tag_filters = {_norm(tag) for tag in tags or [] if tag.strip()}
        for chunk in chunks:
            if subject and _norm(chunk.subject) != _norm(subject):
                continue
            if grade is not None and chunk.grade not in {None, grade}:
                continue
            if language and chunk.language not in {language, "en"}:
                continue
            if content_type and _norm(chunk.content_type) != _norm(content_type):
                continue
            if subtopic and not _is_topic_match(_norm(subtopic), _norm(chunk.subtopic or "")):
                continue
            if tag_filters and not tag_filters.issubset({_norm(tag) for tag in chunk.tags}):
                continue
            if topic and not _topic_matches(chunk, topic):
                if problem_type and problem_type not in chunk.problem_types:
                    continue
                if not problem_type:
                    continue
            elif problem_type and problem_type not in chunk.problem_types:
                if not topic:
                    continue
            filtered.append(chunk)
            if max_results is not None and len(filtered) >= max_results:
                break
        return filtered


@lru_cache(maxsize=1)
def get_default_curriculum_store() -> CurriculumStore:
    return CurriculumStore()


def _load_jsonl_chunks(data_dir: Path) -> Iterable[CurriculumChunk]:
    if not data_dir.exists():
        return []
    chunks: List[CurriculumChunk] = []
    for path in sorted(data_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                    chunks.append(CurriculumChunk.model_validate(payload))
                except Exception as exc:
                    raise ValueError(
                        f"Invalid curriculum row {path}:{line_number}: {exc}"
                    ) from exc
    return chunks


def _build_indexes(
    chunks: list[CurriculumChunk],
) -> dict[str, dict[str, list[CurriculumChunk]]]:
    indexes: dict[str, dict[str, list[CurriculumChunk]]] = {
        "grade": {},
        "subject": {},
        "topic": {},
        "subtopic": {},
        "content_type": {},
        "tags": {},
    }
    for chunk in chunks:
        if chunk.grade is not None:
            _add_index_value(indexes["grade"], str(chunk.grade), chunk)
        _add_index_value(indexes["subject"], _norm(chunk.subject), chunk)
        _add_index_value(indexes["topic"], _norm(chunk.topic), chunk)
        if chunk.subtopic:
            _add_index_value(indexes["subtopic"], _norm(chunk.subtopic), chunk)
        _add_index_value(indexes["content_type"], _norm(chunk.content_type), chunk)
        for tag in chunk.tags:
            _add_index_value(indexes["tags"], _norm(tag), chunk)
    return indexes


def _add_index_value(
    index: dict[str, list[CurriculumChunk]],
    key: str,
    chunk: CurriculumChunk,
) -> None:
    if not key:
        return
    index.setdefault(key, []).append(chunk)


def _topic_matches(chunk: CurriculumChunk, topic: str) -> bool:
    topic_norm = _norm(topic)
    candidates = [
        chunk.topic,
        chunk.subtopic or "",
        chunk.chapter or "",
        *chunk.tags,
    ]
    return any(
        _is_topic_match(topic_norm, _norm(candidate))
        for candidate in candidates
        if candidate
    )


def _is_topic_match(topic_norm: str, candidate_norm: str) -> bool:
    if topic_norm == candidate_norm:
        return True
    if len(candidate_norm) <= 4:
        return candidate_norm in topic_norm.split()
    return topic_norm in candidate_norm or candidate_norm in topic_norm


def _norm(value: str) -> str:
    return value.strip().lower().replace("_", " ")
