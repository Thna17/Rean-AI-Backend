from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorInputRelevance,
    VisualTutorInputUnderstandingResult,
    VisualTutorStudentIntent,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.intent import detect_visual_tutor_student_intent

FINAL_HINT_UNLOCK_THRESHOLD = 3
FINAL_WRONG_UNLOCK_THRESHOLD = 2
PARTIAL_HINT_THRESHOLD = 2
PARTIAL_WRONG_ATTEMPT_THRESHOLD = 2


@dataclass(frozen=True)
class VisualTutorPolicyDecision:
    teaching_mode: VisualTutorTeachingMode
    final_answer_locked: bool = True
    partial_solution_allowed: bool = False
    full_solution_allowed: bool = False
    request_student_step: bool = False
    give_hint: bool = False
    diagnose_misconception: bool = False
    reveal_final: bool = False
    reveal_partial: bool = False
    should_check_step: bool = False
    should_ask_question: bool = False
    use_khmer_explanation: bool = False
    explain_differently: bool = False
    stuck_help: bool = False
    input_relevance: Optional[VisualTutorInputRelevance] = None
    should_redirect_input: bool = False
    possible_final_answer: bool = False
    validation_result: Optional[str] = None
    misconception_type: Optional[str] = None
    reason: str = "guided_learning"
    metadata: dict[str, Any] = field(default_factory=dict)


def decide_visual_tutor_policy(
    request: VisualTutorTurnRequest,
    *,
    has_problem: bool,
    is_correct_step: Optional[bool] = None,
    problem_type: Optional[str] = None,
    known_solver_available: bool = True,
    input_understanding: Optional[VisualTutorInputUnderstandingResult] = None,
) -> VisualTutorPolicyDecision:
    hint_count = _hint_count(request)
    wrong_attempts = _wrong_attempts(request)
    use_khmer = _should_use_khmer(request)
    explain_differently = request.action == VisualTutorAction.EXPLAIN_DIFFERENTLY
    intent_detection = detect_visual_tutor_student_intent(request)
    if (
        input_understanding is not None
        and request.current_state.problem_text
        and input_understanding.student_intent != VisualTutorStudentIntent.NEW_PROBLEM
    ):
        detected_intent = input_understanding.student_intent
    elif intent_detection.intent == VisualTutorStudentIntent.NEW_PROBLEM:
        detected_intent = VisualTutorStudentIntent.NEW_PROBLEM
    else:
        detected_intent = (
            input_understanding.student_intent
            if input_understanding
            else intent_detection.intent
        )
    input_relevance = (
        input_understanding.input_relevance if input_understanding else None
    )
    validation_result = (
        input_understanding.metadata.get("validation_result")
        if input_understanding
        else None
    )
    misconception_type = (
        input_understanding.metadata.get("misconception_type")
        if input_understanding
        else None
    )
    stuck_help = detected_intent == VisualTutorStudentIntent.STUCK
    effective_hint_count = hint_count + 1 if stuck_help else hint_count

    metadata = {
        "policy": "visual_tutor_v1",
        "hint_count": hint_count,
        "effective_hint_count": effective_hint_count,
        "wrong_attempts": wrong_attempts,
        "problem_type": problem_type or "unknown",
        "known_solver_available": known_solver_available,
        "use_khmer_explanation": use_khmer,
        "explain_differently": explain_differently,
        "detected_intent": detected_intent.value,
        "student_intent": detected_intent.value,
        "stuck_reason": intent_detection.reason if stuck_help else None,
        "input_relevance": input_relevance.value if input_relevance else None,
        "input_understanding": (
            input_understanding.model_dump(mode="json") if input_understanding else None
        ),
        "expected_step": (
            input_understanding.metadata.get("expected_step")
            if input_understanding
            else None
        ),
        "validation_result": validation_result,
        "misconception_type": misconception_type,
        "redirect_reason": None,
    }

    should_check_step = _should_check_step(request, input_relevance=input_relevance)

    # A confirmed submitted problem is a teaching turn, not a greeting.  It
    # must reach the guided-question policy so the student receives the first
    # small step and one task rather than an empty welcome response.
    if not has_problem:
        return VisualTutorPolicyDecision(
            teaching_mode=VisualTutorTeachingMode.GREETING,
            should_ask_question=True,
            request_student_step=True,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="ask_guiding_question_first" if has_problem else "no_problem_yet",
            metadata=metadata,
        )

    if validation_result in {
        "understanding_check_yes",
        "understanding_check_no",
    }:
        return VisualTutorPolicyDecision(
            teaching_mode=VisualTutorTeachingMode.STEP_CHECK,
            final_answer_locked=False,
            partial_solution_allowed=True,
            full_solution_allowed=True,
            request_student_step=False,
            reveal_final=True,
            reveal_partial=True,
            should_check_step=True,
            should_ask_question=True,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            possible_final_answer=False,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="understanding_check_response",
            metadata=metadata,
        )

    if stuck_help:
        reveal_final = _can_reveal_final(
            request,
            hint_count_override=effective_hint_count,
        )
        reveal_partial = effective_hint_count >= PARTIAL_HINT_THRESHOLD
        diagnose_misconception = wrong_attempts > 0 and not reveal_partial
        teaching_mode = VisualTutorTeachingMode.STUCK_HELP
        if reveal_partial:
            teaching_mode = VisualTutorTeachingMode.PARTIAL_SOLUTION
        elif diagnose_misconception:
            teaching_mode = VisualTutorTeachingMode.MISCONCEPTION_FIX
        return VisualTutorPolicyDecision(
            teaching_mode=teaching_mode,
            final_answer_locked=not reveal_final,
            partial_solution_allowed=reveal_partial,
            full_solution_allowed=reveal_final,
            request_student_step=not reveal_final,
            give_hint=not reveal_partial,
            diagnose_misconception=diagnose_misconception,
            reveal_final=reveal_final,
            reveal_partial=reveal_partial,
            should_ask_question=not reveal_partial,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=True,
            input_relevance=input_relevance,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="stuck_help",
            metadata={
                **metadata,
                "stuck_progression": (
                    "partial_after_repeated_stuck"
                    if reveal_partial
                    else (
                        "misconception_after_wrong_attempt"
                        if diagnose_misconception
                        else "first_stuck_hint"
                    )
                ),
            },
        )

    if _should_redirect_input(input_relevance):
        teaching_mode = (
            VisualTutorTeachingMode.MISCONCEPTION_FIX
            if input_relevance == VisualTutorInputRelevance.UNRELATED
            else VisualTutorTeachingMode.GUIDED_QUESTION
        )
        redirect_reason = (
            "unrelated_to_current_step"
            if input_relevance == VisualTutorInputRelevance.UNRELATED
            else "off_topic_message"
        )
        return VisualTutorPolicyDecision(
            teaching_mode=teaching_mode,
            final_answer_locked=True,
            request_student_step=True,
            diagnose_misconception=input_relevance
            == VisualTutorInputRelevance.UNRELATED,
            should_ask_question=True,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            should_redirect_input=True,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason=redirect_reason,
            metadata={**metadata, "redirect_reason": redirect_reason},
        )

    if validation_result == "correct_final_step":
        return VisualTutorPolicyDecision(
            teaching_mode=VisualTutorTeachingMode.STEP_CHECK,
            final_answer_locked=False,
            partial_solution_allowed=True,
            full_solution_allowed=True,
            request_student_step=False,
            reveal_final=True,
            reveal_partial=True,
            should_check_step=True,
            should_ask_question=True,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            possible_final_answer=False,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="correct_final_step",
            metadata=metadata,
        )

    if (
        input_relevance == VisualTutorInputRelevance.POSSIBLE_FINAL_ANSWER
        and request.action != VisualTutorAction.REQUEST_FINAL_ANSWER
    ):
        reveal_final = _can_reveal_final(request)
        return VisualTutorPolicyDecision(
            teaching_mode=(
                VisualTutorTeachingMode.FULL_SOLUTION
                if reveal_final
                else VisualTutorTeachingMode.MISCONCEPTION_FIX
            ),
            final_answer_locked=not reveal_final,
            partial_solution_allowed=False,
            full_solution_allowed=reveal_final,
            request_student_step=not reveal_final,
            give_hint=not reveal_final,
            diagnose_misconception=True,
            reveal_final=reveal_final,
            reveal_partial=False,
            should_check_step=False,
            should_ask_question=not reveal_final,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            possible_final_answer=True,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason=(
                "final_answer_attempt_allowed"
                if reveal_final
                else "final_answer_attempt_locked"
            ),
            metadata={
                **metadata,
                "redirect_reason": (
                    None if reveal_final else "reasoning_required_before_final"
                ),
            },
        )

    if should_check_step:
        if is_correct_step is True:
            reveal_final = _can_reveal_final(request)
            return VisualTutorPolicyDecision(
                teaching_mode=VisualTutorTeachingMode.STEP_CHECK,
                final_answer_locked=not reveal_final,
                partial_solution_allowed=True,
                full_solution_allowed=reveal_final,
                request_student_step=True,
                reveal_final=reveal_final,
                reveal_partial=True,
                should_check_step=True,
                should_ask_question=True,
                use_khmer_explanation=use_khmer,
                explain_differently=explain_differently,
                stuck_help=stuck_help,
                input_relevance=input_relevance,
                validation_result=validation_result,
                misconception_type=misconception_type,
                reason="correct_step_check",
                metadata=metadata,
            )

        projected_wrong_attempts = wrong_attempts + 1
        reveal_final = _can_reveal_final(request)
        reveal_partial = projected_wrong_attempts >= PARTIAL_WRONG_ATTEMPT_THRESHOLD
        return VisualTutorPolicyDecision(
            teaching_mode=(
                VisualTutorTeachingMode.PARTIAL_SOLUTION
                if reveal_partial
                else VisualTutorTeachingMode.MISCONCEPTION_FIX
            ),
            final_answer_locked=not reveal_final,
            partial_solution_allowed=reveal_partial,
            full_solution_allowed=reveal_final,
            request_student_step=not reveal_final,
            diagnose_misconception=True,
            reveal_final=reveal_final,
            reveal_partial=reveal_partial,
            should_check_step=True,
            should_ask_question=not reveal_partial,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="misconception_detected",
            metadata={**metadata, "projected_wrong_attempts": projected_wrong_attempts},
        )

    if (
        request.action == VisualTutorAction.REQUEST_FINAL_ANSWER
        or detected_intent == VisualTutorStudentIntent.REQUEST_ANSWER
    ):
        reveal_final = True
        return VisualTutorPolicyDecision(
            teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
            final_answer_locked=False,
            partial_solution_allowed=True,
            full_solution_allowed=True,
            request_student_step=False,
            reveal_final=True,
            reveal_partial=True,
            should_ask_question=True,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="final_answer_requested",
            metadata={**metadata, "answer_reveal_policy": "requested_by_student"},
        )

    if request.action == VisualTutorAction.REQUEST_HINT:
        reveal_final = _can_reveal_final(request)
        reveal_partial = hint_count >= PARTIAL_HINT_THRESHOLD
        return VisualTutorPolicyDecision(
            teaching_mode=(
                VisualTutorTeachingMode.PARTIAL_SOLUTION
                if reveal_partial
                else VisualTutorTeachingMode.HINT
            ),
            final_answer_locked=not reveal_final,
            partial_solution_allowed=reveal_partial,
            full_solution_allowed=reveal_final,
            request_student_step=not reveal_final,
            give_hint=not reveal_partial,
            reveal_final=reveal_final,
            reveal_partial=reveal_partial,
            should_ask_question=not reveal_partial,
            use_khmer_explanation=use_khmer,
            explain_differently=explain_differently,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="hint_progression",
            metadata=metadata,
        )

    if explain_differently:
        reveal_final = _can_reveal_final(request)
        return VisualTutorPolicyDecision(
            teaching_mode=VisualTutorTeachingMode.HINT,
            final_answer_locked=not reveal_final,
            partial_solution_allowed=True,
            full_solution_allowed=reveal_final,
            request_student_step=True,
            give_hint=True,
            reveal_final=reveal_final,
            reveal_partial=True,
            should_ask_question=True,
            use_khmer_explanation=use_khmer,
            explain_differently=True,
            stuck_help=stuck_help,
            input_relevance=input_relevance,
            validation_result=validation_result,
            misconception_type=misconception_type,
            reason="explain_differently",
            metadata=metadata,
        )

    return VisualTutorPolicyDecision(
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        request_student_step=True,
        should_ask_question=True,
        use_khmer_explanation=use_khmer,
        explain_differently=explain_differently,
        stuck_help=stuck_help,
        input_relevance=input_relevance,
        validation_result=validation_result,
        misconception_type=misconception_type,
        reason="ask_guiding_question_first",
        metadata=metadata,
    )


def _hint_count(request: VisualTutorTurnRequest) -> int:
    if request.hint_count is not None:
        return request.hint_count
    return request.current_state.hint_count


def _wrong_attempts(request: VisualTutorTurnRequest) -> int:
    return request.current_state.wrong_attempts


def _can_reveal_final(
    request: VisualTutorTurnRequest,
    *,
    wrong_attempts_override: Optional[int] = None,
    hint_count_override: Optional[int] = None,
) -> bool:
    wrong_attempts = (
        wrong_attempts_override
        if wrong_attempts_override is not None
        else _wrong_attempts(request)
    )
    return (
        request.allow_final_answer
        or request.current_state.final_answer_revealed
        or (
            hint_count_override
            if hint_count_override is not None
            else _hint_count(request)
        )
        >= FINAL_HINT_UNLOCK_THRESHOLD
        or wrong_attempts >= FINAL_WRONG_UNLOCK_THRESHOLD
    )


def _should_check_step(
    request: VisualTutorTurnRequest,
    *,
    input_relevance: Optional[VisualTutorInputRelevance] = None,
) -> bool:
    if (
        input_relevance is not None
        and input_relevance != VisualTutorInputRelevance.RELEVANT_STEP
    ):
        return False
    if (
        detect_visual_tutor_student_intent(request).intent
        == VisualTutorStudentIntent.STUCK
    ):
        return False
    if request.action == VisualTutorAction.SUBMIT_STEP:
        return True
    if (
        request.student_submitted_step is True
        or request.current_state.student_submitted_step
    ):
        return True
    if not request.current_state.problem_text:
        return False

    message = request.message.strip().lower()
    if not message:
        return False
    if re.search(r"\b(i tried|i try|my step|check|is this|i got|i did)\b", message):
        return True
    return bool(re.search(r"[-+*/^().\s\dxX]+=[-+*/^().\s\dxX]+", request.message))


def _should_redirect_input(
    input_relevance: Optional[VisualTutorInputRelevance],
) -> bool:
    return input_relevance in {
        VisualTutorInputRelevance.UNRELATED,
        VisualTutorInputRelevance.OFF_TOPIC,
        VisualTutorInputRelevance.UNKNOWN,
    }


def _should_use_khmer(request: VisualTutorTurnRequest) -> bool:
    locale = (request.locale or "").lower()
    if locale.startswith("km") or locale.startswith("kh"):
        return True

    message = request.message.lower()
    if "khmer" in message or "ភាសាខ្មែរ" in message:
        return True
    return bool(re.search(r"[\u1780-\u17ff]", request.message))
