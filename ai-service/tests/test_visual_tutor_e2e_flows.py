from __future__ import annotations

import copy
import json
from typing import Any, Callable, Optional

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

import api.routes.visual_tutor as visual_tutor_route_module
from api.models.visual_tutor import (
    VisualTutorSession,
    VisualTutorSessionCreateRequest,
    VisualTutorSessionSummary,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.routes.visual_tutor import (
    get_learner_memory_store,
    get_visual_tutor_store,
    router,
)
from api.services.visual_tutor.learner_memory import (
    LearnerMemoryProfile,
    build_learner_memory_update,
)
from api.services.visual_tutor.session_store import (
    _canvas_snapshot_from_response,
    _live_stage_snapshot_from_response,
    _student_response_from_request,
    evaluate_attempt_counters,
)
from api.services.visual_tutor.orchestrator import (
    handle_visual_tutor_turn as real_handle_visual_tutor_turn,
)

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures(
    "guided_tutor_mode", "development_compatibility_contract"
)


class FakeVisualTutorStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}

    async def create_session(
        self,
        request: VisualTutorSessionCreateRequest,
        *,
        session_id: Optional[str] = None,
    ) -> VisualTutorSession:
        sid = session_id or f"session-{len(self.sessions) + 1}"
        doc = {
            "session_id": sid,
            "user_id": request.user_id,
            "subject": request.subject,
            "topic": request.topic,
            "problem_text": request.problem_text,
            "normalized_problem": None,
            "problem_type": None,
            "solver_facts": None,
            "current_step_index": 0,
            "expected_step": None,
            "solved_variables": {},
            "validation_history": [],
            "hint_count": 0,
            "wrong_attempts": 0,
            "stuck_count": 0,
            "attempts": 0,
            "final_answer_revealed": False,
            "board_version": 0,
            "messages": [],
            "turns": [],
            "board_states": [],
            "canvas_state": None,
            "canvas_actions": [],
            "canvas_states": [],
            "locked_canvas_element_ids": [],
            "revealed_canvas_element_ids": [],
            "current_focus_element_id": None,
            "teaching_stage": None,
            "stage_state": None,
            "lesson_state": None,
            "teaching_board_state": None,
            "teaching_board_states": [],
            "visible_board_elements": [],
            "hidden_element_ids": [],
            "locked_element_ids": [],
            "played_action_ids": [],
            "previous_board_action_ids": [],
            "board_action_history": [],
            "pending_interaction": None,
            "allowed_actions": [],
            "student_responses": [],
            "voice_tts_metadata": {},
            "curriculum_chunk_ids": [],
            "response_source_history": [],
            "mastery_signal": None,
            "created_at": "2026-07-20T00:00:00+00:00",
            "updated_at": "2026-07-20T00:00:00+00:00",
            "metadata": request.metadata,
        }
        self.sessions[sid] = doc
        return VisualTutorSession(**doc)

    async def get_session(self, session_id: str) -> Optional[VisualTutorSession]:
        doc = self.sessions.get(session_id)
        return VisualTutorSession(**doc) if doc else None

    async def list_user_sessions(self, user_id: str) -> list[VisualTutorSessionSummary]:
        return [
            VisualTutorSessionSummary(**doc)
            for doc in self.sessions.values()
            if doc["user_id"] == user_id
        ]

    async def get_persisted_turn_response(
        self,
        *,
        session_id: str,
        idempotency_key: str,
    ):
        doc = self.sessions.get(session_id)
        if not doc:
            return None
        for turn in reversed(doc["turns"]):
            turn_key = (
                turn.get("idempotency_key")
                or (turn.get("request", {}).get("metadata", {}).get("idempotency_key"))
                or (turn.get("request", {}).get("metadata", {}).get("client_turn_id"))
            )
            if turn_key == idempotency_key:
                return VisualTutorTurnResponse.model_validate(turn["response"])
        return None

    async def persist_turn(self, *, request, response) -> VisualTutorSession:
        session = await self.get_session(response.session_id)
        if session is None:
            session = await self.create_session(
                VisualTutorSessionCreateRequest(
                    user_id=request.user_id,
                    subject=request.subject,
                    topic=request.topic,
                    problem_text=request.current_state.problem_text,
                ),
                session_id=response.session_id,
            )
        doc = self.sessions[response.session_id]
        problem_item = next(
            (item for item in response.board.items if item.label.lower() == "problem"),
            None,
        )
        is_new_problem = (
            request.message.strip()
            and (
                getattr(request.student_intent, "value", None) == "new_problem"
                or response.metadata.get("student_intent") == "new_problem"
                or not request.current_state.problem_text
            )
            and (
                request.action.value == "submit_problem"
                or response.metadata.get("student_intent") == "new_problem"
            )
        )
        doc["problem_text"] = (
            (problem_item.content if problem_item else request.message.strip())
            if is_new_problem
            else (
                request.current_state.problem_text
                or doc.get("problem_text")
                or (problem_item.content if problem_item else None)
            )
        )
        doc["normalized_problem"] = (
            response.board.metadata.get("normalized_problem")
            or (None if is_new_problem else request.current_state.normalized_problem)
            or (None if is_new_problem else doc.get("normalized_problem"))
        )
        doc["current_step_index"] = response.board.metadata.get(
            "current_step_index",
            request.current_state.current_step_index,
        )
        doc["solver_facts"] = response.metadata.get("solver_facts") or doc.get(
            "solver_facts"
        )
        is_stuck_turn = (
            response.metadata.get("policy", {}).get("detected_intent") == "stuck"
            or response.teaching_mode.value == "stuck_help"
        )
        if is_new_problem:
            doc["hint_count"] = 0
        elif request.action.value == "request_hint" or is_stuck_turn:
            doc["hint_count"] = (
                max(doc["hint_count"], request.current_state.hint_count) + 1
            )
        else:
            doc["hint_count"] = max(doc["hint_count"], request.current_state.hint_count)
        if is_new_problem:
            doc["attempts"] = 0
        validation_result = response.metadata.get("validation_result")
        input_relevance = response.metadata.get("input_relevance")
        doc["attempts"], doc["wrong_attempts"] = evaluate_attempt_counters(
            request,
            response,
            is_new_problem=is_new_problem,
            current_attempts=doc["attempts"],
            current_wrong_attempts=doc["wrong_attempts"],
        )
        doc["final_answer_revealed"] = (
            not response.final_answer_locked
            if is_new_problem
            else doc["final_answer_revealed"] or not response.final_answer_locked
        )
        doc["mastery_signal"] = response.mastery_signal.value
        base_board_version = doc.get("board_version") or 0
        next_board_version = base_board_version + 1
        stored_response = response.model_copy(
            update={
                "board_version": next_board_version,
                "base_board_version": base_board_version,
                "metadata": {
                    **response.metadata,
                    "board_version": next_board_version,
                    "base_board_version": base_board_version,
                },
            }
        )
        idempotency_key = (
            getattr(request, "idempotency_key", None)
            or request.metadata.get("idempotency_key")
            or request.metadata.get("client_turn_id")
        )
        doc["turns"].append(
            {
                "turn_id": response.turn_id,
                "request": request.model_dump(mode="json"),
                "response": stored_response.model_dump(mode="json"),
                **({"idempotency_key": idempotency_key} if idempotency_key else {}),
            }
        )
        doc["board_states"].append(response.board.model_dump(mode="json"))
        live_snapshot = _live_stage_snapshot_from_response(
            response=response,
            previous_session=session,
            reset_board=is_new_problem,
        )
        canvas_snapshot = _canvas_snapshot_from_response(response)
        doc["canvas_state"] = canvas_snapshot
        doc["canvas_states"].append(canvas_snapshot)
        doc["canvas_actions"].extend(canvas_snapshot["canvas_actions"])
        doc["locked_canvas_element_ids"] = canvas_snapshot["locked_canvas_element_ids"]
        doc["revealed_canvas_element_ids"] = canvas_snapshot[
            "revealed_canvas_element_ids"
        ]
        doc["current_focus_element_id"] = canvas_snapshot["current_focus_element_id"]
        doc["teaching_stage"] = live_snapshot["teaching_stage"]
        doc["stage_state"] = live_snapshot["stage_state"]
        doc["lesson_state"] = live_snapshot["lesson_state"]
        doc["teaching_board_state"] = live_snapshot["teaching_board_state"]
        doc["teaching_board_states"].append(live_snapshot["teaching_board_state"])
        doc["visible_board_elements"] = live_snapshot["visible_board_elements"]
        doc["hidden_element_ids"] = live_snapshot["hidden_element_ids"]
        doc["locked_element_ids"] = live_snapshot["locked_element_ids"]
        doc["played_action_ids"] = live_snapshot["played_action_ids"]
        doc["previous_board_action_ids"] = live_snapshot["previous_board_action_ids"]
        doc["pending_interaction"] = live_snapshot["pending_interaction"]
        doc["allowed_actions"] = live_snapshot["allowed_actions"]
        doc["voice_tts_metadata"] = live_snapshot["voice_tts_metadata"]
        doc["curriculum_chunk_ids"] = live_snapshot["curriculum_chunk_ids"]
        student_response = _student_response_from_request(
            request=request,
            timestamp="2026-07-20T00:00:01+00:00",
        )
        if student_response:
            doc["student_responses"].append(student_response)
        validation_result = response.metadata.get("validation_result")
        input_relevance = response.metadata.get("input_relevance")
        if validation_result is not None or input_relevance is not None:
            doc["validation_history"].append(
                {
                    "turn_id": response.turn_id,
                    "input_relevance": input_relevance,
                    "validation_result": validation_result,
                    "current_step_index": doc["current_step_index"],
                }
            )
        doc["response_source_history"].append(
            {
                "turn_id": response.turn_id,
                "response_source": response.metadata.get("response_source"),
                "solver_name": response.metadata.get("solver_name"),
                "llm_called": response.metadata.get("llm_called"),
            }
        )
        action_ids = [
            action.id
            for action in response.board_actions
            if getattr(action, "id", None)
        ]
        if action_ids:
            doc["board_action_history"].append(
                {
                    "turn_id": response.turn_id,
                    "action_ids": action_ids,
                    "scoped_action_ids": [
                        f"{response.turn_id}:{action_id}" for action_id in action_ids
                    ],
                }
            )
        doc["messages"].extend(
            [
                {"role": "user", "content": request.message},
                {"role": "assistant", "content": response.display_text},
            ]
        )
        doc["board_version"] = next_board_version
        doc["updated_at"] = "2026-07-20T00:00:01+00:00"
        return VisualTutorSession(**doc)


class FakeVisualTutorLLMClient:
    def __init__(self, payload_factory: Callable[[VisualTutorTurnRequest], dict]):
        self.payload_factory = payload_factory
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        prompt = json.loads(user_prompt)
        request = VisualTutorTurnRequest.model_validate(
            {
                "user_id": "student-1",
                "message": prompt["student_message"],
                "action": prompt["action"],
                "subject": prompt["subject"],
                "topic": prompt["topic"],
            }
        )
        return json.dumps(self.payload_factory(request), ensure_ascii=False)


class FakeLearnerMemoryStore:
    def __init__(self) -> None:
        self.profiles: dict[tuple[str, str, str], dict[str, Any]] = {}

    @staticmethod
    def _key(*, user_id: str, subject: str, topic: str | None) -> tuple[str, str, str]:
        return (user_id, subject.strip().lower(), (topic or "general").strip().lower())

    async def get_for_authenticated_user(self, *, user_id: str, subject: str, topic: str | None):
        value = self.profiles.get(self._key(user_id=user_id, subject=subject, topic=topic))
        return LearnerMemoryProfile.model_validate(value) if value else None

    async def record_turn(self, *, request, response, topic, session_summary):
        key = self._key(user_id=request.user_id, subject=request.subject, topic=topic)
        profile = build_learner_memory_update(
            previous=self.profiles.get(key), request=request, response=response,
            topic=topic, session_summary=session_summary,
        )
        self.profiles[key] = profile.model_dump(mode="json")
        return profile


def _make_app(store: FakeVisualTutorStore) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def trusted_gateway_headers(request, call_next):
        # The AI service is private in production. E2E tests model the trusted
        # TypeScript gateway rather than bypassing its required credentials.
        headers = list(request.scope["headers"])
        header_names = {name.lower() for name, _value in headers}
        if b"x-visual-tutor-internal-token" not in header_names:
            headers.append((b"x-visual-tutor-internal-token", b"test-visual-tutor-token"))
        if b"x-visual-tutor-user-id" not in header_names:
            headers.append((b"x-visual-tutor-user-id", b"student-1"))
        # These flow tests inspect private persistence and solver state. They
        # intentionally use the authenticated development compatibility path;
        # public-turn coverage lives in the compact-contract tests.
        if b"x-visual-tutor-api-compatibility-version" not in header_names:
            headers.append((b"x-visual-tutor-api-compatibility-version", b"0"))
        request.scope["headers"] = headers
        return await call_next(request)

    app.include_router(router)
    app.dependency_overrides[get_visual_tutor_store] = lambda: store
    app.dependency_overrides[get_learner_memory_store] = FakeLearnerMemoryStore
    return app


@pytest.fixture(autouse=True)
def _visual_tutor_gateway_token(monkeypatch):
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-visual-tutor-token")


async def _create_session(
    client: AsyncClient,
    *,
    subject: str = "Mathematics",
    topic: Optional[str] = "Linear Equations",
) -> str:
    response = await client.post(
        "/api/v1/visual_tutor/sessions",
        json={"user_id": "student-1", "subject": subject, "topic": topic},
    )
    assert response.status_code == 200
    return response.json()["session_id"]


async def _post_turn(
    client: AsyncClient,
    *,
    session_id: str,
    message: str,
    action: str,
    **extra: Any,
) -> dict:
    response = await client.post(
        "/api/v1/visual_tutor/turn",
        json={
            "user_id": "student-1",
            "session_id": session_id,
            "message": message,
            "action": action,
            **extra,
        },
    )
    assert response.status_code == 200
    return response.json()


def _guided(request: VisualTutorTurnRequest) -> VisualTutorTurnRequest:
    """Keep fake-LLM handlers in this module's guided "Try it myself" flow."""
    metadata = dict(request.metadata or {})
    metadata.setdefault("tutor_mode", "try_myself")
    return request.model_copy(update={"metadata": metadata})


async def _get_session(client: AsyncClient, session_id: str) -> dict:
    """Resume through the public endpoint, then return the persisted session.

    The public session DTO deliberately hides server-only tutor state (turn
    history, attempt counters, solver and planner data). These flow tests
    check that state, so they read it from the test store after confirming
    the public endpoint serves the session without leaking it.
    """
    response = await client.get(
        f"/api/v1/visual_tutor/sessions/{session_id}",
        params={"user_id": "student-1"},
    )
    assert response.status_code == 200
    public = response.json()
    assert public["session_id"] == session_id
    for private_field in ("turns", "attempts", "board_states", "solver_facts", "planner"):
        assert private_field not in public

    store = client._transport.app.dependency_overrides[get_visual_tutor_store]()
    # A snapshot, like the JSON the endpoint used to return.
    return copy.deepcopy(store.sessions[session_id])


async def _assert_hint_progression(
    client: AsyncClient,
    *,
    session_id: str,
    **extra: Any,
) -> tuple[dict, dict]:
    first_hint = await _post_turn(
        client,
        session_id=session_id,
        message="hint",
        action="request_hint",
        **extra,
    )
    assert first_hint["teaching_mode"] == "hint"
    assert first_hint["final_answer_locked"] is True

    await _post_turn(
        client,
        session_id=session_id,
        message="hint again",
        action="request_hint",
        **extra,
    )
    partial = await _post_turn(
        client,
        session_id=session_id,
        message="one more hint",
        action="request_hint",
        **extra,
    )
    assert partial["teaching_mode"] == "partial_solution"
    assert partial["final_answer_locked"] is True
    return first_hint, partial


def _generic_llm_payload(request: VisualTutorTurnRequest) -> dict:
    return {
        "spoken_text": "Let's reason about the problem before jumping to the answer.",
        "display_text": "Start by naming what the problem is asking.",
        "teaching_mode": "guided_question",
        "student_task": "Tell me what unknown or idea we should identify first.",
        "board": {
            "type": "formula_card",
            "title": "Problem setup",
            "items": [
                {
                    "label": "Problem",
                    "content": request.message or "Restored problem",
                    "status": "active",
                    "metadata": {},
                }
            ],
            "metadata": {"source": "mock_llm"},
        },
        "mastery_signal": "exploring",
        "metadata": {"source": "mock_llm"},
    }


def _leaky_llm_payload(request: VisualTutorTurnRequest) -> dict:
    return {
        **_generic_llm_payload(request),
        "spoken_text": "Final answer is a = 10 - b.",
        "display_text": "Answer: a = 10 - b",
        "student_task": "Copy a = 10 - b.",
        "board": {
            "type": "formula_card",
            "title": "Leaky setup",
            "items": [
                {
                    "label": "Final",
                    "content": "a = 10 - b",
                    "status": "complete",
                    "metadata": {},
                }
            ],
            "metadata": {},
        },
    }


@pytest.mark.asyncio
async def test_e2e_linear_equation_flow_persists_and_restores() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Solve 2x + 5 = 15",
            action="submit_problem",
        )
        assert initial["teaching_mode"] == "guided_question"
        assert initial["final_answer_locked"] is True
        assert initial["board"]["items"][-1]["content"] == "Final answer is locked."

        step = await _post_turn(
            client,
            session_id=session_id,
            message="2x = 10",
            action="submit_step",
            student_submitted_step=True,
        )
        assert step["teaching_mode"] == "step_check"
        assert step["mastery_signal"] == "ready_for_next_step"
        assert step["board"]["items"][-1]["content"] == "Final answer is locked."

        first_hint, partial = await _assert_hint_progression(
            client,
            session_id=session_id,
        )
        assert "x = 5" not in first_hint["display_text"]
        assert partial["board"]["items"][1]["content"] == "2x = 10"

        restored_hint = await _post_turn(
            client,
            session_id=session_id,
            message="continue with a hint",
            action="request_hint",
        )
        session = await _get_session(client, session_id)

    assert restored_hint["board"]["type"] == "equation_steps"
    assert session["problem_text"] == "2x + 5 = 15"
    assert len(session["turns"]) == 6
    assert len(session["board_states"]) == 6
    assert session["hint_count"] >= 4


@pytest.mark.asyncio
async def test_e2e_linear_equation_rejects_unrelated_input_before_valid_step() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="2x + 5 = 15",
            action="submit_problem",
        )
        assert initial["final_answer_locked"] is True

        unrelated_number = await _post_turn(
            client,
            session_id=session_id,
            message="50",
            action="submit_step",
            student_submitted_step=True,
        )
        assert unrelated_number["final_answer_locked"] is True
        assert unrelated_number["metadata"]["input_relevance"] == "unrelated"
        assert unrelated_number["metadata"]["validation_result"] == (
            "unrelated_numeric_input"
        )
        assert unrelated_number["board"]["metadata"]["current_step_index"] == 0
        assert unrelated_number["display_text"]
        assert unrelated_number["board_actions"]
        assert any(
            action["type"] in {"cross_out", "highlight"}
            for action in unrelated_number["board_actions"]
        )

        final_guess = await _post_turn(
            client,
            session_id=session_id,
            message="4",
            action="submit_step",
            student_submitted_step=True,
        )
        assert final_guess["final_answer_locked"] is True
        assert final_guess["metadata"]["input_relevance"] == "possible_final_answer"
        assert final_guess["metadata"]["validation_result"] == "incorrect_final_answer"
        assert final_guess["board"]["metadata"]["current_step_index"] == 0

        random_text = await _post_turn(
            client,
            session_id=session_id,
            message="banana movie sentence",
            action="submit_step",
            student_submitted_step=True,
        )
        assert random_text["metadata"]["input_relevance"] == "off_topic"
        assert random_text["final_answer_locked"] is True
        assert random_text["board_actions"]

        valid_step = await _post_turn(
            client,
            session_id=session_id,
            message="2x = 10",
            action="submit_step",
            student_submitted_step=True,
        )
        stuck_after_valid_step = await _post_turn(
            client,
            session_id=session_id,
            message="I am stuck",
            action="request_stuck_help",
        )
        session = await _get_session(client, session_id)

    assert valid_step["teaching_mode"] == "step_check"
    assert valid_step["mastery_signal"] == "ready_for_next_step"
    assert valid_step["board"]["metadata"]["current_step_index"] == 1
    assert stuck_after_valid_step["teaching_mode"] == "stuck_help"
    assert stuck_after_valid_step["board"]["metadata"]["current_step_index"] == 1
    assert session["attempts"] == 1
    assert session["wrong_attempts"] == 0
    assert session["final_answer_revealed"] is False


@pytest.mark.asyncio
async def test_e2e_linear_equation_wrong_sign_returns_check_work_metadata() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        await _post_turn(
            client,
            session_id=session_id,
            message="2x + 5 = 15",
            action="submit_problem",
        )
        wrong_sign = await _post_turn(
            client,
            session_id=session_id,
            message="2x = 15 + 5",
            action="submit_step",
            student_submitted_step=True,
            current_state={
                "problem_text": "2x + 5 = 15",
                "current_step_index": 0,
            },
        )

    board_metadata = wrong_sign["board"]["metadata"]
    assert board_metadata["board_type"] == "check_my_work"
    assert board_metadata["screen_state"] == "check_my_work"
    assert board_metadata["problem"] == "2x + 5 = 15"
    assert board_metadata["student_step"] == "2x = 15 + 5"
    assert board_metadata["mistake_location"] == "student_step"
    assert board_metadata["mistake_message"] == "Check your sign here!"
    assert "inverse operation" in board_metadata["corrected_hint"].lower()
    assert wrong_sign["metadata"]["validation_result"] in {
        "incorrect_relevant_step",
        "needs_solver_check",
        "incorrect_step",
    }
    assert wrong_sign["metadata"]["mistake_message"] == "Check your sign here!"
    assert wrong_sign["final_answer_locked"] is True
    assert wrong_sign["board"]["metadata"]["current_step_index"] == 0


@pytest.mark.asyncio
async def test_e2e_line_through_two_points_flow_persists_and_restores() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Find the equation of the line through D(0,1) and E(1,3)",
            action="submit_problem",
        )
        assert initial["teaching_mode"] == "guided_question"
        assert initial["final_answer_locked"] is True
        assert initial["board"]["metadata"]["problem_type"] == "line_through_points"
        assert "y = 2x + 1" not in initial["display_text"]

        step = await _post_turn(
            client,
            session_id=session_id,
            message="m = 2",
            action="submit_step",
            student_submitted_step=True,
        )
        assert step["teaching_mode"] == "step_check"
        assert step["mastery_signal"] == "ready_for_next_step"
        assert step["board"]["items"][-1]["content"] == "Final answer is locked."

        first_hint, partial = await _assert_hint_progression(
            client,
            session_id=session_id,
            locale="km-KH",
        )
        assert first_hint["board"]["items"][-1]["content"] == "Final answer is locked."
        assert partial["display_text"]

        restored = await _get_session(client, session_id)
        restored_hint = await _post_turn(
            client,
            session_id=session_id,
            message="continue",
            action="request_hint",
        )

    assert restored["problem_text"].startswith("Line through")
    assert len(restored["turns"]) == 5
    assert restored_hint["board"]["metadata"]["problem_type"] == "line_through_points"


@pytest.mark.asyncio
async def test_e2e_unsupported_math_fallback_persists_and_restores(monkeypatch) -> None:
    fake_llm = FakeVisualTutorLLMClient(_generic_llm_payload)

    def _handle_with_fake_llm(request: VisualTutorTurnRequest):
        return real_handle_visual_tutor_turn(_guided(request), llm_client=fake_llm)

    monkeypatch.setattr(
        visual_tutor_route_module,
        "handle_visual_tutor_turn",
        _handle_with_fake_llm,
    )
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Solve a + b = 10 for a",
            action="submit_problem",
        )
        assert initial["teaching_mode"] == "guided_question"
        assert initial["final_answer_locked"] is True
        assert initial["metadata"]["planner"] == "visual_tutor_llm_teaching_planner_v1"

        first_hint, partial = await _assert_hint_progression(
            client,
            session_id=session_id,
            locale="km-KH",
        )
        # Recovery turns may use the constrained template path. The student
        # contract is the progressive hint mode and persisted board state, not
        # a particular content-generation implementation.
        assert first_hint["metadata"]["policy_decision"]["teaching_mode"] == "hint"
        assert partial["teaching_mode"] == "partial_solution"

        restored_hint = await _post_turn(
            client,
            session_id=session_id,
            message="restore and continue",
            action="request_hint",
        )
        session = await _get_session(client, session_id)

    assert fake_llm.calls
    assert restored_hint["teaching_mode"] in {"hint", "partial_solution"}
    assert restored_hint["metadata"]["policy_decision"]["teaching_mode"] in {
        "hint",
        "partial_solution",
    }
    assert len(session["turns"]) == 5
    assert len(session["board_states"]) == 5


@pytest.mark.asyncio
async def test_e2e_khmer_math_prompt_flow_persists_and_restores() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="សូមដោះស្រាយ 2x + 5 = 15",
            action="submit_problem",
            locale="km-KH",
        )
        assert initial["teaching_mode"] == "guided_question"
        assert initial["final_answer_locked"] is True
        assert initial["metadata"]["policy"]["use_khmer_explanation"] is True
        assert initial["student_task"]

        step = await _post_turn(
            client,
            session_id=session_id,
            message="2x = 10",
            action="submit_step",
            student_submitted_step=True,
            locale="km-KH",
        )

        first_hint, partial = await _assert_hint_progression(
            client,
            session_id=session_id,
            locale="km-KH",
        )
        assert first_hint["metadata"]["policy"]["use_khmer_explanation"] is True
        assert partial["board"]["items"][-1]["content"] == "Final answer is locked."

        session = await _get_session(client, session_id)

    assert step["teaching_mode"] == "step_check"
    assert step["mastery_signal"] == "ready_for_next_step"
    assert len(session["turns"]) == 5
    assert session["board_states"][-1]["type"] == "equation_steps"


@pytest.mark.asyncio
async def test_e2e_llm_final_answer_leak_is_sanitized_and_persisted(
    monkeypatch,
) -> None:
    fake_llm = FakeVisualTutorLLMClient(_leaky_llm_payload)

    def _handle_with_fake_llm(request: VisualTutorTurnRequest):
        return real_handle_visual_tutor_turn(_guided(request), llm_client=fake_llm)

    monkeypatch.setattr(
        visual_tutor_route_module,
        "handle_visual_tutor_turn",
        _handle_with_fake_llm,
    )
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Solve a + b = 10 for a",
            action="submit_problem",
        )
        combined = " ".join(
            [
                initial["spoken_text"],
                initial["display_text"],
                initial["student_task"],
                *(item["content"] for item in initial["board"]["items"]),
            ]
        )
        assert initial["teaching_mode"] == "guided_question"
        assert initial["final_answer_locked"] is True
        assert "10 - b" not in combined
        assert initial["metadata"]["sanitization"]["applied"] is True

        first_hint, partial = await _assert_hint_progression(
            client, session_id=session_id
        )
        assert "10 - b" not in first_hint["display_text"]
        assert "10 - b" not in partial["display_text"]

        restored = await _get_session(client, session_id)

    assert fake_llm.calls
    assert len(restored["turns"]) == 4
    assert (
        restored["turns"][0]["response"]["metadata"]["sanitization"]["applied"] is True
    )
    assert (
        restored["board_states"][0]["items"][0]["content"] == "Final answer is locked."
    )


@pytest.mark.asyncio
async def test_e2e_linear_equation_stuck_help_is_not_treated_as_step() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Solve 2x + 5 = 15",
            action="submit_problem",
        )
        stuck = await _post_turn(
            client,
            session_id=session_id,
            message="I am stuck",
            action="submit_step",
            student_submitted_step=True,
        )
        restored_hint = await _post_turn(
            client,
            session_id=session_id,
            message="continue",
            action="request_hint",
        )
        session = await _get_session(client, session_id)

    assert initial["teaching_mode"] == "guided_question"
    assert initial["final_answer_locked"] is True
    assert stuck["teaching_mode"] == "stuck_help"
    assert stuck["final_answer_locked"] is True
    assert stuck["metadata"]["policy"]["detected_intent"] == "stuck"
    assert stuck["mastery_signal"] == "needs_hint"
    assert stuck["board"]["type"] == "equation_steps"
    assert stuck["board"]["items"][-1]["content"] == "Final answer is locked."
    assert restored_hint["final_answer_locked"] is True
    assert session["attempts"] == 0
    assert session["hint_count"] >= 1
    assert len(session["turns"]) == 3
    assert len(session["board_states"]) == 3
    assert session["messages"][-4]["content"] == "I am stuck"


@pytest.mark.asyncio
async def test_e2e_line_through_two_points_stuck_help_restores() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Find the equation of the line through D(0,1) and E(1,3)",
            action="submit_problem",
        )
        stuck = await _post_turn(
            client,
            session_id=session_id,
            message="I don't understand",
            action="submit_step",
            student_submitted_step=True,
        )
        restored = await _get_session(client, session_id)
        restored_hint = await _post_turn(
            client,
            session_id=session_id,
            message="hint after restore",
            action="request_hint",
        )

    assert initial["board"]["metadata"]["problem_type"] == "line_through_points"
    assert initial["final_answer_locked"] is True
    assert "y = 2x + 1" not in initial["display_text"]
    assert stuck["teaching_mode"] == "stuck_help"
    assert stuck["final_answer_locked"] is True
    assert stuck["metadata"]["policy"]["detected_intent"] == "stuck"
    assert stuck["board"]["metadata"]["problem_type"] == "line_through_points"
    assert stuck["board"]["items"][-1]["content"] == "Final answer is locked."
    assert restored["attempts"] == 0
    assert len(restored["turns"]) == 2
    assert restored_hint["board"]["metadata"]["problem_type"] == "line_through_points"
    assert restored_hint["final_answer_locked"] is True


@pytest.mark.asyncio
async def test_e2e_new_problem_resets_session_state_before_stuck_help() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        await _post_turn(
            client,
            session_id=session_id,
            message="2x + 5 = 15",
            action="submit_problem",
        )
        await _post_turn(
            client,
            session_id=session_id,
            message="help me",
            action="request_stuck_help",
        )
        unlocked_old_problem = await _post_turn(
            client,
            session_id=session_id,
            message="help me",
            action="request_stuck_help",
        )
        assert unlocked_old_problem["teaching_mode"] == "partial_solution"

        line_initial = await _post_turn(
            client,
            session_id=session_id,
            message="Find the equation of the line through D(0,1) and E(1,3)",
            action="submit_problem",
        )
        line_stuck = await _post_turn(
            client,
            session_id=session_id,
            message="I can't solve this",
            action="request_stuck_help",
        )
        restored = await _get_session(client, session_id)

    assert line_initial["teaching_mode"] == "guided_question"
    assert line_initial["final_answer_locked"] is True
    assert line_initial["board"]["title"] == "Line Equation"
    assert line_stuck["teaching_mode"] == "stuck_help"
    assert line_stuck["final_answer_locked"] is True
    assert line_stuck["board"]["title"] == "Line Equation"
    assert line_stuck["board"]["metadata"]["feedback"] == "stuck_help"
    assert line_stuck["display_text"]
    assert restored["problem_text"].startswith("Line through")
    assert restored["hint_count"] == 1
    assert restored["attempts"] == 0
    assert restored["final_answer_revealed"] is False


@pytest.mark.asyncio
async def test_e2e_quadratic_repeated_stuck_unlocks_partial_not_final() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Solve x^2 - 5x + 6 = 0",
            action="submit_problem",
        )
        first_stuck = await _post_turn(
            client,
            session_id=session_id,
            message="help me",
            action="request_stuck_help",
        )
        partial = await _post_turn(
            client,
            session_id=session_id,
            message="I can't solve this",
            action="submit_step",
            student_submitted_step=True,
        )
        requested_answer = await _post_turn(
            client,
            session_id=session_id,
            message="show answer",
            action="request_final_answer",
        )
        allowed_answer = await _post_turn(
            client,
            session_id=session_id,
            message="show answer",
            action="request_final_answer",
            allow_final_answer=True,
        )
        session = await _get_session(client, session_id)

    assert initial["teaching_mode"] == "guided_question"
    assert initial["final_answer_locked"] is True
    assert first_stuck["teaching_mode"] == "stuck_help"
    assert first_stuck["final_answer_locked"] is True
    assert partial["teaching_mode"] == "partial_solution"
    assert partial["final_answer_locked"] is True
    assert "x = 2" not in partial["display_text"]
    assert "x = 3" not in partial["display_text"]
    assert requested_answer["final_answer_locked"] is False
    assert "x = 2" in requested_answer["display_text"]
    assert "x = 3" in requested_answer["display_text"]
    assert allowed_answer["final_answer_locked"] is False
    assert "x = 2" in allowed_answer["display_text"]
    assert "x = 3" in allowed_answer["display_text"]
    assert session["attempts"] == 0
    assert session["hint_count"] >= 2
    assert len(session["turns"]) == 5
    assert len(session["board_states"]) == 5


@pytest.mark.asyncio
async def test_e2e_khmer_math_stuck_help_persists_and_restores() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="សូមដោះស្រាយ 2x + 5 = 15",
            action="submit_problem",
            locale="km-KH",
        )
        stuck = await _post_turn(
            client,
            session_id=session_id,
            message="ខ្ញុំមិនយល់",
            action="submit_step",
            student_submitted_step=True,
            locale="km-KH",
        )
        restored = await _get_session(client, session_id)
        restored_hint = await _post_turn(
            client,
            session_id=session_id,
            message="ជួយខ្ញុំផង",
            action="request_stuck_help",
            locale="km-KH",
        )

    assert initial["metadata"]["policy"]["use_khmer_explanation"] is True
    assert stuck["teaching_mode"] == "stuck_help"
    assert stuck["final_answer_locked"] is True
    assert stuck["metadata"]["policy"]["detected_intent"] == "stuck"
    assert stuck["metadata"]["policy"]["use_khmer_explanation"] is True
    assert stuck["display_text"]
    assert restored["attempts"] == 0
    assert len(restored["turns"]) == 2
    assert restored_hint["teaching_mode"] == "partial_solution"
    assert restored_hint["final_answer_locked"] is True


@pytest.mark.asyncio
async def test_e2e_unsupported_problem_stuck_asks_guiding_question_and_persists(
    monkeypatch,
) -> None:
    fake_llm = FakeVisualTutorLLMClient(_generic_llm_payload)

    def _handle_with_fake_llm(request: VisualTutorTurnRequest):
        return real_handle_visual_tutor_turn(_guided(request), llm_client=fake_llm)

    monkeypatch.setattr(
        visual_tutor_route_module,
        "handle_visual_tutor_turn",
        _handle_with_fake_llm,
    )
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        session_id = await _create_session(client)
        initial = await _post_turn(
            client,
            session_id=session_id,
            message="Solve a + b = 10 for a",
            action="submit_problem",
        )
        stuck = await _post_turn(
            client,
            session_id=session_id,
            message="I am stuck",
            action="submit_step",
            student_submitted_step=True,
        )
        restored = await _get_session(client, session_id)
        restored_stuck = await _post_turn(
            client,
            session_id=session_id,
            message="help me",
            action="request_stuck_help",
        )

    assert initial["metadata"]["planner"] == "visual_tutor_llm_teaching_planner_v1"
    assert initial["final_answer_locked"] is True
    assert stuck["teaching_mode"] == "stuck_help"
    assert stuck["final_answer_locked"] is True
    assert stuck["metadata"]["policy"]["detected_intent"] == "stuck"
    assert stuck["student_task"]
    assert stuck["board"]["items"]
    assert restored["attempts"] == 0
    assert len(restored["turns"]) == 2
    assert restored_stuck["teaching_mode"] == "partial_solution"
    assert restored_stuck["final_answer_locked"] is True
    assert fake_llm.calls
