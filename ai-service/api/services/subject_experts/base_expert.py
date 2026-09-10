"""Shared contracts and safe utilities for Cambodia STEM subject experts."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from api.models.curriculum_cambodia import RichProblem, VisualizationPlan
from api.models.teaching_step import EvaluationResult, TeachingStep


class SubjectExpert(ABC):
    """Abstract, Socratic expert contract used by Math, Physics, and Chemistry."""

    subject: str

    @abstractmethod
    async def analyze_problem(self, problem: RichProblem) -> dict[str, Any]: ...

    @abstractmethod
    async def create_visualization_plan(self, problem: RichProblem, teaching_approach: str = "socratic") -> VisualizationPlan: ...

    @abstractmethod
    async def evaluate_student_response(self, student_answer: str, step_id: str, expected_answer: str | None = None, validation_strategy: str | None = None) -> EvaluationResult: ...

    @abstractmethod
    async def provide_hint(self, step_id: str, hint_level: int = 1) -> str: ...

    @abstractmethod
    async def detect_misconception(self, student_work: str, correct_answer: str, step_id: str) -> dict[str, str] | None: ...

    @abstractmethod
    async def generate_reteach_step(self, original_step_id: str, misconception: str | None = None) -> TeachingStep: ...

    @staticmethod
    def validate_problem(problem: RichProblem, expected_subject: str) -> None:
        if problem.subject != expected_subject:
            raise ValueError(f"{expected_subject} expert cannot handle {problem.subject} problems")
        if not problem.problem_text.strip():
            raise ValueError("Problem text must not be empty")

    @staticmethod
    def normalize_answer(value: str) -> str:
        return "".join(value.casefold().split())
