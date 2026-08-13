from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Optional, Protocol

import sympy

from api.models.visual_tutor import (
    CanvasElementStyle,
    VisualTutorAllowedAction,
    VisualTutorBoardAction,
    VisualTutorCanvasAction,
    VisualTutorCanvasActionType,
    VisualTutorAction,
    VisualTutorBoard,
    VisualTutorBoardItem,
    VisualTutorBoardType,
    VisualTutorInteraction,
    VisualTutorInteractionType,
    VisualTutorInputUnderstandingResult,
    VisualTutorMasterySignal,
    VisualTutorProblemUnderstandingResult,
    VisualTutorSolverFacts,
    VisualTutorStudentValidationFacts,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
)
from api.services.visual_tutor.policy import (
    VisualTutorPolicyDecision,
    decide_visual_tutor_policy,
)


class VisualTutorSolver(Protocol):
    def can_handle(
        self, understanding: VisualTutorProblemUnderstandingResult
    ) -> bool: ...

    def build_initial_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_hint_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_stuck_help_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_explain_differently_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def check_student_step(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_partial_solution(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_full_solution(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_next_teaching_move(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def validate_student_response(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> dict[str, Any]: ...

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts: ...

    def build_wrong_input_feedback(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_stuck_visual_help(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...

    def build_progressive_answer_reveal(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse: ...


class LiveTeacherMoveMixin:
    """Adapter layer that exposes live-teacher semantics for existing solvers."""

    def build_next_teaching_move(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        if request.action == VisualTutorAction.REQUEST_FINAL_ANSWER:
            return self.build_progressive_answer_reveal(
                request, understanding, policy, session_id=session_id
            )
        if policy.stuck_help:
            return self.build_stuck_visual_help(
                request, understanding, policy, session_id=session_id
            )
        if policy.explain_differently:
            return self.build_explain_differently_turn(
                request, understanding, policy, session_id=session_id
            )
        if policy.should_redirect_input or policy.diagnose_misconception:
            return self.build_wrong_input_feedback(
                request, understanding, policy, session_id=session_id
            )
        if policy.should_check_step or request.student_submitted_step:
            return self.check_student_step(
                request, understanding, policy, session_id=session_id
            )
        if policy.give_hint or request.action == VisualTutorAction.REQUEST_HINT:
            return self.build_hint_turn(
                request, understanding, policy, session_id=session_id
            )
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        return self.build_initial_turn(
            request, understanding, policy, session_id=session_id
        )

    def validate_student_response(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> dict[str, Any]:
        input_understanding = _input_understanding_from_policy(policy)
        return {
            "student_intent": policy.metadata.get("student_intent"),
            "input_relevance": (
                policy.input_relevance.value if policy.input_relevance else None
            ),
            "validation_result": policy.validation_result,
            "misconception_type": policy.misconception_type,
            "expected_step": policy.metadata.get("expected_step"),
            "problem_type": understanding.problem_type,
            "extracted_math": (
                input_understanding.extracted_math if input_understanding else None
            ),
            "extracted_numbers": (
                input_understanding.extracted_numbers if input_understanding else []
            ),
            "metadata": {
                "policy_reason": policy.reason,
                "client_action": request.action.value,
            },
        }

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts:
        validation = self.validate_student_response(request, understanding, policy)
        return VisualTutorSolverFacts(
            solver_name=self.__class__.__name__,
            problem_type=understanding.problem_type,
            normalized_problem=(
                request.current_state.normalized_problem
                or understanding.extracted_problem
            ),
            current_step_index=request.current_state.current_step_index,
            expected_step=_string_or_none(validation.get("expected_step")),
            student_validation=_validation_facts_from_policy(policy, validation),
            metadata={
                "problem_understanding": understanding.model_dump(mode="json"),
                "validation": validation,
            },
        )

    def build_wrong_input_feedback(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        return self.check_student_step(
            request, understanding, policy, session_id=session_id
        )

    def build_stuck_visual_help(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        return self.build_stuck_help_turn(
            request, understanding, policy, session_id=session_id
        )

    def build_progressive_answer_reveal(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        if policy.reveal_final or policy.full_solution_allowed:
            return self.build_full_solution(
                request, understanding, policy, session_id=session_id
            )
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        locked_turn_builder = getattr(self, "build_final_locked_turn", None)
        if callable(locked_turn_builder):
            return locked_turn_builder(
                request, understanding, policy, session_id=session_id
            )
        return self.build_hint_turn(
            request, understanding, policy, session_id=session_id
        )


@dataclass(frozen=True)
class LinearEquation:
    original: str
    normalized: str
    variable: str
    symbol: sympy.Symbol
    lhs: sympy.Expr
    rhs_expr: sympy.Expr
    lhs_coefficient: sympy.Expr
    rhs_coefficient: sympy.Expr
    lhs_constant: sympy.Expr
    rhs_constant: sympy.Expr
    coefficient: sympy.Expr
    constant: sympy.Expr
    rhs: sympy.Expr
    first_step_rhs: sympy.Expr
    solution: sympy.Expr
    operation_text: str

    @property
    def first_step_equation(self) -> str:
        return (
            f"{_format_linear_term(self.coefficient, self.variable)} = "
            f"{_format_expr(self.first_step_rhs)}"
        )

    @property
    def final_equation(self) -> str:
        return f"{self.variable} = {_format_expr(self.solution)}"


@dataclass(frozen=True)
class LineThroughPoints:
    original: str
    normalized: str
    first_label: str
    second_label: str
    x1: sympy.Expr
    y1: sympy.Expr
    x2: sympy.Expr
    y2: sympy.Expr
    slope: sympy.Expr
    intercept: sympy.Expr

    @property
    def delta_y(self) -> sympy.Expr:
        return sympy.simplify(self.y2 - self.y1)

    @property
    def delta_x(self) -> sympy.Expr:
        return sympy.simplify(self.x2 - self.x1)

    @property
    def slope_step(self) -> str:
        return (
            f"m = ({_format_expr(self.y2)} - {_format_expr(self.y1)}) / "
            f"({_format_expr(self.x2)} - {_format_expr(self.x1)}) = "
            f"{_format_expr(self.slope)}"
        )

    @property
    def point_slope_step(self) -> str:
        return (
            f"y - {_format_expr(self.y1)} = {_format_expr(self.slope)}"
            f"(x - {_format_expr(self.x1)})"
        )

    @property
    def final_equation(self) -> str:
        if self.intercept == 0:
            return f"y = {_format_expr(self.slope)}x"
        sign = "+" if self.intercept > 0 else "-"
        return f"y = {_format_expr(self.slope)}x {sign} {_format_expr(abs(self.intercept))}"


def parse_linear_equation(message: str) -> Optional[LinearEquation]:
    equation_text = _extract_equation_text(message)
    if not equation_text:
        return None

    normalized = _normalize_math_text(equation_text)
    try:
        lhs_raw, rhs_raw = normalized.split("=", 1)
        lhs = _sympify_math_expr(lhs_raw.strip())
        rhs = _sympify_math_expr(rhs_raw.strip())
        symbols = sorted(
            lhs.free_symbols | rhs.free_symbols, key=lambda item: item.name
        )
        if len(symbols) != 1:
            return None
        variable_symbol = symbols[0]
        expr = sympy.expand(lhs - rhs)
        polynomial = sympy.Poly(expr, variable_symbol)
    except Exception:
        return None

    if polynomial.degree() != 1:
        return None

    coefficient = polynomial.coeff_monomial(variable_symbol)
    if coefficient == 0:
        return None

    try:
        lhs_expanded = sympy.expand(lhs)
        rhs_expanded = sympy.expand(rhs)
        lhs_poly = sympy.Poly(lhs_expanded, variable_symbol)
        rhs_poly = sympy.Poly(rhs_expanded, variable_symbol)
        lhs_coefficient = sympy.simplify(lhs_poly.coeff_monomial(variable_symbol))
        rhs_coefficient = sympy.simplify(rhs_poly.coeff_monomial(variable_symbol))
        lhs_constant = sympy.simplify(lhs_poly.coeff_monomial(1))
        rhs_constant = sympy.simplify(rhs_poly.coeff_monomial(1))
    except Exception:
        return None
    rhs_has_variable = variable_symbol in rhs_expanded.free_symbols
    lhs_has_only_one_linear_term = (
        variable_symbol in lhs_expanded.free_symbols and lhs_poly.degree() <= 1
    )

    if rhs_has_variable or not lhs_has_only_one_linear_term:
        constant = polynomial.coeff_monomial(1)
        rhs = sympy.Integer(0)
        first_step_rhs = sympy.simplify(-constant)
        operation_text = _collect_terms_operation_text(
            variable_symbol.name,
            rhs_coefficient,
            lhs_constant,
        )
    else:
        coefficient = lhs_coefficient
        constant = lhs_constant
        first_step_rhs = sympy.simplify(rhs - constant)
        operation_text = _inverse_constant_operation_text(constant)
    solution = sympy.simplify(first_step_rhs / coefficient)

    if sympy.simplify(expr.subs(variable_symbol, solution)) != 0:
        return None

    return LinearEquation(
        original=equation_text,
        normalized=normalized,
        variable=variable_symbol.name,
        symbol=variable_symbol,
        lhs=lhs_expanded,
        rhs_expr=rhs_expanded,
        lhs_coefficient=lhs_coefficient,
        rhs_coefficient=rhs_coefficient,
        lhs_constant=lhs_constant,
        rhs_constant=rhs_constant,
        coefficient=coefficient,
        constant=constant,
        rhs=rhs,
        first_step_rhs=first_step_rhs,
        solution=solution,
        operation_text=operation_text,
    )


def parse_line_through_points(message: str) -> Optional[LineThroughPoints]:
    if not re.search(r"\b(line|equation|through|passes)\b", message, re.IGNORECASE):
        return None

    matches = re.findall(
        r"\b([A-Za-z])?\s*\(\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*\)",
        message,
    )
    return _line_from_point_matches(matches)


def parse_line_through_points_from_understanding(
    understanding: VisualTutorProblemUnderstandingResult,
) -> Optional[LineThroughPoints]:
    points = understanding.extracted_entities.get("points")
    if not isinstance(points, list) or len(points) < 2:
        return None
    matches = [
        (
            str(point.get("label") or ""),
            str(point.get("x") or ""),
            str(point.get("y") or ""),
        )
        for point in points[:2]
        if isinstance(point, dict)
    ]
    return _line_from_point_matches(matches)


def _line_from_point_matches(
    matches: list[tuple[str, str, str]],
) -> Optional[LineThroughPoints]:
    if len(matches) < 2:
        return None

    first_label_raw, x1_raw, y1_raw = matches[0]
    second_label_raw, x2_raw, y2_raw = matches[1]
    try:
        x1 = sympy.Rational(x1_raw)
        y1 = sympy.Rational(y1_raw)
        x2 = sympy.Rational(x2_raw)
        y2 = sympy.Rational(y2_raw)
    except Exception:
        return None
    if x1 == x2:
        return None

    slope = sympy.simplify((y2 - y1) / (x2 - x1))
    intercept = sympy.simplify(y1 - slope * x1)
    first_label = first_label_raw or "A"
    second_label = second_label_raw or "B"
    original = (
        f"{first_label}({_format_expr(x1)},{_format_expr(y1)}) and "
        f"{second_label}({_format_expr(x2)},{_format_expr(y2)})"
    )
    return LineThroughPoints(
        original=original,
        normalized=(
            "line_through_points:"
            f"({_format_expr(x1)},{_format_expr(y1)}),"
            f"({_format_expr(x2)},{_format_expr(y2)})"
        ),
        first_label=first_label,
        second_label=second_label,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        slope=slope,
        intercept=intercept,
    )


class LinearEquationSolver(LiveTeacherMoveMixin):
    problem_type = "linear_equation_one_variable"

    def can_handle(self, understanding: VisualTutorProblemUnderstandingResult) -> bool:
        return understanding.problem_type == self.problem_type

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts:
        equation = self._equation(request, understanding)
        validation = _linear_student_validation_facts(request, equation, policy)
        current_step_index = request.current_state.current_step_index
        expected_equation = (
            equation.first_step_equation
            if current_step_index <= 0
            else equation.final_equation
        )
        expected_operation = (
            equation.operation_text
            if current_step_index <= 0
            else f"divide both sides by {_format_expr(equation.coefficient)}"
        )
        return VisualTutorSolverFacts(
            solver_name=self.__class__.__name__,
            problem_type=self.problem_type,
            normalized_problem=equation.normalized,
            variable=equation.variable,
            known_solution=equation.final_equation,
            current_step_index=current_step_index,
            expected_step=(
                "remove the constant or collect like terms"
                if current_step_index <= 0
                else f"isolate {equation.variable}"
            ),
            expected_operation=expected_operation,
            expected_equation=expected_equation,
            student_validation=validation,
            verified_answer=equation.final_equation,
            sympy_verified=True,
            next_concept=(
                f"isolate {equation.variable}"
                if current_step_index <= 0
                else "verify by substitution"
            ),
            safe_formulas=[
                "Keep both sides balanced by doing the same operation to each side.",
                "Use inverse operations to isolate the variable.",
            ],
            board_context={
                "problem": equation.original,
                "first_step_equation": equation.first_step_equation,
                "final_equation": equation.final_equation,
                "coefficient": _format_expr(equation.coefficient),
                "constant": _format_expr(equation.constant),
            },
            metadata={
                "operation_text": equation.operation_text,
                "lhs_coefficient": _format_expr(equation.lhs_coefficient),
                "rhs_coefficient": _format_expr(equation.rhs_coefficient),
                "lhs_constant": _format_expr(equation.lhs_constant),
                "rhs_constant": _format_expr(equation.rhs_constant),
                "policy_reason": policy.reason,
            },
        )

    def build_initial_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        equation = self._equation(request, understanding)
        use_khmer = policy.use_khmer_explanation
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                f"Good problem. Before solving, what first move helps us simplify it?",
                "លំហាត់ល្អ។ មុនដោះស្រាយ តើជំហានដំបូងណាអាចធ្វើឱ្យសមីការងាយជាងមុន?",
            ),
            display_text=_localized_task(
                use_khmer,
                "Let's solve this like a teacher: one small step first.",
                "យើងដោះស្រាយបែបគ្រូបង្រៀន៖ មួយជំហានតូចជាមុន។",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                "Tell me the first operation. Do not calculate the final answer yet.",
                "ប្រាប់គ្រូពីប្រមាណវិធីដំបូង។ កុំគណនាចម្លើយចុងក្រោយនៅឡើយ។",
            ),
            board=_build_linear_board(equation, active_step=0),
            board_actions=_linear_live_actions(equation, focus="constant"),
            interaction=_solver_interaction(
                _localized_task(
                    use_khmer,
                    f"What first move should we use: {equation.operation_text}?",
                    f"តើជំហានដំបូងគួរធ្វើអ្វី៖ {equation.operation_text}?",
                ),
                policy=policy,
            ),
            allowed_actions=_solver_allowed_actions(policy),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(equation.normalized, request, policy),
        )

    def build_hint_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        equation = self._equation(request, understanding)
        use_khmer = policy.use_khmer_explanation
        if request.current_state.current_step_index >= 1:
            variable = equation.variable
            return VisualTutorTurnResponse(
                session_id=session_id,
                turn_id=str(uuid.uuid4()),
                spoken_text=_localized_task(
                    use_khmer,
                    f"Let's focus on the current step. You already simplified the equation, so now isolate {variable} by dividing both sides by the coefficient.",
                    f"យើងផ្តោតលើជំហានបច្ចុប្បន្ន។ អ្នកបានធ្វើឱ្យសមីការងាយជាងមុនហើយ ដូច្នេះឥឡូវដោះស្រាយរក {variable} ដោយចែកទាំងពីរខាងដោយមេគុណ។",
                ),
                display_text=_localized_task(
                    use_khmer,
                    f"Small hint: continue from {equation.first_step_equation}. Divide both sides by {_format_expr(equation.coefficient)}.",
                    f"គន្លឹះតូច៖ បន្តពី {equation.first_step_equation}។ ចែកទាំងពីរខាងដោយ {_format_expr(equation.coefficient)}។",
                ),
                teaching_mode=policy.teaching_mode,
                final_answer_locked=policy.final_answer_locked,
                student_task=_localized_task(
                    use_khmer,
                    f"What operation isolates {variable} in {equation.first_step_equation}?",
                    f"តើប្រមាណវិធីអ្វីអាចដោះស្រាយរក {variable} ក្នុង {equation.first_step_equation}?",
                ),
                board=_build_linear_board(
                    equation,
                    active_step=1,
                    reveal_partial=True,
                    reveal_final=policy.reveal_final,
                    feedback="stuck_help",
                ),
                board_actions=_linear_isolate_x_hint_actions(equation),
                mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
                metadata=_metadata(None, request, policy),
            )
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                f"Hint: {equation.operation_text} first.",
                f"គន្លឹះ៖ ដំបូង {equation.operation_text}។",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Hint: {equation.operation_text}.",
                f"គន្លឹះ៖ {equation.operation_text}។",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                "Write the equation after that operation.",
                "សរសេរសមីការបន្ទាប់ពីធ្វើប្រមាណវិធីនោះ។",
            ),
            board=_build_linear_board(
                equation,
                active_step=0,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def check_student_step(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        equation = self._equation(request, understanding)
        if policy.validation_result in {
            "understanding_check_yes",
            "understanding_check_no",
        }:
            return self._understanding_check_turn(request, equation, policy, session_id)

        is_correct_final = request.current_state.current_step_index >= 1 and (
            policy.validation_result == "correct_final_step"
            or _equations_equivalent(request.message, equation.final_equation)
        )
        if is_correct_final:
            final_policy = decide_visual_tutor_policy(
                request,
                has_problem=True,
                is_correct_step=True,
                problem_type=self.problem_type,
                known_solver_available=True,
                input_understanding=_input_understanding_from_policy(policy),
            )
            return self._final_step_turn(request, equation, final_policy, session_id)

        is_correct_step = (
            policy.validation_result == "correct_operation"
            or _equations_equivalent(request.message, equation.first_step_equation)
        )
        step_policy = decide_visual_tutor_policy(
            request,
            has_problem=True,
            is_correct_step=is_correct_step,
            problem_type=self.problem_type,
            known_solver_available=True,
            input_understanding=_input_understanding_from_policy(policy),
        )
        if is_correct_step:
            return self._correct_step_turn(request, equation, step_policy, session_id)
        if step_policy.reveal_partial:
            return self._incorrect_partial_turn(
                request, equation, step_policy, session_id
            )
        return self._incorrect_hint_turn(request, equation, step_policy, session_id)

    def build_wrong_input_feedback(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        equation = self._equation(request, understanding)
        return self._incorrect_hint_turn(request, equation, policy, session_id)

    def build_partial_solution(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        equation = self._equation(request, understanding)
        use_khmer = policy.use_khmer_explanation
        active_step = 1 if request.current_state.current_step_index >= 1 else 0
        student_task = _localized_task(
            use_khmer,
            "Write the equation after that operation.",
            "សរសេរសមីការបន្ទាប់ពីធ្វើប្រមាណវិធីនោះ។",
        )
        if active_step >= 1:
            student_task = _localized_task(
                use_khmer,
                f"Now isolate {equation.variable} from {equation.first_step_equation}.",
                f"ឥឡូវដោះស្រាយរក {equation.variable} ពី {equation.first_step_equation}។",
            )
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                f"Partial step: after removing {_format_expr(equation.constant)}, you get {equation.first_step_equation}.",
                f"ជំហានមួយផ្នែក៖ បន្ទាប់ពីយក {_format_expr(equation.constant)} ចេញ យើងបាន {equation.first_step_equation}។",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Partial solution: {equation.first_step_equation}",
                f"ដំណោះស្រាយមួយផ្នែក៖ {equation.first_step_equation}",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=student_task,
            board=_build_linear_board(
                equation,
                active_step=active_step,
                reveal_partial=True,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_full_solution(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        equation = self._equation(request, understanding)
        use_khmer = policy.use_khmer_explanation
        final_metadata = _linear_final_verified_metadata(equation, request, policy)
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                "Excellent work! You've completed this problem. Ready for a similar one?",
                "ល្អណាស់! អ្នកបានបញ្ចប់លំហាត់នេះហើយ។ ត្រៀមសាកលំហាត់ស្រដៀងគ្នាទេ?",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Final answer: {equation.final_equation}",
                f"ចម្លើយចុងក្រោយ៖ {equation.final_equation}",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                "Check the steps and tell me which part felt difficult.",
                "ពិនិត្យជំហាន ហើយប្រាប់គ្រូថាផ្នែកណាដែលពិបាក។",
            ),
            board=_build_linear_board(
                equation,
                active_step=2,
                reveal_partial=True,
                reveal_final=True,
                feedback="final_verified_answer",
            ),
            mastery_signal=VisualTutorMasterySignal.MASTERED,
            metadata=final_metadata,
        )

    def build_final_locked_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        equation = self._equation(request, understanding)
        use_khmer = policy.use_khmer_explanation
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                "I will not show the final answer yet. Try the first operation first.",
                "គ្រូមិនទាន់បង្ហាញចម្លើយចុងក្រោយទេ។ សាកល្បងប្រមាណវិធីដំបូងសិន។",
            ),
            display_text=_localized_task(
                use_khmer,
                "Final answer is locked. Try one step first.",
                "ចម្លើយចុងក្រោយត្រូវបានចាក់សោ។ សាកល្បងមួយជំហានសិន។",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                f"What should we do first to simplify this equation?",
                "តើយើងគួរធ្វើអ្វីមុន ដើម្បីធ្វើឱ្យសមីការនេះងាយជាងមុន?",
            ),
            board=_build_linear_board(equation, active_step=0),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(None, request, policy),
        )

    def build_stuck_help_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        equation = self._equation(request, understanding)
        use_khmer = policy.use_khmer_explanation
        if request.current_state.current_step_index >= 1:
            variable = equation.variable
            return VisualTutorTurnResponse(
                session_id=session_id,
                turn_id=str(uuid.uuid4()),
                spoken_text=_localized_task(
                    use_khmer,
                    f"Let's focus on the current step. You already simplified the equation, so now isolate {variable} by dividing both sides by the coefficient.",
                    f"យើងផ្តោតលើជំហានបច្ចុប្បន្ន។ អ្នកបានធ្វើឱ្យសមីការងាយជាងមុនហើយ ដូច្នេះឥឡូវដោះស្រាយរក {variable} ដោយចែកទាំងពីរខាងដោយមេគុណ។",
                ),
                display_text=_localized_task(
                    use_khmer,
                    f"Small hint: continue from {equation.first_step_equation}. Divide both sides by {_format_expr(equation.coefficient)}.",
                    f"គន្លឹះតូច៖ បន្តពី {equation.first_step_equation}។ ចែកទាំងពីរខាងដោយ {_format_expr(equation.coefficient)}។",
                ),
                teaching_mode=policy.teaching_mode,
                final_answer_locked=policy.final_answer_locked,
                student_task=_localized_task(
                    use_khmer,
                    f"What operation isolates {variable} in {equation.first_step_equation}?",
                    f"តើប្រមាណវិធីអ្វីអាចដោះស្រាយរក {variable} ក្នុង {equation.first_step_equation}?",
                ),
                board=_build_linear_board(
                    equation,
                    active_step=1,
                    reveal_partial=True,
                    reveal_final=policy.reveal_final,
                    feedback="stuck_help",
                ),
                mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
                metadata=_metadata(None, request, policy),
            )
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                f"Let's slow down. Focus only on the constant term without {equation.variable}.",
                f"យើងធ្វើយឺតៗ។ ផ្តោតលើតួដែលគ្មាន {equation.variable} សិន។",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Small hint: {equation.operation_text}. Keep both sides balanced.",
                f"គន្លឹះតូច៖ {equation.operation_text}។ រក្សាទាំងពីរខាងឱ្យស្មើគ្នា។",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                "What is the first simplification move?",
                "តើជំហានធ្វើឱ្យសាមញ្ញដំបូងគឺអ្វី?",
            ),
            board=_build_linear_board(
                equation,
                active_step=0,
                reveal_partial=False,
                reveal_final=policy.reveal_final,
                feedback="stuck_help",
            ),
            board_actions=_linear_constant_hint_actions(equation),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_explain_differently_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        equation = self._equation(request, understanding)
        spoken_text = "Think of the equation like a balance scale. Whatever you remove from one side, remove from the other side too."
        display_text = (
            "Different view: keep both sides balanced. Work with the constant "
            f"term first, then isolate {equation.variable}."
        )
        if policy.use_khmer_explanation:
            spoken_text = (
                "សូមគិតសមីការដូចជាជញ្ជីង។ យកអ្វីចេញពីម្ខាង ត្រូវយកចេញពីម្ខាងទៀតដែរ។"
            )
            display_text = f"វិធីពន្យល់ផ្សេង៖ រក្សាឱ្យពីរខាងស្មើគ្នា។ ដំបូងធ្វើឱ្យសាមញ្ញ បន្ទាប់មកដោះស្រាយរក {equation.variable}។"
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=spoken_text,
            display_text=display_text,
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                policy.use_khmer_explanation,
                "Tell me the operation that keeps both sides balanced.",
                "ប្រាប់គ្រូពីប្រមាណវិធីដែលធ្វើឱ្យទាំងពីរខាងនៅតែស្មើគ្នា។",
            ),
            board=_build_linear_board(
                equation,
                active_step=0,
                reveal_partial=policy.reveal_partial,
                reveal_final=policy.reveal_final,
            ),
            board_actions=_linear_balance_scale_actions(equation),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def _equation(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
    ) -> LinearEquation:
        source = _problem_source(request, understanding)
        equation = parse_linear_equation(source)
        if equation is None:
            raise ValueError("LinearEquationSolver could not parse problem")
        return equation

    def _correct_step_turn(
        self,
        request: VisualTutorTurnRequest,
        equation: LinearEquation,
        policy: VisualTutorPolicyDecision,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        use_khmer = policy.use_khmer_explanation
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                f"Good. That is the right first step. Now divide both sides by the coefficient of {equation.variable}.",
                f"ល្អ។ នោះជាជំហានដំបូងត្រឹមត្រូវ។ ឥឡូវចែកទាំងពីរខាងដោយមេគុណរបស់ {equation.variable}។",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Correct first step. Now isolate {equation.variable}.",
                f"ជំហានដំបូងត្រឹមត្រូវ។ ឥឡូវដោះស្រាយរក {equation.variable}។",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                f"What do you do to both sides of {equation.first_step_equation}?",
                f"តើអ្នកគួរធ្វើអ្វីលើទាំងពីរខាងនៃ {equation.first_step_equation}?",
            ),
            board=_build_linear_board(
                equation,
                active_step=1,
                reveal_partial=True,
                reveal_final=policy.reveal_final,
                feedback="correct_step",
            ),
            board_actions=_linear_correct_first_step_actions(equation),
            mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
            metadata=_metadata(None, request, policy),
        )

    def _final_step_turn(
        self,
        request: VisualTutorTurnRequest,
        equation: LinearEquation,
        policy: VisualTutorPolicyDecision,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        use_khmer = policy.use_khmer_explanation
        final_metadata = _linear_final_verified_metadata(equation, request, policy)
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                "Excellent work! You've completed this problem. Ready for a similar one?",
                "ល្អណាស់! អ្នកបានបញ្ចប់លំហាត់នេះហើយ។ ត្រៀមសាកលំហាត់ស្រដៀងគ្នាទេ?",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Verified final answer: {equation.final_equation}",
                f"ចម្លើយចុងក្រោយបានផ្ទៀងផ្ទាត់៖ {equation.final_equation}",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=False,
            student_task=_localized_task(
                use_khmer,
                "Excellent work! You’ve completed this problem. Ready for a similar one?",
                "ល្អណាស់! អ្នកបានបញ្ចប់លំហាត់នេះហើយ។ ត្រៀមសាកលំហាត់ស្រដៀងគ្នាទេ?",
            ),
            board=_build_linear_board(
                equation,
                active_step=2,
                reveal_partial=True,
                reveal_final=True,
                feedback="final_verified_answer",
            ),
            board_actions=_linear_final_step_actions(equation),
            interaction=None,
            allowed_actions=_solver_allowed_actions(policy),
            mastery_signal=VisualTutorMasterySignal.MASTERED,
            metadata={**final_metadata, "policy_reason": "correct_final_step"},
        )

    def _understanding_check_turn(
        self,
        request: VisualTutorTurnRequest,
        equation: LinearEquation,
        policy: VisualTutorPolicyDecision,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        use_khmer = policy.use_khmer_explanation
        answered_yes = policy.validation_result == "understanding_check_yes"
        if answered_yes:
            spoken_text = _localized_task(
                use_khmer,
                "Good. The substitution checks out, so the solution is correct.",
                "ល្អ។ ការជំនួសតម្លៃត្រឡប់ទៅពិនិត្យត្រឹមត្រូវ ដូច្នេះដំណោះស្រាយត្រឹមត្រូវ។",
            )
            display_text = _localized_task(
                use_khmer,
                "Correct. The solution checks in the original equation.",
                "ត្រឹមត្រូវ។ ដំណោះស្រាយនេះផ្ទៀងផ្ទាត់បានក្នុងសមីការដើម។",
            )
            student_task = _localized_task(
                use_khmer,
                "Do you want to try a similar equation or review one step?",
                "តើអ្នកចង់សាកល្បងសមីការស្រដៀងគ្នា ឬរំលឹកជំហានណាមួយទេ?",
            )
            actions = _linear_understanding_check_actions(
                equation,
                confirmed=True,
            )
            mastery = VisualTutorMasterySignal.MASTERED
        else:
            spoken_text = _localized_task(
                use_khmer,
                f"No problem. Let's check it carefully by replacing {equation.variable} with {_format_expr(equation.solution)}.",
                f"មិនអីទេ។ យើងពិនិត្យវាយឺតៗ ដោយជំនួស {equation.variable} ជាមួយ {_format_expr(equation.solution)}។",
            )
            display_text = _localized_task(
                use_khmer,
                "Let's recheck the substitution together.",
                "យើងពិនិត្យការជំនួសតម្លៃជាមួយគ្នាម្តងទៀត។",
            )
            student_task = _localized_task(
                use_khmer,
                f"Calculate the check: {_linear_substitution_check_equation(equation)}.",
                f"គណនាការពិនិត្យ៖ {_linear_substitution_check_equation(equation)}។",
            )
            actions = _linear_understanding_check_actions(
                equation,
                confirmed=False,
            )
            mastery = VisualTutorMasterySignal.IMPROVING

        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=spoken_text,
            display_text=display_text,
            teaching_mode=VisualTutorTeachingMode.STEP_CHECK,
            final_answer_locked=False,
            student_task=student_task,
            board=_build_linear_board(
                equation,
                active_step=2,
                reveal_partial=True,
                reveal_final=True,
                feedback="understanding_check",
            ),
            board_actions=actions,
            interaction=_solver_interaction(
                student_task,
                policy=policy,
                interaction_type=VisualTutorInteractionType.TEXT_RESPONSE,
            ),
            allowed_actions=_solver_allowed_actions(policy),
            mastery_signal=mastery,
            metadata={
                **_metadata(None, request, policy),
                "policy_reason": "understanding_check_response",
            },
        )

    def _incorrect_partial_turn(
        self,
        request: VisualTutorTurnRequest,
        equation: LinearEquation,
        policy: VisualTutorPolicyDecision,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        use_khmer = policy.use_khmer_explanation
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                "Not quite. Here is the first safe step: remove the constant term from both sides.",
                "នៅមិនទាន់ត្រឹមត្រូវទេ។ ជំហានដំបូងគឺយកចំនួនថេរចេញពីទាំងពីរខាង។",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Partial solution: {equation.first_step_equation}",
                f"ដំណោះស្រាយមួយផ្នែក៖ {equation.first_step_equation}",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                f"Now continue from {equation.first_step_equation}.",
                f"ឥឡូវបន្តពី {equation.first_step_equation}។",
            ),
            board=_build_linear_board(
                equation,
                active_step=0,
                reveal_partial=policy.reveal_partial,
                reveal_final=policy.reveal_final,
                feedback="incorrect_step",
            ),
            board_actions=_linear_incorrect_partial_actions(equation),
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata=_metadata(None, request, policy),
        )

    def _incorrect_hint_turn(
        self,
        request: VisualTutorTurnRequest,
        equation: LinearEquation,
        policy: VisualTutorPolicyDecision,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        use_khmer = policy.use_khmer_explanation
        is_redirect = policy.should_redirect_input
        validation_result = policy.validation_result or "incorrect_relevant_step"
        active_step = 1 if request.current_state.current_step_index >= 1 else 0
        reveal_partial = policy.reveal_partial or active_step > 0
        is_later_step = active_step > 0
        check_work_metadata = _check_work_metadata(
            equation,
            student_step=request.message,
            validation_result=validation_result,
            misconception_type=policy.misconception_type,
        )
        board = _build_linear_board(
            equation,
            active_step=active_step,
            reveal_partial=reveal_partial,
            reveal_final=policy.reveal_final,
            feedback="incorrect_step",
        )
        board = board.model_copy(
            update={"metadata": {**board.metadata, **check_work_metadata}}
        )
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                (
                    "That input does not match the current step yet. Focus on removing the constant term from both sides first."
                    if is_redirect
                    else (
                        f"That value does not check out yet. Continue from {equation.first_step_equation} and isolate {equation.variable}."
                        if is_later_step
                        else "You're almost there! Just take a look at the sign in the second step."
                    )
                ),
                (
                    "ចម្លើយនេះមិនត្រូវនឹងជំហានបច្ចុប្បន្នទេ។ ផ្តោតលើយកចំនួនថេរចេញពីទាំងពីរខាងជាមុនសិន។"
                    if is_redirect
                    else "នៅមិនទាន់ត្រឹមត្រូវទេ។ ផ្តោតលើជំហានបច្ចុប្បន្នជាមុនសិន។"
                ),
            ),
            display_text=_localized_task(
                use_khmer,
                (
                    "That does not match the current step yet. Start by removing the constant term."
                    if is_redirect
                    else (
                        f"Not quite. Keep isolating {equation.variable} from {equation.first_step_equation}."
                        if is_later_step
                        else "You're almost there! Check your sign in that step."
                    )
                ),
                (
                    "វាមិនទាន់ត្រូវនឹងជំហានបច្ចុប្បន្នទេ។ ចាប់ផ្តើមដោយយកចំនួនថេរចេញ។"
                    if is_redirect
                    else "នៅមិនទាន់ត្រឹមត្រូវទេ។ ចាប់ផ្តើមពីជំហានបច្ចុប្បន្ន។"
                ),
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                (
                    f"Continue from {equation.first_step_equation}. What operation isolates {equation.variable}?"
                    if is_later_step
                    else "Try again from the same step, or ask me why this sign changed."
                ),
                "សាកសរសេរសមីការបន្ទាប់ពីយកចំនួនថេរចេញ។",
            ),
            board=board,
            board_actions=(
                _linear_isolate_x_hint_actions(equation)
                if is_later_step
                else _linear_wrong_first_step_actions(equation, request.message)
            ),
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata={
                **_metadata(None, request, policy),
                **check_work_metadata,
            },
        )


class LineThroughPointsSolver(LiveTeacherMoveMixin):
    problem_type = "line_through_two_points"

    def can_handle(self, understanding: VisualTutorProblemUnderstandingResult) -> bool:
        return understanding.problem_type == self.problem_type

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts:
        line = self._line(request, understanding)
        current_step_index = request.current_state.current_step_index
        validation = _line_student_validation_facts(request, line, policy)
        return VisualTutorSolverFacts(
            solver_name=self.__class__.__name__,
            problem_type=self.problem_type,
            normalized_problem=line.normalized,
            variable="y",
            known_solution=line.final_equation,
            current_step_index=current_step_index,
            expected_step=_line_expected_step(current_step_index),
            expected_operation=_line_expected_operation(line, current_step_index),
            expected_equation=_line_expected_equation(line, current_step_index),
            student_validation=validation,
            verified_answer=line.final_equation,
            sympy_verified=True,
            next_concept=_line_next_concept(current_step_index),
            safe_formulas=["m = (y2 - y1) / (x2 - x1)", "y = mx + b"],
            board_context=_line_board_context(line),
            metadata={"policy_reason": policy.reason},
        )

    def build_initial_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        line = self._line(request, understanding)
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text="Let's look at the two points first.",
            display_text="Start by comparing the y-values.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="How much does y increase?",
            board=_build_line_board(line, active_step=0),
            board_actions=_line_delta_y_actions(line),
            interaction=_solver_interaction(
                "How much does y increase?",
                policy=policy,
                interaction_type=VisualTutorInteractionType.NUMERIC_INPUT,
            ),
            allowed_actions=_solver_allowed_actions(policy),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(line.normalized, request, policy),
        )

    def build_hint_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        line = self._line(request, understanding)
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text="Hint: subtract the y-values and divide by the change in x.",
            display_text="Hint: slope is change in y divided by change in x.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Write the slope as m = ...",
            board=_build_line_board(
                line,
                active_step=0,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def check_student_step(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        line = self._line(request, understanding)
        current_step_index = request.current_state.current_step_index
        is_correct_delta_y = current_step_index <= 0 and _contains_value(
            request.message, line.delta_y
        )
        is_correct_delta_x = current_step_index == 1 and _contains_value(
            request.message, line.delta_x
        )
        is_correct_slope = current_step_index == 2 and (
            _contains_value(request.message, line.slope)
            or _line_step_is_correct(request.message, line)
        )
        is_correct_intercept = current_step_index >= 3 and _contains_value(
            request.message, line.intercept
        )
        is_correct_step = any(
            [
                is_correct_delta_y,
                is_correct_delta_x,
                is_correct_slope,
                is_correct_intercept,
            ]
        )
        step_policy = decide_visual_tutor_policy(
            request,
            has_problem=True,
            is_correct_step=is_correct_step,
            problem_type=self.problem_type,
            known_solver_available=True,
            input_understanding=_input_understanding_from_policy(policy),
        )
        if is_correct_delta_y:
            return VisualTutorTurnResponse(
                session_id=session_id,
                turn_id=str(uuid.uuid4()),
                spoken_text="Correct. Now let's find how much x changes.",
                display_text="Correct. Next compare the x-values.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task="How much does x increase?",
                board=_build_line_board(
                    line,
                    active_step=1,
                    reveal_partial=False,
                    reveal_final=step_policy.reveal_final,
                    feedback="correct_delta_y",
                ),
                board_actions=_line_delta_y_answer_actions(line)
                + _line_delta_x_actions(line),
                interaction=_solver_interaction(
                    "How much does x increase?",
                    policy=step_policy,
                    interaction_type=VisualTutorInteractionType.NUMERIC_INPUT,
                ),
                allowed_actions=_solver_allowed_actions(step_policy),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata={
                    **_metadata(None, request, step_policy),
                    "line_live_step": "delta_x",
                    "validation_result": "correct_delta_y",
                },
            )
        if is_correct_delta_x:
            return VisualTutorTurnResponse(
                session_id=session_id,
                turn_id=str(uuid.uuid4()),
                spoken_text="Correct. Now we can compare rise over run to make the slope.",
                display_text="Now use slope = change in y divided by change in x.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task="Use the two changes to write the slope m.",
                board=_build_line_board(
                    line,
                    active_step=2,
                    reveal_partial=False,
                    reveal_final=step_policy.reveal_final,
                    feedback="correct_delta_x",
                ),
                board_actions=_line_delta_x_answer_actions(line)
                + _line_slope_question_actions(line),
                interaction=_solver_interaction(
                    "What is m = delta y / delta x?",
                    policy=step_policy,
                    interaction_type=VisualTutorInteractionType.NUMERIC_INPUT,
                ),
                allowed_actions=_solver_allowed_actions(step_policy),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata={
                    **_metadata(None, request, step_policy),
                    "line_live_step": "slope",
                    "validation_result": "correct_delta_x",
                },
            )
        if is_correct_slope:
            return VisualTutorTurnResponse(
                session_id=session_id,
                turn_id=str(uuid.uuid4()),
                spoken_text="Good. The slope is 2. Now we need the y-intercept b.",
                display_text="Correct slope. Next find b in y = mx + b.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task=f"Using point {line.first_label}({_format_expr(line.x1)},{_format_expr(line.y1)}), what is b?",
                board=_build_line_board(
                    line,
                    active_step=3,
                    reveal_partial=True,
                    reveal_final=step_policy.reveal_final,
                    feedback="correct_slope",
                ),
                board_actions=_line_slope_answer_actions(line)
                + _line_intercept_question_actions(line),
                interaction=_solver_interaction(
                    f"What is b in {_format_expr(line.y1)} = {_format_expr(line.slope)}({_format_expr(line.x1)}) + b?",
                    policy=step_policy,
                    interaction_type=VisualTutorInteractionType.NUMERIC_INPUT,
                ),
                allowed_actions=_solver_allowed_actions(step_policy),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata={
                    **_metadata(None, request, step_policy),
                    "line_live_step": "intercept",
                    "validation_result": "correct_slope",
                },
            )
        if is_correct_intercept:
            if step_policy.reveal_final:
                return self.build_full_solution(
                    request, understanding, step_policy, session_id=session_id
                )
            return VisualTutorTurnResponse(
                session_id=session_id,
                turn_id=str(uuid.uuid4()),
                spoken_text="Correct. We have m and b. The final equation stays locked until the policy allows it.",
                display_text="Correct. The pieces are ready: m and b.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task="Ask to show the answer when you are ready, or explain how m and b make the line.",
                board=_build_line_board(
                    line,
                    active_step=3,
                    reveal_partial=True,
                    reveal_final=step_policy.reveal_final,
                    feedback="correct_intercept",
                ),
                board_actions=_line_intercept_answer_actions(line)
                + _line_final_locked_actions(line),
                interaction=_solver_interaction(
                    "How do m and b appear in y = mx + b?",
                    policy=step_policy,
                ),
                allowed_actions=_solver_allowed_actions(step_policy),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata={
                    **_metadata(None, request, step_policy),
                    "line_live_step": "ready_for_final",
                    "validation_result": "correct_intercept",
                },
            )
        if step_policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, step_policy, session_id=session_id
            )
        expected = _line_expected_step(current_step_index)
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=f"Not quite. Stay with the current step: {expected}.",
            display_text=f"Not quite. That answer does not match {expected}.",
            teaching_mode=step_policy.teaching_mode,
            final_answer_locked=step_policy.final_answer_locked,
            student_task=_line_retry_task(line, current_step_index),
            board=_build_line_board(
                line,
                active_step=current_step_index,
                reveal_partial=step_policy.reveal_partial,
                reveal_final=step_policy.reveal_final,
                feedback="incorrect_step",
            ),
            board_actions=_line_wrong_step_actions(line, current_step_index),
            interaction=_solver_interaction(
                _line_retry_task(line, current_step_index),
                policy=step_policy,
                interaction_type=VisualTutorInteractionType.NUMERIC_INPUT,
            ),
            allowed_actions=_solver_allowed_actions(step_policy),
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata={
                **_metadata(None, request, step_policy),
                "validation_result": "incorrect_step",
                "expected_step": expected,
            },
        )

    def build_partial_solution(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        line = self._line(request, understanding)
        use_khmer = policy.use_khmer_explanation
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                f"Partial step: the slope is {line.slope_step}.",
                f"ជំហានមួយផ្នែក៖ ជម្រាលគឺ {line.slope_step}។",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Partial solution: {line.slope_step}",
                f"ដំណោះស្រាយមួយផ្នែក៖ {line.slope_step}",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                "Write the slope as m = ...",
                "សរសេរជម្រាលជា m = ...",
            ),
            board=_build_line_board(
                line,
                active_step=0,
                reveal_partial=True,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_full_solution(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        line = self._line(request, understanding)
        use_khmer = policy.use_khmer_explanation
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                f"Now we can reveal it. The equation is {line.final_equation}.",
                f"ឥឡូវយើងអាចបង្ហាញបាន។ សមីការគឺ {line.final_equation}។",
            ),
            display_text=_localized_task(
                use_khmer,
                f"Final answer: {line.final_equation}",
                f"ចម្លើយចុងក្រោយ៖ {line.final_equation}",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                "Check how the slope and one point create the line equation.",
                "ពិនិត្យថាជម្រាល និងចំណុចមួយបង្កើតសមីការបន្ទាត់យ៉ាងដូចម្តេច។",
            ),
            board=_build_line_board(
                line,
                active_step=4,
                reveal_partial=True,
                reveal_final=True,
            ),
            board_actions=_line_full_solution_actions(line),
            interaction=_solver_interaction(
                "Quick check: in y = mx + b, which number is the slope?",
                policy=policy,
                interaction_type=VisualTutorInteractionType.TEXT_RESPONSE,
            ),
            allowed_actions=_solver_allowed_actions(policy),
            mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
            metadata={
                **_metadata(None, request, policy),
                "line_live_step": "final_equation_revealed",
            },
        )

    def build_final_locked_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        line = self._line(request, understanding)
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text="I will not show the final equation yet. First, find the slope between the two points.",
            display_text="Final answer is locked. Start with the y-change.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=f"What is Δy = {_format_expr(line.y2)} - {_format_expr(line.y1)}?",
            board=_build_line_board(line, active_step=0),
            board_actions=_line_delta_y_actions(line),
            interaction=_solver_interaction(
                f"What is Δy = {_format_expr(line.y2)} - {_format_expr(line.y1)}?",
                policy=policy,
                interaction_type=VisualTutorInteractionType.NUMERIC_INPUT,
            ),
            allowed_actions=_solver_allowed_actions(policy),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(None, request, policy),
        )

    def build_stuck_help_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        line = self._line(request, understanding)
        use_khmer = policy.use_khmer_explanation
        current_step_index = request.current_state.current_step_index
        if current_step_index >= 3:
            return VisualTutorTurnResponse(
                session_id=session_id,
                turn_id=str(uuid.uuid4()),
                spoken_text=_localized_task(
                    use_khmer,
                    "Use point D in y = mx + b. The x-value is zero, so the equation becomes very simple.",
                    "ប្រើចំណុច D ក្នុង y = mx + b។ តម្លៃ x គឺសូន្យ ដូច្នេះសមីការងាយណាស់។",
                ),
                display_text=_localized_task(
                    use_khmer,
                    "Substitute D(0,1): 1 = 2(0) + b.",
                    "ដាក់ D(0,1)៖ 1 = 2(0) + b។",
                ),
                teaching_mode=policy.teaching_mode,
                final_answer_locked=policy.final_answer_locked,
                student_task=_localized_task(
                    use_khmer,
                    "What is b?",
                    "តើ b ស្មើប៉ុន្មាន?",
                ),
                board=_build_line_board(
                    line,
                    active_step=3,
                    reveal_partial=True,
                    reveal_final=policy.reveal_final,
                    feedback="stuck_help",
                ),
                board_actions=_line_intercept_stuck_actions(line),
                interaction=_solver_interaction(
                    "b = ?",
                    policy=policy,
                    interaction_type=VisualTutorInteractionType.NUMERIC_INPUT,
                ),
                allowed_actions=_solver_allowed_actions(policy),
                mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
                metadata={
                    **_metadata(None, request, policy),
                    "line_live_step": "intercept_stuck",
                },
            )
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                "Let's slow down. For a line through two points, start only with the slope.",
                "យើងធ្វើយឺតៗ។ សម្រាប់បន្ទាត់កាត់ពីរចំណុច ចាប់ផ្តើមតែពីជម្រាលសិន។",
            ),
            display_text=_localized_task(
                use_khmer,
                "Small hint: compare the change in y with the change in x.",
                "គន្លឹះតូច៖ ប្រៀបធៀបការប្រែប្រួល y ជាមួយការប្រែប្រួល x។",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                f"What is the change in y: {_format_expr(line.y2)} - {_format_expr(line.y1)}?",
                f"តើការប្រែប្រួល y គឺអ្វី៖ {_format_expr(line.y2)} - {_format_expr(line.y1)}?",
            ),
            board=_build_line_board(
                line,
                active_step=0,
                reveal_partial=False,
                reveal_final=policy.reveal_final,
                feedback="stuck_help",
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_explain_differently_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        line = self._line(request, understanding)
        use_khmer = policy.use_khmer_explanation
        return VisualTutorTurnResponse(
            session_id=session_id,
            turn_id=str(uuid.uuid4()),
            spoken_text=_localized_task(
                use_khmer,
                "Think of the two points as two locations. Slope tells how much y rises for each move in x.",
                "គិតពីចំណុចទាំងពីរដូចជាទីតាំងពីរ។ ជម្រាលប្រាប់ថា y ឡើងប៉ុន្មាន ពេល x ផ្លាស់ទី។",
            ),
            display_text=_localized_task(
                use_khmer,
                "Different view: first measure vertical change, then horizontal change.",
                "វិធីមើលផ្សេង៖ វាស់ការប្រែប្រួលបញ្ឈរជាមុន បន្ទាប់មកការប្រែប្រួលផ្ដេក។",
            ),
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=_localized_task(
                use_khmer,
                "Which change is vertical: y-values or x-values?",
                "ការប្រែប្រួលបញ្ឈរគឺតម្លៃ y ឬតម្លៃ x?",
            ),
            board=_build_line_board(
                line,
                active_step=0,
                reveal_partial=policy.reveal_partial,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def _line(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
    ) -> LineThroughPoints:
        source = _problem_source(request, understanding)
        line = parse_line_through_points(
            source
        ) or parse_line_through_points_from_understanding(understanding)
        if line is None:
            raise ValueError("LineThroughPointsSolver could not parse problem")
        return line


class SlopeFromTwoPointsSolver(LiveTeacherMoveMixin):
    problem_type = "slope_from_two_points"

    def can_handle(self, understanding: VisualTutorProblemUnderstandingResult) -> bool:
        return understanding.problem_type == self.problem_type

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts:
        line = self._line(understanding)
        validation = _slope_student_validation_facts(request, line, policy)
        return VisualTutorSolverFacts(
            solver_name=self.__class__.__name__,
            problem_type=self.problem_type,
            normalized_problem=line.normalized,
            variable="m",
            known_solution=f"m = {_format_expr(line.slope)}",
            current_step_index=request.current_state.current_step_index,
            expected_step="compare vertical change with horizontal change",
            expected_operation="divide Δy by Δx",
            expected_equation=f"m = {_format_expr(line.delta_y)} / {_format_expr(line.delta_x)}",
            student_validation=validation,
            verified_answer=f"m = {_format_expr(line.slope)}",
            sympy_verified=True,
            next_concept="use slope to describe the line's steepness",
            safe_formulas=["m = (y2 - y1) / (x2 - x1)"],
            board_context=_line_board_context(line),
            metadata={"policy_reason": policy.reason},
        )

    def build_initial_turn(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
        *,
        session_id: str,
    ) -> VisualTutorTurnResponse:
        line = self._line(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Good. To find slope, what change in y and change in x do we compare?",
            display_text="Find slope one step at a time.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="First calculate change in y and change in x.",
            board=_build_slope_board(line, reveal_partial=False, reveal_final=False),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(line.normalized, request, policy),
        )

    def build_hint_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        line = self._line(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Hint: slope is change in y divided by change in x.",
            display_text="Hint: m = (y2 - y1) / (x2 - x1).",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Write the fraction for the slope.",
            board=_build_slope_board(line, reveal_partial=False, reveal_final=False),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def check_student_step(self, request, understanding, policy, *, session_id):
        line = self._line(understanding)
        is_correct = _line_step_is_correct(request.message, line)
        step_policy = decide_visual_tutor_policy(
            request,
            has_problem=True,
            is_correct_step=is_correct,
            problem_type=self.problem_type,
            known_solver_available=True,
            input_understanding=_input_understanding_from_policy(policy),
        )
        if is_correct:
            return _solver_response(
                session_id=session_id,
                spoken_text="Correct. That slope matches the two points.",
                display_text="Correct slope.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task="Explain which two differences you compared.",
                board=_build_slope_board(
                    line,
                    reveal_partial=True,
                    reveal_final=step_policy.reveal_final,
                    feedback="correct_step",
                ),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata=_metadata(None, request, step_policy),
            )
        if step_policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, step_policy, session_id=session_id
            )
        return _solver_response(
            session_id=session_id,
            spoken_text="Not quite. Check the order: change in y over change in x.",
            display_text="Try again with m = (y2 - y1) / (x2 - x1).",
            teaching_mode=step_policy.teaching_mode,
            final_answer_locked=step_policy.final_answer_locked,
            student_task="Write only the slope fraction first.",
            board=_build_slope_board(line, feedback="incorrect_step"),
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata=_metadata(None, request, step_policy),
        )

    def build_partial_solution(self, request, understanding, policy, *, session_id):
        line = self._line(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Partial step: the slope setup is {line.slope_step}.",
            display_text=f"Partial solution: {line.slope_step}",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Tell me why we divide by the change in x.",
            board=_build_slope_board(
                line, reveal_partial=True, reveal_final=policy.reveal_final
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_full_solution(self, request, understanding, policy, *, session_id):
        line = self._line(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Now we can reveal it. The slope is m = {_format_expr(line.slope)}.",
            display_text=f"Final answer: m = {_format_expr(line.slope)}",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Check the numerator and denominator one more time.",
            board=_build_slope_board(line, reveal_partial=True, reveal_final=True),
            mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
            metadata=_metadata(None, request, policy),
        )

    def build_stuck_help_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        line = self._line(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Let's slow down. Slope only compares two changes.",
            display_text="Small hint: find change in y first, then change in x.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=f"What is {_format_expr(line.y2)} - {_format_expr(line.y1)}?",
            board=_build_slope_board(
                line,
                reveal_partial=False,
                reveal_final=policy.reveal_final,
                feedback="stuck_help",
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_explain_differently_turn(
        self, request, understanding, policy, *, session_id
    ):
        line = self._line(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Picture walking from the first point to the second. Slope is rise divided by run.",
            display_text="Different view: rise over run means vertical change over horizontal change.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Which number changes vertically between the two points?",
            board=_build_slope_board(
                line,
                reveal_partial=policy.reveal_partial,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def _line(
        self, understanding: VisualTutorProblemUnderstandingResult
    ) -> LineThroughPoints:
        line = parse_line_through_points_from_understanding(understanding)
        if line is None:
            raise ValueError("SlopeFromTwoPointsSolver could not parse points")
        return line


class QuadraticEquationBasicSolver(LiveTeacherMoveMixin):
    problem_type = "quadratic_equation"

    def can_handle(self, understanding: VisualTutorProblemUnderstandingResult) -> bool:
        return understanding.problem_type in {
            self.problem_type,
            "quadratic_equation_basic",
        }

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts:
        problem = self._problem(understanding)
        roots = problem["roots"]
        validation = _generic_answer_validation_facts(
            request,
            is_correct=_contains_all_roots(request.message, roots),
            policy=policy,
            correct_explanation="The submitted roots make the quadratic equal zero.",
            expected_explanation="The input should identify the roots or the next factoring step.",
        )
        verified_answer = "x = " + ", ".join(_format_expr(root) for root in roots)
        return VisualTutorSolverFacts(
            solver_name=self.__class__.__name__,
            problem_type=self.problem_type,
            normalized_problem=problem["normalized"],
            variable="x",
            known_solution=verified_answer,
            current_step_index=request.current_state.current_step_index,
            expected_step="choose a solving method and identify factors",
            expected_operation="factor or use the quadratic formula",
            expected_equation="ax^2 + bx + c = 0",
            student_validation=validation,
            verified_answer=verified_answer,
            sympy_verified=True,
            next_concept="verify each root by substitution",
            safe_formulas=["ax^2 + bx + c = 0", "x = (-b ± sqrt(b^2 - 4ac)) / 2a"],
            board_context=_solver_fact_json_context(problem),
            metadata={"policy_reason": policy.reason},
        )

    def build_initial_turn(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Good quadratic. Before solving, what method looks useful: factoring, square root, or formula?",
            display_text="Choose a method before solving.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Look for two numbers that multiply to c and add to b.",
            board=_build_quadratic_board(
                problem, reveal_partial=False, reveal_final=False
            ),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(problem["normalized"], request, policy),
        )

    def build_hint_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Hint: move everything to one side, then try factoring.",
            display_text="Hint: write it as ax^2 + bx + c = 0.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Tell me the values of a, b, and c.",
            board=_build_quadratic_board(problem),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def check_student_step(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        is_correct = _contains_all_roots(request.message, problem["roots"])
        step_policy = decide_visual_tutor_policy(
            request,
            has_problem=True,
            is_correct_step=is_correct,
            problem_type=self.problem_type,
            known_solver_available=True,
            input_understanding=_input_understanding_from_policy(policy),
        )
        if is_correct:
            return _solver_response(
                session_id=session_id,
                spoken_text="Correct. Those roots make the quadratic equal zero.",
                display_text="Correct roots.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task="Substitute one root back to check it.",
                board=_build_quadratic_board(
                    problem, reveal_partial=True, reveal_final=step_policy.reveal_final
                ),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata=_metadata(None, request, step_policy),
            )
        if step_policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, step_policy, session_id=session_id
            )
        return _solver_response(
            session_id=session_id,
            spoken_text="Not quite. Focus on the factor pair first.",
            display_text="Check the numbers that multiply to c and add to b.",
            teaching_mode=step_policy.teaching_mode,
            final_answer_locked=step_policy.final_answer_locked,
            student_task="Write the factor pair you are trying.",
            board=_build_quadratic_board(problem, feedback="incorrect_step"),
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata=_metadata(None, request, step_policy),
        )

    def build_partial_solution(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Partial step: the factor form is {problem['factorization']} = 0.",
            display_text=f"Partial solution: {problem['factorization']} = 0",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Use the zero product rule on the factors.",
            board=_build_quadratic_board(
                problem, reveal_partial=True, reveal_final=policy.reveal_final
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_full_solution(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        roots_text = " or ".join(
            f"x = {_format_expr(root)}" for root in problem["roots"]
        )
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Now we can reveal it. The solutions are {roots_text}.",
            display_text=f"Final answer: {roots_text}",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Check each root in the original equation.",
            board=_build_quadratic_board(
                problem, reveal_partial=True, reveal_final=True
            ),
            mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
            metadata=_metadata(None, request, policy),
        )

    def build_stuck_help_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Let's slow down. Focus only on choosing the solving method first.",
            display_text="Small hint: for this form, try factoring before calculating roots.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="What two numbers should multiply to c and add to b?",
            board=_build_quadratic_board(
                problem,
                reveal_partial=False,
                reveal_final=policy.reveal_final,
                feedback="stuck_help",
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_explain_differently_turn(
        self, request, understanding, policy, *, session_id
    ):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Think of factoring as finding two brackets whose product recreates the quadratic.",
            display_text="Different view: build two factors, then use zero product rule later.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Which pair of numbers matches the middle and last terms?",
            board=_build_quadratic_board(
                problem,
                reveal_partial=policy.reveal_partial,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def _problem(self, understanding: VisualTutorProblemUnderstandingResult) -> dict:
        equation = (
            understanding.extracted_entities.get("equation")
            or understanding.extracted_problem
        )
        normalized = _normalize_math_text(str(equation))
        lhs_raw, rhs_raw = normalized.split("=", 1)
        variable = sympy.Symbol(
            str(understanding.extracted_entities.get("variable", "x"))
        )
        poly = sympy.Poly(
            sympy.expand(
                sympy.sympify(lhs_raw.strip()) - sympy.sympify(rhs_raw.strip())
            ),
            variable,
        )
        roots = [sympy.simplify(root) for root in sympy.solve(poly.as_expr(), variable)]
        factorization = str(sympy.factor(poly.as_expr())).replace("**", "^")
        return {
            "equation": str(equation),
            "normalized": normalized,
            "roots": roots,
            "factorization": factorization,
        }


class ArithmeticExpressionSolver(LiveTeacherMoveMixin):
    problem_type = "arithmetic_expression"

    def can_handle(self, understanding: VisualTutorProblemUnderstandingResult) -> bool:
        return understanding.problem_type == self.problem_type

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts:
        problem = self._problem(understanding)
        validation = _generic_answer_validation_facts(
            request,
            is_correct=_contains_value(request.message, problem["answer"]),
            policy=policy,
            correct_explanation="The submitted value matches the expression.",
            expected_explanation="The input should follow order of operations.",
        )
        answer = _format_expr(problem["answer"])
        return VisualTutorSolverFacts(
            solver_name=self.__class__.__name__,
            problem_type=self.problem_type,
            normalized_problem=problem["expression"],
            known_solution=answer,
            current_step_index=request.current_state.current_step_index,
            expected_step="identify the first operation using order of operations",
            expected_operation="parentheses, multiplication/division, then addition/subtraction",
            expected_equation=_arithmetic_partial(problem["expression"]),
            student_validation=validation,
            verified_answer=answer,
            sympy_verified=True,
            next_concept="explain the operation order",
            safe_formulas=[
                "Order of operations: parentheses, multiply/divide, add/subtract."
            ],
            board_context=_solver_fact_json_context(problem),
            metadata={"policy_reason": policy.reason},
        )

    def build_initial_turn(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Good arithmetic expression. Which operation should we do first?",
            display_text="Use order of operations.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Identify the first operation before calculating everything.",
            board=_build_arithmetic_board(problem),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(problem["expression"], request, policy),
        )

    def build_hint_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Hint: do parentheses first, then multiplication or division, then addition or subtraction.",
            display_text="Hint: parentheses, multiply/divide, add/subtract.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Tell me the first operation.",
            board=_build_arithmetic_board(problem),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def check_student_step(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        is_correct = _contains_value(request.message, problem["answer"])
        step_policy = decide_visual_tutor_policy(
            request,
            has_problem=True,
            is_correct_step=is_correct,
            problem_type=self.problem_type,
            known_solver_available=True,
            input_understanding=_input_understanding_from_policy(policy),
        )
        if is_correct:
            return _solver_response(
                session_id=session_id,
                spoken_text="Correct calculation.",
                display_text="Correct.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task="Explain the order you used.",
                board=_build_arithmetic_board(
                    problem, reveal_partial=True, reveal_final=step_policy.reveal_final
                ),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata=_metadata(None, request, step_policy),
            )
        if step_policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, step_policy, session_id=session_id
            )
        return _solver_response(
            session_id=session_id,
            spoken_text="Not quite. Recheck the order of operations.",
            display_text="Start with the first priority operation.",
            teaching_mode=step_policy.teaching_mode,
            final_answer_locked=step_policy.final_answer_locked,
            student_task="Write only the first simplified part.",
            board=_build_arithmetic_board(problem, feedback="incorrect_step"),
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata=_metadata(None, request, step_policy),
        )

    def build_partial_solution(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Partial step: simplify the priority operation to get {problem['partial']}.",
            display_text=f"Partial solution: {problem['partial']}",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Now finish the remaining arithmetic.",
            board=_build_arithmetic_board(
                problem, reveal_partial=True, reveal_final=policy.reveal_final
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_full_solution(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Now we can reveal it. The value is {_format_expr(problem['answer'])}.",
            display_text=f"Final answer: {_format_expr(problem['answer'])}",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Check the order of operations used.",
            board=_build_arithmetic_board(
                problem, reveal_partial=True, reveal_final=True
            ),
            mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
            metadata=_metadata(None, request, policy),
        )

    def build_stuck_help_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Let's slow down. Do only the highest-priority operation first.",
            display_text="Small hint: look for multiplication or division before addition.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Which operation should happen first?",
            board=_build_arithmetic_board(
                problem,
                reveal_partial=False,
                reveal_final=policy.reveal_final,
                feedback="stuck_help",
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_explain_differently_turn(
        self, request, understanding, policy, *, session_id
    ):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Think of order of operations as a priority list, not reading left to right every time.",
            display_text="Different view: choose by priority first, then move across the expression.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Which part has the highest priority?",
            board=_build_arithmetic_board(
                problem,
                reveal_partial=policy.reveal_partial,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def _problem(self, understanding: VisualTutorProblemUnderstandingResult) -> dict:
        expression = str(
            understanding.extracted_entities.get("expression")
            or understanding.extracted_problem
        )
        normalized = expression.replace("^", "**")
        answer = sympy.simplify(sympy.sympify(normalized))
        return {
            "expression": expression,
            "partial": _arithmetic_partial(expression),
            "answer": answer,
        }


class SimplePercentageWordProblemSolver(LiveTeacherMoveMixin):
    problem_type = "simple_percentage_word_problem"

    def can_handle(self, understanding: VisualTutorProblemUnderstandingResult) -> bool:
        return understanding.problem_type == self.problem_type

    def solver_facts(
        self,
        request: VisualTutorTurnRequest,
        understanding: VisualTutorProblemUnderstandingResult,
        policy: VisualTutorPolicyDecision,
    ) -> VisualTutorSolverFacts:
        problem = self._problem(understanding)
        is_correct = (
            _contains_value(request.message, problem["answer"])
            or _contains_expression_value(request.message, problem["decimal"])
            or str(problem["decimal"]) in request.message
        )
        validation = _generic_answer_validation_facts(
            request,
            is_correct=is_correct,
            policy=policy,
            correct_explanation="The submitted value matches the percentage setup.",
            expected_explanation="The input should convert the percent or set up percent × base.",
        )
        answer = _format_expr(problem["answer"])
        return VisualTutorSolverFacts(
            solver_name=self.__class__.__name__,
            problem_type=self.problem_type,
            normalized_problem=problem["problem"],
            known_solution=answer,
            current_step_index=request.current_state.current_step_index,
            expected_step=f"convert {problem['percent_text']}% to a decimal or fraction",
            expected_operation=f"{problem['percent_text']} / 100 × {problem['base_text']}",
            expected_equation=f"{_format_expr(problem['decimal'])} × {problem['base_text']}",
            student_validation=validation,
            verified_answer=answer,
            sympy_verified=True,
            next_concept="explain why percent means out of 100",
            safe_formulas=["percent of base = (percent / 100) × base"],
            board_context=_solver_fact_json_context(problem),
            metadata={"policy_reason": policy.reason},
        )

    def build_initial_turn(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Good percentage problem. What does the percent become as a fraction or decimal?",
            display_text="Convert the percent first.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=f"Convert {problem['percent_text']}% to a fraction or decimal.",
            board=_build_percentage_board(problem),
            mastery_signal=VisualTutorMasterySignal.EXPLORING,
            metadata=_metadata(problem["problem"], request, policy),
        )

    def build_hint_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Hint: percent means out of 100.",
            display_text=f"Hint: {problem['percent_text']}% = {problem['percent_text']}/100.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Write the multiplication setup.",
            board=_build_percentage_board(problem),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def check_student_step(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        is_correct = (
            _contains_value(request.message, problem["answer"])
            or _contains_expression_value(request.message, problem["decimal"])
            or str(problem["decimal"]) in request.message
        )
        step_policy = decide_visual_tutor_policy(
            request,
            has_problem=True,
            is_correct_step=is_correct,
            problem_type=self.problem_type,
            known_solver_available=True,
            input_understanding=_input_understanding_from_policy(policy),
        )
        if is_correct:
            return _solver_response(
                session_id=session_id,
                spoken_text="Correct. You converted the percent or reached the value.",
                display_text="Correct step.",
                teaching_mode=step_policy.teaching_mode,
                final_answer_locked=step_policy.final_answer_locked,
                student_task="Explain why we divide the percent by 100.",
                board=_build_percentage_board(
                    problem, reveal_partial=True, reveal_final=step_policy.reveal_final
                ),
                mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
                metadata=_metadata(None, request, step_policy),
            )
        if step_policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, step_policy, session_id=session_id
            )
        return _solver_response(
            session_id=session_id,
            spoken_text="Not quite. Start by changing percent to out of 100.",
            display_text="Percent means per 100.",
            teaching_mode=step_policy.teaching_mode,
            final_answer_locked=step_policy.final_answer_locked,
            student_task=f"Write {problem['percent_text']}/100 first.",
            board=_build_percentage_board(problem, feedback="incorrect_step"),
            mastery_signal=VisualTutorMasterySignal.MISCONCEPTION,
            metadata=_metadata(None, request, step_policy),
        )

    def build_partial_solution(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Partial step: set it up as {problem['percent_text']}/100 x {problem['base_text']}.",
            display_text=f"Partial solution: {problem['percent_text']}/100 x {problem['base_text']}",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Now multiply to get the value.",
            board=_build_percentage_board(
                problem, reveal_partial=True, reveal_final=policy.reveal_final
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_full_solution(self, request, understanding, policy, *, session_id):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text=f"Now we can reveal it. The value is {_format_expr(problem['answer'])}.",
            display_text=f"Final answer: {_format_expr(problem['answer'])}",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task="Check the percent conversion and multiplication.",
            board=_build_percentage_board(
                problem, reveal_partial=True, reveal_final=True
            ),
            mastery_signal=VisualTutorMasterySignal.READY_FOR_NEXT_STEP,
            metadata=_metadata(None, request, policy),
        )

    def build_stuck_help_turn(self, request, understanding, policy, *, session_id):
        if policy.reveal_partial:
            return self.build_partial_solution(
                request, understanding, policy, session_id=session_id
            )
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Let's slow down. A percent is just a number out of 100.",
            display_text=f"Small hint: start by rewriting {problem['percent_text']}% as {problem['percent_text']}/100.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=f"What fraction represents {problem['percent_text']}%?",
            board=_build_percentage_board(
                problem,
                reveal_partial=False,
                reveal_final=policy.reveal_final,
                feedback="stuck_help",
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def build_explain_differently_turn(
        self, request, understanding, policy, *, session_id
    ):
        problem = self._problem(understanding)
        return _solver_response(
            session_id=session_id,
            spoken_text="Think of percent as splitting the whole into 100 equal parts.",
            display_text="Different view: find the fraction of the whole, then multiply by the whole amount.",
            teaching_mode=policy.teaching_mode,
            final_answer_locked=policy.final_answer_locked,
            student_task=f"How many hundredths is {problem['percent_text']}%?",
            board=_build_percentage_board(
                problem,
                reveal_partial=policy.reveal_partial,
                reveal_final=policy.reveal_final,
            ),
            mastery_signal=VisualTutorMasterySignal.NEEDS_HINT,
            metadata=_metadata(None, request, policy),
        )

    def _problem(self, understanding: VisualTutorProblemUnderstandingResult) -> dict:
        percent = sympy.Rational(str(understanding.extracted_entities["percent"]))
        base = sympy.Rational(str(understanding.extracted_entities["base"]))
        decimal = sympy.simplify(percent / 100)
        answer = sympy.simplify(decimal * base)
        return {
            "problem": understanding.extracted_problem,
            "percent": percent,
            "base": base,
            "decimal": decimal,
            "answer": answer,
            "percent_text": _format_expr(percent),
            "base_text": _format_expr(base),
        }


def _solver_response(
    *,
    session_id: str,
    spoken_text: str,
    display_text: str,
    teaching_mode: VisualTutorTeachingMode,
    final_answer_locked: bool,
    student_task: str,
    board: VisualTutorBoard,
    mastery_signal: VisualTutorMasterySignal,
    metadata: dict,
) -> VisualTutorTurnResponse:
    canvas_actions = _canvas_actions_from_board(
        board,
        final_answer_locked=final_answer_locked,
        teaching_mode=teaching_mode,
    )
    board_actions = _generic_live_actions_from_board(
        board,
        final_answer_locked=final_answer_locked,
    )
    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=str(uuid.uuid4()),
        spoken_text=spoken_text,
        display_text=display_text,
        teaching_mode=teaching_mode,
        final_answer_locked=final_answer_locked,
        student_task=student_task,
        board=board,
        canvas_actions=canvas_actions,
        board_actions=board_actions,
        interaction=_solver_interaction(
            student_task,
            policy_final_answer_locked=final_answer_locked,
        ),
        allowed_actions=_solver_allowed_actions(
            final_answer_locked=final_answer_locked,
        ),
        mastery_signal=mastery_signal,
        metadata=metadata,
    )


def _solver_interaction(
    prompt: str,
    *,
    policy: Optional[VisualTutorPolicyDecision] = None,
    policy_final_answer_locked: Optional[bool] = None,
    interaction_type: VisualTutorInteractionType = VisualTutorInteractionType.TEXT_RESPONSE,
) -> VisualTutorInteraction:
    final_answer_locked = (
        policy.final_answer_locked
        if policy is not None
        else bool(policy_final_answer_locked)
    )
    return VisualTutorInteraction(
        type=interaction_type,
        prompt=prompt,
        expected_answer_locked=final_answer_locked,
        validation_strategy=(
            "numeric_or_expression"
            if interaction_type == VisualTutorInteractionType.NUMERIC_INPUT
            else "student_input_understanding"
        ),
        input_enabled=True,
        submit_label="ឆ្លើយ" if policy and policy.use_khmer_explanation else "Submit",
    )


def _solver_allowed_actions(
    policy: Optional[VisualTutorPolicyDecision] = None,
    *,
    final_answer_locked: Optional[bool] = None,
) -> list[VisualTutorAllowedAction]:
    return [
        VisualTutorAllowedAction.SUBMIT_ANSWER,
        VisualTutorAllowedAction.REQUEST_HINT,
        VisualTutorAllowedAction.EXPLAIN_DIFFERENTLY,
        VisualTutorAllowedAction.SHOW_VISUALLY,
        VisualTutorAllowedAction.CHECK_WORK,
        VisualTutorAllowedAction.REQUEST_ANSWER,
        VisualTutorAllowedAction.STUCK,
    ]


def _live_action(
    *,
    id: str,
    type: VisualTutorCanvasActionType,
    sequence_index: int,
    text: Optional[str] = None,
    latex: Optional[str] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    points: Optional[list[dict]] = None,
    target_id: Optional[str] = None,
    locked: bool = False,
    reveal_policy: Optional[str] = None,
    group_id: str = "turn-focus",
    metadata: Optional[dict] = None,
) -> VisualTutorBoardAction:
    return VisualTutorBoardAction(
        id=id,
        type=type,
        sequence_index=sequence_index,
        duration_ms=_live_action_duration(type),
        wait_for_speech_marker=sequence_index == 0,
        requires_student_response=False,
        group_id=group_id,
        section_id="main-board",
        x=x,
        y=y,
        width=width,
        height=height,
        text=text,
        latex=latex,
        points=points or [],
        target_id=target_id,
        style=CanvasElementStyle(),
        locked=locked,
        reveal_policy=reveal_policy,
        metadata=metadata or {},
    )


def _live_action_duration(action_type: VisualTutorCanvasActionType) -> int:
    if action_type in {
        VisualTutorCanvasActionType.WRITE_TEXT,
        VisualTutorCanvasActionType.WRITE_EQUATION,
    }:
        return 700
    if action_type == VisualTutorCanvasActionType.HIGHLIGHT:
        return 250
    return 450


def _generic_live_actions_from_board(
    board: VisualTutorBoard,
    *,
    final_answer_locked: bool,
) -> list[VisualTutorBoardAction]:
    actions: list[VisualTutorBoardAction] = []
    first_visible_item = next(
        (
            item
            for item in board.items
            if item.status != "locked" and not _canvas_item_is_final(item)
        ),
        board.items[0] if board.items else None,
    )
    if first_visible_item is None:
        return actions
    is_math = _looks_like_math_text(first_visible_item.content)
    actions.append(
        _live_action(
            id=f"live-{_safe_id(first_visible_item.label)}-0",
            type=(
                VisualTutorCanvasActionType.WRITE_EQUATION
                if is_math
                else VisualTutorCanvasActionType.WRITE_TEXT
            ),
            sequence_index=0,
            text=first_visible_item.content,
            latex=first_visible_item.content if is_math else None,
            x=40,
            y=40,
            width=560,
            height=56,
            group_id=_safe_id(first_visible_item.label),
            metadata={
                "board_label": first_visible_item.label,
                "current_step": True,
                **first_visible_item.metadata,
            },
        )
    )
    for item in board.items:
        if _canvas_item_is_final(item) or item.status == "locked":
            actions.append(
                _live_action(
                    id=f"live-{_safe_id(item.label)}-locked",
                    type=VisualTutorCanvasActionType.HIDE,
                    sequence_index=len(actions),
                    text=(
                        "Final answer is locked."
                        if _canvas_item_is_final(item)
                        else None
                    ),
                    locked=True,
                    reveal_policy=(
                        "final_answer_unlocked"
                        if _canvas_item_is_final(item)
                        else "after_policy_unlock"
                    ),
                    group_id="locked-future",
                    metadata={
                        "hidden": True,
                        "future_step": not _canvas_item_is_final(item),
                        "is_final_answer": _canvas_item_is_final(item),
                        "final_answer_locked": final_answer_locked,
                    },
                )
            )
            break
    return actions[:2]


def _linear_live_actions(
    equation: LinearEquation,
    *,
    focus: str,
) -> list[VisualTutorBoardAction]:
    focus_value = (
        _format_linear_term(equation.rhs_coefficient, equation.variable)
        if equation.rhs_coefficient != 0
        else _format_expr(abs(equation.constant))
    )
    return [
        _live_action(
            id="linear-original-equation",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=equation.original,
            text=equation.original,
            x=40,
            y=40,
            width=560,
            height=56,
            group_id="linear-step-1",
            metadata={
                "current_step": True,
                "focus": focus,
                "sympy_verified": True,
            },
        ),
        _live_action(
            id="linear-step-1-question",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=2,
            text=f"Step 1: {_linear_first_focus_text(equation)}",
            x=40,
            y=112,
            width=460,
            height=40,
            group_id="linear-step-1",
            metadata={"current_step": True},
        ),
    ]


def _linear_correct_first_step_actions(
    equation: LinearEquation,
) -> list[VisualTutorBoardAction]:
    coefficient = _format_expr(equation.coefficient)
    return [
        _live_action(
            id="linear-step-1-result",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=equation.first_step_equation,
            text=equation.first_step_equation,
            x=40,
            y=178,
            width=560,
            height=56,
            group_id="linear-step-2",
            metadata={"validated": True, "current_step": False},
        ),
        _live_action(
            id="linear-highlight-coefficient",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=1,
            target_id=coefficient,
            x=40,
            y=174,
            width=72,
            height=48,
            group_id="linear-step-2",
            metadata={"reason": "isolate_variable", "coefficient": coefficient},
        ),
        _live_action(
            id="linear-step-2-question",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=2,
            text=f"Step 2: divide both sides by {coefficient}",
            x=40,
            y=250,
            width=520,
            height=40,
            group_id="linear-step-2",
            metadata={"current_step": True},
        ),
    ]


def _linear_constant_hint_actions(
    equation: LinearEquation,
) -> list[VisualTutorBoardAction]:
    focus_target = (
        _format_linear_term(equation.rhs_coefficient, equation.variable)
        if equation.rhs_coefficient != 0
        else _format_expr(abs(equation.constant))
    )
    return [
        _live_action(
            id="linear-focus-constant-again",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=0,
            target_id=focus_target,
            x=150,
            y=36,
            width=88,
            height=50,
            group_id="linear-hint-constant",
            metadata={
                "reason": "stuck_current_step",
                "current_step": True,
                "focus_target": focus_target,
            },
        ),
        _live_action(
            id="linear-constant-inverse-note",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=1,
            text=f"Next move: {equation.operation_text}.",
            x=40,
            y=178,
            width=620,
            height=44,
            group_id="linear-hint-constant",
            metadata={"current_step": True, "hint_only": True},
        ),
    ]


def _linear_isolate_x_hint_actions(
    equation: LinearEquation,
) -> list[VisualTutorBoardAction]:
    coefficient = _format_expr(equation.coefficient)
    return [
        _live_action(
            id="linear-isolate-current-equation",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=equation.first_step_equation,
            text=equation.first_step_equation,
            x=40,
            y=178,
            width=560,
            height=56,
            group_id="linear-hint-isolate",
            metadata={"current_step": True, "hint_only": True},
        ),
        _live_action(
            id="linear-isolate-highlight-coefficient",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=1,
            target_id=coefficient,
            x=40,
            y=174,
            width=72,
            height=48,
            group_id="linear-hint-isolate",
            metadata={"reason": "divide_by_coefficient", "coefficient": coefficient},
        ),
        _live_action(
            id="linear-isolate-question-note",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=2,
            text=f"What operation cancels the {coefficient} beside {equation.variable}?",
            x=40,
            y=250,
            width=620,
            height=40,
            group_id="linear-hint-isolate",
            metadata={"current_step": True, "hint_only": True},
        ),
    ]


def _linear_balance_scale_actions(
    equation: LinearEquation,
) -> list[VisualTutorBoardAction]:
    focus_target = (
        _format_linear_term(equation.rhs_coefficient, equation.variable)
        if equation.rhs_coefficient != 0
        else _format_expr(abs(equation.constant))
    )
    return [
        _live_action(
            id="linear-balance-original",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=equation.original,
            text=equation.original,
            x=40,
            y=40,
            width=560,
            height=56,
            group_id="linear-balance-view",
            metadata={"current_step": True},
        ),
        _live_action(
            id="linear-balance-arrow-left",
            type=VisualTutorCanvasActionType.DRAW_ARROW,
            sequence_index=1,
            points=[
                {"x": 180, "y": 92},
                {"x": 180, "y": 142},
            ],
            group_id="linear-balance-view",
            metadata={"label": focus_target, "hint_only": True},
        ),
        _live_action(
            id="linear-balance-note",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=2,
            text=f"Same move on both sides: {equation.operation_text}.",
            x=40,
            y=170,
            width=560,
            height=42,
            group_id="linear-balance-view",
            metadata={"current_step": True, "hint_only": True},
        ),
    ]


def _linear_incorrect_partial_actions(
    equation: LinearEquation,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="linear-partial-first-step",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=equation.first_step_equation,
            text=equation.first_step_equation,
            x=40,
            y=178,
            width=560,
            height=56,
            group_id="linear-partial-after-wrong",
            metadata={"current_step": False, "partial_solution": True},
        ),
        _live_action(
            id="linear-partial-next-focus",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=1,
            target_id=_format_expr(equation.coefficient),
            x=40,
            y=174,
            width=72,
            height=48,
            group_id="linear-partial-after-wrong",
            metadata={"reason": "next_step_after_partial"},
        ),
    ]


def _linear_final_step_actions(
    equation: LinearEquation,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="linear-final-equation",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=equation.final_equation,
            text=equation.final_equation,
            x=40,
            y=318,
            width=520,
            height=56,
            group_id="linear-final-step",
            metadata={"current_step": True, "is_final_answer": True},
        ),
        _live_action(
            id="linear-final-circle",
            type=VisualTutorCanvasActionType.CIRCLE,
            sequence_index=1,
            x=34,
            y=312,
            width=150,
            height=54,
            group_id="linear-final-step",
            metadata={"reason": "answer_verified", "is_final_answer": True},
        ),
        _live_action(
            id="linear-check-substitution",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=2,
            latex=_linear_substitution_check_equation(equation),
            text=_linear_substitution_check_equation(equation),
            x=40,
            y=392,
            width=620,
            height=56,
            group_id="linear-final-step",
            metadata={"current_step": True, "understanding_check": True},
        ),
    ]


def _linear_understanding_check_actions(
    equation: LinearEquation,
    *,
    confirmed: bool,
) -> list[VisualTutorBoardAction]:
    solution = _format_expr(equation.solution)
    check_text = (
        "Yes, the substitution is true."
        if confirmed
        else "Let's recompute this substitution."
    )
    return [
        _live_action(
            id="linear-understanding-check-focus",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=0,
            x=40,
            y=392,
            width=260,
            height=48,
            group_id="linear-understanding-check",
            metadata={"reason": "verify_substitution", "confirmed": confirmed},
        ),
        _live_action(
            id="linear-understanding-check-note",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=1,
            text=check_text,
            x=40,
            y=466,
            width=640,
            height=44,
            group_id="linear-understanding-check",
            metadata={
                "understanding_check": True,
                "confirmed": confirmed,
                "solution": solution,
            },
        ),
    ]


def _linear_wrong_first_step_actions(
    equation: LinearEquation,
    student_input: str,
) -> list[VisualTutorBoardAction]:
    focus_target = (
        _format_linear_term(equation.rhs_coefficient, equation.variable)
        if equation.rhs_coefficient != 0
        else _format_expr(abs(equation.constant))
    )
    return [
        _live_action(
            id="linear-student-input-mistake",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=0,
            text=f"Your input: {student_input.strip()[:48]}",
            x=40,
            y=178,
            width=620,
            height=40,
            group_id="linear-wrong-first-step",
            metadata={"student_input": student_input, "mistake": True},
        ),
        _live_action(
            id="linear-cross-out-wrong-input",
            type=VisualTutorCanvasActionType.CROSS_OUT,
            sequence_index=1,
            x=40,
            y=178,
            width=280,
            height=40,
            group_id="linear-wrong-first-step",
            metadata={"reason": "does_not_match_current_step"},
        ),
        _live_action(
            id="linear-redirect-constant",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=2,
            target_id=focus_target,
            x=150,
            y=36,
            width=88,
            height=50,
            group_id="linear-wrong-first-step",
            metadata={"reason": "redirect_to_current_step", "current_step": True},
        ),
        _live_action(
            id="linear-redirect-question",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=3,
            text=f"Focus here first: {equation.operation_text}.",
            x=40,
            y=238,
            width=560,
            height=42,
            group_id="linear-wrong-first-step",
            metadata={"current_step": True},
        ),
    ]


def _line_delta_y_actions(line: LineThroughPoints) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-draw-axes",
            type=VisualTutorCanvasActionType.DRAW_AXES,
            sequence_index=0,
            x=80,
            y=60,
            width=360,
            height=260,
            group_id="delta-y",
            metadata={"current_step": True},
        ),
        _live_action(
            id=f"line-point-{line.first_label.lower()}",
            type=VisualTutorCanvasActionType.DRAW_POINT,
            sequence_index=1,
            x=140,
            y=190,
            text=line.first_label,
            points=[
                {
                    "label": line.first_label,
                    "x": float(line.x1),
                    "y": float(line.y1),
                }
            ],
            group_id="delta-y",
            metadata={"math_x": float(line.x1), "math_y": float(line.y1)},
        ),
        _live_action(
            id=f"line-point-{line.second_label.lower()}",
            type=VisualTutorCanvasActionType.DRAW_POINT,
            sequence_index=2,
            x=240,
            y=100,
            text=line.second_label,
            points=[
                {
                    "label": line.second_label,
                    "x": float(line.x2),
                    "y": float(line.y2),
                }
            ],
            group_id="delta-y",
            metadata={"math_x": float(line.x2), "math_y": float(line.y2)},
        ),
        _live_action(
            id="line-highlight-delta-y",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=3,
            target_id="y-values",
            x=460,
            y=84,
            width=180,
            height=56,
            group_id="delta-y",
            metadata={"reason": "vertical_change", "current_step": True},
        ),
        _live_action(
            id="line-write-delta-y",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=4,
            latex=(
                rf"\Delta y = {_format_expr(line.y2)} - "
                rf"{_format_expr(line.y1)} = ?"
            ),
            text=(
                f"Delta y = {_format_expr(line.y2)} - " f"{_format_expr(line.y1)} = ?"
            ),
            x=460,
            y=150,
            width=360,
            height=56,
            group_id="delta-y",
            metadata={"current_step": True},
        ),
    ]


def _line_delta_x_actions(line: LineThroughPoints) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-highlight-delta-x",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=0,
            target_id="x-values",
            x=80,
            y=320,
            width=260,
            height=48,
            group_id="delta-x",
            metadata={"reason": "horizontal_change", "current_step": True},
        ),
        _live_action(
            id="line-write-delta-x",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=1,
            latex=(
                rf"\Delta x = {_format_expr(line.x2)} - "
                rf"{_format_expr(line.x1)} = ?"
            ),
            text=(
                f"Delta x = {_format_expr(line.x2)} - " f"{_format_expr(line.x1)} = ?"
            ),
            x=460,
            y=218,
            width=360,
            height=56,
            group_id="delta-x",
            metadata={"current_step": True},
        ),
    ]


def _line_delta_y_answer_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-write-delta-y-answer",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=rf"\Delta y = {_format_expr(line.delta_y)}",
            text=f"Delta y = {_format_expr(line.delta_y)}",
            x=460,
            y=150,
            width=360,
            height=56,
            group_id="delta-y",
            metadata={"current_step": False, "validated": True},
        ),
    ]


def _line_delta_x_answer_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-write-delta-x-answer",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=rf"\Delta x = {_format_expr(line.delta_x)}",
            text=f"Delta x = {_format_expr(line.delta_x)}",
            x=460,
            y=218,
            width=360,
            height=56,
            group_id="delta-x",
            metadata={"current_step": False, "validated": True},
        ),
    ]


def _line_slope_question_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-write-slope-question",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=1,
            latex=(
                rf"m = \frac{{\Delta y}}{{\Delta x}} = "
                rf"\frac{{{_format_expr(line.delta_y)}}}{{{_format_expr(line.delta_x)}}} = ?"
            ),
            text=(
                f"m = Delta y / Delta x = "
                f"{_format_expr(line.delta_y)} / {_format_expr(line.delta_x)} = ?"
            ),
            x=460,
            y=286,
            width=380,
            height=60,
            group_id="slope",
            metadata={"current_step": True, "formula": "slope"},
        ),
    ]


def _line_slope_formula_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-write-slope-formula",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=r"m = \frac{\Delta y}{\Delta x}",
            text="m = Delta y / Delta x",
            x=460,
            y=286,
            width=360,
            height=56,
            group_id="slope-formula",
            metadata={"current_step": True, "formula": "slope"},
        ),
        _live_action(
            id="line-final-equation-hidden",
            type=VisualTutorCanvasActionType.HIDE,
            sequence_index=1,
            text="Final answer is locked.",
            locked=True,
            reveal_policy="final_answer_unlocked",
            group_id="locked-future",
            metadata={"is_final_answer": True, "hidden": True},
        ),
    ]


def _line_slope_answer_actions(line: LineThroughPoints) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-write-slope-answer",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=rf"m = {_format_expr(line.slope)}",
            text=f"m = {_format_expr(line.slope)}",
            x=460,
            y=286,
            width=360,
            height=56,
            group_id="slope",
            metadata={
                "current_step": False,
                "validated": True,
                "locked_safe_partial": True,
                "partial_value": "slope",
            },
        ),
    ]


def _line_intercept_question_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id=f"line-highlight-point-{line.first_label.lower()}",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=1,
            target_id=f"line-point-{line.first_label.lower()}",
            x=118,
            y=128,
            width=70,
            height=54,
            group_id="intercept",
            metadata={
                "current_step": True,
                "reason": "use_known_point",
                "point": line.first_label,
            },
        ),
        _live_action(
            id="line-write-slope-intercept-form",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=2,
            latex="y = mx + b",
            text="y = mx + b",
            x=460,
            y=354,
            width=360,
            height=56,
            group_id="intercept",
            metadata={"current_step": True, "formula": "slope_intercept"},
        ),
        _live_action(
            id="line-write-intercept-blank",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=3,
            latex=(
                rf"{_format_expr(line.y1)} = {_format_expr(line.slope)}"
                rf"({_format_expr(line.x1)}) + \_\_"
            ),
            text=(
                f"{_format_expr(line.y1)} = {_format_expr(line.slope)}"
                f"({_format_expr(line.x1)}) + __"
            ),
            x=460,
            y=418,
            width=400,
            height=60,
            group_id="intercept",
            metadata={"current_step": True, "blank": "b"},
        ),
    ]


def _line_intercept_stuck_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return _line_intercept_question_actions(line)


def _line_intercept_answer_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-write-intercept-answer",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=0,
            latex=rf"b = {_format_expr(line.intercept)}",
            text=f"b = {_format_expr(line.intercept)}",
            x=460,
            y=486,
            width=360,
            height=56,
            group_id="intercept",
            metadata={
                "current_step": False,
                "validated": True,
                "locked_safe_partial": True,
                "partial_value": "intercept",
            },
        )
    ]


def _line_final_locked_actions(line: LineThroughPoints) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-final-equation-locked",
            type=VisualTutorCanvasActionType.HIDE,
            sequence_index=1,
            text=line.final_equation,
            latex=line.final_equation,
            locked=True,
            reveal_policy="final_answer_unlocked",
            group_id="locked-future",
            metadata={
                "hidden": True,
                "is_final_answer": True,
                "final_answer_locked": True,
            },
        )
    ]


def _line_full_solution_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-reveal-final-equation-prefix",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            sequence_index=0,
            text="Now combine m and b:",
            x=460,
            y=544,
            width=360,
            height=48,
            group_id="final",
            metadata={"current_step": True},
        ),
        _live_action(
            id="line-reveal-final-equation",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=1,
            latex=line.final_equation,
            text=line.final_equation,
            x=460,
            y=596,
            width=360,
            height=60,
            group_id="final",
            metadata={"current_step": True, "is_final_answer": True},
        ),
    ]


def _line_wrong_delta_y_actions(
    line: LineThroughPoints,
) -> list[VisualTutorBoardAction]:
    return [
        _live_action(
            id="line-highlight-y-values-after-wrong",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            sequence_index=0,
            target_id="y-values",
            x=460,
            y=84,
            width=180,
            height=56,
            group_id="delta-y",
            metadata={"reason": "first_mistake", "misconception": "wrong_delta_y"},
        ),
        _live_action(
            id="line-rewrite-delta-y-question",
            type=VisualTutorCanvasActionType.WRITE_EQUATION,
            sequence_index=1,
            latex=(
                rf"\Delta y = {_format_expr(line.y2)} - "
                rf"{_format_expr(line.y1)} = ?"
            ),
            text=(
                f"Delta y = {_format_expr(line.y2)} - " f"{_format_expr(line.y1)} = ?"
            ),
            x=460,
            y=150,
            width=360,
            height=56,
            group_id="delta-y",
            metadata={"current_step": True},
        ),
    ]


def _line_wrong_step_actions(
    line: LineThroughPoints, current_step_index: int
) -> list[VisualTutorBoardAction]:
    if current_step_index <= 0:
        return _line_wrong_delta_y_actions(line)
    if current_step_index == 1:
        return [
            _live_action(
                id="line-highlight-x-values-after-wrong",
                type=VisualTutorCanvasActionType.HIGHLIGHT,
                sequence_index=0,
                target_id="x-values",
                x=80,
                y=320,
                width=260,
                height=48,
                group_id="delta-x",
                metadata={
                    "reason": "first_mistake",
                    "misconception": "wrong_delta_x",
                },
            ),
            _live_action(
                id="line-rewrite-delta-x-question",
                type=VisualTutorCanvasActionType.WRITE_EQUATION,
                sequence_index=1,
                latex=(
                    rf"\Delta x = {_format_expr(line.x2)} - "
                    rf"{_format_expr(line.x1)} = ?"
                ),
                text=(
                    f"Delta x = {_format_expr(line.x2)} - "
                    f"{_format_expr(line.x1)} = ?"
                ),
                x=460,
                y=218,
                width=360,
                height=56,
                group_id="delta-x",
                metadata={"current_step": True},
            ),
        ]
    if current_step_index == 2:
        return _line_slope_question_actions(line)
    return _line_intercept_question_actions(line)


def attach_canvas_actions_to_solver_response(
    response: VisualTutorTurnResponse,
) -> VisualTutorTurnResponse:
    if response.canvas_actions:
        return response
    return response.model_copy(
        update={
            "canvas_actions": _canvas_actions_from_board(
                response.board,
                final_answer_locked=response.final_answer_locked,
                teaching_mode=response.teaching_mode,
            )
        }
    )


def _canvas_actions_from_board(
    board: VisualTutorBoard,
    *,
    final_answer_locked: bool,
    teaching_mode: VisualTutorTeachingMode,
) -> list[VisualTutorCanvasAction]:
    actions: list[VisualTutorCanvasAction] = [
        VisualTutorCanvasAction(
            id=f"canvas-{_safe_id(board.title or board.type.value)}-speak",
            type=VisualTutorCanvasActionType.SPEAK_MARKER,
            metadata={
                "teaching_mode": teaching_mode.value,
                "board_type": board.type.value,
            },
        )
    ]
    y = 36.0
    highlighted_current_step = False
    first_teaching_action_id: str | None = None
    first_teaching_action_y: float | None = None
    for index, item in enumerate(board.items):
        item_id = f"canvas-{_safe_id(item.label)}-{index}"
        is_final = _canvas_item_is_final(item)
        locked = item.status == "locked" or (final_answer_locked and is_final)
        reveal_policy = "final_answer_unlocked" if is_final else None
        if item.label.strip().lower() == "problem":
            actions.append(
                VisualTutorCanvasAction(
                    id=item_id,
                    type=VisualTutorCanvasActionType.WRITE_EQUATION,
                    x=40,
                    y=y,
                    width=520,
                    height=48,
                    text=item.content,
                    latex=item.content,
                    metadata={
                        "board_label": item.label,
                        "current_step": item.status == "active",
                    },
                )
            )
            y += 72
            continue

        if not is_final and first_teaching_action_id is None:
            first_teaching_action_id = item_id
            first_teaching_action_y = y
        action_type = (
            VisualTutorCanvasActionType.HIDE
            if locked
            else (
                VisualTutorCanvasActionType.WRITE_EQUATION
                if _looks_like_math_text(item.content)
                else VisualTutorCanvasActionType.WRITE_TEXT
            )
        )
        text = item.content
        latex = item.content if _looks_like_math_text(item.content) else None
        if locked and is_final:
            text = "Final answer is locked."
            latex = None
        actions.append(
            VisualTutorCanvasAction(
                id=item_id,
                type=action_type,
                x=40,
                y=y,
                width=560,
                height=56,
                text=text,
                latex=latex,
                locked=locked,
                reveal_policy=reveal_policy,
                metadata={
                    "board_label": item.label,
                    "board_status": item.status,
                    "current_step": item.status == "active" and not is_final,
                    "is_final_answer": is_final,
                    "future_step": locked and not is_final,
                    **item.metadata,
                },
            )
        )
        if item.status == "active" and not is_final:
            highlighted_current_step = True
            actions.append(
                VisualTutorCanvasAction(
                    id=f"{item_id}-highlight",
                    type=VisualTutorCanvasActionType.HIGHLIGHT,
                    target_id=item_id,
                    x=34,
                    y=y - 4,
                    width=580,
                    height=64,
                    metadata={
                        "reason": "current_step",
                        "board_label": item.label,
                    },
                )
            )
        y += 76

    if not highlighted_current_step and first_teaching_action_id is not None:
        actions.append(
            VisualTutorCanvasAction(
                id=f"{first_teaching_action_id}-highlight",
                type=VisualTutorCanvasActionType.HIGHLIGHT,
                target_id=first_teaching_action_id,
                x=34,
                y=(first_teaching_action_y or 112) - 4,
                width=580,
                height=64,
                metadata={"reason": "current_step"},
            )
        )

    actions.extend(_specialized_canvas_actions(board))
    actions.append(
        VisualTutorCanvasAction(
            id=f"canvas-{_safe_id(board.title or board.type.value)}-pause",
            type=VisualTutorCanvasActionType.PAUSE_MARKER,
            metadata={"duration_ms": 250},
        )
    )
    return actions


def _specialized_canvas_actions(
    board: VisualTutorBoard,
) -> list[VisualTutorCanvasAction]:
    if board.title != "Linear Equation":
        return []
    constant = str(board.metadata.get("constant") or "").strip()
    if not constant:
        return []
    return [
        VisualTutorCanvasAction(
            id="canvas-linear-step-1-remove-constant",
            type=VisualTutorCanvasActionType.WRITE_TEXT,
            x=40,
            y=112,
            width=420,
            height=36,
            text="Step 1: remove the constant",
            metadata={"current_step": True, "operation": f"subtract {constant}"},
        ),
        VisualTutorCanvasAction(
            id="canvas-linear-highlight-constant",
            type=VisualTutorCanvasActionType.HIGHLIGHT,
            target_id=f"+ {constant}",
            x=160,
            y=36,
            width=72,
            height=44,
            metadata={"reason": "remove_constant", "constant": constant},
        ),
    ]


def _canvas_item_is_final(item: VisualTutorBoardItem) -> bool:
    label = item.label.lower()
    return (
        "final" in label
        or "answer" in label
        or item.metadata.get("is_final_answer") is True
        or item.metadata.get("final_answer") is True
    )


def _looks_like_math_text(text: str) -> bool:
    return bool(re.search(r"[=+\-*/^()]|\b[xyabcm]\b", text, re.IGNORECASE))


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return safe or "item"


def _build_slope_board(
    line: LineThroughPoints,
    *,
    reveal_partial: bool = False,
    reveal_final: bool = False,
    feedback: Optional[str] = None,
) -> VisualTutorBoard:
    items = [
        VisualTutorBoardItem(
            label="Problem",
            content=f"Find slope through {line.original}",
            status="active",
        ),
        VisualTutorBoardItem(
            label="Formula",
            content="m = (y2 - y1) / (x2 - x1)",
            status="complete",
        ),
        VisualTutorBoardItem(
            label="Setup",
            content=(
                line.slope_step
                if reveal_partial or reveal_final
                else "Substitute both points into the slope formula."
            ),
            status="complete" if reveal_partial or reveal_final else "locked",
        ),
        VisualTutorBoardItem(
            label="Final",
            content=(
                f"m = {_format_expr(line.slope)}"
                if reveal_final
                else "Final answer is locked."
            ),
            status="complete" if reveal_final else "locked",
        ),
    ]
    metadata = {
        "problem_type": "slope_from_two_points",
        "normalized_problem": line.normalized,
        "slope": _format_expr(line.slope),
        "current_step_index": 0 if not reveal_partial else 1,
    }
    if feedback:
        metadata["feedback"] = feedback
    return VisualTutorBoard(
        type=VisualTutorBoardType.EQUATION_STEPS,
        title="Slope From Two Points",
        items=items,
        metadata=metadata,
    )


def _build_quadratic_board(
    problem: dict,
    *,
    reveal_partial: bool = False,
    reveal_final: bool = False,
    feedback: Optional[str] = None,
) -> VisualTutorBoard:
    roots_text = " or ".join(f"x = {_format_expr(root)}" for root in problem["roots"])
    items = [
        VisualTutorBoardItem(
            label="Problem",
            content=problem["equation"],
            status="active",
        ),
        VisualTutorBoardItem(
            label="Method",
            content="Try factoring or another quadratic method.",
            status="active",
        ),
        VisualTutorBoardItem(
            label="Factor Form",
            content=(
                f"{problem['factorization']} = 0"
                if reveal_partial or reveal_final
                else "Factor form is locked until you try."
            ),
            status="complete" if reveal_partial or reveal_final else "locked",
        ),
        VisualTutorBoardItem(
            label="Final",
            content=roots_text if reveal_final else "Final answer is locked.",
            status="complete" if reveal_final else "locked",
        ),
    ]
    metadata = {
        "problem_type": "quadratic_equation",
        "normalized_problem": problem["normalized"],
        "current_step_index": 1 if reveal_partial else 0,
    }
    if feedback:
        metadata["feedback"] = feedback
    return VisualTutorBoard(
        type=VisualTutorBoardType.EQUATION_STEPS,
        title="Quadratic Equation",
        items=items,
        metadata=metadata,
    )


def _build_arithmetic_board(
    problem: dict,
    *,
    reveal_partial: bool = False,
    reveal_final: bool = False,
    feedback: Optional[str] = None,
) -> VisualTutorBoard:
    items = [
        VisualTutorBoardItem(
            label="Expression",
            content=problem["expression"],
            status="active",
        ),
        VisualTutorBoardItem(
            label="Order",
            content="Parentheses -> multiply/divide -> add/subtract",
            status="active",
        ),
        VisualTutorBoardItem(
            label="Partial",
            content=(
                problem["partial"]
                if reveal_partial or reveal_final
                else "First simplification is locked until you try."
            ),
            status="complete" if reveal_partial or reveal_final else "locked",
        ),
        VisualTutorBoardItem(
            label="Final",
            content=(
                _format_expr(problem["answer"])
                if reveal_final
                else "Final answer is locked."
            ),
            status="complete" if reveal_final else "locked",
        ),
    ]
    metadata = {
        "problem_type": "arithmetic_expression",
        "current_step_index": 1 if reveal_partial else 0,
    }
    if feedback:
        metadata["feedback"] = feedback
    return VisualTutorBoard(
        type=VisualTutorBoardType.EQUATION_STEPS,
        title="Arithmetic Expression",
        items=items,
        metadata=metadata,
    )


def _build_percentage_board(
    problem: dict,
    *,
    reveal_partial: bool = False,
    reveal_final: bool = False,
    feedback: Optional[str] = None,
) -> VisualTutorBoard:
    setup = f"{problem['percent_text']}/100 x {problem['base_text']}"
    items = [
        VisualTutorBoardItem(
            label="Problem",
            content=problem["problem"],
            status="active",
        ),
        VisualTutorBoardItem(
            label="Percent",
            content=f"{problem['percent_text']}% means {problem['percent_text']}/100",
            status="active",
        ),
        VisualTutorBoardItem(
            label="Setup",
            content=(
                setup
                if reveal_partial or reveal_final
                else "Multiplication setup is locked until you try."
            ),
            status="complete" if reveal_partial or reveal_final else "locked",
        ),
        VisualTutorBoardItem(
            label="Final",
            content=(
                _format_expr(problem["answer"])
                if reveal_final
                else "Final answer is locked."
            ),
            status="complete" if reveal_final else "locked",
        ),
    ]
    metadata = {
        "problem_type": "simple_percentage_word_problem",
        "percent": problem["percent_text"],
        "base": problem["base_text"],
        "current_step_index": 1 if reveal_partial else 0,
    }
    if feedback:
        metadata["feedback"] = feedback
    return VisualTutorBoard(
        type=VisualTutorBoardType.EQUATION_STEPS,
        title="Percentage",
        items=items,
        metadata=metadata,
    )


def _contains_all_roots(message: str, roots: list[sympy.Expr]) -> bool:
    return all(_contains_value(message, root) for root in roots)


def _validation_facts_from_policy(
    policy: VisualTutorPolicyDecision,
    validation: dict[str, Any],
) -> VisualTutorStudentValidationFacts:
    validation_result = _string_or_none(validation.get("validation_result"))
    relevance = _string_or_none(validation.get("input_relevance"))
    is_correct = validation_result in {
        "correct_step",
        "correct_operation",
        "correct_final_step",
        "correct_answer",
    }
    return VisualTutorStudentValidationFacts(
        is_valid=validation_result not in {None, "unknown", "off_topic"},
        is_correct=is_correct,
        is_relevant=relevance
        in {"relevant_step", "possible_final_answer", "clarification"},
        is_possible_final_answer=relevance == "possible_final_answer"
        or validation_result == "correct_final_step",
        mistake_type=_string_or_none(validation.get("misconception_type"))
        or (None if is_correct else validation_result),
        mistake_location=_string_or_none(validation.get("mistake_location")),
        explanation=_string_or_none(validation.get("explanation"))
        or _validation_explanation(validation_result, is_correct=is_correct),
        metadata=validation,
    )


def _linear_student_validation_facts(
    request: VisualTutorTurnRequest,
    equation: LinearEquation,
    policy: VisualTutorPolicyDecision,
) -> VisualTutorStudentValidationFacts:
    message = request.message.strip()
    if (
        request.action == VisualTutorAction.SUBMIT_PROBLEM
        and not request.student_submitted_step
    ):
        return VisualTutorStudentValidationFacts(
            is_valid=False,
            is_correct=False,
            is_relevant=False,
            is_possible_final_answer=False,
            explanation="No student step has been validated yet.",
            metadata={
                "validation_result": None,
                "input_relevance": None,
                "policy_reason": policy.reason,
                "client_action": request.action.value,
            },
        )
    validation = LiveTeacherMoveMixin().validate_student_response(
        request,
        VisualTutorProblemUnderstandingResult(
            subject="Mathematics",
            topic="Linear Equations",
            problem_type="linear_equation_one_variable",
            confidence=1,
            extracted_problem=equation.original,
            known_solver_available=True,
            recommended_board_type=VisualTutorBoardType.EQUATION_STEPS,
        ),
        policy,
    )
    validation_result = policy.validation_result
    is_correct_first = validation_result in {
        "correct_step",
        "correct_operation",
    } or _equations_equivalent(message, equation.first_step_equation)
    is_correct_final = (
        validation_result == "correct_final_step"
        or _equations_equivalent(message, equation.final_equation)
    )
    is_possible_final = (
        policy.input_relevance is not None
        and policy.input_relevance.value == "possible_final_answer"
    ) or is_correct_final
    is_correct = is_correct_first or is_correct_final
    is_relevant = (
        policy.input_relevance is not None
        and policy.input_relevance.value
        in {"relevant_step", "possible_final_answer", "clarification"}
    ) or is_correct
    effective_result = (
        "correct_final_step"
        if is_correct_final
        else "correct_step" if is_correct_first else validation_result
    )
    validation["validation_result"] = effective_result
    return VisualTutorStudentValidationFacts(
        is_valid=bool(message),
        is_correct=is_correct,
        is_relevant=is_relevant,
        is_possible_final_answer=is_possible_final,
        mistake_type=None if is_correct else _linear_mistake_type(policy),
        mistake_location=None if is_correct else _linear_mistake_location(policy),
        explanation=(
            "The student reached the verified final answer."
            if is_correct_final
            else (
                "The student gave a correct first step."
                if is_correct_first
                else _linear_validation_explanation(equation, policy)
            )
        ),
        metadata=validation,
    )


def _line_student_validation_facts(
    request: VisualTutorTurnRequest,
    line: LineThroughPoints,
    policy: VisualTutorPolicyDecision,
) -> VisualTutorStudentValidationFacts:
    current_step_index = request.current_state.current_step_index
    is_correct = (
        (current_step_index <= 0 and _contains_value(request.message, line.delta_y))
        or (current_step_index == 1 and _contains_value(request.message, line.delta_x))
        or (
            current_step_index == 2
            and (
                _contains_value(request.message, line.slope)
                or _line_step_is_correct(request.message, line)
            )
        )
        or (
            current_step_index >= 3 and _contains_value(request.message, line.intercept)
        )
    )
    return _generic_answer_validation_facts(
        request,
        is_correct=is_correct,
        policy=policy,
        correct_explanation="The student response matches the current coordinate step.",
        expected_explanation=f"Expected {_line_expected_step(current_step_index)}.",
    )


def _slope_student_validation_facts(
    request: VisualTutorTurnRequest,
    line: LineThroughPoints,
    policy: VisualTutorPolicyDecision,
) -> VisualTutorStudentValidationFacts:
    return _generic_answer_validation_facts(
        request,
        is_correct=_line_step_is_correct(request.message, line),
        policy=policy,
        correct_explanation="The submitted slope matches the two points.",
        expected_explanation="The input should compare Δy and Δx.",
    )


def _generic_answer_validation_facts(
    request: VisualTutorTurnRequest,
    *,
    is_correct: bool,
    policy: VisualTutorPolicyDecision,
    correct_explanation: str,
    expected_explanation: str,
) -> VisualTutorStudentValidationFacts:
    validation = {
        "student_intent": policy.metadata.get("student_intent"),
        "input_relevance": (
            policy.input_relevance.value if policy.input_relevance else None
        ),
        "validation_result": (
            "correct_answer" if is_correct else policy.validation_result
        ),
        "misconception_type": policy.misconception_type,
        "client_action": request.action.value,
    }
    relevance = validation["input_relevance"]
    return VisualTutorStudentValidationFacts(
        is_valid=bool(request.message.strip()),
        is_correct=is_correct,
        is_relevant=is_correct
        or relevance in {"relevant_step", "possible_final_answer", "clarification"},
        is_possible_final_answer=relevance == "possible_final_answer",
        mistake_type=(
            None
            if is_correct
            else policy.misconception_type or policy.validation_result
        ),
        mistake_location=None,
        explanation=correct_explanation if is_correct else expected_explanation,
        metadata=validation,
    )


def _line_expected_operation(line: LineThroughPoints, current_step_index: int) -> str:
    if current_step_index <= 0:
        return f"{_format_expr(line.y2)} - {_format_expr(line.y1)}"
    if current_step_index == 1:
        return f"{_format_expr(line.x2)} - {_format_expr(line.x1)}"
    if current_step_index == 2:
        return f"{_format_expr(line.delta_y)} / {_format_expr(line.delta_x)}"
    return f"{_format_expr(line.y1)} = {_format_expr(line.slope)}({_format_expr(line.x1)}) + b"


def _line_expected_equation(line: LineThroughPoints, current_step_index: int) -> str:
    if current_step_index <= 0:
        return f"Δy = {_format_expr(line.y2)} - {_format_expr(line.y1)}"
    if current_step_index == 1:
        return f"Δx = {_format_expr(line.x2)} - {_format_expr(line.x1)}"
    if current_step_index == 2:
        return f"m = {_format_expr(line.delta_y)} / {_format_expr(line.delta_x)}"
    return line.final_equation


def _line_next_concept(current_step_index: int) -> str:
    if current_step_index <= 0:
        return "horizontal change Δx"
    if current_step_index == 1:
        return "slope"
    if current_step_index == 2:
        return "y-intercept"
    return "write the final line equation"


def _line_board_context(line: LineThroughPoints) -> dict[str, Any]:
    return {
        "points": [
            {
                "label": line.first_label,
                "x": _format_expr(line.x1),
                "y": _format_expr(line.y1),
            },
            {
                "label": line.second_label,
                "x": _format_expr(line.x2),
                "y": _format_expr(line.y2),
            },
        ],
        "delta_y": _format_expr(line.delta_y),
        "delta_x": _format_expr(line.delta_x),
        "slope": _format_expr(line.slope),
        "intercept": _format_expr(line.intercept),
        "final_equation": line.final_equation,
    }


def _linear_mistake_type(policy: VisualTutorPolicyDecision) -> Optional[str]:
    return policy.misconception_type or policy.validation_result


def _linear_mistake_location(policy: VisualTutorPolicyDecision) -> Optional[str]:
    if policy.validation_result in {"incorrect_relevant_step", "incorrect_step"}:
        return "current_step"
    if policy.validation_result == "incorrect_final_answer":
        return "final_answer"
    return None


def _linear_validation_explanation(
    equation: LinearEquation,
    policy: VisualTutorPolicyDecision,
) -> str:
    if policy.validation_result == "incorrect_final_answer":
        return f"The final answer should satisfy {equation.original}."
    if policy.validation_result in {"incorrect_relevant_step", "incorrect_step"}:
        return f"The current expected equation is {equation.first_step_equation}."
    return f"The expected operation is {equation.operation_text}."


def _validation_explanation(
    validation_result: Optional[str],
    *,
    is_correct: bool,
) -> str:
    if is_correct:
        return "The student response matches the expected step."
    if validation_result:
        return f"Validation result: {validation_result}."
    return "No student step has been validated yet."


def _solver_fact_json_context(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _solver_fact_json_context(item) for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_solver_fact_json_context(item) for item in value]
    if isinstance(value, sympy.Basic):
        return _format_expr(value)
    return value


def _string_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _contains_value(message: str, value: sympy.Expr) -> bool:
    normalized = message.replace("−", "-").replace("^", "**")
    candidates = re.findall(r"[-+]?\d+(?:/\d+)?(?:\.\d+)?", normalized)
    for candidate in candidates:
        try:
            if sympy.simplify(sympy.Rational(candidate) - value) == 0:
                return True
        except Exception:
            continue
    return False


def _contains_expression_value(message: str, value: sympy.Expr) -> bool:
    candidates = re.findall(
        r"[-+]?\d+(?:\.\d+)?\s*/\s*[-+]?\d+(?:\.\d+)?",
        message.replace("−", "-"),
    )
    for candidate in candidates:
        try:
            if sympy.simplify(sympy.sympify(candidate) - value) == 0:
                return True
        except Exception:
            continue
    return False


def _arithmetic_partial(expression: str) -> str:
    if "(" in expression and ")" in expression:
        match = re.search(r"\(([^()]+)\)", expression)
        if match:
            inner = match.group(1)
            try:
                value = _format_expr(sympy.simplify(sympy.sympify(inner)))
                return expression[: match.start()] + value + expression[match.end() :]
            except Exception:
                pass
    match = re.search(r"[-+]?\d+(?:\.\d+)?\s*[*/]\s*[-+]?\d+(?:\.\d+)?", expression)
    if match:
        try:
            value = _format_expr(sympy.simplify(sympy.sympify(match.group(0))))
            return expression[: match.start()] + value + expression[match.end() :]
        except Exception:
            pass
    return expression


def _problem_source(
    request: VisualTutorTurnRequest,
    understanding: VisualTutorProblemUnderstandingResult,
) -> str:
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
        return request.current_state.problem_text
    if request.current_state.problem_text:
        return request.current_state.problem_text
    return understanding.extracted_problem or request.message


def _format_expr(value: sympy.Expr) -> str:
    text = str(sympy.simplify(value))
    return text.replace("**", "^")


def _format_linear_term(coefficient: sympy.Expr, variable: str) -> str:
    coefficient = sympy.simplify(coefficient)
    if coefficient == 1:
        return variable
    if coefficient == -1:
        return f"-{variable}"
    if isinstance(coefficient, sympy.Rational) and coefficient.q != 1:
        numerator = coefficient.p
        denominator = coefficient.q
        if numerator == 1:
            return f"{variable}/{denominator}"
        if numerator == -1:
            return f"-{variable}/{denominator}"
        return f"({numerator}/{denominator}){variable}"
    return f"{_format_expr(coefficient)}{variable}"


def _format_linear_expression(
    coefficient: sympy.Expr, constant: sympy.Expr, variable: str
) -> str:
    coefficient = sympy.simplify(coefficient)
    constant = sympy.simplify(constant)
    if coefficient == 0:
        return _format_expr(constant)
    return (
        f"{_format_linear_term(coefficient, variable)}{_format_signed_term(constant)}"
    )


def _format_signed_term(value: sympy.Expr) -> str:
    value = sympy.simplify(value)
    if value == 0:
        return ""
    if value > 0:
        return f" + {_format_expr(value)}"
    return f" - {_format_expr(abs(value))}"


def _inverse_constant_operation_text(constant: sympy.Expr) -> str:
    constant = sympy.simplify(constant)
    if constant == 0:
        return "simplify both sides"
    if constant > 0:
        return f"subtract {_format_expr(constant)}"
    return f"add {_format_expr(abs(constant))}"


def _collect_terms_operation_text(
    variable: str,
    rhs_coefficient: sympy.Expr,
    lhs_constant: sympy.Expr,
) -> str:
    moves: list[str] = []
    rhs_coefficient = sympy.simplify(rhs_coefficient)
    lhs_constant = sympy.simplify(lhs_constant)
    if rhs_coefficient != 0:
        if rhs_coefficient > 0:
            moves.append(
                f"subtract {_format_linear_term(rhs_coefficient, variable)} from both sides"
            )
        else:
            moves.append(
                f"add {_format_linear_term(abs(rhs_coefficient), variable)} to both sides"
            )
    if lhs_constant != 0:
        if lhs_constant > 0:
            moves.append(f"subtract {_format_expr(lhs_constant)} from both sides")
        else:
            moves.append(f"add {_format_expr(abs(lhs_constant))} to both sides")
    return ", then ".join(moves) if moves else "collect variable terms and constants"


def _linear_first_focus_text(equation: LinearEquation) -> str:
    if equation.rhs_coefficient != 0:
        return f"Move {_format_linear_term(equation.rhs_coefficient, equation.variable)} so the variable terms are together."
    return f"Remove the constant {_format_signed_term(equation.constant).strip()} from both sides."


def _linear_substitution_check_equation(equation: LinearEquation) -> str:
    solution = equation.solution
    lhs_value = sympy.simplify(equation.lhs.subs(equation.symbol, solution))
    rhs_value = sympy.simplify(equation.rhs_expr.subs(equation.symbol, solution))
    lhs_display = _format_linear_expression(
        equation.lhs_coefficient,
        equation.lhs_constant,
        f"({_format_expr(solution)})",
    )
    rhs_display = _format_linear_expression(
        equation.rhs_coefficient,
        equation.rhs_constant,
        f"({_format_expr(solution)})",
    )
    return (
        f"{lhs_display} = {rhs_display} "
        f"→ {_format_expr(lhs_value)} = {_format_expr(rhs_value)}"
    )


def _sympify_math_expr(text: str) -> sympy.Expr:
    return sympy.nsimplify(sympy.sympify(text))


def _normalize_math_text(text: str) -> str:
    normalized = text.strip()
    normalized = normalized.replace("^", "**")
    normalized = normalized.replace("−", "-")
    normalized = re.sub(r"(\d)\s*([a-zA-Z])", r"\1*\2", normalized)
    normalized = re.sub(r"([a-zA-Z])\s*(\d)", r"\1*\2", normalized)
    return normalized


def _extract_equation_text(message: str) -> Optional[str]:
    cleaned = re.sub(
        r"(?i)\b(?:solve|please|calculate|find|what\s+is|i\s+tried|is\s+this\s+right|ដោះស្រាយ|គណនា|រក)\b[: ]*",
        " ",
        message,
    )
    candidates = re.findall(
        r"[-+*/^().\s\da-zA-Z]+=[-+*/^().\s\da-zA-Z]+",
        cleaned,
    )
    if not candidates:
        return None
    return max(
        (candidate.strip().rstrip(".,;:?!") for candidate in candidates),
        key=len,
    )


def _equations_equivalent(left: str, right: str) -> bool:
    try:
        left_eq = parse_linear_equation(left)
        right_eq = parse_linear_equation(right)
        if left_eq and right_eq:
            return (
                sympy.simplify(left_eq.coefficient - right_eq.coefficient) == 0
                and sympy.simplify(left_eq.first_step_rhs - right_eq.first_step_rhs)
                == 0
            )

        left_lhs, left_rhs = _normalize_math_text(left).split("=", 1)
        right_lhs, right_rhs = _normalize_math_text(right).split("=", 1)
        return (
            sympy.simplify(sympy.sympify(left_lhs) - sympy.sympify(right_lhs)) == 0
            and sympy.simplify(sympy.sympify(left_rhs) - sympy.sympify(right_rhs)) == 0
        )
    except Exception:
        return False


def _line_step_is_correct(message: str, line: LineThroughPoints) -> bool:
    normalized = message.strip().lower().replace("−", "-")
    match = re.search(
        r"(?:m|slope)\s*=?\s*([-+]?\d+(?:/\d+)?(?:\.\d+)?)",
        normalized,
    )
    if not match:
        return False
    try:
        return sympy.simplify(sympy.Rational(match.group(1)) - line.slope) == 0
    except Exception:
        return False


def _line_expected_step(current_step_index: int) -> str:
    if current_step_index <= 0:
        return "the vertical change Δy"
    if current_step_index == 1:
        return "the horizontal change Δx"
    if current_step_index == 2:
        return "the slope m"
    return "the y-intercept b"


def _line_retry_task(line: LineThroughPoints, current_step_index: int) -> str:
    if current_step_index <= 0:
        return f"Look only at y-values: what is {_format_expr(line.y2)} - {_format_expr(line.y1)}?"
    if current_step_index == 1:
        return f"Look only at x-values: what is {_format_expr(line.x2)} - {_format_expr(line.x1)}?"
    if current_step_index == 2:
        return (
            f"What is m = {_format_expr(line.delta_y)} / {_format_expr(line.delta_x)}?"
        )
    return f"What is b in {_format_expr(line.y1)} = {_format_expr(line.slope)}({_format_expr(line.x1)}) + b?"


def _state_hint_count(request: VisualTutorTurnRequest) -> int:
    if request.hint_count is not None:
        return request.hint_count
    return request.current_state.hint_count


def _localized_task(policy_uses_khmer: bool, english: str, khmer: str) -> str:
    return khmer if policy_uses_khmer else english


def _build_linear_board(
    equation: LinearEquation,
    *,
    active_step: int,
    reveal_partial: bool = False,
    reveal_final: bool = False,
    feedback: Optional[str] = None,
) -> VisualTutorBoard:
    items = [
        VisualTutorBoardItem(
            label="Problem",
            content=equation.original,
            status="complete" if active_step > 0 else "active",
        )
    ]

    step_one_status = "active"
    if active_step > 0:
        step_one_status = "complete"
    elif not reveal_partial:
        step_one_status = "locked"

    items.append(
        VisualTutorBoardItem(
            label="Step 1",
            content=(
                equation.first_step_equation
                if reveal_partial or active_step > 0 or reveal_final
                else f"{equation.operation_text.capitalize()}."
            ),
            status=step_one_status,
            metadata={"operation": equation.operation_text},
        )
    )

    items.append(
        VisualTutorBoardItem(
            label="Final",
            content=(
                equation.final_equation if reveal_final else "Final answer is locked."
            ),
            status="complete" if reveal_final else "locked",
        )
    )

    metadata = {
        "problem_type": "linear_equation_one_variable",
        "normalized_problem": equation.normalized,
        "coefficient": _format_expr(equation.coefficient),
        "constant": _format_expr(equation.constant),
        "rhs": _format_expr(equation.rhs),
        "current_step_index": active_step,
    }
    if feedback:
        metadata["feedback"] = feedback
        if feedback == "incorrect_step":
            metadata.update(
                _check_work_metadata(
                    equation,
                    student_step="",
                    validation_result="incorrect_relevant_step",
                )
            )
        elif feedback == "final_verified_answer":
            metadata.update(_linear_final_verified_board_metadata(equation))

    return VisualTutorBoard(
        type=VisualTutorBoardType.EQUATION_STEPS,
        title="Linear Equation",
        items=items,
        metadata=metadata,
    )


def _build_line_board(
    line: LineThroughPoints,
    *,
    active_step: int,
    reveal_partial: bool = False,
    reveal_final: bool = False,
    feedback: Optional[str] = None,
) -> VisualTutorBoard:
    items = [
        VisualTutorBoardItem(
            label="Problem",
            content=f"Line through {line.original}",
            status="complete" if active_step > 0 else "active",
        )
    ]

    items.append(
        VisualTutorBoardItem(
            label="Step 1",
            content=(
                line.slope_step
                if reveal_partial or active_step > 0 or reveal_final
                else "Use slope formula: m = (y2 - y1) / (x2 - x1)."
            ),
            status="complete" if active_step > 0 else "active",
            metadata={"operation": "find_slope"},
        )
    )
    items.append(
        VisualTutorBoardItem(
            label="Step 1a",
            content=(
                f"Δy = {_format_expr(line.delta_y)}, Δx = {_format_expr(line.delta_x)}"
                if active_step > 1 or reveal_partial or reveal_final
                else "Find Δy first, then Δx."
            ),
            status="complete" if active_step > 1 else "active",
            metadata={"operation": "compare_changes"},
        )
    )
    items.append(
        VisualTutorBoardItem(
            label="Step 1b",
            content=(
                f"m = {_format_expr(line.slope)}"
                if active_step > 2 or reveal_partial or reveal_final
                else "Use m = Δy / Δx."
            ),
            status="complete" if active_step > 2 else "locked",
            metadata={"operation": "find_slope_value"},
        )
    )
    items.append(
        VisualTutorBoardItem(
            label="Step 2",
            content=(
                f"{_format_expr(line.y1)} = {_format_expr(line.slope)}({_format_expr(line.x1)}) + b"
                if active_step > 3 or reveal_final
                else "After the slope, use a point in y = mx + b."
            ),
            status="active" if active_step >= 3 else "locked",
            metadata={"operation": "find_intercept"},
        )
    )
    items.append(
        VisualTutorBoardItem(
            label="Final",
            content=line.final_equation if reveal_final else "Final answer is locked.",
            status="complete" if reveal_final else "locked",
        )
    )

    metadata = {
        "problem_type": "line_through_points",
        "normalized_problem": line.normalized,
        "slope": _format_expr(line.slope),
        "intercept": _format_expr(line.intercept),
        "current_step_index": active_step,
    }
    if feedback:
        metadata["feedback"] = feedback

    return VisualTutorBoard(
        type=VisualTutorBoardType.EQUATION_STEPS,
        title="Line Equation",
        items=items,
        metadata=metadata,
    )


def _metadata(
    normalized_problem: Optional[str],
    request: VisualTutorTurnRequest,
    policy: VisualTutorPolicyDecision,
) -> dict:
    metadata = {
        "hint_count": _state_hint_count(request),
        "wrong_attempts": request.current_state.wrong_attempts,
        "policy": policy.metadata,
        "policy_reason": policy.reason,
    }
    if normalized_problem:
        metadata["normalized_problem"] = normalized_problem
    return metadata


def _linear_final_verified_metadata(
    equation: LinearEquation,
    request: VisualTutorTurnRequest,
    policy: VisualTutorPolicyDecision,
) -> dict[str, Any]:
    return {
        **_metadata(equation.normalized, request, policy),
        **_linear_final_verified_board_metadata(equation),
        "verified_by": "sympy",
        "sympy_verified": True,
        "final_answer": equation.final_equation,
        "next_practice": {
            "action": "next_practice",
            "topic": "Linear Equations",
            "problem_type": "linear_equation_one_variable",
        },
    }


def _linear_final_verified_board_metadata(equation: LinearEquation) -> dict[str, Any]:
    solution_check = _linear_substitution_check_equation(equation)
    return {
        "screen_state": "final_verified_answer",
        "board_type": "final_verified_answer",
        "problem_title": "Linear Equation",
        "problem": equation.original,
        "verified_by": "sympy",
        "verified_label": "VERIFIED (បានផ្ទៀងផ្ទាត់)",
        "final_answer": equation.final_equation,
        "worked_solution": [
            equation.original,
            equation.first_step_equation,
            equation.final_equation,
            solution_check,
        ],
        "summary": {
            "key_formula": "Keep both sides of the equation balanced.",
            "applied_rule": f"Use inverse operations: {equation.operation_text}, then divide by the coefficient.",
        },
        "key_formula": "Keep both sides of the equation balanced.",
        "applied_rule": f"Use inverse operations: {equation.operation_text}, then divide by the coefficient.",
        "mastery_message": "Great job! You’ve mastered this problem.",
        "next_practice": {
            "label": "Next Practice Problem",
            "topic": "Linear Equations",
            "problem_type": "linear_equation_one_variable",
        },
    }


def _check_work_metadata(
    equation: LinearEquation,
    *,
    student_step: str,
    validation_result: str,
    misconception_type: Optional[str] = None,
) -> dict[str, Any]:
    mistake_message = (
        "Check your sign here!"
        if misconception_type == "sign_error"
        else "Check your step here!"
    )
    return {
        "board_type": "check_my_work",
        "screen_state": "check_my_work",
        "problem": equation.original,
        "student_step": student_step or "Your step",
        "faded_step": equation.final_equation,
        "validation_result": validation_result,
        "mistake_location": "student_step",
        "mistake_message": mistake_message,
        "corrected_hint": f"Use the inverse operation carefully: {equation.operation_text}.",
    }


def _input_understanding_from_policy(
    policy: VisualTutorPolicyDecision,
) -> Optional[VisualTutorInputUnderstandingResult]:
    payload = policy.metadata.get("input_understanding")
    if not isinstance(payload, dict):
        return None
    try:
        return VisualTutorInputUnderstandingResult.model_validate(payload)
    except Exception:
        return None
