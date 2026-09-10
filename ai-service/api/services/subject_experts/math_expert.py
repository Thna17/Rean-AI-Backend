"""Phase 0 mathematics expert contract implementation."""
from __future__ import annotations
import re
from api.models.curriculum_cambodia import RichProblem
from api.services.subject_experts._stub import StubSubjectExpert

class MathExpert(StubSubjectExpert):
    subject = "math"; visual_type = "equation"
    async def equation_parser(self, expression: str) -> dict[str, list[str]]:
        if not expression.strip(): raise ValueError("Expression must not be empty")
        return {"variables": sorted(set(re.findall(r"(?<![A-Za-z])[xyz](?![A-Za-z])", expression))), "numbers": re.findall(r"-?\d+(?:\.\d+)?", expression)}
    async def apply_operation(self, expression: str, operation: str) -> str: return f"{expression} | {operation}"
    async def simplify_expression(self, expression: str) -> str: return " ".join(expression.split())
    async def analyze_problem(self, problem: RichProblem) -> dict[str, object]:
        analysis = await super().analyze_problem(problem); analysis.update(await self.equation_parser(problem.problem_text)); return analysis
