"""Regression tests for the compact, student-safe tutor-turn API envelope."""
from __future__ import annotations

import json

from api.models.visual_tutor import (
    VisualTutorBoard,
    VisualTutorBoardType,
    VisualTutorMasterySignal,
    VisualTutorTeachingMode,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.public_response import project_public_tutor_turn


def _response() -> VisualTutorTurnResponse:
    return VisualTutorTurnResponse(
        session_id="session-public-1",
        turn_id="turn-public-1",
        tutor_status="Waiting for you",
        spoken_text="Keep both sides balanced.",
        display_text="Keep both sides balanced.",
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="What operation removes +5?",
        board=VisualTutorBoard(type=VisualTutorBoardType.EQUATION),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        board_version=7,
        metadata={
            "solver_facts": {"solution_set": "x = 5"},
            "curriculum_context": {"chunks": [{"content": "private RAG"}]},
            "replay_snapshots": [{"private": True}],
            "verification": {
                "status": "incomplete",
                "verified": False,
                "student_message": "Show the operation on both sides.",
                "concise_evidence": "The equation has not changed yet.",
                "raw_evidence": {"expected_step": "subtract 5"},
            },
            "teaching_plan": {
                "schema_version": 1,
                "representation": "equation_transformation",
                "learning_objective": "Use inverse operations to keep both sides equal.",
                "teaching_message": "First remove the constant from both sides.",
                "board_actions": [
                    {
                        "id": "equation",
                        "type": "write_equation",
                        "sequence_index": 0,
                        "latex": "2x + 5 = 15",
                    },
                    {
                        "id": "hidden-private",
                        "type": "write_text",
                        "sequence_index": 1,
                        "text": "The hidden answer is x = 5.",
                        "hidden": True,
                    },
                    {
                        "id": "task",
                        "type": "student_task",
                        "sequence_index": 2,
                        "text": "What operation removes +5?",
                        "requires_student_response": True,
                        "task_type": "conceptual_operation",
                        "accepted_answer_forms": ["operation words"],
                        "expected_operation": "subtract 5",
                        "expected_step": "2x = 10",
                    },
                ],
                "allowed_student_actions": ["submit_answer", "request_hint", "stuck"],
                "hidden_answer_policy": {
                    "mode": "hidden",
                    "deterministic_policy_permits_final_reveal": False,
                },
                "next_state_policy": {
                    "correct": "continue",
                    "invalid": "reteach",
                    "incomplete": "ask_for_work",
                    "stuck": "reteach",
                    "hint": "ask_for_work",
                    "explain_differently": "reteach",
                },
            },
        },
    )


def test_public_projection_has_exact_compact_envelope_and_no_persistence_internals() -> None:
    projected = project_public_tutor_turn(_response())

    assert set(projected) == {
        "schema_version", "session_id", "turn_id", "board_version", "base_board_version", "board_update_mode", "lesson_state", "tutor_status",
        "teaching_plan", "verification", "recovery",
    }
    assert projected["schema_version"] == 2
    assert set(projected["teaching_plan"]) == {
        "schema_version", "representation", "learning_objective", "teaching_message",
        "visible_board_actions", "active_student_task", "allowed_student_actions",
        "hidden_answer_policy", "next_state_policy",
    }
    assert [action["id"] for action in projected["teaching_plan"]["visible_board_actions"]] == ["equation"]
    task = projected["teaching_plan"]["active_student_task"]
    assert task["id"] == "task"
    assert "expected_operation" not in task
    assert "expected_step" not in task
    assert "accepted_answer_forms" not in task
    assert set(projected["verification"]) == {
        "status", "verified", "concise_evidence", "student_facing_feedback",
    }

    serialized = json.dumps(projected)
    for private_key in (
        "solver_facts", "curriculum_context", "replay_snapshots", "raw_evidence",
        "expected_operation", "expected_step", "hidden-private", "x = 5",
    ):
        assert private_key not in serialized


def test_invalid_persisted_plan_recovers_with_a_valid_student_safe_plan() -> None:
    response = _response()
    response.metadata["teaching_plan"] = {"schema_version": 999}

    projected = project_public_tutor_turn(response)

    assert projected["recovery"] == {"state": "invalid_teaching_plan"}
    assert projected["teaching_plan"]["schema_version"] == 1
    assert projected["teaching_plan"]["active_student_task"]["id"] == "safe-recovery-task"


def test_invalid_action_becomes_notice_without_hiding_valid_siblings() -> None:
    response = _response()
    response.metadata["teaching_plan"]["board_actions"].insert(1, {
        "id": "unsafe-widget",
        "type": "write_text",
        "sequence_index": 1,
        "text": "This action is malformed.",
        "widget_code": "Text('never execute')",
    })

    projected = project_public_tutor_turn(response)
    visible = projected["teaching_plan"]["visible_board_actions"]

    assert projected["recovery"] == {"state": "partial_action_recovery"}
    assert [action["id"] for action in visible] == ["equation", "board-recovery-1"]
    assert visible[1]["type"] == "show_feedback"
    assert projected["teaching_plan"]["active_student_task"]["id"] == "task"
    assert "widget_code" not in json.dumps(projected)


def test_public_projection_never_turns_a_hidden_answer_into_a_visible_action() -> None:
    projected = project_public_tutor_turn(_response())
    actions = projected["teaching_plan"]["visible_board_actions"]
    active_task = projected["teaching_plan"]["active_student_task"]

    assert all(action.get("hidden") is not True for action in [*actions, active_task])
    assert projected["teaching_plan"]["hidden_answer_policy"]["mode"] == "hidden"
    assert (
        projected["teaching_plan"]["hidden_answer_policy"].get(
            "deterministic_policy_permits_final_reveal"
        )
        is not True
    )


def test_public_projection_keeps_renderer_safe_layout_and_strips_task_verifier_fields() -> None:
    """A public board action must never make Flutter reject the entire turn.

    Semantic layout is renderer-safe public data.  Answer forms and expected
    work are server-side verifier inputs, so they must be removed without
    dropping the valid visible action or its student task.
    """
    response = _response()
    plan = response.metadata["teaching_plan"]
    visual_action = plan["board_actions"][0]
    visual_action.update(
        {
            "section_id": "logic-intro",
            "layout_zone": "working",
            "layout_flow": "vertical",
            "accepted_answer_forms": ["private form"],
            "expected_operation": "private operation",
            "expected_step": "private expected step",
        }
    )

    projected = project_public_tutor_turn(response)
    visible = projected["teaching_plan"]["visible_board_actions"]
    task = projected["teaching_plan"]["active_student_task"]

    assert [action["id"] for action in visible] == ["equation"]
    assert visible[0]["section_id"] == "logic-intro"
    assert visible[0]["layout_zone"] == "working"
    assert visible[0]["layout_flow"] == "vertical"
    assert task["id"] == "task"
    public_actions = json.dumps([*visible, task])
    for private_field in (
        "accepted_answer_forms",
        "expected_operation",
        "expected_step",
        "private form",
        "private operation",
        "private expected step",
    ):
        assert private_field not in public_actions
    # Pydantic's persisted representation can contain empty optional STEM
    # primitives. They are neither needed for this text action nor part of
    # the compact public action; sending them makes strict clients reject an
    # otherwise valid teaching moment as if it had private data.
    for unused_primitive in (
        "forces",
        "molecule_bonds",
        "atom_model",
        "particle_diagram",
        "circuit_diagram",
        "reaction_layout",
    ):
        assert unused_primitive not in visible[0]
        assert unused_primitive not in task


def test_locked_public_verification_never_leaks_a_solution_or_expected_transformation() -> None:
    response = _response()
    response.metadata["verification"] = {
        "status": "correct",
        "verified": True,
        "student_message": "Correct: x = 5. Now divide by 2.",
        "concise_evidence": "The solution set is {x = 5}; expected step: 2x = 10.",
    }

    projected = project_public_tutor_turn(response)

    assert projected["verification"]["verified"] is True
    assert "x = 5" not in json.dumps(projected["verification"])
    assert "2x = 10" not in json.dumps(projected["verification"])


def test_public_board_snapshot_is_bound_to_the_single_active_lesson_step() -> None:
    response = _response().model_copy(
        update={
            "authoritative_lesson_state": {
                "problem_instance_id": "problem-release-check",
                "lesson_id": "lesson-release-check",
                "active_step_id": "lesson-release-check:step-2:task",
                "current_step_index": 2,
                "expected_student_action_id": "task",
                "teaching_stage": "waiting_for_student",
                "lesson_state": "ask",
                "final_answer_locked": True,
                "board_version": 9,
                "base_board_version": 8,
            },
            "board_version": 9,
            "base_board_version": 8,
        }
    )

    projected = project_public_tutor_turn(response)

    assert projected["lesson_state"]["active_step_id"] == "lesson-release-check:step-2:task"
    assert projected["lesson_state"]["current_step_index"] == 2
    for action in [
        *projected["teaching_plan"]["visible_board_actions"],
        projected["teaching_plan"]["active_student_task"],
    ]:
        assert action["problem_instance_id"] == "problem-release-check"
        assert action["active_step_id"] == projected["lesson_state"]["active_step_id"]
        assert action["board_version"] == 9
        assert action["base_board_version"] == 8
