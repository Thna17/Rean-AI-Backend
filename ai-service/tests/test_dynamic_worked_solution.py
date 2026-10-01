"""Tests for dynamic RAG curriculum gate and universal worked solution builder."""

from __future__ import annotations

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTeachingMode,
    VisualTutorTurnRequest,
    VisualTutorTurnState,
)
from api.services.visual_tutor.dynamic_worked_solution import (
    answer_dynamic_followup,
    build_dynamic_worked_solution_turn,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.rag_curriculum_gate import classify_student_query


def test_classify_tier_1_verified_limit():
    result = classify_student_query("Find the limit of (x^2 - 9)/(x - 3) as x approaches 3")
    assert result.is_in_scope is True
    assert result.is_verified is True
    assert result.subject in ("mathematics", "general_stem")


def test_classify_tier_1_verified_physics():
    result = classify_student_query("A car accelerates from rest at 2 m/s^2 for 10 seconds. Find its final velocity.")
    assert result.is_in_scope is True
    assert result.subject == "physics"


def test_classify_tier_1_verified_chemistry():
    result = classify_student_query("2H2 + O2 -> 2H2O. If we have 4 grams of H2, what is the mass of H2O produced?")
    assert result.is_in_scope is True
    assert result.subject == "chemistry"


def test_classify_tier_2_unverified_stem():
    result = classify_student_query("Find the eigenvalues of a 2x2 matrix [[1, 2], [3, 4]]")
    assert result.is_in_scope is True
    # Advanced STEM topic not in high school curriculum -> Tier 2 (Unverified AI Guidance)
    assert result.tier == "unverified"
    assert result.is_verified is False
    assert result.subject in ("mathematics", "general_stem")


def test_classify_tier_3_out_of_scope():
    result = classify_student_query("Who was George Washington?")
    assert result.tier == "out_of_scope"
    assert result.is_in_scope is False
    assert result.refusal_message_en is not None
    assert "Grade 10–12" in result.refusal_message_en


def test_classify_tier_3_out_of_scope_khmer():
    result = classify_student_query("តើអ្នកណាជាប្រធានាធិបតីអាមេរិកដំបូង?")
    assert result.tier == "out_of_scope"
    assert result.is_in_scope is False
    assert result.refusal_message_km is not None
    assert "ថ្នាក់ទី១០-១២" in result.refusal_message_km


def test_dynamic_worked_solution_limits():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Find the limit of (x^2 - 9)/(x - 3) as x approaches 3",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert len(res.board_actions) >= 4
    # Check that deterministic limit steps were produced
    texts = " ".join(a.text or a.latex or "" for a in res.board_actions)
    assert "6" in texts or "x + 3" in texts
    assert res.metadata.get("verified") is True
    assert res.metadata.get("verification", {}).get("verified") is True
    assert res.metadata.get("generation_path") == "deterministic_solver"
    assert res.metadata.get("curriculum_status") == "verified_curriculum"


def test_dynamic_worked_solution_unverified_stem():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Solve the quadratic equation x^2 - 5x + 6 = 0",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert len(res.board_actions) >= 3
    # Check that actions and student task were built
    assert res.student_task is not None
    assert res.metadata.get("worked_solution") is True


def test_dynamic_worked_solution_followup():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Why can we cancel x - 3?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text="Find the limit of (x^2 - 9)/(x - 3) as x approaches 3",
            board_version=1,
        ),
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    # Follow-up keeps original solution on board and appends a reply
    action_ids = [a.id for a in res.board_actions]
    assert any("reply" in a_id for a_id in action_ids)


def test_out_of_scope_rejection_turn():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="General",
        message="Tell me a recipe for cooking pizza",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    assert res.final_answer_locked is True
    assert "Grade 12" in res.spoken_text or "Grade 10–12" in res.spoken_text


def test_dynamic_worked_solution_physics_kinematics():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Kinematics",
        message="A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert res.metadata.get("worked_solution") is True
    assert res.metadata.get("verified") is True
    assert res.metadata.get("verification", {}).get("verified") is True
    assert res.metadata.get("generation_path") == "deterministic_solver"
    assert res.teaching_mode == VisualTutorTeachingMode.FULL_SOLUTION
    assert any("10" in (a.text or a.latex or "") for a in res.board_actions)


def test_dynamic_worked_solution_chemistry_stoichiometry():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Chemistry",
        topic="Stoichiometry",
        message="Given the reaction 2H2 + O2 -> 2H2O, how many moles of H2O are produced from 4.0 moles of H2?",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    res = handle_visual_tutor_turn(req)
    assert res.board is not None
    assert res.metadata.get("worked_solution") is True
    assert res.metadata.get("verified") is True
    assert res.metadata.get("verification", {}).get("verified") is True
    assert res.metadata.get("generation_path") == "deterministic_solver"
    assert res.teaching_mode == VisualTutorTeachingMode.FULL_SOLUTION
    assert any("4" in (a.text or a.latex or "") for a in res.board_actions)


def test_dynamic_worked_solution_deterministic_ids_contract():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Mathematics",
        message="Find lim x->3 (x^2 - 9)/(x - 3)",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )
    res = handle_visual_tutor_turn(req)
    actions = res.board_actions
    assert len(actions) > 0
    # All IDs must follow deterministic format
    for idx, a in enumerate(actions):
        assert a.sequence_index == idx
        assert a.id.startswith("ws-")
        assert a.duration_ms >= 0


def test_dynamic_worked_solution_honest_degradation_when_required():
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Electromagnetism",
        message="Calculate the magnetic field at the center of a circular loop carrying 5A current.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12, "require_verified_solver": True},
    )
    res = handle_visual_tutor_turn(req)
    assert res.metadata.get("generation_path") == "solver_not_ready"
    assert res.metadata.get("solver_ready") is False
    assert "not ready yet" in res.spoken_text.lower() or "មិនទាន់រួចរាល់" in res.spoken_text


def test_degraded_fallback_not_stored_in_dynamic_solution_cache():
    """Verify that transient LLM failures do not poison _dynamic_solution_cache with fallback solutions."""
    import json
    from api.services.visual_tutor.dynamic_worked_solution import (
        _dynamic_solution_cache,
        solve_dynamic_problem,
    )

    class FailingLLMClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("DeepSeek 503 Service Unavailable")

    class WorkingLLMClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            return json.dumps({
                "steps": [
                    {
                        "key": "solve",
                        "heading": "Step 1 · Solve Trigonometric Equation",
                        "explanation": "Solving sin(x) = 1/2 gives angles in Quadrant I and II: x = 30° and x = 150°.",
                        "latex": r"x = 30^\circ, 150^\circ",
                    }
                ],
                "answer_text": "x = 30° and x = 150°",
                "answer_latex": r"x = 30^\circ, \quad x = 150^\circ",
            })

    problem_query = "Solve sin(x) = 1/2 for 0 <= x <= 360 degrees"
    classification = classify_student_query(problem_query, grade=11, subject="Mathematics")
    req = VisualTutorTurnRequest(
        user_id="probe",
        subject="Mathematics",
        grade=11,
        message=problem_query,
        language_mode="english",
        action=VisualTutorAction.SUBMIT_PROBLEM,
    )

    _dynamic_solution_cache.clear()

    # 1. First call fails because LLM client raises
    turn1 = solve_dynamic_problem(
        req,
        classification,
        session_id="test-session-degraded-cache",
        llm_client=FailingLLMClient(),
    )
    assert turn1 is not None
    assert turn1.metadata["verified"] is False
    assert turn1.metadata["verification"]["verified"] is False
    assert turn1.metadata["generation_path"] == "dynamic_degraded_fallback"

    # The compact public envelope drives the student's verification badge.  A
    # structured fallback still contains board steps, but those steps are only
    # an explanatory placeholder and must never make the UI claim that a
    # deterministic solver verified the answer.
    from api.services.visual_tutor.public_response import project_public_tutor_turn

    public_turn = project_public_tutor_turn(turn1)
    assert public_turn["verification"]["verified"] is False
    assert public_turn["verification"]["status"] == "cannot_verify"

    # BUT the degraded fallback solution must NOT be stored in the cache
    cache_key = f"{problem_query}:False:{classification.is_verified}"
    assert cache_key not in _dynamic_solution_cache
    assert len(_dynamic_solution_cache) == 0

    # 2. Second call with a working LLM client must return the real solution, NOT the poisoned fallback
    turn2 = solve_dynamic_problem(
        req,
        classification,
        session_id="test-session-degraded-cache",
        llm_client=WorkingLLMClient(),
    )
    assert turn2 is not None
    assert any("30" in (a.text or a.latex or "") for a in turn2.board_actions)
    assert not any("Solution completed" in (a.text or "") for a in turn2.board_actions)
    assert turn2.metadata["verified"] is False
    assert turn2.metadata["verification"]["verified"] is False
    assert turn2.metadata["generation_path"] == "dynamic_llm"
    assert project_public_tutor_turn(turn2)["verification"] == {
        "status": "cannot_verify",
        "verified": False,
        "concise_evidence": "AI unverified",
        "student_facing_feedback": "AI answer — not machine-checked.",
    }

    # A real, non-degraded solution may be cached, but remains explicitly
    # unverified because it came from the LLM rather than a deterministic solver.
    assert cache_key in _dynamic_solution_cache


def test_degraded_fallback_not_stored_in_followup_reconstruction():
    """Verify that call site 2 (answer_dynamic_followup) does not cache degraded fallback solutions."""
    from api.services.visual_tutor.dynamic_worked_solution import (
        _dynamic_solution_cache,
        answer_dynamic_followup,
    )

    class FailingLLMClient:
        def complete(self, *, system_prompt: str, user_prompt: str) -> str:
            raise RuntimeError("DeepSeek 500 Internal Error")

    problem_query = "Calculate enthalpy change Delta H for reaction A -> B"
    classification = classify_student_query(problem_query, grade=11, subject="Chemistry")
    req = VisualTutorTurnRequest(
        user_id="probe-followup",
        subject="Chemistry",
        grade=11,
        message="Why is Delta H negative?",
        language_mode="english",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state=VisualTutorTurnState(
            problem_text=problem_query,
            board_version=1,
        ),
    )

    _dynamic_solution_cache.clear()

    turn = answer_dynamic_followup(
        req,
        classification,
        session_id="test-session-followup-degraded",
        llm_client=FailingLLMClient(),
    )
    assert turn is not None

    # Verify that neither language key was stored in _dynamic_solution_cache
    for lang in (True, False):
        key = f"{problem_query}:{lang}:{classification.is_verified}"
        assert key not in _dynamic_solution_cache
    assert len(_dynamic_solution_cache) == 0


def test_ttl_cache_lru_and_expiration():
    """Test TTLCache bounded capacity, LRU eviction order, and TTL expiry."""
    import time
    from api.services.visual_tutor.dynamic_worked_solution import TTLCache

    # 1. Bounded LRU Eviction
    cache: TTLCache[str, int] = TTLCache(maxsize=3, ttl_seconds=60.0)
    cache["a"] = 1
    cache["b"] = 2
    cache["c"] = 3
    assert len(cache) == 3

    # Touch 'a' so 'b' becomes least recently used
    _ = cache["a"]

    # Insert 'd' -> should evict 'b'
    cache["d"] = 4
    assert len(cache) == 3
    assert "b" not in cache
    assert "a" in cache
    assert "c" in cache
    assert "d" in cache
    assert cache.get("b") is None

    # 2. TTL Expiration
    short_cache: TTLCache[str, str] = TTLCache(maxsize=10, ttl_seconds=0.05)
    short_cache["key1"] = "val1"
    assert "key1" in short_cache
    assert short_cache["key1"] == "val1"

    time.sleep(0.08)
    assert "key1" not in short_cache
    assert short_cache.get("key1") is None
    assert len(short_cache) == 0


def test_session_followups_bounded_eviction():
    """Test that _session_followups is bounded and evicts older sessions."""
    from api.services.visual_tutor.dynamic_worked_solution import (
        GenericSolutionStep,
        _session_followups,
    )

    _session_followups.clear()
    assert len(_session_followups) == 0

    # Insert items up to capacity and beyond
    original_maxsize = _session_followups.maxsize
    try:
        _session_followups.maxsize = 5
        for i in range(7):
            _session_followups[f"session_{i}"] = [
                GenericSolutionStep(key=f"s_{i}", heading=f"Heading {i}", explanation=f"Exp {i}")
            ]

        assert len(_session_followups) == 5
        # Oldest sessions 0 and 1 should have been evicted
        assert "session_0" not in _session_followups
        assert "session_1" not in _session_followups
        assert "session_6" in _session_followups
    finally:
        _session_followups.maxsize = original_maxsize
        _session_followups.clear()


def test_generic_worked_solution_is_degraded_flag():
    """Test is_degraded flag defaults to False and is set True on fallback solutions."""
    from api.services.visual_tutor.dynamic_worked_solution import (
        GenericWorkedSolution,
        _build_fallback_solution,
    )
    from api.services.visual_tutor.rag_curriculum_gate import ClassificationResult

    normal_sol = GenericWorkedSolution(
        problem_text="Test",
        steps=[],
        answer_text="Ans",
        answer_latex="Ans",
        is_verified=True,
    )
    assert normal_sol.is_degraded is False

    classification = ClassificationResult(
        tier="unverified",
        subject="mathematics",
    )
    fallback = _build_fallback_solution(
        "Unsolvable problem",
        is_khmer=False,
        classification=classification,
    )
    assert fallback.is_degraded is True
    assert fallback.answer_text == "Solution completed"

    # Curriculum matching is not mathematical verification.  When DeepSeek is
    # unavailable, even a curriculum-matched problem receives only the generic
    # explanatory fallback and therefore cannot inherit the classification's
    # verified flag.
    curriculum_matched = ClassificationResult(
        tier="verified",
        subject="mathematics",
    )
    matched_fallback = _build_fallback_solution(
        "Solve sin(x) = 1/2",
        is_khmer=False,
        classification=curriculum_matched,
    )
    assert matched_fallback.is_degraded is True
    assert matched_fallback.is_verified is False
    assert matched_fallback.generation_path == "dynamic_degraded_fallback"


def test_dynamic_solution_cache_bounded_size_and_ttl():
    """Test that _dynamic_solution_cache bounds memory (maxsize) and evicts on TTL expiry."""
    import time
    from api.services.visual_tutor.dynamic_worked_solution import (
        GenericWorkedSolution,
        _dynamic_solution_cache,
    )

    _dynamic_solution_cache.clear()
    orig_max = _dynamic_solution_cache.maxsize
    orig_ttl = _dynamic_solution_cache.ttl_seconds
    try:
        # 1. Bounded size eviction
        _dynamic_solution_cache.maxsize = 3
        _dynamic_solution_cache.ttl_seconds = 60.0

        for i in range(5):
            _dynamic_solution_cache[f"prob_{i}"] = GenericWorkedSolution(
                problem_text=f"prob_{i}",
                steps=[],
                answer_text=f"ans_{i}",
                answer_latex=f"ans_{i}",
                is_verified=True,
            )

        assert len(_dynamic_solution_cache) == 3
        assert "prob_0" not in _dynamic_solution_cache
        assert "prob_1" not in _dynamic_solution_cache
        assert "prob_4" in _dynamic_solution_cache

        # 2. TTL expiration
        _dynamic_solution_cache.clear()
        _dynamic_solution_cache.ttl_seconds = 0.05
        _dynamic_solution_cache["prob_short"] = GenericWorkedSolution(
            problem_text="short",
            steps=[],
            answer_text="short",
            answer_latex="short",
            is_verified=True,
        )
        assert "prob_short" in _dynamic_solution_cache
        time.sleep(0.08)
        assert "prob_short" not in _dynamic_solution_cache
        assert len(_dynamic_solution_cache) == 0
    finally:
        _dynamic_solution_cache.maxsize = orig_max
        _dynamic_solution_cache.ttl_seconds = orig_ttl
        _dynamic_solution_cache.clear()
