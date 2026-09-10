"""Focused acceptance tests for the live Visual Tutor teaching timeline.

These tests intentionally exercise the planner through the public turn path.
They describe the student-visible contract: one teaching visual, a speech cue
before it, and a thinking pause afterwards. They do not prescribe a widget
implementation or expose solver-only answers.
"""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import pytest
from pydantic import ValidationError

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


@dataclass
class _FakePlanner:
    payload: dict[str, Any]

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        del system_prompt, user_prompt
        return json.dumps(self.payload, ensure_ascii=False)


def _timeline_payload(
    *,
    visual_action: dict[str, Any],
    language: str = "en",
    spoken_text: str = "Let us look at one idea at a time.",
    student_task: str = "What do you notice about this step?",
) -> dict[str, Any]:
    """Make one deliberately small, valid model completion."""
    visual_id = str(visual_action["id"])
    group_id = "current-teaching-moment"
    visual = {
        "sequence_index": 1,
        "duration_ms": 700,
        "metadata": {"group_id": group_id, "current_step": True},
        **visual_action,
    }
    return {
        "spoken_text": spoken_text,
        "display_text": spoken_text,
        "teaching_mode": "guided_question",
        "student_task": student_task,
        "mastery_signal": "exploring",
        "metadata": {"source": "timeline-policy-test"},
        "board": {
            "type": "formula_card",
            "title": "Current teaching step",
            "items": [
                {
                    "label": "Focus",
                    "content": spoken_text,
                    "status": "active",
                    "metadata": {},
                }
            ],
            "metadata": {},
        },
        "canvas_actions": [],
        "screen_state": "speaking_writing",
        "tutor_status": "Writing...",
        "speech": {
            "text": spoken_text,
            "language": language,
            "tts_status": "not_requested",
            "pause_after_ms": 0,
        },
        "board_actions": [
            {
                "id": "timeline-speak",
                "type": "speak_marker",
                "sequence_index": 0,
                "duration_ms": 0,
                "metadata": {"group_id": group_id},
            },
            visual,
            {
                "id": "timeline-highlight",
                "type": "highlight",
                "sequence_index": 2,
                "duration_ms": 220,
                "target_id": visual_id,
                "metadata": {
                    "group_id": group_id,
                    "reason": "current_step",
                    "current_step": True,
                },
            },
            {
                "id": "timeline-pause",
                "type": "pause_marker",
                "sequence_index": 3,
                "duration_ms": 900,
                "metadata": {"group_id": group_id},
            },
        ],
        "interaction": {
            "type": "text_response",
            "prompt": student_task,
            "expected_answer_locked": True,
            "validation_strategy": "teacher_review",
            "choices": [],
            "input_enabled": True,
            "submit_label": "Submit",
        },
        "allowed_actions": ["submit_answer", "request_hint", "stuck"],
        "quick_actions": ["submit_answer", "request_hint", "stuck"],
    }


_EXAMPLES = [
    pytest.param(
        "Mathematics",
        "Linear Equations",
        "2x + 5 = 15",
        {
            "id": "algebra-current-equation",
            "type": "write_equation",
            "x": 40,
            "y": 80,
            "width": 560,
            "height": 56,
            "latex": "2x + 5 = 15",
        },
        "en",
        "Focus on the constant first; do not solve the whole equation yet.",
        "What operation cancels +5?",
        id="algebra-english",
    ),
    pytest.param(
        "Mathematics",
        "Geometry",
        "A rectangle has length 8 cm and width 3 cm.",
        {
            "id": "geometry-rectangle",
            "type": "draw_rectangle",
            "x": 80,
            "y": 70,
            "width": 300,
            "height": 140,
        },
        "en",
        "Look at the rectangle before choosing a formula.",
        "Which two measurements are shown?",
        id="geometry-english",
    ),
    pytest.param(
        "Mathematics",
        "Coordinate Graphs",
        "Plot the point (2, 3).",
        {
            "id": "graph-axes",
            "type": "draw_axes",
            "x": 40,
            "y": 60,
            "width": 420,
            "height": 260,
        },
        "en",
        "Start with the coordinate axes, then locate one point.",
        "Which coordinate tells us the horizontal movement?",
        id="graphs-english",
    ),
    pytest.param(
        "Mathematics",
        "Linear Equations",
        "2x - 5 = 10",
        {
            "id": "khmer-current-step",
            "type": "write_text",
            "x": 40,
            "y": 100,
            "width": 520,
            "height": 56,
            "text": "ផ្តោតលើ -5 មុន។",
        },
        "km",
        "យើងមើលគំនិតមួយជំហានម្តង។",
        "តើប្រមាណវិធីណាអាចលុប -5?",
        id="khmer-english",
    ),
]


@pytest.mark.parametrize(
    "subject,topic,message,visual_action,language,spoken_text,student_task", _EXAMPLES
)
def test_planner_returns_one_timed_visual_teaching_moment_for_subject_examples(
    subject: str,
    topic: str,
    message: str,
    visual_action: dict[str, Any],
    language: str,
    spoken_text: str,
    student_task: str,
) -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="timeline-student",
            subject=subject,
            topic=topic,
            message=message,
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10, "language": language},
        ),
        llm_client=_FakePlanner(
            _timeline_payload(
                visual_action=visual_action,
                language=language,
                spoken_text=spoken_text,
                student_task=student_task,
            )
        ),
    )

    # The validated teaching plan, not the replay-compatible legacy action
    # list, is the authoritative active-turn playback source.
    plan = validate_teaching_plan(response.metadata["teaching_plan"])
    actions = sorted(plan.board_actions, key=lambda action: action.sequence_index)
    action_types = [action.type.value for action in actions]
    visual_actions = [
        action
        for action in actions
        if action.type.value
        not in {
            "speak_marker",
            "pause_marker",
            "highlight",
            "focus",
            "fade_previous",
            "student_task",
        }
    ]

    # A turn is a single teachable visual, not a mini lesson page.
    assert len(visual_actions) == 1
    visible = visual_actions[0]
    assert visible.type.value == visual_action["type"]
    assert 200 <= visible.duration_ms <= 5_000

    # The timeline always says first, draws second, then gives thinking time.
    speak_index = action_types.index("speak_marker")
    pause_index = action_types.index("pause_marker")
    visible_index = actions.index(visible)
    assert speak_index < visible_index < pause_index
    assert 250 <= actions[pause_index].duration_ms <= 5_000

    highlights = [action for action in actions if action.type.value == "highlight"]
    assert len(highlights) == 1
    assert highlights[0].target_id == visible.id

    # The policy owns final answers. A first turn must never leak one through
    # spoken copy, visible action text, or LaTex.
    assert response.final_answer_locked is True
    public_text = " ".join(
        value
        for action in actions
        for value in (action.text or "", action.latex or "", action.label or "")
    )
    assert (
        "x = 5"
        not in f"{response.spoken_text} {response.display_text} {public_text}".lower()
    )


def test_planner_removes_a_premature_final_answer_but_keeps_the_current_visual() -> (
    None
):
    payload = _timeline_payload(
        visual_action={
            "id": "safe-current-equation",
            "type": "write_equation",
            "x": 40,
            "y": 80,
            "width": 560,
            "height": 56,
            "latex": "2x + 5 = 15",
        },
        spoken_text="We will make only the first inverse-operation step.",
        student_task="What should we do to +5?",
    )
    # Deliberately adversarial output. The server must not send it while the
    # policy locks the final answer.
    payload["board_actions"].insert(
        2,
        {
            "id": "premature-final",
            "type": "write_equation",
            "sequence_index": 2,
            "duration_ms": 700,
            "x": 40,
            "y": 160,
            "width": 560,
            "height": 56,
            "latex": "x = 5",
            "metadata": {"group_id": "future-step", "is_final_answer": True},
        },
    )

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="timeline-student",
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        ),
        llm_client=_FakePlanner(payload),
    )

    assert response.final_answer_locked is True
    plan = validate_teaching_plan(response.metadata["teaching_plan"])
    assert any(
        action.id == "plan-safe-current-equation" for action in plan.board_actions
    )
    assert all(
        "x = 5" not in f"{action.text or ''} {action.latex or ''}".lower()
        for action in plan.board_actions
    )


def test_planner_repairs_a_model_timeline_with_two_visuals_and_no_markers() -> None:
    """The model may be verbose; the server still emits one teachable moment."""
    payload = _timeline_payload(
        visual_action={
            "id": "keep-current",
            "type": "write_text",
            "x": 40,
            "y": 80,
            "width": 520,
            "height": 56,
            "text": "Focus on the coefficient beside x.",
        },
        student_task="Which operation removes the coefficient?",
    )
    # This is a realistic, but invalid-for-live-playback, raw model completion:
    # it has two drawings and no timing markers. The planner must normalize it
    # rather than let the client guess what belongs to the active step.
    payload["board_actions"] = [
        payload["board_actions"][1],
        {
            "id": "drop-future",
            "type": "write_text",
            "sequence_index": 2,
            "duration_ms": 700,
            "x": 40,
            "y": 150,
            "width": 520,
            "height": 56,
            "text": "A later step must wait.",
            "metadata": {"current_step": False},
        },
    ]

    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="timeline-student",
            subject="Mathematics",
            topic="Linear Equations",
            message="2x + 5 = 15",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 10},
        ),
        llm_client=_FakePlanner(payload),
    )

    plan = validate_teaching_plan(response.metadata["teaching_plan"])
    actions = sorted(plan.board_actions, key=lambda action: action.sequence_index)
    visual_actions = [
        action
        for action in actions
        if action.type.value
        not in {
            "speak_marker",
            "pause_marker",
            "highlight",
            "focus",
            "fade_previous",
            "student_task",
        }
    ]
    assert [action.id for action in visual_actions] == ["plan-keep-current"]
    assert [action.type.value for action in actions].index(
        "speak_marker"
    ) < actions.index(visual_actions[0])
    assert actions.index(visual_actions[0]) < [
        action.type.value for action in actions
    ].index("pause_marker")


def _strict_timeline_plan() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "representation": "equation_transformation",
        "learning_objective": "Make one verified algebra step.",
        "teaching_message": "Use one inverse operation, then think before continuing.",
        "board_actions": [
            {
                "id": "plan-speak",
                "type": "speak_marker",
                "sequence_index": 0,
                "duration_ms": 0,
            },
            {
                "id": "plan-equation",
                "type": "write_equation",
                "sequence_index": 1,
                "duration_ms": 650,
                "x": 40,
                "y": 80,
                "width": 520,
                "height": 56,
                "latex": "2x + 5 = 15",
                "wait_for_speech_marker": True,
            },
            {
                "id": "plan-highlight",
                "type": "highlight",
                "sequence_index": 2,
                "duration_ms": 220,
                "target_id": "plan-equation",
            },
            {
                "id": "plan-pause",
                "type": "pause_marker",
                "sequence_index": 3,
                "duration_ms": 800,
            },
            {
                "id": "plan-task",
                "type": "student_task",
                "sequence_index": 4,
                "text": "What operation cancels +5?",
                "requires_student_response": True,
                "task_type": "conceptual_operation",
                "accepted_answer_forms": ["operation words"],
            },
        ],
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
    }


def test_teaching_plan_contract_rejects_missing_markers_and_multiple_visual_ideas() -> (
    None
):
    valid = _strict_timeline_plan()
    plan = validate_teaching_plan(valid)
    assert [action.type.value for action in plan.board_actions[:4]] == [
        "speak_marker",
        "write_equation",
        "highlight",
        "pause_marker",
    ]

    missing_speak = deepcopy(valid)
    missing_speak["board_actions"] = missing_speak["board_actions"][1:]
    with pytest.raises(ValidationError, match="preceding speak marker"):
        validate_teaching_plan(missing_speak)

    two_visuals = deepcopy(valid)
    two_visuals["board_actions"].insert(
        2,
        {
            "id": "later-diagram",
            "type": "draw_rectangle",
            "sequence_index": 2,
            "duration_ms": 700,
            "x": 40,
            "y": 160,
            "width": 240,
            "height": 100,
        },
    )
    with pytest.raises(ValidationError, match="one primary visual idea"):
        validate_teaching_plan(two_visuals)
