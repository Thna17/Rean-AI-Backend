"""Build a renderer-safe teaching plan from a validated tutor turn.

The language model may propose a teaching plan, but this module is the final
authority.  It keeps the plan aligned with deterministic verification and the
server's answer-reveal policy before the plan is persisted or returned.
"""
from __future__ import annotations

from typing import Any

from api.models.visual_tutor import VisualTutorTurnRequest, VisualTutorTurnResponse
from api.services.visual_tutor.teaching_plan_contract import (
    HiddenAnswerMode,
    TeachingPlanActionType,
    TeachingPlanNextState,
    TeachingRepresentation,
    VisualTutorTeachingPlan,
    validate_teaching_plan,
)


_DIRECT_ACTION_MAP = {
    "write_text": TeachingPlanActionType.WRITE_TEXT,
    "write_equation": TeachingPlanActionType.WRITE_EQUATION,
    "transform_equation": TeachingPlanActionType.TRANSFORM_EQUATION,
    "highlight": TeachingPlanActionType.HIGHLIGHT,
    "cross_out": TeachingPlanActionType.CROSS_OUT,
    "fade_previous": TeachingPlanActionType.FADE_PREVIOUS,
    "draw_rectangle": TeachingPlanActionType.DRAW_RECTANGLE,
    "circle": TeachingPlanActionType.CIRCLE,
    "draw_arrow": TeachingPlanActionType.DRAW_ARROW,
    "draw_point": TeachingPlanActionType.DRAW_POINT,
    "show_hint": TeachingPlanActionType.SHOW_HINT,
    "show_feedback": TeachingPlanActionType.SHOW_FEEDBACK,
    "show_number_line": TeachingPlanActionType.SHOW_NUMBER_LINE,
    "draw_axes": TeachingPlanActionType.DRAW_AXES,
    "draw_axes": TeachingPlanActionType.DRAW_AXES,
    "show_graph": TeachingPlanActionType.SHOW_GRAPH,
    "plot_function": TeachingPlanActionType.PLOT_FUNCTION,
    "graph_annotation": TeachingPlanActionType.GRAPH_ANNOTATION,
    "show_table": TeachingPlanActionType.SHOW_TABLE,
}


def attach_validated_teaching_plan(
    *,
    response: VisualTutorTurnResponse,
    request: VisualTutorTurnRequest,
    policy: Any = None,
    understanding: Any = None,
    adaptive_decision: Any = None,
) -> VisualTutorTurnResponse:
    """Attach ``metadata.teaching_plan`` and its audit rationale to a turn."""
    plan, source, rationale = _select_plan(
        response=response,
        request=request,
        policy=policy,
        understanding=understanding,
        adaptive_decision=adaptive_decision,
    )
    return response.model_copy(
        update={
            "metadata": {
                **response.metadata,
                "teaching_plan": plan.model_dump(mode="json"),
                "teaching_plan_source": source,
                "teaching_plan_rationale": rationale,
                "learner_model_summary": _learner_model_summary(
                    adaptive_decision=adaptive_decision,
                    understanding=understanding,
                ),
            }
        }
    )


def _learner_model_summary(*, adaptive_decision: Any, understanding: Any) -> dict[str, str]:
    """Student-safe explanation of a decision, without learner evidence."""
    metadata = getattr(adaptive_decision, "metadata", {}) or {}
    metadata = metadata if isinstance(metadata, dict) else {}
    selected_concept = str(
        metadata.get("selected_concept")
        or getattr(understanding, "problem_type", None)
        or "current_skill"
    )[:120]
    wrong = int(metadata.get("wrong_attempts") or 0)
    hints = int(metadata.get("hint_count") or 0)
    readiness = str(metadata.get("learner_level") or "guided")
    evidence_category = (
        "repeated_misconception" if wrong >= 2
        else "needs_scaffold" if hints > 0 or readiness == "beginner"
        else "mastery_evidence" if readiness == "confident"
        else "recent_attempt"
    )
    move = getattr(getattr(adaptive_decision, "tutor_move", None), "value", "teach")
    confidence_band = (
        "confident" if readiness == "confident"
        else "emerging" if readiness == "beginner"
        else "developing"
    )
    return {
        "selected_concept": selected_concept,
        "evidence_category": evidence_category,
        "next_step_reason": str(move)[:120],
        "confidence_band": confidence_band,
    }


def _select_plan(*, response, request, policy, understanding, adaptive_decision):
    proposed = response.metadata.get("teaching_plan")
    if (
        isinstance(proposed, dict)
        and isinstance(response.metadata.get("worked_solution"), dict)
        and not response.final_answer_locked
    ):
        # A server-built, sympy-verified worked solution is meant to show every
        # step at once. _with_task_contract would run it through
        # _to_teaching_timeline, which keeps a single visual per turn and would
        # reduce the whole solution to one line. Keyed on server metadata, not
        # the plan's representation, so model output can never opt out of that
        # pacing.
        plan = validate_teaching_plan(
            {**proposed, "board_actions": _with_semantic_layout(proposed.get("board_actions", []))}
        )
        return plan, "worked_solution", _rationale(
            request, understanding, adaptive_decision, "worked_solution"
        )
    if isinstance(proposed, dict):
        try:
            plan = validate_teaching_plan(
                _with_task_contract(proposed, response=response, request=request, policy=policy)
            )
            if _plan_matches_server_policy(plan, response):
                source = (
                    "local_curriculum_demo"
                    if response.metadata.get("local_curriculum_demo") is True
                    else "llm_validated"
                )
                return plan, source, _rationale(
                    request, understanding, adaptive_decision, source
                )
        except Exception:
            pass
    try:
        plan = _deterministic_plan(
            response=response,
            request=request,
            policy=policy,
            understanding=understanding,
            adaptive_decision=adaptive_decision,
        )
    except Exception:
        # Reconciling the response's own board_actions/canvas_actions can
        # still fail (e.g. a show_table-shaped legacy action that doesn't
        # carry real table data through this stricter contract) -- a student
        # must always get their turn back, never a 500, so fall back to the
        # smallest plan this contract can always validate.
        plan = _minimal_safe_plan(
            response=response, request=request, policy=policy
        )
    return (
        plan,
        "server_reconciled",
        _rationale(request, understanding, adaptive_decision, "server_reconciled"),
    )


def _minimal_safe_plan(*, response, request, policy) -> VisualTutorTeachingPlan:
    """The smallest teaching_plan this contract can always validate: the
    turn's own speech and student task, no reconstructed board actions."""
    reveal_allowed = not response.final_answer_locked
    mode = HiddenAnswerMode.REVEAL_ALLOWED if reveal_allowed else HiddenAnswerMode.HIDDEN
    payload = {
        "schema_version": 1,
        "representation": TeachingRepresentation.CONCEPTUAL_EXPLANATION.value,
        "learning_objective": response.display_text[:500] or "Continue the current step.",
        "teaching_message": response.display_text,
        "board_actions": [
            {
                "id": "safe-fallback-text",
                "type": TeachingPlanActionType.WRITE_TEXT.value,
                "sequence_index": 0,
                "layout_zone": "problem",
                "layout_flow": "vertical",
                "text": response.display_text,
            },
            {
                "id": "safe-fallback-task",
                "type": TeachingPlanActionType.STUDENT_TASK.value,
                "sequence_index": 1,
                "layout_zone": "student_task",
                "layout_flow": "vertical",
                "text": response.student_task,
                "requires_student_response": True,
                **_task_contract(response=response, request=request, policy=policy),
            },
        ],
        "allowed_student_actions": [action.value for action in response.quick_actions]
        or ["submit_answer", "request_hint"],
        "hidden_answer_policy": {
            "mode": mode.value,
            "deterministic_policy_permits_final_reveal": reveal_allowed,
        },
        "next_state_policy": _next_state_policy(response),
    }
    return validate_teaching_plan(payload)


def _with_task_contract(plan: dict[str, Any], *, response, request, policy) -> dict[str, Any]:
    """Backfill task semantics for older planner output before strict validation."""
    copied = dict(plan)
    actions = []
    task_contract = _task_contract(response=response, request=request, policy=policy)
    # A locked final answer has already passed through response_sanitizer. Do
    # not accept a second model-controlled action list at this boundary: an
    # ordinary write_equation could otherwise carry a hidden solution without
    # using final_answer_reveal. Once unlocked, the strict plan remains useful
    # for richer, declarative visuals.
    source_actions = (
        _safe_actions_from_response(response)
        if response.final_answer_locked
        else plan.get("board_actions", [])
    )
    for raw_action in source_actions:
        if not isinstance(raw_action, dict):
            actions.append(raw_action)
            continue
        action = dict(raw_action)
        if action.get("type") == TeachingPlanActionType.STUDENT_TASK.value:
            for key, value in task_contract.items():
                action.setdefault(key, value)
        actions.append(action)
    if not any(
        isinstance(action, dict)
        and action.get("type") == TeachingPlanActionType.STUDENT_TASK.value
        for action in actions
    ):
        actions.append(
            {
                "id": f"teaching-plan-task-{response.turn_id}",
                "type": TeachingPlanActionType.STUDENT_TASK.value,
                "layout_zone": "student_task",
                "layout_flow": "vertical",
                "text": response.student_task,
                "requires_student_response": True,
                **task_contract,
            }
        )
    copied["board_actions"] = _with_semantic_layout(
        _to_teaching_timeline(actions, response=response)
    )
    return copied


def _plan_matches_server_policy(plan: VisualTutorTeachingPlan, response) -> bool:
    reveal_allowed = not response.final_answer_locked
    if plan.hidden_answer_policy.deterministic_policy_permits_final_reveal != reveal_allowed:
        return False
    if plan.hidden_answer_policy.mode != (
        HiddenAnswerMode.REVEAL_ALLOWED if reveal_allowed else HiddenAnswerMode.HIDDEN
    ):
        return False
    if response.final_answer_locked and any(
        action.type == TeachingPlanActionType.FINAL_ANSWER_REVEAL
        for action in plan.board_actions
    ):
        return False
    return True


def _deterministic_plan(*, response, request, policy, understanding, adaptive_decision):
    representation = _representation(response, adaptive_decision)
    actions = _with_semantic_layout(
        _to_teaching_timeline(_safe_actions_from_response(response), response=response)
    )
    task = {
        "id": f"teaching-plan-task-{response.turn_id}",
        "type": TeachingPlanActionType.STUDENT_TASK.value,
        "sequence_index": len(actions),
        "layout_zone": "student_task",
        "layout_flow": "vertical",
        "text": response.student_task,
        "requires_student_response": True,
        **_task_contract(response=response, request=request, policy=policy),
    }
    actions.append(task)
    reveal_allowed = not response.final_answer_locked
    mode = HiddenAnswerMode.REVEAL_ALLOWED if reveal_allowed else HiddenAnswerMode.HIDDEN
    payload = {
        "schema_version": 1,
        "representation": representation.value,
        "learning_objective": _learning_objective(response, understanding),
        "teaching_message": response.display_text,
        "board_actions": actions,
        "allowed_student_actions": [action.value for action in response.quick_actions]
        or ["submit_answer", "request_hint"],
        "hidden_answer_policy": {
            "mode": mode.value,
            "deterministic_policy_permits_final_reveal": reveal_allowed,
        },
        "next_state_policy": _next_state_policy(response),
    }
    return validate_teaching_plan(payload)


def _task_contract(*, response, request, policy) -> dict[str, Any]:
    """Describe the answer form before asking the learner to respond."""
    policy_metadata = getattr(policy, "metadata", {}) if policy is not None else {}
    policy_metadata = policy_metadata if isinstance(policy_metadata, dict) else {}
    solver_facts = response.metadata.get("solver_facts")
    solver_facts = solver_facts if isinstance(solver_facts, dict) else {}
    expected_operation = (
        policy_metadata.get("expected_operation")
        or response.metadata.get("expected_operation")
        or solver_facts.get("expected_operation")
    )
    expected_step = (
        policy_metadata.get("expected_step")
        or response.metadata.get("expected_step")
        or solver_facts.get("expected_step")
    )
    task_text = response.student_task.lower()
    asks_operation = bool(expected_operation) and any(
        phrase in task_text
        for phrase in ("operation", "first move", "what first", "which move", "cancels")
    )
    if asks_operation:
        return {
            "task_type": "conceptual_operation",
            "accepted_answer_forms": ["operation words", "short explanation"],
            "expected_operation": str(expected_operation),
            "explanation_required": False,
        }
    return {
        "task_type": "equation_transformation",
        "accepted_answer_forms": ["equation"],
        "expected_step": str(expected_step or "write one valid next equation step"),
        "explanation_required": False,
    }


def _safe_actions_from_response(response) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for action in response.board_actions:
        action_type = _DIRECT_ACTION_MAP.get(action.type.value)
        if (
            action.type.value == "reveal_answer"
            and not response.final_answer_locked
        ):
            action_type = TeachingPlanActionType.FINAL_ANSWER_REVEAL
        if action_type is None:
            continue
        if action_type in {TeachingPlanActionType.SHOW_GRAPH, TeachingPlanActionType.PLOT_FUNCTION} and action.graph is None:
            continue
        if action_type == TeachingPlanActionType.FINAL_ANSWER_REVEAL and not (
            (action.text or "").strip() or (action.latex or "").strip()
        ):
            continue
        item: dict[str, Any] = {
            "id": f"plan-{action.id}",
            "type": action_type.value,
            "sequence_index": len(result),
        }
        for name in ("text", "latex", "target_id", "duration_ms", "points", "label"):
            value = getattr(action, name, None)
            if value is not None:
                item[name] = value
        # number_line and table are Pydantic models on the legacy action (like
        # graph below), not plain dicts -- must be serialized or
        # TeachingPlanTable/TeachingPlanNumberLine validation rejects them.
        if action.number_line is not None:
            item["number_line"] = action.number_line.model_dump(mode="json")
        if action.table is not None:
            item["table"] = action.table.model_dump(mode="json")
        if action.graph is not None:
            graph = action.graph.model_dump(mode="json")
            # Preserve only the declarative point/annotation fields Flutter's
            # native painters understand; no style, URL, or widget metadata.
            item["graph"] = {
                "x_min": graph["x_min"],
                "x_max": graph["x_max"],
                "y_min": graph["y_min"],
                "y_max": graph["y_max"],
                "function_expression": graph.get("function_expression"),
                "domain": graph.get("domain"),
                "points": [
                    {
                        key: point[key] for key in ("x", "y", "label")
                        if key in point
                    }
                    for point in graph.get("points", [])
                    if isinstance(point, dict) and "x" in point and "y" in point
                ],
                "labels": [
                    str(graph.get("x_label") or "x"),
                    str(graph.get("y_label") or "y"),
                ],
                "annotations": [
                    {key: annotation[key] for key in ("text", "x", "y") if key in annotation}
                    for annotation in graph.get("annotations", [])
                    if isinstance(annotation, dict) and {"text", "x", "y"}.issubset(annotation)
                ],
            }
        try:
            # Validate each action independently by validating a tiny plan later.
            result.append(item)
        except Exception:
            continue
        if len(result) >= 23:
            break
    if not result:
        result.append(
            {
                "id": f"plan-message-{response.turn_id}",
                "type": TeachingPlanActionType.WRITE_TEXT.value,
                "sequence_index": 0,
                "x": 48,
                "y": 48,
                "text": response.display_text,
            }
        )
    return result


def _with_semantic_layout(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Make new public plans Flutter-owned layouts while retaining old plans."""
    visual_types = {
        "show_graph", "plot_function", "show_table", "show_number_line",
        "draw_axes", "draw_rectangle", "circle", "draw_arrow", "draw_point",
    }
    feedback_types = {"show_feedback", "show_hint"}
    normalized: list[dict[str, Any]] = []
    for action in actions:
        item = dict(action)
        action_type = str(item.get("type") or "")
        zone = (
            "student_task" if action_type == "student_task"
            else "feedback" if action_type in feedback_types
            else "visual" if action_type in visual_types
            else "working"
        )
        item.setdefault("layout_zone", zone)
        item.setdefault(
            "layout_flow",
            "diagram" if zone == "visual" else "vertical",
        )
        # The Flutter layout engine owns physical geometry for fresh plans.
        # Keep declarative graph/point data but remove device-specific boxes.
        for key in ("x", "y", "width", "height"):
            item.pop(key, None)
        normalized.append(item)
    return normalized


def _to_teaching_timeline(
    actions: list[dict[str, Any]], *, response: VisualTutorTurnResponse
) -> list[dict[str, Any]]:
    """Normalize one lesson turn to a calm spoken visual idea and think pause."""
    visual_types = {
        TeachingPlanActionType.WRITE_TEXT.value, TeachingPlanActionType.WRITE_EQUATION.value,
        TeachingPlanActionType.TRANSFORM_EQUATION.value, TeachingPlanActionType.DRAW_RECTANGLE.value,
        TeachingPlanActionType.CIRCLE.value, TeachingPlanActionType.DRAW_ARROW.value,
        TeachingPlanActionType.DRAW_POINT.value, TeachingPlanActionType.SHOW_NUMBER_LINE.value,
        TeachingPlanActionType.DRAW_AXES.value, TeachingPlanActionType.SHOW_GRAPH.value, TeachingPlanActionType.PLOT_FUNCTION.value,
        TeachingPlanActionType.SHOW_TABLE.value, TeachingPlanActionType.GRAPH_ANNOTATION.value,
        TeachingPlanActionType.FINAL_ANSWER_REVEAL.value,
    }
    candidates = [action for action in actions if action.get("type") in visual_types]
    priority = {
        TeachingPlanActionType.SHOW_GRAPH.value: 0,
        TeachingPlanActionType.PLOT_FUNCTION.value: 0,
        TeachingPlanActionType.SHOW_NUMBER_LINE.value: 1,
        TeachingPlanActionType.TRANSFORM_EQUATION.value: 2,
        TeachingPlanActionType.WRITE_EQUATION.value: 3,
        TeachingPlanActionType.SHOW_TABLE.value: 4,
    }
    primary = min(candidates, key=lambda action: priority.get(str(action.get("type")), 10), default=None)
    if primary is None:
        primary = {
            "id": f"plan-message-{response.turn_id}",
            "type": TeachingPlanActionType.WRITE_TEXT.value,
            "x": 48, "y": 48, "text": response.display_text,
        }
    primary = dict(primary)
    if primary.get("type") == TeachingPlanActionType.FINAL_ANSWER_REVEAL.value:
        # Even an explicit answer request is paced: reveal one meaningful
        # line, then let the learner ask/confirm before the following line.
        _trim_progressive_answer_piece(primary)
    primary["id"] = str(primary.get("id") or f"plan-visual-{response.turn_id}")
    primary["sequence_index"] = 1
    primary["duration_ms"] = _drawing_duration(primary)
    timeline: list[dict[str, Any]] = [
        {"id": f"plan-speak-{response.turn_id}", "type": TeachingPlanActionType.SPEAK_MARKER.value,
         "sequence_index": 0, "duration_ms": 0},
        primary,
    ]
    # One focused overlay is enough. Older board work may be faded, but never
    # highlighted alongside a different new step.
    fade = next(
        (dict(action) for action in actions
         if action.get("type") == TeachingPlanActionType.FADE_PREVIOUS.value),
        None,
    )
    highlight = next(
        (dict(action) for action in actions
         if action.get("type") == TeachingPlanActionType.HIGHLIGHT.value),
        None,
    )
    # A highlight is meaningful only when it follows the single current visual.
    # Rewrite its target rather than trusting an LLM-provided old action ID.
    if fade is not None:
        fade["sequence_index"] = len(timeline)
        fade["duration_ms"] = min(450, max(150, int(fade.get("duration_ms") or 250)))
        timeline.append(fade)
    if highlight is not None:
        highlight["target_id"] = primary["id"]
        highlight["sequence_index"] = len(timeline)
        highlight["duration_ms"] = min(450, max(150, int(highlight.get("duration_ms") or 250)))
        timeline.append(highlight)
    timeline.append({"id": f"plan-pause-{response.turn_id}", "type": TeachingPlanActionType.PAUSE_MARKER.value,
                     "sequence_index": len(timeline), "duration_ms": 650})
    task = next((dict(action) for action in actions if action.get("type") == TeachingPlanActionType.STUDENT_TASK.value), None)
    if task is not None:
        task["sequence_index"] = len(timeline)
        timeline.append(task)
    return timeline


def _drawing_duration(action: dict[str, Any]) -> int:
    action_type = str(action.get("type") or "")
    if action_type in {TeachingPlanActionType.SHOW_GRAPH.value, TeachingPlanActionType.PLOT_FUNCTION.value}:
        return 900
    if action_type in {TeachingPlanActionType.SHOW_NUMBER_LINE.value, TeachingPlanActionType.SHOW_TABLE.value}:
        return 700
    if action_type in {TeachingPlanActionType.DRAW_ARROW.value, TeachingPlanActionType.DRAW_RECTANGLE.value, TeachingPlanActionType.CIRCLE.value}:
        return 480
    return 420


def _trim_progressive_answer_piece(action: dict[str, Any]) -> None:
    for field in ("text", "latex"):
        value = action.get(field)
        if not isinstance(value, str):
            continue
        compact = value.strip()
        if not compact:
            continue
        pieces = [piece.strip() for piece in compact.splitlines() if piece.strip()]
        first = pieces[0] if pieces else compact
        if len(first) > 180:
            first = first[:177].rstrip() + "…"
        action[field] = first
        break


def _representation(response, adaptive_decision) -> TeachingRepresentation:
    raw = None
    if adaptive_decision is not None:
        metadata = getattr(adaptive_decision, "metadata", {}) or {}
        raw = metadata.get("representation")
    raw = raw or response.metadata.get("representation")
    action_types = {action.type.value for action in response.board_actions}
    if {"show_graph", "plot_function", "draw_axes"} & action_types:
        return TeachingRepresentation.COORDINATE_GRAPH
    if "show_number_line" in action_types:
        return TeachingRepresentation.NUMBER_LINE
    if response.metadata.get("verification_result") in {"invalid", "incomplete"}:
        return TeachingRepresentation.ERROR_ANALYSIS
    if response.metadata.get("student_intent") == "stuck":
        return TeachingRepresentation.WORKED_EXAMPLE
    if raw:
        try:
            return TeachingRepresentation(raw)
        except ValueError:
            pass
    if "transform_equation" in action_types:
        return TeachingRepresentation.EQUATION_TRANSFORMATION
    return TeachingRepresentation.CONCEPTUAL_EXPLANATION


def _learning_objective(response, understanding) -> str:
    objective = response.metadata.get("learning_objective")
    if isinstance(objective, str) and objective.strip():
        return objective
    problem_type = getattr(understanding, "problem_type", None)
    if problem_type:
        return f"Make one verified step in this {str(problem_type).replace('_', ' ')} problem."
    return "Make one meaningful, checkable step before continuing."


def _next_state_policy(response) -> dict[str, str]:
    problem_understanding = response.metadata.get("problem_understanding")
    problem_type = (
        problem_understanding.get("problem_type")
        if isinstance(problem_understanding, dict)
        else None
    )
    if problem_type == "unsupported":
        default = TeachingPlanNextState.UNSUPPORTED_RECOVERY.value
    else:
        default = TeachingPlanNextState.ASK_FOR_WORK.value
    return {
        "correct": TeachingPlanNextState.CONTINUE.value,
        "invalid": TeachingPlanNextState.RETEACH.value,
        "incomplete": TeachingPlanNextState.ASK_FOR_WORK.value,
        "stuck": TeachingPlanNextState.RETEACH.value,
        "hint": TeachingPlanNextState.CONTINUE.value,
        "explain_differently": default,
    }


def _rationale(request, understanding, adaptive_decision, source: str) -> dict[str, Any]:
    metadata = getattr(adaptive_decision, "metadata", {}) or {}
    return {
        "source": source,
        "confirmed_problem": bool(request.current_state.problem_text or request.message),
        "grade": request.metadata.get("grade") or request.metadata.get("grade_level"),
        "topic": request.topic,
        "language": request.locale or request.metadata.get("preferred_language"),
        "problem_type": getattr(understanding, "problem_type", None),
        "tutor_move": getattr(getattr(adaptive_decision, "tutor_move", None), "value", None),
        "representation_reason": metadata.get("representation_reason") or metadata.get("reason"),
        "hint_count": request.hint_count if request.hint_count is not None else request.current_state.hint_count,
        "wrong_attempts": request.current_state.wrong_attempts,
        "stuck_count": request.metadata.get("stuck_count", 0),
        "uses_solver_facts": bool(metadata.get("solver_facts") or request.metadata.get("solver_facts")),
        "uses_curriculum_context": bool(metadata.get("curriculum_context")),
        "strategy_history_count": len(request.metadata.get("strategy_history") or []),
    }
