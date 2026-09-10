from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


QuizQuestionType = Literal["multiple_choice", "short_answer"]


class QuizGenerationRequest(BaseModel):
    user_id: str | None = None
    grade: int | None = Field(default=None, ge=1, le=12)
    subject: str = Field(default="Mathematics", min_length=1)
    topic: str = Field(default="Linear Equations", min_length=1)
    problem_type: str | None = None
    difficulty: str = Field(default="easy", min_length=1)
    language: str = Field(default="en", min_length=1)
    use_llm: bool = False
    tutor_session_id: str | None = Field(default=None, max_length=256)
    skill_tags: list[str] = Field(default_factory=list, max_length=12)
    learning_goals: list[str] = Field(default_factory=list, max_length=12)
    misconceptions: list[str] = Field(default_factory=list, max_length=12)
    hint_count: int = Field(default=0, ge=0, le=100)
    stuck_count: int = Field(default=0, ge=0, le=100)
    verification_results: list[str] = Field(default_factory=list, max_length=30)
    prior_mastery: float | None = Field(default=None, ge=0, le=1)
    prior_quiz_score: int | None = Field(default=None, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuizChoice(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)


class QuizQuestion(BaseModel):
    id: str = Field(min_length=1)
    type: QuizQuestionType = "multiple_choice"
    question_text: str = Field(min_length=1)
    choices: list[QuizChoice] = Field(default_factory=list)
    expected_answer: str | None = None
    correct_answer: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    problem_type: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_answer_shape(self) -> "QuizQuestion":
        if self.type == "multiple_choice":
            if len(self.choices) < 2:
                raise ValueError("multiple_choice questions require at least two choices")
            choice_ids = {choice.id for choice in self.choices}
            choice_texts = {choice.text for choice in self.choices}
            if self.correct_answer not in choice_ids and self.correct_answer not in choice_texts:
                raise ValueError("correct_answer must match a choice id or choice text")
        if self.type == "short_answer" and not self.expected_answer:
            raise ValueError("short_answer questions require expected_answer")
        return self


class QuizGenerationResponse(BaseModel):
    quiz_id: str = Field(min_length=1)
    subject: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    problem_type: str = Field(min_length=1)
    difficulty: str = Field(min_length=1)
    questions: list[QuizQuestion] = Field(min_length=3, max_length=5)
    verified: bool
    cache_hit: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
