from __future__ import annotations

import json
import shlex
import sys

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorCanvasActionType,
    VisualTutorInteractionType,
    VisualTutorTeachingMode,
)
from api.models.visual_tutor import VisualTutorTurnRequest, VisualTutorTurnState
from api.services.visual_tutor.llm_teaching_planner import (
    CodexCLIBridgeVisualTutorLLMClient,
    DeepSeekVisualTutorLLMClient,
    OllamaVisualTutorLLMClient,
    UnavailableVisualTutorLLMClient,
    _bounded_planner_timeout,
    _default_llm_client,
    _provider_identity,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn


class FakeVisualTutorLLMClient:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return json.dumps(self.payload, ensure_ascii=False)


class RawFakeVisualTutorLLMClient:
    def __init__(self, raw_output: str) -> None:
        self.raw_output = raw_output
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.raw_output


class SequenceVisualTutorLLMClient:
    """Return one planned model response per call, including repair attempts."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt})
        return self.responses.pop(0)


def _planner_payload(
    *,
    spoken_text: str = "Let's inspect the problem before solving. What is the unknown?",
    display_text: str = "Start by identifying what the problem asks.",
    teaching_mode: str = "guided_question",
    student_task: str = "Tell me the unknown quantity first.",
    board_item: str = "a + b = 10",
    mastery_signal: str = "exploring",
    canvas_actions: list[dict] | None = None,
) -> dict:
    return {
        "spoken_text": spoken_text,
        "display_text": display_text,
        "teaching_mode": teaching_mode,
        "student_task": student_task,
        "board": {
            "type": "formula_card",
            "title": "Problem setup",
            "items": [
                {
                    "label": "Given",
                    "content": board_item,
                    "status": "active",
                    "metadata": {},
                }
            ],
            "metadata": {},
        },
        "canvas_actions": (
            canvas_actions
            if canvas_actions is not None
            else [
                {
                    "id": "llm-speak",
                    "type": "speak_marker",
                    "metadata": {"source": "mock_llm"},
                },
                {
                    "id": "llm-step",
                    "type": "write_text",
                    "x": 40,
                    "y": 80,
                    "width": 520,
                    "height": 48,
                    "text": board_item,
                    "locked": False,
                    "metadata": {"current_step": True},
                },
                {
                    "id": "llm-highlight",
                    "type": "highlight",
                    "target_id": "llm-step",
                    "metadata": {"reason": "current_step"},
                },
                {
                    "id": "llm-pause",
                    "type": "pause_marker",
                    "metadata": {"duration_ms": 250},
                },
            ]
        ),
        "mastery_signal": mastery_signal,
        "metadata": {"source": "mock_llm"},
    }


def _live_stage_payload(
    *,
    spoken_text: str = "Let's use one visual step. What do you notice first?",
    display_text: str = "One visual step first.",
    student_task: str = "Answer the small question on the board.",
    board_action_text: str = "Look at the given information.",
    board_action_latex: str | None = None,
    interaction_prompt: str = "What should we identify first?",
    language: str = "en",
    teaching_mode: str = "guided_question",
    metadata: dict | None = None,
) -> dict:
    payload = _planner_payload(
        spoken_text=spoken_text,
        display_text=display_text,
        teaching_mode=teaching_mode,
        student_task=student_task,
        board_item=board_action_text,
        canvas_actions=[
            {
                "id": "compat-speak",
                "type": "speak_marker",
                "metadata": {"source": "mock_llm"},
            }
        ],
    )
    payload.update(
        {
            "screen_state": "speaking_writing",
            "tutor_status": "Writing...",
            "speech": {
                "text": spoken_text,
                "language": language,
                "tts_status": "not_requested",
                "pause_after_ms": 400,
            },
            "teaching_stage": {
                "stage_state": "waiting_for_student",
                "lesson_state": "ask",
                "current_focus": "llm-live-step",
                "turn_goal": "Ask one focused question.",
                "max_actions_before_wait": 1,
            },
            "board_actions": [
                {
                    "id": "llm-live-speak",
                    "type": "speak_marker",
                    "sequence_index": 0,
                    "duration_ms": 0,
                    "metadata": {"source": "mock_llm"},
                },
                {
                    "id": "llm-live-step",
                    "type": "write_equation" if board_action_latex else "write_text",
                    "sequence_index": 1,
                    "duration_ms": 650,
                    "x": 40,
                    "y": 80,
                    "width": 620,
                    "height": 56,
                    "text": None if board_action_latex else board_action_text,
                    "latex": board_action_latex,
                    "locked": False,
                    "metadata": {"current_step": True, "source": "mock_llm"},
                },
                {
                    "id": "llm-live-highlight",
                    "type": "highlight",
                    "sequence_index": 2,
                    "target_id": "llm-live-step",
                    "duration_ms": 250,
                    "metadata": {"reason": "current_step"},
                },
            ],
            "interaction": {
                "type": "text_response",
                "prompt": interaction_prompt,
                "expected_answer_locked": True,
                "validation_strategy": "teacher_review",
                "choices": [],
                "input_enabled": True,
                "submit_label": "Submit",
            },
            "allowed_actions": [
                "submit_answer",
                "request_hint",
                "explain_differently",
                "stuck",
            ],
            "quick_actions": [
                "submit_answer",
                "request_hint",
                "explain_differently",
                "stuck",
            ],
            "metadata": {"source": "mock_llm", **(metadata or {})},
        }
    )
    return payload


def test_llm_fallback_for_unsupported_algebra_still_asks_guiding_question() -> None:
    fake_llm = FakeVisualTutorLLMClient(_planner_payload())

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    assert fake_llm.calls
    assert response.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert response.final_answer_locked is True
    assert "unknown" in response.student_task.lower()
    assert response.metadata["planner"] == "visual_tutor_llm_teaching_planner_v1"


def test_supported_linear_equation_uses_llm_as_main_teacher_when_configured() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="Let's move terms one visual step at a time.",
            board_action_text="First focus: collect the variable terms.",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="5a - 8 = 2a + 7",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    board_text = " ".join(action.text or "" for action in response.board_actions)
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert fake_llm.calls
    assert response.metadata["problem_understanding"]["problem_type"] == (
        "linear_equation_one_variable"
    )
    assert response.metadata["response_source"] == "llm_planner"
    assert response.metadata["llm_called"] is True
    assert response.metadata["adaptive_planner_generated_response"] is True
    assert response.metadata["generation_path"] == "llm_main"
    assert response.metadata["orchestrator_flow"] == [
        "restore_session",
        "understand_problem",
        "understand_student_input",
        "retrieve_curriculum",
        "get_solver",
        "get_solver_facts",
        "decide_policy",
        "adaptive_tutor_planner",
        "sanitize_response",
        "persist_session_board_state",
        "return_response",
    ]
    assert "First focus: collect the variable terms." in board_text
    assert user_prompt["solver_facts"]["solver_name"] == "LinearEquationSolver"
    assert user_prompt["solver_facts"]["known_solution"] == "a = 5"
    assert user_prompt["solver_facts"]["expected_step"]
    assert user_prompt["solver_facts"]["verified_answer"] == "a = 5"
    assert user_prompt["adaptive_tutor_decision"]["one_teaching_moment_per_turn"] is True


def test_llm_prompt_includes_student_model_strategy_history_and_move_instruction() -> None:
    fake_llm = FakeVisualTutorLLMClient(_live_stage_payload())
    student_model = {
        "understanding": "exploring",
        "recent_mistakes": ["sign_error"],
        "hint_level": 2,
        "wrong_attempt_streak": 1,
        "recommended_depth": "simple",
        "metadata": {},
    }
    strategy_history = [
        {
            "tutor_move": "show_visual_hint",
            "interaction_type": "numeric_input",
            "mistake_category_addressed": "sign_error",
            "board_update_mode": "patch",
            "asked_for_student_attempt": True,
        }
    ]

    handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="3x - 9 = 12",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={
                "student_model": student_model,
                "strategy_history": strategy_history,
            },
        ),
        llm_client=fake_llm,
    )

    prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert prompt["student_model"] == student_model
    assert prompt["strategy_history"] == strategy_history
    assert prompt["teaching_move_instruction"]["move"]
    assert "teaching_move_instruction.move" in fake_llm.calls[0]["system_prompt"]
    assert "strategy_history describes recent teaching moves" in fake_llm.calls[0][
        "system_prompt"
    ]


def test_llm_receives_solver_facts_and_curriculum_context_for_supported_linear_equation() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="Use the balance rule from the lesson.",
            board_action_text="Subtract the same term from both sides.",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        ),
        llm_client=fake_llm,
    )
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert response.metadata["response_source"] == "llm_planner"
    assert user_prompt["solver_facts"]["solver_name"] == "LinearEquationSolver"
    assert user_prompt["solver_facts"]["expected_equation"] == "2x = 10"
    assert user_prompt["solver_facts"]["sympy_verified"] is True
    assert user_prompt["curriculum_context"]["chunk_ids"]
    assert user_prompt["curriculum_context"]["formulas"]
    # Standing rules live in the cached system prompt, not in every turn.
    assert "use it only to ground explanations" in fake_llm.calls[0]["system_prompt"]


def test_line_through_points_uses_planner_and_solver_facts_when_llm_configured() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="Let's look at the two points first.",
            board_action_text="Plot D(0,1) and E(1,3).",
            interaction_prompt="How much does y increase?",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Find the equation of the line through D(0,1) and E(1,3)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert fake_llm.calls
    assert response.metadata["response_source"] == "llm_planner"
    assert response.metadata["tutor_move"] in {
        "ask_guiding_question",
        "teach_next_visual_step",
    }
    assert user_prompt["solver_facts"]["solver_name"] == "LineThroughPointsSolver"
    assert user_prompt["solver_facts"]["expected_operation"] == "3 - 1"
    assert user_prompt["solver_facts"]["next_concept"] == "horizontal change Δx"
    assert response.interaction is not None
    assert response.board_actions


def test_llm_generates_visual_board_action_for_linear_regression() -> None:
    payload = _live_stage_payload(
        spoken_text="Let's plot the data first.",
        display_text="Use the scatter plot to see the trend.",
        student_task="Which direction does the trend move?",
        board_action_text="Plot (1,2), (2,4), (3,5).",
        interaction_prompt="Does the trend go up or down?",
    )
    payload["board"]["type"] = "graph_hint"
    payload["board"]["title"] = "Regression Scatter Plot"
    payload["board_actions"] = [
        {
            "id": "regression-axes",
            "type": "draw_axes",
            "sequence_index": 0,
            "x": 40,
            "y": 40,
            "width": 420,
            "height": 260,
            "metadata": {"source": "mock_llm"},
        },
        # TeachingPlanAction.DRAW_POINT is one point per action (bounded x/y
        # on the action itself), not a batch of points -- see
        # teaching_plan_contract.py's validate_action.
        {
            "id": "regression-point-a",
            "type": "draw_point",
            "sequence_index": 1,
            "x": 1,
            "y": 2,
            "label": "A",
            "metadata": {"source": "mock_llm"},
        },
        {
            "id": "regression-point-b",
            "type": "draw_point",
            "sequence_index": 2,
            "x": 2,
            "y": 4,
            "label": "B",
            "metadata": {"source": "mock_llm"},
        },
        {
            "id": "regression-point-c",
            "type": "draw_point",
            "sequence_index": 3,
            "x": 3,
            "y": 5,
            "label": "C",
            "metadata": {"source": "mock_llm"},
        },
        # "draw_graph_hint" is not a real TeachingPlanActionType;
        # graph_annotation is the supported way to label a graph.
        {
            "id": "regression-trend-hint",
            "type": "graph_annotation",
            "sequence_index": 4,
            "text": "Upward trend",
            "metadata": {"source": "mock_llm"},
        },
    ]
    fake_llm = FakeVisualTutorLLMClient(payload)

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Regression",
            message="Find the linear regression for points (1,2), (2,4), (3,5)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        ),
        llm_client=fake_llm,
    )
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])
    action_types = [action.type.value for action in response.board_actions]

    assert response.metadata["response_source"] == "llm_planner"
    assert user_prompt["problem_understanding"]["problem_type"] == "linear_regression"
    assert user_prompt["problem_understanding"]["extracted_entities"]["slope"] == "3/2"
    assert user_prompt["problem_understanding"]["extracted_entities"]["intercept"] == "2/3"
    # The guided first turn gives one focused visual update and waits for the
    # student (see test_first_problem_gives_one_focused_visual_action_group),
    # so the plot starts with its axes; points and the trend come next turns.
    assert "draw_axes" in action_types
    assert "student_task" in action_types
    assert response.interaction is not None


def test_unsupported_math_llm_response_contains_live_board_action() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="Let's identify the structure first.",
            display_text="One visual step: mark the unknowns.",
            student_task="Which quantity should we isolate first?",
            board_action_text="Given: a + b = 10. Unknown: a.",
            interaction_prompt="Which symbol are we solving for?",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    main_text = " ".join([response.spoken_text, response.display_text, response.student_task])

    assert fake_llm.calls
    assert response.board_actions
    assert response.interaction is not None
    assert response.allowed_actions
    assert response.quick_actions
    assert response.screen_state.value == "asking_question"
    assert response.metadata["llm_live_stage_fields"]["screen_state"] is True
    assert response.metadata["llm_required_live_fields_present"]["screen_state"] is True
    assert response.tutor_status
    assert "unsupported" not in main_text.lower()
    assert any(
        action.type
        in {
            VisualTutorCanvasActionType.WRITE_TEXT,
            VisualTutorCanvasActionType.WRITE_EQUATION,
            VisualTutorCanvasActionType.HIGHLIGHT,
        }
        for action in response.board_actions
    )


def test_llm_payload_missing_live_fields_is_repaired_for_canvas_first_ui() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="Let's inspect one part first.",
            display_text="Start by marking the given relation.",
            student_task="What is the unknown?",
            board_item="a + b = 10",
            canvas_actions=[],
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    assert response.speech is not None
    assert response.board_actions
    assert response.interaction is not None
    assert response.allowed_actions
    assert response.metadata["llm_required_live_fields_present"]["board_actions"] is True
    assert "board_actions" in response.metadata["llm_payload_recovered_fields"]


def test_llm_returns_valid_live_teaching_stage_json() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            board_action_text="Given: two quantities are related.",
            interaction_prompt="Which quantity is unknown?",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Explain a relation between speed and time",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert response.final_answer_locked is True
    assert response.speech is not None
    assert response.teaching_stage is not None
    assert response.teaching_stage.max_actions_before_wait == 1
    assert response.board_actions
    assert response.board_actions[1].id == "llm-live-step"
    assert response.board_actions[1].text == "Given: two quantities are related."
    assert response.interaction is not None
    assert response.interaction.prompt == "Which quantity is unknown?"
    assert "request_hint" in [action.value for action in response.allowed_actions]
    assert response.metadata["llm_live_stage_fields"]["board_actions"] is True
    assert "live_teaching_stage_schema" in user_prompt
    assert user_prompt["live_teaching_stage_schema"]["required_response_fields"] == [
        "screen_state",
        "tutor_status",
        "speech",
        "board",
        "board_actions",
        "interaction",
        "quick_actions",
        "metadata",
    ]
    assert (
        "Do not generate arbitrary code"
        in fake_llm.calls[0]["system_prompt"]
    )
    assert (
        "Do not return markdown-only answers"
        in fake_llm.calls[0]["system_prompt"]
    )


def test_llm_prompt_requires_next_teacher_action_not_lesson_page() -> None:
    fake_llm = FakeVisualTutorLLMClient(_live_stage_payload())

    handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Explain how to solve equations",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    system_prompt = fake_llm.calls[0]["system_prompt"]
    assert "one-to-one AI visual tutor" in system_prompt
    assert "Return strict JSON only" in system_prompt
    assert "next teacher action" in system_prompt
    assert "one focused visual action group" in system_prompt
    assert "Write on the canvas first" in system_prompt
    assert "board_actions must be visual and useful" in system_prompt
    assert "Use solver_facts as the correctness source" in system_prompt
    assert "curriculum_context is provided" in system_prompt
    assert "lesson page" in system_prompt
    assert "screen_state" in system_prompt
    assert "quick_actions" in system_prompt
    assert "Do not return markdown-only answers" in system_prompt


def test_llm_markdown_only_answer_falls_back_to_structured_turn() -> None:
    fake_llm = RawFakeVisualTutorLLMClient(
        "```markdown\n# Solution\nThe answer is a = 10 - b.\n```"
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    visible_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(action.text or "" for action in response.board_actions),
        ]
    )

    assert fake_llm.calls
    assert response.metadata["planner_fallback"] is True
    assert response.board_actions
    assert response.interaction is not None
    assert "10 - b" not in visible_text
    assert "```" not in visible_text


def test_llm_invalid_json_falls_back_safely() -> None:
    fake_llm = RawFakeVisualTutorLLMClient(
        "{ this is not valid json and should not reach the frontend"
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Find the linear regression for points (1,2), (2,4), (3,5)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    assert fake_llm.calls
    assert response.metadata["planner_fallback"] is True
    assert response.metadata["response_source"] == "template_fallback"
    assert response.board_actions
    assert response.interaction is not None
    assert "not valid json" not in response.spoken_text


def test_linear_step_two_stuck_fallback_reteaches_the_coefficient() -> None:
    """A stuck learner on Step 2 must not be sent back to the Step 1 constant."""
    fake_llm = RawFakeVisualTutorLLMClient("{ this is invalid json")

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Linear Equations",
            message="I don't understand",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            current_state=VisualTutorTurnState(
                problem_text="2x - 5 = 10",
                current_step_index=1,
            ),
        ),
        llm_client=fake_llm,
    )

    visible_text = " ".join(
        [response.spoken_text, response.display_text, response.student_task]
    ).lower()
    assert response.metadata["planner_fallback"] is True
    assert "divide both sides by 2" in visible_text
    assert "constant -5" not in visible_text


def test_llm_uses_exactly_one_repair_attempt_before_accepting_a_valid_plan() -> None:
    client = SequenceVisualTutorLLMClient(
        ["{not valid json", json.dumps(_live_stage_payload())]
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=client,
    )

    assert len(client.calls) == 2
    assert response.metadata["response_source"] == "llm_planner"
    assert response.metadata["schema_rejection_count"] == 1
    assert response.metadata["fallback_reason"] is None


def test_llm_repair_failure_returns_safe_template_after_one_retry() -> None:
    client = SequenceVisualTutorLLMClient(["{not valid json", "{still invalid"])

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=client,
    )

    assert len(client.calls) == 2
    assert response.metadata["response_source"] == "template_fallback"
    assert response.metadata["schema_rejection_count"] == 2
    assert response.metadata["fallback_reason"] == "invalid_model_output"


def test_planner_timeout_returns_a_safe_recoverable_template() -> None:
    class TimeoutClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            del system_prompt, user_prompt
            raise TimeoutError("provider timed out while processing private prompt")

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=TimeoutClient(),
    )

    assert response.metadata["response_source"] == "template_fallback"
    assert response.metadata["fallback_reason"] == "planner_timeout"
    assert "private prompt" not in str(response.metadata)


def test_llm_arbitrary_code_output_falls_back_to_structured_turn() -> None:
    fake_llm = RawFakeVisualTutorLLMClient(
        json.dumps(
            {
                "spoken_text": "Here is Flutter code.",
                "display_text": "```dart\nCustomPaint(...)\n```",
                "teaching_mode": "guided_question",
                "student_task": "Copy this code.",
                "board": {"type": "formula_card", "title": "Code", "items": []},
                "canvas_actions": [],
                "mastery_signal": "exploring",
                "metadata": {},
                "board_actions": [
                    {
                        "id": "bad-code",
                        "type": "write_text",
                        "text": "Widget build(BuildContext context) {}",
                    }
                ],
                "interaction": {
                    "type": "text_response",
                    "prompt": "Use this Flutter code?",
                    "choices": [],
                    "input_enabled": True,
                    "submit_label": "Submit",
                },
                "speech": {"text": "Here is Flutter code.", "language": "en"},
                "allowed_actions": ["submit_answer"],
                "quick_actions": ["submit_answer"],
                "screen_state": "speaking_writing",
                "tutor_status": "Writing...",
            }
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Explain a strange equation",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    visible_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(action.text or "" for action in response.board_actions),
        ]
    )

    assert "Widget build" not in visible_text
    assert "CustomPaint" not in visible_text
    assert response.board_actions


def test_llm_returns_one_focused_visual_action_group() -> None:
    payload = _live_stage_payload(
        board_action_text="Current focus: identify the known values.",
        interaction_prompt="Which value is given first?",
    )
    payload["board_actions"].extend(
        [
            {
                "id": "llm-future-section",
                "type": "write_text",
                "sequence_index": 3,
                "duration_ms": 400,
                "x": 40,
                "y": 180,
                "text": "Future lesson section: solve everything now.",
                "group_id": "full-lesson",
                "metadata": {"source": "mock_llm"},
            },
            {
                "id": "llm-future-highlight",
                "type": "highlight",
                "sequence_index": 4,
                "target_id": "llm-future-section",
                "group_id": "full-lesson",
                "metadata": {"source": "mock_llm"},
            },
        ]
    )
    for action in payload["board_actions"][:3]:
        action["group_id"] = "current-step"
    fake_llm = FakeVisualTutorLLMClient(payload)

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Explain a new topic",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    board_text = " ".join(action.text or "" for action in response.board_actions)
    visible_groups = {
        action.group_id
        for action in response.board_actions
        if action.type != VisualTutorCanvasActionType.SPEAK_MARKER
    }

    assert "Current focus" in board_text
    assert "Future lesson section" not in board_text
    assert "full-lesson" not in visible_groups
    assert response.board_actions[0].metadata["llm_visual_group_trimmed"] == 2


def test_llm_does_not_produce_full_lesson_board_when_multiple_groups_returned() -> None:
    payload = _live_stage_payload(board_action_text="Step now: read the given points.")
    payload["board_actions"] = [
        {
            "id": "group-one-speak",
            "type": "speak_marker",
            "sequence_index": 0,
            "group_id": "step-now",
        },
        {
            "id": "group-one-note",
            "type": "write_text",
            "sequence_index": 1,
            "text": "Step now: read the given points.",
            "group_id": "step-now",
            "metadata": {"current_step": True},
        },
        {
            "id": "group-two-note",
            "type": "write_text",
            "sequence_index": 2,
            "text": "Step later: compute slope, intercept, and final equation.",
            "group_id": "full-page",
        },
    ]
    fake_llm = FakeVisualTutorLLMClient(payload)

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Find the equation of a line through two points",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    board_text = " ".join(action.text or "" for action in response.board_actions)

    assert "read the given points" in board_text
    assert "compute slope, intercept, and final equation" not in board_text


def test_llm_stuck_live_response_reteaches_current_step() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="Let's slow down and look only at this step.",
            display_text="Reteach the current step.",
            teaching_mode="stuck_help",
            board_action_text="Current step: remove the constant from both sides.",
            interaction_prompt="What operation removes +5?",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            current_state=VisualTutorTurnState(problem_text="Solve a + b = 10 for a"),
        ),
        llm_client=fake_llm,
    )
    board_text = " ".join(action.text or "" for action in response.board_actions)

    assert response.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert "Current step" in board_text
    assert response.interaction is not None
    assert "operation removes +5" in response.interaction.prompt


def test_llm_wrong_answer_highlights_first_mistake() -> None:
    payload = _live_stage_payload(
        spoken_text="Not quite. Let's inspect the first mismatch.",
        display_text="Check the first mismatch.",
        teaching_mode="misconception_fix",
        board_action_text="Student wrote 50, but the current step is subtract 5.",
        interaction_prompt="What should we subtract from both sides?",
    )
    payload["board_actions"].append(
        {
            "id": "wrong-input-cross",
            "type": "highlight",
            "sequence_index": 3,
            "target_id": "llm-live-step",
            "group_id": None,
            "metadata": {"mistake_marker": True},
        }
    )
    fake_llm = FakeVisualTutorLLMClient(payload)

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="50",
            action=VisualTutorAction.SUBMIT_STEP,
            current_state=VisualTutorTurnState(problem_text="Solve a + b = 10 for a"),
        ),
        llm_client=fake_llm,
    )

    assert response.metadata["llm_teaching_mode"] == "misconception_fix"
    assert any(
        action.type == VisualTutorCanvasActionType.HIGHLIGHT
        and action.metadata.get("mistake_marker") is True
        for action in response.board_actions
    )
    assert response.interaction is not None
    assert "subtract" in response.interaction.prompt.lower()


def test_llm_returns_valid_canvas_actions() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            board_item="First identify the unknown.",
            canvas_actions=[
                {
                    "id": "canvas-speak",
                    "type": "speak_marker",
                    "metadata": {"source": "mock_llm"},
                },
                {
                    "id": "canvas-note",
                    "type": "write_text",
                    "x": 40,
                    "y": 80,
                    "width": 520,
                    "height": 42,
                    "text": "Step 1: identify the unknown",
                    "style": {"font_size": 20},
                    "locked": False,
                    "metadata": {"current_step": True},
                },
                {
                    "id": "canvas-note-highlight",
                    "type": "highlight",
                    "target_id": "canvas-note",
                    "metadata": {"reason": "current_step"},
                },
                {
                    "id": "canvas-pause",
                    "type": "pause_marker",
                    "metadata": {"duration_ms": 250},
                },
            ],
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    assert response.canvas_actions
    assert response.canvas_actions[0].type == VisualTutorCanvasActionType.SPEAK_MARKER
    assert response.canvas_actions[1].type == VisualTutorCanvasActionType.WRITE_TEXT
    assert response.canvas_actions[1].text == "Step 1: identify the unknown"
    assert response.canvas_actions[2].type == VisualTutorCanvasActionType.HIGHLIGHT
    assert response.canvas_actions[-1].type == VisualTutorCanvasActionType.PAUSE_MARKER


def test_llm_final_answer_leak_is_removed_and_locked_by_policy() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="Final answer is a = 10 - b.",
            display_text="Answer: a = 10 - b",
            teaching_mode="full_solution",
            student_task="Copy a = 10 - b.",
            board_item="a = 10 - b",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    combined_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(item.content for item in response.board.items),
        ]
    )
    assert response.final_answer_locked is True
    assert response.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert "10 - b" not in combined_text
    assert response.board.items[0].status == "locked"
    assert response.metadata["final_answer_locked_by_policy"] is True


def test_llm_live_stage_full_solution_is_locked_by_sanitizer() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="The full solution is a = 10 - b.",
            display_text="Answer: a = 10 - b",
            teaching_mode="full_solution",
            student_task="Choose a = 10 - b.",
            board_action_latex="a = 10 - b",
            interaction_prompt="Is the answer a = 10 - b?",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    visible_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            response.interaction.prompt if response.interaction else "",
            *(action.text or "" for action in response.board_actions),
            *(action.latex or "" for action in response.board_actions),
        ]
    )

    assert response.final_answer_locked is True
    assert response.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert "10 - b" not in visible_text
    assert response.metadata["response_source"] == "llm_planner"
    assert response.metadata["llm_called"] is True
    assert any(
        action.type == VisualTutorCanvasActionType.HIDE and action.locked is True
        for action in response.board_actions
    )
    assert response.metadata["sanitization"]["applied"] is True


def test_llm_canvas_final_answer_leak_is_sanitized_while_locked() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="Let's inspect the problem first.",
            display_text="Start with the unknown.",
            student_task="Tell me the unknown first.",
            board_item="a + b = 10",
            canvas_actions=[
                {
                    "id": "canvas-leak",
                    "type": "write_equation",
                    "x": 40,
                    "y": 80,
                    "width": 520,
                    "height": 48,
                    "latex": "a = 10 - b",
                    "metadata": {"is_final_answer": True},
                }
            ],
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    action = response.canvas_actions[0]
    assert response.final_answer_locked is True
    assert action.type == VisualTutorCanvasActionType.HIDE
    assert action.latex == r"\text{Final answer is locked.}"
    assert action.locked is True
    assert response.metadata["sanitization"]["canvas_action_ids"] == ["canvas-leak"]


def test_llm_fallback_preserves_khmer_friendly_explanation() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="យើងចាប់ផ្តើមដោយសួរថា លំហាត់នេះចង់ឱ្យរកអ្វី?",
            display_text="រកអ្វីដែលលំហាត់សួរជាមុន។",
            student_task="សូមប្រាប់គ្រូថា ត្រូវរកតម្លៃអ្វី?",
            board_item="មានលេខ 5 និង 3",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="សុខមានផ្លែប៉ោម 5 ហើយទិញ 3 បន្ថែម តើសរុបប៉ុន្មាន?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            locale="km-KH",
        ),
        llm_client=fake_llm,
    )

    assert fake_llm.calls
    assert response.final_answer_locked is True
    assert "លំហាត់" in response.spoken_text
    assert "ត្រូវរកតម្លៃអ្វី" in response.student_task
    assert response.metadata["problem_understanding"]["language"] == "km"
    assert response.board_actions
    assert response.speech is not None
    assert response.speech.language == "km"


def test_llm_response_contains_one_focused_teaching_move() -> None:
    payload = _live_stage_payload(
        board_action_text="Focus now: identify the unknown.",
        interaction_prompt="What is the unknown?",
    )
    payload["board_actions"].extend(
        [
            {
                "id": "extra-full-page-step",
                "type": "write_text",
                "sequence_index": 4,
                "text": "Later: solve all remaining steps and show the final answer.",
                "group_id": "future-full-page",
            },
            {
                "id": "extra-full-page-highlight",
                "type": "highlight",
                "sequence_index": 5,
                "target_id": "extra-full-page-step",
                "group_id": "future-full-page",
            },
        ]
    )
    for action in payload["board_actions"][:3]:
        action["group_id"] = "current-focused-move"
    fake_llm = FakeVisualTutorLLMClient(payload)

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Solve a + b = 10 for a",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )
    board_text = " ".join(action.text or "" for action in response.board_actions)
    visible_groups = {
        action.group_id
        for action in response.board_actions
        if action.type
        not in {
            VisualTutorCanvasActionType.SPEAK_MARKER,
            VisualTutorCanvasActionType.PAUSE_MARKER,
        }
    }

    assert "identify the unknown" in board_text
    assert "solve all remaining steps" not in board_text
    assert visible_groups == {"current-focused-move"}


def test_unsupported_problem_gets_useful_canvas_guidance_when_llm_fails() -> None:
    class BrokenLLMClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("planner unavailable")

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="Explain why math is useful for engineering",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=BrokenLLMClient(),
    )

    canvas_text = " ".join(
        str(value)
        for action in response.canvas_actions
        for value in (action.text, action.latex, action.target_id)
        if value
    )
    assert response.final_answer_locked is True
    assert response.metadata["planner_fallback"] is True
    assert response.canvas_actions
    assert "Start with one focused observation" in canvas_text
    assert any(
        action.type == VisualTutorCanvasActionType.HIGHLIGHT
        for action in response.canvas_actions
    )


def test_english_grammar_fallback_uses_text_interaction_not_math_prompt() -> None:
    class BrokenLLMClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("planner unavailable")

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="English",
            message="Can you explain when to use has and have?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=BrokenLLMClient(),
    )
    canvas_text = " ".join(action.text or "" for action in response.canvas_actions)

    assert response.interaction is not None
    assert response.interaction.type == VisualTutorInteractionType.TEXT_RESPONSE
    assert "grammar choice" in response.interaction.prompt
    assert "value" not in response.interaction.prompt.lower()
    assert "first step" not in response.interaction.prompt.lower()
    assert "grammar choice" in canvas_text


def test_llm_khmer_prompt_returns_khmer_friendly_canvas_text() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="យើងចាប់ផ្តើមមួយជំហានតូចសិន។",
            display_text="រកអ្វីដែលលំហាត់សួរជាមុន។",
            student_task="តើសំណួរនេះចង់ឱ្យរកអ្វី?",
            board_item="ផ្តោតលើសំណួរ",
            canvas_actions=[
                {
                    "id": "khmer-canvas-speak",
                    "type": "speak_marker",
                    "metadata": {"source": "mock_llm"},
                },
                {
                    "id": "khmer-canvas-step",
                    "type": "write_text",
                    "x": 40,
                    "y": 80,
                    "width": 620,
                    "height": 48,
                    "text": "ជំហានទី ១៖ រកអ្វីដែលលំហាត់សួរ",
                    "metadata": {"current_step": True},
                },
                {
                    "id": "khmer-canvas-highlight",
                    "type": "highlight",
                    "target_id": "khmer-canvas-step",
                    "metadata": {"reason": "current_step"},
                },
            ],
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="ខ្ញុំមិនយល់",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            locale="km-KH",
            current_state=VisualTutorTurnState(problem_text="ពន្យល់លំហាត់នេះ"),
        ),
        llm_client=fake_llm,
    )
    canvas_text = " ".join(action.text or "" for action in response.canvas_actions)

    assert response.final_answer_locked is True
    assert "ជំហានទី ១" in canvas_text
    assert response.metadata["policy"]["use_khmer_explanation"] is True


def test_llm_live_stage_khmer_speech_and_board_text_are_preserved() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="យើងមើលតែមួយជំហានសិន។",
            display_text="មើលព័ត៌មានដែលបានឱ្យ។",
            student_task="តើសំណួរនេះសួររកអ្វី?",
            board_action_text="ជំហានទី ១៖ រកអ្វីដែលសំណួរសួរ",
            interaction_prompt="តើត្រូវរកអ្វី?",
            language="km",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Khmer",
            message="ខ្ញុំមិនយល់សំណួរនេះ",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            locale="km-KH",
            current_state=VisualTutorTurnState(problem_text="ពន្យល់លំហាត់នេះ"),
        ),
        llm_client=fake_llm,
    )
    board_text = " ".join(action.text or "" for action in response.board_actions)

    assert response.final_answer_locked is True
    assert response.speech is not None
    assert response.speech.language == "km"
    assert "យើងមើល" in response.speech.text
    assert "ជំហានទី ១" in board_text
    assert response.interaction is not None
    assert "តើត្រូវរកអ្វី" in response.interaction.prompt


def test_llm_stuck_response_is_accepted_when_no_final_answer_leaks() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="Let's slow down. First, identify the unknown.",
            display_text="Small step: name what we need to find.",
            teaching_mode="stuck_help",
            student_task="What value are we trying to find?",
            board_item="Focus on the unknown before solving.",
            mastery_signal="needs_hint",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I am stuck",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            current_state=VisualTutorTurnState(
                problem_text="Solve a + b = 10 for a",
            ),
        ),
        llm_client=fake_llm,
    )

    assert fake_llm.calls
    assert response.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert response.student_intent.value == "stuck"
    assert response.final_answer_locked is True
    visible_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(item.content for item in response.board.items),
        ]
    ).lower()
    assert "unknown" in visible_text
    assert response.board.items[0].status == "active"
    assert response.metadata["planner"] == "visual_tutor_llm_teaching_planner_v1"
    assert response.metadata["policy"]["student_intent"] == "stuck"


def test_llm_stuck_final_answer_leak_is_sanitized_while_locked() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="Final answer is a = 10 - b.",
            display_text="Answer: a = 10 - b",
            teaching_mode="stuck_help",
            student_task="Copy a = 10 - b.",
            board_item="a = 10 - b",
            mastery_signal="needs_hint",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            message="I don't understand",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            current_state=VisualTutorTurnState(
                problem_text="Solve a + b = 10 for a",
            ),
        ),
        llm_client=fake_llm,
    )
    combined_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(item.content for item in response.board.items),
        ]
    )

    assert response.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert response.final_answer_locked is True
    assert "10 - b" not in combined_text
    assert response.board.items[0].status == "locked"
    assert response.metadata["sanitization"]["applied"] is True
    assert response.metadata["policy"]["student_intent"] == "stuck"


def test_llm_khmer_stuck_input_returns_khmer_friendly_support() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="មិនអីទេ យើងធ្វើមួយជំហានតូចៗសិន។",
            display_text="គន្លឹះតូច៖ ស្វែងរកអ្វីដែលសំណួរសួរ។",
            teaching_mode="stuck_help",
            student_task="តើសំណួរនេះចង់ឱ្យរកអ្វី?",
            board_item="ផ្តោតលើសំណួរមុន។",
            mastery_signal="needs_hint",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Khmer",
            message="ខ្ញុំមិនយល់",
            action=VisualTutorAction.REQUEST_STUCK_HELP,
            locale="km-KH",
            current_state=VisualTutorTurnState(
                problem_text="ពន្យល់អត្ថបទខ្មែរនេះ",
            ),
        ),
        llm_client=fake_llm,
    )
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert response.teaching_mode == VisualTutorTeachingMode.STUCK_HELP
    assert response.student_intent.value == "stuck"
    assert response.final_answer_locked is True
    assert "មិនអីទេ" in response.spoken_text
    assert "តើសំណួរនេះ" in response.student_task
    assert response.metadata["policy"]["use_khmer_explanation"] is True
    assert user_prompt["student_intent"] == "stuck"
    assert user_prompt["policy"]["use_khmer_explanation"] is True


def test_llm_receives_curriculum_context_for_unsupported_topic() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="Use function notation first. What input is restricted?",
            display_text="Grounding: domain means valid x-values.",
            student_task="Identify which x-value makes the denominator invalid.",
            board_item="for f(x) = 1 / g(x), require g(x) != 0",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Domain and Range",
            message="Find the domain of f(x) = 1 / (x - 2)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 11},
        ),
        llm_client=fake_llm,
    )
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert response.final_answer_locked is True
    assert user_prompt["curriculum_context"]["chunk_ids"]
    assert (
        "math.g11.functions.domain_range"
        in user_prompt["curriculum_context"]["chunk_ids"]
    )
    assert user_prompt["curriculum_context"]["formulas"]
    assert (
        "Do not copy worked example answers"
        in fake_llm.calls[0]["system_prompt"]
    )


def test_llm_uses_formula_and_prerequisite_from_curriculum() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="Use the domain rule for rational functions and simple equation solving.",
            display_text="Formula: for f(x) = 1 / g(x), require g(x) != 0.",
            student_task="Use the prerequisite skill: solve the denominator equation.",
            board_item="Prerequisite: solving simple equations",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Domain and Range",
            message="Find the domain of f(x) = 1 / (x - 2)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 11},
        ),
        llm_client=fake_llm,
    )

    visible_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(item.content for item in response.board.items),
        ]
    )
    assert "g(x) != 0" in visible_text
    assert "solving simple equations" in visible_text
    assert response.final_answer_locked is True


def test_llm_curriculum_example_answer_leak_is_sanitized() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="The final answer is all real numbers except x = 2.",
            display_text="Answer: x != 2",
            teaching_mode="full_solution",
            student_task="Copy x = 2 as excluded.",
            board_item="x = 2",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Domain and Range",
            message="Find the domain of f(x) = 1 / (x - 2)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 11},
        ),
        llm_client=fake_llm,
    )
    combined_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            *(item.content for item in response.board.items),
        ]
    )

    assert response.final_answer_locked is True
    assert "x = 2" not in combined_text
    assert "all real numbers except" not in combined_text
    assert response.metadata["sanitization"]["applied"] is True


def test_llm_live_stage_curriculum_example_answer_does_not_leak() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _live_stage_payload(
            spoken_text="The worked example answer is x = 2.",
            display_text="From the curriculum example: answer x = 2.",
            teaching_mode="full_solution",
            student_task="Copy the example answer x = 2.",
            board_action_latex="x = 2",
            interaction_prompt="Is the excluded value x = 2?",
            metadata={
                "curriculum_context": {
                    "worked_example": {"final_answer": "x = 2"},
                }
            },
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Domain and Range",
            message="Find the domain of f(x) = 1 / (x - 2)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 11},
        ),
        llm_client=fake_llm,
    )
    combined_text = " ".join(
        [
            response.spoken_text,
            response.display_text,
            response.student_task,
            response.interaction.prompt if response.interaction else "",
            *(action.text or "" for action in response.board_actions),
            *(action.latex or "" for action in response.board_actions),
        ]
    )

    assert response.final_answer_locked is True
    assert "x = 2" not in combined_text
    assert any(action.locked for action in response.board_actions)
    assert response.metadata["sanitization"]["applied"] is True


def test_llm_khmer_prompt_receives_khmer_term_metadata() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        _planner_payload(
            spoken_text="ពាក្យ domain មានន័យថា ដែនកំណត់។",
            display_text="ដែនកំណត់គឺតម្លៃ x ដែលអាចប្រើបាន។",
            student_task="រកមើលថា តម្លៃ x ណាធ្វើឱ្យភាគបែងសូន្យ។",
            board_item="domain: ដែនកំណត់",
        )
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Domain and Range",
            message="សូមរក domain នៃ f(x) = 1 / (x - 2)",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            locale="km-KH",
            metadata={"grade": 11},
        ),
        llm_client=fake_llm,
    )
    user_prompt = json.loads(fake_llm.calls[0]["user_prompt"])

    assert response.final_answer_locked is True
    assert "ដែនកំណត់" in response.spoken_text
    assert user_prompt["policy"]["use_khmer_explanation"] is True
    assert user_prompt["curriculum_context"]["khmer_terms"]["domain"] == "ដែនកំណត់"


def test_default_llm_client_can_use_codex_cli_provider(tmp_path, monkeypatch) -> None:
    payload = _planner_payload(
        spoken_text="Let's use one visual idea first.",
        display_text="Identify what the question asks.",
        student_task="What is the unknown?",
        board_item="Question -> unknown",
    )
    fake_codex = tmp_path / "fake_codex.py"
    fake_codex.write_text(
        "\n".join(
            [
                "import sys",
                # The real client passes --output-last-message <path> and
                # reads the JSON plan from that file, not from stdout (see
                # CodexCLIVisualTutorLLMClient.complete).
                "output_path = sys.argv[sys.argv.index('--output-last-message') + 1]",
                "with open(output_path, 'w', encoding='utf-8') as handle:",
                f"    handle.write({json.dumps(json.dumps(payload))})",
            ]
        )
    )
    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "codex_cli")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACKS", "true")
    monkeypatch.setenv(
        "VISUAL_TUTOR_CODEX_CLI_COMMAND",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(fake_codex))}",
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="English",
            message="Explain the difference between affect and effect",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert response.final_answer_locked is True
    assert response.spoken_text == "Let's use one visual idea first."
    assert response.student_task == "What is the unknown?"
    assert response.metadata["planner"] == "visual_tutor_llm_teaching_planner_v1"


def test_codex_bridge_client_returns_content(monkeypatch) -> None:
    calls = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"content": '{"spoken_text":"from bridge"}'}

    def _fake_post(url, *, headers, json, timeout):
        calls.append(
            {
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": timeout,
            }
        )
        return _Response()

    monkeypatch.setattr(
        "api.services.visual_tutor.llm_teaching_planner.httpx.post",
        _fake_post,
    )
    client = CodexCLIBridgeVisualTutorLLMClient(
        url="http://bridge.test/complete",
        timeout=12,
        token="secret",
    )

    output = client.complete(system_prompt="system", user_prompt="user")

    assert output == '{"spoken_text":"from bridge"}'
    assert calls[0]["url"] == "http://bridge.test/complete"
    assert calls[0]["headers"]["Authorization"] == "Bearer secret"
    assert calls[0]["json"]["system_prompt"] == "system"
    assert calls[0]["json"]["user_prompt"] == "user"
    # All provider work, including a development bridge call, is bounded by
    # the production planner deadline (15s cap; the requested 12s is under it).
    assert calls[0]["timeout"] == 12


def test_default_llm_client_can_use_codex_bridge_provider(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "codex_bridge")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACKS", "true")
    monkeypatch.setenv(
        "VISUAL_TUTOR_CODEX_BRIDGE_URL",
        "http://bridge.test/complete",
    )

    client = _default_llm_client()

    assert isinstance(client, CodexCLIBridgeVisualTutorLLMClient)
    assert client.url == "http://bridge.test/complete"


def test_ollama_visual_tutor_client_returns_chat_content(monkeypatch) -> None:
    calls = []

    class _Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"message": {"content": '{"spoken_text":"hi"}'}}

    def _fake_post(url, *, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return _Response()

    monkeypatch.setattr(
        "api.services.visual_tutor.llm_teaching_planner.httpx.post",
        _fake_post,
    )
    client = OllamaVisualTutorLLMClient(
        base_url="http://ollama.test",
        model="qwen-test",
        timeout=7,
    )

    output = client.complete(system_prompt="system", user_prompt="user")

    assert output == '{"spoken_text":"hi"}'
    assert calls[0]["url"] == "http://ollama.test/api/chat"
    assert calls[0]["json"]["model"] == "qwen-test"
    assert calls[0]["json"]["format"] == "json"
    assert calls[0]["timeout"] == 7


def test_llm_simplified_json_is_recovered_instead_of_template_fallback() -> None:
    fake_llm = FakeVisualTutorLLMClient(
        {
            "spoken_text": "To find an inverse, switch x and y first.",
            "teaching_mode": "student_task",
            "student_task": "Rewrite f(x) as y.",
            "board": {
                "title": "Inverse Function",
                "instruction": "Start with y = 2x + 3.",
            },
            "canvas_actions": [],
            "metadata": {"source": "ollama_like"},
        }
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Functions",
            message="Find the inverse of f(x)=2x+3",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=fake_llm,
    )

    assert response.metadata["planner"] == "visual_tutor_llm_teaching_planner_v1"
    assert response.metadata.get("planner_fallback") is not True
    assert response.metadata["llm_payload_recovered_fields"]
    assert response.spoken_text == "To find an inverse, switch x and y first."
    assert response.teaching_mode == VisualTutorTeachingMode.GUIDED_QUESTION
    assert response.board.items[0].content == "Start with y = 2x + 3."


def test_default_llm_client_allows_ollama_only_with_explicit_local_development_flag(monkeypatch) -> None:
    monkeypatch.delenv("VISUAL_TUTOR_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACKS", "true")

    client = _default_llm_client()

    assert isinstance(client, OllamaVisualTutorLLMClient)


def test_deepseek_client_uses_the_fixed_endpoint_and_default_model(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"spoken_text":"ok"}'}}]}

    def fake_post(url, *, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setattr("api.services.visual_tutor.llm_teaching_planner.httpx.post", fake_post)

    result = DeepSeekVisualTutorLLMClient(timeout=1).complete(
        system_prompt="Return JSON.",
        user_prompt="Teach one step.",
    )

    assert result == '{"spoken_text":"ok"}'
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["headers"] == {
        "Authorization": "Bearer test-deepseek-key",
        "Content-Type": "application/json",
    }
    assert captured["json"] == {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Return JSON."},
            {"role": "user", "content": "Teach one step."},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }


def test_deepseek_client_model_is_configurable_via_env(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"choices": [{"message": {"content": '{"spoken_text":"ok"}'}}]}

    def fake_post(url, *, headers, json, timeout):
        captured.update({"json": json})
        return FakeResponse()

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    monkeypatch.setattr("api.services.visual_tutor.llm_teaching_planner.httpx.post", fake_post)

    DeepSeekVisualTutorLLMClient(timeout=1).complete(
        system_prompt="Return JSON.",
        user_prompt="Teach one step.",
    )

    assert captured["json"]["model"] == "deepseek-reasoner"


def test_deepseek_client_tracks_token_usage(monkeypatch) -> None:
    class FakeResponseWithUsage:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "choices": [{"message": {"content": '{"spoken_text":"ok"}'}}],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 35,
                    "total_tokens": 155,
                },
            }

    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setattr("api.services.visual_tutor.llm_teaching_planner.httpx.post", lambda *a, **kw: FakeResponseWithUsage())

    DeepSeekVisualTutorLLMClient.reset_global_token_usage()
    client = DeepSeekVisualTutorLLMClient(timeout=1)
    client.complete(system_prompt="s", user_prompt="u")

    usage = client.get_token_usage()
    assert usage["prompt_tokens"] == 120
    assert usage["completion_tokens"] == 35
    assert usage["total_tokens"] == 155
    assert usage["call_count"] == 1

    global_usage = DeepSeekVisualTutorLLMClient.get_global_token_usage()
    assert global_usage["total_tokens"] == 155
    assert global_usage["call_count"] == 1


def test_default_llm_client_selects_deepseek_only_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")

    assert isinstance(_default_llm_client(), DeepSeekVisualTutorLLMClient)


def test_auto_provider_selects_deepseek_when_it_is_the_only_hosted_key(monkeypatch) -> None:
    monkeypatch.delenv("VISUAL_TUTOR_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")

    assert isinstance(_default_llm_client(), DeepSeekVisualTutorLLMClient)


def test_deepseek_provider_identity_does_not_mark_the_real_client_as_injected(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    assert _provider_identity(DeepSeekVisualTutorLLMClient()) == (
        "deepseek",
        "deepseek-chat",
    )


def test_default_llm_client_never_uses_auto_ollama_in_staging_or_without_flag(monkeypatch) -> None:
    monkeypatch.delenv("VISUAL_TUTOR_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACKS", "true")

    assert isinstance(_default_llm_client(), UnavailableVisualTutorLLMClient)

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACKS", "false")
    assert isinstance(_default_llm_client(), UnavailableVisualTutorLLMClient)


@pytest.mark.parametrize("provider", ["ollama", "codex_cli", "codex_bridge"])
def test_explicit_development_provider_is_rejected_outside_explicit_development(
    provider, monkeypatch
) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", provider)
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACKS", "true")

    assert isinstance(_default_llm_client(), UnavailableVisualTutorLLMClient)


def test_planner_timeout_is_never_more_than_fifteen_seconds(monkeypatch) -> None:
    monkeypatch.setenv("VISUAL_TUTOR_PLANNER_TIMEOUT_SECONDS", "120")
    assert _bounded_planner_timeout() == 15


def test_provider_failure_persists_only_safe_metric_fields() -> None:
    class SecretFailureClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            del system_prompt, user_prompt
            raise RuntimeError("provider body included student text: x = 42")

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Mathematics",
            topic="Functions",
            message="Find the inverse of f(x)=2x+3",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        llm_client=SecretFailureClient(),
    )

    assert response.metadata["planner_fallback"] is True
    assert response.metadata["planner_error"] == "provider_unavailable"
    assert response.metadata["fallback_reason"] == "provider_unavailable"
    assert response.metadata["provider_name"] == "injected"
    assert isinstance(response.metadata["latency_ms"], int)
    assert "x = 42" not in str(response.metadata)

def test_codex_cli_provider_failure_uses_template_fallback(
    tmp_path, monkeypatch
) -> None:
    fake_codex = tmp_path / "broken_codex.py"
    fake_codex.write_text(
        "\n".join(
            [
                "import sys",
                "sys.stderr.write('not signed in')",
                "raise SystemExit(7)",
            ]
        )
    )
    monkeypatch.setenv("VISUAL_TUTOR_LLM_PROVIDER", "codex_cli")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACKS", "true")
    monkeypatch.setenv(
        "VISUAL_TUTOR_CODEX_CLI_COMMAND",
        f"{shlex.quote(sys.executable)} {shlex.quote(str(fake_codex))}",
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="English",
            message="Explain the difference between affect and effect",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        )
    )

    assert response.final_answer_locked is True
    assert response.metadata["planner_fallback"] is True
    assert response.metadata["planner_error"] == "provider_unavailable"

import math
from api.services.visual_tutor.llm_teaching_planner import _compute_board_next_y

# These tests cover the guided "Try it myself" flow (answer locked, one
# step at a time); the default full-solution flow is covered elsewhere.
pytestmark = pytest.mark.usefixtures("guided_tutor_mode")

def test_compute_board_next_y_empty_list() -> None:
    assert _compute_board_next_y([]) == 40.0
    assert _compute_board_next_y(None) == 40.0

def test_compute_board_next_y_normal_elements() -> None:
    elements = [
        {"y": 10, "height": 20}, # bottom = 30
        {"y": 50, "height": 30}, # bottom = 80
        {"y": 20, "height": 10}, # bottom = 30
    ]
    # max bottom is 80, + 18 = 98.0
    assert _compute_board_next_y(elements) == 98.0

def test_compute_board_next_y_out_of_bounds() -> None:
    elements = [
        {"y": -10, "height": -20}, # bounded to 0 + 0 = 0
        {"y": 6000, "height": 6000}, # bounded to 5000 + 5000 = 10000
    ]
    # max bottom is 10000, + 18 = 10018.0
    assert _compute_board_next_y(elements) == 10018.0

def test_compute_board_next_y_inf_nan() -> None:
    elements = [
        {"y": math.inf, "height": 10}, # ignored
        {"y": 10, "height": math.nan}, # ignored
        {"y": 10, "height": 20}, # bottom = 30
    ]
    # max valid bottom is 30, + 18 = 48.0
    assert _compute_board_next_y(elements) == 48.0

def test_compute_board_next_y_hidden_and_invalid_types() -> None:
    elements = [
        {"y": 100, "height": 50, "hidden": True}, # ignored
        "not a dict", # ignored
        {"y": "100", "height": "50"}, # ignored (strings not allowed)
    ]
    assert _compute_board_next_y(elements) == 40.0
