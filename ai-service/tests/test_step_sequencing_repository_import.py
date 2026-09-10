"""Regression coverage for the step-sequencing repository import path."""

from pathlib import Path

from api.repositories.problem_repository import ProblemRepository


def test_step_sequencing_uses_repository_problem_repository_import() -> None:
    """The route must use the existing repository package, not a service shim."""
    route_source = (
        Path(__file__).parents[1] / "api" / "routes" / "step_sequencing.py"
    ).read_text(encoding="utf-8")

    assert ProblemRepository.__module__ == "api.repositories.problem_repository"
    assert (
        "from api.repositories.problem_repository import ProblemRepository"
        in route_source
    )
    assert "from api.services.problem_repository import ProblemRepository" not in route_source
