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
    if not msg or "=" not in msg:
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
