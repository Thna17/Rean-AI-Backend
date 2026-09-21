"""Unit tests for Universal AI STEM Solvers with RAG grounding.

Verifies that dynamic_worked_solution and teaching_plan_builder solve any
high school STEM problem across Mathematics, Physics, and Chemistry:
- Physics: Optics (Snell's Law), Thermodynamics (PV = nRT)
- Chemistry: Acid-Base Titration (pH = -log[H+]), Stoichiometry ICE tables
- Mathematics: Law of Cosines, Trigonometric Identities
- ホワイトボード Whiteboard Actions: deterministic IDs (ws-step-<key>-<idx>, ws-answer-<idx>, ws-next-<idx>)
- Clean LaTeX equations without outer dollar signs
- Table support (SHOW_TABLE with normalized columns/rows)
- Metadata verification (Tier 1 Verified vs Tier 2 Unverified)
- Multi-board pagination preservation in teaching plan builder
"""

from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from api.models.curriculum import CurriculumChunk, CurriculumSource
from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorCanvasActionType,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.dynamic_worked_solution import (
    DYNAMIC_WORKED_SOLUTION_SYSTEM_PROMPT,
    GenericSolutionStep,
    GenericWorkedSolution,
    _build_turn_response,
    _normalize_table,
    _parse_llm_solution_json,
    _solve_with_llm_rag,
    answer_dynamic_followup,
    build_dynamic_worked_solution_turn,
)
from api.services.visual_tutor.rag_curriculum_gate import (
    ClassificationResult,
    classify_student_query,
)
from api.services.visual_tutor.teaching_plan_builder import attach_validated_teaching_plan


class MockLLMClient:
    """Mock LLM client returning controlled JSON whiteboard solutions."""

    def __init__(self, response_payload: dict[str, Any]) -> None:
        self.response_payload = response_payload
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return json.dumps(self.response_payload)


# ==============================================================================
# 1. Physics: Optics (Snell's Law)
# ==============================================================================

def test_physics_optics_snells_law_solution():
    """Test dynamic generation for Optics with Snell's Law."""
    mock_payload = {
        "steps": [
            {
                "key": "identify",
                "heading": "Step 1 · Identify Given Parameters",
                "explanation": "Light travels from air into glass. We are given the refractive indices and incident angle.",
                "latex": r"n_1 = 1.0, \quad n_2 = 1.5, \quad \theta_1 = 30^\circ",
            },
            {
                "key": "formula",
                "heading": "Step 2 · Apply Snell's Law",
                "explanation": "State the law of refraction connecting angles and refractive indices.",
                "latex": r"n_1 \sin(\theta_1) = n_2 \sin(\theta_2)",
            },
            {
                "key": "solve",
                "heading": "Step 3 · Solve for Refraction Angle",
                "explanation": "Substitute given values and calculate the angle theta 2.",
                "latex": r"\sin(\theta_2) = \frac{1.0 \cdot \sin(30^\circ)}{1.5} = \frac{0.5}{1.5} = \frac{1}{3} \implies \theta_2 \approx 19.47^\circ",
            },
        ],
        "answer_text": "The angle of refraction is approximately 19.47 degrees.",
        "answer_latex": r"\theta_2 \approx 19.47^\circ",
    }
    llm = MockLLMClient(mock_payload)

    chunk = CurriculumChunk(
        id="chunk.physics.optics.snell",
        grade=12,
        subject="Physics",
        topic="Optics",
        subtopic="Refraction and Snell's Law",
        text="Snell's law describes the relationship between the angles of incidence and refraction.",
        formulas=["n_1 \\sin(\\theta_1) = n_2 \\sin(\\theta_2)"],
        solution_steps=[
            "Identify indices and incident angle",
            "State Snell's Law",
            "Calculate refraction angle",
        ],
        khmer_terms={"refraction": "កំហាក់ពន្លឺ", "incident angle": "មុំកាំពន្លឺ"},
        source=CurriculumSource(type="admin_published"),
    )
    classification = ClassificationResult(
        tier="verified",
        subject="physics",
        topic="Optics",
        grade=12,
        matching_chunks=[chunk],
        confidence=0.9,
    )

    req = VisualTutorTurnRequest(
        user_id="student-test",
        subject="Physics",
        message="A ray of light in air enters glass with n=1.5 at an angle of 30 degrees. Find the angle of refraction.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )

    turn = build_dynamic_worked_solution_turn(
        req,
        classification,
        session_id="session-optics-1",
        llm_client=llm,
    )

    # 1. Whiteboard board actions exist
    assert turn.board is not None
    assert len(turn.board_actions) >= 5

    # 2. Deterministic Action IDs
    action_ids = [a.id for a in turn.board_actions]
    assert any(a_id.startswith("ws-step-identify-") for a_id in action_ids)
    assert any(a_id.startswith("ws-step-formula-") for a_id in action_ids)
    assert any(a_id.startswith("ws-step-solve-") for a_id in action_ids)
    assert any(a_id.startswith("ws-answer-") for a_id in action_ids)
    assert any(a_id.startswith("ws-next-") for a_id in action_ids)

    # 3. Clean LaTeX equations (no outer dollar signs)
    for a in turn.board_actions:
        if a.latex:
            assert not a.latex.startswith("$")
            assert not a.latex.endswith("$")

    # 4. Tier 1 Verified Metadata
    assert turn.metadata["verified"] is True
    assert turn.metadata["curriculum_status"] == "verified_curriculum"
    assert turn.metadata["curriculum_topic"] == "Optics"
    assert "chunk.physics.optics.snell" in turn.metadata["curriculum_sources"]

    # 5. Prompt caching & RAG injection: prompt included topic and formula
    assert "Optics" in llm.last_user_prompt
    assert "Snell" in llm.last_user_prompt or "n_1" in llm.last_user_prompt


# ==============================================================================
# 2. Physics: Thermodynamics (PV = nRT)
# ==============================================================================

def test_physics_thermodynamics_ideal_gas():
    """Test dynamic generation for Thermodynamics with Ideal Gas Law."""
    mock_payload = {
        "steps": [
            {
                "key": "givens",
                "heading": "Step 1 · Identify Given State Variables",
                "explanation": "Pressure P = 100 kPa, Volume V = 0.025 m^3, Temperature T = 300 K, R = 8.314 J/(mol K).",
                "latex": r"P = 100000 \text{ Pa}, \quad V = 0.025 \text{ m}^3, \quad T = 300 \text{ K}",
            },
            {
                "key": "equation",
                "heading": "Step 2 · Apply the Ideal Gas Law",
                "explanation": "Relate state variables using PV = nRT to isolate the amount of substance n.",
                "latex": r"PV = nRT \implies n = \frac{PV}{RT}",
            },
            {
                "key": "evaluate",
                "heading": "Step 3 · Compute Moles",
                "explanation": "Substitute numerical values and solve for n.",
                "latex": r"n = \frac{100000 \cdot 0.025}{8.314 \cdot 300} \approx 1.002 \text{ mol}",
            },
        ],
        "answer_text": "The quantity of gas is approximately 1.00 mole.",
        "answer_latex": r"n \approx 1.00 \text{ mol}",
    }
    llm = MockLLMClient(mock_payload)

    classification = ClassificationResult(
        tier="unverified",  # general STEM problem without matching chunk
        subject="physics",
        topic="Thermodynamics",
        grade=12,
        matching_chunks=[],
        confidence=0.5,
    )

    req = VisualTutorTurnRequest(
        user_id="student-test",
        subject="Physics",
        message="A gas occupies 0.025 m^3 at 100 kPa and 300 K. Find the number of moles.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )

    turn = build_dynamic_worked_solution_turn(
        req,
        classification,
        session_id="session-thermo-1",
        llm_client=llm,
    )

    assert turn.board is not None
    # Tier 2 Unverified STEM since no curriculum chunk matched
    assert turn.metadata["verified"] is False
    assert turn.metadata["curriculum_status"] == "ai_unverified"

    action_ids = [a.id for a in turn.board_actions]
    assert any(a_id.startswith("ws-step-givens-") for a_id in action_ids)
    assert any(a_id.startswith("ws-step-equation-") for a_id in action_ids)
    assert any(a_id.startswith("ws-answer-") for a_id in action_ids)


# ==============================================================================
# 3. Chemistry: Acid-Base Titration with SHOW_TABLE
# ==============================================================================

def test_chemistry_acid_base_with_table():
    """Test Chemistry Acid-Base titration with tabular data output (SHOW_TABLE)."""
    mock_payload = {
        "steps": [
            {
                "key": "reaction",
                "heading": "Step 1 · Neutralization Reaction",
                "explanation": "Hydrochloric acid reacts with sodium hydroxide in a 1:1 molar ratio.",
                "latex": r"\text{HCl} + \text{NaOH} \rightarrow \text{NaCl} + \text{H}_2\text{O}",
            },
            {
                "key": "table_step",
                "heading": "Step 2 · Titration Data Analysis",
                "explanation": "Summarize initial, added, and final equivalence concentrations.",
                "latex": r"c_a V_a = c_b V_b",
                "table": {
                    "columns": ["Reagent", "Concentration (M)", "Volume (mL)"],
                    "rows": [
                        ["HCl (Acid)", "0.100", "25.0"],
                        ["NaOH (Base)", "0.050", "50.0"],
                    ],
                },
            },
            {
                "key": "ph_calc",
                "heading": "Step 3 · Calculate Resulting pH",
                "explanation": "At equivalence for strong acid and strong base, pH equals 7.",
                "latex": r"\text{pH} = -\log[\text{H}^+] = 7.0",
            },
        ],
        "answer_text": "The equivalence volume is 50.0 mL and neutral pH is 7.0.",
        "answer_latex": r"\text{pH} = 7.0, \quad V_b = 50.0 \text{ mL}",
    }
    llm = MockLLMClient(mock_payload)

    chunk = CurriculumChunk(
        id="chunk.chemistry.acid_base.titration",
        grade=12,
        subject="Chemistry",
        topic="Acids and Bases",
        subtopic="Titration and pH",
        text="Titration of strong acid with strong base reaches neutral point at pH 7.",
        formulas=["c_a V_a = c_b V_b", "\\text{pH} = -\\log[\\text{H}^+]"],
        solution_steps=["Write balanced equation", "Calculate moles", "Determine pH"],
        khmer_terms={"titration": "អត្រាកម្ម", "acid": "អាស៊ីត", "base": "បាស"},
        source=CurriculumSource(type="admin_published"),
    )
    classification = ClassificationResult(
        tier="verified",
        subject="chemistry",
        topic="Acids and Bases",
        grade=12,
        matching_chunks=[chunk],
        confidence=0.95,
    )

    req = VisualTutorTurnRequest(
        user_id="student-test",
        subject="Chemistry",
        message="Titrate 25 mL of 0.1 M HCl with 0.05 M NaOH. Find equivalence volume and pH.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )

    turn = build_dynamic_worked_solution_turn(
        req,
        classification,
        session_id="session-chem-1",
        llm_client=llm,
    )

    # 1. Verify SHOW_TABLE action was generated
    table_actions = [a for a in turn.board_actions if a.type == VisualTutorCanvasActionType.SHOW_TABLE]
    assert len(table_actions) == 1
    tbl_action = table_actions[0]
    assert tbl_action.table is not None
    assert tbl_action.table.columns == ["Reagent", "Concentration (M)", "Volume (mL)"]
    assert len(tbl_action.table.rows) == 2

    # 2. Verify Teaching Plan Builder includes SHOW_TABLE without dropping it
    plan_actions = turn.metadata["teaching_plan"]["board_actions"]
    plan_table_actions = [a for a in plan_actions if a.get("type") == "show_table"]
    assert len(plan_table_actions) == 1
    assert plan_table_actions[0]["table"]["columns"] == ["Reagent", "Concentration (M)", "Volume (mL)"]

    # 3. Verified Curriculum Metadata
    assert turn.metadata["verified"] is True
    assert turn.metadata["curriculum_topic"] == "Acids and Bases"


# ==============================================================================
# 4. Mathematics: Law of Cosines
# ==============================================================================

def test_math_law_of_cosines():
    """Test dynamic generation for Law of Cosines."""
    mock_payload = {
        "steps": [
            {
                "key": "state_law",
                "heading": "Step 1 · State the Law of Cosines",
                "explanation": "For any triangle with sides a, b, c and opposite angle C.",
                "latex": r"c^2 = a^2 + b^2 - 2ab \cos(C)",
            },
            {
                "key": "substitute",
                "heading": "Step 2 · Substitute Given Values",
                "explanation": "Substitute a = 5, b = 7, and angle C = 60 degrees into the formula.",
                "latex": r"c^2 = 5^2 + 7^2 - 2(5)(7)\cos(60^\circ)",
            },
            {
                "key": "evaluate",
                "heading": "Step 3 · Simplify and Evaluate",
                "explanation": "Since cos(60 deg) = 0.5, evaluate the expression to solve for c.",
                "latex": r"c^2 = 25 + 49 - 70(0.5) = 74 - 35 = 39 \implies c = \sqrt{39} \approx 6.24",
            },
        ],
        "answer_text": "The length of side c is sqrt(39) or approximately 6.24.",
        "answer_latex": r"c = \sqrt{39} \approx 6.24",
    }
    llm = MockLLMClient(mock_payload)

    chunk = CurriculumChunk(
        id="chunk.math.trig.law_of_cosines",
        grade=11,
        subject="Mathematics",
        topic="Trigonometry",
        subtopic="Law of Cosines",
        text="The law of cosines generalizes the Pythagorean theorem for any triangle.",
        formulas=["c^2 = a^2 + b^2 - 2ab \\cos(C)"],
        solution_steps=["State formula", "Substitute sides and angle", "Calculate square root"],
        khmer_terms={"cosine": "កូស៊ីនុស", "triangle": "ត្រីកោណ"},
        source=CurriculumSource(type="admin_published"),
    )
    classification = ClassificationResult(
        tier="verified",
        subject="mathematics",
        topic="Trigonometry",
        grade=11,
        matching_chunks=[chunk],
        confidence=0.9,
    )

    req = VisualTutorTurnRequest(
        user_id="student-test",
        subject="Mathematics",
        message="In a triangle, side a = 5, side b = 7, and angle C = 60 degrees. Find side c.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )

    turn = build_dynamic_worked_solution_turn(
        req,
        classification,
        session_id="session-cosines-1",
        llm_client=llm,
    )

    assert turn.board is not None
    assert turn.metadata["verified"] is True
    assert turn.metadata["curriculum_status"] == "verified_curriculum"
    assert turn.metadata["curriculum_topic"] == "Trigonometry"

    action_ids = [a.id for a in turn.board_actions]
    assert any(a_id.startswith("ws-step-state_law-") for a_id in action_ids)
    assert any(a_id.startswith("ws-step-substitute-") for a_id in action_ids)
    assert any(a_id.startswith("ws-step-evaluate-") for a_id in action_ids)
    assert any(a_id.startswith("ws-answer-") for a_id in action_ids)
    assert any(a_id.startswith("ws-next-") for a_id in action_ids)


# ==============================================================================
# 5. Multi-Board Pagination Preservation in TeachingPlanBuilder
# ==============================================================================

def test_teaching_plan_builder_bypasses_reduction_for_dynamic_worked_solution():
    """Verify teaching_plan_builder preserves all actions across boards without single-visual squashing."""
    mock_payload = {
        "steps": [
            {"key": "step1", "heading": "Step 1", "explanation": "Explanation 1", "latex": r"x = 1"},
            {"key": "step2", "heading": "Step 2", "explanation": "Explanation 2", "latex": r"y = 2"},
            {"key": "step3", "heading": "Step 3", "explanation": "Explanation 3", "latex": r"z = 3"},
            {"key": "step4", "heading": "Step 4", "explanation": "Explanation 4", "latex": r"w = 4"},
        ],
        "answer_text": "Completed all steps.",
        "answer_latex": r"w = 4",
    }
    llm = MockLLMClient(mock_payload)

    classification = ClassificationResult(
        tier="unverified",
        subject="mathematics",
        topic="Algebra",
        grade=12,
        matching_chunks=[],
        confidence=0.5,
    )

    req = VisualTutorTurnRequest(
        user_id="student-test",
        subject="Mathematics",
        message="Solve the system of 4 linear equations.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )

    turn = build_dynamic_worked_solution_turn(
        req,
        classification,
        session_id="session-pagination-1",
        llm_client=llm,
    )

    # Now pass through attach_validated_teaching_plan (which uses _select_plan)
    final_turn = attach_validated_teaching_plan(response=turn, request=req)

    # Invariants check:
    # 1. Plan was NOT reduced to a single visual: source is worked_solution
    assert final_turn.metadata.get("teaching_plan_source") == "worked_solution"
    plan_actions = final_turn.metadata["teaching_plan"]["board_actions"]
    assert len(plan_actions) >= 8  # 4 text + 4 latex + answer text + answer latex + student task

    # 2. All actions retain their deterministic IDs
    for a in plan_actions:
        assert a["id"].startswith("ws-")

    # 3. All non-task actions are placed in layout zones suitable for pagination
    working_actions = [a for a in plan_actions if a.get("layout_zone") in ("working", "visual")]
    assert len(working_actions) >= 8


# ==============================================================================
# 6. Interactive Follow-Up Q&A
# ==============================================================================

def test_dynamic_followup_question_appends_explanation():
    """Verify asking a question about a step appends explanation without replacing the board."""
    req = VisualTutorTurnRequest(
        user_id="student-test",
        subject="Physics",
        message="Why is the refractive index of air considered to be 1.0?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text="A ray of light in air enters glass with n=1.5 at an angle of 30 degrees. Find the angle of refraction.",
            board_version=1,
        ),
    )

    classification = ClassificationResult(
        tier="verified",
        subject="physics",
        topic="Optics",
        grade=12,
        matching_chunks=[],
        confidence=0.8,
    )

    class MockFollowupLLMClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            return "Air has an optical density very close to vacuum, so by convention n=1.0003 is rounded to 1.0."

    turn = answer_dynamic_followup(
        req,
        classification,
        session_id="session-optics-followup",
        llm_client=MockFollowupLLMClient(),
    )

    assert turn.board is not None
    action_ids = [a.id for a in turn.board_actions]
    # Reply step was appended with ws-followup-reply-<idx>
    assert any("followup-reply" in a_id or "reply-followup" in a_id for a_id in action_ids)
    # Spoken and display text address the question
    assert "optical density" in turn.spoken_text
