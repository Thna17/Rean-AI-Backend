"""Reusable Socratic placeholder behavior; replace with domain logic by phase."""
from __future__ import annotations
import logging
from typing import Any
from api.models.curriculum_cambodia import RichProblem, VisualizationPlan, VisualizationStep
from api.models.teaching_step import DifficultyLevel, EvaluationResult, InteractionConfig, StepType, Subject, TeachingStep, VisualizationConfig, VisualizationType
from api.services.subject_experts.base_expert import SubjectExpert

class StubSubjectExpert(SubjectExpert):
    """Deterministic, cached Phase 0 implementation of the common contract."""
    visual_type: str = "diagram"
    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._cache: dict[str, VisualizationPlan] = {}

    async def analyze_problem(self, problem: RichProblem) -> dict[str, Any]:
        self.validate_problem(problem, self.subject)
        return {"problem_type": problem.problem_type, "key_elements": problem.concepts, "relevant_concepts": problem.concepts, "solution_approach": problem.teaching_approach}

    async def create_visualization_plan(self, problem: RichProblem, teaching_approach: str = "socratic") -> VisualizationPlan:
        self.validate_problem(problem, self.subject)
        key = f"{self.subject}:{problem.problem_id}:{teaching_approach}"
        if key not in self._cache:
            question = "What do you notice in this representation?"
            self._cache[key] = VisualizationPlan(problem_id=problem.problem_id, visualization_steps=[VisualizationStep(step_id=f"{problem.problem_id}_observe", visualization_type=self.visual_type, content={"problem": problem.problem_text, "concepts": problem.concepts}, animation_type="fade_in", student_question=question, student_question_khmer="តើអ្នកសង្កេតឃើញអ្វីក្នុងរូបភាពនេះ?", expected_response_type="text")], animations=["fade_in"], student_questions=[question], metadata={"subject": self.subject, "renderer": "RichMediaCanvas", "teaching_approach": teaching_approach})
        return self._cache[key].model_copy(deep=True)

    async def evaluate_student_response(self, student_answer: str, step_id: str, expected_answer: str | None = None, validation_strategy: str | None = None) -> EvaluationResult:
        if not student_answer.strip(): raise ValueError("Student answer must not be empty")
        correct = expected_answer is None or self.normalize_answer(student_answer) == self.normalize_answer(expected_answer)
        return EvaluationResult(is_correct=correct, condition="correct" if correct else "incorrect", confidence=1.0 if correct else 0.8, feedback_message="Good thinking—let's build on that." if correct else "Good attempt. Let's examine the representation again.", should_offer_hint=not correct, hint_text=None if correct else await self.provide_hint(step_id), evaluation_time_ms=0, model_used="phase_0_rules")

    async def provide_hint(self, step_id: str, hint_level: int = 1) -> str:
        if hint_level not in {1, 2, 3}: raise ValueError("hint_level must be 1, 2, or 3")
        return ["Look carefully at what is given.", "Identify the relationship shown in the visual.", "Use that relationship for the next small step."][hint_level - 1]

    async def detect_misconception(self, student_work: str, correct_answer: str, step_id: str) -> dict[str, str] | None:
        if self.normalize_answer(student_work) == self.normalize_answer(correct_answer): return None
        return {"misconception_type": "needs_diagnostic", "description": "The response does not yet match the expected relationship.", "remediation": "Use a simpler visual representation and ask one focused question."}

    async def generate_reteach_step(self, original_step_id: str, misconception: str | None = None) -> TeachingStep:
        visualization_type = {"math": VisualizationType.NUMBER_LINE, "physics": VisualizationType.VECTOR, "chemistry": VisualizationType.MOLECULE}[self.subject]
        return TeachingStep(id=f"{original_step_id}_reteach", step_number=1, type=StepType.QUESTION, title="Try a different view", description="Let's use a simpler visual and identify one relationship before continuing.", visualizations=[VisualizationConfig(type=visualization_type, data={"renderer": "RichMediaCanvas", "mode": "reteach"})], interaction=InteractionConfig(question_text="What is the first relationship you can identify?", hint_text=await self.provide_hint(original_step_id)), learning_objective="Identify the key relationship", difficulty=DifficultyLevel.UNDERSTAND, subject=Subject(self.subject if self.subject != "math" else "mathematics"), metadata={"misconception": misconception})
