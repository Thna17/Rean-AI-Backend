"""Tests for Grade 12 Physics: Kinematics (Constant Acceleration).

Verifies:
1. 8 distinct 1D constant acceleration kinematics problem shapes.
2. Explicit unit carrying and unit validation (missing or wrong units fail).
3. SymPy-grounded deterministic solving (numbers decided by physics, not LLM).
4. Board actions have deterministic IDs and valid schemas (SHOW_TABLE, DRAW_FREE_BODY_DIAGRAM, etc.).
5. Follow-up questions about individual steps are answered accurately.
6. Khmer language phrasing parsing and bilingual handling.
7. Unsupported physics problems (e.g. 2D projectile motion) degrade honestly to solver_not_ready.
"""

import pytest

from api.models.visual_tutor import (
    VisualTutorAction,
    VisualTutorTurnRequest,
)
from api.services.visual_tutor.orchestrator import handle_visual_tutor_turn
from api.services.visual_tutor.physics_kinematics import (
    parse_physics_kinematics_problem,
    solve_kinematics,
    verify_kinematics_answer,
    match_physics_kinematics_problem,
    build_physics_worked_solution_turn,
    match_physics_kinematics_followup,
    answer_about_physics_solution,
)


@pytest.fixture(autouse=True)
def _scope_lock_grade12_stem(monkeypatch):
    """Enable the Grade 12 STEM scope lock for these tests."""
    from api.core.config import settings

    monkeypatch.setattr(settings, "VISUAL_TUTOR_SCOPE_LOCK", "grade12_stem")


# ==============================================================================
# 1. 8 Distinct Kinematics Problem Shapes
# ==============================================================================


def test_shape_1_acceleration_from_rest_find_velocity() -> None:
    """Shape 1: u = 0, a = 2 m/s^2, t = 5 s -> v = 10 m/s."""
    text = "A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity."
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 0.0
    assert problem.knowns["a"] == 2.0
    assert problem.knowns["t"] == 5.0
    assert problem.target == "v"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(10.0)
    assert solution.target_unit == "m/s"
    assert "v = 10" in solution.answer_text or "10 m/s" in solution.answer_text
    assert "v = u + a t" in solution.formula_latex or "v = u + at" in solution.formula_latex


def test_shape_2_acceleration_from_rest_find_distance() -> None:
    """Shape 2: u = 0, a = 3 m/s^2, t = 4 s -> s = 24 m."""
    text = "A vehicle starts from rest and accelerates at 3 m/s^2 for 4 seconds. How far does it travel?"
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 0.0
    assert problem.knowns["a"] == 3.0
    assert problem.knowns["t"] == 4.0
    assert problem.target == "s"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(24.0)
    assert solution.target_unit == "m"
    assert "24" in solution.answer_text


def test_shape_3_braking_find_stopping_distance() -> None:
    """Shape 3: u = 20 m/s, v = 0, a = -5 m/s^2 (deceleration 5 m/s^2) -> s = 40 m."""
    text = "A car traveling at 20 m/s brakes with a deceleration of 5 m/s^2 until it stops. Find the stopping distance."
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 20.0
    assert problem.knowns["v"] == 0.0
    assert problem.knowns["a"] == -5.0
    assert problem.target == "s"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(40.0)
    assert solution.target_unit == "m"
    assert "40" in solution.answer_text


def test_shape_4_braking_find_stopping_time() -> None:
    """Shape 4: u = 30 m/s, v = 0, a = -6 m/s^2 -> t = 5 s."""
    text = "A train moving at 30 m/s decelerates at 6 m/s^2 to a complete stop. How long does it take to stop?"
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 30.0
    assert problem.knowns["v"] == 0.0
    assert problem.knowns["a"] == -6.0
    assert problem.target == "t"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(5.0)
    assert solution.target_unit == "s"
    assert "5" in solution.answer_text


def test_shape_5_free_fall_find_velocity() -> None:
    """Shape 5: dropped from rest (u = 0), a = 9.8 m/s^2, t = 3 s -> v = 29.4 m/s."""
    text = "A stone is dropped from rest from a cliff and falls for 3 seconds. What is its velocity before impact? (g = 9.8 m/s^2)"
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 0.0
    assert problem.knowns["t"] == 3.0
    assert problem.knowns["a"] == 9.8
    assert problem.target == "v"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(29.4)
    assert solution.target_unit == "m/s"


def test_shape_6_free_fall_find_height() -> None:
    """Shape 6: dropped from rest (u = 0), a = 9.8 m/s^2, t = 2 s -> s = 19.6 m."""
    text = "An object is dropped from a bridge and hits the water after 2 seconds. How high is the bridge? (g = 9.8 m/s^2)"
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 0.0
    assert problem.knowns["t"] == 2.0
    assert problem.knowns["a"] == 9.8
    assert problem.target == "s"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(19.6)
    assert solution.target_unit == "m"


def test_shape_7_vertical_upward_find_max_height() -> None:
    """Shape 7: u = 14 m/s, at max height v = 0, a = -9.8 m/s^2 -> s = 10 m."""
    text = "A ball is thrown vertically upward with an initial speed of 14 m/s. Find the maximum height reached. (g = 9.8 m/s^2)"
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 14.0
    assert problem.knowns["v"] == 0.0
    assert problem.knowns["a"] == -9.8
    assert problem.target == "s"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(10.0)
    assert solution.target_unit == "m"


def test_shape_8_vertical_upward_find_time_to_peak() -> None:
    """Shape 8: u = 19.6 m/s, at max height v = 0, a = -9.8 m/s^2 -> t = 2 s."""
    text = "A ball is projected upwards with an initial velocity of 19.6 m/s. How long does it take to reach its highest point? (g = 9.8 m/s^2)"
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 19.6
    assert problem.knowns["v"] == 0.0
    assert problem.knowns["a"] == -9.8
    assert problem.target == "t"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(2.0)
    assert solution.target_unit == "s"


# ==============================================================================
# 2. Khmer Language Problem Phrasing
# ==============================================================================


def test_khmer_kinematics_problem_parsing() -> None:
    """Khmer phrasing for acceleration from rest."""
    text = "ឡានមួយចាប់ផ្តើមចេញពីភាពស្ងៀមស្ងាត់ (u = 0) ដោយសំទុះ a = 2 m/s^2 ក្នុងរយៈពេល t = 5 s។ រកល្បឿនចុងក្រោយ v?"
    problem = parse_physics_kinematics_problem(text)
    assert problem is not None
    assert problem.knowns["u"] == 0.0
    assert problem.knowns["a"] == 2.0
    assert problem.knowns["t"] == 5.0
    assert problem.target == "v"

    solution = solve_kinematics(problem)
    assert solution.target_value == pytest.approx(10.0)
    assert solution.target_unit == "m/s"


# ==============================================================================
# 3. Unit Enforcement: A physics answer is wrong if the unit is wrong
# ==============================================================================


def test_unit_enforcement_correct() -> None:
    valid, msg = verify_kinematics_answer("10 m/s", expected_value=10.0, expected_unit="m/s")
    assert valid is True
    assert "correct" in msg.lower()


def test_unit_enforcement_missing_unit_fails() -> None:
    valid, msg = verify_kinematics_answer("10", expected_value=10.0, expected_unit="m/s")
    assert valid is False
    assert "missing" in msg.lower() or "unit" in msg.lower()


def test_unit_enforcement_wrong_unit_fails() -> None:
    valid, msg = verify_kinematics_answer("10 m", expected_value=10.0, expected_unit="m/s")
    assert valid is False
    assert "unit" in msg.lower()

    valid2, msg2 = verify_kinematics_answer("10 m/s^2", expected_value=10.0, expected_unit="m/s")
    assert valid2 is False
    assert "unit" in msg2.lower()


def test_unit_enforcement_wrong_value_fails() -> None:
    valid, msg = verify_kinematics_answer("15 m/s", expected_value=10.0, expected_unit="m/s")
    assert valid is False
    assert "value" in msg.lower() or "expected 10" in msg.lower()


# ==============================================================================
# 4. Deterministic Board Actions and Contract Validation
# ==============================================================================


def test_board_action_deterministic_ids_and_primitives() -> None:
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Kinematics",
        message="A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity.",
        action=VisualTutorAction.SUBMIT_PROBLEM,
        metadata={"grade": 12},
    )
    problem = parse_physics_kinematics_problem(req.message or "")
    assert problem is not None

    response = build_physics_worked_solution_turn(req, problem, session_id="test-session")
    assert response is not None
    assert response.teaching_mode.value == "full_solution"

    # Action IDs must be deterministic: ws-physics-step-...
    action_ids = [a.id for a in response.board_actions]
    assert any("ws-physics-step-givens" in aid for aid in action_ids)
    assert any("ws-physics-step-diagram" in aid for aid in action_ids)
    assert any("ws-physics-step-formula" in aid for aid in action_ids)
    assert any("ws-physics-step-calc" in aid for aid in action_ids)
    assert any("ws-physics-answer" in aid for aid in action_ids)
    assert any("ws-physics-next" in aid for aid in action_ids)

    # Primitives: show_table and draw_free_body_diagram present
    action_types = [a.type.value for a in response.board_actions]
    assert "show_table" in action_types
    assert "draw_free_body_diagram" in action_types
    assert "write_equation" in action_types
    assert "write_text" in action_types
    assert "student_task" in action_types


# ==============================================================================
# 5. Follow-Up Questions Grounded in Steps
# ==============================================================================


def test_followup_question_about_step() -> None:
    problem_text = "A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity."
    problem = parse_physics_kinematics_problem(problem_text)
    assert problem is not None

    # Follow-up question: why is u = 0?
    req = VisualTutorTurnRequest(
        user_id="student-1",
        subject="Physics",
        topic="Kinematics",
        message="Why is u equal to 0?",
        action=VisualTutorAction.SUBMIT_STEP,
        current_state={"problem_text": problem_text},
        metadata={"grade": 12, "board_action_id": "ws-physics-step-givens-0"},
    )

    match = match_physics_kinematics_followup(req)
    assert match is not None

    response = answer_about_physics_solution(req, match, session_id="test-session")
    assert response is not None
    # Explanation should mention 'rest'
    assert "rest" in response.spoken_text.lower() or "0" in response.spoken_text
    # Board actions still contain the full solution + reply step
    action_ids = [a.id for a in response.board_actions]
    assert any("reply" in aid for aid in action_ids)


# ==============================================================================
# 6. End-to-End Orchestrator Dispatch & Honest Degradation
# ==============================================================================


def test_orchestrator_dispatches_kinematics_to_worked_solution() -> None:
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Physics",
            topic="Kinematics",
            message="A car starts from rest and accelerates at 2 m/s^2 for 5 seconds. Find its final velocity.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )

    assert response.metadata.get("worked_solution") is True
    assert any("ws-physics" in a.id for a in response.board_actions)
    assert "10 m/s" in response.spoken_text or "10" in response.spoken_text


def test_unsupported_physics_problem_degrades_honestly() -> None:
    """2D projectile motion with require_verified_solver must degrade honestly to solver_not_ready."""
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Physics",
            topic="Projectile Motion",
            message="A cannonball is launched at an angle of 45 degrees with velocity 50 m/s. Find its horizontal range.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12, "require_verified_solver": True},
        )
    )

    assert response.metadata.get("fallback_reason") != "out_of_scope_lock"
    assert response.metadata.get("generation_path") == "solver_not_ready"
    assert response.metadata.get("solver_ready") is False
    assert "not ready yet" in response.spoken_text.lower() or "មិនទាន់រួចរាល់" in response.spoken_text


def test_unsupported_physics_problem_dynamic_unverified() -> None:
    """Without require_verified_solver, 2D projectile motion is answered dynamically as unverified."""
    response = handle_visual_tutor_turn(
        VisualTutorTurnRequest(
            user_id="student-1",
            subject="Physics",
            topic="Projectile Motion",
            message="A cannonball is launched at an angle of 45 degrees with velocity 50 m/s. Find its horizontal range.",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={"grade": 12},
        )
    )
    assert response.metadata.get("verified") is False
    assert response.metadata.get("curriculum_status") == "ai_unverified"
