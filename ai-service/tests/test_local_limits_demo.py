"""Regression tests for the deterministic Grade 12 Limits local MVP flow."""
from __future__ import annotations

import json

import httpx
import pytest

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest, VisualTutorTurnState
from api.services.visual_tutor.local_limits_demo import build_local_limits_demo_turn, matches_local_limits_demo
from api.services.visual_tutor.local_limits_deepseek_planner import bounded_limits_planner_context
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.public_response import project_public_tutor_turn
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan

_LESSON_ID = "math.g12.lesson1.limits-of-functions"
_VERSION = "local-g12-math-limits-2025-10-01-v1"
_MOMENT = "math.g12.lesson1.limits-of-functions.finite-at-point.01"


@pytest.fixture(autouse=True)
def _local_limits_demo_enabled_by_default(monkeypatch):
    # This file's whole purpose is exercising the scripted demo, which
    # handle_visual_tutor_turn now only reaches behind an explicit opt-in
    # (VISUAL_TUTOR_LOCAL_LIMITS_DEMO_ENABLED, off by default -- see
    # orchestrator.py). Individual tests that specifically want the
    # dynamic-planner path can still override this with their own
    # monkeypatch.setattr call.
    from api.services.visual_tutor.orchestrator import settings as orchestrator_settings

    monkeypatch.setattr(
        orchestrator_settings, "VISUAL_TUTOR_LOCAL_LIMITS_DEMO_ENABLED", True
    )


def _request(*, action: VisualTutorAction = VisualTutorAction.START, message: str = "", step: int = 0, wrong_attempts: int = 0) -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id="test-student", session_id="limits-local-session", subject="Mathematics", topic="Limits of Functions", language_mode="khmer", action=action, message=message,
        current_state=VisualTutorTurnState(lesson_id=_LESSON_ID, current_step_index=step, wrong_attempts=wrong_attempts),
        metadata={"entry_context": "lesson", "is_curriculum_scoped": True, "grade": 12, "subject_id": "math", "topic_id": "math-g12-limits-of-functions", "lesson_id": _LESSON_ID, "teaching_moment_id": _MOMENT, "curriculum_version_id": _VERSION},
    )


def _turn(**kwargs: object):
    return build_local_limits_demo_turn(_request(**kwargs), session_id="limits-local-session")


def _types(response) -> list[str]:
    return [action.type.value for action in response.board_actions]


def test_matches_only_the_explicit_grade_12_limits_local_mvp_scope() -> None:
    assert matches_local_limits_demo(_request()) is True
    assert matches_local_limits_demo(_request().model_copy(update={"topic": "Logic"})) is False


def test_opening_turn_is_small_khmer_first_visible_and_keeps_answer_locked() -> None:
    response = _turn()
    assert response.final_answer_locked is True
    assert response.metadata["local_demo_label"] == "Local curriculum demo"
    assert response.metadata["source_id"] == "provided-pdf-2025-10-01-00007213"
    assert response.metadata["source_page"] == 1
    assert response.student_task == "តើ f(x) ខិតជិតលេខណា នៅពេល x ខិតជិត 1?"
    assert _types(response) == ["write_equation", "show_table", "student_task"]
    assert len(response.board_actions) == 3
    assert response.metadata["waiting_for_student_input"] is True
    plan = validate_teaching_plan(response.metadata["teaching_plan"])
    assert plan.hidden_answer_policy.mode.value == "hidden"
    assert plan.hidden_answer_policy.deterministic_policy_permits_final_reveal is False


def test_correct_response_advances_exactly_one_source_backed_moment() -> None:
    response = _turn(action=VisualTutorAction.SUBMIT_STEP, message="5")
    assert response.authoritative_lesson_state["current_step_index"] == 1
    assert response.final_answer_locked is True
    assert _types(response) == ["transform_equation", "student_task"]
    assert response.student_task == "ចំពោះ x ≠ 1 តើ f(x) សម្រួលបានជា​អ្វី?"
    assert response.metadata["evaluation"] == {"outcome": "correct"}
    assert response.display_text.startswith("ត្រឹមត្រូវ")


@pytest.mark.parametrize("wrong_attempts, outcome", [(0, "incorrect"), (1, "repeated_wrong")])
def test_wrong_and_repeated_wrong_reteach_only_the_current_point(wrong_attempts: int, outcome: str) -> None:
    response = _turn(action=VisualTutorAction.SUBMIT_STEP, message="4", wrong_attempts=wrong_attempts)
    assert response.authoritative_lesson_state["current_step_index"] == 0
    assert response.metadata["evaluation"] == {"outcome": outcome}
    assert _types(response) == ["write_equation", "show_table", "student_task"]
    assert response.final_answer_locked is True


@pytest.mark.parametrize("action, expected_outcome", [(VisualTutorAction.REQUEST_HINT, "hint"), (VisualTutorAction.EXPLAIN_DIFFERENTLY, "explain_differently")])
def test_hint_and_explain_differently_switch_to_approved_symbolic_representation(action, expected_outcome: str) -> None:
    response = _turn(action=action)
    assert response.authoritative_lesson_state["current_step_index"] == 1
    assert response.metadata["evaluation"] == {"outcome": expected_outcome}
    assert _types(response) == ["transform_equation", "student_task"]
    assert response.final_answer_locked is True


@pytest.mark.parametrize("action", [VisualTutorAction.REQUEST_HINT, VisualTutorAction.EXPLAIN_DIFFERENTLY])
def test_hint_or_explain_at_a_symbolic_step_changes_back_to_the_approved_table(action) -> None:
    response = _turn(action=action, step=1)
    assert response.authoritative_lesson_state["current_step_index"] == 1
    assert _types(response) == ["write_equation", "show_table", "student_task"]
    assert response.student_task == "ចំពោះ x ≠ 1 តើ f(x) សម្រួលបានជា​អ្វី?"


def test_show_answer_progresses_before_revealing_the_final_answer() -> None:
    first = _turn(action=VisualTutorAction.REQUEST_FINAL_ANSWER, step=0)
    second = _turn(action=VisualTutorAction.REQUEST_FINAL_ANSWER, step=1)
    final = _turn(action=VisualTutorAction.REQUEST_FINAL_ANSWER, step=2)
    assert first.authoritative_lesson_state["current_step_index"] == 1
    assert second.authoritative_lesson_state["current_step_index"] == 2
    assert _types(first) == ["transform_equation", "student_task"]
    assert _types(second) == ["transform_equation", "student_task"]
    assert first.final_answer_locked is second.final_answer_locked is True
    assert _types(final) == ["final_answer_reveal"]
    assert final.final_answer_locked is False


def test_retry_and_resumed_session_preserve_the_expected_moment() -> None:
    retry = _turn(action=VisualTutorAction.START, step=2)
    resumed = _turn(action=VisualTutorAction.SUBMIT_STEP, message="2x + 3", step=1)
    assert retry.authoritative_lesson_state["current_step_index"] == 2
    assert _types(retry) == ["transform_equation", "student_task"]
    assert resumed.authoritative_lesson_state["current_step_index"] == 2
    assert resumed.student_task == "នៅពេល x ខិតជិត 1 តើ 2x + 3 ខិតជិតលេខណា?"


def test_correct_final_observation_reveals_only_after_the_student_has_responded() -> None:
    response = _turn(action=VisualTutorAction.SUBMIT_STEP, message="5", step=2)
    assert response.final_answer_locked is False
    assert _types(response) == ["final_answer_reveal"]
    assert response.display_text.startswith("ត្រឹមត្រូវ")


def test_provider_independent_opening_is_identical_for_start_and_submit_problem() -> None:
    start = _turn()
    submit = _turn(action=VisualTutorAction.SUBMIT_PROBLEM)
    assert start.board_actions == submit.board_actions
    assert start.student_task == submit.student_task


def test_provider_failure_cannot_prevent_the_local_limits_flow() -> None:
    class UnavailableProvider:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("the local deterministic flow must not call the provider")

    response = handle_visual_tutor_turn(_request(), llm_client=UnavailableProvider())
    assert _types(response) == ["write_equation", "show_table", "student_task"]
    assert response.final_answer_locked is True


def test_orchestrator_preserves_the_final_reveal_after_the_last_student_response() -> None:
    response = handle_visual_tutor_turn(
        _request(action=VisualTutorAction.SUBMIT_STEP, message="5", step=2),
    )
    assert response.final_answer_locked is False
    assert response.board_actions[0].type.value == "final_answer_reveal"


def test_first_local_moment_never_calls_deepseek_even_when_configured(monkeypatch) -> None:
    class MustNotBeCalled:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            raise AssertionError("first local lesson moment must be deterministic")

    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "deepseek")
    response = handle_visual_tutor_turn(_request(), llm_client=MustNotBeCalled())
    assert _types(response) == ["write_equation", "show_table", "student_task"]


def test_later_local_moment_uses_only_bounded_source_context_for_deepseek(monkeypatch) -> None:
    captured: dict[str, str] = {}
    approved_plan = _turn().metadata["teaching_plan"]

    class SourceBoundClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            captured["system"] = system_prompt
            captured["user"] = user_prompt
            return json.dumps({"teaching_plan": approved_plan}, ensure_ascii=False)

    private_message = "private student response / secret-sentinel"
    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "deepseek")
    response = handle_visual_tutor_turn(
        _request(action=VisualTutorAction.REQUEST_HINT, message=private_message),
        llm_client=SourceBoundClient(),
    )
    assert response.metadata["deepseek_planner"] == "validated"
    assert private_message not in captured["user"]
    assert "secret-sentinel" not in captured["user"]
    assert "student_model" not in captured["user"]
    assert "telemetry" not in captured["user"]
    assert "untrusted reference data" in captured["system"]
    assert len(captured["user"]) <= 4_000


@pytest.mark.parametrize("failure, expected_status", [
    (TimeoutError("timeout"), "timeout_fallback"),
    (httpx.ReadTimeout("timeout"), "timeout_fallback"),
    (RuntimeError("provider unavailable"), "invalid_or_unavailable_fallback"),
    (None, "invalid_or_unavailable_fallback"),
])
def test_later_deepseek_failure_or_malformed_plan_uses_deterministic_limits_fallback(monkeypatch, failure, expected_status: str) -> None:
    class FailingClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            del system_prompt, user_prompt
            if failure is not None:
                raise failure
            return '{"teaching_plan":{"not":"a valid plan"}}'

    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "deepseek")
    response = handle_visual_tutor_turn(
        _request(action=VisualTutorAction.REQUEST_HINT),
        llm_client=FailingClient(),
    )
    assert response.metadata["deepseek_planner"] == expected_status
    assert _types(response) == ["transform_equation", "student_task"]
    assert response.final_answer_locked is True


@pytest.mark.parametrize("private_field", ["accepted_answer_forms", "expected_step"])
def test_private_verifier_fields_in_an_otherwise_valid_deepseek_plan_are_rejected(monkeypatch, private_field: str) -> None:
    plan = json.loads(json.dumps(_turn().metadata["teaching_plan"]))
    plan["board_actions"][-1][private_field] = ["5"] if private_field == "accepted_answer_forms" else "evaluate"

    class PrivatePlanClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            del system_prompt, user_prompt
            return json.dumps({"teaching_plan": plan})

    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "deepseek")
    response = handle_visual_tutor_turn(
        _request(action=VisualTutorAction.REQUEST_HINT),
        llm_client=PrivatePlanClient(),
    )
    assert response.metadata["deepseek_planner"] == "invalid_or_unavailable_fallback"
    assert _types(response) == ["transform_equation", "student_task"]


def test_deepseek_failure_text_cannot_reach_the_public_response_metadata(monkeypatch) -> None:
    class SecretFailureClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            del system_prompt, user_prompt
            raise RuntimeError("provider secret-sentinel and private learner text")

    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "deepseek")
    response = handle_visual_tutor_turn(
        _request(action=VisualTutorAction.REQUEST_HINT),
        llm_client=SecretFailureClient(),
    )
    assert response.metadata["deepseek_planner"] == "invalid_or_unavailable_fallback"
    assert "secret-sentinel" not in json.dumps(response.metadata, ensure_ascii=False)


def test_bounded_deepseek_context_excludes_private_request_data() -> None:
    request = _request(message="private answer and token")
    request.metadata["telemetry"] = {"raw": "do-not-send"}
    request.metadata["student_model"] = {"private": "do-not-send"}
    context = bounded_limits_planner_context(request)
    serialized = json.dumps(context, ensure_ascii=False)
    for forbidden in ("private answer", "do-not-send", "telemetry", "student_model", "session_id", "user_id"):
        assert forbidden not in serialized


def test_public_payload_has_no_answer_leak_until_final_reveal_is_allowed() -> None:
    opening = project_public_tutor_turn(_turn())
    answer_progress = project_public_tutor_turn(_turn(action=VisualTutorAction.REQUEST_FINAL_ANSWER, step=1))
    final = project_public_tutor_turn(_turn(action=VisualTutorAction.REQUEST_FINAL_ANSWER, step=2))
    correct = project_public_tutor_turn(_turn(action=VisualTutorAction.SUBMIT_STEP, message="5"))
    wrong = project_public_tutor_turn(_turn(action=VisualTutorAction.SUBMIT_STEP, message="4"))
    for payload in (opening, answer_progress, correct, wrong):
        serialized = json.dumps(payload, ensure_ascii=False)
        assert "final_answer_reveal" not in serialized
        assert "accepted_answer_forms" not in serialized
        assert "expected_step" not in serialized
        assert "លីមីតនៃអនុគមន៍នេះគឺ 5" not in serialized
    assert final["teaching_plan"]["visible_board_actions"][0]["type"] == "final_answer_reveal"


class _FakeDynamicPlannerClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return json.dumps(
            {
                "spoken_text": "Let's look at the table of values.",
                "display_text": "Check the table of values.",
                "teaching_mode": "guided_question",
                "student_task": "What value does f(x) approach?",
                "board": {
                    "type": "table",
                    "title": "Limit of a Function",
                    "items": [
                        {
                            "label": "Function",
                            "content": "f(x) = 2x + 1",
                            "status": "active",
                            "metadata": {},
                        }
                    ],
                    "metadata": {},
                },
                "canvas_actions": [
                    {
                        "id": "limit-speak",
                        "type": "speak_marker",
                        "metadata": {"source": "mock_llm"},
                    },
                ],
                "mastery_signal": "exploring",
                "metadata": {"source": "mock_llm"},
            },
            ensure_ascii=False,
        )


def test_new_limit_problem_answers_with_the_full_worked_solution(monkeypatch) -> None:
    """A new limit problem is answered in full, not one step at a time.

    The solution is built from sympy, so no planner call is needed and the
    student sees every step at once with the answer.
    """
    from api.services.visual_tutor.orchestrator import settings as orchestrator_settings

    monkeypatch.setattr(
        orchestrator_settings, "VISUAL_TUTOR_LOCAL_LIMITS_DEMO_ENABLED", False
    )
    fake_llm = _FakeDynamicPlannerClient()

    response = handle_visual_tutor_turn(
        _request(
            action=VisualTutorAction.SUBMIT_PROBLEM,
            message="Find the limit of f(x) = 2x + 1 as x approaches 3",
        ),
        llm_client=fake_llm,
    )

    assert not fake_llm.calls, "a verified worked solution needs no planner call"
    assert response.final_answer_locked is False
    assert response.metadata["worked_solution"]["answer"] == "The limit is 7."
    assert response.metadata["verification"]["verified"] is True
    # Every step reaches the student in one turn, rather than a single visual.
    plan_actions = response.metadata["teaching_plan"]["board_actions"]
    assert len([action for action in plan_actions if action["type"] == "write_equation"]) >= 2


def test_try_it_myself_keeps_the_guided_dynamic_planner(monkeypatch) -> None:
    """Choosing "Try it myself" keeps the original step-by-step flow, which
    flows through understand_visual_tutor_problem -> LimitOfFunctionSolver ->
    the dynamic LLM planner (see orchestrator.py's
    VISUAL_TUTOR_LOCAL_LIMITS_DEMO_ENABLED gate)."""
    from api.services.visual_tutor.orchestrator import settings as orchestrator_settings

    monkeypatch.setattr(
        orchestrator_settings, "VISUAL_TUTOR_LOCAL_LIMITS_DEMO_ENABLED", False
    )
    fake_llm = _FakeDynamicPlannerClient()
    request = _request(
        action=VisualTutorAction.SUBMIT_PROBLEM,
        message="Find the limit of f(x) = 2x + 1 as x approaches 3",
    )
    request = request.model_copy(
        update={"metadata": {**request.metadata, "tutor_mode": "try_myself"}}
    )

    response = handle_visual_tutor_turn(request, llm_client=fake_llm)

    assert fake_llm.calls, "the dynamic planner should have been called"
    assert response.metadata["response_source"] == "llm_planner"
    assert response.metadata.get("local_curriculum_demo") is not True
    assert response.board_actions


def test_local_limits_demo_still_reachable_as_an_explicit_reference(monkeypatch) -> None:
    """The scripted demo must still work when explicitly opted into, so it
    stays usable as a known-good reference to compare the dynamic path
    against."""
    from api.services.visual_tutor.orchestrator import settings as orchestrator_settings

    monkeypatch.setattr(
        orchestrator_settings, "VISUAL_TUTOR_LOCAL_LIMITS_DEMO_ENABLED", True
    )

    response = handle_visual_tutor_turn(_request())

    assert response.metadata.get("local_curriculum_demo") is True
