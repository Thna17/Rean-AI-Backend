from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CurriculumSource(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(..., min_length=1)
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    pdf_path: Optional[str] = None
    page: Optional[int] = Field(default=None, ge=1)
    page_start: Optional[int] = Field(default=None, ge=1)
    page_end: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    section: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_page_range(self) -> "CurriculumSource":
        if (
            self.page_start is not None
            and self.page_end is not None
            and self.page_end < self.page_start
        ):
            raise ValueError("page_end must be greater than or equal to page_start")
        return self


class CurriculumConcept(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    subject: str = Field(..., min_length=1)
    chapter: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    content_type: str = Field(default="concept", min_length=1)
    text: str = Field(..., min_length=1)
    prerequisites: List[str] = Field(default_factory=list)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    difficulty: Optional[str] = None
    source: Optional[CurriculumSource] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CurriculumFormula(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    subject: Optional[str] = None
    chapter: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    content_type: str = Field(default="formula", min_length=1)
    text: Optional[str] = None
    expression: str = Field(..., min_length=1)
    variables: Dict[str, str] = Field(default_factory=dict)
    solution_steps: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    difficulty: Optional[str] = None
    source: Optional[CurriculumSource] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CurriculumExample(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    subject: Optional[str] = None
    chapter: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    content_type: str = Field(default="example", min_length=1)
    text: Optional[str] = None
    problem: str = Field(..., min_length=1)
    answer: Optional[str] = None
    solution_steps: List[str] = Field(default_factory=list)
    formulas: List[Union[str, CurriculumFormula]] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    common_misconceptions: List[str] = Field(default_factory=list)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    difficulty: Optional[str] = None
    source: Optional[CurriculumSource] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CurriculumExercise(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    subject: Optional[str] = None
    chapter: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    content_type: str = Field(default="exercise", min_length=1)
    text: Optional[str] = None
    prompt: str = Field(..., min_length=1)
    answer: Optional[str] = None
    solution_steps: List[str] = Field(default_factory=list)
    hints: List[str] = Field(default_factory=list)
    formulas: List[Union[str, CurriculumFormula]] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    common_misconceptions: List[str] = Field(default_factory=list)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    difficulty: Optional[str] = None
    source: Optional[CurriculumSource] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CurriculumMisconception(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    subject: Optional[str] = None
    chapter: Optional[str] = None
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    content_type: str = Field(default="misconception", min_length=1)
    text: str = Field(..., min_length=1)
    correction: Optional[str] = None
    diagnostic_cues: List[str] = Field(default_factory=list)
    solution_steps: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    difficulty: Optional[str] = None
    source: Optional[CurriculumSource] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CurriculumReviewStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ReviewedKhmerGlossaryTerm(BaseModel):
    """A Khmer STEM term that has passed curriculum review.

    Raw ``khmer_terms`` on an authoring chunk are deliberately not accepted by
    this contract.  A term is student-facing only after its source and review
    information are present.
    """

    model_config = ConfigDict(extra="forbid")

    english: str = Field(min_length=1, max_length=160)
    khmer: str = Field(min_length=1, max_length=240)
    glossary_version: str = Field(min_length=1, max_length=80)
    source_id: str = Field(min_length=1, max_length=160)
    reviewer_status: CurriculumReviewStatus
    curriculum_version: str = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def must_be_approved(self) -> "ReviewedKhmerGlossaryTerm":
        if self.reviewer_status != CurriculumReviewStatus.APPROVED:
            raise ValueError("only approved Khmer glossary terms may be displayed")
        return self


class ReviewedKhmerGlossarySet(BaseModel):
    """Reviewed terminology for one exact Cambodian curriculum lesson."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    grade: int = Field(ge=10, le=12)
    subject: str = Field(min_length=1)
    lesson: str = Field(min_length=1)
    glossary_version: str = Field(min_length=1)
    curriculum_version: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    reviewer_status: CurriculumReviewStatus
    terms: List[ReviewedKhmerGlossaryTerm] = Field(min_length=1, max_length=80)

    @model_validator(mode="after")
    def must_have_consistent_approved_terms(self) -> "ReviewedKhmerGlossarySet":
        if self.reviewer_status != CurriculumReviewStatus.APPROVED:
            raise ValueError("only approved Khmer glossary sets may be displayed")
        if any(
            term.glossary_version != self.glossary_version
            or term.curriculum_version != self.curriculum_version
            for term in self.terms
        ):
            raise ValueError("glossary terms must match their set version")
        return self


class ReviewedLessonChunk(BaseModel):
    """Strict production lesson record; authoring drafts stay outside this contract."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    grade: int = Field(ge=10, le=12)
    subject: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    lesson: str = Field(min_length=1)
    curriculum_version: str = Field(min_length=1)
    learning_objectives: List[str] = Field(min_length=1, max_length=8)
    formulas: List[CurriculumFormula] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    dependent_concepts: List[str] = Field(default_factory=list)
    common_misconceptions: List[CurriculumMisconception] = Field(default_factory=list)
    visual_representations: List[str] = Field(min_length=1, max_length=8)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    source_ids: List[str] = Field(min_length=1, max_length=12)
    review_status: CurriculumReviewStatus

    @model_validator(mode="after")
    def approved_requires_complete_evidence(self) -> "ReviewedLessonChunk":
        if self.review_status != CurriculumReviewStatus.APPROVED:
            raise ValueError("only approved lesson chunks may enter the production store")
        if any(not value.strip() for value in [*self.learning_objectives, *self.source_ids]):
            raise ValueError("reviewed lesson has blank objective or source ID")
        if any(not key.strip() or not value.strip() for key, value in self.khmer_terms.items()):
            raise ValueError("Khmer glossary entries must be approved non-empty values")
        return self


class CurriculumChunk(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str = Field(..., min_length=1)
    grade: Optional[int] = Field(default=None, ge=1, le=12)
    subject: str = Field(..., min_length=1)
    chapter: Optional[str] = None
    topic: str = Field(..., min_length=1)
    subtopic: Optional[str] = None
    problem_types: List[str] = Field(default_factory=list)
    content_type: str = Field(default="concept", min_length=1)
    text: str = Field(..., min_length=1)
    concepts: List[CurriculumConcept] = Field(default_factory=list)
    formulas: List[Union[str, CurriculumFormula]] = Field(default_factory=list)
    examples: List[CurriculumExample] = Field(default_factory=list)
    exercises: List[CurriculumExercise] = Field(default_factory=list)
    solution_steps: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    common_misconceptions: List[Union[str, CurriculumMisconception]] = Field(
        default_factory=list
    )
    teaching_sequence: List[str] = Field(default_factory=list)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    language: str = Field(default="en", min_length=1)
    difficulty: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    source: CurriculumSource
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CurriculumRetrievalRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    grade: Optional[int] = Field(default=None, ge=1, le=12)
    subject: str = Field(default="Mathematics", min_length=1)
    topic: Optional[str] = None
    problem_type: Optional[str] = None
    message: str = ""
    language: Optional[str] = None
    max_results: int = Field(default=5, ge=1, le=20)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CurriculumRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    chunks: List[CurriculumChunk] = Field(default_factory=list)
    formulas: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    common_misconceptions: List[str] = Field(default_factory=list)
    teaching_sequence: List[str] = Field(default_factory=list)
    khmer_terms: Dict[str, str] = Field(default_factory=dict)
    curriculum_chunk_ids: List[str] = Field(default_factory=list)
    curriculum_sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0, le=1)
    metadata: Dict[str, Any] = Field(default_factory=dict)
