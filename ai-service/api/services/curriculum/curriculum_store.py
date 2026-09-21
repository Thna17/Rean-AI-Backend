from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional

from api.models.curriculum import CurriculumChunk
from api.services.curriculum.published_curriculum_store import PublishedCurriculumStore


def default_curriculum_data_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "curriculum"


class CurriculumStore:
    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = data_dir or default_curriculum_data_dir()
        self._chunks: Optional[list[CurriculumChunk]] = None
        self._indexes: dict[str, dict[str, list[CurriculumChunk]]] = {}
        self._published_generation: int | None = None

    def load_chunks(self) -> list[CurriculumChunk]:
        published = PublishedCurriculumStore()
        generation = published.generation()
        if self._chunks is None or self._published_generation != generation:
            self._chunks = list(_load_jsonl_chunks(self.data_dir)) + published.load()
            self._indexes = _build_indexes(self._chunks)
            self._published_generation = generation
        return list(self._chunks)

    def reload(self) -> None:
        self._chunks = None
        self._indexes = {}
        self._published_generation = None

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

    def list_subjects(self) -> list[str]:
        chunks = self.load_chunks()
        seen = set()
        subjects = []
        for chunk in chunks:
            s = chunk.subject.strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                subjects.append(s)
        return subjects

    def list_topics(self, subject: Optional[str] = None) -> list[str]:
        chunks = self.load_chunks()
        seen = set()
        topics = []
        norm_subj = _norm(subject) if subject else None
        for chunk in chunks:
            if norm_subj and _norm(chunk.subject) != norm_subj:
                continue
            t = chunk.topic.strip()
            if t and t.lower() not in seen:
                seen.add(t.lower())
                topics.append(t)
        return topics

    def search_chunks_by_query(
        self,
        query: str,
        *,
        grade: Optional[int] = None,
        subject: Optional[str] = None,
        limit: int = 5,
    ) -> list[tuple[float, CurriculumChunk]]:
        """Rank and return curriculum chunks matching tokens/terms in query."""
        if not query or not query.strip():
            return []
        chunks = self.load_chunks()
        query_norm = _norm(query)
        _STOPWORDS = {
            "the", "a", "an", "and", "or", "of", "in", "on", "to", "for", "with", "at",
            "by", "from", "is", "are", "was", "were", "be", "been", "being",
            "what", "how", "why", "which", "who", "whom", "this", "that", "these", "those",
            "find", "calculate", "solve", "evaluate", "determine", "given", "if", "we", "have",
            "can", "you", "its", "it", "let", "following", "show",
            "នៃ", "និង", "ឬ", "ក្នុង", "លើ", "ទៅ", "សម្រាប់", "ជាមួយ", "នៅ", "ពី", "គឺ", "ជា",
            "តើ", "អ្វី", "យ៉ាងណា", "ហេតុអ្វី", "ដែល", "នេះ", "នោះ",
            "រក", "គណនា", "ដោះស្រាយ", "កំណត់", "ឱ្យ", "ប្រសិនបើ", "យើង", "មាន", "ចូរ",
        }
        query_tokens = [
            t for t in re.findall(r"[\w\u1780-\u17ff]+", query_norm)
            if len(t) > 1 and t not in _STOPWORDS
        ]
        if not query_tokens:
            query_tokens = [t for t in re.findall(r"[\w\u1780-\u17ff]+", query_norm) if len(t) > 1]
        if not query_tokens:
            query_tokens = [query_norm]

        scored: list[tuple[float, CurriculumChunk]] = []
        norm_subj = _norm(subject) if subject else None

        for chunk in chunks:
            if grade is not None and chunk.grade not in {None, grade}:
                continue
            if norm_subj and _norm(chunk.subject) != norm_subj:
                continue

            score = 0.0
            # Target fields to check
            topic_str = _norm(f"{chunk.topic} {chunk.subtopic or ''} {chunk.chapter or ''}")
            tags_str = " ".join(_norm(t) for t in chunk.tags)
            text_str = _norm(chunk.text)
            formulas_str = ""
            for f in chunk.formulas:
                if isinstance(f, str):
                    formulas_str += " " + _norm(f)
                elif hasattr(f, "expression"):
                    formulas_str += " " + _norm(f.expression)

            khmer_terms_str = ""
            for en_term, km_term in chunk.khmer_terms.items():
                khmer_terms_str += f" {_norm(en_term)} {_norm(km_term)}"

            examples_str = ""
            for ex in chunk.examples:
                if hasattr(ex, "problem"):
                    examples_str += f" {_norm(ex.problem)} {_norm(ex.answer or '')}"
                elif isinstance(ex, dict):
                    examples_str += f" {_norm(str(ex.get('problem', '')))} {_norm(str(ex.get('answer', '')))}"

            exercises_str = ""
            for prac in chunk.exercises:
                if hasattr(prac, "prompt"):
                    exercises_str += f" {_norm(prac.prompt)} {_norm(prac.answer or '')}"
                elif isinstance(prac, dict):
                    exercises_str += f" {_norm(str(prac.get('prompt', '')))} {_norm(str(prac.get('answer', '')))}"

            solution_steps_str = " ".join(_norm(s) for s in chunk.solution_steps)

            # Direct whole topic match
            if _norm(chunk.topic) in query_norm:
                score += 10.0
            if chunk.subtopic and _norm(chunk.subtopic) in query_norm:
                score += 8.0

            # Direct formula match if formula is non-trivial
            for f in chunk.formulas:
                expr = f if isinstance(f, str) else getattr(f, "expression", "") if hasattr(f, "expression") else f.get("expression", "") if isinstance(f, dict) else ""
                norm_expr = _norm(expr)
                if norm_expr and len(norm_expr) >= 3 and (norm_expr in query_norm or query_norm in norm_expr):
                    score += 6.0

            # Direct Khmer term matching in query (handles continuous unsegmented Khmer script)
            for en_term, km_term in chunk.khmer_terms.items():
                km_norm = _norm(km_term)
                if km_norm and len(km_norm) >= 2 and km_norm in query_norm:
                    score += 5.0

            # Token matching
            for token in query_tokens:
                if token in topic_str:
                    score += 5.0
                elif token in tags_str:
                    score += 4.0
                elif token in formulas_str:
                    score += 4.0
                elif token in examples_str:
                    score += 4.5
                elif token in exercises_str:
                    score += 4.0
                elif token in solution_steps_str:
                    score += 3.5
                elif token in khmer_terms_str:
                    score += 4.0
                elif token in text_str:
                    score += 1.5

            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda item: (-item[0], item[1].id))
        return scored[:limit]


@lru_cache(maxsize=1)
def get_default_curriculum_store() -> CurriculumStore:
    return CurriculumStore()


def _load_jsonl_chunks(data_dir: Path) -> Iterable[CurriculumChunk]:
    if not data_dir.exists():
        return []
    chunks: List[CurriculumChunk] = []
    for path in sorted(data_dir.glob("*.jsonl")):
        if path.name == "admin-published.jsonl":
            continue
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
