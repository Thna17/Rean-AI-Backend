"""The SSE stream the student app actually consumes.

Note the version asymmetry that bites everyone: the turn body is
`schema_version: 2`, but stream frames are `schema_version: 1`. The Flutter client
discards a frame with the wrong version silently, so a mistake here looks like an
outage rather than a parse error.
"""

from __future__ import annotations

import time

import httpx
import pytest

from conftest import (
    DEMO_TOKEN,
    GATEWAY_BASE,
    PUBLIC_VERIFICATION_STATUSES,
    STUDENT_ORIGIN,
    parse_sse,
)

PROBLEM = "Find the limit of (x^2-4)/(x-2) as x approaches 2"


def _stream(body: dict, *, last_event_id: str | None = None, timeout: float = 240.0):
    headers = {
        "Authorization": f"Bearer {DEMO_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Origin": STUDENT_ORIGIN,
    }
    if last_event_id:
        headers["Last-Event-ID"] = last_event_id
    with httpx.Client(timeout=timeout) as client:
        started = time.monotonic()
        response = client.post(
            f"{GATEWAY_BASE}/tutor/turn/stream", json=body, headers=headers
        )
        return response, time.monotonic() - started


@pytest.fixture(scope="module")
def streamed():
    response, elapsed = _stream(
        {
            "subject": "Mathematics",
            "message": PROBLEM,
            "action": "submit_problem",
            "language_mode": "english",
        }
    )
    assert response.status_code == 200, (
        f"the gateway refused to open the stream: {response.status_code} "
        f"{response.text[:300]}"
    )
    events = parse_sse(response.text)
    assert events, f"the stream produced no decodable events: {response.text[:400]!r}"
    return response, events, elapsed


def test_the_stream_is_served_as_server_sent_events(streamed):
    response, _events, _elapsed = streamed
    content_type = response.headers.get("content-type", "")
    assert "text/event-stream" in content_type, (
        f"the client only parses SSE; got content-type {content_type!r}"
    )


def test_every_frame_uses_the_version_the_client_accepts(streamed):
    _response, events, _elapsed = streamed
    versions = {event.get("schema_version") for event in events}
    assert versions == {1}, (
        "the Flutter client drops any frame whose schema_version is not 1, so the "
        f"board would stay blank; saw {versions}"
    )


def test_the_stream_ends_with_the_authoritative_turn(streamed):
    _response, events, _elapsed = streamed
    types = [event.get("type") for event in events]
    assert types[-1] == "turn_complete", (
        f"a stream must finish with turn_complete so the client has an "
        f"authoritative board; ended with {types[-1]!r} (all: {types})"
    )

    final = events[-1].get("data", {}).get("response")
    assert isinstance(final, dict), "turn_complete carried no response payload"
    verification = final.get("verification") or {}
    assert verification.get("status") in PUBLIC_VERIFICATION_STATUSES, (
        f"the streamed turn reports a status the gateway forbids: {verification}"
    )


def test_board_actions_arrive_before_the_turn_completes(streamed):
    _response, events, _elapsed = streamed
    types = [event.get("type") for event in events]
    assert "board_action" in types, (
        "nothing was streamed to the board, so the student watches a blank canvas "
        "until the whole turn finishes"
    )
    assert types.index("board_action") < types.index("turn_complete")


def test_frames_carry_ordered_unique_event_ids(streamed):
    _response, events, _elapsed = streamed
    ids = [event.get("event_id") for event in events]
    assert all(ids), "a frame without an event_id cannot be resumed from"
    assert len(ids) == len(set(ids)), f"duplicate event ids in one stream: {ids}"

    sequences = [event.get("sequence") for event in events]
    assert sequences == sorted(sequences), f"frames arrived out of order: {sequences}"


def test_no_solution_content_is_streamed_then_dropped(streamed):
    """A board built from the stream must not contradict the authoritative turn.

    Two kinds of streamed action are legitimately absent from `turn_complete`:
    the provisional `stream-preview-*` placeholder documented in CLAUDE.md §3,
    which exists only while the solver runs, and the `ws-next-*` control, which
    the public projection reports as `active_student_task` rather than as a
    visible action. Anything else vanishing would mean the student watched
    something the server then disowned.
    """
    _response, events, _elapsed = streamed
    streamed_ids = [
        (event.get("data", {}).get("action") or {}).get("id")
        for event in events
        if event.get("type") == "board_action"
    ]
    assert streamed_ids, "no board actions were streamed at all"

    final = events[-1]["data"]["response"]
    plan = final.get("teaching_plan") or {}
    final_ids = {
        action.get("id") for action in plan.get("visible_board_actions") or []
    }

    def is_provisional(action_id: str) -> bool:
        return action_id.startswith("stream-preview-") or action_id.startswith(
            "ws-next-"
        )

    dropped = [
        action_id
        for action_id in streamed_ids
        if action_id and action_id not in final_ids and not is_provisional(action_id)
    ]
    assert not dropped, (
        "these actions were drawn from the stream and then disowned by "
        f"turn_complete: {dropped}"
    )

    # And the solution itself really did arrive over the stream, rather than only
    # in the final payload.
    solution_ids = {i for i in final_ids if str(i).startswith(("ws-step-", "ws-answer-"))}
    assert solution_ids, "turn_complete contained no worked-solution actions"
    assert solution_ids.issubset(set(streamed_ids)), (
        "part of the solution never reached the board progressively: "
        f"{sorted(solution_ids - set(streamed_ids))}"
    )


def test_the_provisional_preview_is_replaced_not_kept(streamed):
    """The placeholder must not survive into the authoritative board."""
    _response, events, _elapsed = streamed
    final_ids = [
        action.get("id")
        for action in (events[-1]["data"]["response"].get("teaching_plan") or {}).get(
            "visible_board_actions"
        )
        or []
    ]
    assert not [i for i in final_ids if str(i).startswith("stream-preview-")], (
        "a provisional preview action was left on the authoritative board"
    )


def test_resuming_with_a_last_event_id_is_accepted(streamed):
    """The client resumes a dropped stream with this header rather than restarting."""
    _response, events, _elapsed = streamed
    first_id = events[0].get("event_id")

    resumed, _elapsed_resume = _stream(
        {
            "subject": "Mathematics",
            "message": PROBLEM,
            "action": "submit_problem",
            "language_mode": "english",
        },
        last_event_id=str(first_id),
    )
    assert resumed.status_code == 200, (
        "a resume attempt was refused, so a student on a dropped connection would "
        f"have to watch the whole solution redraw: {resumed.status_code}"
    )
    assert parse_sse(resumed.text), "the resumed stream produced no events"


def test_a_stream_cannot_be_opened_without_a_student(streamed):
    with httpx.Client(timeout=60.0) as client:
        response = client.post(
            f"{GATEWAY_BASE}/tutor/turn/stream",
            json={"subject": "Mathematics", "message": PROBLEM},
            headers={"Accept": "text/event-stream", "Origin": STUDENT_ORIGIN},
        )
    assert response.status_code in (401, 403)
