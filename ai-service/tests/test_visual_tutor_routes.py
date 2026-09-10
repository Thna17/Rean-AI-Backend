import json
import os

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from api.models.visual_tutor import (
    VisualTutorSession,
    VisualTutorSessionCreateRequest,
    VisualTutorSessionSummary,
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


class FakeVisualTutorStore:
    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}

    async def create_session(
        self,
        request: VisualTutorSessionCreateRequest,
        *,
        session_id: str | None = None,
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


    async def get_session(self, session_id: str) -> VisualTutorSession | None:
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
        understanding = response.metadata.get("problem_understanding")
        doc["problem_type"] = (
            (
                (understanding or {}).get("problem_type")
                if isinstance(understanding, dict)
                else None
            )
            or response.metadata.get("problem_type")
            or response.board.metadata.get("problem_type")
            or (None if is_new_problem else doc.get("problem_type"))
        )
        doc["current_step_index"] = response.board.metadata.get(
            "current_step_index",
            request.current_state.current_step_index,
        )
        doc["solver_facts"] = response.metadata.get("solver_facts") or (
            None if is_new_problem else doc.get("solver_facts")
        )
        doc["expected_step"] = (
            response.metadata.get("expected_step")
            or response.board.metadata.get("expected_step")
            or (
                response.interaction.prompt
                if response.interaction is not None
                else response.student_task
            )
            or (None if is_new_problem else doc.get("expected_step"))
        )
        final_answer = response.metadata.get(
            "final_answer"
        ) or response.board.metadata.get("final_answer")
        if is_new_problem:
            doc["solved_variables"] = {}
        if isinstance(final_answer, str) and "=" in final_answer:
            variable, value = final_answer.split("=", 1)
            doc["solved_variables"][variable.strip()] = value.strip()
        if is_new_problem:
            doc["hint_count"] = 0
        elif request.action.value == "request_hint":
            doc["hint_count"] = (
                max(doc["hint_count"], request.current_state.hint_count) + 1
            )
        else:
            doc["hint_count"] = max(doc["hint_count"], request.current_state.hint_count)
        if is_new_problem:
            doc["stuck_count"] = 0
            doc["attempts"] = 0
            doc["wrong_attempts"] = 0
        if (
            response.student_intent.value == "stuck"
            or request.action.value == "request_stuck_help"
        ):
            doc["stuck_count"] += 1
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


class FakeLearnerMemoryStore:
    """Durable-store test double; route tests must not open a real Mongo client."""

    def __init__(self) -> None:
        self.profiles: dict[tuple[str, str, str], dict] = {}

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


def _make_app(store: FakeVisualTutorStore | None = None) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def trusted_gateway_headers(request, call_next):
        # Route tests exercise the private AI-service boundary through a fake
        # durable store. Production headers are still mandatory; inject only
        # the test gateway identity rather than bypassing auth.
        headers = list(request.scope["headers"])
        header_names = {name.lower() for name, _value in headers}
        if b"x-visual-tutor-internal-token" not in header_names:
            headers.append((b"x-visual-tutor-internal-token", b"test-visual-tutor-token"))
        if b"x-visual-tutor-user-id" not in header_names:
            headers.append((b"x-visual-tutor-user-id", b"student-1"))
        # This file asserts server-side replay/persistence internals. It uses
        # the explicit development-only compatibility header instead of
        # treating the production Flutter response as legacy.
        if b"x-visual-tutor-api-compatibility-version" not in header_names:
            headers.append((b"x-visual-tutor-api-compatibility-version", b"0"))
        request.scope["headers"] = headers
        return await call_next(request)

    app.include_router(router)
    if store is not None:
        app.dependency_overrides[get_visual_tutor_store] = lambda: store
    app.dependency_overrides[get_learner_memory_store] = FakeLearnerMemoryStore
    return app


@pytest.fixture(autouse=True)
def _visual_tutor_gateway_token(monkeypatch):
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "test-visual-tutor-token")


async def _create_session(
    client: AsyncClient,
    *,
    user_id: str = "student-1",
    subject: str = "Mathematics",
    topic: str | None = "Linear Equations",
) -> str:
    response = await client.post(
        "/api/v1/visual_tutor/sessions",
        json={"user_id": user_id, "subject": subject, "topic": topic},
    )
    assert response.status_code == 200
    return response.json()["session_id"]


def _assert_target_screen_contract(data: dict, expected_screen_state: str) -> None:
    assert data["screen_state"] == expected_screen_state
    assert isinstance(data["tutor_status"], str)
    assert data["tutor_status"]
    assert isinstance(data["speech"], dict)
    assert isinstance(data["board"], dict)
    assert isinstance(data["interaction"], dict)
    assert isinstance(data["quick_actions"], list)
    assert isinstance(data["metadata"], dict)
    assert data["metadata"]["screen_state"] == expected_screen_state


@pytest.mark.asyncio
async def test_visual_tutor_turn_greeting_when_no_problem() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={"user_id": "student-1", "action": "start"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "greeting"
    assert data["final_answer_locked"] is True
    assert "What lesson or problem" in data["spoken_text"]
    assert data["board"]["type"] == "formula_card"
    _assert_target_screen_contract(data, "home")


@pytest.mark.asyncio
async def test_visual_tutor_first_linear_equation_locks_answer() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "message": "Solve 2x + 5 = 15",
                "action": "submit_problem",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert data["teaching_mode"] == "guided_question"
    assert data["final_answer_locked"] is True
    assert data["board"]["type"] == "equation_steps"
    assert data["board"]["items"][0]["content"] == "2x + 5 = 15"
    assert data["board"]["items"][-1]["content"] == "Final answer is locked."
    assert "x = 5" not in data["display_text"]
    assert data["metadata"]["policy_reason"] == "ask_guiding_question_first"


@pytest.mark.asyncio
async def test_visual_tutor_turn_replays_idempotent_retry_without_new_board_version() -> (
    None
):
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        payload = {
            "user_id": "student-1",
            "session_id": session_id,
            "subject": "Mathematics",
            "topic": "Linear Equations",
            "message": "Solve 2x + 5 = 15",
            "action": "submit_problem",
            "idempotency_key": "client-turn-1",
            "metadata": {
                "client_turn_id": "client-turn-1",
                "client_board_version": 0,
            },
        }
        first_response = await client.post("/api/v1/visual_tutor/turn", json=payload)
        retry_response = await client.post("/api/v1/visual_tutor/turn", json=payload)
        session_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert first_response.status_code == 200
    assert retry_response.status_code == 200
    first = first_response.json()
    retry = retry_response.json()
    session = session_response.json()
    assert retry["turn_id"] == first["turn_id"]
    assert retry["board_version"] == first["board_version"] == 1
    assert retry["base_board_version"] == first["base_board_version"] == 0
    # PublicVisualTutorSession is a minimal resume DTO and does not expose
    # raw turn history; board_version is the student-safe idempotency signal.
    assert session["board_version"] == 1


@pytest.mark.asyncio
async def test_visual_tutor_turn_rejects_stale_client_board_version() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        first_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "Solve 2x + 5 = 15",
                "action": "submit_problem",
                "metadata": {"client_board_version": 0},
            },
        )
        stale_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "hint",
                "action": "request_hint",
                "metadata": {"client_board_version": 0},
            },
        )

    assert first_response.status_code == 200
    assert stale_response.status_code == 409
    assert stale_response.json()["detail"]["expected_board_version"] == 1
    assert stale_response.json()["detail"]["client_board_version"] == 0


@pytest.mark.asyncio
async def test_visual_tutor_linear_equation_includes_curriculum_metadata() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "message": "Solve 2x + 5 = 15",
                "action": "submit_problem",
                "metadata": {"grade_level_hint": "grade 10"},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["final_answer_locked"] is True
    assert (
        "math.g10.linear_equations.one_variable"
        in data["metadata"]["curriculum_chunk_ids"]
    )
    assert "ax + b = c" in data["metadata"]["formulas"]
    assert data["metadata"]["curriculum_confidence"] > 0
    assert data["metadata"]["curriculum_sources"]
    assert "x = 5" not in str(data["metadata"]["curriculum_context"])


@pytest.mark.asyncio
async def test_visual_tutor_line_through_points_asks_for_slope_first() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "message": "Find the equation of the line through D(0,1) and E(1,3)",
                "action": "submit_problem",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "guided_question"
    assert data["final_answer_locked"] is True
    assert data["board"]["type"] == "equation_steps"


@pytest.mark.asyncio
async def test_visual_tutor_line_through_points_retrieves_line_context() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client, topic="Coordinate Geometry")
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Coordinate Geometry",
                "message": "Find the equation of the line through D(0,1) and E(1,3)",
                "action": "submit_problem",
                "metadata": {"grade": 10},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["final_answer_locked"] is True
    assert (
        "math.g10.coordinate_geometry.slope" in data["metadata"]["curriculum_chunk_ids"]
    )
    assert "m = (y2 - y1) / (x2 - x1)" in data["metadata"]["formulas"]


@pytest.mark.asyncio
async def test_visual_tutor_function_problem_retrieves_function_context() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client, topic="Functions")
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Functions",
                "message": "Find the domain of f(x) = 1 / (x - 2)",
                "action": "submit_problem",
                "metadata": {"grade": 11},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["final_answer_locked"] is True
    assert "math.g11.functions.domain_range" in data["metadata"]["curriculum_chunk_ids"]
    assert data["metadata"]["khmer_terms"]["function"] == "អនុគមន៍"


@pytest.mark.asyncio
async def test_visual_tutor_graph_prompt_returns_graph_based_board() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client, topic="Functions")
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Functions",
                "message": "Show graph of f(x)=sin(x)",
                "action": "submit_problem",
                "metadata": {"grade": 11},
            },
        )

    assert response.status_code == 200
    data = response.json()
    board_metadata = data["board"]["metadata"]
    graph_elements = board_metadata["graph_elements"]
    assert data["final_answer_locked"] is True
    assert data["board"]["type"] == "graph_hint"
    assert board_metadata["board_type"] == "graph_based"
    assert board_metadata["screen_state"] == "graph_based"
    _assert_target_screen_contract(data, "graph_based")
    assert graph_elements["axes"] is True
    assert graph_elements["function_name"] == "sin(x)"
    assert len(graph_elements["curve_points"]) > 3
    assert graph_elements["labels"]["peak"] == "Peak"
    assert graph_elements["labels"]["trough"] == "Trough"
    assert graph_elements["labels"]["amplitude"] == "Amplitude = 1"
    assert graph_elements["highlighted_point"]["id"] == "graph-frequency-point"
    assert graph_elements["instruction"] == "Drag the point to change the frequency"
    assert data["interaction"]["type"] == "text_response"
    assert "show_visually" in data["allowed_actions"]


@pytest.mark.asyncio
async def test_visual_tutor_unsupported_topic_curriculum_empty_without_crash() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client, topic="Unknown Topic")
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Unknown Topic",
                "message": "Explain a strange math puzzle with no known topic",
                "action": "submit_problem",
                "metadata": {"grade": 12},
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["final_answer_locked"] is True
    assert data["metadata"]["curriculum_chunk_ids"] == []
    assert data["metadata"]["curriculum_confidence"] == 0
    _assert_target_screen_contract(data, "unsupported_problem")
    assert data["metadata"]["problem_understanding"]["problem_type"] == "unsupported"
    # "Unknown Topic" has no reviewed curriculum lesson at all, so the
    # curriculum-grounding gate (not the generic unsupported-problem-type
    # gate) is what actually blocks it -- same student-facing screen via
    # _friendly_unsupported_turn either way, but a more precise reason.
    assert data["metadata"]["generation_path"] == "curriculum_recovery"
    assert data["metadata"]["fallback_reason"] == "reviewed_curriculum_required"
    assert data["board"]["metadata"]["problem_type"] == "unsupported"
    assert data["board"]["metadata"]["known_solver_available"] is False
    assert data["board_actions"]
    assert data["interaction"]["input_enabled"] is True
    assert data["interaction"]["prompt"]
    assert "unsupported" not in data["spoken_text"].lower()
    assert "No deterministic solver" not in data["spoken_text"]
    assert data["teaching_mode"] == "guided_question"
    assert data["student_task"]


@pytest.mark.asyncio
async def test_visual_tutor_line_through_points_accepts_slope_step() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "m = 2",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": "Find the equation of the line through D(0,1) and E(1,3)",
                    "current_step_index": 2,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "step_check"
    assert data["mastery_signal"] == "ready_for_next_step"
    assert data["final_answer_locked"] is True
    assert data["board"]["metadata"]["current_step_index"] == 3
    assert "m = 2" in json.dumps(data["board_actions"])
    assert data["student_task"]
    assert "y = mx + b" in json.dumps(data["board_actions"])
    assert data["board"]["items"][-1]["content"] == "Final answer is locked."


@pytest.mark.asyncio
async def test_visual_tutor_direct_solve_request_does_not_reveal_final_answer() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "message": "Please solve this fully: 2x + 5 = 15",
                "action": "submit_problem",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "guided_question"
    assert data["final_answer_locked"] is True
    assert data["metadata"]["policy_reason"] == "ask_guiding_question_first"
    assert "x = 5" not in data["spoken_text"]
    assert "x = 5" not in data["display_text"]


@pytest.mark.asyncio
async def test_visual_tutor_hint_does_not_reveal_final_answer() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "hint",
                "action": "request_hint",
                "hint_count": 1,
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "hint_count": 1,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "hint"
    assert data["final_answer_locked"] is True
    assert data["board"]["items"][-1]["status"] == "locked"
    assert "x = 5" not in data["spoken_text"]
    assert "x = 5" not in data["board"]["items"][-1]["content"]


@pytest.mark.asyncio
async def test_visual_tutor_valid_student_step_advances_board() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x = 10",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "current_step_index": 0,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "step_check"
    assert data["mastery_signal"] == "ready_for_next_step"
    assert data["board"]["metadata"]["current_step_index"] == 1
    assert data["board"]["items"][1]["content"] == "2x = 10"
    assert data["board"]["items"][1]["status"] == "complete"
    action_text = " ".join(
        str(action.get("text") or action.get("latex") or "")
        for action in data["board_actions"]
    )
    assert "2x = 10" in action_text
    assert "divide both sides by 2" in action_text
    assert data["final_answer_locked"] is True
    assert data["board"]["items"][-1]["content"] == "Final answer is locked."


@pytest.mark.asyncio
async def test_visual_tutor_final_student_step_completes_linear_equation() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "x = 5",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "current_step_index": 1,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["validation_result"] == "correct_final_step"
    assert data["mastery_signal"] == "mastered"
    assert data["final_answer_locked"] is False
    assert data["board"]["metadata"]["current_step_index"] == 2
    assert data["board"]["items"][-1]["content"] == "x = 5"
    action_text = " ".join(
        str(action.get("text") or action.get("latex") or "")
        for action in data["board_actions"]
    )
    assert "x = 5" in action_text
    assert "2(5) + 5 = 15" in action_text


@pytest.mark.asyncio
async def test_visual_tutor_yes_no_check_does_not_reset_completed_linear_board() -> (
    None
):
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "Yes",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "current_step_index": 2,
                    "final_answer_revealed": True,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["metadata"]["validation_result"] == "understanding_check_yes"
    assert data["metadata"]["policy_reason"] == "understanding_check_response"
    assert data["mastery_signal"] == "mastered"
    assert data["final_answer_locked"] is False
    assert data["board"]["metadata"]["current_step_index"] == 2
    assert data["board"]["items"][-1]["content"] == "x = 5"
    response_text = f"{data['spoken_text']} {data['display_text']}"
    assert "Start by removing" not in response_text
    action_text = " ".join(
        str(action.get("text") or action.get("latex") or "")
        for action in data["board_actions"]
    )
    assert "substitution is true" in action_text


@pytest.mark.asyncio
async def test_visual_tutor_supports_non_x_linear_equation_variable() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        first = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "5a - 8 = 2a + 7",
                "subject": "Mathematics",
                "topic": "Linear Equations",
            },
        )
        step = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "3a = 15",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": "5a - 8 = 2a + 7",
                    "current_step_index": 0,
                },
            },
        )
        final = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "a = 5",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": "5a - 8 = 2a + 7",
                    "current_step_index": 1,
                },
            },
        )

    assert first.status_code == 200
    first_data = first.json()
    assert (
        first_data["metadata"]["policy"]["problem_type"]
        == "linear_equation_one_variable"
    )
    assert (
        first_data["metadata"]["problem_understanding"]["problem_type"]
        == "linear_equation_one_variable"
    )
    assert (
        first_data["metadata"]["problem_understanding"]["extracted_entities"][
            "variable"
        ]
        == "a"
    )
    assert first_data["final_answer_locked"] is True
    first_action_text = " ".join(
        str(action.get("text") or action.get("latex") or "")
        for action in first_data["board_actions"]
    )
    assert "5a - 8 = 2a + 7" in first_action_text
    assert "a = 5" not in first_action_text

    assert step.status_code == 200
    step_data = step.json()
    assert step_data["metadata"]["validation_result"] == "correct_step"
    assert step_data["board"]["metadata"]["current_step_index"] == 1
    assert step_data["board"]["items"][1]["content"] == "3a = 15"

    assert final.status_code == 200
    final_data = final.json()
    assert final_data["metadata"]["validation_result"] == "correct_final_step"
    assert final_data["final_answer_locked"] is False
    assert final_data["board"]["items"][-1]["content"] == "a = 5"


@pytest.mark.asyncio
async def test_visual_tutor_i_tried_message_triggers_step_check() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "I tried 2x = 10. Is this right?",
                "action": "submit_problem",
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "current_step_index": 0,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "step_check"
    assert data["mastery_signal"] == "ready_for_next_step"
    assert data["metadata"]["policy_reason"] == "correct_step_check"
    assert data["board"]["items"][1]["content"] == "2x = 10"


@pytest.mark.asyncio
async def test_visual_tutor_repeated_wrong_attempts_trigger_partial_solution() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "I tried 2x = 15",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "wrong_attempts": 1,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "partial_solution"
    assert data["mastery_signal"] == "misconception"
    assert data["metadata"]["policy_reason"] == "misconception_detected"
    assert data["metadata"]["policy"]["projected_wrong_attempts"] == 2
    assert data["final_answer_locked"] is True
    assert data["board"]["items"][1]["content"] == "2x = 10"
    assert data["board"]["items"][-1]["content"] == "Final answer is locked."
    action_text = " ".join(
        str(action.get("text") or action.get("latex") or "")
        for action in data["board_actions"]
    )
    assert "2x = 10" in action_text
    assert any(action["type"] == "highlight" for action in data["board_actions"])


@pytest.mark.asyncio
async def test_visual_tutor_explain_differently_can_switch_to_khmer() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "សូមពន្យល់ជាភាសាខ្មែរ",
                "locale": "km-KH",
                "action": "explain_differently",
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "hint_count": 1,
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["teaching_mode"] == "hint"
    assert data["final_answer_locked"] is True
    assert data["metadata"]["policy_reason"] == "explain_differently"
    assert data["metadata"]["policy"]["use_khmer_explanation"] is True
    assert data["spoken_text"]
    assert data["board_actions"]
    assert any(action["type"] == "draw_arrow" for action in data["board_actions"])


@pytest.mark.asyncio
async def test_visual_tutor_final_answer_reveals_on_student_request() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        requested_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "show answer",
                "action": "request_final_answer",
                "current_state": {"problem_text": "2x + 5 = 15"},
            },
        )
        allowed_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "show answer",
                "action": "request_final_answer",
                "allow_final_answer": True,
                "current_state": {"problem_text": "2x + 5 = 15"},
            },
        )
        threshold_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "show answer",
                "action": "request_final_answer",
                "current_state": {
                    "problem_text": "2x + 5 = 15",
                    "wrong_attempts": 2,
                },
            },
        )

    assert requested_response.status_code == 200
    requested = requested_response.json()
    assert requested["final_answer_locked"] is False
    assert requested["teaching_mode"] == "full_solution"
    assert requested["board"]["items"][-1]["content"] == "x = 5"

    assert allowed_response.status_code == 200
    allowed = allowed_response.json()
    assert allowed["final_answer_locked"] is False
    assert allowed["teaching_mode"] == "full_solution"
    assert allowed["board"]["items"][-1]["content"] == "x = 5"

    assert threshold_response.status_code == 200
    threshold = threshold_response.json()
    assert threshold["final_answer_locked"] is False
    assert threshold["board"]["items"][-1]["content"] == "x = 5"


@pytest.mark.asyncio
async def test_visual_tutor_session_create_and_restore() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/api/v1/visual_tutor/sessions",
            json={
                "user_id": "student-1",
                "subject": "Mathematics",
                "topic": "Linear Equations",
            },
        )
        session_id = create_response.json()["session_id"]
        restore_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )
        list_response = await client.get(
            "/api/v1/visual_tutor/sessions/user/student-1",
        )

    assert create_response.status_code == 200
    assert restore_response.status_code == 200
    restored = restore_response.json()
    assert restored["session_id"] == session_id
    # PublicVisualTutorSession deliberately omits user_id -- the endpoint is
    # already scoped by the user_id query param plus gateway auth.
    assert restored["subject"] == "Mathematics"
    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1


@pytest.mark.asyncio
async def test_visual_tutor_session_ownership_blocks_other_user() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        create_response = await client.post(
            "/api/v1/visual_tutor/sessions",
            json={"user_id": "student-1", "subject": "Mathematics"},
        )
        session_id = create_response.json()["session_id"]
        restore_response = await client.get(
                f"/api/v1/visual_tutor/sessions/{session_id}",
                params={"user_id": "student-2"},
                headers={"x-visual-tutor-user-id": "student-2"},
            )
        turn_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-2",
                "session_id": session_id,
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )

    assert restore_response.status_code == 403
    assert turn_response.status_code == 403


@pytest.mark.asyncio
async def test_visual_tutor_turn_rejects_unknown_session_id() -> None:
    app = _make_app(FakeVisualTutorStore())

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": "missing-session",
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_visual_tutor_turn_persists_session_state() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        turn_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )
        session_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert turn_response.status_code == 200
    assert session_response.status_code == 200
    session = session_response.json()
    assert session["problem_text"] == "2x + 5 = 15"
    assert session["wrong_attempts"] == 0
    # normalized_problem/problem_type/expected_step/solved_variables/
    # stuck_count/mastery_signal/turns/messages are server-only replay and
    # solver state -- PublicVisualTutorSession deliberately does not expose
    # them (see public_response.py). Verify them against the durable store
    # directly instead of the public resume endpoint.
    internal_session = await store.get_session(session_id)
    assert internal_session.normalized_problem == "2*x + 5 = 15"
    assert internal_session.problem_type == "linear_equation_one_variable"
    assert internal_session.expected_step
    assert internal_session.solved_variables == {}
    assert internal_session.stuck_count == 0
    assert internal_session.mastery_signal == "exploring"
    assert len(internal_session.turns) == 1
    assert len(internal_session.messages) == 2


@pytest.mark.asyncio
async def test_visual_tutor_persists_current_step_index_after_valid_step() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )
        step_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Linear Equations",
                "message": "2x = 10",
                "action": "submit_step",
                "student_submitted_step": True,
            },
        )
        session_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert step_response.status_code == 200
    assert session_response.status_code == 200
    step_data = step_response.json()
    session = session_response.json()
    assert step_data["board"]["metadata"]["current_step_index"] == 1
    assert session["current_step_index"] == 1
    assert session["problem_text"] == "2x + 5 = 15"
    # Raw turn replay history is server-only; check it against the durable
    # store rather than the public resume endpoint (see public_response.py).
    internal_session = await store.get_session(session_id)
    assert internal_session.turns[-1]["response"]["metadata"]["orchestrator_flow"][-1] == (
        "return_response"
    )


@pytest.mark.asyncio
async def test_visual_tutor_create_session_with_canvas_defaults() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        session_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    # These are server-only replay/canvas defaults -- PublicVisualTutorSession
    # does not expose them (see public_response.py) -- so assert against the
    # durable store's full record, not the public resume endpoint.
    session = await store.get_session(session_id)
    assert session.canvas_state is None
    assert session.canvas_actions == []
    assert session.canvas_states == []
    assert session.problem_type is None
    assert session.expected_step is None
    assert session.solved_variables == {}
    assert session.wrong_attempts == 0
    assert session.stuck_count == 0
    assert session.locked_canvas_element_ids == []
    assert session.revealed_canvas_element_ids == []
    assert session.current_focus_element_id is None
    assert session.teaching_stage is None
    assert session.stage_state is None
    assert session.lesson_state is None
    assert session.teaching_board_state is None
    assert session.teaching_board_states == []
    assert session.visible_board_elements == []
    assert session.hidden_element_ids == []
    assert session.locked_element_ids == []
    assert session.played_action_ids == []
    assert session.pending_interaction is None
    assert session.allowed_actions == []
    assert session.student_responses == []
    assert session.voice_tts_metadata == {}
    assert session.curriculum_chunk_ids == []
    # The public resume DTO exposes only the minimal student-safe subset.
    public = session_response.json()
    assert public["curriculum_chunk_ids"] == []


@pytest.mark.asyncio
async def test_visual_tutor_restore_returns_canvas_state() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )
    # canvas_state/canvas_states are server-only replay state --
    # PublicVisualTutorSession does not expose them (see public_response.py)
    # -- so assert against the durable store's full record.
    restored = await store.get_session(session_id)
    assert restored.canvas_state["canvas_actions"]
    assert restored.canvas_states[0]["canvas_actions"]
    assert any(
        action["type"] == "write_equation"
        for action in restored.canvas_state["canvas_actions"]
    )
    assert any(
        action["type"] == "highlight"
        for action in restored.canvas_state["canvas_actions"]
    )


@pytest.mark.asyncio
async def test_visual_tutor_persists_first_live_teaching_stage_turn() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client, topic="Coordinate Geometry")
        turn_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "subject": "Mathematics",
                "topic": "Coordinate Geometry",
                "message": "Find the equation of the line through D(0,1) and E(1,3)",
                "action": "submit_problem",
            },
        )
        restored_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert turn_response.status_code == 200
    # Live teaching-stage replay state is server-only -- PublicVisualTutorSession
    # does not expose it (see public_response.py) -- so assert against the
    # durable store's full record, not the public resume endpoint.
    restored = await store.get_session(session_id)
    assert restored.stage_state == "waiting_for_student"
    assert restored.lesson_state in {"ask", "teach"}
    assert restored.teaching_stage["max_actions_before_wait"] >= 1
    assert restored.teaching_board_state["actions"]
    assert restored.visible_board_elements
    assert restored.pending_interaction["type"] == "numeric_input"
    assert restored.pending_interaction["prompt"]
    assert "request_hint" in restored.allowed_actions
    assert "stuck" in restored.allowed_actions
    assert restored.student_responses[0]["content"].startswith("Find the equation")
    assert restored.voice_tts_metadata["speech_text"]
    assert restored.curriculum_chunk_ids
    assert all(
        action["id"] in restored.played_action_ids
        for action in restored.teaching_board_state["actions"]
        if action.get("id")
    )


@pytest.mark.asyncio
async def test_visual_tutor_restore_live_board_does_not_require_action_replay() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client, topic="Coordinate Geometry")
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "Find the equation of the line through D(0,1) and E(1,3)",
                "action": "submit_problem",
            },
        )
        restored_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert restored_response.status_code == 200
    # Board replay state is server-only -- PublicVisualTutorSession does not
    # expose it (see public_response.py) -- so assert against the durable
    # store's full record, not the public resume endpoint.
    restored = await store.get_session(session_id)
    action_ids = [
        action["id"]
        for action in restored.teaching_board_state["actions"]
        if action.get("id")
    ]
    visible_ids = [
        element["id"]
        for element in restored.visible_board_elements
        if element.get("id")
    ]
    assert action_ids
    assert set(action_ids).issubset(set(restored.played_action_ids))
    assert visible_ids
    assert set(visible_ids).isdisjoint(set(restored.hidden_element_ids))


@pytest.mark.asyncio
async def test_visual_tutor_requested_final_answer_remains_revealed_after_restore() -> (
    None
):
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "show answer",
                "action": "request_final_answer",
                "current_state": {"problem_text": "2x + 5 = 15"},
            },
        )
        restored_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    public = restored_response.json()
    # final_answer_revealed is part of the minimal public resume DTO.
    assert public["final_answer_revealed"] is True
    # canvas/board replay state is server-only -- PublicVisualTutorSession
    # does not expose it (see public_response.py) -- so assert against the
    # durable store's full record for the rest.
    restored = await store.get_session(session_id)
    visible_final_actions = [
        action
        for action in restored.canvas_state["canvas_actions"]
        if "x = 5" in str(action.get("text") or action.get("latex") or "")
    ]
    assert visible_final_actions
    assert not restored.locked_canvas_element_ids
    assert all(
        element["id"] not in restored.hidden_element_ids
        for element in restored.visible_board_elements
    )


@pytest.mark.asyncio
async def test_visual_tutor_live_session_continues_after_restore() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client, topic="Coordinate Geometry")
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "Find the equation of the line through D(0,1) and E(1,3)",
                "action": "submit_problem",
            },
        )
        restored_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )
        restored = restored_response.json()
        # normalized_problem is server-only and not in PublicVisualTutorSession
        # (see public_response.py); fetch it from the durable store instead.
        restored_internal = await store.get_session(session_id)
        step_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2",
                "action": "submit_step",
                "student_submitted_step": True,
                "current_state": {
                    "problem_text": restored["problem_text"],
                    "normalized_problem": restored_internal.normalized_problem,
                    "current_step_index": restored["current_step_index"],
                    "hint_count": restored["hint_count"],
                    "wrong_attempts": restored["wrong_attempts"],
                    "final_answer_revealed": restored["final_answer_revealed"],
                },
            },
        )
        continued_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert step_response.status_code == 200
    continued = continued_response.json()
    assert continued["current_step_index"] == 1
    # pending_interaction/visible_board_elements/student_responses are
    # server-only replay state -- assert against the durable store.
    continued_internal = await store.get_session(session_id)
    assert continued_internal.pending_interaction["prompt"]
    assert any(
        element.get("text") == "Δy = 2" or element.get("latex") == "\\Delta y = 2"
        for element in continued_internal.visible_board_elements
    )
    assert "2" == continued_internal.student_responses[-1]["content"]


@pytest.mark.asyncio
async def test_visual_tutor_turn_restores_state_from_session() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )
        step_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x = 10",
                "action": "submit_step",
                "student_submitted_step": True,
            },
        )

    assert step_response.status_code == 200
    data = step_response.json()
    assert data["teaching_mode"] == "step_check"
    assert data["board"]["items"][1]["content"] == "2x = 10"


@pytest.mark.asyncio
async def test_visual_tutor_final_step_restores_state_from_session() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x = 10",
                "action": "submit_step",
                "student_submitted_step": True,
            },
        )
        final_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "x = 5",
                "action": "submit_step",
                "student_submitted_step": True,
            },
        )

    assert final_response.status_code == 200
    data = final_response.json()
    assert data["metadata"]["validation_result"] == "correct_final_step"
    assert data["mastery_signal"] == "mastered"
    assert data["final_answer_locked"] is False
    assert data["board"]["metadata"]["current_step_index"] == 2
    assert data["board"]["items"][-1]["content"] == "x = 5"


@pytest.mark.asyncio
async def test_visual_tutor_restore_after_first_step_continues_to_final_answer() -> (
    None
):
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        first_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )
        step_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x = 10",
                "action": "submit_step",
                "student_submitted_step": True,
            },
        )
        restored_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )
        # Snapshot server-only state at this checkpoint now -- reading it
        # after the `async with` block would see state as of the *final*
        # step below, not this intermediate restore point.
        restored_internal = await store.get_session(session_id)
        final_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "x = 5",
                "action": "submit_step",
                "student_submitted_step": True,
            },
        )
        final_session_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert first_response.status_code == 200
    assert step_response.status_code == 200
    assert restored_response.status_code == 200
    assert final_response.status_code == 200
    assert final_session_response.status_code == 200

    restored = restored_response.json()
    assert restored["problem_text"] == "2x + 5 = 15"
    assert restored["current_step_index"] == 1
    assert restored["wrong_attempts"] == 0
    assert restored["final_answer_revealed"] is False
    # Everything below is server-only replay/solver state -- not part of
    # PublicVisualTutorSession (see public_response.py) -- so assert
    # against the durable store's snapshot at this checkpoint instead.
    assert restored_internal.problem_type == "linear_equation_one_variable"
    assert restored_internal.expected_step
    # Not yet the final step at this checkpoint, so nothing is solved yet.
    assert restored_internal.solved_variables == {}
    assert restored_internal.stuck_count == 0
    assert restored_internal.teaching_board_state["elements"]
    assert restored_internal.visible_board_elements
    assert restored_internal.pending_interaction
    assert restored_internal.played_action_ids
    assert restored_internal.solver_facts["solver_name"] == "LinearEquationSolver"
    assert restored_internal.validation_history
    assert restored_internal.validation_history[-1]["validation_result"] in {
        "correct_step",
        "correct_first_step",
        "correct_equivalent_step",
    }
    assert restored_internal.response_source_history
    assert (
        restored_internal.response_source_history[-1]["solver_name"]
        == "LinearEquationSolver"
    )
    assert restored_internal.previous_board_action_ids
    assert restored_internal.board_action_history
    scoped_before_restore = [
        scoped_id
        for entry in restored_internal.board_action_history
        for scoped_id in entry["scoped_action_ids"]
    ]
    assert len(scoped_before_restore) == len(set(scoped_before_restore))

    final_data = final_response.json()
    final_action_ids = [
        action["id"] for action in final_data["board_actions"] if action.get("id")
    ]
    assert final_data["metadata"]["validation_result"] == "correct_final_step"
    assert final_data["mastery_signal"] == "mastered"
    assert final_data["final_answer_locked"] is False
    assert final_data["board"]["metadata"]["current_step_index"] == 2
    assert "linear-original-equation" not in final_action_ids
    assert "linear-step-1-result" not in final_action_ids
    assert "linear-final-equation" in final_action_ids

    final_session = final_session_response.json()
    assert final_session["final_answer_revealed"] is True
    assert final_session["current_step_index"] == 2
    # solved_variables/played_action_ids/validation_history/board_action_history
    # are server-only -- assert against the durable store's full record.
    final_session_internal = await store.get_session(session_id)
    assert final_session_internal.solved_variables == {"x": "5"}
    assert final_session_internal.played_action_ids
    assert final_session_internal.validation_history[-1]["validation_result"] == (
        "correct_final_step"
    )
    scoped_after_final = [
        scoped_id
        for entry in final_session_internal.board_action_history
        for scoped_id in entry["scoped_action_ids"]
    ]
    assert len(scoped_after_final) == len(set(scoped_after_final))


@pytest.mark.asyncio
async def test_visual_tutor_new_problem_clears_stale_board_state() -> None:
    store = FakeVisualTutorStore()
    app = _make_app(store)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        session_id = await _create_session(client)
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x + 5 = 15",
                "action": "submit_problem",
            },
        )
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x = 10",
                "action": "submit_step",
                "student_submitted_step": True,
            },
        )
        new_problem_response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "5a - 8 = 2a + 7",
                "action": "submit_problem",
            },
        )
        restored_response = await client.get(
            f"/api/v1/visual_tutor/sessions/{session_id}",
            params={"user_id": "student-1"},
        )

    assert new_problem_response.status_code == 200
    assert restored_response.status_code == 200
    restored = restored_response.json()
    assert restored["problem_text"] == "5a - 8 = 2a + 7"
    assert restored["current_step_index"] == 0
    assert restored["final_answer_revealed"] is False
    # solved_variables/visible_board_elements are server-only -- assert
    # against the durable store's full record.
    restored_internal = await store.get_session(session_id)
    assert restored_internal.solved_variables == {}
    visible_board_json = json.dumps(restored_internal.visible_board_elements)
    assert "2x + 5 = 15" not in visible_board_json
    assert "2x = 10" not in visible_board_json
    assert "5a - 8 = 2a + 7" in visible_board_json


@pytest.mark.asyncio
async def test_public_turn_contract_exposes_only_current_student_safe_plan() -> None:
    app = _make_app(FakeVisualTutorStore())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x - 5 = 20",
                "action": "submit_problem",
                "metadata": {"public_contract_version": 1},
            },
        )
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "schema_version", "session_id", "turn_id", "board_version",
        "base_board_version", "board_update_mode", "lesson_state",
        "tutor_status", "teaching_plan", "verification", "recovery",
    }
    assert set(data["verification"]) == {
        "status", "verified", "concise_evidence", "student_facing_feedback"
    }
    assert "canvas_actions" not in data
    assert "metadata" not in data
    plan = data["teaching_plan"]
    assert "board_actions" not in plan
    assert plan["active_student_task"]["task_type"] in {
        "conceptual_operation", "equation_transformation"
    }


@pytest.mark.asyncio
async def test_staging_ignores_legacy_compatibility_header_and_returns_compact_turn(monkeypatch) -> None:
    from api.routes.visual_tutor import settings as tutor_settings

    monkeypatch.setattr(tutor_settings, "ENVIRONMENT", "staging")
    app = _make_app(FakeVisualTutorStore())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        session_id = await _create_session(client)
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1",
                "session_id": session_id,
                "message": "2x - 5 = 20",
                "action": "submit_problem",
            },
        )

    assert response.status_code == 200
    assert set(response.json()) == {
        "schema_version", "session_id", "turn_id", "board_version",
        "base_board_version", "board_update_mode", "lesson_state",
        "tutor_status", "teaching_plan", "verification", "recovery",
    }


@pytest.mark.asyncio
async def test_conceptual_operation_answer_is_verified_without_equation_notation() -> None:
    app = _make_app(FakeVisualTutorStore())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        session_id = await _create_session(client)
        await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1", "session_id": session_id,
                "message": "2x - 5 = 20", "action": "submit_problem",
            },
        )
        response = await client.post(
            "/api/v1/visual_tutor/turn",
            json={
                "user_id": "student-1", "session_id": session_id,
                "message": "add 5", "action": "submit_step",
                "client_board_version": 1,
                "metadata": {"public_contract_version": 1},
            },
        )
    assert response.status_code == 200
    verification = response.json()["verification"]
    assert verification["status"] == "correct"
    assert verification["verified"] is True
