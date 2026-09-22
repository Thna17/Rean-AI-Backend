"""Unit and integration tests for Deep Conversational Follow-Up & Misconception Engine.

Verifies Prompt 4 requirements:
- Step-referencing follow-up identification (by number, ordinal, token, LaTeX)
- Language switching to Khmer with clean LaTeX equation preservation
- RAG curriculum misconception retrieval and pedagogical remediation
- Monotonic board_version increments with base_board_version linkage
- 3+ consecutive multi-turn conversational follow-ups on the same whiteboard without erasing earlier work
- Verification that equation verifier (verify_student_work) is skipped for conversational questions
- Verification that Flutter's boardIdentityMustChange remains False across turns (no whiteboard replay)
"""

from __future__ import annotations

import json
import re
from typing import Any
import pytest

from api.models.curriculum import CurriculumChunk, CurriculumMisconception, CurriculumSource
from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorCanvasActionType,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.dynamic_worked_solution import (
    GenericSolutionStep,
    GenericWorkedSolution,
    _detect_khmer_request,
    _extract_khmer_terms_summary,
    _find_targeted_misconception,
    _identify_referenced_step,
    answer_dynamic_followup,
    build_dynamic_worked_solution_turn,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.rag_curriculum_gate import ClassificationResult


class MockFollowupLLMClient:
    """Mock LLM client returning controlled educational explanations."""

    def __init__(self, reply_text: str = "This step applies the core formula to compute the exact result.") -> None:
        self.reply_text = reply_text
        self.last_system_prompt: str | None = None
        self.last_user_prompt: str | None = None
        self.calls = 0

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.last_system_prompt = system_prompt
        self.last_user_prompt = user_prompt
        return self.reply_text


# ==============================================================================
# 1. Step-referencing and Keyword Detection Unit Tests
# ==============================================================================

def test_identify_referenced_step_by_number_and_keywords():
    """Verify semantic and ordinal identification of referenced whiteboard steps."""
    solution = GenericWorkedSolution(
        problem_text="In triangle ABC, a=5, b=7, C=60 deg. Find side c.",
        steps=[
            GenericSolutionStep(
                key="identify",
                heading="Step 1 · Identify Given Values",
                explanation="We are given sides a=5, b=7, and angle C=60 degrees.",
                latex="a = 5, \\quad b = 7, \\quad C = 60^\\circ",
            ),
            GenericSolutionStep(
                key="formula",
                heading="Step 2 · Apply Law of Cosines",
                explanation="State the cosine rule for side c.",
                latex="c^2 = a^2 + b^2 - 2ab \\cos(C)",
            ),
            GenericSolutionStep(
                key="solve",
                heading="Step 3 · Evaluate and Take Square Root",
                explanation="Substitute values and take the square root.",
                latex="c = \\sqrt{25 + 49 - 35} = \\sqrt{39}",
            ),
        ],
        answer_text="Side c is sqrt(39).",
        answer_latex="c = \\sqrt{39}",
        is_verified=True,
    )

    # By explicit step number (English)
    step, idx = _identify_referenced_step("Why did we do that in step 2?", solution, [])
    assert idx == 1
    assert step is not None and step.key == "formula"

    # By ordinal (English)
    step, idx = _identify_referenced_step("What is the first step doing?", solution, [])
    assert idx == 0
    assert step is not None and step.key == "identify"

    step, idx = _identify_referenced_step("Why did we take the square root in the last step?", solution, [])
    assert idx == 2
    assert step is not None and step.key == "solve"

    # By mathematical token (sqrt)
    step, idx = _identify_referenced_step("Where did the square root come from?", solution, [])
    assert idx == 2
    assert step is not None and step.key == "solve"

    # In Khmer by step digit (ជំហានទី ២)
    step, idx = _identify_referenced_step("ហេតុអ្វីបានជាយើងធ្វើបែបនេះក្នុងជំហានទី ២?", solution, [])
    assert idx == 1
    assert step is not None and step.key == "formula"

    # In Khmer by ordinal (ជំហានចុងក្រោយ)
    step, idx = _identify_referenced_step("ពន្យល់ជំហានចុងក្រោយ", solution, [])
    assert idx == 2
    assert step is not None and step.key == "solve"


def test_detect_khmer_request():
    """Verify detection of Khmer script and explicit Khmer language requests."""
    req_en = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Why take square root?",
        action=VisualTutorAction.SUBMIT_STEP,
    )
    assert not _detect_khmer_request("Why take square root?", req_en)

    # Khmer unicode characters
    assert _detect_khmer_request("ហេតុអ្វី?", req_en)

    # English phrases requesting Khmer
    assert _detect_khmer_request("Can you explain this in Khmer please?", req_en)
    assert _detect_khmer_request("Explain to khmer", req_en)

    # Request language_mode set to Khmer
    req_km = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Explain step 1",
        action=VisualTutorAction.SUBMIT_STEP,
        language_mode="khmer",
    )
    assert _detect_khmer_request("Explain step 1", req_km)


def test_find_targeted_misconception():
    """Verify matching common student misconceptions from curriculum chunks."""
    chunk = CurriculumChunk(
        id="chunk.optics.refraction",
        grade=12,
        subject="Physics",
        topic="Optics",
        subtopic="Snell's Law",
        text="Light bends when transitioning between media.",
        source=CurriculumSource(type="admin_published"),
        common_misconceptions=[
            CurriculumMisconception(
                text="Light always bends towards the normal line regardless of medium",
                correction="Light only bends towards the normal when passing into a denser medium (n2 > n1).",
            ),
            CurriculumMisconception(
                text="Angle of refraction is measured from the surface boundary",
                correction="Angles theta 1 and theta 2 are measured relative to the normal line, not the surface.",
            ),
        ],
    )

    misc = _find_targeted_misconception("Why isn't the angle measured from the surface?", [chunk])
    assert misc is not None
    assert "surface boundary" in misc
    assert "measured relative to the normal line" in misc


def test_extract_khmer_terms_summary():
    """Verify glossary extraction of authoritative Khmer curriculum terms."""
    chunk = CurriculumChunk(
        id="chunk.math.trig",
        grade=12,
        subject="Mathematics",
        topic="Trigonometry",
        subtopic="Law of Cosines",
        text="Cosine theorem relating sides and angles.",
        source=CurriculumSource(type="admin_published"),
        khmer_terms={
            "refraction": "ចំណាំងបែរ",
            "incident angle": "មុំចាំង",
            "refractive index": "សន្ទស្សន៍ចំណាំងបែរ",
        },
    )
    summary = _extract_khmer_terms_summary([chunk])
    assert "ចំណាំងបែរ" in summary
    assert "សន្ទស្សន៍ចំណាំងបែរ" in summary


# ==============================================================================
# 2. Math Follow-Up: Law of Cosines & Whiteboard Append Verification
# ==============================================================================

def test_math_law_of_cosines_followup_appends_smoothly():
    """Test follow-up question on Law of Cosines appends explanation without clearing whiteboard."""
    prob_text = "In triangle ABC, a = 5, b = 7, and angle C = 60 degrees. Find side c."
    session_id = "sess-math-followup-test-1"

    classification = ClassificationResult(
        tier="verified",
        grade=12,
        subject="mathematics",
        topic="Law of Cosines",
        is_khmer=False,
    )

    llm_solver = MockFollowupLLMClient(
        json.dumps({
            "steps": [
                {
                    "key": "identify",
                    "heading": "Step 1 · Identify Given Parameters",
                    "explanation": "We are given sides a=5, b=7, and angle C=60 degrees.",
                    "latex": r"a = 5, \quad b = 7, \quad C = 60^\circ",
                },
                {
                    "key": "formula",
                    "heading": "Step 2 · Apply the Law of Cosines",
                    "explanation": "State the standard relationship for unknown side c.",
                    "latex": r"c^2 = a^2 + b^2 - 2ab \cos(C)",
                },
                {
                    "key": "solve",
                    "heading": "Step 3 · Calculate and Take the Square Root",
                    "explanation": "Substitute the values and take the square root to find c.",
                    "latex": r"c = \sqrt{25 + 49 - 2(5)(7)(0.5)} = \sqrt{39}",
                },
            ],
            "answer_text": "The length of side c is sqrt(39).",
            "answer_latex": r"c = \sqrt{39}",
        })
    )

    # 1. First turn: Solve the problem
    req_solve = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message=prob_text,
        action=VisualTutorAction.SUBMIT_PROBLEM,
        current_state=VisualTutorTurnState(problem_text=prob_text),
    )
    resp_solve = build_dynamic_worked_solution_turn(
        req_solve,
        classification,
        session_id=session_id,
        llm_client=llm_solver,
    )

    assert resp_solve.metadata["board_update_mode"] == "replace"
    assert resp_solve.board_version == 1
    base_action_ids = [a.id for a in resp_solve.board_actions if a.type != VisualTutorCanvasActionType.STUDENT_TASK]
    assert "ws-step-identify-0" in base_action_ids
    assert "ws-answer-6" in base_action_ids

    # 2. Second turn: Student asks a follow-up question about the square root
    llm_followup = MockFollowupLLMClient(
        "We take the square root because the Law of Cosines formula gives $c^2 = 39$. "
        "To find the linear side length $c$, taking $\\sqrt{39}$ isolates the side."
    )

    req_followup = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Why did we take the square root in the last step?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text=prob_text),
        client_board_version=1,
    )

    resp_followup = answer_dynamic_followup(
        req_followup,
        classification,
        session_id=session_id,
        llm_client=llm_followup,
    )

    # Invariants for board persistence
    assert resp_followup.metadata["board_update_mode"] == "append"
    assert resp_followup.metadata["is_followup"] is True
    assert resp_followup.board_version == 2
    assert resp_followup.base_board_version == 1

    followup_action_ids = [a.id for a in resp_followup.board_actions]
    # All original base action IDs are still present
    for base_id in base_action_ids:
        assert base_id in followup_action_ids, f"Base action {base_id} was dropped on follow-up!"

    # New action with deterministic ID ws-followup-reply-0 exists
    assert "ws-followup-reply-0" in followup_action_ids
    reply_action = next(a for a in resp_followup.board_actions if a.id == "ws-followup-reply-0")
    assert "Explanation of Step 3" in reply_action.text
    assert "square root" in reply_action.text or "$c^2 = 39$" in reply_action.text


# ==============================================================================
# 3. Physics Follow-Up: Optics (Snell's Law) & RAG Injected Remediation
# ==============================================================================

def test_physics_optics_followup_explains_variable():
    """Test follow-up question on Optics explains variable meaning with LaTeX."""
    prob_text = "A light ray travels from air (n1 = 1.0) into glass (n2 = 1.5) at 30 degrees. Find the angle of refraction."
    session_id = "sess-optics-followup-test"

    chunk = CurriculumChunk(
        id="chunk.physics.optics.snell",
        grade=12,
        subject="Physics",
        topic="Optics",
        subtopic="Snell's Law",
        text="Snell's law of refraction.",
        source=CurriculumSource(type="admin_published"),
        khmer_terms={"refractive index": "សន្ទស្សន៍ចំណាំងបែរ", "incident angle": "មុំចាំង"},
        common_misconceptions=[
            CurriculumMisconception(
                text="n1 is the angle of refraction",
                correction="n1 represents the index of refraction of the initial incident medium.",
            )
        ],
    )

    classification = ClassificationResult(
        tier="verified",
        grade=12,
        subject="physics",
        topic="Optics",
        is_khmer=False,
        matching_chunks=[chunk],
    )

    llm_solver = MockFollowupLLMClient(
        json.dumps({
            "steps": [
                {
                    "key": "identify",
                    "heading": "Step 1 · Identify Indices of Refraction",
                    "explanation": "Air has index n_1 = 1.0 and glass has n_2 = 1.5.",
                    "latex": r"n_1 = 1.0, \quad n_2 = 1.5, \quad \theta_1 = 30^\circ",
                },
                {
                    "key": "solve",
                    "heading": "Step 2 · Apply Snell's Law",
                    "explanation": "Solve for the refracted angle theta 2.",
                    "latex": r"n_1 \sin(\theta_1) = n_2 \sin(\theta_2) \implies \theta_2 \approx 19.47^\circ",
                },
            ],
            "answer_text": "The angle of refraction is 19.47 degrees.",
            "answer_latex": r"\theta_2 \approx 19.47^\circ",
        })
    )

    # Initial solve
    req_solve = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        message=prob_text,
        action=VisualTutorAction.SUBMIT_PROBLEM,
        current_state=VisualTutorTurnState(problem_text=prob_text),
    )
    build_dynamic_worked_solution_turn(req_solve, classification, session_id=session_id, llm_client=llm_solver)

    # Student asks: What does n_1 mean?
    llm_followup = MockFollowupLLMClient(
        "In Snell's Law, $n_1$ represents the index of refraction of the first medium (air)."
    )

    req_followup = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        message="What does n_1 mean?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text=prob_text),
        client_board_version=1,
    )

    resp_followup = answer_dynamic_followup(
        req_followup,
        classification,
        session_id=session_id,
        llm_client=llm_followup,
    )

    assert resp_followup.metadata["board_update_mode"] == "append"
    assert "ws-followup-reply-0" in [a.id for a in resp_followup.board_actions]
    # Check that LLM prompt received target step 1 and the misconception
    assert "Step 1" in (llm_followup.last_user_prompt or "")
    assert "n1 represents the index of refraction" in (llm_followup.last_user_prompt or "")


# ==============================================================================
# 4. Khmer Language Switching Follow-Up
# ==============================================================================

def test_khmer_language_switching_in_followup():
    """Test switching language to Khmer when requested or asked in Khmer script."""
    prob_text = "A car starts from rest (u = 0) and accelerates at 2 m/s^2 for 5 seconds. Find final velocity."
    session_id = "sess-khmer-followup-test"

    classification = ClassificationResult(
        tier="verified",
        grade=12,
        subject="physics",
        topic="Kinematics",
        is_khmer=False,
    )

    llm_solver = MockFollowupLLMClient(
        json.dumps({
            "steps": [
                {
                    "key": "identify",
                    "heading": "Step 1 · Identify Given Parameters",
                    "explanation": "Car starts from rest, so initial velocity u = 0.",
                    "latex": r"u = 0, \quad a = 2\,\text{m/s}^2, \quad t = 5\,\text{s}",
                },
                {
                    "key": "solve",
                    "heading": "Step 2 · Apply Velocity Formula",
                    "explanation": "Calculate final velocity v = u + at.",
                    "latex": r"v = 0 + 2(5) = 10\,\text{m/s}",
                },
            ],
            "answer_text": "Final velocity is 10 m/s.",
            "answer_latex": r"v = 10\,\text{m/s}",
        })
    )

    # Initial solve
    req_solve = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        message=prob_text,
        action=VisualTutorAction.SUBMIT_PROBLEM,
        current_state=VisualTutorTurnState(problem_text=prob_text),
    )
    build_dynamic_worked_solution_turn(req_solve, classification, session_id=session_id, llm_client=llm_solver)

    # Student asks in Khmer: ហេតុអ្វីបានជា u = 0?
    km_reply = "ពីព្រោះរថយន្តចាប់ផ្តើមចេញដំណើរពីភាពស្ងៀម (starts from rest) ដូច្នេះល្បឿនដើមគឺ $u = 0$ ។"
    llm_followup = MockFollowupLLMClient(km_reply)

    req_followup = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        message="ហេតុអ្វីបានជា u = 0?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text=prob_text),
        client_board_version=1,
    )

    resp_followup = answer_dynamic_followup(
        req_followup,
        classification,
        session_id=session_id,
        llm_client=llm_followup,
    )

    assert resp_followup.metadata["board_update_mode"] == "append"
    reply_action = next(a for a in resp_followup.board_actions if a.id == "ws-followup-reply-0")
    # Heading and explanation in Khmer with preserved LaTeX
    assert "ការពន្យល់ជំហានទី ១" in reply_action.text
    assert re.search(r"[\u1780-\u17ff]", reply_action.text)
    assert "$u = 0$" in reply_action.text


# ==============================================================================
# 5. Multi-Turn Persistence: 3+ Consecutive Follow-Ups Without Board Replay
# ==============================================================================

def test_multi_turn_persistence_three_consecutive_followups():
    """Verify that 3+ consecutive questions smoothly append and never cause board rebuild/replay."""
    prob_text = "In triangle ABC, a = 5, b = 7, and angle C = 60 degrees. Find side c."
    session_id = "sess-consecutive-3-turns-test"

    classification = ClassificationResult(
        tier="verified",
        grade=12,
        subject="mathematics",
        topic="Law of Cosines",
        is_khmer=False,
    )

    # Turn 0: Base solve
    req_0 = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message=prob_text,
        action=VisualTutorAction.SUBMIT_PROBLEM,
        current_state=VisualTutorTurnState(problem_text=prob_text),
    )
    llm_solve = MockFollowupLLMClient(
        json.dumps({
            "steps": [
                {
                    "key": "identify",
                    "heading": "Step 1 · Identify Givens",
                    "explanation": "Given parameters a=5, b=7, C=60 deg.",
                    "latex": r"a = 5, \quad b = 7, \quad C = 60^\circ",
                },
                {
                    "key": "formula",
                    "heading": "Step 2 · Apply Formula",
                    "explanation": "State cosine law.",
                    "latex": r"c^2 = a^2 + b^2 - 2ab \cos(C)",
                },
                {
                    "key": "solve",
                    "heading": "Step 3 · Solve",
                    "explanation": "Evaluate root.",
                    "latex": r"c = \sqrt{39}",
                },
            ],
            "answer_text": "c is sqrt(39).",
            "answer_latex": r"c = \sqrt{39}",
        })
    )
    resp_0 = build_dynamic_worked_solution_turn(req_0, classification, session_id=session_id, llm_client=llm_solve)
    assert resp_0.board_version == 1

    rendered_actions_turn_0 = [a for a in resp_0.board_actions]
    action_ids_turn_0 = [a.id for a in rendered_actions_turn_0 if a.type != VisualTutorCanvasActionType.STUDENT_TASK]

    # Turn 1: Follow-up 1 ("What is the first step doing?")
    llm_f1 = MockFollowupLLMClient("Step 1 extracts all the given variables from the question.")
    req_1 = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="What is the first step doing?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text=prob_text),
        client_board_version=resp_0.board_version,
    )
    resp_1 = answer_dynamic_followup(req_1, classification, session_id=session_id, llm_client=llm_f1)

    assert resp_1.metadata["board_update_mode"] == "append"
    assert resp_1.board_version == 2
    assert resp_1.base_board_version == 1

    action_ids_turn_1 = [a.id for a in resp_1.board_actions if a.type != VisualTutorCanvasActionType.STUDENT_TASK]
    # Check that Turn 1 contains ALL Turn 0 actions + ws-followup-reply-0
    for id_0 in action_ids_turn_0:
        assert id_0 in action_ids_turn_1
    assert "ws-followup-reply-0" in action_ids_turn_1

    # Turn 2: Follow-up 2 ("Why is cos(60) equal to 0.5?")
    llm_f2 = MockFollowupLLMClient("$\\cos(60^\\circ) = \\frac{1}{2} = 0.5$ from the special right triangle (30-60-90).")
    req_2 = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Why is cos(60) equal to 0.5 in step 2?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text=prob_text),
        client_board_version=resp_1.board_version,
    )
    resp_2 = answer_dynamic_followup(req_2, classification, session_id=session_id, llm_client=llm_f2)

    assert resp_2.metadata["board_update_mode"] == "append"
    assert resp_2.board_version == 3
    assert resp_2.base_board_version == 2

    action_ids_turn_2 = [a.id for a in resp_2.board_actions if a.type != VisualTutorCanvasActionType.STUDENT_TASK]
    # Check that Turn 2 contains ALL Turn 1 actions + ws-followup-reply-1
    for id_1 in action_ids_turn_1:
        assert id_1 in action_ids_turn_2
    assert "ws-followup-reply-0" in action_ids_turn_2
    assert "ws-followup-reply-1" in action_ids_turn_2

    # Turn 3: Follow-up 3 ("Can you explain the final step in Khmer?")
    llm_f3 = MockFollowupLLMClient("ជំហានចុងក្រោយគណនាឫសការេនៃ $39$ ដើម្បីរកប្រវែងជ្រុង $c$ ។")
    req_3 = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Can you explain the final step in Khmer?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(problem_text=prob_text),
        client_board_version=resp_2.board_version,
    )
    resp_3 = answer_dynamic_followup(req_3, classification, session_id=session_id, llm_client=llm_f3)

    assert resp_3.metadata["board_update_mode"] == "append"
    assert resp_3.board_version == 4
    assert resp_3.base_board_version == 3

    action_ids_turn_3 = [a.id for a in resp_3.board_actions if a.type != VisualTutorCanvasActionType.STUDENT_TASK]
    # Check that Turn 3 contains ALL Turn 2 actions + ws-followup-reply-2
    for id_2 in action_ids_turn_2:
        assert id_2 in action_ids_turn_3
    assert "ws-followup-reply-0" in action_ids_turn_3
    assert "ws-followup-reply-1" in action_ids_turn_3
    assert "ws-followup-reply-2" in action_ids_turn_3

    # =========================================================================
    # Critical Flutter Invariant Verification:
    # `boardIdentityMustChange` in Flutter:
    # renderedActionIds.any((actionId) => !next.contains(actionId))
    # MUST BE FALSE for every transition!
    # =========================================================================
    def flutter_board_identity_must_change(rendered: list[str], incoming: list[str]) -> bool:
        incoming_set = set(incoming)
        return any(act_id not in incoming_set for act_id in rendered)

    assert not flutter_board_identity_must_change(action_ids_turn_0, action_ids_turn_1), "Turn 0 -> Turn 1 would trigger board replay!"
    assert not flutter_board_identity_must_change(action_ids_turn_1, action_ids_turn_2), "Turn 1 -> Turn 2 would trigger board replay!"
    assert not flutter_board_identity_must_change(action_ids_turn_2, action_ids_turn_3), "Turn 2 -> Turn 3 would trigger board replay!"


# ==============================================================================
# 6. Orchestrator End-to-End Integration & Equation Verifier Bypass
# ==============================================================================

def test_orchestrator_routes_followup_and_skips_equation_verifier():
    """Verify handle_visual_tutor_turn routes follow-up questions and skips verify_student_work."""
    prob_text = "In triangle ABC, a = 5, b = 7, and angle C = 60 degrees. Find side c."
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Why did we take the square root?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text=prob_text,
            board_version=1,
        ),
        client_board_version=1,
        metadata={"entry_context": "ask_question"},
    )

    llm = MockFollowupLLMClient("We take the square root because the formula gives c^2.")
    resp = handle_visual_tutor_turn(req, llm_client=llm)

    # 1. Check metadata contains board_update_mode: append
    assert resp.metadata.get("board_update_mode") == "append"
    assert resp.metadata.get("is_followup") is True

    # 2. Monotonically bumped board_version
    assert resp.board_version == 2
    assert resp.base_board_version == 1

    # 3. verify_student_work must be bypassed (conversational question is not an equation submission)
    # If verify_student_work ran, response.metadata["verification_result"] would be "invalid" or "error"
    assert resp.metadata.get("verification_result") is None
    assert resp.metadata.get("verification_verified") is None

    # 4. Whiteboard contains follow-up reply action
    action_ids = [a.id for a in resp.board_actions]
    assert any(act_id.startswith("ws-followup-reply-") for act_id in action_ids)
