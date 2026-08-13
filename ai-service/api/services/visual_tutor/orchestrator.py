from __future__ import annotations

import os
import re
import uuid
from typing import Any
from typing import Optional

from api.models.curriculum import CurriculumRetrievalRequest
from api.models.visual_tutor import (
    CanvasElementStyle,
    VisualTutorAllowedAction,
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorBehavior,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorInputRelevance,
    VisualTutorLessonState,
    VisualTutorMasterySignal,
    VisualTutorNextStudentAction,
    VisualTutorProblemUnderstandingRequest,
    VisualTutorScreenState,
    VisualTutorSolverFacts,
    VisualTutorSpeech,
    VisualTutorStageState,
    VisualTutorStudentIntent,
    VisualTutorTeachingStage,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
    VisualTutorVisualFocus,
)
from api.services.curriculum.curriculum_retriever import (
    curriculum_metadata,
    retrieve_curriculum_context,
)
from api.services.visual_tutor.adaptive_tutor_planner import (
    AdaptiveTutorDecision,
    VisualTutorAnswerLockDecision,
    VisualTutorMove,
    plan_adaptive_tutor_move,
)
from api.services.visual_tutor.input_understanding import (
    understand_visual_tutor_student_input,
)
from api.services.visual_tutor.llm_teaching_planner import (
    VisualTutorLLMClient,
    plan_visual_tutor_turn_with_llm,
)
from api.services.visual_tutor.intent import (
    detect_visual_tutor_student_intent,
    is_stuck_help_request,
)
from api.services.visual_tutor.policy import decide_visual_tutor_policy
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
)
from api.services.visual_tutor.response_sanitizer import (
    sanitize_visual_tutor_response,
)
from api.services.visual_tutor.teaching_stage_policy import (
    apply_live_teaching_stage_policy,
)
from api.services.visual_tutor.solver_registry import (
    DEFAULT_VISUAL_TUTOR_SOLVER_REGISTRY,
    VisualTutorSolverRegistry,
)
from api.services.visual_tutor.solvers import (
    LineThroughPoints,
    LinearEquation,
    attach_canvas_actions_to_solver_response,
    parse_line_through_points,
    parse_linear_equation,
)


class _ImmediateTemplateFallbackLLMClient:
    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        del system_prompt, user_prompt
        raise RuntimeError(
            "No LLM client supplied; using structured teaching fallback."
        )


def handle_visual_tutor_turn(
    request: VisualTutorTurnRequest,
    llm_client: Optional[VisualTutorLLMClient] = None,
    solver_registry: VisualTutorSolverRegistry = DEFAULT_VISUAL_TUTOR_SOLVER_REGISTRY,
) -> VisualTutorTurnResponse:
    session_id = request.session_id or str(uuid.uuid4())
    problem_message = _problem_message(request)
    if not problem_message:
        return _finalize_response(request, _greeting(request, session_id=session_id))

    understanding = understand_visual_tutor_problem(
        VisualTutorProblemUnderstandingRequest(
            subject=request.subject,
            topic=request.topic,
            message=problem_message,
            locale=request.locale,
            grade_level_hint=request.metadata.get("grade_level_hint"),
            metadata=request.metadata,
        )
    )
    input_understanding = None
    if _should_understand_student_input(request):
        input_understanding = understand_visual_tutor_student_input(
            request,
            understanding,
        )
    curriculum_result = retrieve_curriculum_context(
        CurriculumRetrievalRequest(
            grade=_grade_from_request(request),
            subject=understanding.subject or request.subject,
            topic=understanding.topic or request.topic,
            problem_type=understanding.problem_type,
            message=problem_message,
            language=understanding.language,
            max_results=3,
            metadata={
                "session_id": request.session_id,
                "visual_tutor": True,
            },
        )
    )
    curriculum_meta = curriculum_metadata(curriculum_result)
    solver = solver_registry.get_solver(understanding)
    preliminary_policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        problem_type=understanding.problem_type,
        known_solver_available=understanding.known_solver_available,
        input_understanding=input_understanding,
    )
    solver_facts = _solver_facts(
        solver=solver,
        request=request,
        understanding=understanding,
        policy=preliminary_policy,
    )
    is_correct_step_fact = (
        solver_facts.student_validation.is_correct
        if solver_facts and getattr(solver_facts, "student_validation", None)
        else None
    )
    policy = decide_visual_tutor_policy(
        request,
        has_problem=True,
        is_correct_step=is_correct_step_fact,
        problem_type=understanding.problem_type,
        known_solver_available=understanding.known_solver_available,
        input_understanding=input_understanding,
    )
    policy.metadata.update(curriculum_meta)
    if solver_facts is not None:
        policy.metadata["solver_facts"] = solver_facts.model_dump(mode="json")
    policy.metadata["orchestrator_flow"] = [
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

    is_new_problem = (
        request.action == VisualTutorAction.GENERATE_PRACTICE
        or (
            request.action == VisualTutorAction.SUBMIT_PROBLEM
            and request.student_intent == VisualTutorStudentIntent.NEW_PROBLEM
        )
        or (
            request.action == VisualTutorAction.SUBMIT_PROBLEM
            and request.metadata.get("client_intent_hint") == "new_problem"
        )
        or (
            input_understanding
            and input_understanding.input_relevance
            == VisualTutorInputRelevance.NEW_PROBLEM
        )
    )

    if is_new_problem:
        new_problem_request = request.model_copy(
            update={
                "action": VisualTutorAction.SUBMIT_PROBLEM,
                # The new-problem reset has already happened.  Leaving the
                # intent set here re-enters this branch forever for an
                # unsupported prompt.
                "student_intent": None,
                "current_state": request.current_state.model_copy(
                    update={
                        "problem_text": None,
                        "normalized_problem": None,
                        "current_step_index": 0,
                        "hint_count": 0,
                        "wrong_attempts": 0,
                        "final_answer_revealed": False,
                        "student_submitted_step": False,
                    }
                ),
            }
        )
        return handle_visual_tutor_turn(
            new_problem_request,
            llm_client=llm_client,
            solver_registry=solver_registry,
        )

    response = _planner_first_turn(
        request=request,
        understanding=understanding,
        input_understanding=input_understanding,
        solver=solver,
        policy=policy,
        solver_facts=solver_facts,
        curriculum_meta=curriculum_meta,
        session_id=session_id,
        llm_client=llm_client,
    )
    return _finalize_response(
        request,
        _enforce_requested_teaching_mode(
            _sanitize_response(response, policy),
            request=request,
            policy=policy,
        ),
        policy=policy,
        understanding=understanding,
        input_understanding=input_understanding,
        curriculum_meta=curriculum_meta,
    )


def _sanitize_response(
    response: VisualTutorTurnResponse,
    policy,
) -> VisualTutorTurnResponse:
    return sanitize_visual_tutor_response(
        attach_canvas_actions_to_solver_response(response),
        policy=policy,
    )


def _planner_first_turn(
    *,
    request: VisualTutorTurnRequest,
    understanding,
    input_understanding,
    solver,
    policy,
    solver_facts: Optional[VisualTutorSolverFacts],
    curriculum_meta: Optional[dict[str, Any]],
    session_id: str,
    llm_client: Optional[VisualTutorLLMClient],
) -> VisualTutorTurnResponse:
    student_intent = (
        input_understanding.student_intent
        if input_understanding is not None
        else detect_visual_tutor_student_intent(request).intent
    )
    adaptive_decision = plan_adaptive_tutor_move(
        problem_understanding=understanding,
        student_input_understanding=input_understanding,
        teaching_board_state=None,
        lesson_state=None,
        current_step_index=request.current_state.current_step_index,
        wrong_attempts=request.current_state.wrong_attempts,
        stuck_count=int(request.metadata.get("stuck_count") or 0),
        hint_count=(
            request.hint_count
            if request.hint_count is not None
            else request.current_state.hint_count
        ),
        student_intent=student_intent,
        curriculum_context=(
            curriculum_meta.get("curriculum_context") if curriculum_meta else None
        ),
        solver_facts=solver_facts,
        allow_final_answer=request.allow_final_answer or policy.full_solution_allowed,
        student_model=_student_model_from_request(request),
        strategy_history=_strategy_history_from_request(request),
    )
    policy.metadata.update(
        {
            "student_intent": student_intent.value,
            "adaptive_tutor_decision": adaptive_decision.metadata,
            "tutor_move": adaptive_decision.tutor_move.value,
            "answer_lock_decision": adaptive_decision.answer_lock_decision.value,
            "planner_inputs": _planner_inputs_metadata(
                request=request,
                input_understanding=input_understanding,
                solver_facts=solver_facts,
                curriculum_meta=curriculum_meta,
                adaptive_decision=adaptive_decision,
            ),
            "student_model": _student_model_from_request(request),
            "strategy_history": _strategy_history_from_request(request),
        }
    )

    # An unsupported or ambiguous math prompt must never be handed to a
    # free-form planner that could invent mathematics. Graph requests are the
    # one deliberate visual fallback, handled immediately below with explicit
    # graph payloads rather than generated UI/code.
    if (
        solver is None
        and (understanding.problem_type or "").lower() == "unsupported"
        and not _should_return_graph_board(request.message, understanding)
        # "Solve a + b = 10 for a" is an explicit symbolic rearrangement,
        # rather than an ambiguous unsupported domain. Existing constrained
        # planner handling can teach that relationship without claiming a
        # numeric verified answer.
        and not _is_explicit_symbolic_rearrangement(
            request.current_state.problem_text or request.message
        )
    ):
        return _mark_adaptive_generation_metadata(
            _friendly_unsupported_turn(
                request,
                understanding=understanding,
                policy=policy,
                session_id=session_id,
            ),
            adaptive_decision=adaptive_decision,
            generation_path="template_fallback",
            fallback_reason="friendly_unsupported_screen",
        )

    if solver is None and _should_return_graph_board(request.message, understanding):
        return _mark_adaptive_generation_metadata(
            _graph_based_function_turn(
                request,
                understanding=understanding,
                policy=policy,
                session_id=session_id,
            ),
            adaptive_decision=adaptive_decision,
            generation_path="template_fallback",
            fallback_reason="graph_based_visual_guidance",
        )

    # A registered solver is the source of truth for supported mathematics.  Do
    # not replace its verified steps with an LLM completion just because a model
    # happens to be configured.
    if solver is not None:
        return _mark_adaptive_generation_metadata(
            _deterministic_template_turn_for_move(
                request=request,
                understanding=understanding,
                solver=solver,
                policy=policy,
                session_id=session_id,
                adaptive_decision=adaptive_decision,
            ),
            adaptive_decision=adaptive_decision,
            generation_path="deterministic_solver",
            fallback_reason=None,
        )

    llm_response = plan_visual_tutor_turn_with_llm(
        request=request,
        understanding=understanding,
        policy=policy,
        session_id=session_id,
        student_model=policy.metadata.get("student_model")
        or request.metadata.get("student_model"),
        strategy_history=policy.metadata.get("strategy_history")
        or _strategy_history_from_request(request),
        llm_client=_configured_or_fallback_llm_client(llm_client),
    )
    llm_response = _enforce_requested_teaching_mode(
        llm_response,
        request=request,
        policy=policy,
    )
    if llm_response.metadata.get("planner_fallback") is not True:
        return _mark_adaptive_generation_metadata(
            llm_response,
            adaptive_decision=adaptive_decision,
            generation_path="llm_main",
            fallback_reason=None,
        )
    if solver is None:
        return _mark_adaptive_generation_metadata(
            llm_response,
            adaptive_decision=adaptive_decision,
            generation_path="template_fallback",
            fallback_reason=llm_response.metadata.get("planner_error")
            or "llm_unavailable",
        )

    fallback = _deterministic_template_turn_for_move(
        request=request,
        understanding=understanding,
        solver=solver,
        policy=policy,
        session_id=session_id,
        adaptive_decision=adaptive_decision,
    )
    return _mark_adaptive_generation_metadata(
        fallback,
        adaptive_decision=adaptive_decision,
        generation_path="deterministic_template_fallback",
        fallback_reason=llm_response.metadata.get("planner_error") or "llm_unavailable",
    )


def _enforce_requested_teaching_mode(
    response: VisualTutorTurnResponse,
    *,
    request: VisualTutorTurnRequest,
    policy,
) -> VisualTutorTurnResponse:
    """Keep the LLM inside the student-action policy for recovery turns.

    The planner may choose wording and a safe board representation, but it
    cannot turn an explicit hint or stuck request into a generic first lesson.
    That would repeat the same step and make progressive help unreliable.
    """
    if request.action not in {
        VisualTutorAction.REQUEST_HINT,
        VisualTutorAction.REQUEST_STUCK_HELP,
    } and not policy.stuck_help:
        return response
    if response.teaching_mode == policy.teaching_mode:
        return response
    return response.model_copy(
        update={
            "teaching_mode": policy.teaching_mode,
            "metadata": {
                **response.metadata,
                "planner_teaching_mode": response.teaching_mode.value,
                "teaching_mode_policy_enforced": True,
            },
        }
    )


def _configured_or_fallback_llm_client(
    llm_client: Optional[VisualTutorLLMClient],
) -> Optional[VisualTutorLLMClient]:
    if llm_client is not None:
        return llm_client
    provider = os.getenv("VISUAL_TUTOR_LLM_PROVIDER", "auto").strip().lower()
    if provider in {
        "codex",
        "codex_cli",
        "codex_bridge",
        "codex_cli_bridge",
        "codex_http",
        "ollama",
    }:
        return None
    if provider == "openrouter" and os.getenv("OPENROUTER_API_KEY", "").strip():
        return None
    if provider == "auto" and os.getenv("OPENROUTER_API_KEY", "").strip():
        return None
    return _ImmediateTemplateFallbackLLMClient()


def _deterministic_template_turn_for_move(
    *,
    request: VisualTutorTurnRequest,
    understanding,
    solver,
    policy,
    session_id: str,
    adaptive_decision: AdaptiveTutorDecision,
) -> VisualTutorTurnResponse:
    if solver is None:
        if _should_return_friendly_unsupported(request.message, understanding):
            return _friendly_unsupported_turn(
                request,
                understanding=understanding,
                policy=policy,
                session_id=session_id,
            )
        if _should_return_graph_board(request.message, understanding):
            return _graph_based_function_turn(
                request,
                understanding=understanding,
                policy=policy,
                session_id=session_id,
            )
        return plan_visual_tutor_turn_with_llm(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            student_model=policy.metadata.get("student_model")
            or _student_model_from_request(request),
            strategy_history=policy.metadata.get("strategy_history")
            or _strategy_history_from_request(request),
            llm_client=_ImmediateTemplateFallbackLLMClient(),
        )

    move = adaptive_decision.tutor_move
    if move == VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY or (
        policy.full_solution_allowed
        and policy.reveal_final
        and policy.reason == "final_answer_requested"
    ):
        return solver.build_full_solution(
            request,
            understanding,
            policy,
            session_id=session_id,
        )
    if move == VisualTutorMove.REVEAL_PARTIAL_SOLUTION:
        if (
            request.action == VisualTutorAction.SUBMIT_STEP
            and adaptive_decision.metadata.get("reason")
            == "repeated_wrong_relevant_steps_unlock_partial_solution"
        ):
            response = solver.check_student_step(
                request,
                understanding,
                policy,
                session_id=session_id,
            )
        else:
            response = solver.build_partial_solution(
                request,
                understanding,
                policy,
                session_id=session_id,
            )
        if (
            adaptive_decision.metadata.get("reason")
            == "repeated_wrong_relevant_steps_unlock_partial_solution"
        ):
            response = response.model_copy(
                update={
                    "mastery_signal": VisualTutorMasterySignal.MISCONCEPTION,
                    "metadata": {
                        **response.metadata,
                        "mastery_signal_adjusted_for_wrong_attempt": True,
                    },
                }
            )
        return response

    if request.action == VisualTutorAction.REQUEST_FINAL_ANSWER:
        if policy.full_solution_allowed:
            return solver.build_full_solution(
                request, understanding, policy, session_id=session_id
            )
        if hasattr(solver, "build_final_locked_turn"):
            solver_visual_response = solver.build_final_locked_turn(  # type: ignore[attr-defined]
                request, understanding, policy, session_id=session_id
            )
        else:
            solver_visual_response = solver.build_initial_turn(
                request, understanding, policy, session_id=session_id
            )
        return _template_turn_with_solver_visuals(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            solver_visual_response=solver_visual_response,
        )

    if (
        request.action == VisualTutorAction.REQUEST_HINT
        or move == VisualTutorMove.SHOW_VISUAL_HINT
    ):
        return _template_turn_with_solver_visuals(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            solver_visual_response=solver.build_hint_turn(
                request, understanding, policy, session_id=session_id
            ),
        )

    if policy.stuck_help or move == VisualTutorMove.GIVE_INSTANT_HELP:
        return _template_turn_with_solver_visuals(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            solver_visual_response=solver.build_stuck_help_turn(
                request, understanding, policy, session_id=session_id
            ),
        )

    if (
        policy.should_redirect_input
        or (
            policy.possible_final_answer
            and not policy.full_solution_allowed
            and request.action != VisualTutorAction.SUBMIT_STEP
        )
        or move == VisualTutorMove.DIAGNOSE_WRONG_INPUT
    ):
        solver_visual_response = solver.build_wrong_input_feedback(
            request, understanding, policy, session_id=session_id
        )
        if not solver_visual_response.board_actions:
            solver_visual_response = _input_validation_turn(
                request,
                policy=policy,
                session_id=session_id,
                fallback_board=solver.build_hint_turn(
                    request, understanding, policy, session_id=session_id
                ).board,
            )
        return _template_turn_with_solver_visuals(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            solver_visual_response=solver_visual_response,
        )

    if (
        request.action == VisualTutorAction.SUBMIT_STEP
        or move == VisualTutorMove.CHECK_STUDENT_ANSWER
        or policy.should_check_step
    ):
        return _template_turn_with_solver_visuals(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            solver_visual_response=solver.check_student_step(
                request, understanding, policy, session_id=session_id
            ),
        )

    if policy.possible_final_answer and policy.full_solution_allowed:
        return solver.build_full_solution(
            request, understanding, policy, session_id=session_id
        )

    if (
        request.action == VisualTutorAction.EXPLAIN_DIFFERENTLY
        or move == VisualTutorMove.RETEACH_DIFFERENTLY
    ) and hasattr(solver, "build_explain_differently_turn"):
        return _template_turn_with_solver_visuals(
            request=request,
            understanding=understanding,
            policy=policy,
            session_id=session_id,
            solver_visual_response=solver.build_explain_differently_turn(  # type: ignore[attr-defined]
                request, understanding, policy, session_id=session_id
            ),
        )

    return _template_turn_with_solver_visuals(
        request=request,
        understanding=understanding,
        policy=policy,
        session_id=session_id,
        solver_visual_response=solver.build_initial_turn(
            request, understanding, policy, session_id=session_id
        ),
    )


def _template_turn_with_solver_visuals(
    *,
    request: VisualTutorTurnRequest,
    understanding,
    policy,
    session_id: str,
    solver_visual_response: VisualTutorTurnResponse,
) -> VisualTutorTurnResponse:
    template_response = plan_visual_tutor_turn_with_llm(
        request=request,
        understanding=understanding,
        policy=policy,
        session_id=session_id,
        student_model=policy.metadata.get("student_model")
        or _student_model_from_request(request),
        strategy_history=policy.metadata.get("strategy_history")
        or _strategy_history_from_request(request),
        llm_client=_ImmediateTemplateFallbackLLMClient(),
    )
    template_response = _adapt_template_text_to_solver_visual_state(
        template_response,
        solver_visual_response=solver_visual_response,
        request=request,
    )
    solver_visual_response = attach_canvas_actions_to_solver_response(
        solver_visual_response
    )
    board_actions = (
        solver_visual_response.board_actions
        if solver_visual_response.board_actions
        else template_response.board_actions
    )
    canvas_actions = (
        solver_visual_response.canvas_actions
        if solver_visual_response.canvas_actions
        else template_response.canvas_actions
    )
    teaching_board = (
        solver_visual_response.teaching_board
        if solver_visual_response.teaching_board is not None
        else template_response.teaching_board
    )
    teaching_mode = solver_visual_response.teaching_mode
    if policy.teaching_mode == VisualTutorTeachingMode.GREETING and policy.reason in {
        "new_problem_greeting",
        "ask_guiding_question_first",
    }:
        teaching_mode = VisualTutorTeachingMode.GUIDED_QUESTION
    return template_response.model_copy(
        update={
            "teaching_mode": teaching_mode,
            "final_answer_locked": solver_visual_response.final_answer_locked,
            "mastery_signal": solver_visual_response.mastery_signal,
            "board": solver_visual_response.board,
            "board_actions": board_actions,
            "canvas_actions": canvas_actions,
            "teaching_board": teaching_board,
            "allowed_actions": (
                solver_visual_response.allowed_actions
                or template_response.allowed_actions
            ),
            "quick_actions": (
                solver_visual_response.quick_actions or template_response.quick_actions
            ),
            "metadata": {
                **template_response.metadata,
                **{
                    key: value
                    for key, value in solver_visual_response.metadata.items()
                    if key
                    not in {
                        "spoken_text",
                        "display_text",
                        "student_task",
                        "speech",
                    }
                },
                "solver_speech_bypassed": True,
                "solver_visuals_used": bool(board_actions or canvas_actions),
                "solver_board_metadata": solver_visual_response.board.metadata,
                "validation_result": solver_visual_response.metadata.get(
                    "validation_result",
                    template_response.metadata.get("validation_result"),
                ),
                "input_relevance": solver_visual_response.metadata.get(
                    "input_relevance",
                    template_response.metadata.get("input_relevance"),
                ),
                "misconception_type": solver_visual_response.metadata.get(
                    "misconception_type",
                    template_response.metadata.get("misconception_type"),
                ),
                "mistake_category": solver_visual_response.metadata.get(
                    "mistake_category",
                    template_response.metadata.get("mistake_category"),
                ),
                "expected_step": solver_visual_response.metadata.get(
                    "expected_step",
                    template_response.metadata.get("expected_step"),
                ),
            },
        }
    )


def _adapt_template_text_to_solver_visual_state(
    response: VisualTutorTurnResponse,
    *,
    solver_visual_response: VisualTutorTurnResponse,
    request: VisualTutorTurnRequest,
) -> VisualTutorTurnResponse:
    board_metadata = solver_visual_response.board.metadata
    validation_result = str(
        solver_visual_response.metadata.get("validation_result")
        or board_metadata.get("feedback")
        or ""
    )
    problem_type = str(board_metadata.get("problem_type") or "")
    if (
        problem_type == "linear_equation_one_variable"
        and validation_result == "correct_step"
    ):
        first_step = _board_item_content(solver_visual_response, "Step 1")
        coefficient = str(board_metadata.get("coefficient") or "").strip()
        variable = _linear_variable_from_step(first_step)
        spoken_text = (
            f"Yes. That gives {first_step}. Now undo the {coefficient} beside {variable}."
            if coefficient and first_step
            else "Yes. That first step is right. Now isolate the variable."
        )
        display_text = (
            f"{first_step}. Next, use the inverse operation on {coefficient}{variable}."
            if coefficient and first_step
            else "Correct first step. Now isolate the variable."
        )
        student_task = (
            f"What operation should we apply to both sides of {first_step}?"
            if first_step
            else "What operation isolates the variable?"
        )
        return response.model_copy(
            update={
                "spoken_text": spoken_text,
                "display_text": display_text,
                "student_task": student_task,
                "speech": (
                    response.speech.model_copy(update={"text": spoken_text})
                    if response.speech is not None
                    else None
                ),
                "interaction": (
                    response.interaction.model_copy(update={"prompt": student_task})
                    if response.interaction is not None
                    else None
                ),
            }
        )
    if problem_type == "linear_equation_one_variable" and validation_result in {
        "correct_final_step",
        "final_verified_answer",
    }:
        final_answer = _board_item_content(solver_visual_response, "Final")
        problem = _board_item_content(solver_visual_response, "Problem")
        spoken_text = (
            f"Correct. {final_answer} checks in the original equation."
            if final_answer
            else "Correct. Your final step checks in the original equation."
        )
        display_text = (
            f"{final_answer} is verified from {problem}."
            if final_answer and problem
            else "Your answer is verified."
        )
        student_task = "Do you want a quick summary or a similar practice problem?"
        return response.model_copy(
            update={
                "screen_state": VisualTutorScreenState.FINAL_VERIFIED_ANSWER,
                "tutor_status": "Verified",
                "spoken_text": spoken_text,
                "display_text": display_text,
                "student_task": student_task,
                "speech": (
                    response.speech.model_copy(update={"text": spoken_text})
                    if response.speech is not None
                    else None
                ),
                "interaction": (
                    response.interaction.model_copy(
                        update={
                            "type": VisualTutorInteractionType.YES_NO,
                            "prompt": student_task,
                            "input_enabled": True,
                        }
                    )
                    if response.interaction is not None
                    else None
                ),
            }
        )
    return response


def _board_item_content(
    response: VisualTutorTurnResponse,
    label: str,
) -> str:
    for item in response.board.items:
        if item.label.strip().lower() == label.strip().lower():
            return item.content
    return ""


def _linear_variable_from_step(step: str) -> str:
    match = re.search(r"\b([a-zA-Z])\b", step)
    return match.group(1) if match else "x"


def _mark_adaptive_generation_metadata(
    response: VisualTutorTurnResponse,
    *,
    adaptive_decision: AdaptiveTutorDecision,
    generation_path: str,
    fallback_reason: Optional[str],
) -> VisualTutorTurnResponse:
    metadata = {
        **response.metadata,
        "adaptive_planner_generated_response": True,
        "adaptive_tutor_decision": adaptive_decision.metadata,
        "tutor_move": adaptive_decision.tutor_move.value,
        "answer_lock_decision": adaptive_decision.answer_lock_decision.value,
        "generation_path": generation_path,
        "planner_output": {
            "screen_state": adaptive_decision.screen_state.value,
            "tutor_status": adaptive_decision.tutor_status,
            "stage_state": adaptive_decision.stage_state.value,
            "lesson_state": adaptive_decision.lesson_state.value,
            "interaction_type": adaptive_decision.interaction_type.value,
            "quick_actions": [
                action.value for action in adaptive_decision.quick_actions
            ],
            "final_answer_locked": adaptive_decision.final_answer_locked,
        },
    }
    if generation_path == "deterministic_template_fallback":
        metadata["planner_fallback"] = True
        metadata["fallback_reason"] = fallback_reason or "llm_unavailable"
        metadata["solver_speech_bypassed"] = True
    return response.model_copy(update={"metadata": metadata})


def _build_board_patch(
    *,
    response: VisualTutorTurnResponse,
    request: VisualTutorTurnRequest,
    adaptive_decision: AdaptiveTutorDecision,
) -> VisualTutorTurnResponse:
    raw_played_action_ids = request.metadata.get("played_action_ids") or []
    raw_previous_board_action_ids = (
        request.metadata.get("previous_board_action_ids") or []
    )
    played_action_ids: list[str] = (
        [action_id for action_id in raw_played_action_ids if isinstance(action_id, str)]
        if isinstance(raw_played_action_ids, list)
        else []
    )
    previous_board_action_ids: list[str] = (
        [
            action_id
            for action_id in raw_previous_board_action_ids
            if isinstance(action_id, str)
        ]
        if isinstance(raw_previous_board_action_ids, list)
        else []
    )
    current_step_index: int = request.current_state.current_step_index
    current_turn_id = response.turn_id

    def with_mode(
        mode: str,
        *,
        patch_generated: bool,
        patch_actions: Optional[list[VisualTutorBoardAction]] = None,
        errors: Optional[list[str]] = None,
    ) -> VisualTutorTurnResponse:
        metadata = {
            **response.metadata,
            "board_update_mode": mode,
            "patch_generated": patch_generated,
            "patch_ops": [
                {
                    "id": action.id,
                    "op": action.metadata.get("patch_op"),
                    "target_id": action.target_id,
                    "reason": action.metadata.get("reason"),
                }
                for action in (patch_actions or [])
            ],
        }
        if errors:
            metadata["board_patch_errors"] = errors
        return response.model_copy(
            update={
                "board_actions": [
                    *(patch_actions or []),
                    *response.board_actions,
                ],
                "metadata": metadata,
            }
        )

    if (
        current_step_index == 0
        or request.action == VisualTutorAction.SUBMIT_PROBLEM
        or not response.final_answer_locked
    ):
        return with_mode("replace", patch_generated=False)

    tutor_move = adaptive_decision.tutor_move
    patch_actions: list[VisualTutorBoardAction] = []
    errors: list[str] = []
    if tutor_move == VisualTutorMove.CHECK_STUDENT_ANSWER:
        if not played_action_ids or not previous_board_action_ids:
            return with_mode("replace", patch_generated=False)
        try:
            patch_actions.append(
                VisualTutorBoardAction(
                    id=f"patch-highlight-{uuid.uuid4().hex[:8]}",
                    type=VisualTutorCanvasActionType.HIGHLIGHT,
                    target_id=previous_board_action_ids[-1],
                    sequence_index=0,
                    duration_ms=250,
                    metadata={
                        "patch_op": "highlight",
                        "reason": "check_student_answer",
                        "created_from_turn_id": current_turn_id,
                    },
                )
            )
        except Exception as exc:
            errors.append(str(exc))
    elif tutor_move == VisualTutorMove.SHOW_VISUAL_HINT:
        if not played_action_ids or not previous_board_action_ids:
            return with_mode("replace", patch_generated=False)
        for action_id in previous_board_action_ids[-2:]:
            try:
                patch_actions.append(
                    VisualTutorBoardAction(
                        id=f"patch-fade-{uuid.uuid4().hex[:8]}",
                        type=VisualTutorCanvasActionType.FADE_PREVIOUS,
                        target_id=action_id,
                        sequence_index=0,
                        duration_ms=180,
                        metadata={
                            "patch_op": "fade",
                            "reason": "visual_hint_transition",
                            "created_from_turn_id": current_turn_id,
                        },
                    )
                )
            except Exception as exc:
                errors.append(str(exc))
    elif tutor_move == VisualTutorMove.RETEACH_DIFFERENTLY:
        if not played_action_ids:
            return with_mode("replace", patch_generated=False)
        for action_id in played_action_ids[-5:]:
            try:
                patch_actions.append(
                    VisualTutorBoardAction(
                        id=f"patch-fade-{uuid.uuid4().hex[:8]}",
                        type=VisualTutorCanvasActionType.FADE_PREVIOUS,
                        target_id=action_id,
                        sequence_index=0,
                        duration_ms=150,
                        metadata={
                            "patch_op": "fade",
                            "reason": "reteach_differently",
                            "created_from_turn_id": current_turn_id,
                        },
                    )
                )
            except Exception as exc:
                errors.append(str(exc))
    else:
        return with_mode("replace", patch_generated=False)

    if not patch_actions:
        return with_mode("replace", patch_generated=False, errors=errors)
    return with_mode(
        "patch",
        patch_generated=True,
        patch_actions=patch_actions,
        errors=errors,
    )


def _planner_inputs_metadata(
    *,
    request: VisualTutorTurnRequest,
    input_understanding,
    solver_facts: Optional[VisualTutorSolverFacts],
    curriculum_meta: Optional[dict[str, Any]],
    adaptive_decision: AdaptiveTutorDecision,
) -> dict[str, Any]:
    current_state_payload = request.current_state.model_dump(mode="json")
    return {
        "problem_understanding_available": True,
        "student_input_understanding": (
            input_understanding.model_dump(mode="json")
            if input_understanding is not None
            else None
        ),
        "solver_facts": (
            solver_facts.model_dump(mode="json") if solver_facts is not None else None
        ),
        "curriculum_context": (
            curriculum_meta.get("curriculum_context") if curriculum_meta else None
        ),
        "session_state": current_state_payload,
        "previous_turns": request.metadata.get("previous_turns")
        or current_state_payload.get("previous_turns")
        or [],
        "board_state": request.metadata.get("board_state")
        or current_state_payload.get("board_state"),
        "student_model": _student_model_from_request(request),
        "strategy_history": _strategy_history_from_request(request),
        "hint_count": (
            request.hint_count
            if request.hint_count is not None
            else request.current_state.hint_count
        ),
        "wrong_attempts": request.current_state.wrong_attempts,
        "stuck_count": int(request.metadata.get("stuck_count") or 0),
        "allow_final_answer": request.allow_final_answer,
        "policy_decision": {
            "reason": adaptive_decision.metadata.get("reason"),
            "answer_lock_decision": adaptive_decision.answer_lock_decision.value,
            "tutor_move": adaptive_decision.tutor_move.value,
        },
    }


def _student_model_from_request(
    request: VisualTutorTurnRequest,
) -> Optional[dict[str, Any]]:
    student_model = request.metadata.get("student_model")
    if isinstance(student_model, dict):
        return student_model
    return None


def _strategy_history_from_request(
    request: VisualTutorTurnRequest,
) -> list[dict[str, Any]]:
    strategy_history = request.metadata.get("strategy_history")
    if not isinstance(strategy_history, list):
        student_model = _student_model_from_request(request)
        metadata = (
            student_model.get("metadata")
            if isinstance(student_model, dict)
            and isinstance(student_model.get("metadata"), dict)
            else {}
        )
        strategy_history = metadata.get("strategy_history")
    if not isinstance(strategy_history, list):
        return []
    return [entry for entry in strategy_history[-12:] if isinstance(entry, dict)]


def _finalize_response(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    *,
    policy=None,
    understanding=None,
    input_understanding=None,
    curriculum_meta: Optional[dict] = None,
) -> VisualTutorTurnResponse:
    intent_detection = detect_visual_tutor_student_intent(request)
    student_intent = (
        input_understanding.student_intent
        if input_understanding
        else intent_detection.intent
    )
    metadata = {
        **response.metadata,
        "detected_intent": student_intent.value,
        "student_intent": student_intent.value,
    }
    if understanding and "problem_understanding" not in metadata:
        metadata["problem_understanding"] = understanding.model_dump(mode="json")
    if input_understanding:
        input_payload = input_understanding.model_dump(mode="json")
        metadata.update(
            {
                "input_understanding": input_payload,
                "input_relevance": input_payload["input_relevance"],
                "expected_step": input_understanding.metadata.get("expected_step"),
                "validation_result": input_understanding.metadata.get(
                    "validation_result"
                ),
                "misconception_type": input_understanding.metadata.get(
                    "misconception_type"
                ),
                "redirect_reason": response.metadata.get(
                    "redirect_reason",
                    input_understanding.metadata.get("redirect_reason"),
                ),
            }
        )
    if curriculum_meta:
        metadata.update(curriculum_meta)
    if policy is not None and policy.metadata.get("orchestrator_flow"):
        metadata["orchestrator_flow"] = policy.metadata["orchestrator_flow"]
    solver_facts = _solver_facts_from_policy(policy)
    if solver_facts is not None:
        metadata["solver_facts"] = solver_facts.model_dump(mode="json")
    if intent_detection.intent.value == "stuck":
        metadata["stuck_reason"] = intent_detection.reason
    elif "stuck_reason" not in metadata:
        metadata["stuck_reason"] = None
    enriched_response = _apply_curriculum_context_to_response(
        response,
        curriculum_meta=curriculum_meta,
        use_khmer=_uses_khmer(request, metadata),
    )
    if policy is not None:
        enriched_response = apply_live_teaching_stage_policy(
            request,
            enriched_response,
            policy,
            input_understanding=input_understanding,
        )
    adaptive_decision = None
    if understanding is not None and policy is not None:
        adaptive_decision = plan_adaptive_tutor_move(
            problem_understanding=understanding,
            student_input_understanding=input_understanding,
            teaching_board_state=enriched_response.teaching_board,
            lesson_state=(
                enriched_response.teaching_stage.lesson_state
                if enriched_response.teaching_stage
                else None
            ),
            current_step_index=request.current_state.current_step_index,
            wrong_attempts=request.current_state.wrong_attempts,
            stuck_count=int(request.metadata.get("stuck_count") or 0),
            hint_count=(
                request.hint_count
                if request.hint_count is not None
                else request.current_state.hint_count
            ),
            student_intent=student_intent,
            curriculum_context=(
                curriculum_meta.get("curriculum_context") if curriculum_meta else None
            ),
            solver_facts=solver_facts,
            allow_final_answer=request.allow_final_answer
            or policy.full_solution_allowed,
            student_model=_student_model_from_request(request),
            strategy_history=_strategy_history_from_request(request),
        )
        enriched_response = _apply_adaptive_tutor_decision(
            enriched_response,
            adaptive_decision,
        )
        enriched_response = _enrich_final_verified_board(
            enriched_response,
            solver_facts=solver_facts,
        )
        enriched_response = _build_board_patch(
            response=enriched_response,
            request=request,
            adaptive_decision=adaptive_decision,
        )
    enriched_response = _enforce_teaching_turn_contract(enriched_response)
    screen_state = _resolve_screen_state(request, enriched_response)
    tutor_status = _resolve_tutor_status(screen_state, enriched_response)
    speech = enriched_response.speech or VisualTutorSpeech(
        text=enriched_response.spoken_text,
        language="km" if _uses_khmer(request, metadata) else "en",
    )
    interaction = enriched_response.interaction or VisualTutorInteraction(
        type=VisualTutorInteractionType.TEXT_RESPONSE,
        prompt=enriched_response.student_task,
        input_enabled=True,
        submit_label="Submit",
        expected_answer_locked=enriched_response.final_answer_locked,
    )
    quick_actions = (
        enriched_response.quick_actions
        or enriched_response.allowed_actions
        or [
            VisualTutorAllowedAction.SUBMIT_ANSWER,
            VisualTutorAllowedAction.REQUEST_HINT,
        ]
    )
    response_metadata = {
        **metadata,
        **enriched_response.metadata,
        "screen_state": screen_state.value,
        "tutor_status": tutor_status,
        "quick_actions": [action.value for action in quick_actions],
    }
    if policy is not None:
        # Preserve the original controlled policy alongside planner metadata so
        # a resumed hint/stuck turn remains auditable and cannot appear as an
        # unscoped generic response to the client.
        response_metadata.setdefault("policy", policy.metadata)
    if adaptive_decision is not None:
        response_metadata["adaptive_tutor_decision"] = adaptive_decision.metadata
        response_metadata["tutor_move"] = adaptive_decision.tutor_move.value
        response_metadata["answer_lock_decision"] = (
            adaptive_decision.answer_lock_decision.value
        )
    if request.action == VisualTutorAction.SUBMIT_STEP:
        problem = request.current_state.problem_text or request.metadata.get("problem_text")
        if isinstance(problem, str) and problem.strip():
            # Import at the execution boundary to avoid coupling the core
            # teaching service to FastAPI route-package initialisation. The
            # verifier itself is deterministic; this is not an HTTP call.
            from api.routes.math_verifier import verify_student_work

            verification = verify_student_work(
                problem=problem,
                student_step=request.message,
                expected_step=response_metadata.get("expected_step"),
            )
            verification_contract = verification.model_dump(mode="json")
            response_metadata["verification"] = verification_contract
            response_metadata["verification_result"] = verification.status
            response_metadata["verification_evidence"] = verification.evidence
            response_metadata["verification_verified"] = verification.verified
    response_metadata.update(
        _debug_metadata(
            request=request,
            response=enriched_response,
            metadata={
                **response_metadata,
                "student_model": (
                    response_metadata.get("student_model")
                    or request.metadata.get("student_model")
                ),
                "strategy_history": (
                    response_metadata.get("strategy_history")
                    or _strategy_history_from_request(request)
                ),
            },
            policy=policy,
            understanding=understanding,
            input_understanding=input_understanding,
            adaptive_decision=adaptive_decision,
        )
    )
    # This is the stable teaching-loop contract consumed by the mobile board.
    # It deliberately contains policy/state, never executable UI code.
    response_metadata["teaching_loop"] = {
        "schema_version": 1,
        "representation": _representation_for_response(enriched_response),
        "one_student_task": True,
        "active_student_task_id": response_metadata.get("active_student_task_id"),
        "next_state": (
            enriched_response.teaching_stage.lesson_state.value
            if enriched_response.teaching_stage is not None
            else "ask"
        ),
        "final_answer_locked": enriched_response.final_answer_locked,
        "final_answer_policy": (
            "hidden" if enriched_response.final_answer_locked else "progressively_revealed"
        ),
        "verification": response_metadata.get("verification_result"),
    }
    return enriched_response.model_copy(
        update={
            "student_intent": student_intent,
            "screen_state": screen_state,
            "tutor_status": tutor_status,
            "speech": speech,
            "interaction": interaction,
            "quick_actions": quick_actions,
            "metadata": response_metadata,
        }
    )


def _representation_for_response(response: VisualTutorTurnResponse) -> str:
    decision = response.metadata.get("adaptive_tutor_decision")
    if isinstance(decision, dict) and isinstance(decision.get("representation"), str):
        return decision["representation"]
    action_types = {action.type.value for action in response.board_actions}
    if {"show_graph", "plot_function", "draw_axes"} & action_types:
        return "coordinate_graph"
    if "show_number_line" in action_types:
        return "number_line"
    if "transform_equation" in action_types or response.board.type.value in {"equation", "equation_steps"}:
        return "equation_transformation"
    return "guided_text_visual"


def _enforce_teaching_turn_contract(
    response: VisualTutorTurnResponse,
) -> VisualTutorTurnResponse:
    """Keep one explicit task active, even if a planner proposes several.

    This is deliberately applied after the planner/sanitizer path, so solver and
    LLM responses share the same mobile-safe teaching-loop invariant.
    """
    task_actions = [
        action
        for action in response.board_actions
        if action.type == VisualTutorCanvasActionType.STUDENT_TASK
        or action.requires_student_response
    ]
    selected = task_actions[0] if task_actions else None
    actions = [
        action
        for action in response.board_actions
        if action not in task_actions
    ]
    if selected is None:
        active_group_id = next(
            (action.group_id for action in actions if action.group_id),
            None,
        )
        selected = VisualTutorBoardAction(
            id=f"student-task-{response.turn_id}",
            type=VisualTutorCanvasActionType.STUDENT_TASK,
            sequence_index=max((action.sequence_index for action in actions), default=-1) + 1,
            text=response.student_task,
            requires_student_response=True,
            group_id=active_group_id,
            metadata={"teaching_loop_task": True},
        )
    else:
        selected = selected.model_copy(
            update={
                "requires_student_response": True,
                "text": selected.text or response.student_task,
                "group_id": selected.group_id
                or next((action.group_id for action in actions if action.group_id), None),
            }
        )
    actions.append(selected)
    metadata = {
        **response.metadata,
        "active_student_task_id": selected.id,
        "discarded_student_task_count": max(0, len(task_actions) - 1),
    }
    return response.model_copy(update={"board_actions": actions[:24], "metadata": metadata})


def _debug_metadata(
    *,
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    metadata: dict[str, Any],
    policy=None,
    understanding=None,
    input_understanding=None,
    adaptive_decision: Optional[AdaptiveTutorDecision] = None,
) -> dict[str, Any]:
    response_source = _response_source(metadata, understanding=understanding)
    # A deterministic solver can use the schema planner's local template to
    # shape a safe board response.  That is not an external LLM invocation and
    # must not be reported as one in audit metadata.
    llm_called = metadata.get("generation_path") == "llm_main"
    return {
        "response_source": response_source,
        "solver_name": _solver_name_for_understanding(understanding),
        "llm_called": llm_called,
        "llm_provider": _llm_provider_name() if llm_called else None,
        "fallback_reason": _fallback_reason(metadata, response_source),
        "current_step_index": _current_step_index(request, response, metadata),
        "input_relevance": _input_relevance(input_understanding, metadata),
        "validation_result": _validation_result(input_understanding, metadata),
        "tutor_move": (
            adaptive_decision.tutor_move.value
            if adaptive_decision is not None
            else metadata.get("tutor_move")
        ),
        "policy_decision": _policy_decision(policy, metadata),
        "board_action_ids": _board_action_ids(response),
        "teaching_strategy": (
            adaptive_decision.tutor_move.value
            if adaptive_decision is not None
            else metadata.get("tutor_move", "unknown")
        ),
        "board_version": metadata.get("board_version"),
        "base_board_version": metadata.get("base_board_version"),
        "board_update_mode": metadata.get("board_update_mode", "replace"),
        "patch_generated": metadata.get("patch_generated", False),
        "student_model_available": bool(metadata.get("student_model")),
        "student_intent_final": (
            input_understanding.student_intent.value
            if input_understanding
            else metadata.get("student_intent", "unknown")
        ),
        "move_instruction_sent_to_llm": bool(metadata.get("tutor_move")),
        "solver_speech_bypassed": metadata.get("solver_speech_bypassed", False),
        "llm_latency_ms": metadata.get("llm_latency_ms"),
    }


def _response_source(metadata: dict[str, Any], *, understanding=None) -> str:
    generation_path = metadata.get("generation_path")
    if generation_path == "llm_main":
        return "llm_planner"
    if generation_path in {"deterministic_solver", "deterministic_template_fallback"}:
        return "deterministic_solver"
    if metadata.get("planner_fallback") is True:
        return "template_fallback"
    if understanding is not None and _solver_name_for_understanding(understanding):
        return (
            "hybrid"
            if metadata.get("adaptive_tutor_decision")
            else "deterministic_solver"
        )
    return "template_fallback"


def _solver_name_for_understanding(understanding) -> Optional[str]:
    if understanding is None:
        return None
    problem_type = getattr(understanding, "problem_type", None)
    return {
        "linear_equation_one_variable": "LinearEquationSolver",
        "line_through_two_points": "LineThroughPointsSolver",
        "slope_from_two_points": "SlopeFromTwoPointsSolver",
        "quadratic_equation_basic": "QuadraticEquationBasicSolver",
        "quadratic_equation": "QuadraticEquationBasicSolver",
        "arithmetic_expression": "ArithmeticExpressionSolver",
        "simple_percentage_word_problem": "SimplePercentageWordProblemSolver",
    }.get(str(problem_type))


def _llm_provider_name() -> str:
    provider = os.getenv("VISUAL_TUTOR_LLM_PROVIDER", "auto").strip().lower()
    if provider and provider != "auto":
        return provider
    if os.getenv("OPENROUTER_API_KEY", "").strip():
        return "openrouter"
    return "auto"


def _fallback_reason(metadata: dict[str, Any], response_source: str) -> Optional[str]:
    if response_source == "deterministic_solver":
        return None
    if metadata.get("planner_error"):
        return str(metadata["planner_error"])
    if response_source == "template_fallback":
        return "structured_template_response"
    return None


def _current_step_index(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
    metadata: dict[str, Any],
) -> int:
    raw = (
        response.board.metadata.get("current_step_index")
        or metadata.get("current_step_index")
        or request.current_state.current_step_index
    )
    try:
        return int(raw)
    except (TypeError, ValueError):
        return request.current_state.current_step_index


def _input_relevance(input_understanding, metadata: dict[str, Any]) -> Optional[str]:
    if input_understanding is not None:
        return input_understanding.input_relevance.value
    raw = metadata.get("input_relevance")
    return str(raw) if raw is not None else None


def _validation_result(input_understanding, metadata: dict[str, Any]) -> Optional[str]:
    raw = metadata.get("validation_result")
    if raw is not None:
        return str(raw)
    if input_understanding is not None:
        raw = input_understanding.metadata.get("validation_result")
        return str(raw) if raw is not None else None
    return None


def _policy_decision(policy, metadata: dict[str, Any]) -> dict[str, Any]:
    if policy is None:
        return {
            "reason": metadata.get("policy_reason"),
            "teaching_mode": metadata.get("teaching_mode"),
        }
    return {
        "reason": policy.reason,
        "teaching_mode": policy.teaching_mode.value,
        "final_answer_locked": policy.final_answer_locked,
        "reveal_partial": policy.reveal_partial,
        "reveal_final": policy.reveal_final,
        "full_solution_allowed": policy.full_solution_allowed,
        "input_relevance": (
            policy.input_relevance.value if policy.input_relevance is not None else None
        ),
        "validation_result": policy.validation_result,
    }


def _board_action_ids(response: VisualTutorTurnResponse) -> list[str]:
    ids = [
        action.id
        for action in [*response.board_actions, *response.canvas_actions]
        if action.id
    ]
    if response.teaching_board is not None:
        ids.extend(
            action.id
            for action in response.teaching_board.actions
            if getattr(action, "id", None)
        )
        ids.extend(
            element.id
            for element in response.teaching_board.elements
            if getattr(element, "id", None)
        )
    return ids


def _solver_facts(
    *,
    solver,
    request: VisualTutorTurnRequest,
    understanding,
    policy,
) -> Optional[VisualTutorSolverFacts]:
    if solver is None or understanding is None:
        return None
    solver_facts = getattr(solver, "solver_facts", None)
    if not callable(solver_facts):
        return None
    try:
        return solver_facts(request, understanding, policy)
    except Exception as exc:
        policy.metadata["solver_facts_error"] = str(exc)
        return None


def _solver_facts_from_policy(policy) -> Optional[VisualTutorSolverFacts]:
    if policy is None:
        return None
    raw = policy.metadata.get("solver_facts")
    if not isinstance(raw, dict):
        return None
    try:
        return VisualTutorSolverFacts.model_validate(raw)
    except Exception:
        return None


def _apply_adaptive_tutor_decision(
    response: VisualTutorTurnResponse,
    decision: AdaptiveTutorDecision,
) -> VisualTutorTurnResponse:
    preserve_screen_state = (
        response.screen_state == VisualTutorScreenState.UNSUPPORTED_PROBLEM
        or response.metadata.get("screen_state") == "unsupported_problem"
        or response.board.metadata.get("screen_state") == "unsupported_problem"
    )
    screen_state = (
        VisualTutorScreenState.UNSUPPORTED_PROBLEM
        if preserve_screen_state
        else decision.screen_state
    )
    tutor_status = (
        "Needs a different problem" if preserve_screen_state else decision.tutor_status
    )
    teaching_stage = response.teaching_stage
    if teaching_stage is not None:
        teaching_stage = teaching_stage.model_copy(
            update={
                "stage_state": decision.stage_state,
                "lesson_state": decision.lesson_state,
                "max_actions_before_wait": decision.board_action_budget,
                "metadata": {
                    **teaching_stage.metadata,
                    "adaptive_tutor_decision": decision.metadata,
                },
            }
        )
    interaction = response.interaction
    if interaction is not None:
        interaction = interaction.model_copy(
            update={
                "type": decision.interaction_type,
                "expected_answer_locked": decision.final_answer_locked,
                "metadata": {
                    **interaction.metadata,
                    "adaptive_tutor_decision": decision.metadata,
                },
            }
        )
    next_student_action = response.next_student_action
    if interaction is not None:
        next_student_action = VisualTutorNextStudentAction(
            type=interaction.type,
            prompt=interaction.prompt,
            input_enabled=interaction.input_enabled,
            submit_label=interaction.submit_label,
            expected_answer_locked=interaction.expected_answer_locked,
            validation_strategy=interaction.validation_strategy,
            metadata={"adaptive_tutor_decision": decision.metadata},
        )
    behavior = response.tutor_behavior
    behavior_update = {
        "should_speak": True,
        "should_draw": bool(response.board_actions or response.canvas_actions),
        "should_ask": decision.tutor_move
        not in {
            VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY,
        },
        "should_wait": decision.tutor_move
        != VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY,
        "should_evaluate": decision.stage_state == VisualTutorStageState.EVALUATING,
        "should_reteach": decision.tutor_move
        in {
            VisualTutorMove.DIAGNOSE_WRONG_INPUT,
            VisualTutorMove.RETEACH_DIFFERENTLY,
            VisualTutorMove.REVEAL_PARTIAL_SOLUTION,
        },
        "explanation_language": decision.explanation_mode.value,
        "max_actions_before_wait": decision.board_action_budget,
        "answer_reveal_strategy": _answer_reveal_strategy_for_decision(decision),
        "metadata": {"adaptive_tutor_decision": decision.metadata},
    }
    if behavior is None:
        behavior = VisualTutorBehavior(**behavior_update)
    else:
        behavior = behavior.model_copy(
            update={
                **behavior_update,
                "metadata": {
                    **behavior.metadata,
                    **behavior_update["metadata"],
                },
            }
        )
    metadata = {
        **response.metadata,
        "adaptive_tutor_decision": decision.metadata,
        "tutor_move": decision.tutor_move.value,
        "answer_lock_decision": decision.answer_lock_decision.value,
        "screen_state": screen_state.value,
        "tutor_status": tutor_status,
        "quick_actions": [action.value for action in decision.quick_actions],
    }
    if decision.answer_lock_decision == VisualTutorAnswerLockDecision.ALLOW_FULL_REVEAL:
        final_answer_locked = False
    else:
        final_answer_locked = response.final_answer_locked
    return response.model_copy(
        update={
            "screen_state": screen_state,
            "tutor_status": tutor_status,
            "teaching_stage": teaching_stage,
            "interaction": interaction,
            "allowed_actions": list(decision.quick_actions),
            "quick_actions": list(decision.quick_actions),
            "next_student_action": next_student_action,
            "tutor_behavior": behavior,
            "final_answer_locked": final_answer_locked,
            "metadata": metadata,
        }
    )


def _enrich_final_verified_board(
    response: VisualTutorTurnResponse,
    *,
    solver_facts: Optional[VisualTutorSolverFacts],
) -> VisualTutorTurnResponse:
    """Attach solver-backed content for specialized adaptive board states."""
    if solver_facts is None:
        return response

    board_context = solver_facts.board_context
    problem = (
        board_context.get("problem") or solver_facts.normalized_problem or ""
    ).strip()
    if response.screen_state == VisualTutorScreenState.ASKING_QUESTION:
        if not problem:
            return response
        constant = str(board_context.get("constant") or "the constant").strip()
        operation = str(solver_facts.expected_operation or "").strip()
        operation_blank = re.sub(r"[-+]?\d+(?:\.\d+)?", "?", operation).capitalize()
        board_metadata = {
            **response.board.metadata,
            "screen_state": "asking_question",
            "board_type": "asking_question",
            "problem": problem,
            "handwritten_question": f"What number cancels {constant}?",
            "equation_with_blank": operation_blank,
            "next_step_preview": solver_facts.expected_equation,
            "solver_backed": True,
        }
        board = response.board.model_copy(update={"metadata": board_metadata})
        return response.model_copy(update={"board": board})

    if response.screen_state != VisualTutorScreenState.FINAL_VERIFIED_ANSWER:
        return response

    first_step = str(board_context.get("first_step_equation") or "").strip()
    final_answer = (
        solver_facts.verified_answer
        or solver_facts.known_solution
        or str(board_context.get("final_equation") or "")
    ).strip()
    if not problem or not final_answer:
        return response

    worked_solution = [step for step in (problem, first_step, final_answer) if step]
    board_metadata = {
        **response.board.metadata,
        "screen_state": "final_verified_answer",
        "board_type": "final_verified_answer",
        "problem": problem,
        "final_answer": final_answer,
        "worked_solution": worked_solution,
        "key_formula": "Keep both sides of the equation balanced.",
        "applied_rule": solver_facts.metadata.get("operation_text")
        or "Use inverse operations to isolate the variable.",
        "mastery_message": "Great job! You have completed this problem.",
        "verified_by": "solver_facts",
    }
    board = response.board.model_copy(update={"metadata": board_metadata})
    return response.model_copy(update={"board": board})


def _answer_reveal_strategy_for_decision(decision: AdaptiveTutorDecision) -> str:
    if decision.tutor_move == VisualTutorMove.REVEAL_FULL_SOLUTION_PROGRESSIVELY:
        return "progressive_full_solution"
    if decision.final_answer_locked:
        return "guided_learning_locked"
    return "answer_unlocked"


def _resolve_screen_state(
    request: VisualTutorTurnRequest,
    response: VisualTutorTurnResponse,
) -> VisualTutorScreenState:
    board_screen_state = response.board.metadata.get(
        "screen_state"
    ) or response.board.metadata.get("board_type")
    if board_screen_state == "final_verified_answer":
        return VisualTutorScreenState.FINAL_VERIFIED_ANSWER
    explicit_raw = response.metadata.get("screen_state") or board_screen_state
    if (
        explicit_raw is None
        and request.action == VisualTutorAction.START
        and not request.message.strip()
    ):
        return VisualTutorScreenState.HOME
    raw = explicit_raw or (
        response.screen_state.value
        if isinstance(response.screen_state, VisualTutorScreenState)
        else str(response.screen_state)
    )
    try:
        return VisualTutorScreenState(str(raw))
    except ValueError:
        pass

    if response.teaching_mode == VisualTutorTeachingMode.FULL_SOLUTION:
        return VisualTutorScreenState.FINAL_VERIFIED_ANSWER
    if response.teaching_mode == VisualTutorTeachingMode.STEP_CHECK:
        return VisualTutorScreenState.CHECK_MY_WORK
    return VisualTutorScreenState.SPEAKING_WRITING


def _resolve_tutor_status(
    screen_state: VisualTutorScreenState,
    response: VisualTutorTurnResponse,
) -> str:
    raw = response.metadata.get("tutor_status") or response.tutor_status
    if raw and str(raw) != "Waiting":
        return str(raw)
    if screen_state == VisualTutorScreenState.HOME:
        return "Waiting"
    if screen_state == VisualTutorScreenState.ASKING_QUESTION:
        return "Waiting for you"
    if screen_state == VisualTutorScreenState.GRAPH_BASED:
        return "Explaining"
    if screen_state == VisualTutorScreenState.CHECK_MY_WORK:
        return "Checking"
    if screen_state == VisualTutorScreenState.FINAL_VERIFIED_ANSWER:
        return "Verified"
    if screen_state == VisualTutorScreenState.UNSUPPORTED_PROBLEM:
        return "Needs a different problem"
    if response.teaching_stage and response.teaching_stage.stage_state in {
        VisualTutorStageState.SPEAKING,
        VisualTutorStageState.DRAWING,
    }:
        return "Writing..."
    return "Waiting"


def _grade_from_request(request: VisualTutorTurnRequest) -> Optional[int]:
    raw = (
        request.metadata.get("grade")
        or request.metadata.get("grade_level")
        or request.metadata.get("grade_level_hint")
    )
    if raw is None:
        return None
    try:
        if isinstance(raw, str):
            digits = "".join(ch for ch in raw if ch.isdigit())
            return int(digits) if digits else None
        return int(raw)
    except Exception:
        return None


def _apply_curriculum_context_to_response(
    response: VisualTutorTurnResponse,
    *,
    curriculum_meta: Optional[dict],
    use_khmer: bool,
) -> VisualTutorTurnResponse:
    if not curriculum_meta or not curriculum_meta.get("curriculum_chunk_ids"):
        return response
    if (
        response.screen_state == VisualTutorScreenState.UNSUPPORTED_PROBLEM
        or response.metadata.get("screen_state") == "unsupported_problem"
        or response.board.metadata.get("screen_state") == "unsupported_problem"
    ):
        return response

    formulas = _safe_formula_texts(curriculum_meta.get("formulas"))
    prerequisites = _safe_texts(curriculum_meta.get("prerequisites"))
    misconceptions = _safe_texts(curriculum_meta.get("common_misconceptions"))
    teaching_sequence = _safe_texts(curriculum_meta.get("teaching_sequence"))
    khmer_terms = curriculum_meta.get("khmer_terms")
    if not isinstance(khmer_terms, dict):
        khmer_terms = {}

    board = _curriculum_enriched_board(
        response.board,
        formulas=formulas,
        prerequisites=prerequisites,
        misconceptions=misconceptions,
        teaching_sequence=teaching_sequence,
        khmer_terms=khmer_terms,
        use_khmer=use_khmer,
    )
    student_task = response.student_task
    screen_state = str(
        response.board.metadata.get("screen_state")
        or response.board.metadata.get("board_type")
        or ""
    )
    # Curriculum can enrich board context and planning metadata, but it must
    # not turn the learner's one small task into a second instruction.

    display_text = response.display_text
    if (
        response.teaching_mode == VisualTutorTeachingMode.MISCONCEPTION_FIX
        and misconceptions
        and misconceptions[0] not in display_text
    ):
        prefix = "ចំណុចដែលសិស្សច្រឡំញឹកញាប់៖" if use_khmer else "Common misconception:"
        display_text = f"{display_text} {prefix} {misconceptions[0]}"

    interaction = response.interaction
    if interaction is not None and interaction.prompt != student_task:
        interaction = interaction.model_copy(update={"prompt": student_task})

    return response.model_copy(
        update={
            "student_task": student_task,
            "display_text": display_text,
            "interaction": interaction,
            "board": board,
            "canvas_actions": _with_curriculum_canvas_actions(
                response.canvas_actions,
                formulas=formulas,
                prerequisites=prerequisites,
                misconceptions=misconceptions,
                khmer_terms=khmer_terms,
                use_khmer=use_khmer,
                teaching_mode=response.teaching_mode,
            ),
        }
    )


def _safe_current_step_index(response: VisualTutorTurnResponse) -> int:
    try:
        return max(0, int(response.board.metadata.get("current_step_index") or 0))
    except (TypeError, ValueError):
        return 0


def _with_curriculum_canvas_actions(
    actions: list[VisualTutorCanvasAction],
    *,
    formulas: list[str],
    prerequisites: list[str],
    misconceptions: list[str],
    khmer_terms: dict,
    use_khmer: bool,
    teaching_mode: VisualTutorTeachingMode,
) -> list[VisualTutorCanvasAction]:
    curriculum_actions = _curriculum_canvas_actions(
        formulas=formulas,
        prerequisites=prerequisites,
        misconceptions=misconceptions,
        khmer_terms=khmer_terms,
        use_khmer=use_khmer,
        teaching_mode=teaching_mode,
    )
    if not curriculum_actions:
        return actions

    existing_ids = {action.id for action in actions}
    merged = list(actions)
    for action in curriculum_actions:
        if action.id not in existing_ids:
            merged.append(action)
            existing_ids.add(action.id)
    return merged


def _curriculum_canvas_actions(
    *,
    formulas: list[str],
    prerequisites: list[str],
    misconceptions: list[str],
    khmer_terms: dict,
    use_khmer: bool,
    teaching_mode: VisualTutorTeachingMode,
) -> list[VisualTutorCanvasAction]:
    actions: list[VisualTutorCanvasAction] = []
    y = 424.0

    if formulas:
        label = "រូបមន្ត" if use_khmer else "Formula"
        for index, formula in enumerate(formulas[:2]):
            actions.append(
                VisualTutorCanvasAction(
                    id=f"canvas-curriculum-formula-{index}-{_safe_canvas_id(formula)}",
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    x=640,
                    y=y,
                    width=320,
                    height=44,
                    text=f"{label}: {formula}",
                    latex=formula,
                    style=CanvasElementStyle(
                        color="#d7f9ff",
                        background_color="#10324a",
                        stroke_color="#22d3ee",
                        font_size=18,
                    ),
                    metadata={
                        "source": "curriculum",
                        "canvas_card_type": "formula_card",
                        "formula": formula,
                    },
                )
            )
            y += 54

    if prerequisites:
        reminder_label = "រំលឹក" if use_khmer else "Reminder"
        reminder = prerequisites[0]
        actions.append(
            VisualTutorCanvasAction(
                id=f"canvas-curriculum-prerequisite-{_safe_canvas_id(reminder)}",
                type=VisualTutorCanvasActionType.WRITE_TEXT,
                x=640,
                y=y,
                width=320,
                height=48,
                text=f"{reminder_label}: {reminder}",
                style=CanvasElementStyle(
                    color="#fff7d6",
                    background_color="#3b3215",
                    stroke_color="#f59e0b",
                    font_size=16,
                ),
                metadata={
                    "source": "curriculum",
                    "canvas_card_type": "prerequisite_reminder",
                    "prerequisite": reminder,
                },
            )
        )
        y += 58

    if use_khmer and khmer_terms:
        terms = "; ".join(
            f"{english}: {khmer}"
            for english, khmer in list(khmer_terms.items())[:3]
            if str(english).strip() and str(khmer).strip()
        )
        if terms:
            actions.append(
                VisualTutorCanvasAction(
                    id=f"canvas-curriculum-khmer-terms-{_safe_canvas_id(terms)}",
                    type=VisualTutorCanvasActionType.WRITE_TEXT,
                    x=640,
                    y=y,
                    width=320,
                    height=58,
                    text=terms,
                    style=CanvasElementStyle(
                        color="#e0fff8",
                        background_color="#103b35",
                        stroke_color="#2dd4bf",
                        font_size=15,
                    ),
                    metadata={
                        "source": "curriculum",
                        "canvas_card_type": "khmer_terms",
                        "khmer_terms": khmer_terms,
                    },
                )
            )
            y += 68

    if teaching_mode == VisualTutorTeachingMode.MISCONCEPTION_FIX and misconceptions:
        misconception_label = (
            "ចំណុចច្រឡំញឹកញាប់" if use_khmer else "Common misconception"
        )
        misconception = misconceptions[0]
        actions.append(
            VisualTutorCanvasAction(
                id=f"canvas-curriculum-misconception-{_safe_canvas_id(misconception)}",
                type=VisualTutorCanvasActionType.WRITE_TEXT,
                x=640,
                y=y,
                width=320,
                height=68,
                text=f"{misconception_label}: {misconception}",
                style=CanvasElementStyle(
                    color="#ffe4e6",
                    background_color="#451a23",
                    stroke_color="#fb7185",
                    font_size=15,
                ),
                metadata={
                    "source": "curriculum",
                    "canvas_card_type": "misconception_card",
                    "misconception": misconception,
                },
            )
        )

    return actions


def _curriculum_enriched_board(
    board: VisualTutorBoard,
    *,
    formulas: list[str],
    prerequisites: list[str],
    misconceptions: list[str],
    teaching_sequence: list[str],
    khmer_terms: dict,
    use_khmer: bool,
) -> VisualTutorBoard:
    items = list(board.items)
    existing_content = "\n".join(item.content for item in items)
    if formulas:
        formula_text = "; ".join(formulas[:3])
        if formula_text not in existing_content:
            insert_at = _final_item_index(items)
            items.insert(
                insert_at,
                VisualTutorBoardItem(
                    label="Formula",
                    content=formula_text,
                    status="complete",
                    metadata={"source": "curriculum"},
                ),
            )

    if use_khmer and khmer_terms:
        terms_text = "; ".join(
            f"{english}: {khmer}" for english, khmer in list(khmer_terms.items())[:4]
        )
        if terms_text and terms_text not in existing_content:
            insert_at = _final_item_index(items)
            items.insert(
                insert_at,
                VisualTutorBoardItem(
                    label="Khmer Terms",
                    content=terms_text,
                    status="complete",
                    metadata={"source": "curriculum"},
                ),
            )

    metadata = {
        **board.metadata,
        "curriculum_formulas": formulas,
        "curriculum_prerequisites": prerequisites,
        "curriculum_common_misconceptions": misconceptions,
        "curriculum_teaching_sequence": teaching_sequence,
        "curriculum_khmer_terms": khmer_terms,
        "curriculum_enriched": True,
    }
    return board.model_copy(update={"items": items, "metadata": metadata})


def _final_item_index(items: list[VisualTutorBoardItem]) -> int:
    for index, item in enumerate(items):
        if item.label.strip().lower() == "final":
            return index
    return len(items)


def _safe_formula_texts(values) -> list[str]:
    output: list[str] = []
    for value in values or []:
        if isinstance(value, str):
            text = value
        elif isinstance(value, dict):
            text = str(value.get("expression") or value.get("text") or "")
        else:
            text = str(value)
        text = text.strip()
        if text and text not in output:
            output.append(text)
    return output


def _safe_texts(values) -> list[str]:
    output: list[str] = []
    for value in values or []:
        if isinstance(value, str):
            text = value
        elif isinstance(value, dict):
            text = str(value.get("text") or value.get("correction") or "")
        else:
            text = str(value)
        text = text.strip()
        if text and text not in output:
            output.append(text)
    return output


def _safe_canvas_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return safe[:72] or "curriculum"


def _uses_khmer(request: VisualTutorTurnRequest, metadata: dict) -> bool:
    locale = (request.locale or "").lower()
    if locale.startswith("km"):
        return True
    policy = metadata.get("policy") if isinstance(metadata.get("policy"), dict) else {}
    return bool(policy.get("use_khmer_explanation"))


def _should_understand_student_input(request: VisualTutorTurnRequest) -> bool:
    if not request.current_state.problem_text:
        return False
    if request.action == VisualTutorAction.START:
        return False
    return bool(request.message.strip()) or request.action in {
        VisualTutorAction.REQUEST_HINT,
        VisualTutorAction.REQUEST_STUCK_HELP,
        VisualTutorAction.REQUEST_FINAL_ANSWER,
        VisualTutorAction.EXPLAIN_DIFFERENTLY,
    }


def _input_validation_turn(
    request: VisualTutorTurnRequest,
    *,
    policy,
    session_id: str,
    fallback_board: VisualTutorBoard,
) -> VisualTutorTurnResponse:
    use_khmer = policy.use_khmer_explanation
    relevance = policy.input_relevance
    if policy.possible_final_answer:
        spoken_text = "That looks like a final-answer guess. I will check it, but first show the reasoning step."
        display_text = "That looks like an answer guess, not the current step yet."
        student_task = (
            policy.metadata.get("expected_step")
            or "Write the next reasoning step for the current problem."
        )
        if use_khmer:
            spoken_text = "នេះមើលទៅដូចជាការស្មានចម្លើយចុងក្រោយ។ គ្រូនឹងពិនិត្យ ប៉ុន្តែសូមបង្ហាញជំហានគិតជាមុន។"
            display_text = "នេះដូចជាការស្មានចម្លើយ មិនទាន់ជាជំហានបច្ចុប្បន្នទេ។"
            student_task = "សរសេរជំហានគិតបន្ទាប់សម្រាប់លំហាត់នេះ។"
    elif relevance == VisualTutorInputRelevance.UNRELATED:
        spoken_text = "That input does not match the current step. Let's focus on the next small operation."
        display_text = "That does not match the current step yet."
        student_task = (
            policy.metadata.get("expected_step")
            or "Try the next operation for the current problem."
        )
        if use_khmer:
            spoken_text = "ចម្លើយនេះមិនត្រូវនឹងជំហានបច្ចុប្បន្នទេ។ យើងផ្តោតលើប្រមាណវិធីតូចបន្ទាប់សិន។"
            display_text = "វាមិនទាន់ត្រូវនឹងជំហានបច្ចុប្បន្នទេ។"
            student_task = "សាកធ្វើប្រមាណវិធីបន្ទាប់សម្រាប់លំហាត់នេះ។"
    else:
        spoken_text = "That message seems off topic for this problem. Bring it back to the current step."
        display_text = "That does not look like a math step for this problem."
        student_task = "Tell me the next math operation you would try."
        if use_khmer:
            spoken_text = (
                "សារនេះហាក់ដូចជាមិនទាក់ទងនឹងលំហាត់នេះទេ។ សូមត្រឡប់មកជំហានបច្ចុប្បន្ន។"
            )
            display_text = "វាមិនមើលទៅដូចជាជំហានគណិតវិទ្យាសម្រាប់លំហាត់នេះទេ។"
            student_task = "ប្រាប់គ្រូពីប្រមាណវិធីគណិតវិទ្យាបន្ទាប់ដែលអ្នកនឹងសាក។"

    board = fallback_board.model_copy(
        update={
            "metadata": {
                **fallback_board.metadata,
                "feedback": "input_redirect",
                "input_relevance": relevance.value if relevance else None,
            }
        }
    )
    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=str(uuid.uuid4()),
        spoken_text=spoken_text,
        display_text=display_text,
        teaching_mode=policy.teaching_mode,
        final_answer_locked=policy.final_answer_locked,
        student_task=student_task,
        board=board,
        mastery_signal=(
            VisualTutorMasterySignal.MISCONCEPTION
            if relevance == VisualTutorInputRelevance.UNRELATED
            else VisualTutorMasterySignal.EXPLORING
        ),
        metadata={
            "policy": policy.metadata,
            "policy_reason": policy.reason,
            "redirect_reason": policy.reason,
        },
    )


def _should_return_graph_board(problem_message: str, understanding) -> bool:
    message = problem_message.lower()
    problem_type = (understanding.problem_type or "").lower()
    entities = understanding.extracted_entities or {}
    if problem_type.startswith("function_"):
        return any(
            cue in message
            for cue in (
                "graph",
                "draw",
                "sketch",
                "visual",
                "curve",
                "sin",
                "cos",
                "wave",
                "amplitude",
                "frequency",
                "ក្រាប",
                "គូរ",
            )
        )
    return bool(
        entities.get("function_expression")
        and any(cue in message for cue in ("graph", "draw", "sketch", "sin", "cos"))
    ) or bool(
        re.search(r"\bf\s*\(\s*x\s*\)\s*=", message)
        and any(cue in message for cue in ("graph", "draw", "sketch", "sin", "cos"))
    )


def _should_return_friendly_unsupported(
    problem_message: str,
    understanding,
) -> bool:
    """Use the friendly unsupported screen for clearly off-topic requests.

    Unsupported algebra or subject questions should still flow through the LLM
    teaching planner so the tutor can provide a useful next teaching move.
    """

    if (understanding.problem_type or "").lower() != "unsupported":
        return False

    message = problem_message.strip().lower()
    if not message:
        return False

    has_math_syntax = bool(re.search(r"[=+\-*/^√∫π()]|\d|[a-z]\s*\(", message))
    academic_cues = (
        "explain",
        "teach",
        "learn",
        "topic",
        "relation",
        "concept",
        "math",
        "algebra",
        "equation",
        "solve",
        "function",
        "graph",
        "slope",
        "line",
        "physics",
        "chemistry",
        "english",
        "khmer",
        "grammar",
        "គណិត",
        "សមីការ",
        "អនុគមន៍",
        "រូបវិទ្យា",
        "គីមី",
    )
    if has_math_syntax or any(cue in message for cue in academic_cues):
        return False

    off_topic_cues = (
        "dragon",
        "bicycle",
        "joke",
        "story",
        "song",
        "movie",
        "game",
        "weather",
        "recipe",
        "draw",
        "paint",
    )
    return any(cue in message for cue in off_topic_cues)


def _is_explicit_symbolic_rearrangement(message: str) -> bool:
    return bool(
        re.search(r"\b(?:solve|isolate|rearrange)\b.+\bfor\s+[a-z]\b", message, re.I)
    )


def _graph_based_function_turn(
    request: VisualTutorTurnRequest,
    *,
    understanding,
    policy,
    session_id: str,
) -> VisualTutorTurnResponse:
    graph_metadata = _graph_board_metadata(request.message, understanding)
    use_khmer = policy.use_khmer_explanation
    spoken_text = (
        "Notice how the wave repeats every 2π. This is the period."
        if not use_khmer
        else "សង្កេតមើលរលកនេះ វាធ្វើដដែលៗរៀងរាល់ 2π។ នេះហៅថារយៈពេល។"
    )
    student_task = (
        "What do you notice about the distance between two peaks?"
        if not use_khmer
        else "តើអ្នកសង្កេតឃើញចម្ងាយរវាងកំពូលពីរដូចម្តេច?"
    )
    instruction = graph_metadata["instruction"]

    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=str(uuid.uuid4()),
        spoken_text=spoken_text,
        display_text=spoken_text,
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=policy.final_answer_locked,
        student_task=student_task,
        board=VisualTutorBoard(
            type=VisualTutorBoardType.GRAPH_HINT,
            title="Graph-Based Board",
            items=[
                VisualTutorBoardItem(
                    label="Function",
                    content=graph_metadata["equation_title"],
                    status="active",
                ),
                VisualTutorBoardItem(
                    label="Instruction",
                    content=instruction,
                    status="active",
                ),
            ],
            metadata=graph_metadata,
        ),
        board_actions=[
            VisualTutorBoardAction(
                id="graph-draw-axes",
                type=VisualTutorCanvasActionType.DRAW_AXES,
                sequence_index=0,
                duration_ms=420,
                group_id="graph-intro",
                metadata={"screen_state": "graph_based"},
            ),
            VisualTutorBoardAction(
                id="graph-draw-curve",
                type=VisualTutorCanvasActionType.SHOW_GRAPH,
                sequence_index=1,
                duration_ms=620,
                group_id="graph-intro",
                x=80,
                y=100,
                width=800,
                height=460,
                text=graph_metadata["equation_title"],
                points=graph_metadata["graph_elements"]["curve_points"],
                graph={
                    "x_min": -3.5,
                    "x_max": 3.5,
                    "y_min": -1.5,
                    "y_max": 1.5,
                    "x_label": "x",
                    "y_label": "f(x)",
                    "function_expression": graph_metadata["function_name"],
                    "domain": [-3.14, 3.14],
                    "points": graph_metadata["graph_elements"]["curve_points"],
                    "annotations": [
                        {"text": "Period focus", "x": 0.0, "y": 0.0},
                    ],
                },
                metadata={"function_name": graph_metadata["function_name"]},
            ),
            VisualTutorBoardAction(
                id="graph-highlight-point",
                type=VisualTutorCanvasActionType.HIGHLIGHT,
                sequence_index=2,
                duration_ms=260,
                target_id="graph-frequency-point",
                group_id="graph-intro",
                metadata=graph_metadata["graph_elements"]["highlighted_point"],
            ),
        ],
        speech=VisualTutorSpeech(
            text=spoken_text,
            language="km" if use_khmer else "en",
            pause_after_ms=350,
        ),
        teaching_stage=VisualTutorTeachingStage(
            stage_state=VisualTutorStageState.WAITING_FOR_STUDENT,
            lesson_state=VisualTutorLessonState.ASK,
            current_focus="graph-frequency-point",
            turn_goal="Connect the visual graph to period, peak, trough, and amplitude.",
            max_actions_before_wait=1,
        ),
        interaction=VisualTutorInteraction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt=student_task,
            expected_answer_locked=True,
            validation_strategy="concept_observation",
            input_enabled=True,
            submit_label="Submit",
            metadata={"graph_focus": "period_between_peaks"},
        ),
        allowed_actions=[
            VisualTutorAllowedAction.SHOW_VISUALLY,
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.REQUEST_HINT,
            VisualTutorAllowedAction.STUCK,
        ],
        visual_focus=VisualTutorVisualFocus(
            element_id="graph-frequency-point",
            group_id="graph-intro",
            description="Highlighted point on the sine graph",
            metadata={"screen_state": "graph_based"},
        ),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata={
            "screen_state": "graph_based",
            "board_type": "graph_based",
            "problem_type": understanding.problem_type,
            "graph_elements": graph_metadata["graph_elements"],
            "function_name": graph_metadata["function_name"],
        },
    )


def _friendly_unsupported_turn(
    request: VisualTutorTurnRequest,
    *,
    understanding,
    policy,
    session_id: str,
) -> VisualTutorTurnResponse:
    use_khmer = policy.use_khmer_explanation
    allow_problem_retry = not _should_return_friendly_unsupported(
        request.message, understanding
    )
    tutor_message = (
        "I'm still learning! I can help with Math, Physics, and Chemistry for now."
        if not use_khmer
        else "គ្រូនៅកំពុងរៀនបន្ថែម! ឥឡូវនេះគ្រូអាចជួយគណិតវិទ្យា រូបវិទ្យា និងគីមីវិទ្យា។"
    )
    friendly_quote = (
        "I'm sorry, I can't solve this type of problem yet."
        if not use_khmer
        else "សុំទោស គ្រូមិនទាន់អាចដោះស្រាយលំហាត់ប្រភេទនេះបាននៅឡើយទេ។"
    )
    khmer_explanation = (
        "សូមសាកល្បងប្រធានបទផ្សេង ឬពិនិត្យមើលគុណភាពរូបភាព ប្រសិនបើអ្នកបានស្កេនលំហាត់។"
    )
    unsupported_reason = "No deterministic solver or supported teaching planner is available for this request."
    retry_options = [
        {
            "id": "try_different_topic",
            "label": "Try a different topic",
            "khmer_label": "សាកប្រធានបទផ្សេង",
        },
        {
            "id": "check_image_quality",
            "label": "Check the image quality",
            "khmer_label": "ពិនិត្យគុណភាពរូបភាព",
        },
    ]
    metadata = {
        "screen_state": "unsupported_problem",
        "board_type": "unsupported_problem",
        "problem_type": understanding.problem_type,
        "known_solver_available": False,
        "unsupported_reason": unsupported_reason,
        "friendly_message": friendly_quote,
        "khmer_explanation": khmer_explanation,
        "retry_options": retry_options,
        "raw_error_hidden": True,
    }
    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=str(uuid.uuid4()),
        spoken_text=tutor_message,
        display_text=tutor_message,
        teaching_mode=VisualTutorTeachingMode.GUIDED_QUESTION,
        final_answer_locked=True,
        student_task="Try another problem or choose a supported topic.",
        board=VisualTutorBoard(
            type=VisualTutorBoardType.FORMULA_CARD,
            title="Unsupported Problem",
            items=[
                VisualTutorBoardItem(
                    label="Status",
                    content="Unsupported Problem",
                    status="active",
                ),
                VisualTutorBoardItem(
                    label="Retry",
                    content="Try a different topic or check the image quality.",
                    status="active",
                ),
            ],
            metadata=metadata,
        ),
        speech=VisualTutorSpeech(
            text=tutor_message,
            language="km" if use_khmer else "en",
        ),
        teaching_stage=VisualTutorTeachingStage(
            stage_state=VisualTutorStageState.WAITING_FOR_STUDENT,
            lesson_state=VisualTutorLessonState.UNDERSTAND_REQUEST,
            current_focus="unsupported-problem",
            turn_goal="Recover from an unsupported request without exposing a technical error.",
            max_actions_before_wait=1,
        ),
        interaction=VisualTutorInteraction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt="Try another problem or choose a supported topic.",
            input_enabled=allow_problem_retry,
            expected_answer_locked=not allow_problem_retry,
            metadata={
                "recovery_action": "submit_another_problem"
                if allow_problem_retry
                else "choose_supported_topic"
            },
        ),
        allowed_actions=[],
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata=metadata,
    )


def _graph_board_metadata(problem_message: str, understanding) -> dict:
    raw_expression = (
        (understanding.extracted_entities or {}).get("function_expression")
        or _extract_graph_function_expression(problem_message)
        or "f(x) = sin(x)"
    )
    equation_title = _normalize_graph_equation_title(str(raw_expression))
    function_name = (
        equation_title.split("=", 1)[1].strip()
        if "=" in equation_title
        else equation_title
    )
    labels = {
        "peak": "Peak",
        "trough": "Trough",
        "amplitude": "Amplitude = 1",
    }
    curve_points = _sine_curve_points()
    instruction = "Drag the point to change the frequency"
    return {
        "screen_state": "graph_based",
        "board_type": "graph_based",
        "equation_title": equation_title,
        "function_name": function_name,
        "peak_label": labels["peak"],
        "trough_label": labels["trough"],
        "amplitude_label": labels["amplitude"],
        "instruction": instruction,
        "graph_elements": {
            "axes": True,
            "curve_points": curve_points,
            "function_name": function_name,
            "labels": labels,
            "highlighted_point": {
                "id": "graph-frequency-point",
                "x": 0,
                "y": 0,
                "label": "frequency point",
            },
            "instruction": instruction,
        },
    }


def _extract_graph_function_expression(message: str) -> Optional[str]:
    match = re.search(
        r"((?:f\s*\(\s*x\s*\)|y)\s*=\s*[^,.;?]+)",
        message,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    if "sin" in message.lower():
        return "f(x) = sin(x)"
    if "cos" in message.lower():
        return "f(x) = cos(x)"
    return None


def _normalize_graph_equation_title(expression: str) -> str:
    text = expression.strip()
    if not text:
        return "f(x) = sin(x)"
    if "=" in text:
        return re.sub(r"\s+", " ", text)
    return f"f(x) = {text}"


def _sine_curve_points() -> list[dict]:
    return [
        {"x": -3.14, "y": 0.0},
        {"x": -2.36, "y": -0.71},
        {"x": -1.57, "y": -1.0},
        {"x": -0.79, "y": -0.71},
        {"x": 0.0, "y": 0.0},
        {"x": 0.79, "y": 0.71},
        {"x": 1.57, "y": 1.0},
        {"x": 2.36, "y": 0.71},
        {"x": 3.14, "y": 0.0},
    ]


def _problem_message(request: VisualTutorTurnRequest) -> str:
    if (
        request.action
        in {
            VisualTutorAction.SUBMIT_STEP,
            VisualTutorAction.REQUEST_HINT,
            VisualTutorAction.REQUEST_STUCK_HELP,
            VisualTutorAction.REQUEST_FINAL_ANSWER,
            VisualTutorAction.EXPLAIN_DIFFERENTLY,
        }
        and request.current_state.problem_text
    ):
        return request.current_state.problem_text.strip()
    if is_stuck_help_request(request) and request.current_state.problem_text:
        return request.current_state.problem_text.strip()
    return request.message.strip() or (request.current_state.problem_text or "").strip()


def _greeting(
    request: VisualTutorTurnRequest,
    *,
    session_id: str,
) -> VisualTutorTurnResponse:
    policy = decide_visual_tutor_policy(request, has_problem=False)
    spoken_text = (
        "Welcome to math class. What lesson or problem do you want to explore today?"
    )
    display_text = "What lesson or problem do you want to explore today?"
    if policy.use_khmer_explanation:
        spoken_text = (
            "សូមស្វាគមន៍មកកាន់ថ្នាក់គណិតវិទ្យា។ តើអ្នកចង់រៀនមេរៀន ឬលំហាត់អ្វីថ្ងៃនេះ?"
        )
        display_text = "តើអ្នកចង់រៀនមេរៀន ឬលំហាត់អ្វីថ្ងៃនេះ?"

    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=str(uuid.uuid4()),
        spoken_text=spoken_text,
        display_text=display_text,
        teaching_mode=policy.teaching_mode,
        final_answer_locked=policy.final_answer_locked,
        student_task="Type or say a math problem, for example: 2x + 5 = 15.",
        board=VisualTutorBoard(
            type=VisualTutorBoardType.FORMULA_CARD,
            title="Math Class",
            items=[
                VisualTutorBoardItem(
                    label="Ready",
                    content="Send a linear equation and we will solve it together.",
                    status="active",
                )
            ],
        ),
        mastery_signal=VisualTutorMasterySignal.EXPLORING,
        metadata={
            "subject": request.subject,
            "topic": request.topic,
            "policy": policy.metadata,
            "policy_reason": policy.reason,
        },
    )
