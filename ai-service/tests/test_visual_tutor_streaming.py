"""Focused SSE contract coverage for the Visual Tutor streaming endpoint."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from api.models.visual_tutor import VisualTutorTurnRequest
from api.routes import visual_tutor as visual_tutor_route


class _ConnectedRequest:
    async def is_disconnected(self) -> bool:
        return False


class _OwnedSession:
    user_id = "student-1"
    board_version = 0


class _OwnedSessionStore:
    """Small preflight-compatible store; the patched /turn owns no persistence."""

    async def get_session(self, session_id: str) -> _OwnedSession | None:
        return _OwnedSession() if session_id == "session-1" else None


@pytest.fixture(autouse=True)
def _configure_gateway_token(monkeypatch) -> None:
    """Use the real gateway/user checks with a test-only internal token."""
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-stream-token")


def _request() -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id="student-1",
        session_id="session-1",
        subject="Mathematics",
        message="2x + 5 = 15",
        idempotency_key="stream-key-1",
        metadata={"public_contract_version": 1},
    )


async def _stream(*, last_event_id: str | None = None):
    """Open a stream through the same auth and owned-session preflight as production."""
    return await visual_tutor_route.visual_tutor_turn_stream(
        request=_request(),
        http_request=_ConnectedRequest(),
        x_visual_tutor_user_id="student-1",
        x_visual_tutor_internal_token="test-stream-token",
        last_event_id=last_event_id,
        store=_OwnedSessionStore(),
        learner_memory_store=object(),
    )


def _public_turn(*, actions: list[dict] | None = None) -> dict:
    action_list = actions if actions is not None else [
        {
            "id": "equation-1",
            "action_id": "equation-1",
            "type": "write_equation",
            "sequence_index": 0,
            "x": 40,
            "y": 40,
            "width": 360,
            "height": 56,
            "text": "2x + 5 = 15",
            "problem_instance_id": "problem-1",
            "active_step_id": "lesson-1:step-0",
            "board_version": 1,
            "base_board_version": 0,
        }
    ]
    return {
        "schema_version": 2,
        "session_id": "session-1",
        "turn_id": "turn-1",
        "board_version": 1,
        "base_board_version": 0,
        "board_update_mode": "replace",
        "lesson_state": {
            "problem_instance_id": "problem-1",
            "lesson_id": "lesson-1",
            "active_step_id": "lesson-1:step-0",
            "current_step_index": 0,
            "expected_student_action_id": "task-1",
            "teaching_stage": "waiting_for_student",
            "lesson_state": "ask",
            "final_answer_locked": True,
            "board_version": 1,
            "base_board_version": 0,
        },
        "teaching_plan": {
            "schema_version": 1,
            "representation": "equation_transformation",
            "learning_objective": "Make one verified step.",
            "teaching_message": "Look at the constant.",
            "visible_board_actions": action_list,
            "active_student_task": {
                "id": "task-1",
                "action_id": "task-1",
                "type": "student_task",
                "sequence_index": len(action_list),
                "x": 40,
                "y": 520,
                "text": "What should we do first?",
                "requires_student_response": True,
                "task_type": "conceptual_operation",
                "accepted_answer_forms": ["operation words"],
                "explanation_required": False,
                "problem_instance_id": "problem-1",
                "active_step_id": "lesson-1:step-0",
                "board_version": 1,
                "base_board_version": 0,
            },
            "allowed_student_actions": ["submit_answer", "request_hint"],
            "hidden_answer_policy": {
                "mode": "hidden",
                "deterministic_policy_permits_final_reveal": False,
            },
            "next_state_policy": {
                "correct": "continue",
                "invalid": "reteach",
                "incomplete": "ask_for_work",
                "stuck": "reteach",
                "hint": "continue",
                "explain_differently": "ask_for_work",
            },
        },
        "tutor_status": "Waiting for you",
        "verification": {"status": "cannot_verify", "verified": False},
        "recovery": {"state": "ready"},
    }


async def _events(response) -> list[dict]:
    body = b""
    async for part in response.body_iterator:
        body += part
    frames = [frame for frame in body.decode("utf-8").split("\n\n") if frame]
    events: list[dict] = []
    for frame in frames:
        lines = dict(line.split(": ", 1) for line in frame.splitlines() if ": " in line)
        assert lines["event"] == "visual_tutor"
        events.append(json.loads(lines["data"]))
    return events


def _event_from_frame(frame: bytes) -> dict:
    """Decode one SSE frame while preserving the iterator's delivery order."""
    lines = dict(
        line.split(": ", 1)
        for line in frame.decode("utf-8").splitlines()
        if ": " in line
    )
    assert lines["event"] == "visual_tutor"
    return json.loads(lines["data"])


@pytest.mark.asyncio
async def test_stream_emits_validated_preview_before_authoritative_turn_completes(monkeypatch) -> None:
    payload = _public_turn()
    generation_started = asyncio.Event()
    allow_completion = asyncio.Event()
    completed = False

    async def _completed(**_kwargs):
        nonlocal completed
        generation_started.set()
        await allow_completion.wait()
        completed = True
        return JSONResponse(payload)

    monkeypatch.setattr(visual_tutor_route, "visual_tutor_turn", _completed)
    response = await _stream()
    iterator = response.body_iterator.__aiter__()
    planning = _event_from_frame(await anext(iterator))
    preview = _event_from_frame(await anext(iterator))
    reasoning = _event_from_frame(await anext(iterator))

    # The preview is yielded while the authoritative /turn call is still
    # blocked, proving the student sees a validated board action live rather
    # than only after the full lesson response has been generated.
    assert planning["type"] == "status"
    assert preview["type"] == "board_action"
    assert preview["data"]["provisional"] is True
    assert preview["data"]["action"]["metadata"]["provisional"] is True
    assert reasoning["type"] == "status"
    await asyncio.wait_for(generation_started.wait(), timeout=0.1)
    assert completed is False

    allow_completion.set()
    events = [planning, preview, reasoning]
    async for frame in iterator:
        events.append(_event_from_frame(frame))

    assert [event["type"] for event in events] == [
        "status", "board_action", "status", "speech_ready", "board_action",
        "board_action", "turn_complete",
    ]
    assert [event["sequence"] for event in events] == list(range(7))
    event_ids = [event["event_id"] for event in events]
    assert event_ids == [f"stream-key-1:{index}" for index in range(7)]
    assert len(event_ids) == len(set(event_ids))
    assert all(event["schema_version"] == 1 for event in events)
    assert events[4]["data"]["action"] == payload["teaching_plan"]["visible_board_actions"][0]
    assert events[-1]["data"]["response"] == payload
    assert "solver_facts" not in json.dumps(events[-1]["data"])
    assert "x = 5" not in json.dumps(events[-1]["data"])


@pytest.mark.asyncio
async def test_stream_resumes_after_last_event_id_without_replaying_prior_events(monkeypatch) -> None:
    async def _completed(**_kwargs):
        return JSONResponse(_public_turn())

    monkeypatch.setattr(visual_tutor_route, "visual_tutor_turn", _completed)
    response = await _stream(last_event_id="stream-key-1:2")
    events = await _events(response)

    assert [event["sequence"] for event in events] == [3, 4, 5, 6]
    assert [event["type"] for event in events] == [
        "speech_ready", "board_action", "board_action", "turn_complete",
    ]
    assert all(event["sequence"] > 2 for event in events)
    assert len({event["event_id"] for event in events}) == len(events)


@pytest.mark.asyncio
async def test_stream_returns_recoverable_stale_board_error(monkeypatch) -> None:
    async def _stale(**_kwargs):
        raise HTTPException(
            status_code=409,
            detail={"message": "Board is stale", "expected_board_version": 3},
        )

    monkeypatch.setattr(visual_tutor_route, "visual_tutor_turn", _stale)
    response = await _stream()
    events = await _events(response)

    assert [event["type"] for event in events] == ["status", "board_action", "status", "error"]
    assert events[-1]["data"] == {
        "code": "STALE_BOARD",
        "message": "Board is stale",
        "recoverable": True,
        "expected_board_version": 3,
    }


@pytest.mark.asyncio
async def test_stream_times_out_with_recoverable_error(monkeypatch) -> None:
    async def _slow(**_kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(visual_tutor_route, "visual_tutor_turn", _slow)
    monkeypatch.setattr(visual_tutor_route, "_STREAM_TIMEOUT_SECONDS", 0.001)
    response = await _stream()
    events = await _events(response)

    assert events[-1]["type"] == "error"
    assert events[-1]["data"]["code"] == "TIMEOUT"
    assert events[-1]["data"]["recoverable"] is True


@pytest.mark.asyncio
async def test_stream_does_not_emit_an_invalid_board_action(monkeypatch) -> None:
    payload = _public_turn(actions=[
        {
            "id": "out-of-bounds",
            "action_id": "out-of-bounds",
            "type": "write_text",
            "sequence_index": 0,
            "x": 20_000,
            "text": "This action exceeds the board boundary.",
            "problem_instance_id": "problem-1",
            "active_step_id": "lesson-1:step-0",
            "board_version": 1,
            "base_board_version": 0,
        }
    ])

    async def _completed(**_kwargs):
        return JSONResponse(payload)

    monkeypatch.setattr(visual_tutor_route, "visual_tutor_turn", _completed)
    response = await _stream()
    events = await _events(response)

    # The only allowed incremental action is the server-authored preview. The
    # invalid model action must never cross the stream boundary.
    board_actions = [event["data"]["action"] for event in events if event["type"] == "board_action"]
    assert board_actions
    assert all(action["action_id"] != "out-of-bounds" for action in board_actions)
    assert all(action.get("metadata", {}).get("provisional") is True for action in board_actions)
    assert events[-1]["type"] == "error"
    assert events[-1]["data"]["recoverable"] is True
