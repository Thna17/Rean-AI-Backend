"""Deterministic SymPy-verified algebra worked solutions for visual tutor.

Supported topics:
1. Linear Equations in one variable (e.g., 3x + 7 = 22)
2. Quadratic Equations in one variable (e.g., x^2 - 5x + 6 = 0)
3. Systems of Linear Equations in two variables (e.g., 2x + 3y = 12, x - y = 1)

Verification invariant:
All solutions MUST be verified by substituting candidate values back into the
original equations and asserting that sympy.simplify(lhs - rhs) == 0.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional, Tuple

import sympy
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

from api.models.visual_tutor import VisualTutorTurnRequest

logger = logging.getLogger(__name__)

_TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)

_STOP_WORDS = {
    "solve", "the", "quadratic", "linear", "system", "of", "equations", "equation",
    "what", "is", "if", "find", "calculate", "please", "for", "with", "and", "in",
    "value", "roots", "root", "solution", "solutions", "simultaneous", "both",
}


def _clean_single_equation_text(text: str) -> str:
    """Strip prompt words and normalize symbols from an equation string."""
    text = text.replace("−", "-").replace("—", "-").replace("^", "**")
    if "=" not in text:
        return ""
    lhs, rhs = text.split("=", 1)
    lhs_words = lhs.strip().split()
    while lhs_words and lhs_words[0].lower().rstrip(":,") in _STOP_WORDS:
        lhs_words.pop(0)
    lhs_clean = " ".join(lhs_words).strip(": ")

    rhs_words = rhs.strip().split()
    while rhs_words and rhs_words[-1].lower().rstrip(".,;:?!") in _STOP_WORDS:
        rhs_words.pop()
    rhs_clean = " ".join(rhs_words).rstrip(".,;:?! ")

    # Remove Khmer prose
    lhs_clean = re.sub(r"[\u1780-\u17ff]+", "", lhs_clean).strip()
    rhs_clean = re.sub(r"[\u1780-\u17ff]+", "", rhs_clean).strip()

    if lhs_clean and rhs_clean:
        return f"{lhs_clean} = {rhs_clean}"
    return ""


def extract_algebra_equations(message: str) -> list[tuple[str, sympy.Expr, sympy.Expr]]:
    """Extract and parse equations from a message string."""
    cleaned = message.replace("−", "-").replace("—", "-")
    # Split clauses by newline, semicolon, comma, 'and', 'with', 'និង'
    chunks = re.split(r"[\n;,]|\b(?:and|with)\b|(?:\bនិង\b)", cleaned, flags=re.IGNORECASE)
    results: list[tuple[str, sympy.Expr, sympy.Expr]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if "=" in chunk:
            eq_text = _clean_single_equation_text(chunk)
            if not eq_text or "=" not in eq_text:
                continue
            lhs_raw, rhs_raw = eq_text.split("=", 1)
            try:
                lhs = parse_expr(lhs_raw.strip(), transformations=_TRANSFORMS)
                rhs = parse_expr(rhs_raw.strip(), transformations=_TRANSFORMS)
                # Ensure no forbidden operations
                if lhs.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo) or rhs.has(sympy.zoo, sympy.nan, sympy.oo, -sympy.oo):
                    continue
                results.append((eq_text, lhs, rhs))
            except Exception:
                continue
    return results


def _states_a_given(lhs: sympy.Expr, rhs: sympy.Expr) -> bool:
    """True when an equation merely names a value, as in `a = 5`.

    Word problems state their data this way ("a = 5, b = 7, and angle C = 60
    degrees"). Such an equation is already solved, so treating it as the problem
    answers with the question's own givens instead of the unknown it asked for.
    """
    for named, valued in ((lhs, rhs), (rhs, lhs)):
        if isinstance(named, sympy.Symbol) and not valued.free_symbols:
            return True
    return False


def try_solve_algebra_problem(
    request: VisualTutorTurnRequest,
    *,
    is_khmer: bool = False,
) -> Optional[Any]:
    """Attempt deterministic SymPy solution and substitution check for algebra problems."""
    from api.services.visual_tutor.dynamic_worked_solution import (
        GenericSolutionStep,
        GenericWorkedSolution,
    )

    msg = (request.message or request.current_state.problem_text or "").strip()
    if not msg:
        return None

    # Grade 12 Complex Numbers, Derivatives, Integrals, and ODEs (SymPy verified)
    for specialized_solver in (
        _try_solve_complex_number_problem,
        _try_solve_derivative_problem,
        _try_solve_integral_problem,
        _try_solve_ode_problem,
    ):
        try:
            sol = specialized_solver(
                msg,
                is_khmer=is_khmer,
                step_cls=GenericSolutionStep,
                solution_cls=GenericWorkedSolution,
            )
            if sol is not None:
                return sol
        except Exception as exc:
            logger.debug("Specialized SymPy solver %s skipped: %s", specialized_solver.__name__, exc)

    if "=" not in msg:
        return None

    # Don't hijack limit, calculus, kinematics, or stoichiometry problems
    lowered = msg.lower()
    if any(k in lowered for k in ("lim", "limit", "d/dx", "m/s", "mol", "gram", "->", "→", "acceleration")):
        return None

    parsed_equations = extract_algebra_equations(msg)
    if not parsed_equations:
        return None

    # Equations that only name values are the problem's givens, not the problem.
    if all(_states_a_given(lhs, rhs) for _, lhs, rhs in parsed_equations):
        return None

    try:
        if len(parsed_equations) == 1:
            eq_text, lhs, rhs = parsed_equations[0]
            diff = sympy.simplify(lhs - rhs)
            syms = sorted(diff.free_symbols, key=lambda s: s.name)
            if len(syms) != 1:
                return None
            var = syms[0]

            try:
                poly = sympy.Poly(diff, var)
            except Exception:
                return None

            if poly.degree() == 1:
                return _solve_linear_equation(
                    problem_text=msg,
                    eq_text=eq_text,
                    lhs=lhs,
                    rhs=rhs,
                    var=var,
                    poly=poly,
                    is_khmer=is_khmer,
                    step_cls=GenericSolutionStep,
                    solution_cls=GenericWorkedSolution,
                )
            elif poly.degree() == 2:
                return _solve_quadratic_equation(
                    problem_text=msg,
                    eq_text=eq_text,
                    lhs=lhs,
                    rhs=rhs,
                    var=var,
                    poly=poly,
                    is_khmer=is_khmer,
                    step_cls=GenericSolutionStep,
                    solution_cls=GenericWorkedSolution,
                )

        elif len(parsed_equations) == 2:
            return _solve_linear_system(
                problem_text=msg,
                parsed_equations=parsed_equations,
                is_khmer=is_khmer,
                step_cls=GenericSolutionStep,
                solution_cls=GenericWorkedSolution,
            )
    except Exception as exc:
        logger.warning("Deterministic algebra solver encountered error: %s", exc)
        return None

    return None


def _solve_linear_equation(
    *,
    problem_text: str,
    eq_text: str,
    lhs: sympy.Expr,
    rhs: sympy.Expr,
    var: sympy.Symbol,
    poly: sympy.Poly,
    is_khmer: bool,
    step_cls: Any,
    solution_cls: Any,
) -> Optional[Any]:
    """Solve linear equation ax + b = c and verify by substitution."""
    coeff = poly.coeff_monomial(var)
    const = poly.coeff_monomial(1)
    if coeff == 0:
        return None

    solutions = sympy.solve(sympy.Eq(lhs, rhs), var)
    if not solutions:
        return None
    sol = solutions[0]

    # Verification: substitute solution back into original equation
    lhs_val = sympy.simplify(lhs.subs(var, sol))
    rhs_val = sympy.simplify(rhs.subs(var, sol))
    diff_val = sympy.simplify(lhs_val - rhs_val)
    if diff_val != 0:
        return None

    var_name = var.name
    sol_latex = sympy.latex(sol)
    sol_str = str(sol)

    # Step 1: Identify Equation
    step1_heading = "ជំហានទី ១ · កំណត់សមីការ" if is_khmer else "Step 1 · Identify the equation"
    step1_exp = (
        f"យើងមានសមីការដឺក្រេទីមួយមានមួយអថេរ៖ ${sympy.latex(lhs)} = {sympy.latex(rhs)}$។ គោលដៅគឺរកតម្លៃ ${var_name}$។"
        if is_khmer
        else f"We have a linear equation in one variable: ${sympy.latex(lhs)} = {sympy.latex(rhs)}$. Our goal is to isolate ${var_name}$."
    )
    step1_latex = f"{sympy.latex(lhs)} = {sympy.latex(rhs)}"

    # Step 2: Isolate Variable Term
    step2_heading = "ជំហានទី ២ · ញែកតួអថេរ" if is_khmer else "Step 2 · Isolate the variable term"
    step2_exp = (
        "ផ្លាស់ប្តូរតួលេខថេរទៅម្ខាងទៀតដើម្បីរក្សាតុល្យភាពសមីការ៖"
        if is_khmer
        else "Move the constant term to the other side to keep the equation balanced:"
    )
    isolated_rhs = -const
    step2_latex = f"{sympy.latex(coeff * var)} = {sympy.latex(isolated_rhs)}"

    # Step 3: Solve for variable
    step3_heading = "ជំហានទី ៣ · រកតម្លៃអថេរ" if is_khmer else f"Step 3 · Solve for {var_name}"
    step3_exp = (
        f"ចែកអង្គសងខាងនឹង {sympy.latex(coeff)} ដើម្បីរកតម្លៃ {var_name}៖"
        if is_khmer
        else f"Divide both sides by {sympy.latex(coeff)} to isolate {var_name}:"
    )
    step3_latex = f"{var_name} = {sol_latex}"

    # Step 4: Verification by substitution
    step4_heading = "ជំហានទី ៤ · ផ្ទៀងផ្ទាត់ដោយជំនួស (SymPy)" if is_khmer else "Step 4 · Verify by substitution (SymPy)"
    step4_exp = (
        f"ជំនួស {var_name} = {sol_latex} ត្រឡប់ចូលក្នុងសមីការដើមដើម្បីផ្ទៀងផ្ទាត់សមភាព៖"
        if is_khmer
        else f"Substitute {var_name} = {sol_latex} back into the original equation to verify equality:"
    )
    step4_latex = f"{sympy.latex(lhs_val)} = {sympy.latex(rhs_val)} \\quad \\checkmark"

    steps = [
        step_cls(key="step1", heading=step1_heading, explanation=step1_exp, latex=step1_latex),
        step_cls(key="step2", heading=step2_heading, explanation=step2_exp, latex=step2_latex),
        step_cls(key="step3", heading=step3_heading, explanation=step3_exp, latex=step3_latex),
        step_cls(key="step4", heading=step4_heading, explanation=step4_exp, latex=step4_latex),
    ]

    answer_text = f"{var_name} = {sol_str}"
    answer_latex = f"{var_name} = {sol_latex}"

    return solution_cls(
        problem_text=problem_text,
        steps=steps,
        answer_text=answer_text,
        answer_latex=answer_latex,
        is_verified=True,
        curriculum_topic="Linear Equations",
        curriculum_sources=["sympy_algebra_linear_v1"],
    )


def _solve_quadratic_equation(
    *,
    problem_text: str,
    eq_text: str,
    lhs: sympy.Expr,
    rhs: sympy.Expr,
    var: sympy.Symbol,
    poly: sympy.Poly,
    is_khmer: bool,
    step_cls: Any,
    solution_cls: Any,
) -> Optional[Any]:
    """Solve quadratic equation ax^2 + bx + c = 0 and verify all roots by substitution."""
    a = poly.coeff_monomial(var**2)
    b = poly.coeff_monomial(var)
    c = poly.coeff_monomial(1)
    if a == 0:
        return None

    roots = sympy.solve(sympy.Eq(lhs, rhs), var)
    if not roots:
        return None

    # Verification: substitute each root back into (lhs - rhs)
    diff_expr = lhs - rhs
    for r in roots:
        sub_val = sympy.simplify(diff_expr.subs(var, r))
        if sub_val != 0:
            return None

    var_name = var.name
    delta = b**2 - 4 * a * c

    # Step 1: Standard Form
    step1_heading = "ជំហានទី ១ · សរសេរជាទម្រង់ស្តង់ដារ" if is_khmer else "Step 1 · Identify quadratic form"
    step1_exp = (
        f"កំណត់សមីការដឺក្រេទីពីរតាមទម្រង់ស្តង់ដារ $ax^2 + bx + c = 0$ ដែល $a = {sympy.latex(a)}, b = {sympy.latex(b)}, c = {sympy.latex(c)}$៖"
        if is_khmer
        else f"Identify the quadratic equation in standard form $ax^2 + bx + c = 0$ with $a = {sympy.latex(a)}, b = {sympy.latex(b)}, c = {sympy.latex(c)}$:"
    )
    step1_latex = f"{sympy.latex(poly.as_expr())} = 0"

    # Step 2: Factoring or Discriminant
    factored = sympy.factor(poly.as_expr())
    is_factored = (factored != poly.as_expr())
    if is_factored:
        step2_heading = "ជំហានទី ២ · ដាក់ជាផលគុណកត្តា" if is_khmer else "Step 2 · Factor the quadratic expression"
        step2_exp = (
            "ដាក់កន្សោមដឺក្រេទីពីរជាផលគុណកត្តា៖"
            if is_khmer
            else "Factor the quadratic expression:"
        )
        step2_latex = f"{sympy.latex(factored)} = 0"
    else:
        step2_heading = "ជំហានទី ២ · គណនាឌីសគ្រីមីណង់" if is_khmer else "Step 2 · Calculate the discriminant"
        step2_exp = (
            f"គណនា $\\Delta = b^2 - 4ac = ({sympy.latex(b)})^2 - 4({sympy.latex(a)})({sympy.latex(c)}) = {sympy.latex(delta)}$៖"
            if is_khmer
            else f"Calculate the discriminant $\\Delta = b^2 - 4ac = ({sympy.latex(b)})^2 - 4({sympy.latex(a)})({sympy.latex(c)}) = {sympy.latex(delta)}$:"
        )
        step2_latex = f"\\Delta = {sympy.latex(delta)}"

    # Step 3: Solve for roots
    step3_heading = "ជំហានទី ៣ · រកឫសនៃសមីការ" if is_khmer else "Step 3 · Solve for the roots"
    step3_exp = (
        "កំណត់ឫសទាំងពីរនៃសមីការ៖"
        if is_khmer
        else "Determine the solutions for the variable:"
    )
    if len(roots) == 1:
        step3_latex = f"{var_name} = {sympy.latex(roots[0])}"
    else:
        step3_latex = ", \\quad ".join(f"{var_name}_{{{i+1}}} = {sympy.latex(r)}" for i, r in enumerate(roots))

    # Step 4: Verification by substitution
    step4_heading = "ជំហានទី ៤ · ផ្ទៀងផ្ទាត់ដោយជំនួស (SymPy)" if is_khmer else "Step 4 · Verify by substitution (SymPy)"
    step4_exp = (
        "ជំនួសឫសនីមួយៗចូលសមីការដើមដើម្បីផ្ទៀងផ្ទាត់តុល្យភាព៖"
        if is_khmer
        else "Substitute each solution back into the original equation to verify equality:"
    )
    step4_items = []
    for r in roots:
        term2 = b * r
        term2_str = f"+ {sympy.latex(term2)}" if term2 >= 0 else f"- {sympy.latex(-term2)}"
        c_str = f"+ {sympy.latex(c)}" if c >= 0 else f"- {sympy.latex(-c)}"
        step4_items.append(f"({sympy.latex(r)})^2 {term2_str} {c_str} = 0 \\quad \\checkmark")
    step4_latex = ", \\quad ".join(step4_items)

    steps = [
        step_cls(key="step1", heading=step1_heading, explanation=step1_exp, latex=step1_latex),
        step_cls(key="step2", heading=step2_heading, explanation=step2_exp, latex=step2_latex),
        step_cls(key="step3", heading=step3_heading, explanation=step3_exp, latex=step3_latex),
        step_cls(key="step4", heading=step4_heading, explanation=step4_exp, latex=step4_latex),
    ]

    answer_text = ", ".join(f"{var_name} = {r}" for r in roots)
    answer_latex = ", \\quad ".join(f"{var_name} = {sympy.latex(r)}" for r in roots)

    return solution_cls(
        problem_text=problem_text,
        steps=steps,
        answer_text=answer_text,
        answer_latex=answer_latex,
        is_verified=True,
        curriculum_topic="Quadratic Equations",
        curriculum_sources=["sympy_algebra_quadratic_v1"],
    )


def _solve_linear_system(
    *,
    problem_text: str,
    parsed_equations: list[tuple[str, sympy.Expr, sympy.Expr]],
    is_khmer: bool,
    step_cls: Any,
    solution_cls: Any,
) -> Optional[Any]:
    """Solve system of 2 linear equations in 2 variables and verify by substitution."""
    eq1_str, lhs1, rhs1 = parsed_equations[0]
    eq2_str, lhs2, rhs2 = parsed_equations[1]

    diff1 = sympy.simplify(lhs1 - rhs1)
    diff2 = sympy.simplify(lhs2 - rhs2)
    syms = sorted((diff1.free_symbols | diff2.free_symbols), key=lambda s: s.name)
    if len(syms) != 2:
        return None

    var1, var2 = syms[0], syms[1]

    # Verify both equations are linear in both variables
    poly1_1 = sympy.Poly(diff1, var1)
    poly1_2 = sympy.Poly(diff1, var2)
    poly2_1 = sympy.Poly(diff2, var1)
    poly2_2 = sympy.Poly(diff2, var2)
    if not (poly1_1.degree() <= 1 and poly1_2.degree() <= 1 and poly2_1.degree() <= 1 and poly2_2.degree() <= 1):
        return None

    sol_dict = sympy.solve([sympy.Eq(lhs1, rhs1), sympy.Eq(lhs2, rhs2)], (var1, var2))
    if not isinstance(sol_dict, dict) or var1 not in sol_dict or var2 not in sol_dict:
        return None

    # Verification: substitute solution back into both original equations
    lhs1_val = sympy.simplify(lhs1.subs(sol_dict))
    rhs1_val = sympy.simplify(rhs1.subs(sol_dict))
    lhs2_val = sympy.simplify(lhs2.subs(sol_dict))
    rhs2_val = sympy.simplify(rhs2.subs(sol_dict))

    if sympy.simplify(lhs1_val - rhs1_val) != 0 or sympy.simplify(lhs2_val - rhs2_val) != 0:
        return None

    v1_name, v2_name = var1.name, var2.name
    v1_val, v2_val = sol_dict[var1], sol_dict[var2]

    # Isolate var1 from eq2 if possible, else from eq1
    iso_sol = sympy.solve(sympy.Eq(lhs2, rhs2), var1)
    if iso_sol:
        iso_expr = iso_sol[0]
        iso_from = "2"
        sub_into = "1"
        sub_eq_lhs = lhs1.subs(var1, iso_expr)
        sub_eq_rhs = rhs1
    else:
        iso_expr = sympy.solve(sympy.Eq(lhs1, rhs1), var1)[0]
        iso_from = "1"
        sub_into = "2"
        sub_eq_lhs = lhs2.subs(var1, iso_expr)
        sub_eq_rhs = rhs2

    # Step 1: Identify System
    step1_heading = "ជំហានទី ១ · កំណត់ប្រព័ន្ធសមីការ" if is_khmer else "Step 1 · Identify the system of equations"
    step1_exp = (
        "យើងមានប្រព័ន្ធសមីការលីនេអ៊ែរមានពីរអថេរ (1) និង (2)៖"
        if is_khmer
        else "We have a system of two linear equations in two variables:"
    )
    step1_latex = (
        f"\\begin{{cases}} {sympy.latex(lhs1)} = {sympy.latex(rhs1)} & (1) \\\\ "
        f"{sympy.latex(lhs2)} = {sympy.latex(rhs2)} & (2) \\end{{cases}}"
    )

    # Step 2: Express variable (Substitution method)
    step2_heading = "ជំហានទី ២ · ញែកអថេរមួយ (វិធីជំនួស)" if is_khmer else "Step 2 · Express one variable (Substitution method)"
    step2_exp = (
        f"តាមសមីការ ({iso_from}) យើងទាញបាន {v1_name} ជាកន្សោមនៃ {v2_name}៖"
        if is_khmer
        else f"From equation ({iso_from}), express {v1_name} in terms of {v2_name}:"
    )
    step2_latex = f"{v1_name} = {sympy.latex(iso_expr)} \\quad (3)"

    # Step 3: Substitute and solve
    step3_heading = "ជំហានទី ៣ · ជំនួស និងគណនារកអថេរ" if is_khmer else "Step 3 · Substitute and solve for both variables"
    step3_exp = (
        f"ជំនួស (3) ចូលក្នុងសមីការ ({sub_into}) ដើម្បីរក {v2_name} រួចទាញរក {v1_name}៖"
        if is_khmer
        else f"Substitute (3) into equation ({sub_into}) to solve for {v2_name}, then find {v1_name}:"
    )
    step3_latex = (
        f"{sympy.latex(sub_eq_lhs)} = {sympy.latex(sub_eq_rhs)} "
        f"\\implies {v2_name} = {sympy.latex(v2_val)}, \\quad {v1_name} = {sympy.latex(v1_val)}"
    )

    # Step 4: Verification by substitution
    step4_heading = "ជំហានទី ៤ · ផ្ទៀងផ្ទាត់ដោយជំនួស (SymPy)" if is_khmer else "Step 4 · Verify by substitution (SymPy)"
    step4_exp = (
        f"ជំនួស ({v1_name}, {v2_name}) = ({sympy.latex(v1_val)}, {sympy.latex(v2_val)}) ចូលក្នុងសមីការទាំងពីរដើម្បីផ្ទៀងផ្ទាត់៖"
        if is_khmer
        else f"Substitute ({v1_name}, {v2_name}) = ({sympy.latex(v1_val)}, {sympy.latex(v2_val)}) into both original equations to verify equality:"
    )
    step4_latex = (
        f"{sympy.latex(lhs1_val)} = {sympy.latex(rhs1_val)} \\quad \\checkmark, \\quad "
        f"{sympy.latex(lhs2_val)} = {sympy.latex(rhs2_val)} \\quad \\checkmark"
    )

    steps = [
        step_cls(key="step1", heading=step1_heading, explanation=step1_exp, latex=step1_latex),
        step_cls(key="step2", heading=step2_heading, explanation=step2_exp, latex=step2_latex),
        step_cls(key="step3", heading=step3_heading, explanation=step3_exp, latex=step3_latex),
        step_cls(key="step4", heading=step4_heading, explanation=step4_exp, latex=step4_latex),
    ]

    answer_text = f"{v1_name} = {v1_val}, {v2_name} = {v2_val}"
    answer_latex = f"{v1_name} = {sympy.latex(v1_val)}, \\quad {v2_name} = {sympy.latex(v2_val)}"

    return solution_cls(
        problem_text=problem_text,
        steps=steps,
        answer_text=answer_text,
        answer_latex=answer_latex,
        is_verified=True,
        curriculum_topic="Systems of Linear Equations",
        curriculum_sources=["sympy_algebra_systems_v1"],
    )


def verify_algebra_solution_by_substitution(
    problem_text: str,
    candidate_answer_text: str,
    candidate_answer_latex: str = "",
) -> Tuple[bool, Optional[str]]:
    """Verify an arbitrary candidate solution by substituting back into problem equations."""
    eqs = extract_algebra_equations(problem_text)
    if not eqs:
        return False, None

    combined_text = f"{candidate_answer_text} {candidate_answer_latex}".replace("−", "-").replace("—", "-")
    # Extract assignments like x = 5, y = 2 or x_1 = 2, x_2 = 3
    assignments = re.findall(r"([a-zA-Z](?:_\{\d+\})?)\s*=\s*([-+]?\d+(?:/\d+)?)", combined_text)
    if not assignments:
        return False, None

    subs_dict: dict[sympy.Symbol, sympy.Expr] = {}
    for var_str, val_str in assignments:
        clean_var = re.sub(r"_\{\d+\}", "", var_str).strip()
        try:
            var_sym = sympy.Symbol(clean_var)
            val_expr = sympy.Rational(val_str.strip())
            subs_dict[var_sym] = val_expr
        except Exception:
            continue

    if not subs_dict:
        return False, None

    # Check each equation
    for _, lhs, rhs in eqs:
        try:
            lhs_val = sympy.simplify(lhs.subs(subs_dict))
            rhs_val = sympy.simplify(rhs.subs(subs_dict))
            # If any free symbol remains, this solution is incomplete
            if lhs_val.free_symbols or rhs_val.free_symbols:
                return False, None
            if sympy.simplify(lhs_val - rhs_val) != 0:
                return False, None
        except Exception:
            return False, None

    return True, "SymPy verified by substitution"


def _normalize_latex_expr(raw: str) -> str:
    """Convert common LaTeX math constructs into SymPy-parseable expression syntax."""
    expr = raw.strip()
    expr = expr.replace("−", "-").replace("—", "-")
    expr = re.sub(r"\\quad\b|\\qquad\b|\\,", " ", expr)
    expr = re.sub(r"\\left\s*", "", expr)
    expr = re.sub(r"\\right\s*", "", expr)
    while r"\sqrt{" in expr:
        expr = re.sub(r"\\sqrt\{([^{}]+)\}", r" sqrt(\1)", expr)
    while r"\frac{" in expr:
        expr = re.sub(r"\\frac\{([^{}]+)\}\{([^{}]+)\}", r" ((\1)/(\2))", expr)
    expr = expr.replace("{", "(").replace("}", ")")
    expr = expr.replace("^", "**")
    return expr.strip()


def _try_solve_complex_number_problem(
    msg: str,
    *,
    is_khmer: bool,
    step_cls: Any,
    solution_cls: Any,
) -> Optional[Any]:
    """Deterministically solve Grade 12 Complex Numbers problems (|z|, arg(z), De Moivre z^n)."""
    lowered = msg.lower()
    if not ("z" in lowered and ("arg" in lowered or "|z|" in lowered or "modulus" in lowered or "de moivre" in lowered or "i\\sqrt" in lowered or "i*sqrt" in lowered)):
        return None

    m = re.search(
        r"\bz\s*=\s*([^,;]+?)(?=(?:,|;|\b(?:find|calculate|compute|and)\b|\\quad|$))",
        msg,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    z_raw = m.group(1).strip()
    z_norm = _normalize_latex_expr(z_raw)
    # Replace standalone imaginary unit 'i' with 'I'
    z_norm = re.sub(r"(?<![a-zA-Z])i(?![a-zA-Z])", "I", z_norm)
    z_expr = sympy.simplify(
        parse_expr(
            z_norm,
            local_dict={"I": sympy.I, "sqrt": sympy.sqrt, "pi": sympy.pi},
            transformations=_TRANSFORMS,
        )
    )
    a = sympy.simplify(sympy.re(z_expr))
    b = sympy.simplify(sympy.im(z_expr))
    if a.free_symbols or b.free_symbols:
        return None
    if sympy.simplify((a + sympy.I * b) - z_expr) != 0:
        return None

    r = sympy.simplify(sympy.Abs(z_expr))
    theta = sympy.simplify(sympy.arg(z_expr))
    # Verify modulus and trigonometric representation
    if sympy.simplify(r**2 - (a**2 + b**2)) != 0:
        return None
    if sympy.simplify(r * (sympy.cos(theta) + sympy.I * sympy.sin(theta)) - z_expr) != 0:
        return None

    a_latex = sympy.latex(a)
    b_latex = sympy.latex(b)
    r_latex = sympy.latex(r)
    theta_latex = sympy.latex(theta)
    z_latex = sympy.latex(z_expr)

    # Check if a power z^n is requested
    power_match = re.search(r"\bz\s*\^\s*\{?\s*(\d+)\s*\}?", msg)
    power_n = int(power_match.group(1)) if power_match else None

    step1_heading = (
        "ជំហានទី ១ · កំណត់ផ្នែកពិត និងផ្នែកនិម្មិត"
        if is_khmer
        else "Step 1 · Identify real and imaginary parts"
    )
    step1_exp = (
        f"ចំពោះចំនួនកុំផ្លិចទម្រង់ពីជគណិត $z = a + bi$ យើងទាញបានផ្នែកពិត $a = {a_latex}$ និងផ្នែកនិម្មិត $b = {b_latex}$៖"
        if is_khmer
        else f"For the complex number $z = a + bi$, identify the real part $a = {a_latex}$ and imaginary part $b = {b_latex}$:"
    )
    step1_latex = f"z = {z_latex} \\implies a = {a_latex}, \\quad b = {b_latex}"

    step2_heading = (
        "ជំហានទី ២ · គណនាម៉ូឌុល និងអាកុយម៉ង់"
        if is_khmer
        else "Step 2 · Compute modulus and argument"
    )
    step2_exp = (
        f"គណនាម៉ូឌុល $r = |z| = \\sqrt{{a^2 + b^2}} = {r_latex}$ និងអាកុយម៉ង់ $\\theta = \\arg(z) = {theta_latex}$៖"
        if is_khmer
        else f"Compute the modulus $r = |z| = \\sqrt{{a^2 + b^2}} = {r_latex}$ and argument $\\theta = \\arg(z) = {theta_latex}$:"
    )
    cos_t = sympy.latex(sympy.simplify(a / r))
    sin_t = sympy.latex(sympy.simplify(b / r))
    step2_latex = (
        f"|z| = \\sqrt{{({a_latex})^2 + ({b_latex})^2}} = {r_latex}, \\quad "
        f"\\cos\\theta = {cos_t}, \\; \\sin\\theta = {sin_t} \\implies \\theta = {theta_latex}"
    )

    steps = [
        step_cls(key="step1", heading=step1_heading, explanation=step1_exp, latex=step1_latex),
        step_cls(key="step2", heading=step2_heading, explanation=step2_exp, latex=step2_latex),
    ]

    if power_n is not None:
        z_n_de_moivre = sympy.simplify(
            r**power_n * (sympy.cos(power_n * theta) + sympy.I * sympy.sin(power_n * theta))
        )
        z_n_direct = sympy.expand(z_expr**power_n)
        if sympy.simplify(z_n_de_moivre - z_n_direct) != 0:
            return None
        z_n_latex = sympy.latex(z_n_de_moivre)
        n_theta_latex = sympy.latex(sympy.simplify(power_n * theta))

        step3_heading = (
            f"ជំហានទី ៣ · អនុវត្តរូបមន្តដឺម័រ (De Moivre) សម្រាប់ z^{power_n}"
            if is_khmer
            else f"Step 3 · Apply De Moivre's Theorem for z^{power_n}"
        )
        step3_exp = (
            f"សរសេរទម្រង់ត្រីកោណមាត្រ $z = {r_latex}(\\cos({theta_latex}) + i\\sin({theta_latex}))$ រួចអនុវត្ត $z^n = r^n(\\cos(n\\theta) + i\\sin(n\\theta))$៖"
            if is_khmer
            else f"Write the trigonometric form $z = {r_latex}\\left(\\cos({theta_latex}) + i\\sin({theta_latex})\\right)$ and apply $z^n = r^n(\\cos(n\\theta) + i\\sin(n\\theta))$:"
        )
        step3_latex = (
            f"z^{{{power_n}}} = {r_latex}^{{{power_n}}}\\left(\\cos({n_theta_latex}) + i\\sin({n_theta_latex})\\right) = {z_n_latex}"
        )
        steps.append(
            step_cls(key="step3", heading=step3_heading, explanation=step3_exp, latex=step3_latex)
        )
        answer_text = f"|z| = {r}, arg(z) = {theta}, z^{power_n} = {z_n_de_moivre}"
        answer_latex = f"|z| = {r_latex}, \\quad \\arg(z) = {theta_latex}, \\quad z^{{{power_n}}} = {z_n_latex}"
    else:
        trig_latex = f"z = {r_latex}\\left(\\cos\\left({theta_latex}\\right) + i\\sin\\left({theta_latex}\\right)\\right)"
        step3_heading = (
            "ជំហានទី ៣ · ទម្រង់ត្រីកោណមាត្រ"
            if is_khmer
            else "Step 3 · Trigonometric form"
        )
        step3_exp = (
            "សរសេរចំនួនកុំផ្លិចក្នុងទម្រង់ត្រីកោណមាត្រ $z = r(\\cos\\theta + i\\sin\\theta)$៖"
            if is_khmer
            else "Express the complex number in trigonometric form $z = r(\\cos\\theta + i\\sin\\theta)$:"
        )
        steps.append(
            step_cls(key="step3", heading=step3_heading, explanation=step3_exp, latex=trig_latex)
        )
        answer_text = f"|z| = {r}, arg(z) = {theta}"
        answer_latex = f"|z| = {r_latex}, \\quad \\arg(z) = {theta_latex}"

    return solution_cls(
        problem_text=msg,
        steps=steps,
        answer_text=answer_text,
        answer_latex=answer_latex,
        is_verified=True,
        curriculum_topic="Complex Numbers",
        curriculum_sources=["sympy_complex_v1"],
        generation_path="deterministic_solver",
        verification_method="sympy_complex",
    )


def _try_solve_derivative_problem(
    msg: str,
    *,
    is_khmer: bool,
    step_cls: Any,
    solution_cls: Any,
) -> Optional[Any]:
    """Deterministically solve Grade 12 Derivatives & Tangent Line problems with SymPy."""
    lowered = msg.lower()
    if not ("f(x)" in lowered and ("f'" in lowered or "f^\\prime" in lowered or "derivative" in lowered or "tangent" in lowered)):
        return None

    m = re.search(
        r"f\s*\(\s*x\s*\)\s*=\s*([^,;]+?)(?=(?:,|;|\b(?:find|evaluate|calculate)\b|\\quad|$))",
        msg,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    x = sympy.Symbol("x", real=True)
    expr_str = _normalize_latex_expr(m.group(1))
    f_expr = sympy.simplify(
        parse_expr(expr_str, local_dict={"x": x, "e": sympy.E, "ln": sympy.log}, transformations=_TRANSFORMS)
    )
    if f_expr.free_symbols - {x}:
        return None

    f_prime = sympy.simplify(sympy.diff(f_expr, x))
    # Verify via limit definition at symbolic h -> 0
    h = sympy.Symbol("h", real=True)
    limit_check = sympy.simplify(sympy.limit((f_expr.subs(x, x + h) - f_expr) / h, h, 0) - f_prime)
    if limit_check != 0:
        return None

    # Check if evaluation point x = a or f'(a) is requested
    eval_match = re.search(r"f(?:'|\^\\prime)\s*\(\s*([-+]?\d+)\s*\)", msg) or re.search(
        r"\bx\s*=\s*([-+]?\d+)\b", msg
    )
    x0 = sympy.Integer(int(eval_match.group(1))) if eval_match else None
    wants_tangent = "tangent" in lowered or "បន្ទាត់ប៉ះ" in msg

    f_latex = sympy.latex(f_expr)
    fp_latex = sympy.latex(f_prime)

    step1_heading = (
        "ជំហានទី ១ · គណនាដេរីវេទីមួយ f'(x)"
        if is_khmer
        else "Step 1 · Differentiate f(x) to find f'(x)"
    )
    step1_exp = (
        f"អនុវត្តរូបមន្តដេរីវេលើអនុគមន៍ $f(x) = {f_latex}$៖"
        if is_khmer
        else f"Apply the differentiation rules term-by-term to $f(x) = {f_latex}$:"
    )
    step1_latex = f"f'(x) = \\frac{{d}}{{dx}}\\left({f_latex}\\right) = {fp_latex}"

    steps = [
        step_cls(key="step1", heading=step1_heading, explanation=step1_exp, latex=step1_latex),
    ]

    if x0 is not None:
        fp_x0 = sympy.simplify(f_prime.subs(x, x0))
        f_x0 = sympy.simplify(f_expr.subs(x, x0))
        x0_latex = sympy.latex(x0)
        fp_x0_latex = sympy.latex(fp_x0)
        f_x0_latex = sympy.latex(f_x0)

        step2_heading = (
            f"ជំហានទី ២ · គណនាតម្លៃដេរីវេត្រង់ x = {x0_latex}"
            if is_khmer
            else f"Step 2 · Evaluate the derivative at x = {x0_latex}"
        )
        step2_exp = (
            f"ជំនួស $x = {x0_latex}$ ចូលក្នុង $f'(x)$ ដើម្បីរកមេគុណប្រាប់ទិស៖"
            if is_khmer
            else f"Substitute $x = {x0_latex}$ into $f'(x)$ to find the instantaneous rate of change (slope):"
        )
        step2_latex = f"f'({x0_latex}) = {fp_x0_latex}"
        steps.append(
            step_cls(key="step2", heading=step2_heading, explanation=step2_exp, latex=step2_latex)
        )

        if wants_tangent:
            tangent_rhs = sympy.simplify(f_x0 + fp_x0 * (x - x0))
            tangent_latex = sympy.latex(tangent_rhs)
            step3_heading = (
                f"ជំហានទី ៣ · សមីការបន្ទាត់ប៉ះត្រង់ x = {x0_latex}"
                if is_khmer
                else f"Step 3 · Tangent line equation at x = {x0_latex}"
            )
            step3_exp = (
                f"ដោយ $f({x0_latex}) = {f_x0_latex}$ និង $f'({x0_latex}) = {fp_x0_latex}$ សមីការបន្ទាត់ប៉ះ $y - f(x_0) = f'(x_0)(x - x_0)$ គឺ៖"
                if is_khmer
                else f"Using $f({x0_latex}) = {f_x0_latex}$ and $f'({x0_latex}) = {fp_x0_latex}$, the tangent line $y - f(x_0) = f'(x_0)(x - x_0)$ is:"
            )
            step3_latex = f"y = {tangent_latex}"
            steps.append(
                step_cls(key="step3", heading=step3_heading, explanation=step3_exp, latex=step3_latex)
            )
            answer_text = f"f'(x) = {f_prime}, f'({x0}) = {fp_x0}, tangent line: y = {tangent_rhs}"
            answer_latex = f"f'(x) = {fp_latex}, \\quad f'({x0_latex}) = {fp_x0_latex}, \\quad y = {tangent_latex}"
        else:
            answer_text = f"f'(x) = {f_prime}, f'({x0}) = {fp_x0}"
            answer_latex = f"f'(x) = {fp_latex}, \\quad f'({x0_latex}) = {fp_x0_latex}"
    else:
        answer_text = f"f'(x) = {f_prime}"
        answer_latex = f"f'(x) = {fp_latex}"

    return solution_cls(
        problem_text=msg,
        steps=steps,
        answer_text=answer_text,
        answer_latex=answer_latex,
        is_verified=True,
        curriculum_topic="Derivatives of Functions",
        curriculum_sources=["sympy_calculus_derivatives_v1"],
        generation_path="deterministic_solver",
        verification_method="sympy_calculus",
    )


def _try_solve_integral_problem(
    msg: str,
    *,
    is_khmer: bool,
    step_cls: Any,
    solution_cls: Any,
) -> Optional[Any]:
    """Deterministically solve Grade 12 Definite & Indefinite Integrals with SymPy."""
    if r"\int" not in msg and "∫" not in msg:
        return None

    m = re.search(
        r"(?:\\int|∫)\s*(?:_\s*\{?\s*([-+]?\d+)\s*\}?\s*\^\s*\{?\s*([-+]?\d+)\s*\}?)?\s*(.+?)\s*(?:\\,\s*)?d\s*x\b",
        msg,
        flags=re.IGNORECASE,
    )
    if not m:
        return None

    lower_str, upper_str, integrand_raw = m.group(1), m.group(2), m.group(3)
    x = sympy.Symbol("x", real=True)
    integrand_expr = sympy.simplify(
        parse_expr(
            _normalize_latex_expr(integrand_raw),
            local_dict={"x": x, "e": sympy.E, "sin": sympy.sin, "cos": sympy.cos},
            transformations=_TRANSFORMS,
        )
    )
    if integrand_expr.free_symbols - {x}:
        return None

    antideriv = sympy.simplify(sympy.integrate(integrand_expr, x))
    # Verify Fundamental Theorem of Calculus: d/dx F(x) == f(x)
    if sympy.simplify(sympy.diff(antideriv, x) - integrand_expr) != 0:
        return None

    integrand_latex = sympy.latex(integrand_expr)
    antideriv_latex = sympy.latex(antideriv)

    step1_heading = (
        "ជំហានទី ១ · រកព្រីមីទីវ F(x)"
        if is_khmer
        else "Step 1 · Find the antiderivative F(x)"
    )
    step1_exp = (
        f"គណនាព្រីមីទីវនៃ $f(x) = {integrand_latex}$ និងផ្ទៀងផ្ទាត់ $F'(x) = f(x)$៖"
        if is_khmer
        else f"Find an antiderivative $F(x)$ of $f(x) = {integrand_latex}$ and verify $F'(x) = f(x)$:"
    )
    step1_latex = f"F(x) = \\int \\left({integrand_latex}\\right) dx = {antideriv_latex}"
    steps = [
        step_cls(key="step1", heading=step1_heading, explanation=step1_exp, latex=step1_latex),
    ]

    if lower_str is not None and upper_str is not None:
        a_val = sympy.Integer(int(lower_str))
        b_val = sympy.Integer(int(upper_str))
        f_b = sympy.simplify(antideriv.subs(x, b_val))
        f_a = sympy.simplify(antideriv.subs(x, a_val))
        total = sympy.simplify(f_b - f_a)
        if sympy.simplify(sympy.integrate(integrand_expr, (x, a_val, b_val)) - total) != 0:
            return None

        a_latex = sympy.latex(a_val)
        b_latex = sympy.latex(b_val)
        total_latex = sympy.latex(total)
        step2_heading = (
            "ជំហានទី ២ · អនុវត្តរូបមន្តញូតុន-ឡៃប៊ីនីស (Newton-Leibniz)"
            if is_khmer
            else "Step 2 · Apply the Fundamental Theorem of Calculus"
        )
        step2_exp = (
            f"គណនា $F({b_latex}) - F({a_latex})$៖"
            if is_khmer
            else f"Evaluate $F({b_latex}) - F({a_latex})$ across the limits of integration:"
        )
        step2_latex = (
            f"\\left[{antideriv_latex}\\right]_{{{a_latex}}}^{{{b_latex}}} = "
            f"{sympy.latex(f_b)} - ({sympy.latex(f_a)}) = {total_latex}"
        )
        steps.append(
            step_cls(key="step2", heading=step2_heading, explanation=step2_exp, latex=step2_latex)
        )
        answer_text = f"The definite integral is {total}."
        answer_latex = f"\\int_{{{a_latex}}}^{{{b_latex}}} \\left({integrand_latex}\\right) dx = {total_latex}"
    else:
        answer_text = f"The indefinite integral is {antideriv} + C."
        answer_latex = f"{antideriv_latex} + C"

    return solution_cls(
        problem_text=msg,
        steps=steps,
        answer_text=answer_text,
        answer_latex=answer_latex,
        is_verified=True,
        curriculum_topic="Indefinite and Definite Integrals",
        curriculum_sources=["sympy_calculus_integrals_v1"],
        generation_path="deterministic_solver",
        verification_method="sympy_calculus",
    )


def _try_solve_ode_problem(
    msg: str,
    *,
    is_khmer: bool,
    step_cls: Any,
    solution_cls: Any,
) -> Optional[Any]:
    """Deterministically solve Grade 12 second-order homogeneous ODEs ay'' + by' + cy = 0."""
    if "y''" not in msg and "y^{\\prime\\prime}" not in msg:
        return None

    cleaned = msg.replace("−", "-").replace("—", "-").replace("y^{\\prime\\prime}", "y''").replace("y^{\\prime}", "y'")
    m = re.search(
        r"([+-]?\s*\d*)\s*y''\s*([+-]\s*\d*)\s*y'\s*([+-]\s*\d+)\s*y\s*=\s*0",
        cleaned,
    )
    if not m:
        return None

    def _parse_coeff(s: str) -> int:
        s_clean = s.replace(" ", "")
        if s_clean in ("", "+"):
            return 1
        if s_clean == "-":
            return -1
        return int(s_clean)

    a_val = sympy.Integer(_parse_coeff(m.group(1)))
    b_val = sympy.Integer(_parse_coeff(m.group(2)))
    c_val = sympy.Integer(_parse_coeff(m.group(3)))

    r = sympy.Symbol("r")
    char_poly = a_val * r**2 + b_val * r + c_val
    roots = sympy.solve(sympy.Eq(char_poly, 0), r)
    if len(roots) != 2 or any(not rt.is_real for rt in roots):
        return None

    r1, r2 = roots[0], roots[1]
    x = sympy.Symbol("x", real=True)
    C1, C2 = sympy.Symbol("C_1"), sympy.Symbol("C_2")
    y_expr = C1 * sympy.exp(r1 * x) + C2 * sympy.exp(r2 * x)
    # Verify ODE residual a*y'' + b*y' + c*y == 0
    residual = sympy.simplify(
        a_val * sympy.diff(y_expr, x, 2) + b_val * sympy.diff(y_expr, x) + c_val * y_expr
    )
    if residual != 0:
        return None

    char_latex = f"{sympy.latex(char_poly)} = 0"
    r1_latex, r2_latex = sympy.latex(r1), sympy.latex(r2)
    y_latex = f"y(x) = C_1 e^{{{sympy.latex(r1 * x)}}} + C_2 e^{{{sympy.latex(r2 * x)}}}"

    step1_heading = (
        "ជំហានទី ១ · សមីការសម្គាល់ (Characteristic Equation)"
        if is_khmer
        else "Step 1 · Form the characteristic equation"
    )
    step1_exp = (
        "ជំនួស $y = e^{rx}$ ដើម្បីបង្កើតសមីការសម្គាល់ដឺក្រេទីពីរ៖"
        if is_khmer
        else "Substitute the trial solution $y = e^{rx}$ to obtain the quadratic characteristic equation:"
    )
    step2_heading = (
        "ជំហានទី ២ · រកឫសនៃសមីការសម្គាល់"
        if is_khmer
        else "Step 2 · Solve for the characteristic roots"
    )
    step2_exp = (
        f"ដោះស្រាយសមីការដឺក្រេទីពីរដើម្បីរកឫស $r_1 = {r1_latex}$ និង $r_2 = {r2_latex}$៖"
        if is_khmer
        else f"Factor the quadratic equation to find the distinct real roots $r_1 = {r1_latex}$ and $r_2 = {r2_latex}$:"
    )
    step2_latex = f"r_1 = {r1_latex}, \\quad r_2 = {r2_latex}"

    step3_heading = (
        "ជំហានទី ៣ · ចម្លើយទូទៅនៃសមីការឌីផេរ៉ង់ស្យែល"
        if is_khmer
        else "Step 3 · Write the general solution"
    )
    step3_exp = (
        "ចំពោះឫសពិតពីរផ្សេងគ្នា ចម្លើយទូទៅគឺ $y(x) = C_1 e^{r_1 x} + C_2 e^{r_2 x}$៖"
        if is_khmer
        else "For two distinct real roots, the general solution is $y(x) = C_1 e^{r_1 x} + C_2 e^{r_2 x}$:"
    )

    steps = [
        step_cls(key="step1", heading=step1_heading, explanation=step1_exp, latex=char_latex),
        step_cls(key="step2", heading=step2_heading, explanation=step2_exp, latex=step2_latex),
        step_cls(key="step3", heading=step3_heading, explanation=step3_exp, latex=y_latex),
    ]

    return solution_cls(
        problem_text=msg,
        steps=steps,
        answer_text=f"y(x) = C_1 e^({r1}x) + C_2 e^({r2}x)",
        answer_latex=y_latex,
        is_verified=True,
        curriculum_topic="Differential Equations",
        curriculum_sources=["sympy_calculus_ode_v1"],
        generation_path="deterministic_solver",
        verification_method="sympy_calculus",
    )

