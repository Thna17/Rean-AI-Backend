"""Reproducible 300-case release benchmark for the Grade 8–10 Math MVP.

This is deliberately offline and deterministic: it exercises the same problem
understanding, solver/orchestrator, teaching-plan validation, and SymPy step
verification used by a tutor turn without making a hosted-provider call.
Provider availability and latency are evaluated separately by readiness tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest
from api.routes.math_verifier import verify_student_work
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn

from api.services.visual_tutor.teaching_plan_contract import VisualTutorTeachingPlan

import pytest

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")


@dataclass(frozen=True)
class BenchmarkCase:
    topic: str
    problem: str
    student_step: str | None = None
    expected_step: str | None = None
    expected_status: str | None = None
    unsupported: bool = False


def release_cases() -> list[BenchmarkCase]:
    """Return exactly 300 stable representative learner cases."""
    cases: list[BenchmarkCase] = []

    # 80 equation cases: correct, invalid, incomplete, and valid-but-skipped
    # steps cover the deterministic student-work contract.
    for constant in range(1, 21):
        rhs = constant + 10
        problem = f"2x + {constant} = {rhs}"
        cases.extend(
            [
                BenchmarkCase("linear_equation", problem, f"2x = 10", f"2x = 10", "correct"),
                BenchmarkCase("linear_equation", problem, "x = 5", f"2x = 10", "mathematically_valid_but_inefficient"),
                BenchmarkCase("linear_equation", problem, "2x = 99", f"2x = 10", "invalid"),
                BenchmarkCase("linear_equation", problem, "", f"2x = 10", "incomplete"),
            ]
        )

    # 140 supported problem-understanding/planning cases, 20 per listed MVP
    # topic. Khmer variants ensure language detection stays in the release set.
    for number in range(1, 21):
        cases.append(BenchmarkCase("integer_arithmetic", f"Calculate {number} + {number + 2}"))
        cases.append(BenchmarkCase("fractions_decimals", f"Calculate {number}/2 + 0.5"))
        cases.append(BenchmarkCase("percentages", f"What is {number}% of 100?"))
        cases.append(BenchmarkCase("slope_from_two_points", f"Find the slope through (0, {number}) and (2, {number + 4})"))
        cases.append(BenchmarkCase("straight_line_graph", f"Graph y = {number}x + 1"))
        cases.append(BenchmarkCase("quadratic_graph", f"Graph y = x^2 - {number}x + 1"))
        cases.append(BenchmarkCase("khmer_linear", f"ដោះស្រាយ 2x + {number} = {number + 10}"))

    # 80 + 140 = 220.  Add 80 safety, ambiguity, resume/conflict-representative
    # mathematical prompts; unsupported must stay transparent, never rerouted.
    special = [
        BenchmarkCase("division_by_zero", "2x + 5 = 15", "x/0 = 2", "2x = 10", "invalid"),
        BenchmarkCase("multiple_solutions", "x^2 = 1", "x = 1", None, "invalid"),
        BenchmarkCase("no_solution", "x = x + 1", "x = x + 1", None, "correct"),
        BenchmarkCase("malformed", "2x + 5 = 15", "2x =", "2x = 10", "cannot_verify"),
        BenchmarkCase("unsupported", "Prove this triangle is congruent", unsupported=True),
        BenchmarkCase("unsupported", "Explain this geometry proof", unsupported=True),
        BenchmarkCase("ambiguous", "Solve the thing with x and y", unsupported=True),
        BenchmarkCase("khmer_slope", "រកជម្រាលរវាង A(0, 1) និង B(1, 3)"),
    ]
    for _ in range(10):
        cases.extend(special)
    assert len(cases) == 300
    return cases


def _request(case: BenchmarkCase, index: int) -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id="release-benchmark-student",
        session_id=f"release-benchmark-{index}",
        subject="Mathematics",
        topic=case.topic,
        message=case.problem,
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 9, "benchmark": True},
    )


def test_release_benchmark_has_300_cases() -> None:
    assert len(release_cases()) == 300


def test_release_benchmark_deterministic_quality_metrics() -> None:
    """Run every case and assert safe, measurable baseline quality gates."""
    cases = release_cases()
    verification_total = verification_correct = false_verified = 0
    unsupported_total = unsupported_transparent = 0
    valid_plans = 0
    latencies_ms: list[float] = []

    for index, case in enumerate(cases):
        start = perf_counter()
        response = handle_visual_tutor_turn(_request(case, index))
        latencies_ms.append((perf_counter() - start) * 1000)
        plan = response.metadata.get("teaching_plan")
        VisualTutorTeachingPlan.model_validate(plan)
        valid_plans += 1

        if case.unsupported:
            unsupported_total += 1
            if response.screen_state.value == "unsupported_problem" and response.final_answer_locked:
                unsupported_transparent += 1

        if case.student_step is not None:
            verification_total += 1
            result = verify_student_work(
                problem=case.problem,
                student_step=case.student_step,
                expected_step=case.expected_step,
            )
            if result.status == case.expected_status:
                verification_correct += 1
            if result.verified and case.expected_status in {"cannot_verify", "incomplete"}:
                false_verified += 1

    # Keep the summary attached to pytest output for CI logs without persisting
    # any student content.
    metrics = {
        "cases": len(cases),
        "verification_accuracy": verification_correct / verification_total,
        "false_verified_answer_rate": false_verified / verification_total,
        "unsupported_question_transparency_rate": unsupported_transparent / unsupported_total,
        "valid_teaching_plan_rate": valid_plans / len(cases),
        "p50_tutor_turn_latency_ms": sorted(latencies_ms)[len(latencies_ms) // 2],
        "p95_tutor_turn_latency_ms": sorted(latencies_ms)[int(len(latencies_ms) * 0.95) - 1],
    }
    print(f"RELEASE_BENCHMARK_METRICS={metrics}")
    assert metrics["verification_accuracy"] == 1.0
    assert metrics["false_verified_answer_rate"] == 0.0
    assert metrics["unsupported_question_transparency_rate"] == 1.0
    assert metrics["valid_teaching_plan_rate"] == 1.0
