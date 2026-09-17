"""Complete, step-by-step worked solution for Grade 12 Chemistry: Stoichiometry.

Ground truth rules:
1. Chemical equations are balanced programmatically using SymPy and verified.
2. Molar masses come from an explicit atomic weight table in the code, never an LLM.
3. Significant figures are applied consistently to all final answers.
4. Deterministic action IDs (ws-chem-step-..., ws-chem-answer-..., ws-chem-next-...)
   ensure streaming previews and completed turns match identically.
5. Board uses SHOW_REACTION_LAYOUT, SHOW_TABLE, WRITE_TEXT, WRITE_EQUATION,
   and STUDENT_TASK primitives.
"""

from __future__ import annotations

import json
import logging
import math
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
from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan

logger = logging.getLogger(__name__)

TRY_MYSELF_MODE = "try_myself"

# Standard atomic weights from IUPAC periodic table (g/mol)
ATOMIC_WEIGHTS: dict[str, float] = {
    "H": 1.008,
    "He": 4.003,
    "Li": 6.941,
    "Be": 9.012,
    "B": 10.81,
    "C": 12.011,
    "N": 14.007,
    "O": 15.999,
    "F": 18.998,
    "Ne": 20.180,
    "Na": 22.990,
    "Mg": 24.305,
    "Al": 26.982,
    "Si": 28.085,
    "P": 30.974,
    "S": 32.06,
    "Cl": 35.45,
    "K": 39.098,
    "Ca": 40.078,
    "Fe": 55.845,
    "Cu": 63.546,
    "Zn": 65.38,
    "Br": 79.904,
    "Ag": 107.868,
    "I": 126.904,
    "Ba": 137.327,
    "Pb": 207.2,
}

# Standard molar volume of ideal gas at STP (L/mol)
STP_MOLAR_VOLUME = 22.414  # standard 22.4 L/mol in high school


# ------------------------------------------------------------------------------
# Chemical Formula Parsing & Molar Masses
# ------------------------------------------------------------------------------


def parse_formula(formula: str) -> dict[str, int]:
    """Parse a chemical formula into element counts, supporting parentheses."""
    clean = formula.strip().replace(" ", "")
    # Remove state symbols like (s), (l), (g), (aq)
    clean = re.sub(r"\((?:s|l|g|aq)\)$", "", clean)

    def _parse_tokens(tokens: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        idx = 0
        n = len(tokens)
        while idx < n:
            if tokens[idx] == "(":
                # Find matching closing paren
                depth = 1
                close_idx = idx + 1
                while close_idx < n and depth > 0:
                    if tokens[close_idx] == "(":
                        depth += 1
                    elif tokens[close_idx] == ")":
                        depth -= 1
                    close_idx += 1
                inner_str = tokens[idx + 1 : close_idx - 1]
                # Read multiplier after paren
                mult_match = re.match(r"\d+", tokens[close_idx:])
                multiplier = 1
                if mult_match:
                    multiplier = int(mult_match.group(0))
                    idx = close_idx + len(mult_match.group(0))
                else:
                    idx = close_idx
                inner_counts = _parse_tokens(inner_str)
                for elem, cnt in inner_counts.items():
                    counts[elem] = counts.get(elem, 0) + cnt * multiplier
            else:
                elem_match = re.match(r"([A-Z][a-z]?)(\d*)", tokens[idx:])
                if elem_match:
                    elem = elem_match.group(1)
                    mult = int(elem_match.group(2)) if elem_match.group(2) else 1
                    counts[elem] = counts.get(elem, 0) + mult
                    idx += len(elem_match.group(0))
                else:
                    idx += 1
        return counts

    return _parse_tokens(clean)


def calculate_molar_mass(formula: str) -> float:
    """Calculate the molar mass of a compound in g/mol from hardcoded atomic weights."""
    counts = parse_formula(formula)
    total = 0.0
    for elem, count in counts.items():
        weight = ATOMIC_WEIGHTS.get(elem)
        if weight is None:
            raise ValueError(f"Unknown element in formula: {elem}")
        total += weight * count
    return round(total, 3)


# ------------------------------------------------------------------------------
# Programmatic Reaction Balancing
# ------------------------------------------------------------------------------


def balance_reaction(reactants: list[str], products: list[str]) -> list[int]:
    """Programmatically balance a chemical equation using SymPy nullspace.

    Returns positive integer coefficients in order [*reactants, *products].
    """
    clean_reactants = [re.sub(r"^\d+", "", r.strip()) for r in reactants]
    clean_products = [re.sub(r"^\d+", "", p.strip()) for p in products]
    species = clean_reactants + clean_products

    parsed = [parse_formula(s) for s in species]
    all_elements = sorted({elem for p in parsed for elem in p.keys()})

    # Build atom balance matrix: columns are species, rows are elements
    # reactants have positive counts, products have negative counts
    matrix_rows: list[list[int]] = []
    num_reactants = len(clean_reactants)

    for elem in all_elements:
        row: list[int] = []
        for i, comp in enumerate(parsed):
            count = comp.get(elem, 0)
            row.append(count if i < num_reactants else -count)
        matrix_rows.append(row)

    mat = sympy.Matrix(matrix_rows)
    null = mat.nullspace()

    if not null:
        # Already balanced or trivial 1s
        return [1] * len(species)

    vec = null[0]
    # Multiply by common denominator
    denominators = [val.q for val in vec]
    lcm_denom = 1
    for d in denominators:
        lcm_denom = sympy.lcm(lcm_denom, d)

    scaled = [val * lcm_denom for val in vec]
    # Invert sign if negative
    if any(val < 0 for val in scaled):
        scaled = [-val for val in scaled]

    # Divide by gcd
    numerators = [int(val) for val in scaled]
    gcd_num = numerators[0]
    for n in numerators[1:]:
        gcd_num = sympy.gcd(gcd_num, n)

    coeffs = [int(n // gcd_num) for n in numerators]

    # Verify balance
    for elem in all_elements:
        left_count = sum(coeffs[i] * parsed[i].get(elem, 0) for i in range(num_reactants))
        right_count = sum(coeffs[i] * parsed[i].get(elem, 0) for i in range(num_reactants, len(species)))
        if left_count != right_count:
            raise ValueError(f"Balancing verification failed for element {elem}: {left_count} != {right_count}")

    return coeffs


# ------------------------------------------------------------------------------
# Significant Figures
# ------------------------------------------------------------------------------


def count_sig_figs(val_str: str) -> int:
    """Count significant figures in a numeric string."""
    cleaned = val_str.strip().lstrip("+-")
    if "e" in cleaned or "E" in cleaned:
        cleaned = cleaned.split("e")[0].split("E")[0]
    if "." in cleaned:
        digits = cleaned.replace(".", "").lstrip("0")
        return len(digits) if digits else 1
    else:
        # Non-decimal integer
        stripped = cleaned.lstrip("0")
        return len(stripped) if stripped else 1


def format_sig_figs(value: float, sig_figs: int = 3) -> str:
    """Format a float to a given number of significant figures."""
    if value == 0:
        return "0"
    if math.isnan(value) or math.isinf(value):
        return str(value)
    # Determine magnitude
    order = math.floor(math.log10(abs(value)))
    decimals = sig_figs - 1 - order
    if decimals < 0:
        # Round to whole numbers
        rounded = round(value, decimals)
        return f"{rounded:g}"
    else:
        rounded = round(value, decimals)
        formatted = f"{rounded:.{decimals}f}"
        return formatted


def verify_stoichiometry_answer(
    submitted: str, expected_value: float, expected_unit: str, tolerance: float = 0.05
) -> tuple[bool, str]:
    """Verify a student's answer for stoichiometry carrying correct units."""
    cleaned = submitted.strip()
    if not cleaned:
        return False, "Answer is empty. Please provide both a value and a unit (e.g. 34.1 g)."

    match = re.search(r"(?P<val>[-+]?\d+(?:\.\d+)?)\s*(?P<unit>g|grams?|mol|moles?|l|liters?|litres?)\b", cleaned, re.IGNORECASE)
    if not match:
        if re.search(r"[-+]?\d+(?:\.\d+)?", cleaned):
            return False, f"Missing unit: Chemistry quantities require units. Expected '{expected_unit}'."
        return False, f"Could not parse physical quantity and unit. Expected '{expected_unit}'."

    submitted_val = float(match.group("val"))
    raw_unit = match.group("unit").lower()
    norm_unit = "g" if "g" in raw_unit else ("mol" if "mol" in raw_unit else "L")
    norm_expected = expected_unit.lower()

    if norm_unit.lower() != norm_expected:
        return False, f"Incorrect unit: Expected '{expected_unit}', but got '{match.group('unit')}'."

    if not math.isclose(submitted_val, expected_value, rel_tol=tolerance, abs_tol=tolerance):
        return False, f"Value is incorrect: Expected {expected_value:g} {expected_unit}, got {submitted_val:g} {expected_unit}."

    return True, f"Correct! {expected_value:g} {expected_unit}."


# ------------------------------------------------------------------------------
# Data Models
# ------------------------------------------------------------------------------


@dataclass(frozen=True)
class ChemistryStoichiometryProblem:
    original: str
    normalized_problem: str
    reactants: list[str]
    products: list[str]
    coefficients: list[int]
    needs_balancing: bool
    given_species: str
    given_value: float
    given_unit: str  # "g" or "mol"
    target_species: str
    target_unit: str  # "g", "mol", "L"
    sig_figs: int = 3
    is_limiting_reactant_problem: bool = False
    second_given_species: Optional[str] = None
    second_given_value: Optional[float] = None
    second_given_unit: Optional[str] = None
    is_khmer: bool = False


@dataclass(frozen=True)
class ChemistrySolutionStep:
    key: str
    heading: str
    explanation: str
    latex: Optional[str] = None
    table: Optional[dict[str, Any]] = None
    reaction_layout: Optional[dict[str, Any]] = None


@dataclass
class WorkedChemistrySolution:
    reactants: list[str]
    products: list[str]
    coefficients: list[int]
    equation_latex: str
    target_species: str
    target_value: float
    target_unit: str
    answer_latex: str
    answer_text: str
    steps: list[ChemistrySolutionStep] = field(default_factory=list)
    limiting_reactant: Optional[str] = None


# ------------------------------------------------------------------------------
# Problem Parsing
# ------------------------------------------------------------------------------

_UNSUPPORTED_CHEMISTRY_RE = re.compile(
    r"\b(titration|molarity|\b\d+(?:\.\d+)?\s*M\b|neutraliz|acid-base|buffer|equilibrium|ka|kb|half-reaction|oxidation-reduction|galvanic|electrochem)\b",
    re.IGNORECASE,
)
_UNSUPPORTED_CHEMISTRY_KM_RE = re.compile(r"(ទីត្រា|កំហាប់ម៉ូល|អាស៊ីត-បាស|សមតុល្យគីមី|កាតូត|អាណូត|អេឡិចត្រូគីមី)")


def parse_chemistry_stoichiometry_problem(text: str) -> Optional[ChemistryStoichiometryProblem]:
    """Parse a high school chemistry stoichiometry problem in English or Khmer."""
    if not text or not text.strip():
        return None

    # Check unsupported topics first -> honest degradation
    if _UNSUPPORTED_CHEMISTRY_RE.search(text) or _UNSUPPORTED_CHEMISTRY_KM_RE.search(text):
        return None

    is_km = bool(re.search(r"[\u1780-\u17ff]", text))
    lowered = text.lower()

    # Match reaction: e.g. "2H2 + O2 -> 2H2O" or "N2 + H2 -> NH3" or "CH4 + 2O2 -> CO2 + 2H2O"
    eq_match = re.search(
        r"(?P<reactants>\d*\s*[A-Z][A-Za-z0-9\(\)]*(?:\s*\+\s*\d*\s*[A-Z][A-Za-z0-9\(\)]*)*)\s*(?:->|→|=)\s*(?P<products>\d*\s*[A-Z][A-Za-z0-9\(\)]*(?:\s*\+\s*\d*\s*[A-Z][A-Za-z0-9\(\)]*)*)",
        text,
    )
    if not eq_match:
        return None

    reactants_raw, products_raw = eq_match.group("reactants").strip(), eq_match.group("products").strip()

    def _split_species(s: str) -> tuple[list[str], list[int]]:
        parts = [p.strip() for p in s.split("+") if p.strip()]
        species = []
        coeffs = []
        for p in parts:
            m = re.match(r"^(\d+)\s*([A-Za-z0-9\(\)]+)$", p)
            if m:
                coeffs.append(int(m.group(1)))
                species.append(m.group(2).strip())
            else:
                coeffs.append(1)
                species.append(p)
        return species, coeffs

    reactants, r_coeffs = _split_species(reactants_raw)
    products, p_coeffs = _split_species(products_raw)

    if not reactants or not products:
        return None

    # Check if balancing is needed
    try:
        balanced_coeffs = balance_reaction(reactants, products)
    except Exception:
        return None

    needs_balancing = "unbalanced" in lowered or balanced_coeffs != (r_coeffs + p_coeffs)

    # Detect Limiting Reactant problem
    is_limiting = "limiting" in lowered or "limite" in lowered or "ប្រតិកម្មកំណត់" in text

    # Extract given quantities and species
    all_species = reactants + products

    # Find numbers with units: (value, unit, species)
    quantities: list[tuple[float, str, str]] = []
    matches = list(re.finditer(
        r"(?P<val>\d+(?:\.\d+)?)\s*(?P<unit>g|grams?|mol|moles?|l|liters?|litres?)\b(?:\s+(?:of\s+)?(?P<spec>[A-Za-z0-9\(\)]+))?",
        text,
        re.IGNORECASE,
    ))

    for m in matches:
        val = float(m.group("val"))
        unit_str = m.group("unit").lower()
        unit = "g" if "g" in unit_str else ("mol" if "mol" in unit_str else "L")
        spec_candidate = m.group("spec")
        matched_spec = None
        if spec_candidate:
            for s in all_species:
                if s.lower() == spec_candidate.lower():
                    matched_spec = s
                    break
        # If not right next to it, search nearby before or after
        if not matched_spec:
            nearby_before = text[max(0, m.start() - 30) : m.start()]
            for s in all_species:
                if re.search(r"\b" + re.escape(s) + r"\b", nearby_before, re.IGNORECASE) or s in nearby_before:
                    matched_spec = s
                    break
        if not matched_spec:
            nearby_after = text[m.end() : m.end() + 30]
            for s in all_species:
                if re.search(r"\b" + re.escape(s) + r"\b", nearby_after, re.IGNORECASE) or s in nearby_after:
                    matched_spec = s
                    break

        if matched_spec:
            quantities.append((val, unit, matched_spec, m.group("val")))

    if not quantities:
        return None

    given_val, given_unit, given_species, given_val_str = quantities[0]
    second_species, second_val, second_unit = None, None, None
    if len(quantities) > 1 and is_limiting:
        second_val, second_unit, second_species, _ = quantities[1]

    # Target species & unit
    target_unit = "g"
    if "how many moles" in lowered or "in moles" in lowered or ("mol" in lowered and ("រក" in text or "ប៉ុន្មាន" in text)):
        target_unit = "mol"
    elif ("liters" in lowered or "litres" in lowered or "volume" in lowered or "stp" in lowered) and not ("mass" in lowered or "in grams" in lowered):
        target_unit = "L"
    elif "mass of" in lowered or "grams of" in lowered or "how many grams" in lowered or "in grams" in lowered or "ម៉ាស" in text:
        target_unit = "g"
    elif "moles of" in lowered and "produced" in lowered:
        target_unit = "mol"

    target_species = None
    target_match = re.search(
        r"(?:mass\s+of|moles\s+of|grams\s+of|volume\s+of|produced\s+(?:is\s+)?|required\s+for|កកើត\s*(?:ជា\s*)?|រក\s*)\s*([A-Za-z0-9\(\)]+)",
        text,
        re.IGNORECASE,
    )
    if target_match:
        cand = target_match.group(1).strip()
        for s in all_species:
            if s.lower() == cand.lower():
                target_species = s
                break

    if not target_species or target_species == given_species:
        # Pick from products first, or a different reactant
        for s in products:
            if s != given_species:
                target_species = s
                break
        if not target_species:
            for s in reactants:
                if s != given_species:
                    target_species = s
                    break
        if not target_species:
            target_species = products[0]

    sig_figs = count_sig_figs(given_val_str)

    return ChemistryStoichiometryProblem(
        original=text,
        normalized_problem=text.strip(),
        reactants=reactants,
        products=products,
        coefficients=balanced_coeffs,
        needs_balancing=needs_balancing,
        given_species=given_species,
        given_value=given_val,
        given_unit=given_unit,
        target_species=target_species,
        target_unit=target_unit,
        sig_figs=max(2, sig_figs),
        is_limiting_reactant_problem=is_limiting and second_species is not None,
        second_given_species=second_species,
        second_given_value=second_val,
        second_given_unit=second_unit,
        is_khmer=is_km,
    )


# ------------------------------------------------------------------------------
# Stoichiometry Solver
# ------------------------------------------------------------------------------


def solve_stoichiometry(problem: ChemistryStoichiometryProblem) -> WorkedChemistrySolution:
    """Solve the stoichiometry problem step by step with SymPy and molar masses."""
    reactants = problem.reactants
    products = problem.products
    coeffs = problem.coefficients
    species_order = reactants + products
    coeff_map = dict(zip(species_order, coeffs))

    # Calculate molar masses
    molar_masses = {s: calculate_molar_mass(s) for s in species_order}

    # Step 1: Reaction layout & balanced equation LaTeX
    reactant_terms = [f"{coeff_map[r] if coeff_map[r] > 1 else ''}{r}" for r in reactants]
    product_terms = [f"{coeff_map[p] if coeff_map[p] > 1 else ''}{p}" for p in products]
    equation_latex = f"{' + '.join(reactant_terms)} \\to {' + '.join(product_terms)}"

    steps: list[ChemistrySolutionStep] = []

    # Step 1: Balanced Equation & Reaction Layout
    steps.append(
        ChemistrySolutionStep(
            key="reaction",
            heading="ជំហានទី ១ · សមីការតុល្យការគីមី" if problem.is_khmer else "Step 1 · Balanced Chemical Reaction",
            explanation=(
                "ផ្ទៀងផ្ទាត់សមីការតុល្យការគីមី និងមេគុណស្ទូគ្យូមេទ្រី៖"
                if problem.is_khmer
                else "Verify the balanced chemical equation and stoichiometric coefficients:"
            ),
            reaction_layout={
                "reactants": reactants,
                "products": products,
                "coefficients": coeffs,
            },
            latex=equation_latex,
        )
    )

    # Step 2: Molar Masses Table
    table_rows = []
    for s in species_order:
        role = ("Reactant" if s in reactants else "Product") if not problem.is_khmer else ("អង្គធាតុប្រតិករ" if s in reactants else "អង្គធាតុកកើត")
        mm = f"{molar_masses[s]:.2f} g/mol"
        status = ""
        if s == problem.given_species:
            status = f"Given: {problem.given_value:g} {problem.given_unit}"
        elif s == problem.second_given_species and problem.second_given_value is not None:
            status = f"Given: {problem.second_given_value:g} {problem.second_given_unit}"
        elif s == problem.target_species:
            status = f"Target: ? {problem.target_unit}"
        else:
            status = "Excess" if not problem.is_khmer else "លើស"
        table_rows.append([s, role, mm, status])

    steps.append(
        ChemistrySolutionStep(
            key="molar",
            heading="ជំហានទី ២ · ម៉ាសម៉ូលនៃសារធាតុ" if problem.is_khmer else "Step 2 · Molar Masses & Quantities",
            explanation=(
                "ស្រង់ម៉ាសម៉ូលពីតារាងខួបនៃធាតុគីមី និងកំណត់បម្រាប់ប្រធាន៖"
                if problem.is_khmer
                else "Determine molar masses from atomic weights and identify initial quantities:"
            ),
            table={
                "columns": ["Substance", "Role", "Molar Mass", "Quantity"],
                "rows": table_rows,
            },
        )
    )

    # Step 3: Stoichiometric Calculations
    # Conversion of given 1
    limiting_reactant = None
    if problem.is_limiting_reactant_problem and problem.second_given_species:
        # Limiting reactant calculation
        m1 = problem.given_value
        spec1 = problem.given_species
        n1 = m1 / molar_masses[spec1] if problem.given_unit == "g" else m1

        m2 = problem.second_given_value or 0.0
        spec2 = problem.second_given_species
        n2 = m2 / molar_masses[spec2] if problem.second_given_unit == "g" else m2

        # Ratio of moles to coefficient
        r1 = n1 / coeff_map[spec1]
        r2 = n2 / coeff_map[spec2]

        if r1 <= r2:
            limiting_reactant = spec1
            n_limiting = n1
            limiting_coeff = coeff_map[spec1]
        else:
            limiting_reactant = spec2
            n_limiting = n2
            limiting_coeff = coeff_map[spec2]

        target_coeff = coeff_map[problem.target_species]
        n_target = n_limiting * (target_coeff / limiting_coeff)

        steps.append(
            ChemistrySolutionStep(
                key="limiting",
                heading="ជំហានទី ៣ · កំណត់អង្គធាតុប្រតិករកំណត់" if problem.is_khmer else "Step 3 · Determine Limiting Reactant",
                explanation=(
                    f"គណនាចំនួនម៉ូល {spec1} = {n1:.3f} mol និង {spec2} = {n2:.3f} mol។ "
                    f"អង្គធាតុប្រតិករកំណត់គឺ {limiting_reactant} ព្រោះមានសមាមាត្រម៉ូលតូចជាង។"
                    if problem.is_khmer
                    else f"Moles of {spec1} = {n1:.3f} mol; moles of {spec2} = {n2:.3f} mol. "
                    f"{limiting_reactant} is the limiting reactant because it has the smaller mole ratio."
                ),
                latex=f"n({spec1}) = {n1:.3f}\\text{{ mol}},\\quad n({spec2}) = {n2:.3f}\\text{{ mol}}",
            )
        )

    else:
        # Standard single given calculation
        spec = problem.given_species
        val = problem.given_value
        if problem.given_unit == "g":
            n_given = val / molar_masses[spec]
            step_calc_latex = f"n({spec}) = \\frac{{{val:g}\\text{{ g}}}}{{{molar_masses[spec]:.2f}\\text{{ g/mol}}}} = {n_given:.4f}\\text{{ mol}}"
        else:
            n_given = val
            step_calc_latex = f"n({spec}) = {val:g}\\text{{ mol}}"

        # Mole ratio
        given_coeff = coeff_map[spec]
        target_coeff = coeff_map[problem.target_species]
        n_target = n_given * (target_coeff / given_coeff)
        ratio_latex = f"n({problem.target_species}) = {n_given:.4f} \\times \\frac{{{target_coeff}}}{{{given_coeff}}} = {n_target:.4f}\\text{{ mol}}"

        steps.append(
            ChemistrySolutionStep(
                key="calc",
                heading="ជំហានទី ៣ · គណនាចំនួនម៉ូល និងសមាមាត្រម៉ូល" if problem.is_khmer else "Step 3 · Mole Ratio & Conversions",
                explanation=(
                    f"បំលែងម៉ាសទៅជាម៉ូល រួចប្រើសមាមាត្រស្ទូគ្យូមេទ្រី {target_coeff}:{given_coeff}៖"
                    if problem.is_khmer
                    else f"Convert given mass to moles, then apply the stoichiometric mole ratio ({target_coeff}:{given_coeff}):"
                ),
                latex=f"{step_calc_latex} \\implies {ratio_latex}",
            )
        )

    # Step 4: Final Target Value & Unit Conversion
    if problem.target_unit == "g":
        target_val = n_target * molar_masses[problem.target_species]
    elif problem.target_unit == "L":
        target_val = n_target * STP_MOLAR_VOLUME
    else:  # "mol"
        target_val = n_target

    disp_val = format_sig_figs(target_val, problem.sig_figs)
    final_float = float(disp_val)

    answer_latex = f"{disp_val}\\text{{ {problem.target_unit} of {problem.target_species}}}"
    if limiting_reactant:
        answer_text = (
            f"អង្គធាតុប្រតិករកំណត់គឺ {limiting_reactant}។ បរិមាណ {problem.target_species} ដែលកកើតគឺ {disp_val} {problem.target_unit}។"
            if problem.is_khmer
            else f"The limiting reactant is {limiting_reactant}. The yield of {problem.target_species} is {disp_val} {problem.target_unit}."
        )
    else:
        answer_text = (
            f"បរិមាណ {problem.target_species} គឺ {disp_val} {problem.target_unit}។"
            if problem.is_khmer
            else f"The calculated amount of {problem.target_species} is {disp_val} {problem.target_unit}."
        )

    return WorkedChemistrySolution(
        reactants=reactants,
        products=products,
        coefficients=coeffs,
        equation_latex=equation_latex,
        target_species=problem.target_species,
        target_value=final_float,
        target_unit=problem.target_unit,
        answer_latex=answer_latex,
        answer_text=answer_text,
        steps=steps,
        limiting_reactant=limiting_reactant,
    )


# ------------------------------------------------------------------------------
# Request Matchers & Turn Builders
# ------------------------------------------------------------------------------


def match_chemistry_stoichiometry_problem(request: VisualTutorTurnRequest) -> Optional[ChemistryStoichiometryProblem]:
    """Check if the request is a chemistry stoichiometry problem to solve in full."""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if str(metadata.get("tutor_mode") or "").strip().lower() == TRY_MYSELF_MODE:
        return None

    subject = str(request.subject or "").lower()
    if subject and subject not in ("chemistry", "general", "គីមីវិទ្យា"):
        return None

    msg = request.message or ""
    problem = parse_chemistry_stoichiometry_problem(msg)
    if problem is None:
        return None

    if request.action == VisualTutorAction.SUBMIT_PROBLEM:
        return problem
    if request.action == VisualTutorAction.SUBMIT_STEP:
        current = parse_chemistry_stoichiometry_problem(request.current_state.problem_text or "")
        if current is None or current.normalized_problem != problem.normalized_problem:
            return problem
    return None


def match_chemistry_stoichiometry_followup(request: VisualTutorTurnRequest) -> Optional[ChemistryStoichiometryProblem]:
    """Check if the student is asking a follow-up question about a stoichiometry solution."""
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    if str(metadata.get("tutor_mode") or "").strip().lower() == TRY_MYSELF_MODE:
        return None
    if not (request.message or "").strip():
        return None
    if parse_chemistry_stoichiometry_problem(request.message or "") is not None:
        return None
    return parse_chemistry_stoichiometry_problem(request.current_state.problem_text or "")


def build_chemistry_worked_solution_turn(
    request: VisualTutorTurnRequest,
    problem: ChemistryStoichiometryProblem,
    *,
    session_id: str,
) -> VisualTutorTurnResponse:
    """Build the complete worked solution turn with deterministic action IDs."""
    solution = solve_stoichiometry(problem)
    msg = (
        f"នេះជាដំណោះស្រាយស្តូគ្យូមេទ្រីមួយជំហានម្តងៗ។ {solution.answer_text} "
        "អ្នកអាចសួរខ្ញុំបន្ថែមអំពីជំហានណាមួយបាន។"
        if problem.is_khmer
        else (
            f"Here is the full worked solution, step by step. {solution.answer_text} "
            "Ask me about any step you want me to explain."
        )
    )
    task = (
        "សួរខ្ញុំអំពីជំហានណាមួយ ឬសាកល្បងលំហាត់គីមីវិទ្យាថ្មីមួយទៀត។"
        if problem.is_khmer
        else "Ask me about any step you'd like explained, or try another chemistry problem."
    )
    return _chemistry_solution_turn(
        request,
        problem,
        solution,
        session_id=session_id,
        message=msg,
        task=task,
    )


def answer_about_chemistry_solution(
    request: VisualTutorTurnRequest,
    problem: ChemistryStoichiometryProblem,
    *,
    session_id: str,
    llm_client: Any = None,
) -> VisualTutorTurnResponse:
    """Answer a student's follow-up question about one step of the chemistry solution."""
    solution = solve_stoichiometry(problem)
    step = _referenced_chemistry_step(request, solution)
    answer = _explain_chemistry_step(
        question=request.message or "",
        solution=solution,
        step=step,
        llm_client=llm_client,
        is_khmer=problem.is_khmer,
    )
    heading = (
        (f"អំពី{step.heading}" if step else "អំពីដំណោះស្រាយនេះ")
        if problem.is_khmer
        else (f"About {step.heading}" if step else "About this solution")
    )
    task = (
        "សួរខ្ញុំបន្ថែមអំពីជំហានណាមួយ ឬសាកល្បងលំហាត់ថ្មីមួយទៀត។"
        if problem.is_khmer
        else "Ask me anything else about this solution, or send another problem."
    )
    return _chemistry_solution_turn(
        request,
        problem,
        solution,
        session_id=session_id,
        message=answer,
        task=task,
        extra_sections=[
            ChemistrySolutionStep(key="reply", heading=heading, explanation=answer)
        ],
    )


def _referenced_chemistry_step(
    request: VisualTutorTurnRequest, solution: WorkedChemistrySolution
) -> Optional[ChemistrySolutionStep]:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    tapped = str(metadata.get("board_action_id") or "")
    if tapped.startswith("ws-chem-step-"):
        key = tapped[len("ws-chem-step-") :].rsplit("-", 1)[0]
        for step in solution.steps:
            if step.key == key:
                return step

    words = (request.message or "").lower()
    keywords = {
        "balance": "reaction",
        "equation": "reaction",
        "reaction": "reaction",
        "សមីការ": "reaction",
        "molar": "molar",
        "mass": "molar",
        "periodic": "molar",
        "ម៉ាសម៉ូល": "molar",
        "ratio": "calc",
        "mole": "calc",
        "calculate": "calc",
        "ម៉ូល": "calc",
        "limiting": "limiting",
        "excess": "limiting",
        "កំណត់": "limiting",
    }
    for needle, key in keywords.items():
        if needle in words or needle in (request.message or ""):
            for step in solution.steps:
                if step.key == key:
                    return step

    for step in solution.steps:
        if step.heading.split("·")[0].strip().lower() in words:
            return step
    return None


def _explain_chemistry_step(
    *,
    question: str,
    solution: WorkedChemistrySolution,
    step: Optional[ChemistrySolutionStep],
    llm_client: Any,
    is_khmer: bool = False,
) -> str:
    """Generate a concise explanation grounded strictly in the verified chemistry."""
    q_low = question.lower()
    if "where" in q_low and ("come from" in q_low or "molar mass" in q_low or "g/mol" in q_low):
        return (
            "ម៉ាសម៉ូលត្រូវបានគណនាចេញពីតារាងខួបនៃធាតុគីមី ដោយបូកម៉ាសអាតូមនៃធាតុទាំងអស់ក្នុងរូបមន្ត។"
            if is_khmer
            else "The molar mass is calculated directly from standard atomic weights on the periodic table."
        )
    if "ratio" in q_low or "multiply" in q_low or "divide" in q_low or "coefficient" in q_low:
        return (
            "សមាមាត្រម៉ូលបានមកពីមេគុណស្ទូគ្យូមេទ្រីនៃសមីការគីមីដែលបានថ្លឹងរួច។"
            if is_khmer
            else "The mole ratio comes directly from the coefficients of the balanced chemical equation."
        )
    if "limiting" in q_low or "excess" in q_low:
        return (
            "អង្គធាតុប្រតិករកំណត់គឺជាអង្គធាតុដែលត្រូវបានប្រើប្រាស់អស់មុនគេក្នុងប្រតិកម្ម។"
            if is_khmer
            else "The limiting reactant is completely consumed first, dictating the maximum theoretical yield."
        )

    grounded = step.explanation if step else solution.answer_text

    system_prompt = (
        "You are a patient Grade 12 chemistry teacher in Cambodia. Answer the "
        "student's question about one step of a stoichiometry solution on the board. "
        "Rules: speak directly in simple terms; at most 3 short sentences; never "
        "contradict the solution; never invent numbers; no markdown, no LaTeX. "
        'Reply with JSON in exactly this shape: {"answer": "..."}'
    )
    user_prompt = (
        f"Solution on board: {solution.answer_text}\n"
        f"Equation: {solution.equation_latex}\n"
        + (f"Step: {step.heading}: {step.explanation}\n" if step else "")
        + f"Student question: {question.strip()}\n"
        "Answer the question accurately."
    )

    try:
        from api.services.visual_tutor.llm_teaching_planner import _default_llm_client

        client = llm_client or _default_llm_client()
        reply = client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
        raw = str(reply or "").strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        if isinstance(data, dict) and "answer" in data and isinstance(data["answer"], str):
            ans = " ".join(data["answer"].split())
            if ans and len(ans) <= 500:
                return ans
    except Exception:
        pass
    return grounded


def _chemistry_solution_turn(
    request: VisualTutorTurnRequest,
    problem: ChemistryStoichiometryProblem,
    solution: WorkedChemistrySolution,
    *,
    session_id: str,
    message: str,
    task: str,
    extra_sections: Optional[list[ChemistrySolutionStep]] = None,
) -> VisualTutorTurnResponse:
    """Render the chemistry solution actions and validate against teaching plan contract."""
    turn_id = str(uuid.uuid4())
    actions: list[VisualTutorBoardAction] = []
    plan_actions: list[dict[str, Any]] = []

    def add(action_type: VisualTutorCanvasActionType, section: str, **fields: Any) -> None:
        index = len(actions)
        action_id = f"ws-chem-{section}-{index}"
        zone = fields.pop("layout_zone", "working")
        duration = fields.pop("duration_ms", 450)

        action_kwargs: dict[str, Any] = {
            "id": action_id,
            "type": action_type,
            "sequence_index": index,
            "duration_ms": duration,
            "layout_zone": zone,
            "layout_flow": "vertical",
            "section_id": section,
            "metadata": {},
        }
        if "width" in fields:
            action_kwargs["width"] = fields["width"]
        if "height" in fields:
            action_kwargs["height"] = fields["height"]
        if "table" in fields:
            action_kwargs["table"] = fields["table"]
        if "reaction_layout" in fields:
            action_kwargs["metadata"]["reaction_layout"] = fields["reaction_layout"]
        for k in ("text", "latex", "requires_student_response", "task_type"):
            if k in fields and fields[k] is not None:
                action_kwargs[k] = fields[k]

        actions.append(VisualTutorBoardAction(**action_kwargs))

        item: dict[str, Any] = {
            "id": action_id,
            "type": action_type.value,
            "sequence_index": index,
            "duration_ms": duration,
            "layout_zone": zone,
            "layout_flow": "vertical",
            "section_id": section,
        }
        for k in ("text", "latex", "table", "reaction_layout", "requires_student_response", "task_type"):
            if k in fields and fields[k] is not None:
                item[k] = fields[k]
        plan_actions.append(item)

    for step in solution.steps:
        sec = f"step-{step.key}"
        add(VisualTutorCanvasActionType.WRITE_TEXT, sec, text=f"{step.heading}. {step.explanation}")
        if step.reaction_layout:
            add(
                VisualTutorCanvasActionType.SHOW_REACTION_LAYOUT,
                sec,
                reaction_layout=step.reaction_layout,
                duration_ms=650,
                width=450,
                height=120,
            )
        if step.table:
            add(
                VisualTutorCanvasActionType.SHOW_TABLE,
                sec,
                table=step.table,
                duration_ms=600,
                width=450,
                height=40 + 28 * len(step.table["rows"]),
            )
        if step.latex:
            add(VisualTutorCanvasActionType.WRITE_EQUATION, sec, latex=step.latex, duration_ms=550)

    # Final Answer
    add(
        VisualTutorCanvasActionType.WRITE_TEXT,
        "answer",
        text=f"{'ចម្លើយ' if problem.is_khmer else 'Answer'} · {solution.answer_text}",
    )
    add(
        VisualTutorCanvasActionType.WRITE_EQUATION,
        "answer",
        latex=solution.answer_latex,
        duration_ms=600,
    )

    # Extra reply sections
    for reply in extra_sections or []:
        add(
            VisualTutorCanvasActionType.WRITE_TEXT,
            f"reply-{reply.key}",
            text=f"{reply.heading}. {reply.explanation}",
        )

    # Student Task
    add(
        VisualTutorCanvasActionType.STUDENT_TASK,
        "next",
        layout_zone="student_task",
        text=task,
        requires_student_response=True,
        task_type="conceptual_operation",
        duration_ms=0,
    )

    plan = validate_teaching_plan(
        {
            "schema_version": 1,
            "representation": "worked_example",
            "learning_objective": "Understand reaction stoichiometry and mole calculations.",
            "teaching_message": message,
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

    return VisualTutorTurnResponse(
        session_id=session_id,
        turn_id=turn_id,
        screen_state=VisualTutorScreenState.ASKING_QUESTION,
        tutor_status="Waiting for you",
        spoken_text=message,
        display_text=message,
        teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
        final_answer_locked=False,
        student_task=task,
        board=VisualTutorBoard(
            type=VisualTutorBoardType.EQUATION_STEPS,
            title="Stoichiometry Worked Solution",
            items=[
                VisualTutorBoardItem(label=step.heading, content=step.explanation, status="done")
                for step in solution.steps
            ],
            metadata={"worked_solution": True, "chemistry_stoichiometry": True},
            actions=actions,
        ),
        board_actions=actions,
        speech=VisualTutorSpeech(text=message, language="km" if problem.is_khmer else "en"),
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
        teaching_plan=plan,
        metadata={
            "teaching_plan": plan,
            "worked_solution": True,
            "chemistry_stoichiometry": True,
            "target": solution.target_species,
            "target_value": solution.target_value,
            "target_unit": solution.target_unit,
        },
    )
