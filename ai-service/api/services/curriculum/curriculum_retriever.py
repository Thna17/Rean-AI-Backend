from __future__ import annotations

import re
from typing import Iterable, Optional

from api.models.curriculum import (
    CurriculumChunk,
    CurriculumFormula,
    CurriculumMisconception,
    CurriculumRetrievalRequest,
    CurriculumRetrievalResult,
)
from api.services.curriculum.curriculum_store import (
    CurriculumStore,
    get_default_curriculum_store,
)


PROBLEM_TYPE_TOPIC_HINTS = {
    "linear_equation_one_variable": [
        "linear equations",
        "one-variable linear equations",
        "equation",
        "algebra",
    ],
    "line_through_two_points": [
        "slope",
        "equation of a line",
        "line through two points",
        "coordinate geometry",
    ],
    "slope_from_two_points": ["slope", "slope from two points"],
    "quadratic_equation": [
        "quadratic functions",
        "quadratic equations",
        "factoring",
        "roots",
    ],
    "arithmetic_expression": ["arithmetic", "order of operations"],
    "simple_percentage_word_problem": ["percentages", "percentage", "percent"],
    "function_domain": ["functions", "domain", "domain and range"],
    "function_range": ["functions", "range", "domain and range"],
    "function_transformation": ["advanced functions", "transformations", "functions"],
}


def retrieve_curriculum_context(
    request: CurriculumRetrievalRequest,
    *,
    store: Optional[CurriculumStore] = None,
) -> CurriculumRetrievalResult:
    active_store = store or get_default_curriculum_store()
    candidates = active_store.query(
        grade=request.grade,
        subject=request.subject,
        topic=request.topic,
        problem_type=request.problem_type,
        language=request.language,
    )
    if request.problem_type and not any(
        request.problem_type in chunk.problem_types for chunk in candidates
    ):
        candidates = _merge_candidates(
            candidates,
            active_store.query(
                subject=request.subject,
                problem_type=request.problem_type,
                language=request.language,
            ),
        )
    scored = [
        (_score_chunk(chunk, request), chunk)
        for chunk in candidates
    ]
    scored = [(score, chunk) for score, chunk in scored if score > 0]
    scored.sort(key=lambda item: (-item[0], item[1].id))
    selected = [chunk for _, chunk in scored[: request.max_results]]
    confidence = min(1.0, scored[0][0] / 10.0) if scored else 0.0
    return CurriculumRetrievalResult(
        chunks=selected,
        formulas=_unique_flatten(_formula_texts(chunk.formulas) for chunk in selected),
        prerequisites=_unique_flatten(chunk.prerequisites for chunk in selected),
        common_misconceptions=_unique_flatten(
            _misconception_texts(chunk.common_misconceptions) for chunk in selected
        ),
        teaching_sequence=_unique_flatten(chunk.teaching_sequence for chunk in selected),
        khmer_terms=_merge_khmer_terms(selected),
        curriculum_chunk_ids=[chunk.id for chunk in selected],
        curriculum_sources=[
            {
                "chunk_id": chunk.id,
                "source": chunk.source.model_dump(mode="json"),
                "grade": chunk.grade,
                "subject": chunk.subject,
                "topic": chunk.topic,
                "subtopic": chunk.subtopic,
            }
            for chunk in selected
        ],
        confidence=confidence,
        metadata={
            "retriever": "visual_tutor_curriculum_retriever_v1",
            "candidate_count": len(candidates),
            "selected_count": len(selected),
            "ranking": {
                "grade": "exact_match_preferred",
                "subject": "exact_match_required_by_store_when_provided",
                "topic": "topic_subtopic_chapter_tag_match",
                "problem_type": "mapped_topic_hints_plus_direct_problem_type",
                "message": "keyword_overlap",
                "language": "requested_language_preferred_with_english_fallback",
            },
            "selected_scores": [
                {"chunk_id": chunk.id, "score": round(float(score), 4)}
                for score, chunk in scored[: request.max_results]
            ],
            "problem_type_topic_hints": PROBLEM_TYPE_TOPIC_HINTS.get(
                request.problem_type or "",
                [],
            ),
        },
    )


def _merge_candidates(
    primary: list[CurriculumChunk],
    fallback: list[CurriculumChunk],
) -> list[CurriculumChunk]:
    seen = {chunk.id for chunk in primary}
    merged = list(primary)
    for chunk in fallback:
        if chunk.id not in seen:
            merged.append(chunk)
            seen.add(chunk.id)
    return merged


def curriculum_metadata(result: CurriculumRetrievalResult) -> dict:
    safe_context = [
        {
            "id": chunk.id,
            "grade": chunk.grade,
            "subject": chunk.subject,
            "topic": chunk.topic,
            "subtopic": chunk.subtopic,
            "content_type": chunk.content_type,
            "text": chunk.text,
            "formulas": [
                _model_or_value_to_json(item) for item in chunk.formulas
            ],
            "concepts": [
                concept.model_dump(mode="json") for concept in chunk.concepts
            ],
            "prerequisites": chunk.prerequisites,
            "common_misconceptions": [
                _model_or_value_to_json(item)
                for item in chunk.common_misconceptions
            ],
            "teaching_sequence": chunk.teaching_sequence,
            "khmer_terms": chunk.khmer_terms,
            "source": chunk.source.model_dump(mode="json"),
        }
        for chunk in result.chunks
    ]
    return {
        "curriculum_context": safe_context,
        "curriculum_chunk_ids": result.curriculum_chunk_ids,
        "curriculum_confidence": result.confidence,
        "curriculum_sources": result.curriculum_sources,
        "prerequisites": result.prerequisites,
        "formulas": result.formulas,
        "common_misconceptions": result.common_misconceptions,
        "teaching_sequence": result.teaching_sequence,
        "khmer_terms": result.khmer_terms,
        "curriculum_retriever": result.metadata,
    }


def _score_chunk(chunk: CurriculumChunk, request: CurriculumRetrievalRequest) -> float:
    score = 0.0
    if request.grade is not None and chunk.grade == request.grade:
        score += 2.0
    elif request.grade is None:
        score += 0.5

    if _norm(chunk.subject) == _norm(request.subject):
        score += 2.0

    if request.topic and _topic_matches(chunk, request.topic):
        score += 2.5

    if request.problem_type and request.problem_type in chunk.problem_types:
        score += 4.0

    hints = PROBLEM_TYPE_TOPIC_HINTS.get(request.problem_type or "", [])
    haystack = _chunk_search_text(chunk)
    for hint in hints:
        if _norm(hint) in haystack:
            score += 1.0

    message_tokens = _tokens(request.message)
    if message_tokens:
        overlap = message_tokens & _tokens(haystack)
        score += min(2.5, len(overlap) * 0.35)

    if request.language and chunk.language == request.language:
        score += 0.5

    return score


def _unique_flatten(values: Iterable[Iterable[str]]) -> list[str]:
    seen = set()
    output = []
    for group in values:
        for value in group:
            normalized = value.strip()
            if normalized and normalized not in seen:
                seen.add(normalized)
                output.append(normalized)
    return output


def _formula_texts(values: Iterable[str | CurriculumFormula]) -> list[str]:
    output: list[str] = []
    for value in values:
        if isinstance(value, CurriculumFormula):
            output.append(value.expression)
        else:
            output.append(str(value))
    return output


def _misconception_texts(
    values: Iterable[str | CurriculumMisconception],
) -> list[str]:
    output: list[str] = []
    for value in values:
        if isinstance(value, CurriculumMisconception):
            output.append(value.text)
        else:
            output.append(str(value))
    return output


def _model_or_value_to_json(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return value


def _merge_khmer_terms(chunks: list[CurriculumChunk]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for chunk in chunks:
        merged.update(chunk.khmer_terms)
    return merged


def _topic_matches(chunk: CurriculumChunk, topic: str) -> bool:
    topic_norm = _norm(topic)
    return any(
        _is_topic_match(topic_norm, candidate)
        for candidate in [
            _norm(chunk.topic),
            _norm(chunk.subtopic or ""),
            _norm(chunk.chapter or ""),
            *[_norm(tag) for tag in chunk.tags],
        ]
        if candidate
    )


def _is_topic_match(topic_norm: str, candidate_norm: str) -> bool:
    if topic_norm == candidate_norm:
        return True
    if len(candidate_norm) <= 4:
        return candidate_norm in topic_norm.split()
    return topic_norm in candidate_norm or candidate_norm in topic_norm


def _chunk_search_text(chunk: CurriculumChunk) -> str:
    return _norm(
        " ".join(
            [
                chunk.id,
                chunk.subject,
                chunk.chapter or "",
                chunk.topic,
                chunk.subtopic or "",
                chunk.text,
                " ".join(chunk.problem_types),
                " ".join(chunk.tags),
                " ".join(_formula_texts(chunk.formulas)),
                " ".join(example.problem for example in chunk.examples),
                " ".join(exercise.prompt for exercise in chunk.exercises),
                " ".join(chunk.prerequisites),
                " ".join(_misconception_texts(chunk.common_misconceptions)),
            ]
        )
    )


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[\w\u1780-\u17ff]+", _norm(text))
        if len(token) > 2
    }


def _norm(value: str) -> str:
    return value.strip().lower().replace("_", " ")
