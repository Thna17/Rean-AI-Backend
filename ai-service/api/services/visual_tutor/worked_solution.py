"""Complete, step-by-step worked solution for a Grade 12 limit.

Every number and expression on the board is computed by sympy, never by a
language model, and the final value is cross-checked against
``_limit_computation_facts`` (the same ground truth the rest of the tutor is
verified against). If an algebraic route disagrees with that ground truth the
builder falls back to a table-based explanation instead of showing a wrong
line, so a student can never be shown inconsistent working.
"""
from __future__ import annotations

import json
import logging
import httpx
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import sympy

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorAllowedAction,
    VisualTutorBoard,
    VisualTutorBoardAction,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorCanvasActionType,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorMasterySignal,
    VisualTutorScreenState,
    VisualTutorSpeech,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.solvers import (
    LimitOfFunctionProblem,
    _limit_computation_facts,
    _limit_sympy_expression,
    _limit_sympy_point,
    parse_limit_of_function,
)
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


def _solver_facts(request: VisualTutorTurnRequest) -> Optional[dict[str, Any]]:
    """Ground-truth facts in the same shape the guided flow publishes.

    Showing the whole solution must not drop the machine-checked facts other
    parts of the tutor (and the follow-up questions in a later step) rely on.
    """
    # Imported here: solver_registry imports the solvers package, and importing
    # it at module scope would make this module part of that import cycle.
    from api.services.visual_tutor.policy import decide_visual_tutor_policy
    from api.services.visual_tutor.problem_understanding import (
        VisualTutorProblemUnderstandingRequest,
        understand_visual_tutor_problem,
    )
    from api.services.visual_tutor.solvers import LimitOfFunctionSolver

    try:
        understanding = understand_visual_tutor_problem(
            VisualTutorProblemUnderstandingRequest(message=request.message or "")
        )
        solver = LimitOfFunctionSolver()
        if not solver.can_handle(understanding):
            return None
        policy = decide_visual_tutor_policy(
            request, has_problem=True, problem_type=understanding.problem_type
        )
        return solver.solver_facts(request, understanding, policy).model_dump(mode="json")
    except Exception:
        return None

logger = logging.getLogger(__name__)

TRY_MYSELF_MODE = "try_myself"
_X = sympy.Symbol("x")
# The variable token in sympy's LaTeX, excluding letters inside commands such
# as \exp or \max.
_X_TOKEN_RE = re.compile(r"(?<![A-Za-z\\])x(?![A-Za-z])")


@dataclass(frozen=True)
class SolutionStep:
    key: str
    heading: str
    explanation: str
    latex: Optional[str] = None
    table: Optional[dict[str, list[Any]]] = None


@dataclass
class WorkedSolution:
    problem_latex: str
    answer_latex: str
    answer_text: str
    steps: list[SolutionStep] = field(default_factory=list)
    method: str = "table"


_worked_solution_cache: dict[str, WorkedSolution] = {}
_explanation_cache: dict[str, str] = {}


def clear_worked_solution_cache() -> None:
    """Clear in-memory worked solution and explanation caches."""
    _worked_solution_cache.clear()
    _explanation_cache.clear()


def get_cache_stats() -> dict[str, int]:
    """Return cache entry count for metrics and tests."""
    return {
        "worked_solutions_cached": len(_worked_solution_cache),
        "explanations_cached": len(_explanation_cache),
    }


def match_worked_solution(request: VisualTutorTurnRequest) -> Optional[LimitOfFunctionProblem]:
    """The limit problem to solve in full, or None to use the guided flow.

    A student who typed a whole new limit mid-session gets a fresh solution
    too: the gateway sends that as submit_step once a problem exists, but a
    message that parses as a complete, different limit is a new problem.
    Also handles START actions with problem text to avoid expensive LLM fallthrough.
    """
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if str(metadata.get("tutor_mode") or "").strip().lower() == TRY_MYSELF_MODE:
        return None
    problem = parse_limit_of_function(request.message or "")
    if problem is None and request.action == VisualTutorAction.START:
        problem = parse_limit_of_function(request.current_state.problem_text or "")
    if problem is None:
        return None
    if request.action in {VisualTutorAction.SUBMIT_PROBLEM, VisualTutorAction.START}:
        return problem
    if request.action == VisualTutorAction.SUBMIT_STEP:
        current = parse_limit_of_function(request.current_state.problem_text or "")
        if current is None or current.normalized_problem != problem.normalized_problem:
            return problem
    return None


def match_worked_solution_followup(
    request: VisualTutorTurnRequest,
) -> Optional[LimitOfFunctionProblem]:
    """The limit a student is asking a question *about*, or None.

    The solution is rebuilt from the problem text rather than read back from
    storage: it is fully deterministic, so the rebuilt steps are byte-for-byte
    what the student is looking at, with no persistence to fall out of sync.
    """
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if str(metadata.get("tutor_mode") or "").strip().lower() == TRY_MYSELF_MODE:
        return None
    if not (request.message or "").strip():
        return None
    # A message that is itself a whole new limit starts a new solution instead.
    if parse_limit_of_function(request.message or "") is not None:
        return None
    return parse_limit_of_function(request.current_state.problem_text or "")


def _normalize_question_key(question: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", question.lower())
    return " ".join(cleaned.split())


def answer_about_solution(
    request: VisualTutorTurnRequest,
    problem: LimitOfFunctionProblem,
    *,
    session_id: str,
    llm_client: Any = None,
) -> VisualTutorTurnResponse:
    """Answer a student's question about one step, keeping the solution on the
    board so they can still see the step being discussed."""
    is_khmer = _uses_khmer(request, problem)
    solution = solve_limit(problem)
    step = _referenced_step(request, solution)
    answer, degraded_reason = _explain_step(
        question=request.message or "",
        solution=solution,
        step=step,
        is_khmer=is_khmer,
        llm_client=llm_client,
    )
    heading = f"About {step.heading}" if step else "About this solution"
    extra_metadata = (
        {"degraded_mode": True, "degraded_reason": degraded_reason}
        if degraded_reason
        else {}
    )
    return _solution_turn(
        request,
        problem,
        solution,
        session_id=session_id,
        extra_sections=[
            SolutionStep(key="reply", heading=heading, explanation=answer),
        ],
        message=answer,
        task="Ask me anything else about this solution, or send another problem.",
        focus_section=f"step-{step.key}" if step else None,
        extra_metadata=extra_metadata,
    )


def _referenced_step(
    request: VisualTutorTurnRequest, solution: WorkedSolution
) -> Optional[SolutionStep]:
    """Which step the question is about: the one the student tapped, else the
    one their words point at."""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    tapped = str(metadata.get("board_action_id") or "")
    if tapped.startswith("ws-step-"):
        # "ws-step-cancel-7" -> "cancel"
        key = tapped[len("ws-step-") :].rsplit("-", 1)[0]
        for step in solution.steps:
            if step.key == key:
                return step
    words = (request.message or "").lower()
    keywords = {
        "factor": "factor",
        "cancel": "cancel",
        "substitut": "substitute",
        "table": "check",
        "0/0": "try",
        "indeterminate": "try",
        "zero over zero": "try",
    }
    for needle, key in keywords.items():
        if needle in words:
            for step in solution.steps:
                if step.key == key:
                    return step
    # A question with no clear target is about the step numbered in it, if any.
    for step in solution.steps:
        if step.heading.split("·")[0].strip().lower() in words:
            return step
    return None


def _explain_step(
    *,
    question: str,
    solution: WorkedSolution,
    step: Optional[SolutionStep],
    is_khmer: bool = False,
    llm_client: Any = None,
) -> tuple[str, Optional[str]]:
    """A short answer in the tutor's voice, grounded in the verified solution.

    Returns (explanation_text, degraded_reason).
    If cached, returns the cached explanation with degraded_reason=None.
    The deterministic explanation is the floor: if the model is unavailable,
    times out, or is rate-limited (HTTP 429), the student receives a verified
    grounded answer with degraded mode marked in metadata.
    """
    grounded = step.explanation if step else solution.answer_text
    q_key = _normalize_question_key(question)
    step_key = step.key if step else "all"
    cache_key = f"{solution.problem_latex}:{step_key}:{q_key}:{is_khmer}"
    if cache_key in _explanation_cache:
        return _explanation_cache[cache_key], None

    prompt_steps = "\n".join(
        f"{item.heading}: {item.explanation}"
        + (f" [written on the board: {item.latex}]" if item.latex else "")
        for item in solution.steps
    )
    # The shared client always asks the provider for JSON, so the answer is
    # requested as one JSON field rather than as prose.
    system_prompt = (
        "You are a patient Grade 12 maths teacher in Cambodia. Answer the "
        "student's question about one step of a solution that is already on "
        "the board. Rules: speak directly to the student in simple English; at "
        "most 3 short sentences; never contradict the solution; never invent "
        "numbers that are not in it; no markdown, no LaTeX, no code. "
        'Reply with JSON in exactly this shape: {"answer": "..."}'
    )
    user_prompt = (
        f"The solution on the board:\n{prompt_steps}\n\n"
        f"Final answer: {solution.answer_text}\n\n"
        + (f"The student is asking about: {step.heading}\n" if step else "")
        + f"Student's question: {question.strip()}\n\n"
        "Answer only that question."
    )
    try:
        from api.services.visual_tutor.llm_teaching_planner import _default_llm_client

        client = llm_client or _default_llm_client()
        reply = client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        cleaned = " ".join(_answer_text(reply).split())
        if cleaned and len(cleaned) <= 600 and not _looks_unsafe(cleaned):
            _explanation_cache[cache_key] = cleaned
            return cleaned, None
    except Exception as exc:
        exc_str = str(exc)
        if "429" in exc_str:
            reason = "rate_limited"
        elif isinstance(exc, (TimeoutError, httpx.TimeoutException)) or "timeout" in exc_str.lower():
            reason = "timeout"
        else:
            reason = "unavailable"
        logger.warning(
            "visual_tutor step explanation failed (%s: %s); entering degraded mode",
            type(exc).__name__,
            exc,
        )
        degraded_message = (
            f"{grounded} (ចំណាំ៖ គ្រូ AI កំពុងមានសិស្សច្រើន និងផ្ដល់ការពន្យល់ផ្ទៀងផ្ទាត់។)"
            if is_khmer
            else f"{grounded} (Note: AI visual tutor is experiencing high demand; showing verified step guidance.)"
        )
        return degraded_message, reason

    return grounded, None


def _answer_text(reply: Any) -> str:
    raw = str(reply or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if isinstance(payload, dict):
        for key in ("answer", "text", "explanation", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return ""
    return raw


def _looks_unsafe(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("<", "```", "http://", "https://", "\\frac", "function(")
    )


def solve_limit(problem: LimitOfFunctionProblem) -> WorkedSolution:
    cache_key = f"{problem.normalized_problem}:{getattr(problem, 'is_khmer', False)}"
    if cache_key in _worked_solution_cache:
        return _worked_solution_cache[cache_key]

    expression = _limit_sympy_expression(problem.function_expression)
    point = _limit_sympy_point(problem.target_point_display)
    direction = problem.requested_direction
    facts = _limit_computation_facts(expression, _X, point, direction)
    target = _sympy_value(facts.get("reported_value"))
    lim = _lim_latex(point, direction)
    problem_latex = f"{lim} {_limit_body(expression)}"
    answer_latex, answer_text = _answer(lim, expression, target, facts)

    steps: list[SolutionStep] = [
        SolutionStep(
            key="read",
            heading="Step 1 · Understand the question",
            explanation=_question_words(point, direction),
            latex=problem_latex,
        )
    ]
    method_steps: Optional[list[SolutionStep]] = None
    method = "table"
    if point in (sympy.oo, -sympy.oo):
        method_steps = _divide_by_highest_power(expression, point, lim, target)
        method = "divide_by_highest_power"
    else:
        substituted = _safe_subs(expression, point)
        if substituted is not None and substituted.is_finite and target is not None:
            method_steps = _direct_substitution(expression, point, lim, target)
            method = "direct_substitution"
        elif substituted is sympy.nan:
            method_steps = _factor_and_cancel(expression, point, lim, target)
            method = "factor_and_cancel"

    if method_steps is None:
        method = "table"
        method_steps = _table_reasoning(expression, point, direction, facts)

    steps.extend(method_steps)
    table = _table(facts, point, direction)
    if table is not None and method != "table":
        steps.append(
            SolutionStep(
                key="check",
                heading="Check with a table of values",
                explanation=_table_check_words(point, direction, facts),
                table=table,
            )
        )
    solution = WorkedSolution(
        problem_latex=problem_latex,
        answer_latex=answer_latex,
        answer_text=answer_text,
        steps=_numbered(steps),
        method=method,
    )
    _worked_solution_cache[cache_key] = solution
    return solution


def build_worked_solution_turn(
    request: VisualTutorTurnRequest,
    problem: LimitOfFunctionProblem,
    *,
    session_id: str,
) -> VisualTutorTurnResponse:
    solution = solve_limit(problem)
    return _solution_turn(
        request,
        problem,
        solution,
        session_id=session_id,
        message=(
            f"Here is the full solution, step by step. {solution.answer_text} "
            "Ask me about any step you want me to explain."
        ),
        task="Ask me about any step you'd like explained, or try another limit.",
    )


def _uses_khmer(request: VisualTutorTurnRequest, problem: Optional[LimitOfFunctionProblem] = None) -> bool:
    if getattr(problem, "is_khmer", False):
        return True
    lang = getattr(request, "language_mode", None)
    if hasattr(lang, "value"):
        lang = lang.value
    val = str(lang or request.metadata.get("language_mode") or "").strip().lower()
    if val in {"khmer", "km"}:
        return True
    locale = (request.locale or "").lower()
    if locale.startswith("km"):
        return True
    return False


def _solution_turn(
    request: VisualTutorTurnRequest,
    problem: LimitOfFunctionProblem,
    solution: WorkedSolution,
    *,
    session_id: str,
    message: str,
    task: str,
    extra_sections: Optional[list[SolutionStep]] = None,
    focus_section: Optional[str] = None,
    extra_metadata: Optional[dict[str, Any]] = None,
) -> VisualTutorTurnResponse:
    """The solution on the board, optionally with a reply written after it.

    The whole solution is re-sent with every follow-up so the step being
    discussed stays in front of the student instead of being replaced by a
    bare answer.
    """
    is_khmer = _uses_khmer(request, problem)
    effective_task = task
    if is_khmer:
        effective_task = "សួរខ្ញុំអំពីជំហានណាមួយ ឬសុំឱ្យពន្យល់តាមរបៀបផ្សេង។"

    effective_message = message
    if is_khmer:
        effective_message = "នេះជាដំណោះស្រាយលម្អិតមួយជំហានម្តងៗ។ អ្នកអាចសួរអំពីជំហានណាមួយដែលចង់ឱ្យពន្យល់បន្ថែមបាន។"

    turn_id = str(uuid.uuid4())
    actions: list[VisualTutorBoardAction] = []
    plan_actions: list[dict[str, Any]] = []

    def add(action_type: VisualTutorCanvasActionType, section: str, **fields: Any) -> None:
        index = len(actions)
        action_id = f"ws-{section}-{index}"
        zone = fields.pop("layout_zone", "working")
        actions.append(
            VisualTutorBoardAction(
                id=action_id,
                type=action_type,
                sequence_index=index,
                duration_ms=fields.pop("duration_ms", 450),
                layout_zone=zone,
                layout_flow="vertical",
                section_id=section,
                **{key: value for key, value in fields.items() if key != "table"},
                **({"table": fields["table"]} if "table" in fields else {}),
            )
        )
        item: dict[str, Any] = {
            "id": action_id,
            "type": action_type.value,
            "sequence_index": index,
            "duration_ms": actions[-1].duration_ms,
            "layout_zone": zone,
            "layout_flow": "vertical",
            "section_id": section,
        }
        for key in ("text", "latex", "table", "requires_student_response", "task_type"):
            if key in fields and fields[key] is not None:
                item[key] = fields[key]
        plan_actions.append(item)

    for step in solution.steps:
        section = f"step-{step.key}"
        add(VisualTutorCanvasActionType.WRITE_TEXT, section, text=f"{step.heading}. {step.explanation}")
        if step.latex:
            add(VisualTutorCanvasActionType.WRITE_EQUATION, section, latex=step.latex, duration_ms=550)
        if step.table:
            add(
                VisualTutorCanvasActionType.SHOW_TABLE,
                section,
                table=step.table,
                duration_ms=700,
                # Required by the legacy board model only; the public plan drops
                # geometry and lets Flutter lay the table out.
                width=420,
                height=40 + 28 * len(step.table["rows"]),
            )
    # Written as an ordinary heading + equation, not final_answer_reveal: the
    # server contract forbids a student task alongside a reveal while the
    # Flutter contract requires exactly one task, so a reveal could never
    # coexist with the "ask me about any step" prompt below.
    answer_label = "ចម្លើយ" if is_khmer else "Answer"
    add(VisualTutorCanvasActionType.WRITE_TEXT, "answer", text=f"{answer_label} · {solution.answer_text}")
    add(
        VisualTutorCanvasActionType.WRITE_EQUATION,
        "answer",
        latex=solution.answer_latex,
        duration_ms=600,
    )
    # A reply is written under the finished solution, the way a teacher answers
    # a question in the space below their working.
    for reply in extra_sections or []:
        add(
            VisualTutorCanvasActionType.WRITE_TEXT,
            f"reply-{reply.key}",
            text=f"{reply.heading}. {reply.explanation}",
        )
    add(
        VisualTutorCanvasActionType.STUDENT_TASK,
        "next",
        layout_zone="student_task",
        text=effective_task,
        requires_student_response=True,
        task_type="conceptual_operation",
        duration_ms=0,
    )

    plan = validate_teaching_plan(
        {
            "schema_version": 1,
            "representation": "worked_example",
            "learning_objective": "យល់គ្រប់ជំហានក្នុងការរកដែនកំណត់នេះ" if is_khmer else "Understand every step of finding this limit, and why each step is allowed.",
            "teaching_message": effective_message,
            "board_actions": plan_actions,
            "allowed_student_actions": ["submit_answer", "explain_differently", "request_hint"],
            "hidden_answer_policy": {
                "mode": "reveal_allowed",
                "deterministic_policy_permits_final_reveal": True,
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
    ).model_dump(mode="json")
    evidence = "Checked two ways: the algebra and a table of values agree."
    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=turn_id,
        screen_state=VisualTutorScreenState.ASKING_QUESTION,
        tutor_status="Waiting for you",
        spoken_text=effective_message,
        display_text=effective_message,
        teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
        final_answer_locked=False,
        student_task=effective_task,
        board=VisualTutorBoard(
            type=VisualTutorBoardType.EQUATION_STEPS,
            title="ដំណោះស្រាយលម្អិត" if is_khmer else "Worked solution",
            items=[
                VisualTutorBoardItem(label=step.heading, content=step.explanation, status="done")
                for step in solution.steps
            ],
            metadata={"worked_solution": True},
        ),
        board_actions=actions,
        speech=VisualTutorSpeech(text=effective_message, language="km" if is_khmer else "en"),
        interaction=VisualTutorInteraction(
            type=VisualTutorInteractionType.TEXT_RESPONSE,
            prompt=task,
            expected_answer_locked=False,
            input_enabled=True,
        ),
        allowed_actions=[
            VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
            VisualTutorAllowedAction.SUBMIT_ANSWER,
        ],
        quick_actions=[VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY],
        mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
        authoritative_lesson_state={
            "active_step_id": "worked-solution",
            "current_step_index": len(solution.steps),
            "final_answer_locked": False,
        },
        metadata={
            "teaching_plan": plan,
            "worked_solution": {
                "problem": problem.normalized_problem,
                "method": solution.method,
                "answer": solution.answer_text,
                "steps": [
                    {
                        "section_id": f"step-{step.key}",
                        "heading": step.heading,
                        "explanation": step.explanation,
                        "latex": step.latex,
                    }
                    for step in solution.steps
                ],
            },
            "verified": True,
            "curriculum_status": "verified_curriculum",
            "curriculum_topic": "Limits of Functions",
            "verification": {
                "status": "correct",
                "verified": True,
                "student_message": evidence,
                "concise_evidence": "Verified",
            },
            "verification_result": "correct",
            "board_update_mode": "replace",
            "problem_text": problem.original,
            **({"discussing_section_id": focus_section} if focus_section else {}),
            **({"solver_facts": facts} if (facts := _solver_facts(request)) else {}),
            **(extra_metadata or {}),
        },
    )


# ── algebraic routes ────────────────────────────────────────────────────────


def _direct_substitution(expression, point, lim, target) -> Optional[list[SolutionStep]]:
    value = _safe_subs(expression, point)
    if value is None or not _same(value, target):
        return None
    return [
        SolutionStep(
            key="substitute",
            heading="Step 2 · Substitute directly",
            explanation=(
                f"Putting x = {_plain(point)} into f(x) does not divide by zero, "
                "so the function is continuous there and we can simply substitute."
            ),
            latex=_chain(
                f"{lim} {_limit_body(expression)}",
                _substituted_latex(expression, point),
                sympy.latex(value),
            ),
        )
    ]


def _factor_and_cancel(expression, point, lim, target) -> Optional[list[SolutionStep]]:
    numerator, denominator = sympy.fraction(sympy.together(expression))
    if denominator == 1 or not (numerator.is_polynomial(_X) and denominator.is_polynomial(_X)):
        return None
    common = sympy.gcd(numerator, denominator)
    if common.is_number:
        return None
    simplified = sympy.cancel(expression)
    value = _safe_subs(simplified, point)
    if value is None or not value.is_finite or not _same(value, target):
        return None
    factored = sympy.Mul(
        sympy.factor(numerator), sympy.Pow(sympy.factor(denominator), -1, evaluate=False),
        evaluate=False,
    )
    return [
        SolutionStep(
            key="try",
            heading="Step 2 · Try substituting first",
            explanation=(
                f"Putting x = {_plain(point)} in gives 0/0. This is called an "
                "indeterminate form. It does not mean the answer is 0 — it tells "
                "us to simplify the expression before substituting."
            ),
            latex=(
                f"\\frac{{{_substituted_latex(numerator, point)}}}"
                f"{{{_substituted_latex(denominator, point)}}} = \\frac{{0}}{{0}}"
            ),
        ),
        SolutionStep(
            key="factor",
            heading="Step 3 · Factor the top and bottom",
            explanation=(
                f"{_factor_hint(numerator, denominator)} Both parts share the "
                f"factor ({_plain(common)}), which is exactly what makes 0/0."
            ),
            latex=f"{sympy.latex(expression)} = {sympy.latex(factored)}",
        ),
        SolutionStep(
            key="cancel",
            heading="Step 4 · Cancel the common factor",
            explanation=(
                f"We can cancel ({_plain(common)}) because x only gets close to "
                f"{_plain(point)} and never equals it, so ({_plain(common)}) is "
                "never zero."
            ),
            latex=f"{sympy.latex(expression)} = {sympy.latex(simplified)}, \\quad x \\neq {sympy.latex(point)}",
        ),
        SolutionStep(
            key="substitute",
            heading="Step 5 · Substitute into the simpler expression",
            explanation=(
                f"The simplified expression has no problem at x = {_plain(point)}, "
                "so now substitution works."
            ),
            latex=_chain(
                f"{lim} {_limit_body(simplified)}",
                _substituted_latex(simplified, point),
                sympy.latex(value),
            ),
        ),
    ]


def _divide_by_highest_power(expression, point, lim, target) -> Optional[list[SolutionStep]]:
    numerator, denominator = sympy.fraction(sympy.together(expression))
    if denominator == 1 or not (numerator.is_polynomial(_X) and denominator.is_polynomial(_X)):
        return None
    degree = sympy.degree(denominator, _X)
    if degree < 1:
        return None
    power = _X**degree
    top = sympy.expand(numerator / power)
    bottom = sympy.expand(denominator / power)
    if bottom == 1:
        # e.g. 1/x: dividing by x only rewrites it as (1/x)/1, which teaches
        # nothing -- the table route says it more plainly.
        return None
    top_limit = sympy.limit(top, _X, point)
    bottom_limit = sympy.limit(bottom, _X, point)
    if not (top_limit.is_finite and bottom_limit.is_finite) or bottom_limit == 0:
        return None
    value = sympy.simplify(top_limit / bottom_limit)
    if not _same(value, target):
        return None
    return [
        SolutionStep(
            key="divide",
            heading=f"Step 2 · Divide top and bottom by {_plain(power)}",
            explanation=(
                f"For a fraction as x → ∞, divide every term by the highest power "
                f"of x in the bottom, which is {_plain(power)}. This does not change "
                "the value of the fraction."
            ),
            latex=f"{sympy.latex(expression)} = \\frac{{{sympy.latex(top)}}}{{{sympy.latex(bottom)}}}",
        ),
        SolutionStep(
            key="shrink",
            heading="Step 3 · Let x grow very large",
            explanation=(
                "Every term with x in its denominator gets closer and closer to 0 "
                "as x gets huge, so only the constant terms are left."
            ),
            latex=_chain(
                f"{lim} \\frac{{{sympy.latex(top)}}}{{{sympy.latex(bottom)}}}",
                f"\\frac{{{sympy.latex(top_limit)}}}{{{sympy.latex(bottom_limit)}}}",
                sympy.latex(value),
            ),
        ),
    ]


def _table_reasoning(expression, point, direction, facts) -> list[SolutionStep]:
    steps: list[SolutionStep] = []
    if point not in (sympy.oo, -sympy.oo):
        substituted = _safe_subs(expression, point)
        if substituted is sympy.nan:
            what = "0/0, an indeterminate form, so substitution alone cannot tell us the limit"
        elif substituted is None or not substituted.is_finite:
            what = "a division by zero, so f(x) is not defined at that point"
        else:
            what = f"{_plain(substituted)}, but the limit depends on nearby values, not the value at the point"
        steps.append(
            SolutionStep(
                key="try",
                heading="Step 2 · Try substituting first",
                explanation=f"Putting x = {_plain(point)} in gives {what}.",
            )
        )
    steps.append(
        SolutionStep(
            key="table",
            heading="Look at a table of values",
            explanation=_table_check_words(point, direction, facts),
            table=_table(facts, point, direction),
        )
    )
    return steps


# ── wording and formatting helpers ──────────────────────────────────────────


def _numbered(steps: list[SolutionStep]) -> list[SolutionStep]:
    numbered: list[SolutionStep] = []
    for number, step in enumerate(steps, start=1):
        heading = step.heading.split("·", 1)[-1].strip()
        numbered.append(
            SolutionStep(
                key=step.key,
                heading=f"Step {number} · {heading}",
                explanation=step.explanation,
                latex=step.latex,
                table=step.table,
            )
        )
    return numbered


def _answer(lim: str, expression, target, facts) -> tuple[str, str]:
    classification = facts.get("classification")
    body = f"{lim} {_limit_body(expression)}"
    if target is not None and target.is_finite:
        return f"{body} = {sympy.latex(target)}", f"The limit is {_plain(target)}."
    if target in (sympy.oo, -sympy.oo):
        return (
            f"{body} = {sympy.latex(target)}",
            f"f(x) grows without bound, so the limit is {'∞' if target == sympy.oo else '−∞'}.",
        )
    if classification == "does_not_exist":
        return f"{body} \\text{{ does not exist}}", "The limit does not exist."
    return f"{body} \\text{{ does not exist}}", "The limit does not exist."


def _table_check_words(point, direction, facts) -> str:
    left = _sympy_value(facts.get("left_value"))
    right = _sympy_value(facts.get("right_value"))
    if point in (sympy.oo, -sympy.oo):
        value = _sympy_value(facts.get("limit_value"))
        if value is not None and value.is_finite:
            return f"As x gets larger and larger, f(x) gets closer and closer to {_plain(value)}."
        return "As x gets larger and larger, f(x) does not settle on one number."
    if direction in ("left", "right"):
        # A one-sided question is answered by that side alone; mentioning the
        # other side would contradict its (valid) one-sided answer.
        value = left if direction == "left" else right
        approach = f"As x gets closer to {_plain(point)} from the {direction}"
        if value is not None and value.is_finite:
            return f"{approach}, f(x) gets closer and closer to {_plain(value)}."
        if value == -sympy.oo:
            return f"{approach}, f(x) becomes more and more negative without stopping."
        if value == sympy.oo:
            return f"{approach}, f(x) becomes larger and larger without stopping."
        return f"{approach}, f(x) does not settle on one number."
    if left is not None and right is not None and _same(left, right) and left.is_finite:
        return (
            f"From the left and from the right of x = {_plain(point)}, f(x) gets "
            f"closer to {_plain(left)} — both sides agree."
        )
    if left is not None and right is not None and not _same(left, right):
        return (
            f"From the left f(x) approaches {_plain(left)}, but from the right it "
            f"approaches {_plain(right)}. The two sides do not agree, so the "
            "two-sided limit does not exist."
        )
    return f"Near x = {_plain(point)}, f(x) grows without bound instead of settling on a number."


def _factor_hint(numerator, denominator) -> str:
    for part in (numerator, denominator):
        poly = sympy.Poly(part, _X)
        if poly.degree() != 2:
            continue
        a, b, c = poly.all_coeffs()
        if b == 0 and a > 0 and c < 0:
            return f"{_plain(part)} is a difference of squares: a² − b² = (a − b)(a + b)."
        if a == 1:
            roots = [root for root, count in sympy.roots(poly).items() for _ in range(count)]
            if len(roots) == 2 and all(root.is_integer for root in roots):
                first, second = -roots[0], -roots[1]
                return (
                    f"To factor {_plain(part)}, find two numbers that multiply to "
                    f"{_plain(c)} and add to {_plain(b)}: they are {_plain(first)} "
                    f"and {_plain(second)}."
                )
    return "Factor each part so we can see what they have in common."


def _table(facts, point, direction) -> Optional[dict[str, list[Any]]]:
    raw = facts.get("table")
    if not isinstance(raw, dict) or not raw.get("rows"):
        return None
    entries = []
    for row in raw["rows"]:
        x_value = _sympy_value(row.get("x"))
        if x_value is None or not x_value.is_finite:
            continue
        if direction == "left" and not x_value < point:
            continue
        if direction == "right" and not x_value > point:
            continue
        entries.append((x_value, [_decimal(row.get("x")), _decimal(row.get("f_x"))]))
    # Ascending x reads as "approaching from the left, then from the right",
    # which is how a teacher builds this table on the board.
    entries.sort(key=lambda entry: float(entry[0]))
    rows = [cells for _, cells in entries][:10]
    return {"columns": ["x", "f(x)"], "rows": rows} if rows else None


def _decimal(raw: Any) -> str:
    text = str(raw)
    try:
        value = sympy.Rational(text)
    except (TypeError, ValueError, sympy.SympifyError):
        return text
    formatted = f"{float(value):.6f}".rstrip("0").rstrip(".")
    return formatted or "0"


def _lim_latex(point, direction) -> str:
    side = "^{-}" if direction == "left" else "^{+}" if direction == "right" else ""
    return f"\\lim_{{x \\to {sympy.latex(point)}{side}}}"


def _question_words(point, direction) -> str:
    if point == sympy.oo:
        return (
            "We want to know what value f(x) gets closer and closer to as x grows "
            "larger and larger. x never reaches infinity — we look at the trend."
        )
    if point == -sympy.oo:
        return (
            "We want to know what value f(x) gets closer and closer to as x becomes "
            "more and more negative. We look at the trend, not one value."
        )
    side = " from the left (values just below it)" if direction == "left" else (
        " from the right (values just above it)" if direction == "right" else ""
    )
    return (
        f"We want to know what value f(x) gets closer and closer to as x gets "
        f"closer to {_plain(point)}{side}. x does not have to equal "
        f"{_plain(point)} — we look at values near it."
    )


def _limit_body(expression) -> str:
    latex = sympy.latex(expression)
    return f"\\left({latex}\\right)" if isinstance(expression, sympy.Add) else latex


def _chain(*parts: str) -> str:
    """Join an equality chain, dropping a link that repeats the one before it
    (e.g. "3/2 = 3/2")."""
    kept: list[str] = []
    for part in parts:
        if not kept or kept[-1].replace(" ", "") != part.replace(" ", ""):
            kept.append(part)
    return " = ".join(kept)


def _substituted_latex(expression, point) -> str:
    """The expression with the point written in place of x, keeping the order
    a student wrote it in ("3^2 - 9", not sympy's canonical "-9 + 3^2")."""
    value = sympy.latex(point)
    if point.is_negative or "frac" in value:
        value = f"\\left({value}\\right)"
    latex = sympy.latex(expression)

    def replace(match: re.Match[str]) -> str:
        before = latex[: match.start()].rstrip()
        # "2 x" was implicit multiplication; once x is a number it needs a dot.
        if before and (before[-1].isdigit() or before[-1] in "})"):
            return f"\\cdot {value}"
        return value

    return _X_TOKEN_RE.sub(replace, latex)


def _safe_subs(expression, point):
    try:
        return sympy.simplify(expression.subs(_X, point))
    except Exception:
        return None


def _same(left, right) -> bool:
    if left is None or right is None:
        return False
    try:
        return bool(sympy.simplify(left - right) == 0)
    except Exception:
        return left == right


def _sympy_value(raw: Any):
    if raw is None:
        return None
    try:
        return sympy.sympify(raw)
    except (sympy.SympifyError, TypeError):
        return None


def _plain(expression) -> str:
    text = sympy.sstr(expression)
    for power, glyph in (("**2", "²"), ("**3", "³"), ("**4", "⁴")):
        text = text.replace(power, glyph)
    text = text.replace("oo", "∞").replace("*", "").replace("-", "−")
    return text
