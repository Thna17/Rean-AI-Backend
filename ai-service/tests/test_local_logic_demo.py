"""Regression tests for the deterministic local Grade 10 Logic demo.

The demo is deliberately a development fallback, not a published curriculum
lesson.  These tests keep its hidden answer server-side while requiring the
same renderer-safe teaching-plan contract used by ordinary tutor turns.
"""
from __future__ import annotations

import json

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.local_logic_demo import (
    build_local_logic_demo_turn,
    matches_local_logic_demo,
)
from api.services.visual_tutor.public_response import project_public_tutor_turn
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


_LESSON_ID = "math.g10.part1.logic.1.1.statements"
_CURRICULUM_VERSION = "moeys-g10-math-part1.local-demo"
_QUESTION = "២ ជាចំនួនបឋម"


def _request(
    *,
    message: str = "",
    action: VisualTutorAction = VisualTutorAction.START,
    current_step_index: int = 0,
    wrong_attempts: int = 0,
) -> VisualTutorTurnRequest:
    return VisualTutorTurnRequest(
        user_id="local-demo-test-student",
        session_id="local-demo-session",
        subject="Mathematics",
        topic="Logic",
        language_mode="khmer",
        action=action,
        message=message,
        current_state=VisualTutorTurnState(
            lesson_id=_LESSON_ID,
            current_step_index=current_step_index,
            wrong_attempts=wrong_attempts,
        ),
        metadata={
            "entry_context": "lesson",
            "is_curriculum_scoped": True,
            "grade": 10,
            "grade_level_id": "grade-10",
            "subject_id": "math",
            "topic_id": "math-g10-part1-logic",
            "lesson_id": _LESSON_ID,
            "teaching_moment_id": _LESSON_ID,
            "curriculum_version_id": _CURRICULUM_VERSION,
        },
    )


def _public_payload(response) -> dict[str, object]:
    return project_public_tutor_turn(response)


def test_matches_only_the_explicit_scoped_grade_10_logic_local_demo() -> None:
    assert matches_local_logic_demo(_request()) is True

    wrong_topic = _request().model_copy(update={"topic": "Linear Equations"})
    assert matches_local_logic_demo(wrong_topic) is False

    unscoped = _request().model_copy(
        update={"metadata": {"entry_context": "ask_question", "is_curriculum_scoped": False}}
    )
    assert matches_local_logic_demo(unscoped) is False


def test_opening_builds_one_small_khmer_first_teacher_moment_without_an_answer() -> None:
    response = build_local_logic_demo_turn(_request(), session_id="local-demo-session")

    assert response.session_id == "local-demo-session"
    assert response.final_answer_locked is True
    assert response.student_task == f"“{_QUESTION}” ជាសំណើពិត ឬមិនពិត?"
    assert _QUESTION in response.spoken_text
    assert response.metadata["local_curriculum_demo"] is True
    assert response.metadata["lesson_id"] == _LESSON_ID
    assert response.metadata["source_id"] == "moeys-math-g10-part1-2020-ch1-logic"
    assert response.metadata["source_page"] == 9

    plan = validate_teaching_plan(response.metadata["teaching_plan"])
    assert plan.schema_version == 1
    assert len(plan.board_actions) <= 3
    assert [action.type.value for action in plan.board_actions].count("student_task") == 1
    assert all(action.layout_zone is not None for action in plan.board_actions)
    assert all(action.layout_flow is not None for action in plan.board_actions)
    assert plan.hidden_answer_policy.mode.value == "hidden"
    assert plan.hidden_answer_policy.deterministic_policy_permits_final_reveal is False
    assert not any(action.type.value == "final_answer_reveal" for action in plan.board_actions)

def test_public_local_demo_payload_has_a_board_update_and_locked_answer() -> None:
    public = _public_payload(build_local_logic_demo_turn(_request(), session_id="local-demo-session"))
    plan = public["teaching_plan"]

    assert plan["active_student_task"]["text"] == f"“{_QUESTION}” ជាសំណើពិត ឬមិនពិត?"
    assert plan["hidden_answer_policy"]["mode"] == "hidden"
    assert len(plan["visible_board_actions"]) >= 1

    serialized = json.dumps(public, ensure_ascii=False)
    for private_field in ("accepted_answer_forms", "expected_operation", "expected_step"):
        assert private_field not in serialized


def test_correct_response_advances_exactly_one_step_without_revealing_a_final_answer() -> None:
    response = build_local_logic_demo_turn(
        _request(message="ពិត", action=VisualTutorAction.SUBMIT_STEP),
        session_id="local-demo-session",
    )

    assert response.final_answer_locked is True
    assert response.authoritative_lesson_state["current_step_index"] == 1
    assert response.authoritative_lesson_state["final_answer_locked"] is True
    assert response.metadata["local_curriculum_demo"] is True
    assert response.metadata["evaluation"]["outcome"] == "correct"
    assert "final_answer_reveal" not in json.dumps(response.metadata, ensure_ascii=False)


def test_incorrect_response_reteaches_only_the_statement_classification_point() -> None:
    response = build_local_logic_demo_turn(
        _request(
            message="មិនពិត",
            action=VisualTutorAction.SUBMIT_STEP,
            wrong_attempts=1,
        ),
        session_id="local-demo-session",
    )

    assert response.final_answer_locked is True
    assert response.authoritative_lesson_state["current_step_index"] == 0
    assert response.authoritative_lesson_state["final_answer_locked"] is True
    assert response.metadata["evaluation"]["outcome"] == "incorrect"
    assert response.metadata["evaluation"]["misconception_category"] == "statement_truth_value"
    assert "final_answer_reveal" not in json.dumps(response.metadata, ensure_ascii=False)


def test_retry_rebuilds_the_same_first_moment_without_advancing_or_exposing_an_answer() -> None:
    first = build_local_logic_demo_turn(_request(), session_id="local-demo-session")
    retry = build_local_logic_demo_turn(_request(), session_id="local-demo-session")

    first_plan = first.metadata["teaching_plan"]
    retry_plan = retry.metadata["teaching_plan"]
    assert first.final_answer_locked is True
    assert retry.final_answer_locked is True
    assert first.student_task == retry.student_task
    assert first_plan == retry_plan
    assert retry.authoritative_lesson_state["current_step_index"] == 0


def test_offline_fallback_delivers_identical_first_moment() -> None:
    """Provider-independent path (START and SUBMIT_PROBLEM) must return the same
    first teaching moment so the lesson works when the AI backend is unavailable.
    """
    via_start = build_local_logic_demo_turn(
        _request(action=VisualTutorAction.START),
        session_id="local-demo-session",
    )
    via_submit = build_local_logic_demo_turn(
        _request(action=VisualTutorAction.SUBMIT_PROBLEM),
        session_id="local-demo-session",
    )

    # Both paths must return the opening teaching moment — not a blank board.
    assert via_start.student_task == via_submit.student_task
    assert via_start.final_answer_locked is True
    assert via_submit.final_answer_locked is True
    assert via_start.authoritative_lesson_state["current_step_index"] == 0
    assert via_submit.authoritative_lesson_state["current_step_index"] == 0

    # The first board action must be identical so Flutter renders the same
    # Khmer-first teaching moment regardless of which action triggered it.
    start_actions = via_start.metadata["teaching_plan"]["board_actions"]
    submit_actions = via_submit.metadata["teaching_plan"]["board_actions"]
    assert start_actions == submit_actions

    # The answer must remain locked in both paths.
    start_json = json.dumps(via_start.metadata, ensure_ascii=False)
    submit_json = json.dumps(via_submit.metadata, ensure_ascii=False)
    assert "final_answer_reveal" not in start_json
    assert "final_answer_reveal" not in submit_json
    assert via_start.metadata["local_curriculum_demo"] is True
    assert via_submit.metadata["local_curriculum_demo"] is True


def test_opening_board_actions_are_non_blank_with_valid_types() -> None:
    """Every board action in the opening turn must have non-empty renderable
    content so the whiteboard never shows a blank panel.  An invalid sibling
    action must not prevent the valid primary teaching action from rendering.
    """
    response = build_local_logic_demo_turn(_request(), session_id="local-demo-session")

    _TEXT_TYPES = {"write_text", "write_equation", "show_hint", "show_feedback", "student_task"}
    _ALL_KNOWN_TYPES = {
        "write_text", "write_equation", "transform_equation", "highlight",
        "cross_out", "fade_previous", "speak_marker", "pause_marker",
        "draw_rectangle", "circle", "draw_arrow", "draw_point", "show_hint",
        "show_feedback", "student_task", "show_number_line", "draw_axes",
        "show_graph", "plot_function", "graph_annotation", "show_table",
        "draw_free_body_diagram", "draw_molecule", "draw_wave", "draw_atom_model",
        "draw_particle_diagram", "draw_circuit_diagram", "show_reaction_layout",
        "final_answer_reveal",
    }

    plan = validate_teaching_plan(response.metadata["teaching_plan"])
    actions = plan.board_actions

    # There must be at least one primary (non-control) visible action.
    visible = [
        a for a in actions
        if a.type.value not in {"speak_marker", "pause_marker", "fade_previous"}
        and a.type.value != "final_answer_reveal"
        and not a.hidden
    ]
    assert visible, "Opening board must have at least one visible teaching action"

    for action in actions:
        # All types must be within the known set — no remote_widget or arbitrary code.
        assert action.type.value in _ALL_KNOWN_TYPES, (
            f"action {action.id!r} has unknown type {action.type.value!r}"
        )
        # Text-bearing action types must never be blank.
        if action.type.value in _TEXT_TYPES:
            assert (action.text or "").strip() or (action.latex or "").strip(), (
                f"action {action.id!r} of type {action.type.value!r} has blank content"
            )
        # All teaching-plan actions must have semantic layout — never raw coordinates.
        assert action.layout_zone is not None, (
            f"action {action.id!r} is missing a layout_zone"
        )
