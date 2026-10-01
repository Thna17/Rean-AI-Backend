from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from api.models.visual_tutor import (
    CanvasElementStyle,
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoardAction,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorLessonState,
    VisualTutorNextStudentAction,
    VisualTutorSpeech,
    VisualTutorStageState,
    VisualTutorTeachingMode,
    VisualTutorTeachingStage,
    VisualTutorTtsStatus,
    VisualTutorBehavior,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
    VisualTutorVisualFocus,
)
from api.services.visual_tutor.policy import VisualTutorPolicyDecision

LIVE_STAGE_POLICY_VERSION = "visual_tutor_live_stage_policy_v1"
MAX_VISIBLE_INSTRUCTIONAL_ACTIONS = 3
_ANSWER_ASSIGNMENT_RE = re.compile(
    r"\b[a-zA-Z]\s*=\s*[-+]?\d+(?:\.\d+)?(?:/\d+)?"
    r"(?:\s*[-+*/]\s*[a-zA-Z0-9().]+)*\b"
)


@dataclass(frozen=True)
class LiveTeachingStagePolicyDecision:
    stage_state: VisualTutorStageState
    lesson_state: VisualTutorLessonState
    should_speak: bool = True
    should_draw: bool = True
    should_ask: bool = True
    should_wait: bool = True
    should_evaluate: bool = False
    should_reteach: bool = False
    max_visual_action_groups: int = 1
    interaction_input_enabled: bool = True
    allowed_actions: list[VisualTutorAllowedAction] = field(default_factory=list)
    full_solution_allowed: bool = False
    final_answer_locked: bool = True
    use_khmer_teaching: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


def decide_live_teaching_stage_policy(
    request: VisualTutorTurnRequest,
    policy: VisualTutorPolicyDecision,
    *,
    input_understanding: Optional[VisualTutorInputUnderstandingResult] = None,
) -> LiveTeachingStagePolicyDecision:
    """Translate tutor policy into the live-stage state machine contract."""

    lesson_state = _lesson_state_for_policy(request, policy)
    should_evaluate = policy.should_check_step or policy.possible_final_answer
    should_reteach = (
        policy.diagnose_misconception
        or policy.should_redirect_input
        or policy.teaching_mode == VisualTutorTeachingMode.MISCONCEPTION_FIX
    )
    full_solution_allowed = policy.full_solution_allowed and policy.reveal_final
    final_answer_locked = policy.final_answer_locked or not full_solution_allowed

    should_speak = True
    should_draw = True
    should_ask = policy.should_ask_question or not full_solution_allowed
    should_wait = not full_solution_allowed
    max_visual_action_groups = _max_visual_action_groups(policy)
    interaction_input_enabled = (
        not full_solution_allowed or lesson_state == VisualTutorLessonState.VERIFY
    )
    allowed_actions = _allowed_actions(policy)

    return LiveTeachingStagePolicyDecision(
        stage_state=_stage_state_for_policy(policy, lesson_state),
        lesson_state=lesson_state,
        should_speak=should_speak,
        should_draw=should_draw,
        should_ask=should_ask,
        should_wait=should_wait,
        should_evaluate=should_evaluate,
        should_reteach=should_reteach,
        max_visual_action_groups=max_visual_action_groups,
        interaction_input_enabled=interaction_input_enabled,
        allowed_actions=allowed_actions,
        full_solution_allowed=full_solution_allowed,
        final_answer_locked=final_answer_locked,
        use_khmer_teaching=policy.use_khmer_explanation,
        metadata={
            "policy": LIVE_STAGE_POLICY_VERSION,
            "source_policy_reason": policy.reason,
            "teaching_mode": policy.teaching_mode.value,
            "student_intent": policy.metadata.get("student_intent"),
            "input_relevance": (
                input_understanding.input_relevance.value
                if input_understanding
                else (
                    policy.input_relevance.value
                    if policy.input_relevance is not None
                    else None
                )
            ),
            "one_turn_rule": "one_short_speech_one_visual_idea_one_student_task",
            "should_speak": should_speak,
            "should_draw": should_draw,
            "should_ask": should_ask,
            "should_wait": should_wait,
            "should_evaluate": should_evaluate,
            "should_reteach": should_reteach,
            "max_visual_action_groups": max_visual_action_groups,
            "interaction_input_enabled": interaction_input_enabled,
            "allowed_actions": [action.value for action in allowed_actions],
            "final_answer_locked": final_answer_locked,
            "full_solution_allowed": full_solution_allowed,
            "use_khmer_teaching": policy.use_khmer_explanation,
        },
    )


def apply_live_teaching_stage_policy(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    policy: VisualTutorPolicyDecision,
    *,
    input_understanding: Optional[VisualTutorInputUnderstandingResult] = None,
) -> VisualTutorTurnResponse:
    decision = decide_live_teaching_stage_policy(
        request,
        policy,
        input_understanding=input_understanding,
    )
    has_explicit_board_actions = bool(response.board_actions)
    board_actions = response.board_actions or normalize_live_board_actions(
        response.canvas_actions,
        decision=decision,
    )
    board_actions = _ensure_active_board_actions(
        response,
        board_actions,
        decision=decision,
    )
    # Explicit planner actions are not trusted to obey the turn budget. Apply
    # the same cap to every normal response, including solver/LLM output.
    board_actions = _limit_board_action_groups(board_actions, decision=decision)
    board_actions = _enforce_single_teaching_moment(board_actions)
    interaction = response.interaction or _interaction_for_response(response, decision)
    waiting_for_student = decision.should_wait or interaction.input_enabled
    concise_spoken_text = _concise_spoken_explanation(response.spoken_text)
    speech = VisualTutorSpeech(
        text=concise_spoken_text,
        language="km" if decision.use_khmer_teaching else "en",
        tts_status=VisualTutorTtsStatus.NOT_REQUESTED,
        speak_after_action_id=board_actions[0].id if board_actions else None,
        pause_after_ms=500 if decision.should_wait else 0,
    )
    teaching_stage = VisualTutorTeachingStage(
        stage_state=decision.stage_state,
        lesson_state=decision.lesson_state,
        current_focus=_current_focus(response, input_understanding),
        turn_goal=_turn_goal(response, decision),
        max_actions_before_wait=decision.max_visual_action_groups,
        metadata=decision.metadata,
    )
    metadata = {
        **response.metadata,
        "live_teaching_stage": decision.metadata,
        "interactive_teaching_moment": {
            "objective_count": 1,
            "learning_objective_count": 1,
            "visible_instructional_actions": _visible_instructional_action_count(
                board_actions
            ),
            "student_task_count": 1 if (interaction.prompt or "").strip() else 0,
            "waiting_for_student_input": waiting_for_student,
            "spoken_explanation_concise": concise_spoken_text != response.spoken_text,
            "progressive_reveal": bool(policy.reveal_final),
            "revealed_step_count": 1 if policy.reveal_final else 0,
        },
        # Public, explicit state for clients that should display a waiting UI
        # without interpreting internal stage-policy fields.
        "waiting_for_student_input": waiting_for_student,
    }
    visual_focus = _visual_focus_for(
        response,
        board_actions=board_actions,
        input_understanding=input_understanding,
    )
    next_student_action = _next_student_action_for(
        interaction,
        decision=decision,
    )
    tutor_behavior = _tutor_behavior_for(decision)
    return response.model_copy(
        update={
            "speech": speech,
            "teaching_stage": teaching_stage,
            "board_actions": board_actions,
            "spoken_text": concise_spoken_text,
            "interaction": interaction,
            "allowed_actions": response.allowed_actions or decision.allowed_actions,
            "visual_focus": visual_focus,
            "next_student_action": next_student_action,
            "tutor_behavior": tutor_behavior,
            "final_answer_locked": decision.final_answer_locked,
            "metadata": metadata,
        }
    )


def _enforce_single_teaching_moment(
    board_actions: list[VisualTutorBoardAction],
) -> list[VisualTutorBoardAction]:
    """Keep one board moment: up to three teaching visuals and one task.

    Markers and focus/fade modifiers are retained only when attached to an
    accepted visual. They do not become a route for an LLM to display later
    solution steps in the same turn.
    """
    markers = {
        VisualTutorCanvasActionType.SPEAK_MARKER,
        VisualTutorCanvasActionType.PAUSE_MARKER,
    }
    modifiers = {
        VisualTutorCanvasActionType.HIGHLIGHT,
        VisualTutorCanvasActionType.FOCUS,
        VisualTutorCanvasActionType.FADE_PREVIOUS,
    }
    ordered = sorted(board_actions, key=lambda action: (action.sequence_index, action.id))
    accepted: list[VisualTutorBoardAction] = []
    accepted_ids: set[str] = set()
    accepted_groups: set[str] = set()
    instructional_count = 0
    task_seen = False
    for action in ordered:
        if action.type in markers:
            # Markers control playback only and are not learner-visible.
            accepted.append(action)
            continue
        if action.type == VisualTutorCanvasActionType.STUDENT_TASK:
            if task_seen:
                continue
            task_seen = True
            accepted.append(action.model_copy(update={"requires_student_response": True}))
            accepted_ids.add(action.id)
            if action.group_id:
                accepted_groups.add(action.group_id)
            continue
        if action.type in modifiers:
            if (
                action.target_id is None
                or action.target_id in accepted_ids
                or (action.group_id and action.group_id in accepted_groups)
                or (bool(accepted_ids) and action.x is not None and action.y is not None)
            ):
                accepted.append(action)
            continue
        if instructional_count >= MAX_VISIBLE_INSTRUCTIONAL_ACTIONS:
            continue
        accepted.append(action)
        accepted_ids.add(action.id)
        if action.group_id:
            accepted_groups.add(action.group_id)
        instructional_count += 1
    return [
        action.model_copy(update={"sequence_index": index})
        for index, action in enumerate(accepted)
    ]


def _visible_instructional_action_count(
    board_actions: list[VisualTutorBoardAction],
) -> int:
    ignored = {
        VisualTutorCanvasActionType.SPEAK_MARKER,
        VisualTutorCanvasActionType.PAUSE_MARKER,
        VisualTutorCanvasActionType.HIGHLIGHT,
        VisualTutorCanvasActionType.FOCUS,
        VisualTutorCanvasActionType.FADE_PREVIOUS,
        VisualTutorCanvasActionType.STUDENT_TASK,
    }
    return sum(action.type not in ignored for action in board_actions)


def _concise_spoken_explanation(text: str) -> str:
    """Limit ordinary turn speech to one calm, short teaching explanation."""
    normalized = " ".join((text or "").split())
    if len(normalized) <= 280:
        return normalized
    # Preserve at most two natural clauses rather than returning a raw hard
    # cutoff whenever the model gave us punctuation.
    sentences = re.split(r"(?<=[.!?។])\s+", normalized)
    concise = " ".join(sentences[:2]).strip()
    if concise and len(concise) <= 280:
        return concise
    return normalized[:277].rstrip() + "…"


def _ensure_active_board_actions(
    response: VisualTutorTurnResponse,
    board_actions: list[VisualTutorBoardAction],
    *,
    decision: LiveTeachingStagePolicyDecision,
) -> list[VisualTutorBoardAction]:
    if board_actions or not decision.should_draw:
        return board_actions
    text = response.display_text or response.student_task
    return [
        VisualTutorBoardAction(
            id=f"live-fallback-{response.turn_id}",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=0,
            duration_ms=450,
            wait_for_speech_marker=True,
            requires_student_response=decision.should_wait,
            group_id="fallback-teaching-move",
            section_id="main-board",
            x=40,
            y=64,
            width=640,
            height=56,
            text=text,
            metadata={
                "generated_by": LIVE_STAGE_POLICY_VERSION,
                "current_step": True,
                "fallback_live_action": True,
            },
        )
    ]


def _limit_board_action_groups(
    board_actions: list[VisualTutorBoardAction],
    *,
    decision: LiveTeachingStagePolicyDecision,
) -> list[VisualTutorBoardAction]:
    if not board_actions:
        return []
    marker_types = {
        VisualTutorCanvasActionType.SPEAK_MARKER,
        VisualTutorCanvasActionType.PAUSE_MARKER,
    }
    allowed_groups: list[str] = []
    allowed_action_ids: set[str] = set()
    for action in board_actions:
        if action.type in marker_types:
            continue
        if (
            action.type
            in {
                VisualTutorCanvasActionType.HIGHLIGHT,
                VisualTutorCanvasActionType.FOCUS,
            }
            and action.target_id in allowed_action_ids
        ):
            allowed_action_ids.add(action.id)
            continue
        group_id = action.group_id or f"action-{action.id}"
        if group_id not in allowed_groups:
            allowed_groups.append(group_id)
        allowed_action_ids.add(action.id)
        if len(allowed_groups) >= decision.max_visual_action_groups:
            break
    allowed = set(allowed_groups)
    return [
        action
        for action in board_actions
        if action.type in marker_types
        or action.id in allowed_action_ids
        or (action.group_id or f"action-{action.id}") in allowed
        or (
            action.type
            in {
                VisualTutorCanvasActionType.HIGHLIGHT,
                VisualTutorCanvasActionType.FOCUS,
            }
            and action.target_id in allowed_action_ids
        )
    ]


def normalize_live_board_actions(
    canvas_actions: list[VisualTutorCanvasAction],
    *,
    decision: LiveTeachingStagePolicyDecision,
) -> list[VisualTutorBoardAction]:
    """Convert compatibility canvas actions into the next live teaching action group."""

    visible_actions = [
        action
        for action in canvas_actions
        if action.type
        not in {
            VisualTutorCanvasActionType.SPEAK_MARKER,
            VisualTutorCanvasActionType.PAUSE_MARKER,
        }
    ]
    selected = _first_focused_action_group(
        visible_actions,
        max_groups=decision.max_visual_action_groups,
    )
    return [
        _to_live_board_action(
            action,
            sequence_index=index,
            decision=decision,
        )
        for index, action in enumerate(selected)
    ]


def _stage_state_for_policy(
    policy: VisualTutorPolicyDecision,
    lesson_state: VisualTutorLessonState,
) -> VisualTutorStageState:
    if policy.should_check_step or lesson_state == VisualTutorLessonState.EVALUATE:
        return VisualTutorStageState.EVALUATING
    if policy.diagnose_misconception or policy.explain_differently or policy.stuck_help:
        return VisualTutorStageState.ADAPTING
    if policy.reveal_partial or policy.give_hint or policy.should_ask_question:
        return VisualTutorStageState.WAITING_FOR_STUDENT
    if policy.reveal_final:
        return VisualTutorStageState.DRAWING
    return VisualTutorStageState.WAITING_FOR_STUDENT


def _lesson_state_for_policy(
    request: VisualTutorTurnRequest,
    policy: VisualTutorPolicyDecision,
) -> VisualTutorLessonState:
    if policy.teaching_mode == VisualTutorTeachingMode.GREETING:
        return VisualTutorLessonState.UNDERSTAND_REQUEST
    if policy.stuck_help:
        return VisualTutorLessonState.RETEACH_OR_CONTINUE
    if policy.should_redirect_input or policy.diagnose_misconception:
        return VisualTutorLessonState.RETEACH_OR_CONTINUE
    if policy.should_check_step or policy.possible_final_answer:
        return VisualTutorLessonState.EVALUATE
    if request.action == VisualTutorAction.REQUEST_FINAL_ANSWER:
        return (
            VisualTutorLessonState.VERIFY
            if policy.full_solution_allowed and policy.reveal_final
            else VisualTutorLessonState.ASK
        )
    if request.action == VisualTutorAction.REQUEST_HINT:
        return VisualTutorLessonState.INSTANT_HELP
    if policy.explain_differently:
        return VisualTutorLessonState.RETEACH_OR_CONTINUE
    if policy.teaching_mode in {
        VisualTutorTeachingMode.HINT,
        VisualTutorTeachingMode.PARTIAL_SOLUTION,
    }:
        return VisualTutorLessonState.TEACH
    return VisualTutorLessonState.ASK


def _max_visual_action_groups(policy: VisualTutorPolicyDecision) -> int:
    if policy.reveal_final:
        return 3
    if policy.reveal_partial:
        return 2
    return 1


def _allowed_actions(
    policy: VisualTutorPolicyDecision,
) -> list[VisualTutorAllowedAction]:
    actions = [
        VisualTutorAllowedAction.SUBMIT_ANSWER,
        VisualTutorAllowedAction.REQUEST_HINT,
        VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
        VisualTutorAllowedAction.SHOW_VISUALLY,
        VisualTutorAllowedAction.CHECK_WORK,
        VisualTutorAllowedAction.STUCK,
        VisualTutorAllowedAction.REQUEST_ANSWER,
    ]
    return actions


def _interaction_for_response(
    response: VisualTutorTurnResponse,
    decision: LiveTeachingStagePolicyDecision,
) -> VisualTutorInteraction:
    interaction_type = VisualTutorInteractionType.TEXT_RESPONSE
    if _expects_numeric(response.student_task):
        interaction_type = VisualTutorInteractionType.NUMERIC_INPUT
    elif decision.lesson_state == VisualTutorLessonState.VERIFY:
        interaction_type = VisualTutorInteractionType.YES_NO

    prompt = response.student_task
    if not decision.interaction_input_enabled and decision.final_answer_locked:
        prompt = (
            "The answer is locked for now. Try the next small step first."
            if not decision.use_khmer_teaching
            else "ចម្លើយចុងក្រោយនៅត្រូវបានចាក់សោ។ សាកល្បងជំហានតូចបន្ទាប់សិន។"
        )

    return VisualTutorInteraction(
        type=interaction_type,
        prompt=prompt,
        expected_answer_locked=decision.final_answer_locked,
        validation_strategy=_validation_strategy(interaction_type),
        input_enabled=decision.interaction_input_enabled,
        submit_label="ឆ្លើយ" if decision.use_khmer_teaching else "Submit",
    )


def _to_live_board_action(
    action: VisualTutorCanvasAction,
    *,
    sequence_index: int,
    decision: LiveTeachingStagePolicyDecision,
) -> VisualTutorBoardAction:
    locked = action.locked or (
        decision.final_answer_locked and _is_locked_or_final_action(action)
    )
    action_type = VisualTutorCanvasActionType.HIDE if locked else action.type
    text = action.text
    latex = action.latex
    metadata = {
        **action.metadata,
        "source_action_id": action.id,
        "live_stage_policy": LIVE_STAGE_POLICY_VERSION,
    }
    if locked:
        text = "Final answer is locked." if text else text
        latex = r"\text{Final answer is locked.}" if latex else latex
        metadata.update({"hidden": True, "final_answer_locked": True})
    return VisualTutorBoardAction(
        id=f"live-{action.id}",
        type=action_type,
        sequence_index=sequence_index,
        duration_ms=_duration_for_action(action.type),
        wait_for_speech_marker=sequence_index == 0,
        requires_student_response=sequence_index == 0 and decision.should_wait,
        group_id=_action_group_id(action),
        section_id=str(action.metadata.get("section_id") or "main-board"),
        x=action.x,
        y=action.y,
        width=action.width,
        height=action.height,
        text=text,
        latex=latex,
        points=action.points,
        target_id=action.target_id,
        style=action.style or CanvasElementStyle(),
        locked=locked,
        reveal_policy=action.reveal_policy,
        metadata=metadata,
    )


def _first_focused_action_group(
    actions: list[VisualTutorCanvasAction],
    *,
    max_groups: int,
) -> list[VisualTutorCanvasAction]:
    if not actions:
        return []

    current_group = [
        action for action in actions if action.metadata.get("current_step") is True
    ]
    if current_group:
        return _include_related_highlights(actions, current_group[: max(1, max_groups)])

    active = [
        action
        for action in actions
        if not action.locked
        and not action.metadata.get("future_step")
        and not action.metadata.get("is_final_answer")
    ]
    if not active:
        active = actions
    first = active[: max(1, max_groups)]
    return _include_related_highlights(actions, first)


def _include_related_highlights(
    actions: list[VisualTutorCanvasAction],
    selected: list[VisualTutorCanvasAction],
) -> list[VisualTutorCanvasAction]:
    selected_ids = {action.id for action in selected}
    output = list(selected)
    for action in actions:
        if (
            action.type == VisualTutorCanvasActionType.HIGHLIGHT
            and action.target_id in selected_ids
            and action.id not in selected_ids
        ):
            output.append(action)
            selected_ids.add(action.id)
    return output[:3]


def _is_locked_or_final_action(action: VisualTutorCanvasAction) -> bool:
    metadata = action.metadata
    if action.locked:
        return True
    if action.reveal_policy:
        return True
    if metadata.get("is_final_answer") is True or metadata.get("final_answer") is True:
        return True
    if metadata.get("future_step") is True:
        return True
    if _action_leaks_answer(action):
        return True
    return False


def _action_leaks_answer(action: VisualTutorCanvasAction) -> bool:
    return any(
        value and _ANSWER_ASSIGNMENT_RE.search(value)
        for value in (action.text, action.latex)
    )


def _action_group_id(action: VisualTutorCanvasAction) -> str:
    return str(
        action.metadata.get("group_id")
        or action.metadata.get("board_label")
        or action.target_id
        or "turn-focus"
    )


def _duration_for_action(action_type: VisualTutorCanvasActionType) -> int:
    if action_type in {
        VisualTutorCanvasActionType.WRITE_TEXT,
        VisualTutorCanvasActionType.WRITE_EQUATION,
    }:
        return 700
    if action_type in {
        VisualTutorCanvasActionType.DRAW_LINE,
        VisualTutorCanvasActionType.DRAW_ARROW,
        VisualTutorCanvasActionType.DRAW_POINT,
        VisualTutorCanvasActionType.DRAW_AXES,
    }:
        return 450
    if action_type == VisualTutorCanvasActionType.HIGHLIGHT:
        return 250
    return 300


def _current_focus(
    response: VisualTutorTurnResponse,
    input_understanding: Optional[VisualTutorInputUnderstandingResult],
) -> Optional[str]:
    if input_understanding:
        expected_step = input_understanding.metadata.get("expected_step")
        if expected_step:
            return str(expected_step)
    for action in response.canvas_actions:
        if action.metadata.get("current_step"):
            return action.id
    return response.board.title or response.board.type.value


def _visual_focus_for(
    response: VisualTutorTurnResponse,
    *,
    board_actions: list[VisualTutorBoardAction],
    input_understanding: Optional[VisualTutorInputUnderstandingResult],
) -> VisualTutorVisualFocus:
    focused_action = _focused_board_action(board_actions)
    expected_step = (
        input_understanding.metadata.get("expected_step")
        if input_understanding
        else None
    )
    return VisualTutorVisualFocus(
        element_id=focused_action.id if focused_action else None,
        group_id=focused_action.group_id if focused_action else None,
        section_id=focused_action.section_id if focused_action else "main-board",
        x=focused_action.x if focused_action else None,
        y=focused_action.y if focused_action else None,
        width=focused_action.width if focused_action else None,
        height=focused_action.height if focused_action else None,
        description=str(expected_step or response.student_task),
        reason=(
            "expected_step"
            if expected_step
            else (
                "current_board_action"
                if focused_action
                else "student_task"
            )
        ),
        metadata={
            "turn_id": response.turn_id,
            "teaching_mode": response.teaching_mode.value,
        },
    )


def _focused_board_action(
    board_actions: list[VisualTutorBoardAction],
) -> Optional[VisualTutorBoardAction]:
    for action in board_actions:
        if action.metadata.get("current_step") is True:
            return action
    for action in board_actions:
        if action.type not in {
            VisualTutorCanvasActionType.SPEAK_MARKER,
            VisualTutorCanvasActionType.PAUSE_MARKER,
            VisualTutorCanvasActionType.HIDE,
        }:
            return action
    return board_actions[0] if board_actions else None


def _next_student_action_for(
    interaction: VisualTutorInteraction,
    *,
    decision: LiveTeachingStagePolicyDecision,
) -> VisualTutorNextStudentAction:
    return VisualTutorNextStudentAction(
        type=interaction.type,
        prompt=interaction.prompt,
        input_enabled=interaction.input_enabled and decision.interaction_input_enabled,
        submit_label=interaction.submit_label,
        expected_answer_locked=interaction.expected_answer_locked,
        validation_strategy=interaction.validation_strategy,
        metadata={
            **interaction.metadata,
            "lesson_state": decision.lesson_state.value,
            "stage_state": decision.stage_state.value,
        },
    )


def _tutor_behavior_for(
    decision: LiveTeachingStagePolicyDecision,
) -> VisualTutorBehavior:
    if decision.full_solution_allowed:
        answer_reveal_strategy = "progressive_full_solution"
    elif decision.final_answer_locked:
        answer_reveal_strategy = "guided_learning_locked"
    else:
        answer_reveal_strategy = "answer_unlocked"
    return VisualTutorBehavior(
        should_speak=decision.should_speak,
        should_draw=decision.should_draw,
        should_ask=decision.should_ask,
        should_wait=decision.should_wait,
        should_evaluate=decision.should_evaluate,
        should_reteach=decision.should_reteach,
        explanation_language="km" if decision.use_khmer_teaching else "en",
        tone="khmer_friendly_teacher" if decision.use_khmer_teaching else "teacher",
        max_actions_before_wait=decision.max_visual_action_groups,
        answer_reveal_strategy=answer_reveal_strategy,
        metadata=decision.metadata,
    )


def _turn_goal(
    response: VisualTutorTurnResponse,
    decision: LiveTeachingStagePolicyDecision,
) -> str:
    if decision.should_reteach:
        return "Repair the first misunderstanding and ask for one small next action."
    if decision.should_evaluate:
        return "Evaluate the student's step and guide the next attempt."
    if decision.full_solution_allowed:
        return "Reveal the solution progressively, then verify understanding."
    if response.teaching_mode == VisualTutorTeachingMode.STUCK_HELP:
        return "Make the current step simpler without revealing the final answer."
    return "Give one focused visual update and ask the student to respond."


def _expects_numeric(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ["what is", "how much", "value", "number", "calculate", "find"]
    )


def _validation_strategy(interaction_type: VisualTutorInteractionType) -> str:
    if interaction_type == VisualTutorInteractionType.NUMERIC_INPUT:
        return "numeric_or_expression"
    if interaction_type == VisualTutorInteractionType.YES_NO:
        return "yes_no"
    return "student_input_understanding"
