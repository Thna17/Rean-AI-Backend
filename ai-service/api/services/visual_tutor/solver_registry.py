from __future__ import annotations

from typing import Iterable, Optional

from api.models.visual_tutor import VisualTutorProblemUnderstandingResult
from api.services.visual_tutor.solvers import (
    ArithmeticExpressionSolver,
    LineThroughPointsSolver,
    LinearEquationSolver,
    QuadraticEquationBasicSolver,
    SimplePercentageWordProblemSolver,
    SlopeFromTwoPointsSolver,
    VisualTutorSolver,
)


class VisualTutorSolverRegistry:
    def __init__(self, solvers: Iterable[VisualTutorSolver] | None = None) -> None:
        self._solvers = list(
            solvers
            or [
                LineThroughPointsSolver(),
                SlopeFromTwoPointsSolver(),
                LinearEquationSolver(),
                QuadraticEquationBasicSolver(),
                ArithmeticExpressionSolver(),
                SimplePercentageWordProblemSolver(),
            ]
        )

    def get_solver(
        self, understanding: VisualTutorProblemUnderstandingResult
    ) -> Optional[VisualTutorSolver]:
        for solver in self._solvers:
            if solver.can_handle(understanding):
                return solver
        return None


DEFAULT_VISUAL_TUTOR_SOLVER_REGISTRY = VisualTutorSolverRegistry()
