from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from api.models.visual_tutor import (
    TeachingBoardState,
    VisualTutorAllowedAction,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorInteractionType,
    VisualTutorLessonState,
    VisualTutorProblemUnderstandingResult,
    VisualTutorScreenState,
    VisualTutorSolverFacts,
    VisualTutorStageState,
    VisualTutorStudentIntent,
)

ADAPTIVE_TUTOR_PLANNER_VERSION = "visual_tutor_adaptive_planner_v1"
PARTIAL_UNLOCK_HINT_THRESHOLD = 2
PARTIAL_UNLOCK_WRONG_THRESHOLD = 2
FULL_UNLOCK_HINT_THRESHOLD = 3
FULL_UNLOCK_WRONG_THRESHOLD = 2


class VisualTutorMove(str, Enum):
    TEACH_NEXT_VISUAL_STEP = "teach_next_visual_step"
    ASK_GUIDING_QUESTION = "ask_guiding_question"
    CHECK_STUDENT_ANSWER = "check_student_answer"
    DIAGNOSE_WRONG_INPUT = "diagnose_wrong_input"
    RETEACH_DIFFERENTLY = "reteach_differently"
    GIVE_INSTANT_HELP = "give_instant_help"
    SHOW_VISUAL_HINT = "show_visual_hint"
    REVEAL_PARTIAL_SOLUTION = "reveal_partial_solution"
    REVEAL_FULL_SOLUTION_PROGRESSIVELY = "reveal_full_solution_progressively"
    ASK_UNDERSTANDING_CHECK = "ask_understanding_check"


class VisualTutorAnswerLockDecision(str, Enum):
    LOCK_FINAL_ANSWER = "lock_final_answer"
    ALLOW_PARTIAL_REVEAL = "allow_partial_reveal"
    ALLOW_FULL_REVEAL = "allow_full_reveal"


class VisualTutorExplanationMode(str, Enum):
    ENGLISH = "english"
    KHMER = "khmer"


@dataclass(frozen=True)
class AdaptiveTutorDecision:
    tutor_move: VisualTutorMove
    screen_state: VisualTutorScreenState
    tutor_status: str
    stage_state: VisualTutorStageState
    lesson_state: VisualTutorLessonState
    board_action_budget: int
    interaction_type: VisualTutorInteractionType
    quick_actions: tuple[VisualTutorAllowedAction, ...]
    answer_lock_decision: VisualTutorAnswerLockDecision
    explanation_mode: VisualTutorExplanationMode
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def final_answer_locked(self) -> bool:
        return (
            self.answer_lock_decision != VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL
        )

    @property
    def partial_solution_allowed(self) -> bool:
        return self.answer_lock_decision in {
            VisualTutorAnswerLockDecision.ALLOW_PARTIAL_REVEAL,
            VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL,
        }


def plan_adaptive_tutor_move(
    *,
    problem_understanding: VisualTutorProblemUnderstandingResult,
    student_input_understanding: Optional[VisualTutorInputUnderstandingResult] = None,
    teaching_board_state: Optional[TeachingBoardState] = None,
    lesson_state: Optional[VisualTutorLessonState] = None,
    current_step_index: int = 0,
    wrong_attempts: int = 0,
    stuck_count: int = 0,
    hint_count: int = 0,
    student_intent: Optional[VisualTutorStudentIntent] = None,
    curriculum_context: Optional[dict[str, Any] | list[dict[str, Any]]] = None,
    solver_facts: Optional[VisualTutorSolverFacts] = None,
    allow_final_answer: bool = False,
    student_model: Optional[dict[str, Any]] = None,
    strategy_history: Optional[list[dict[str, Any]]] = None,
) -> AdaptiveTutorDecision:
    """Choose the next canvas-first teaching move.

    This layer is intentionally deterministic. It does not solve the problem; it
    decides the pedagogical move the solver or LLM planner should execute next.
    """

    effective_intent = _effective_intent(
        student_intent,
        student_input_understanding,
    )
    relevance = (
        student_input_understanding.input_relevance
        if student_input_understanding
        else None
    )
    validation_result = (
        student_input_understanding.metadata.get("validation_result")
        if student_input_understanding
        else None
    )
    safe_student_model = _safe_student_model(student_model)
    safe_strategy_history = _safe_strategy_history(
        strategy_history
        or safe_student_model.get("metadata", {}).get("strategy_history")
    )
    model_wrong_attempts = _safe_int(
        safe_student_model.get("wrong_attempt_streak"),
        default=wrong_attempts,
    )
    model_hint_count = _safe_int(
        safe_student_model.get("hint_level"),
        default=hint_count,
    )
    effective_wrong_attempts = max(wrong_attempts, model_wrong_attempts)
    effective_hint_count = max(hint_count, model_hint_count)
    recent_mistakes = [
        str(item)
        for item in safe_student_model.get("recent_mistakes", [])
        if str(item or "").strip()
    ][:3]
    explanation_mode = _explanation_mode(
        problem_understanding,
        student_input_understanding,
    )
    answer_lock_decision = _answer_lock_decision(
        allow_final_answer=allow_final_answer,
        hint_count=effective_hint_count,
        wrong_attempts=effective_wrong_attempts,
        stuck_count=stuck_count,
        intent=effective_intent,
    )
    base_metadata = {
        "planner": ADAPTIVE_TUTOR_PLANNER_VERSION,
        "problem_type": problem_understanding.problem_type,
        "known_solver_available": problem_understanding.known_solver_available,
        "confidence": problem_understanding.confidence,
        "student_intent": effective_intent.value,
        "input_relevance": relevance.value if relevance else None,
        "validation_result": validation_result,
        "current_step_index": current_step_index,
        "solver_facts_available": solver_facts is not None,
        "solver_facts": solver_facts.model_dump(mode="json")
        if solver_facts is not None
        else None,
        "wrong_attempts": effective_wrong_attempts,
        "raw_wrong_attempts": wrong_attempts,
        "stuck_count": stuck_count,
        "hint_count": effective_hint_count,
        "raw_hint_count": hint_count,
        "has_teaching_board_state": teaching_board_state is not None,
        "current_focus_element_id": (
            teaching_board_state.focus_element_id if teaching_board_state else None
        ),
        "curriculum_context_available": bool(curriculum_context),
        "lesson_state_in": lesson_state.value if lesson_state else None,
        "allow_final_answer": allow_final_answer,
        "student_model": safe_student_model,
        "student_model_available": bool(student_model),
        "strategy_history": safe_strategy_history,
        "strategy_history_available": bool(safe_strategy_history),
        "recent_mistakes": recent_mistakes,
    }
    representation, alternate_representation = _representation_plan(
        problem_type=problem_understanding.problem_type,
        strategy_history=safe_strategy_history,
        explain_differently=effective_intent
        == VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY,
    )
    base_metadata.update(
        {
            "representation": representation,
            "alternate_representation": alternate_representation,
            "explain_differently_requires_representation_change": (
                effective_intent == VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY
            ),
        }
    )

    if effective_intent == VisualTutorStudentIntent.REQUEST_ANSWER:
        if answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL:
            return _decision(
                VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY,
                VisualTutorStageState.DRAWING,
                VisualTutorLessonState.VERIFY,
                board_action_budget=3,
                interaction_type=VisualTutorInteractionType.YES_NO,
                answer_lock_decision=answer_lock_decision,
                explanation_mode=explanation_mode,
                metadata={
                    **base_metadata,
                    "reason": "student_requested_answer_and_policy_allows_full_reveal",
                },
            )
        if answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_PARTIAL_REVEAL:
            return _decision(
                VisualTutorMove.REVEAL_PARTIAL_SOLUTION,
                VisualTutorStageState.DRAWING,
                VisualTutorLessonState.TEACH,
                board_action_budget=2,
                interaction_type=_interaction_for_problem(problem_understanding),
                answer_lock_decision=answer_lock_decision,
                explanation_mode=explanation_mode,
                metadata={
                    **base_metadata,
                    "reason": "student_requested_answer_but_only_partial_reveal_allowed",
                },
            )
        return _decision(
            VisualTutorMove.GIVE_INSTANT_HELP,
            VisualTutorStageState.WAITING_FOR_STUDENT,
            VisualTutorLessonState.INSTANT_HELP,
            board_action_budget=1,
            interaction_type=_interaction_for_problem(problem_understanding),
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={
                **base_metadata,
                "reason": "student_requested_answer_but_reasoning_support_needed_first",
            },
        )

    if effective_intent == VisualTutorStudentIntent.STUCK:
        if answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_PARTIAL_REVEAL:
            return _decision(
                VisualTutorMove.REVEAL_PARTIAL_SOLUTION,
                VisualTutorStageState.DRAWING,
                VisualTutorLessonState.TEACH,
                board_action_budget=2,
                interaction_type=_interaction_for_problem(problem_understanding),
                answer_lock_decision=answer_lock_decision,
                explanation_mode=explanation_mode,
                metadata={
                    **base_metadata,
                    "reason": "repeated_stuck_unlocks_partial_solution",
                },
            )
        return _decision(
            VisualTutorMove.RETEACH_DIFFERENTLY,
            VisualTutorStageState.ADAPTING,
            VisualTutorLessonState.RETEACH_OR_CONTINUE,
            board_action_budget=1,
            interaction_type=_interaction_for_problem(problem_understanding),
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={
                **base_metadata,
                "reason": "student_is_stuck_reteach_current_step",
            },
        )

    if effective_intent == VisualTutorStudentIntent.REQUEST_EXPLAIN_DIFFERENTLY:
        return _decision(
            VisualTutorMove.RETEACH_DIFFERENTLY,
            VisualTutorStageState.ADAPTING,
            VisualTutorLessonState.RETEACH_OR_CONTINUE,
            board_action_budget=1,
            interaction_type=_interaction_for_problem(problem_understanding),
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={
                **base_metadata,
                "reason": "student_requested_different_explanation",
            },
        )

    if relevance in {
        VisualTutorInputRelevance.UNRELATED,
        VisualTutorInputRelevance.OFF_TOPIC,
        VisualTutorInputRelevance.UNKNOWN,
    }:
        return _decision(
            VisualTutorMove.DIAGNOSE_WRONG_INPUT,
            VisualTutorStageState.ADAPTING,
            VisualTutorLessonState.RETEACH_OR_CONTINUE,
            board_action_budget=1,
            interaction_type=VisualTutorInteractionType.TEXT_RESPONSE,
            answer_lock_decision=VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER,
            explanation_mode=explanation_mode,
            metadata={
                **base_metadata,
                "reason": "input_does_not_match_current_visual_step",
                "do_not_count_as_submitted_step": True,
                "board_should_advance": False,
                "wrong_input_does_not_advance_board": True,
            },
        )

    if relevance == VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER:
        return _decision(
            (
                VisualTutorMove.CHECK_STUDENT_ANSWER
                if _looks_correct(validation_result)
                else VisualTutorMove.DIAGNOSE_WRONG_INPUT
            ),
            VisualTutorStageState.EVALUATING,
            VisualTutorLessonState.EVALUATE,
            board_action_budget=1,
            interaction_type=_interaction_for_problem(problem_understanding),
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={
                **base_metadata,
                "reason": "student_submitted_possible_final_answer_check_without_copying",
                "board_should_advance": _looks_correct(validation_result),
                "possible_final_answer_checked_separately": True,
            },
        )

    if relevance == VisualTutorInputRelevance.RELEVANT_STEP:
        if _looks_correct(validation_result):
            return _decision(
                VisualTutorMove.TEACH_NEXT_VISUAL_STEP,
                VisualTutorStageState.WAITING_FOR_STUDENT,
                VisualTutorLessonState.ASK,
                board_action_budget=1,
                interaction_type=_interaction_for_problem(problem_understanding),
                answer_lock_decision=answer_lock_decision,
                explanation_mode=explanation_mode,
                metadata={
                    **base_metadata,
                    "reason": "valid_relevant_step_advance_one_visual_step",
                    "board_should_advance": True,
                    "valid_answer_advances_board": True,
                },
            )
        if effective_wrong_attempts + 1 >= PARTIAL_UNLOCK_WRONG_THRESHOLD:
            return _decision(
                VisualTutorMove.REVEAL_PARTIAL_SOLUTION,
                VisualTutorStageState.DRAWING,
                VisualTutorLessonState.TEACH,
                board_action_budget=2,
                interaction_type=_interaction_for_problem(problem_understanding),
                answer_lock_decision=VisualTutorAnswerLockDecision.ALLOW_PARTIAL_REVEAL,
                explanation_mode=explanation_mode,
                metadata={
                    **base_metadata,
                    "reason": "repeated_wrong_relevant_steps_unlock_partial_solution",
                    "board_should_advance": False,
                    "answer_reveal_progressive": True,
                },
            )
        return _decision(
            VisualTutorMove.DIAGNOSE_WRONG_INPUT,
            VisualTutorStageState.EVALUATING,
            VisualTutorLessonState.RETEACH_OR_CONTINUE,
            board_action_budget=1,
            interaction_type=_interaction_for_problem(problem_understanding),
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={
                **base_metadata,
                "reason": "wrong_relevant_step_highlight_first_mistake_only",
                "highlight_first_mistake_only": True,
                "board_should_advance": False,
                "wrong_input_does_not_advance_board": True,
            },
        )

    if effective_intent == VisualTutorStudentIntent.REQUEST_HINT:
        if answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_PARTIAL_REVEAL:
            return _decision(
                VisualTutorMove.REVEAL_PARTIAL_SOLUTION,
                VisualTutorStageState.DRAWING,
                VisualTutorLessonState.TEACH,
                board_action_budget=2,
                interaction_type=_interaction_for_problem(problem_understanding),
                answer_lock_decision=answer_lock_decision,
                explanation_mode=explanation_mode,
                metadata={**base_metadata, "reason": "hint_threshold_allows_partial"},
            )
        return _decision(
            VisualTutorMove.SHOW_VISUAL_HINT,
            VisualTutorStageState.WAITING_FOR_STUDENT,
            VisualTutorLessonState.INSTANT_HELP,
            board_action_budget=1,
            interaction_type=_interaction_for_problem(problem_understanding),
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={**base_metadata, "reason": "student_requested_visual_hint"},
        )

    if effective_intent == VisualTutorStudentIntent.CLARIFICATION:
        return _decision(
            VisualTutorMove.ASK_GUIDING_QUESTION,
            VisualTutorStageState.WAITING_FOR_STUDENT,
            VisualTutorLessonState.ASK,
            board_action_budget=1,
            interaction_type=VisualTutorInteractionType.TEXT_RESPONSE,
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={**base_metadata, "reason": "student_asked_clarification"},
        )

    if lesson_state == VisualTutorLessonState.COMPLETE:
        return _decision(
            VisualTutorMove.ASK_UNDERSTANDING_CHECK,
            VisualTutorStageState.WAITING_FOR_STUDENT,
            VisualTutorLessonState.VERIFY,
            board_action_budget=1,
            interaction_type=VisualTutorInteractionType.YES_NO,
            answer_lock_decision=answer_lock_decision,
            explanation_mode=explanation_mode,
            metadata={
                **base_metadata,
                "reason": "verify_understanding_after_completion",
            },
        )

    return _decision(
        VisualTutorMove.ASK_GUIDING_QUESTION,
        VisualTutorStageState.WAITING_FOR_STUDENT,
        VisualTutorLessonState.ASK,
        board_action_budget=1,
        interaction_type=_interaction_for_problem(problem_understanding),
        answer_lock_decision=answer_lock_decision,
        explanation_mode=explanation_mode,
        metadata={
            **base_metadata,
            "reason": "default_canvas_first_guiding_question",
            "prefer_visual_response_over_chat": True,
        },
    )


def _decision(
    tutor_move: VisualTutorMove,
    stage_state: VisualTutorStageState,
    lesson_state: VisualTutorLessonState,
    *,
    board_action_budget: int,
    interaction_type: VisualTutorInteractionType,
    answer_lock_decision: VisualTutorAnswerLockDecision,
    explanation_mode: VisualTutorExplanationMode,
    metadata: dict[str, Any],
) -> AdaptiveTutorDecision:
    (
        tutor_move,
        stage_state,
        lesson_state,
        board_action_budget,
        interaction_type,
        answer_lock_decision,
        metadata,
    ) = _apply_adaptive_strategy_overrides(
        tutor_move=tutor_move,
        stage_state=stage_state,
        lesson_state=lesson_state,
        board_action_budget=board_action_budget,
        interaction_type=interaction_type,
        answer_lock_decision=answer_lock_decision,
        metadata=metadata,
    )
    screen_state = _screen_state_for_move(tutor_move, metadata=metadata)
    tutor_status = _tutor_status_for_move(tutor_move, stage_state=stage_state)
    quick_actions = _quick_actions_for_move(
        tutor_move,
        answer_lock_decision,
        metadata=metadata,
    )
    decision_metadata = {
        **metadata,
        "screen_state": screen_state.value,
        "tutor_status": tutor_status,
        "quick_actions": [action.value for action in quick_actions],
        "one_teaching_moment_per_turn": True,
        "one_short_speech": True,
        "one_focused_visual_update": True,
        "one_student_task_or_question": True,
        "answer_reveal_progressive": metadata.get(
            "answer_reveal_progressive",
            answer_lock_decision
            == VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL,
        ),
        "llm_cannot_bypass_policy": True,
    }
    return AdaptiveTutorDecision(
        tutor_move=tutor_move,
        screen_state=screen_state,
        tutor_status=tutor_status,
        stage_state=stage_state,
        lesson_state=lesson_state,
        board_action_budget=max(1, board_action_budget),
        interaction_type=interaction_type,
        quick_actions=quick_actions,
        answer_lock_decision=answer_lock_decision,
        explanation_mode=explanation_mode,
        metadata=decision_metadata,
    )


def _apply_adaptive_strategy_overrides(
    *,
    tutor_move: VisualTutorMove,
    stage_state: VisualTutorStageState,
    lesson_state: VisualTutorLessonState,
    board_action_budget: int,
    interaction_type: VisualTutorInteractionType,
    answer_lock_decision: VisualTutorAnswerLockDecision,
    metadata: dict[str, Any],
) -> tuple[
    VisualTutorMove,
    VisualTutorStageState,
    VisualTutorLessonState,
    int,
    VisualTutorInteractionType,
    VisualTutorAnswerLockDecision,
    dict[str, Any],
]:
    if tutor_move in {
        VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY,
        VisualTutorMove.REVEAL_PARTIAL_SOLUTION,
    } and metadata.get("student_intent") == VisualTutorStudentIntent.REQUEST_ANSWER.value:
        return (
            tutor_move,
            stage_state,
            lesson_state,
            board_action_budget,
            interaction_type,
            answer_lock_decision,
            metadata,
        )

    strategy_history = _safe_strategy_history(metadata.get("strategy_history"))
    recent_moves = _recent_strategy_values(strategy_history, "tutor_move")
    latest_move = recent_moves[-1] if recent_moves else None
    consecutive_same = _consecutive_tail_count(recent_moves, tutor_move.value)
    recent_mistakes = metadata.get("recent_mistakes")
    if not isinstance(recent_mistakes, list):
        recent_mistakes = []
    latest_mistake = str(recent_mistakes[0]) if recent_mistakes else None
    repeated_mistake = (
        len(recent_mistakes) >= 2 and str(recent_mistakes[0]) == str(recent_mistakes[1])
    )
    wrong_attempts = _safe_int(metadata.get("wrong_attempts"), default=0)
    student_intent = str(metadata.get("student_intent") or "")
    adapted_reason: Optional[str] = None

    if (
        wrong_attempts >= 3
        and tutor_move
        not in {
            VisualTutorMove.RETEACH_DIFFERENTLY,
            VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY,
        }
    ):
        tutor_move = VisualTutorMove.RETEACH_DIFFERENTLY
        stage_state = VisualTutorStageState.ADAPTING
        lesson_state = VisualTutorLessonState.RETEACH_OR_CONTINUE
        interaction_type = VisualTutorInteractionType.TEXT_RESPONSE
        answer_lock_decision = VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER
        adapted_reason = "wrong_attempt_streak_requires_simpler_reteach"
    elif wrong_attempts >= 2 and latest_move == VisualTutorMove.CHECK_STUDENT_ANSWER.value:
        tutor_move = VisualTutorMove.RETEACH_DIFFERENTLY
        stage_state = VisualTutorStageState.ADAPTING
        lesson_state = VisualTutorLessonState.RETEACH_OR_CONTINUE
        interaction_type = VisualTutorInteractionType.TEXT_RESPONSE
        answer_lock_decision = VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER
        adapted_reason = "repeated_wrong_after_check_requires_reteach"
    elif (
        latest_move == VisualTutorMove.SHOW_VISUAL_HINT.value
        and student_intent == VisualTutorStudentIntent.STUCK.value
    ):
        tutor_move = VisualTutorMove.RETEACH_DIFFERENTLY
        stage_state = VisualTutorStageState.ADAPTING
        lesson_state = VisualTutorLessonState.RETEACH_OR_CONTINUE
        interaction_type = VisualTutorInteractionType.TEXT_RESPONSE
        adapted_reason = "visual_hint_did_not_unstick_student"
    elif (wrong_attempts >= 2 or repeated_mistake) and consecutive_same >= 2:
        if tutor_move == VisualTutorMove.SHOW_VISUAL_HINT:
            tutor_move = VisualTutorMove.RETEACH_DIFFERENTLY
            stage_state = VisualTutorStageState.ADAPTING
            lesson_state = VisualTutorLessonState.RETEACH_OR_CONTINUE
            interaction_type = VisualTutorInteractionType.TEXT_RESPONSE
            adapted_reason = "avoid_repeating_visual_hint"
        elif tutor_move in {
            VisualTutorMove.RETEACH_DIFFERENTLY,
            VisualTutorMove.DIAGNOSE_WRONG_INPUT,
            VisualTutorMove.CHECK_STUDENT_ANSWER,
            VisualTutorMove.ASK_GUIDING_QUESTION,
        }:
            tutor_move = VisualTutorMove.SHOW_VISUAL_HINT
            stage_state = VisualTutorStageState.WAITING_FOR_STUDENT
            lesson_state = VisualTutorLessonState.INSTANT_HELP
            board_action_budget = max(board_action_budget, 2)
            adapted_reason = "avoid_repeating_same_pedagogy"
    elif (
        tutor_move == VisualTutorMove.REVEAL_PARTIAL_SOLUTION
        and (wrong_attempts >= 2 or repeated_mistake)
        and latest_move
        in {
            VisualTutorMove.DIAGNOSE_WRONG_INPUT.value,
            VisualTutorMove.CHECK_STUDENT_ANSWER.value,
            VisualTutorMove.ASK_GUIDING_QUESTION.value,
        }
    ):
        tutor_move = VisualTutorMove.SHOW_VISUAL_HINT
        stage_state = VisualTutorStageState.WAITING_FOR_STUDENT
        lesson_state = VisualTutorLessonState.INSTANT_HELP
        board_action_budget = max(board_action_budget, 2)
        answer_lock_decision = VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER
        adapted_reason = "repeated_mistake_prefers_visual_before_reveal"

    if tutor_move == VisualTutorMove.SHOW_VISUAL_HINT:
        board_action_budget = max(board_action_budget, 2)
        metadata = {
            **metadata,
            "visual_hint_required": True,
            "visual_first_strategy": True,
            "spoken_text_should_be_short": True,
        }
    elif tutor_move == VisualTutorMove.RETEACH_DIFFERENTLY:
        metadata = {
            **metadata,
            "explanation_strategy": _next_explanation_strategy(
                latest_mistake=latest_mistake,
                strategy_history=strategy_history,
            ),
            "must_change_explanation_strategy": True,
            "should_not_replay_same_board_action": True,
        }

    if adapted_reason:
        metadata = {
            **metadata,
            "adaptation_override": adapted_reason,
            "reason": adapted_reason,
            "previous_tutor_moves": recent_moves[-5:],
            "last_addressed_mistake_category": latest_mistake,
        }

    return (
        tutor_move,
        stage_state,
        lesson_state,
        board_action_budget,
        interaction_type,
        answer_lock_decision,
        metadata,
    )


def _effective_intent(
    student_intent: Optional[VisualTutorStudentIntent],
    student_input_understanding: Optional[VisualTutorInputUnderstandingResult],
) -> VisualTutorStudentIntent:
    if student_intent and student_intent != VisualTutorStudentIntent.UNKNOWN:
        return student_intent
    if student_input_understanding:
        return student_input_understanding.student_intent
    return VisualTutorStudentIntent.UNKNOWN


def _safe_student_model(value: Optional[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "understanding": "exploring",
            "recent_mistakes": [],
            "hint_level": 0,
            "wrong_attempt_streak": 0,
            "preferred_language": "en",
            "preferred_explanation_level": "standard",
            "recommended_depth": "standard",
            "last_mastery_signal": None,
            "metadata": {},
        }
    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
    recent_mistakes = value.get("recent_mistakes")
    if not isinstance(recent_mistakes, list):
        recent_mistakes = []
    return {
        "understanding": value.get("understanding", "exploring"),
        "recent_mistakes": recent_mistakes,
        "hint_level": _safe_int(value.get("hint_level"), default=0),
        "wrong_attempt_streak": _safe_int(value.get("wrong_attempt_streak"), default=0),
        "preferred_language": value.get("preferred_language", "en"),
        "preferred_explanation_level": value.get(
            "preferred_explanation_level",
            "standard",
        ),
        "recommended_depth": value.get("recommended_depth", "standard"),
        "last_mastery_signal": value.get("last_mastery_signal"),
        "metadata": metadata,
    }


def _safe_strategy_history(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value[-12:] if isinstance(entry, dict)]


def _safe_int(value: Any, *, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _recent_strategy_values(
    strategy_history: list[dict[str, Any]],
    key: str,
) -> list[str]:
    values: list[str] = []
    for entry in strategy_history:
        value = entry.get(key)
        if value is not None and str(value).strip():
            values.append(str(value))
    return values


def _consecutive_tail_count(values: list[str], candidate: str) -> int:
    count = 0
    for value in reversed(values):
        if value != candidate:
            break
        count += 1
    return count


def _next_explanation_strategy(
    *,
    latest_mistake: Optional[str],
    strategy_history: list[dict[str, Any]],
) -> str:
    previous = [
        str(entry.get("explanation_strategy"))
        for entry in strategy_history
        if entry.get("explanation_strategy")
    ]
    if latest_mistake:
        preferred = "misconception_correction"
        if previous and previous[-1] == preferred:
            return "decompose_smaller_step"
        return preferred
    candidates = ["decompose_smaller_step", "use_analogy", "compare_examples"]
    for candidate in candidates:
        if not previous or previous[-1] != candidate:
            return candidate
    return candidates[0]


def _representation_plan(
    *,
    problem_type: str,
    strategy_history: list[dict[str, Any]],
    explain_differently: bool,
) -> tuple[str, str]:
    """Choose a suitable visual, then a genuinely different fallback visual."""
    choices = {
        "linear_equation_one_variable": ("equation_transformation", "balance_scale"),
        "slope_from_two_points": ("coordinate_graph", "rise_over_run_table"),
        "line_through_two_points": ("coordinate_graph", "value_table"),
        "quadratic_equation_basic": ("factor_pairs", "parabola_graph"),
    }.get(problem_type, ("guided_text_visual", "worked_example_comparison"))
    prior = [str(item.get("representation")) for item in strategy_history if item.get("representation")]
    if explain_differently or (prior and prior[-1] == choices[0]):
        return choices[1], choices[0]
    return choices


def _explanation_mode(
    problem_understanding: VisualTutorProblemUnderstandingResult,
    student_input_understanding: Optional[VisualTutorInputUnderstandingResult],
) -> VisualTutorExplanationMode:
    if problem_understanding.language == "km":
        return VisualTutorExplanationMode.KHMER
    if student_input_understanding and (
        student_input_understanding.metadata.get("language") == "km"
        or student_input_understanding.metadata.get("use_khmer_explanation") is True
    ):
        return VisualTutorExplanationMode.KHMER
    return VisualTutorExplanationMode.ENGLISH


def _answer_lock_decision(
    *,
    allow_final_answer: bool,
    hint_count: int,
    wrong_attempts: int,
    stuck_count: int,
    intent: VisualTutorStudentIntent,
) -> VisualTutorAnswerLockDecision:
    if intent == VisualTutorStudentIntent.REQUEST_ANSWER:
        return VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL
    if (
        allow_final_answer
        or hint_count >= FULL_UNLOCK_HINT_THRESHOLD
        or wrong_attempts >= FULL_UNLOCK_WRONG_THRESHOLD
    ):
        return VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL
    if (
        hint_count >= PARTIAL_UNLOCK_HINT_THRESHOLD
        or stuck_count >= PARTIAL_UNLOCK_HINT_THRESHOLD
        or (
            intent == VisualTutorStudentIntent.STUCK
            and stuck_count + 1 >= PARTIAL_UNLOCK_HINT_THRESHOLD
        )
    ):
        return VisualTutorAnswerLockDecision.ALLOW_PARTIAL_REVEAL
    return VisualTutorAnswerLockDecision.LOCK_FINAL_ANSWER


def _screen_state_for_move(
    tutor_move: VisualTutorMove,
    *,
    metadata: dict[str, Any],
) -> VisualTutorScreenState:
    if tutor_move == VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY:
        return VisualTutorScreenState.FINAL_VERIFIED_ANSWER
    if tutor_move in {
        VisualTutorMove.CHECK_STUDENT_ANSWER,
        VisualTutorMove.DIAGNOSE_WRONG_INPUT,
    }:
        return VisualTutorScreenState.CHECK_MY_WORK
    if metadata.get("problem_type") == "function_graph":
        return VisualTutorScreenState.GRAPH_BASED
    if tutor_move in {
        VisualTutorMove.ASK_GUIDING_QUESTION,
        VisualTutorMove.ASK_UNDERSTANDING_CHECK,
    }:
        return VisualTutorScreenState.ASKING_QUESTION
    return VisualTutorScreenState.SPEAKING_WRITING


def _tutor_status_for_move(
    tutor_move: VisualTutorMove,
    *,
    stage_state: VisualTutorStageState,
) -> str:
    if tutor_move == VisualTutorMove.DIAGNOSE_WRONG_INPUT:
        return "Checking"
    if tutor_move == VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY:
        return "Verified"
    if tutor_move in {
        VisualTutorMove.RETEACH_DIFFERENTLY,
        VisualTutorMove.GIVE_INSTANT_HELP,
        VisualTutorMove.SHOW_VISUAL_HINT,
        VisualTutorMove.REVEAL_PARTIAL_SOLUTION,
    }:
        return "Writing..."
    if stage_state == VisualTutorStageState.EVALUATING:
        return "Checking"
    return "Waiting for you"


def _quick_actions_for_move(
    tutor_move: VisualTutorMove,
    answer_lock_decision: VisualTutorAnswerLockDecision,
    *,
    metadata: dict[str, Any],
) -> tuple[VisualTutorAllowedAction, ...]:
    if metadata.get("problem_type") == "function_graph":
        return (
            VisualTutorAllowedAction.SHOW_VISUALLY,
            VisualTutorAllowedAction.REQUEST_HINT,
            VisualTutorAllowedAction.STUCK,
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
        )
    common = (
        VisualTutorAllowedAction.REQUEST_HINT,
        VisualTutorAllowedAction.STUCK,
        VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
    )
    if tutor_move == VisualTutorMove.DIAGNOSE_WRONG_INPUT:
        return (
            VisualTutorAllowedAction.REQUEST_HINT,
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.CHECK_WORK,
            VisualTutorAllowedAction.REQUEST_ANSWER,
        )
    if answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL:
        return (
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.SHOW_VISUALLY,
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.REQUEST_ANSWER,
        )
    return (
        VisualTutorAllowedAction.SUBMIT_ANSWER,
        *common,
        VisualTutorAllowedAction.REQUEST_ANSWER,
    )


def _interaction_for_problem(
    problem_understanding: VisualTutorProblemUnderstandingResult,
) -> VisualTutorInteractionType:
    problem_type = problem_understanding.problem_type
    if problem_type in {
        "linear_equation_one_variable",
        "line_through_two_points",
        "slope_from_two_points",
        "arithmetic_expression",
        "simple_percentage_word_problem",
    }:
        return VisualTutorInteractionType.NUMERIC_INPUT
    return VisualTutorInteractionType.TEXT_RESPONSE


def _looks_correct(validation_result: Optional[Any]) -> bool:
    value = str(validation_result or "").lower()
    return value.startswith("correct")
