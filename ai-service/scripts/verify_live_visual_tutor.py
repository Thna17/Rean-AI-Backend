#!/usr/bin/env python3
"""Manually verify Live Visual Tutor flows against a running ai-service.

Default target: http://localhost:8001

The script creates one Visual Tutor session, sends a realistic sequence of
student turns, prints the live-stage contract summary, and exits non-zero when
core safety or interaction expectations fail.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Optional

DEFAULT_BASE_URL = "http://localhost:8001"
DEFAULT_USER_ID = "manual-live-visual-tutor"


@dataclass(frozen=True)
class FlowStep:
    label: str
    message: str
    action: str = "submit_step"
    subject: str = "Mathematics"
    topic: Optional[str] = None
    student_intent: Optional[str] = None
    expect_advance: Optional[bool] = None
    final_answer_patterns: tuple[str, ...] = field(default_factory=tuple)


@dataclass
class StepResult:
    step: FlowStep
    response: dict[str, Any]
    session_before: dict[str, Any]
    session_after: dict[str, Any]
    board_advanced: bool
    final_answer_leaked: bool
    failures: list[str]


FLOW_STEPS = [
    FlowStep(
        label="linear problem",
        message="2x + 5 = 15",
        action="submit_problem",
        topic="Linear Equations",
        student_intent="new_problem",
        final_answer_patterns=(r"\bx\s*=\s*5\b",),
    ),
    FlowStep(
        label="unrelated number 50",
        message="50",
        expect_advance=False,
        final_answer_patterns=(r"\bx\s*=\s*5\b",),
    ),
    FlowStep(
        label="incorrect early answer 4",
        message="4",
        expect_advance=False,
        final_answer_patterns=(r"\bx\s*=\s*5\b",),
    ),
    FlowStep(
        label="random text",
        message="random text",
        expect_advance=False,
        final_answer_patterns=(r"\bx\s*=\s*5\b",),
    ),
    FlowStep(
        label="valid first linear step",
        message="2x = 10",
        expect_advance=True,
        final_answer_patterns=(r"\bx\s*=\s*5\b",),
    ),
    FlowStep(
        label="linear stuck help",
        message="I am stuck",
        action="request_stuck_help",
        student_intent="stuck",
        final_answer_patterns=(r"\bx\s*=\s*5\b",),
    ),
    FlowStep(
        label="line through two points",
        message="Find the equation of the line through D(0,1) and E(1,3)",
        action="submit_problem",
        topic="Coordinate Geometry",
        student_intent="new_problem",
        final_answer_patterns=(r"\by\s*=\s*2x\s*\+\s*1\b",),
    ),
    FlowStep(
        label="line delta y answer",
        message="2",
        expect_advance=True,
        final_answer_patterns=(r"\by\s*=\s*2x\s*\+\s*1\b",),
    ),
    FlowStep(
        label="line delta x answer",
        message="1",
        expect_advance=True,
        final_answer_patterns=(r"\by\s*=\s*2x\s*\+\s*1\b",),
    ),
    FlowStep(
        label="slope problem",
        message="What is the slope between A(2,4) and B(5,10)?",
        action="submit_problem",
        topic="Coordinate Geometry",
        student_intent="new_problem",
        final_answer_patterns=(r"\bm\s*=\s*2\b", r"\bslope\s*(?:is|=|:)\s*2\b"),
    ),
    FlowStep(
        label="quadratic problem",
        message="Solve x^2 - 5x + 6 = 0",
        action="submit_problem",
        topic="Quadratic Equations",
        student_intent="new_problem",
        final_answer_patterns=(
            r"\bx\s*=\s*2\b",
            r"\bx\s*=\s*3\b",
            r"\broots?\s*(?:are|:)\s*2\s*(?:and|,)\s*3\b",
        ),
    ),
    FlowStep(
        label="Khmer stuck phrase",
        message="ខ្ញុំមិនយល់",
        action="request_stuck_help",
        student_intent="stuck",
        final_answer_patterns=(r"\bx\s*=\s*2\b", r"\bx\s*=\s*3\b"),
    ),
    FlowStep(
        label="English grammar question",
        message="Can you explain when to use has and have?",
        action="submit_problem",
        subject="English",
        topic="Grammar",
        student_intent="new_problem",
    ),
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--user-id", default=DEFAULT_USER_ID)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--json", action="store_true", help="Print raw JSON summary")
    args = parser.parse_args()

    client = ApiClient(args.base_url.rstrip("/"), timeout=args.timeout)
    try:
        session = client.post(
            "/api/v1/visual_tutor/sessions",
            {
                "user_id": args.user_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "metadata": {"manual_verification": True},
            },
        )
    except Exception as exc:
        print(f"FAIL: could not create Visual Tutor session: {exc}", file=sys.stderr)
        return 2

    session_id = str(session["session_id"])
    print(f"Live Visual Tutor verification")
    print(f"base_url={client.base_url}")
    print(f"session_id={session_id}")
    print("")

    results: list[StepResult] = []
    for index, step in enumerate(FLOW_STEPS, start=1):
        before = client.get_session(session_id, args.user_id)
        try:
            response = client.post(
                "/api/v1/visual_tutor/turn",
                _turn_payload(
                    step=step,
                    session_id=session_id,
                    user_id=args.user_id,
                    session=before,
                ),
            )
        except Exception as exc:
            result = StepResult(
                step=step,
                response={},
                session_before=before,
                session_after=before,
                board_advanced=False,
                final_answer_leaked=False,
                failures=[f"no response: {exc}"],
            )
            results.append(result)
            _print_result(index, result)
            continue

        after = client.get_session(session_id, args.user_id)
        result = _evaluate_step(
            step=step, response=response, before=before, after=after
        )
        results.append(result)
        _print_result(index, result)

    failures = [failure for result in results for failure in result.failures]
    if args.json:
        print(
            json.dumps(
                [_result_json(result) for result in results],
                ensure_ascii=False,
                indent=2,
            )
        )

    print("")
    if failures:
        print(f"FAIL: {len(failures)} issue(s) found")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("PASS: Live Visual Tutor manual verification completed")
    return 0


class ApiClient:
    def __init__(self, base_url: str, *, timeout: float) -> None:
        self.base_url = base_url
        self.timeout = timeout

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload=payload)

    def get_session(self, session_id: str, user_id: str) -> dict[str, Any]:
        query = urllib.parse.urlencode({"user_id": user_id})
        return self._request(
            "GET", f"/api/v1/visual_tutor/sessions/{session_id}?{query}"
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(str(exc.reason)) from exc
        elapsed = time.monotonic() - started
        if elapsed > self.timeout:
            raise RuntimeError(f"request exceeded timeout: {elapsed:.1f}s")
        parsed = json.loads(body)
        if not isinstance(parsed, dict):
            raise RuntimeError(f"expected JSON object, got: {type(parsed).__name__}")
        return parsed


def _turn_payload(
    *,
    step: FlowStep,
    session_id: str,
    user_id: str,
    session: dict[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "user_id": user_id,
        "session_id": session_id,
        "subject": step.subject,
        "topic": step.topic or session.get("topic"),
        "message": step.message,
        "action": step.action,
        "current_state": {
            "problem_text": session.get("problem_text"),
            "normalized_problem": session.get("normalized_problem"),
            "current_step_index": int(session.get("current_step_index") or 0),
            "hint_count": int(session.get("hint_count") or 0),
            "wrong_attempts": int(session.get("attempts") or 0),
            "final_answer_revealed": bool(session.get("final_answer_revealed")),
        },
        "metadata": {"manual_verification": True},
    }
    if step.student_intent:
        payload["student_intent"] = step.student_intent
    if step.action == "submit_step":
        payload["student_submitted_step"] = True
    return payload


def _evaluate_step(
    *,
    step: FlowStep,
    response: dict[str, Any],
    before: dict[str, Any],
    after: dict[str, Any],
) -> StepResult:
    failures: list[str] = []
    before_index = int(before.get("current_step_index") or 0)
    after_index = int(after.get("current_step_index") or 0)
    board_advanced = after_index > before_index
    final_answer_locked = bool(response.get("final_answer_locked", True))
    final_answer_leaked = final_answer_locked and _final_answer_leaked(
        response,
        patterns=step.final_answer_patterns,
    )

    if not response:
        failures.append(f"{step.label}: no response")
    if final_answer_leaked:
        failures.append(f"{step.label}: final answer leaked while locked")
    if step.expect_advance is False and board_advanced:
        failures.append(f"{step.label}: unrelated/invalid input advanced board")
    if step.expect_advance is True and not board_advanced:
        failures.append(f"{step.label}: valid step did not advance board")
    if not response.get("interaction"):
        failures.append(f"{step.label}: missing interaction")
    if _board_action_count(response) == 0:
        failures.append(f"{step.label}: missing board action")

    return StepResult(
        step=step,
        response=response,
        session_before=before,
        session_after=after,
        board_advanced=board_advanced,
        final_answer_leaked=final_answer_leaked,
        failures=failures,
    )


def _print_result(index: int, result: StepResult) -> None:
    response = result.response
    metadata = (
        response.get("metadata") if isinstance(response.get("metadata"), dict) else {}
    )
    teaching_stage = response.get("teaching_stage")
    if not isinstance(teaching_stage, dict):
        teaching_stage = (
            metadata.get("teaching_stage")
            if isinstance(metadata.get("teaching_stage"), dict)
            else {}
        )
    interaction = (
        response.get("interaction")
        if isinstance(response.get("interaction"), dict)
        else {}
    )
    problem_understanding = metadata.get("problem_understanding")
    if not isinstance(problem_understanding, dict):
        problem_understanding = {}

    status = "OK" if not result.failures else "FAIL"
    print(f"[{index:02d}] {status} {result.step.label}: {result.step.message}")
    print(f"     teaching_mode={response.get('teaching_mode')}")
    print(
        f"     stage_state={teaching_stage.get('stage_state') or metadata.get('stage_state')}"
    )
    print(
        f"     lesson_state={teaching_stage.get('lesson_state') or metadata.get('lesson_state')}"
    )
    print(f"     final_answer_locked={response.get('final_answer_locked')}")
    print(f"     board_action_count={_board_action_count(response)}")
    print(f"     interaction_type={interaction.get('type')}")
    print(
        f"     expected_input={interaction.get('prompt') or response.get('student_task')}"
    )
    print(
        f"     problem_type={problem_understanding.get('problem_type') or metadata.get('problem_type')}"
    )
    print(f"     input_relevance={metadata.get('input_relevance')}")
    print(f"     final_answer_leaked={result.final_answer_leaked}")
    print(f"     board_advanced={result.board_advanced}")
    for failure in result.failures:
        print(f"     ! {failure}")


def _board_action_count(response: dict[str, Any]) -> int:
    board_actions = response.get("board_actions")
    canvas_actions = response.get("canvas_actions")
    return len(board_actions if isinstance(board_actions, list) else []) + len(
        canvas_actions if isinstance(canvas_actions, list) else []
    )


def _final_answer_leaked(
    response: dict[str, Any], *, patterns: tuple[str, ...]
) -> bool:
    if not patterns:
        return False
    visible_text = "\n".join(_visible_strings(response))
    return any(
        re.search(pattern, visible_text, flags=re.IGNORECASE) for pattern in patterns
    )


def _visible_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, list):
        for item in value:
            strings.extend(_visible_strings(item))
    elif isinstance(value, dict):
        if (
            value.get("locked") is True
            or value.get("hidden") is True
            or value.get("type") == "hide"
        ):
            return strings
        metadata = value.get("metadata")
        if isinstance(metadata, dict) and metadata.get("hidden") is True:
            return strings
        for key, item in value.items():
            if key in {"metadata", "request", "current_state"}:
                continue
            strings.extend(_visible_strings(item))
    return strings


def _result_json(result: StepResult) -> dict[str, Any]:
    metadata = result.response.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    interaction = result.response.get("interaction")
    if not isinstance(interaction, dict):
        interaction = {}
    return {
        "label": result.step.label,
        "message": result.step.message,
        "teaching_mode": result.response.get("teaching_mode"),
        "final_answer_locked": result.response.get("final_answer_locked"),
        "board_action_count": _board_action_count(result.response),
        "interaction_type": interaction.get("type"),
        "problem_type": metadata.get("problem_type"),
        "input_relevance": metadata.get("input_relevance"),
        "final_answer_leaked": result.final_answer_leaked,
        "board_advanced": result.board_advanced,
        "failures": result.failures,
    }


if __name__ == "__main__":
    raise SystemExit(main())
