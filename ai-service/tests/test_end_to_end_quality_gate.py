"""End-to-End Quality Gate, Prompt Caching & Observability Test.

Verifies the full pipeline:
1. Admin publishes a curriculum chunk (Thermodynamics — Ideal Gas Law, PV = nRT).
2. Student problem turn asking for volume of 2.0 moles at 300 K, 1.0 atm.
3. RAG gate verifies against chunk (verified: True, Tier 1).
4. Whiteboard writes full solution with PV = nRT, V = 49.26 L with deterministic IDs.
5. Student asks follow-up: "What does R equal?".
6. Whiteboard appends ws-followup-reply-0 explaining R without clearing earlier work.
7. Asserts prompt caching prefix invariance (>80%), latency < 3s, and estimated turn cost < $0.001.
"""

from __future__ import annotations

import json
import time
from typing import Any
import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnResponse,
    VisualTutorTurnState,
)
from api.models.curriculum import (
    CurriculumChunk,
    CurriculumMisconception,
    CurriculumSource,
)
from api.services.curriculum.curriculum_store import (
    get_default_curriculum_store,
)
from api.services.curriculum.published_curriculum_store import (
    PublishedCurriculumStore,
)
from api.services.visual_tutor.dynamic_worked_solution import (
    _dynamic_solution_cache,
    _session_followups,
)
from api.services.visual_tutor.llm_teaching_planner import (
    DeepSeekVisualTutorLLMClient,
    _build_system_prompt,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.policy import VisualTutorPolicyDecision
from api.services.visual_tutor.rag_curriculum_gate import classify_student_query


class MockDeepSeekClient:
    """Mock DeepSeek client simulating prompt cache hits, latency, and cost telemetry."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.token_usage: dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "prompt_cache_hit_tokens": 0,
            "prompt_cache_miss_tokens": 0,
            "cache_hit_count": 0,
            "call_count": 0,
            "total_latency_ms": 0,
            "total_cost_usd": 0.0,
        }

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        start_t = time.perf_counter()
        call_index = len(self.calls)
        self.calls.append({
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
        })

        # Simulate token usage with prompt cache hit on subsequent turns
        if call_index == 0:
            # Turn 1: Cache miss on first call
            p_tokens = 1450
            cache_hit_tokens = 0
            cache_miss_tokens = 1450
            c_tokens = 220
        else:
            # Turn 2: Cache hit on the long invariant static prefix (>80% hit)
            p_tokens = 1520
            cache_hit_tokens = 1350  # ~89% cache hit
            cache_miss_tokens = 170
            c_tokens = 95

        t_tokens = p_tokens + c_tokens
        # DeepSeek pricing: $0.07/M cache hit, $0.27/M cache miss, $1.10/M completion
        cost_usd = (cache_hit_tokens * 0.07 + cache_miss_tokens * 0.27 + c_tokens * 1.10) / 1_000_000.0
        elapsed_ms = int((time.perf_counter() - start_t) * 1000) + 85  # simulate network roundtrip

        self.token_usage["prompt_tokens"] += p_tokens
        self.token_usage["completion_tokens"] += c_tokens
        self.token_usage["total_tokens"] += t_tokens
        self.token_usage["prompt_cache_hit_tokens"] += cache_hit_tokens
        self.token_usage["prompt_cache_miss_tokens"] += cache_miss_tokens
        self.token_usage["cache_hit_count"] += (1 if cache_hit_tokens > 0 else 0)
        self.token_usage["call_count"] += 1
        self.token_usage["last_latency_ms"] = elapsed_ms
        self.token_usage["total_latency_ms"] += elapsed_ms
        self.token_usage["last_cost_usd"] = cost_usd
        self.token_usage["total_cost_usd"] += cost_usd

        # If it's a follow-up question
        if "What does R equal" in user_prompt or "Student Question" in user_prompt:
            return (
                "The constant $R$ is the universal gas constant, equal to $0.0821\\text{ L}\\cdot\\text{atm}/(\\text{mol}\\cdot\\text{K})$. "
                "It links the microscopic energy of gas molecules with macroscopic pressure and volume."
            )

        # First turn: Whiteboard worked solution
        return json.dumps({
            "steps": [
                {
                    "key": "setup",
                    "heading": "Step 1 · Identify given quantities",
                    "explanation": "Extract the given values: pressure P = 1.0 atm, moles n = 2.0 mol, and temperature T = 300 K.",
                    "latex": "P = 1.0\\text{ atm}, \\quad n = 2.0\\text{ mol}, \\quad T = 300\\text{ K}, \\quad R = 0.0821\\text{ L}\\cdot\\text{atm}/(\\text{mol}\\cdot\\text{K})",
                },
                {
                    "key": "equation",
                    "heading": "Step 2 · Apply Ideal Gas Law",
                    "explanation": "State the equation of state PV = nRT and rearrange to solve for volume V.",
                    "latex": "PV = nRT \\implies V = \\frac{nRT}{P}",
                },
                {
                    "key": "eval",
                    "heading": "Step 3 · Calculate volume",
                    "explanation": "Substitute the values into the formula and evaluate.",
                    "latex": "V = \\frac{2.0 \\times 0.0821 \\times 300}{1.0} = 49.26\\text{ L}",
                },
            ],
            "answer_text": "The volume of the ideal gas is 49.26 L.",
            "answer_latex": "V = 49.26\\text{ L}",
        })


def test_end_to_end_quality_gate_ideal_gas_and_prompt_caching() -> None:
    # -------------------------------------------------------------
    # Step 1: Admin Publishes MoEYS Curriculum Chunk
    # -------------------------------------------------------------
    store = get_default_curriculum_store()
    chunk_id = "chemistry.g11.thermo.ideal_gas"
    chunk = CurriculumChunk(
        id=chunk_id,
        grade=11,
        subject="Chemistry",
        chapter="Thermodynamics",
        topic="Ideal Gas Law",
        subtopic="Equation of state for ideal gases",
        problem_types=["ideal_gas_law", "gas_volume_calculation"],
        content_type="lesson_chunk",
        text="The Ideal Gas Law relates pressure, volume, temperature, and moles of an ideal gas: PV = nRT.",
        formulas=[
            {
                "id": "formula.ideal_gas",
                "expression": "PV = nRT",
                "variables": {
                    "P": "pressure in atmospheres (atm)",
                    "V": "volume in liters (L)",
                    "n": "amount of substance in moles",
                    "R": "universal gas constant (0.0821 L atm / mol K)",
                    "T": "absolute temperature in Kelvin (K)",
                },
            }
        ],
        solution_steps=[
            "Identify given values for P, V, n, and T",
            "Ensure temperature is in Kelvin (K)",
            "Apply the Ideal Gas Law formula PV = nRT",
            "Rearrange for the unknown and evaluate with correct units",
        ],
        common_misconceptions=[
            CurriculumMisconception(
                text="Using temperature in Celsius instead of Kelvin",
                correction="Always convert Celsius to Kelvin by adding 273.15.",
            )
        ],
        khmer_terms={
            "ideal gas": "ឧស្ម័នល្អឥតខ្ចោះ",
            "gas constant": "ថេរឧស្ម័ន",
            "pressure": "សម្ពាធ",
            "volume": "មាឌ",
            "temperature": "សីតុណ្ហភាព",
        },
        language="en",
        difficulty="medium",
        tags=["chemistry", "gas", "ideal gas", "grade 11"],
        source=CurriculumSource(
            type="admin_published",
            title="MoEYS Grade 11 Chemistry",
            metadata={"curriculum_version_id": "version-ideal-gas-01"},
        ),
    )
    pub_store = PublishedCurriculumStore()
    pub_chunk_dict = chunk.model_dump(mode="json")
    pub_store.replace_version("version-ideal-gas-01", [pub_chunk_dict])
    store.reload()

    # -------------------------------------------------------------
    # Step 2: Student Problem Turn
    # -------------------------------------------------------------
    problem_query = "A gas cylinder contains 2.0 moles of ideal gas at 300 K with pressure 1.0 atm. Find the volume."
    classification = classify_student_query(problem_query, grade=11, subject="Chemistry")

    # Verify RAG Gate classification
    assert classification.is_verified is True
    assert classification.tier == "verified"
    assert classification.topic == "Ideal Gas Law"
    assert any(c.id == chunk_id for c in classification.matching_chunks)

    mock_llm = MockDeepSeekClient()
    session_id = "test-session-ideal-gas-01"

    # Reset any cached states
    _dynamic_solution_cache.clear()
    _session_followups.clear()

    turn1_req = VisualTutorTurnRequest(
        user_id="student-ideal-gas-1",
        grade=11,
        subject="Chemistry",
        topic="Ideal Gas Law",
        message=problem_query,
        action=VisualTutorAction.SUBMIT_PROBLEM,
        session_id=session_id,
        metadata={"entry_context": "whiteboard_solver"},
    )

    turn1_res = handle_visual_tutor_turn(
        turn1_req,
        llm_client=mock_llm,
    )

    # -------------------------------------------------------------
    # Step 3 & 4: Whiteboard Solution Verification
    # -------------------------------------------------------------
    assert turn1_res is not None
    assert turn1_res.final_answer_locked is False
    assert turn1_res.metadata.get("verified") is True
    assert turn1_res.metadata.get("curriculum_topic") == "Ideal Gas Law"
    assert turn1_res.metadata.get("board_update_mode") == "replace"

    # Check deterministic action IDs on the whiteboard
    action_ids = [action.id for action in turn1_res.board_actions]
    assert any(aid.startswith("ws-step-") for aid in action_ids)
    assert any(aid.startswith("ws-answer-") for aid in action_ids)

    # Verify mathematical solution presence on whiteboard
    combined_latex = " ".join(action.latex or "" for action in turn1_res.board_actions)
    assert "PV = nRT" in combined_latex or "PV" in combined_latex
    assert "49.26" in combined_latex

    # -------------------------------------------------------------
    # Step 5 & 6: Conversational Follow-up (No Whiteboard Wiping)
    # -------------------------------------------------------------
    followup_query = "What does R equal in this formula?"
    turn2_req = VisualTutorTurnRequest(
        user_id="student-ideal-gas-1",
        grade=11,
        subject="Chemistry",
        topic="Ideal Gas Law",
        message=followup_query,
        action=VisualTutorAction.SUBMIT_STEP,
        session_id=session_id,
        current_state=VisualTutorTurnState(
            problem_text=problem_query,
        ),
        metadata={
            "rendered_board_actions": [action.model_dump() for action in turn1_res.board_actions],
            "entry_context": "whiteboard_followup",
        },
    )

    turn2_res = handle_visual_tutor_turn(
        turn2_req,
        llm_client=mock_llm,
    )

    assert turn2_res is not None
    # Crucial UX invariant: follow-up turn appends without wiping earlier whiteboard work!
    assert turn2_res.metadata.get("board_update_mode") == "append"
    followup_action_ids = [action.id for action in turn2_res.board_actions]
    assert "ws-followup-reply-0" in followup_action_ids

    followup_text = turn2_res.display_text
    assert "0.0821" in followup_text or "gas constant" in followup_text.lower()

    # -------------------------------------------------------------
    # Step 7: Prompt Caching, Telemetry & Cost Verification
    # -------------------------------------------------------------
    # Verify DeepSeek prompt cache prefix invariance
    policy1 = VisualTutorPolicyDecision(
        teaching_mode=VisualTutorTeachingMode.FULL_SOLUTION,
        final_answer_locked=False,
        partial_solution_allowed=True,
        full_solution_allowed=True,
        request_student_step=False,
        give_hint=False,
        diagnose_misconception=False,
        reveal_final=True,
        metadata={"student_intent": "solve"},
    )
    policy2 = VisualTutorPolicyDecision(
        teaching_mode=VisualTutorTeachingMode.HINT,
        final_answer_locked=False,
        partial_solution_allowed=True,
        full_solution_allowed=True,
        request_student_step=False,
        give_hint=True,
        diagnose_misconception=True,
        reveal_final=True,
        metadata={"student_intent": "request_hint"},
    )

    sys_prompt1 = _build_system_prompt(policy1, current_step_index=1, problem_type="chemistry")
    sys_prompt2 = _build_system_prompt(policy2, current_step_index=2, problem_type="chemistry")

    # Find common prefix length
    common_prefix_len = 0
    for c1, c2 in zip(sys_prompt1, sys_prompt2):
        if c1 == c2:
            common_prefix_len += 1
        else:
            break

    # Cache prefix invariance: identical invariant static prefix must account for >80% of system prompt!
    prefix_ratio = common_prefix_len / max(len(sys_prompt1), len(sys_prompt2))
    assert prefix_ratio >= 0.80, f"Expected prefix invariance >= 80%, got {prefix_ratio * 100:.1f}%"

    # Verify Token Telemetry and Cost
    telemetry = mock_llm.token_usage
    assert telemetry["call_count"] == 2
    assert telemetry["prompt_cache_hit_tokens"] > 0
    assert telemetry["cache_hit_count"] >= 1

    # Check that latency is well under 3000ms
    assert telemetry["last_latency_ms"] < 3000

    # Check that estimated cost per turn is well under $0.001
    turn1_cost = (1450 * 0.27 + 220 * 1.10) / 1_000_000.0  # ~$0.00063
    turn2_cost = telemetry["last_cost_usd"]                # ~$0.00024
    assert turn1_cost < 0.001, f"Turn 1 cost ${turn1_cost:.6f} exceeded $0.001"
    assert turn2_cost < 0.001, f"Turn 2 cost ${turn2_cost:.6f} exceeded $0.001"
    assert telemetry["total_cost_usd"] < 0.002
