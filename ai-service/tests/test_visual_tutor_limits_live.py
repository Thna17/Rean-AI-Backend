"""Live end-to-end sessions for all 10 Grade 12 limits teachable moments.

Runs real student sessions -- submit problem, request hint, submit a
correct step, submit a wrong step, request the final answer -- through
handle_visual_tutor_turn against the real DeepSeek API (no mocked LLM
client). This costs real API calls and is non-deterministic, so it is
skipped by default: set RUN_LIVE_LLM_TESTS=1 to run it.

Correctness here is deliberately loose (a real model's wording varies
turn to turn): each turn must complete without raising and return a
structurally valid response. What's tracked and reported per moment is
response_source (llm_planner vs template_fallback/deterministic_solver)
and any board_contract rejections, written to
tests/.live_llm_report.json for inspection after the run.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
import sympy

RUN_LIVE = os.getenv("RUN_LIVE_LLM_TESTS") == "1"

if RUN_LIVE:
    try:
        from dotenv import load_dotenv

        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.board_contract import validate_board_response
from api.services.visual_tutor.llm_teaching_planner import (
    DeepSeekVisualTutorLLMClient,
    _bad_board_action_count,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn

pytestmark = [
    pytest.mark.live_llm,
    pytest.mark.skipif(
        not RUN_LIVE,
        reason="Live DeepSeek integration test; set RUN_LIVE_LLM_TESTS=1 to run "
        "(costs real API calls, non-deterministic).",
    ),
]

_REPORT_PATH = Path(__file__).resolve().parent / ".live_llm_report.json"

# One representative problem per teachable moment, chosen so
# parse_limit_of_function/understand_visual_tutor_problem classify it as
# limit_of_function and sympy can compute an exact ground-truth value.
_MOMENTS: list[dict[str, Any]] = [
    {"number": 1, "topic": "finite-at-point", "problem": "Find the limit of f(x) = 2x + 1 as x approaches 3"},
    {"number": 2, "topic": "one-sided-infinite", "problem": "Find the limit of 1/(x - 2) as x approaches 2 from the right"},
    {"number": 3, "topic": "at-infinity", "problem": "Find the limit of (3x + 1)/(x - 2) as x approaches infinity"},
    {"number": 4, "topic": "algebraic-laws", "problem": "Find the limit of (x^2 - 1)/(x - 1) as x approaches 1"},
    {"number": 5, "topic": "composition", "problem": "Find the limit of (x - 1)/(sqrt(x) - 1) as x approaches 1"},
    {"number": 6, "topic": "comparison", "problem": "Find the limit of x^2 - 4 as x approaches 2"},
    {"number": 7, "topic": "indeterminate-forms", "problem": "Find the limit of (sin(x))/x as x approaches 0"},
    {"number": 8, "topic": "trigonometric", "problem": "Find the limit of sin(x) as x approaches 0"},
    {"number": 9, "topic": "exponential", "problem": "Find the limit of exp(x) as x approaches 0"},
    {"number": 10, "topic": "logarithmic", "problem": "Find the limit of log(x) as x approaches 1"},
]


def _ground_truth_step_texts(problem: dict[str, Any]) -> tuple[str, str]:
    """(correct_step_text, wrong_step_text) computed independently of the
    solver, straight from sympy, so the test doesn't trust the code under
    test to grade itself."""
    from api.services.visual_tutor.solvers import parse_limit_of_function

    parsed = parse_limit_of_function(problem["problem"])
    x = sympy.Symbol("x")
    expr = sympy.sympify(parsed.function_expression.replace("^", "**"))
    point = (
        sympy.oo
        if parsed.target_point_display == "infinity"
        else sympy.sympify(parsed.target_point_display)
    )
    direction = {"left": "-", "right": "+"}.get(parsed.requested_direction, "+-")
    value = sympy.limit(expr, x, point, dir=direction)
    if value.is_finite:
        correct = str(sympy.nsimplify(value))
        wrong = str(sympy.nsimplify(value) + 1000)
    else:
        correct = "the limit is infinity" if value in (sympy.oo, -sympy.oo) else "the limit does not exist"
        wrong = "42"
    return correct, wrong


def _turn_summary(label: str, response) -> dict[str, Any]:
    rejection_count, rejection_reasons = _bad_board_action_count(response)
    validated = validate_board_response(response)
    rejected_ids = validated.metadata.get("rejected_board_action_ids") or []
    return {
        "action": label,
        "teaching_mode": str(response.teaching_mode),
        "mastery_signal": str(response.mastery_signal),
        "final_answer_locked": response.final_answer_locked,
        "response_source": response.metadata.get("response_source"),
        "fallback_reason": response.metadata.get("fallback_reason"),
        "schema_rejection_count": response.metadata.get("schema_rejection_count"),
        "board_action_rejection_count": rejection_count,
        "board_action_rejection_reasons": rejection_reasons,
        "rejected_board_action_ids": rejected_ids,
        "has_board_content": bool(response.canvas_actions or response.board_actions),
    }


def _append_report(moment_number: int, topic: str, turns: list[dict[str, Any]], error: str | None) -> None:
    report: dict[str, Any] = {}
    if _REPORT_PATH.exists():
        try:
            report = json.loads(_REPORT_PATH.read_text())
        except Exception:
            report = {}
    report[str(moment_number)] = {"topic": topic, "turns": turns, "error": error}
    _REPORT_PATH.write_text(json.dumps(report, indent=2, default=str))


@pytest.mark.parametrize("moment", _MOMENTS, ids=[f"moment_{m['number']:02d}_{m['topic']}" for m in _MOMENTS])
def test_live_session_for_moment(moment: dict[str, Any]) -> None:
    if not os.getenv("DEEPSEEK_API_KEY", "").strip():
        pytest.skip("DEEPSEEK_API_KEY is not set; cannot run a live DeepSeek session.")

    client = DeepSeekVisualTutorLLMClient(timeout=20)
    session_id = f"live-llm-moment-{moment['number']:02d}"
    problem_text = moment["problem"]
    correct_text, wrong_text = _ground_truth_step_texts(moment)
    turns: list[dict[str, Any]] = []

    try:
        submit = handle_visual_tutor_turn(
            VisualTutorTurnRequest(
                user_id="live-student-1",
                session_id=session_id,
                subject="Mathematics",
                topic="Limits of Functions",
                message=problem_text,
                action=VisualTutorAction.SUBMIT_PROBLEM,
                metadata={"grade": 12},
            ),
            llm_client=client,
        )
        turns.append(_turn_summary("submit_problem", submit))
        assert submit.canvas_actions or submit.board_actions

        hint = handle_visual_tutor_turn(
            VisualTutorTurnRequest(
                user_id="live-student-1",
                session_id=session_id,
                subject="Mathematics",
                topic="Limits of Functions",
                action=VisualTutorAction.REQUEST_HINT,
                current_state=VisualTutorTurnState(problem_text=problem_text),
                metadata={"grade": 12},
            ),
            llm_client=client,
        )
        turns.append(_turn_summary("request_hint", hint))
        assert hint.canvas_actions or hint.board_actions

        correct_step = handle_visual_tutor_turn(
            VisualTutorTurnRequest(
                user_id="live-student-1",
                session_id=session_id,
                subject="Mathematics",
                topic="Limits of Functions",
                message=correct_text,
                action=VisualTutorAction.SUBMIT_STEP,
                current_state=VisualTutorTurnState(
                    problem_text=problem_text, current_step_index=1
                ),
                student_submitted_step=True,
                metadata={"grade": 12},
            ),
            llm_client=client,
        )
        turns.append(_turn_summary("submit_correct_step", correct_step))
        assert correct_step.canvas_actions or correct_step.board_actions

        wrong_step = handle_visual_tutor_turn(
            VisualTutorTurnRequest(
                user_id="live-student-1",
                session_id=session_id,
                subject="Mathematics",
                topic="Limits of Functions",
                message=wrong_text,
                action=VisualTutorAction.SUBMIT_STEP,
                current_state=VisualTutorTurnState(
                    problem_text=problem_text, current_step_index=1
                ),
                student_submitted_step=True,
                metadata={"grade": 12},
            ),
            llm_client=client,
        )
        turns.append(_turn_summary("submit_wrong_step", wrong_step))
        assert wrong_step.canvas_actions or wrong_step.board_actions

        final_answer = handle_visual_tutor_turn(
            VisualTutorTurnRequest(
                user_id="live-student-1",
                session_id=session_id,
                subject="Mathematics",
                topic="Limits of Functions",
                action=VisualTutorAction.REQUEST_FINAL_ANSWER,
                current_state=VisualTutorTurnState(
                    problem_text=problem_text, current_step_index=1
                ),
                allow_final_answer=True,
                metadata={"grade": 12},
            ),
            llm_client=client,
        )
        turns.append(_turn_summary("request_final_answer", final_answer))
        assert final_answer.canvas_actions or final_answer.board_actions
    except Exception as exc:  # noqa: BLE001 -- report, then re-raise for pytest
        _append_report(moment["number"], moment["topic"], turns, error=f"{type(exc).__name__}: {exc}")
        raise
    else:
        _append_report(moment["number"], moment["topic"], turns, error=None)

    print(f"\n=== moment {moment['number']:02d} ({moment['topic']}) ===")
    for turn in turns:
        print(
            f"  {turn['action']:22s} response_source={turn['response_source']!s:20s} "
            f"schema_rejections={turn['schema_rejection_count']!s:4s} "
            f"board_rejections={turn['board_action_rejection_count']}"
        )
