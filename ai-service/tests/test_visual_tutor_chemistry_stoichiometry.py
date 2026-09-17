"""Tests for Grade 12 Chemistry: Stoichiometry.

Verifies:
1. Programmatic equation balancing with SymPy.
2. Molar masses computed from hardcoded periodic table atomic weights.
3. Consistent significant figures.
4. 8 distinct stoichiometry problem shapes (including balancing first).
5. Explicit unit carrying and unit validation.
6. Board actions have deterministic IDs and valid schemas (SHOW_REACTION_LAYOUT, SHOW_TABLE, etc.).
7. Follow-up questions about individual steps are answered accurately.
8. Khmer language problem phrasing.
9. Unsupported chemistry topics degrade honestly to solver_not_ready.
"""

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.chemistry_stoichiometry import (
    parse_chemistry_stoichiometry_problem,
    solve_stoichiometry,
    verify_stoichiometry_answer,
    calculate_molar_mass,
    balance_reaction,
    match_chemistry_stoichiometry_problem,
    build_chemistry_worked_solution_turn,
    match_chemistry_stoichiometry_followup,
    answer_about_chemistry_solution,
)


@pytest.fixture(autouse=True)
def _scope_lock_grade12_stem(monkeypatch):
    """Enable the Grade 12 STEM scope lock for these tests."""
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_SCOPE_LOCK", "grade12_stem")


# ==============================================================================
# 1. Ground Truth Verification: Periodic Table & Programmatic Balancing
# ==============================================================================


def test_molar_mass_table_in_code() -> None:
    """Molar masses come from an explicit table in the code, not from an LLM."""
    assert calculate_molar_mass("H2O") == pytest.approx(18.015, abs=0.01)
    assert calculate_molar_mass("CO2") == pytest.approx(44.01, abs=0.01)
    assert calculate_molar_mass("CH4") == pytest.approx(16.04, abs=0.01)
    assert calculate_molar_mass("CaCO3") == pytest.approx(100.09, abs=0.01)
    assert calculate_molar_mass("NH3") == pytest.approx(17.03, abs=0.01)
    assert calculate_molar_mass("O2") == pytest.approx(32.00, abs=0.01)
    assert calculate_molar_mass("N2") == pytest.approx(28.01, abs=0.01)


def test_programmatic_equation_balancing() -> None:
    """Equations are balanced programmatically and verified before teaching."""
    coeffs = balance_reaction(["N2", "H2"], ["NH3"])
    assert coeffs == [1, 3, 2]

    combustion_coeffs = balance_reaction(["C3H8", "O2"], ["CO2", "H2O"])
    assert combustion_coeffs == [1, 5, 3, 4]


# ==============================================================================
# 2. 8 Distinct Stoichiometry Problem Shapes
# ==============================================================================


def test_shape_1_mole_to_mole() -> None:
    """Shape 1: 2H2 + O2 -> 2H2O, given 4.0 mol H2 -> 4.0 mol H2O."""
    text = "Given the reaction 2H2 + O2 -> 2H2O, how many moles of H2O are produced from 4.0 moles of H2?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.given_species == "H2"
    assert problem.given_value == 4.0
    assert problem.given_unit == "mol"
    assert problem.target_species == "H2O"
    assert problem.target_unit == "mol"

    solution = solve_stoichiometry(problem)
    assert solution.target_value == pytest.approx(4.0)
    assert solution.target_unit == "mol"
    assert "4.0" in solution.answer_text


def test_shape_2_mass_to_mole() -> None:
    """Shape 2: CH4 + 2O2 -> CO2 + 2H2O, given 32.0 g CH4 -> 2.00 mol CO2."""
    text = "How many moles of CO2 are produced by the complete combustion of 32.0 g of CH4 in CH4 + 2O2 -> CO2 + 2H2O?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.given_species == "CH4"
    assert problem.given_value == 32.0
    assert problem.given_unit == "g"
    assert problem.target_species == "CO2"
    assert problem.target_unit == "mol"

    solution = solve_stoichiometry(problem)
    assert solution.target_value == pytest.approx(2.00, abs=0.05)
    assert solution.target_unit == "mol"


def test_shape_3_mole_to_mass() -> None:
    """Shape 3: 2H2 + O2 -> 2H2O, given 3.00 mol O2 -> 108 g H2O."""
    text = "What mass of H2O in grams is produced from 3.00 moles of O2 reacting with excess H2 in 2H2 + O2 -> 2H2O?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.given_species == "O2"
    assert problem.given_value == 3.00
    assert problem.given_unit == "mol"
    assert problem.target_species == "H2O"
    assert problem.target_unit == "g"

    solution = solve_stoichiometry(problem)
    assert solution.target_value == pytest.approx(108.0, abs=1.0)
    assert solution.target_unit == "g"


def test_shape_4_mass_to_mass() -> None:
    """Shape 4: CaCO3 -> CaO + CO2, given 25.0 g CaCO3 -> 11.0 g CO2."""
    text = "What mass of CO2 in grams is produced from the thermal decomposition of 25.0 g of CaCO3 according to CaCO3 -> CaO + CO2?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.given_species == "CaCO3"
    assert problem.given_value == 25.0
    assert problem.given_unit == "g"
    assert problem.target_species == "CO2"
    assert problem.target_unit == "g"

    solution = solve_stoichiometry(problem)
    assert solution.target_value == pytest.approx(11.0, abs=0.2)
    assert solution.target_unit == "g"


def test_shape_5_unbalanced_reaction_needs_balancing_first() -> None:
    """Shape 5: Unbalanced reaction N2 + H2 -> NH3, given 28.0 g N2 -> 34.1 g NH3."""
    text = "Given the unbalanced reaction N2 + H2 -> NH3, how many grams of NH3 are produced from 28.0 g of N2?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.needs_balancing is True

    solution = solve_stoichiometry(problem)
    # Balanced coefficients should be [1, 3, 2]
    assert solution.coefficients == [1, 3, 2]
    # 28.0 g N2 / 28.01 g/mol = 1.00 mol N2 -> 2.00 mol NH3 -> 2.00 * 17.03 = 34.1 g NH3
    assert solution.target_value == pytest.approx(34.1, abs=0.3)
    assert solution.target_unit == "g"


def test_shape_6_combustion_reaction() -> None:
    """Shape 6: C3H8 + 5O2 -> 3CO2 + 4H2O, given 44.0 g C3H8, find mass of O2 needed."""
    text = "What mass of O2 in grams is required for the complete combustion of 44.0 g of C3H8 in C3H8 + 5O2 -> 3CO2 + 4H2O?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.given_species == "C3H8"
    assert problem.target_species == "O2"

    solution = solve_stoichiometry(problem)
    # 44.0 g C3H8 / 44.1 g/mol = 0.998 mol C3H8 -> 0.998 * 5 = 4.99 mol O2 -> 4.99 * 32.0 = 160 g
    assert solution.target_value == pytest.approx(160.0, abs=2.0)
    assert solution.target_unit == "g"


def test_shape_7_limiting_reactant() -> None:
    """Shape 7: 10.0 g H2 + 64.0 g O2 -> H2O. O2 is limiting, forms 72.1 g H2O."""
    text = "If 10.0 g of H2 reacts with 64.0 g of O2 to form H2O according to 2H2 + O2 -> 2H2O, which is the limiting reactant and how many grams of H2O are produced?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.is_limiting_reactant_problem is True

    solution = solve_stoichiometry(problem)
    assert solution.limiting_reactant == "O2"
    assert solution.target_value == pytest.approx(72.1, abs=0.5)
    assert solution.target_unit == "g"


def test_shape_8_gas_stoichiometry_stp() -> None:
    """Shape 8: Mg + 2HCl -> MgCl2 + H2, given 12.0 g Mg, find liters of H2 at STP (22.4 L/mol)."""
    text = "What volume of H2 gas at STP in liters is produced when 12.0 g of Mg reacts with excess HCl in Mg + 2HCl -> MgCl2 + H2?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.target_unit == "L"

    solution = solve_stoichiometry(problem)
    # 12.0 g / 24.31 = 0.494 mol -> 0.494 * 22.4 = 11.1 L
    assert solution.target_value == pytest.approx(11.1, abs=0.2)
    assert solution.target_unit == "L"


# ==============================================================================
# 3. Khmer Language Phrasing
# ==============================================================================


def test_khmer_stoichiometry_problem_parsing() -> None:
    """Khmer phrasing for mole calculation."""
    text = "តាមសមីការ 2H2 + O2 -> 2H2O បើសិនជាមាន H2 ចំនួន 4.0 mol ចូលរួមប្រតិកម្ម តើកកើត H2O ចំនួនប៉ុន្មាន mol?"
    problem = parse_chemistry_stoichiometry_problem(text)
    assert problem is not None
    assert problem.given_species == "H2"
    assert problem.given_value == 4.0
    assert problem.target_species == "H2O"

    solution = solve_stoichiometry(problem)
    assert solution.target_value == pytest.approx(4.0)
    assert solution.target_unit == "mol"


# ==============================================================================
# 4. Unit & Significant Figures Enforcement
# ==============================================================================


def test_unit_enforcement_correct() -> None:
    valid, msg = verify_stoichiometry_answer("34.1 g", expected_value=34.1, expected_unit="g")
    assert valid is True
    assert "correct" in msg.lower()


def test_unit_enforcement_missing_unit_fails() -> None:
    valid, msg = verify_stoichiometry_answer("34.1", expected_value=34.1, expected_unit="g")
    assert valid is False
    assert "missing" in msg.lower() or "unit" in msg.lower()


def test_unit_enforcement_wrong_unit_fails() -> None:
    valid, msg = verify_stoichiometry_answer("34.1 mol", expected_value=34.1, expected_unit="g")
    assert valid is False
    assert "unit" in msg.lower()


def test_unit_enforcement_wrong_value_fails() -> None:
    valid, msg = verify_stoichiometry_answer("50.0 g", expected_value=34.1, expected_unit="g")
    assert valid is False
    assert "value" in msg.lower() or "expected" in msg.lower()


# ==============================================================================
# 5. Deterministic Board Actions and Contract Validation
# ==============================================================================


def test_board_action_deterministic_ids_and_reaction_layout() -> None:
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Chemistry",
        topic="Stoichiometry",
        message="Given the reaction 2H2 + O2 -> 2H2O, how many moles of H2O are produced from 4.0 moles of H2?",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    problem = parse_chemistry_stoichiometry_problem(req.message or "")
    assert problem is not None

    response = build_chemistry_worked_solution_turn(req, problem, session_id="test-session")
    assert response is not None
    assert response.teaching_mode.value == "full_solution"

    # Deterministic action IDs: ws-chem-step-...
    action_ids = [a.id for a in response.board_actions]
    assert any("ws-chem-step-reaction" in aid for aid in action_ids)
    assert any("ws-chem-step-molar" in aid for aid in action_ids)
    assert any("ws-chem-step-calc" in aid for aid in action_ids)
    assert any("ws-chem-answer" in aid for aid in action_ids)
    assert any("ws-chem-next" in aid for aid in action_ids)

    # Primitives: show_reaction_layout and show_table
    action_types = [a.type.value for a in response.board_actions]
    assert "show_reaction_layout" in action_types
    assert "show_table" in action_types
    assert "write_equation" in action_types
    assert "write_text" in action_types
    assert "student_task" in action_types


# ==============================================================================
# 6. Follow-Up Questions Grounded in Steps
# ==============================================================================


def test_followup_question_about_molar_mass() -> None:
    problem_text = "What mass of CO2 in grams is produced from 25.0 g of CaCO3 in CaCO3 -> CaO + CO2?"
    problem = parse_chemistry_stoichiometry_problem(problem_text)
    assert problem is not None

    # Follow-up: Where did 44.01 come from?
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Chemistry",
        topic="Stoichiometry",
        message="Where did 44.01 g/mol come from?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state={"problem_text": problem_text},
        metadata={"grade": 12, "board_action_id": "ws-chem-step-molar-1"},
    )

    match = match_chemistry_stoichiometry_followup(req)
    assert match is not None

    response = answer_about_chemistry_solution(req, match, session_id="test-session")
    assert response is not None
    assert "molar mass" in response.spoken_text.lower() or "periodic table" in response.spoken_text.lower() or "44.01" in response.spoken_text
    # Full solution remains on board + reply step
    action_ids = [a.id for a in response.board_actions]
    assert any("reply" in aid for aid in action_ids)


# ==============================================================================
# 7. End-to-End Orchestrator Dispatch & Honest Degradation
# ==============================================================================


def test_orchestrator_dispatches_chemistry_to_worked_solution() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Chemistry",
            topic="Stoichiometry",
            message="Given the reaction 2H2 + O2 -> 2H2O, how many moles of H2O are produced from 4.0 moles of H2?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("worked_solution") is True
    assert any("ws-chem" in a.id for a in response.board_actions)
    assert "4.0" in response.spoken_text or "4" in response.spoken_text


def test_unsupported_chemistry_problem_degrades_honestly() -> None:
    """Titration / solution stoichiometry is unsupported: must degrade honestly to solver_not_ready."""
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Chemistry",
            topic="Titration",
            message="What volume of 0.1 M NaOH is required to neutralize 25 mL of 0.2 M HCl in a titration?",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    assert response.metadata.get("generation_path") == "solver_not_ready"
    assert response.metadata.get("solver_ready") is False
    assert "not ready yet" in response.spoken_text.lower() or "មិនទាន់រួចរាល់" in response.spoken_text
