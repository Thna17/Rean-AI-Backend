"""Validated curriculum and visual-problem contracts for Cambodia STEM lessons."""

from __future__ import annotations

from collections import deque
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Subject = Literal["math", "physics", "chemistry"]
Grade = Literal[10, 11, 12]


class Concept(BaseModel):
    """A reusable skill or idea addressed by one or more curriculum topics."""

    concept_id: str = Field(pattern=r"^[a-z0-9_]+$")
    name: str
    name_khmer: str
    description: str
    category: str
    difficulty_level: int = Field(ge=1, le=5)


class LearningOutcome(BaseModel):
    """A locally traceable outcome; ``code`` is verified against the source map."""

    code: str = Field(min_length=3)
    description: str
    description_khmer: str
    grade: Grade
    subject: Subject
    source: str = (
        "MoEYS upper-secondary curriculum (2006); local mapping pending review"
    )


class Topic(BaseModel):
    """A teachable topic and its prerequisite links within one subject/grade."""

    topic_id: str = Field(pattern=r"^[a-z0-9_]+$")
    subject: Subject
    grade: Grade
    unit_name: str
    name: str
    name_khmer: str
    concepts: list[str] = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    learning_outcomes: list[LearningOutcome] = Field(min_length=1)
    example_problems: list[str] = Field(min_length=3, max_length=5)

    @model_validator(mode="after")
    def validate_outcomes_match_topic(self) -> "Topic":
        if any(
            outcome.grade != self.grade or outcome.subject != self.subject
            for outcome in self.learning_outcomes
        ):
            raise ValueError("Learning outcomes must match the topic subject and grade")
        return self


class CurriculumUnit(BaseModel):
    unit_id: str = Field(pattern=r"^[a-z0-9_]+$")
    subject: Subject
    grade: Grade
    name: str
    name_khmer: str
    weeks: int = Field(ge=1, le=52)
    topics: list[Topic] = Field(min_length=1)


class CurriculumGraph(BaseModel):
    """A validated directed acyclic prerequisite graph for one subject/grade."""

    subject: Subject
    grade: Grade
    topics: dict[str, Topic]
    edges: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph(self) -> "CurriculumGraph":
        if set(self.topics) != set(self.edges):
            raise ValueError("Every topic must have an edges entry")
        for topic_id, prerequisites in self.edges.items():
            if topic_id not in self.topics or any(
                item not in self.topics for item in prerequisites
            ):
                raise ValueError("Prerequisite references an unknown topic")
            topic = self.topics[topic_id]
            if topic.subject != self.subject or topic.grade != self.grade:
                raise ValueError("Topics must match the graph subject and grade")
            if prerequisites != topic.prerequisites:
                raise ValueError("Graph edges must match topic prerequisites")
            if topic_id in prerequisites:
                raise ValueError("A topic cannot depend on itself")
        self._assert_acyclic()
        return self

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise ValueError("Curriculum prerequisites must form a DAG")
            if node not in visited:
                visiting.add(node)
                for dependency in self.edges[node]:
                    visit(dependency)
                visiting.remove(node)
                visited.add(node)

        for topic_id in self.topics:
            visit(topic_id)

    def get_prerequisites(self, topic_id: str) -> list[Topic]:
        return [self.topics[item] for item in self.edges.get(topic_id, [])]

    def get_dependents(self, topic_id: str) -> list[Topic]:
        return [
            self.topics[item]
            for item, dependencies in self.edges.items()
            if topic_id in dependencies
        ]

    def get_path(self, start_topic_id: str, end_topic_id: str) -> list[Topic]:
        """Return a shortest prerequisite-to-dependent path, or an empty list."""
        if start_topic_id not in self.topics or end_topic_id not in self.topics:
            return []
        reverse = {
            item: [node for node, deps in self.edges.items() if item in deps]
            for item in self.topics
        }
        queue: deque[list[str]] = deque([[start_topic_id]])
        seen = {start_topic_id}
        while queue:
            path = queue.popleft()
            node = path[-1]
            if node == end_topic_id:
                return [self.topics[item] for item in path]
            for next_node in reverse[node]:
                if next_node not in seen:
                    seen.add(next_node)
                    queue.append([*path, next_node])
        return []


class RichProblem(BaseModel):
    """A curriculum-aligned problem whose solution is taught visually."""

    problem_id: str = Field(pattern=r"^[a-z0-9_]+$")
    subject: Subject
    grade: Grade
    unit: str
    topic_id: str
    problem_text: str
    problem_text_khmer: str
    problem_type: str
    visualizations_needed: list[str] = Field(min_length=1)
    concepts: list[str] = Field(min_length=1)
    prerequisites: list[str] = Field(default_factory=list)
    teaching_approach: Literal["socratic", "discovery", "guided"] = "socratic"
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualizationStep(BaseModel):
    step_id: str
    visualization_type: str
    content: dict[str, Any]
    animation_type: str | None = None
    duration_ms: int = Field(default=1000, ge=0, le=30_000)
    student_question: str
    student_question_khmer: str
    expected_response_type: Literal[
        "multiple_choice", "numeric", "text", "draw", "handwriting"
    ]
    on_correct: str = "next_step"
    on_incorrect: str = "reteach"


class VisualizationPlan(BaseModel):
    problem_id: str
    visualization_steps: list[VisualizationStep] = Field(min_length=1)
    animations: list[str] = Field(default_factory=list)
    student_questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
