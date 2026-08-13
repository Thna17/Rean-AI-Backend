from __future__ import annotations

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
