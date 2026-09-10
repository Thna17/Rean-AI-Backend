"""Student-safe projection of a persisted Visual Tutor turn.

The persisted response intentionally contains replay state, solver facts and
planner audit data.  This projection is the only shape returned to Flutter.
"""
from __future__ import annotations

import re
from typing import Any

from api.models.visual_tutor import PublicVisualTutorSession, VisualTutorSession, VisualTutorTurnResponse
from api.services.visual_tutor.teaching_plan_contract import (
    TeachingPlanAction,
    validate_teaching_plan,
)


PUBLIC_TUTOR_TURN_SCHEMA_VERSION = 2


def project_public_session(session: VisualTutorSession) -> PublicVisualTutorSession:
    """Allow session resume without leaking solver, replay, or learner state."""
    allowed_lesson_keys = {
        "problem_instance_id", "lesson_id", "active_step_id", "current_step_index",
        "expected_student_action_id", "teaching_stage", "lesson_state",
        "final_answer_locked", "board_version", "base_board_version",
    }
    lesson_state = {
        key: value for key, value in (session.authoritative_lesson_state or {}).items()
        if key in allowed_lesson_keys
    }
    return PublicVisualTutorSession(
        session_id=session.session_id, session_mode=session.session_mode,
        subject=session.subject, grade_level=session.grade_level, topic=session.topic,
        problem_text=session.problem_text, current_step_index=session.current_step_index,
        hint_count=session.hint_count, wrong_attempts=session.wrong_attempts,
        final_answer_revealed=session.final_answer_revealed,
        board_version=session.board_version,
        authoritative_lesson_state=lesson_state,
        curriculum_chunk_ids=list(session.curriculum_chunk_ids), status=session.status,
        created_at=session.created_at, updated_at=session.updated_at,
    )


def project_public_tutor_turn(response: VisualTutorTurnResponse) -> dict[str, Any]:
    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    raw_plan = metadata.get("teaching_plan")
    if not isinstance(raw_plan, dict):
        raise ValueError("Visual Tutor turn is missing its validated teaching plan")
    # Revalidate at the public boundary. A corrupt *action* is not a reason to
    # discard the rest of a teaching moment: project valid siblings and place a
    # compact, renderer-safe notice in the same section instead.
    try:
        # Keep the public action payload compact. Pydantic otherwise emits
        # every empty STEM primitive field (for example ``forces: []``) on a
        # simple text action. Those fields are safe but irrelevant, and older
        # public gateways correctly reject unknown action keys. Only fields
        # that the validated plan actually uses may cross this boundary.
        plan = _normalize_plan_for_public_projection(raw_plan)
        recovery_state = "ready"
    except (TypeError, ValueError):
        plan = _safe_recovery_plan()
        recovery_state = "invalid_teaching_plan"
    lesson_state = _public_lesson_state(response)
    actions, recovered_actions = _project_public_actions(
        plan.get("board_actions", []), lesson_state=lesson_state
    )
    if recovered_actions:
        recovery_state = "partial_action_recovery"
    active_task = next(
        (action for action in actions if action.get("requires_student_response") is True),
        None,
    )
    visible_actions = [
        action for action in actions if action is not active_task
    ]
    hidden_answer_policy = plan.get("hidden_answer_policy", {
        "mode": "hidden" if response.final_answer_locked else "reveal_allowed",
        "deterministic_policy_permits_final_reveal": not response.final_answer_locked,
    })
    if isinstance(hidden_answer_policy, dict):
        # ``exclude_defaults=True`` omits the default false value. Keep it
        # explicit at the public boundary so a client never has to infer an
        # answer-lock policy from a missing field.
        hidden_answer_policy = {
            **hidden_answer_policy,
            "deterministic_policy_permits_final_reveal": bool(
                hidden_answer_policy.get("deterministic_policy_permits_final_reveal")
            ),
        }
    public_plan = {
        "schema_version": plan.get("schema_version", PUBLIC_TUTOR_TURN_SCHEMA_VERSION),
        "representation": plan.get("representation", "conceptual_explanation"),
        "learning_objective": plan.get("learning_objective", response.display_text),
        "teaching_message": plan.get("teaching_message", response.display_text),
        "visible_board_actions": visible_actions,
        "active_student_task": active_task,
        "allowed_student_actions": plan.get("allowed_student_actions", []),
        "hidden_answer_policy": hidden_answer_policy,
        "next_state_policy": plan.get("next_state_policy", {}),
    }
    stored_verification = metadata.get("verification")
    stored_verification = (
        dict(stored_verification) if isinstance(stored_verification, dict) else {}
    )
    # Do not forward raw solver evidence, solution sets, or the expected next
    # step.  They are useful for persistence and audit, but may disclose a
    # locked answer.  The app receives just enough deterministic feedback to
    # guide the student's next move.
    if response.final_answer_locked:
        # Even a deterministic verifier can contain a solution set or expected
        # transformation. While locked, return only a status-level message.
        feedback = _locked_verification_feedback(stored_verification.get("status"))
        concise_evidence = feedback
    else:
        feedback = stored_verification.get("student_message")
        if not isinstance(feedback, str) or not feedback.strip():
            feedback = "Submit your next step when you are ready."
        concise_evidence = stored_verification.get("concise_evidence")
        if not isinstance(concise_evidence, str) or not concise_evidence.strip():
            concise_evidence = feedback
    verification = {
        "status": stored_verification.get("status", "cannot_verify"),
        "verified": stored_verification.get("verified", False) is True,
        "concise_evidence": concise_evidence,
        "student_facing_feedback": feedback,
    }
    return {
        "schema_version": PUBLIC_TUTOR_TURN_SCHEMA_VERSION,
        "session_id": response.session_id,
        "turn_id": response.turn_id,
        "board_version": response.board_version,
        "base_board_version": response.base_board_version,
        "board_update_mode": metadata.get("board_update_mode", "replace"),
        "lesson_state": lesson_state,
        "tutor_status": response.tutor_status,
        "teaching_plan": public_plan,
        "verification": verification,
        "recovery": {"state": recovery_state},
    }


def _public_board_action(action: dict[str, Any], *, lesson_state: dict[str, Any]) -> dict[str, Any]:
    """Strip server-only answer targets and planner data from a board action."""
    allowed = {
        "id", "type", "sequence_index", "duration_ms", "wait_for_speech_marker", "x", "y", "width", "height",
        "section_id", "layout_zone", "layout_flow",
        "text", "latex", "target_id", "graph", "points", "label",
        "number_line", "table",
        "forces", "molecule_bonds", "atom_model", "particle_diagram", "circuit_diagram", "reaction_layout",
        "requires_student_response", "task_type",
        "explanation_required",
    }
    public = {key: value for key, value in action.items() if key in allowed}
    # Target IDs are renderer references, never student-facing solution text.
    # Accepted answer forms describe hidden verifier policy and can disclose the
    # answer while the final answer remains locked, so they are not public.
    target_id = public.get("target_id")
    if target_id is not None and (
        not isinstance(target_id, str)
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", target_id)
    ):
        public.pop("target_id", None)
    public.update({key: lesson_state[key] for key in ("problem_instance_id", "active_step_id", "board_version", "base_board_version") if lesson_state.get(key) is not None})
    public["action_id"] = str(action.get("id") or "")
    return public


def _normalize_plan_for_public_projection(raw_plan: dict[str, Any]) -> dict[str, Any]:
    """Validate the plan envelope while tolerating one corrupt persisted action.

    ``VisualTutorTeachingPlan`` intentionally validates all actions together.
    At the public boundary we first validate the normal path, then fall back to
    a bounded envelope whose individual actions are validated below. This keeps
    a malformed legacy action from erasing an otherwise valid lesson.
    """
    try:
        validate_teaching_plan(raw_plan)
        # Keep the original action maps until per-action projection below.
        # Pydantic's dump intentionally omits forbidden legacy keys, but then
        # the public boundary could not tell a stripped unsafe action from a
        # valid one and would omit the recoverable board notice.
        return dict(raw_plan)
    except (TypeError, ValueError):
        required = {
            "schema_version", "representation", "learning_objective",
            "teaching_message", "allowed_student_actions",
            "hidden_answer_policy", "next_state_policy", "board_actions",
        }
        if not required.issubset(raw_plan) or not isinstance(raw_plan.get("board_actions"), list):
            raise
        # The action list is repaired individually by _project_public_actions.
        return dict(raw_plan)


def _project_public_actions(
    raw_actions: Any, *, lesson_state: dict[str, Any]
) -> tuple[list[dict[str, Any]], bool]:
    if not isinstance(raw_actions, list):
        return [], True
    projected: list[dict[str, Any]] = []
    recovered = False
    seen_ids: set[str] = set()
    for index, raw_action in enumerate(raw_actions[:24]):
        action = raw_action if isinstance(raw_action, dict) else None
        if action is None or action.get("hidden") is True:
            continue
        try:
            known_internal_keys = {
                "id", "type", "sequence_index", "duration_ms", "wait_for_speech_marker",
                "section_id", "layout_zone", "layout_flow", "x", "y", "width", "height",
                "text", "latex", "target_id", "graph", "points", "label", "number_line", "table",
                "forces", "molecule_bonds", "atom_model", "particle_diagram", "circuit_diagram",
                "reaction_layout", "hidden", "requires_student_response", "task_type",
                "accepted_answer_forms", "expected_operation", "expected_step", "explanation_required",
            }
            if any(key not in known_internal_keys for key in action):
                raise ValueError("unsupported board action field")
            # Validation occurs after projection so server-only verifier fields
            # never become a client-side contract requirement.
            public = _public_board_action(action, lesson_state=lesson_state)
            # ``action_id`` and board identities are public envelope fields,
            # not persisted-plan fields, so remove them for strict model
            # validation and add them back only after it succeeds.
            contract_action = {
                key: value for key, value in public.items()
                if key not in {"problem_instance_id", "active_step_id", "action_id", "board_version", "base_board_version"}
            }
            validated = TeachingPlanAction.model_validate(contract_action).model_dump(
                mode="json", exclude_none=True, exclude_defaults=True
            )
            public = _public_board_action(validated, lesson_state=lesson_state)
            action_id = public.get("id")
            if not isinstance(action_id, str) or action_id in seen_ids:
                raise ValueError("duplicate or missing public action id")
            seen_ids.add(action_id)
            projected.append(public)
        except (TypeError, ValueError):
            recovered = True
            notice_id = f"board-recovery-{index}"
            while notice_id in seen_ids:
                notice_id = f"{notice_id}-notice"
            seen_ids.add(notice_id)
            projected.append(_public_board_action({
                "id": notice_id,
                "type": "show_feedback",
                "sequence_index": min(index, 23),
                "text": "One board item could not be shown. Continue with this step.",
                "layout_zone": "feedback",
                "layout_flow": "vertical",
            }, lesson_state=lesson_state))
    return projected, recovered


def _public_lesson_state(response: VisualTutorTurnResponse) -> dict[str, Any]:
    state = response.authoritative_lesson_state or response.metadata.get("authoritative_lesson_state", {})
    allowed = {"problem_instance_id", "lesson_id", "active_step_id", "current_step_index", "expected_student_action_id", "teaching_stage", "lesson_state", "final_answer_locked", "board_version", "base_board_version"}
    return {key: value for key, value in state.items() if key in allowed}


def _locked_verification_feedback(status: object) -> str:
    return {
        "correct": "That step is verified. Continue with the requested next step.",
        "mathematically_valid_but_inefficient": "That work is mathematically valid. Try the requested step next.",
        "invalid": "This step needs a correction. Check the operation requested on the board.",
        "incomplete": "This step is not complete yet. Finish the requested transformation.",
    }.get(str(status), "Math check unavailable. Write one clear equation step and try again.")


def _safe_recovery_plan() -> dict[str, Any]:
    """Return a complete, non-sensitive plan when persisted planner data is bad."""
    return {
        "schema_version": 1,
        "representation": "conceptual_explanation",
        "learning_objective": "Continue with one clear math step.",
        "teaching_message": "This teaching step needs to be refreshed safely.",
        "board_actions": [
            {
                "id": "safe-recovery-message",
                "type": "write_text",
                "sequence_index": 0,
                "text": "Please retry this step.",
            },
            {
                "id": "safe-recovery-task",
                "type": "student_task",
                "sequence_index": 1,
                "text": "Write one equation step you would like checked.",
                "requires_student_response": True,
                "task_type": "equation_transformation",
            },
        ],
        "allowed_student_actions": ["submit_step", "request_hint"],
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
            "explain_differently": "reteach",
        },
    }
