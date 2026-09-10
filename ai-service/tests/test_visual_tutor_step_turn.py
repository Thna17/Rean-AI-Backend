"""Integration tests for the additive subject-expert step endpoint."""

from __future__ import annotations

from copy import deepcopy

import pytest
from fastapi import HTTPException

from api.models.visual_tutor import (
    VisualTutorSession,
    VisualTutorStepTurnRequest,
)
from api.routes.visual_tutor import (
    _public_expert_step_response,
    submit_visual_tutor_step_turn,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_step_turn


class _StepStore:
    """Small in-memory store exposing only the step endpoint's dependency API."""

    def __init__(self, session: VisualTutorSession) -> None:
        self.session = session
        self.persisted_evaluation: dict[str, object] | None = None

    async def get_session(self, session_id: str) -> VisualTutorSession | None:
        return self.session if session_id == self.session.session_id else None

    async def persist_expert_step_state(
        self,
        *,
        session_id: str,
        teaching_sequence: list[dict[str, object]],
        current_step_index: int,
        evaluation: dict[str, object] | None,
        expert_metadata: dict[str, object],
        user_id: str,
        expected_expert_step_version: int,
    ) -> VisualTutorSession:
        assert session_id == self.session.session_id
        assert user_id == self.session.user_id
        assert expected_expert_step_version == self.session.expert_step_version
        self.session.teaching_sequence = deepcopy(teaching_sequence)
        self.session.current_step_index = current_step_index
        self.session.expert_metadata = deepcopy(expert_metadata)
        self.persisted_evaluation = deepcopy(evaluation)
        if evaluation is not None:
            self.session.step_evaluations.append(deepcopy(evaluation))
        self.session.expert_step_version += 1
        return self.session


def _session(*, subject: str = "Physics") -> VisualTutorSession:
    return VisualTutorSession(
        session_id="physics-session",
        user_id="student-1",
        subject=subject,
        grade_level="Grade 10",
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
        created_at="2026-08-26T00:00:00+00:00",
        updated_at="2026-08-26T00:00:00+00:00",
    )


@pytest.mark.asyncio
async def test_step_turn_builds_a_physics_sequence_and_resumes_it() -> None:
    initial = VisualTutorStepTurnRequest(
        user_id="student-1",
        session_id="physics-session",
        subject="physics",
    )
    first = await handle_visual_tutor_step_turn(
        initial,
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
    )

    assert first.total_steps == 6
    assert first.current_step["visualization_type"] == "scenario"
    assert first.expert_metadata["expert"] == "PhysicsExpert"

    resumed = await handle_visual_tutor_step_turn(
        initial.model_copy(update={"action": "skip"}),
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
        existing_sequence=first.teaching_sequence,
        current_step_index=first.current_step_index,
    )
    assert resumed.current_step_index == 1
    assert resumed.current_step["visualization_type"] == "free_body_diagram"


@pytest.mark.asyncio
async def test_step_turn_inserts_renderer_compatible_reteach_step() -> None:
    initial = await handle_visual_tutor_step_turn(
        VisualTutorStepTurnRequest(
            user_id="student-1",
            session_id="physics-session",
            subject="physics",
        ),
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
    )
    sequence = deepcopy(initial.teaching_sequence)
    sequence[0]["content"]["expected_answer"] = "a net force changes velocity"
    request = VisualTutorStepTurnRequest(
        user_id="student-1",
        session_id="physics-session",
        subject="physics",
        step_id=sequence[0]["step_id"],
        message="an unrelated answer",
        expected_answer="a net force changes velocity",
    )

    response = await handle_visual_tutor_step_turn(
        request,
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
        existing_sequence=sequence,
    )

    assert response.recommended_action == "reteach"
    assert response.current_step["step_id"].endswith("_reteach")
    assert response.current_step["content"]["renderer"] == "RichMediaCanvas"


@pytest.mark.asyncio
async def test_client_cannot_supply_rubric_or_evaluate_an_inactive_step() -> None:
    initial = VisualTutorStepTurnRequest(
        user_id="student-1", session_id="physics-session", subject="physics"
    )
    plan = await handle_visual_tutor_step_turn(
        initial,
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
    )
    forged = initial.model_copy(
        update={
            "step_id": plan.current_step["step_id"],
            "message": "anything",
            "expected_answer": "anything",
        }
    )
    protected = await handle_visual_tutor_step_turn(
        forged,
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
        existing_sequence=plan.teaching_sequence,
    )
    assert protected.recommended_action == "await_rubric"
    assert protected.current_step_index == 0

    stale = forged.model_copy(update={"step_id": "not-the-active-step"})
    with pytest.raises(ValueError, match="not the active"):
        await handle_visual_tutor_step_turn(
            stale,
            problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
            existing_sequence=plan.teaching_sequence,
        )


@pytest.mark.asyncio
async def test_public_step_response_does_not_leak_server_rubrics() -> None:
    response = await handle_visual_tutor_step_turn(
        VisualTutorStepTurnRequest(
            user_id="student-1", session_id="physics-session", subject="physics"
        ),
        problem_text="A 5 kg box is pushed with 20 N on a horizontal surface.",
    )
    response.teaching_sequence[0]["content"]["expected_answer"] = "secret answer"
    response.teaching_sequence[0]["content"]["reteach"] = {
        "interaction": {"expected_answer": "another secret"}
    }

    public = _public_expert_step_response(response)
    assert "expected_answer" not in str(public.model_dump())


@pytest.mark.asyncio
async def test_step_endpoint_authenticates_owns_and_persists_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "step-token")
    store = _StepStore(_session())
    request = VisualTutorStepTurnRequest(
        user_id="student-1",
        session_id="physics-session",
        subject="physics",
        action="skip",
    )

    response = await submit_visual_tutor_step_turn(
        request,
        x_visual_tutor_user_id="student-1",
        x_visual_tutor_internal_token="step-token",
        store=store,  # type: ignore[arg-type]
    )

    assert response.current_step_index == 1
    assert len(store.session.teaching_sequence) == 6
    assert store.session.expert_metadata["subject"] == "physics"


@pytest.mark.asyncio
async def test_step_endpoint_rejects_subject_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_INTERNAL_TOKEN", "step-token")
    request = VisualTutorStepTurnRequest(
        user_id="student-1",
        session_id="physics-session",
        subject="chemistry",
    )

    with pytest.raises(HTTPException) as exc_info:
        await submit_visual_tutor_step_turn(
            request,
            x_visual_tutor_user_id="student-1",
            x_visual_tutor_internal_token="step-token",
            store=_StepStore(_session()),  # type: ignore[arg-type]
        )

    assert exc_info.value.status_code == 422
