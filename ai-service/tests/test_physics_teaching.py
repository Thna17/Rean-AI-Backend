import pytest

from api.models.curriculum_cambodia import RichProblem
from api.services.subject_experts.physics_expert import PhysicsExpert


def physics_problem(text: str, kind: str = "force") -> RichProblem:
    return RichProblem(problem_id="physics_g10_teaching", subject="physics", grade=10, unit="Dynamics", topic_id="physics_g10_dynamics_01", problem_text=text, problem_text_khmer="លំហាត់រូបវិទ្យា", problem_type=kind, visualizations_needed=["free_body_diagram", "graph"], concepts=["force"])


@pytest.mark.asyncio
async def test_force_problem_analysis_identifies_values_forces_and_law() -> None:
    analysis = await PhysicsExpert().analyze_problem(physics_problem("A 5kg box is pushed with 20N force"))
    assert analysis["scenario_type"] == "force"
    assert analysis["given_values"] == {"mass_kg": 5.0, "force_n": 20.0}
    assert "applied" in analysis["forces"]
    assert "F_net = ma" in analysis["applicable_laws"][0]


@pytest.mark.asyncio
async def test_motion_problem_analysis_identifies_kinematics_laws() -> None:
    analysis = await PhysicsExpert().analyze_problem(physics_problem("Car accelerates from 0 to 20 m/s in 5 seconds", "motion"))
    assert analysis["scenario_type"] == "motion"
    assert analysis["applicable_laws"] == ["v = u + at", "x = ut + ½at²"]


@pytest.mark.asyncio
async def test_teaching_plan_follows_six_stage_physics_pattern() -> None:
    plan = await PhysicsExpert().create_visualization_plan(physics_problem("A 5kg car is pushed with 20N force"))
    assert [step.step_id.rsplit("_", 1)[-1] for step in plan.visualization_steps] == ["scenario", "fbd", "force", "newton", "graphs", "interpret"]
    assert all(step.student_question and step.student_question_khmer for step in plan.visualization_steps)
    assert plan.visualization_steps[1].content["renderer"] == "VectorRenderer"
    assert plan.visualization_steps[4].content["renderer"] == "GraphRenderer"


@pytest.mark.asyncio
async def test_physics_evaluation_and_misconception_detection() -> None:
    expert = PhysicsExpert()
    assert (await expert.evaluate_student_response("9.8 m/s²", "step", "10 m/s²", "numeric")).is_correct
    misconception = await expert.detect_misconception("A heavier object falls faster", "", "step")
    assert misconception and misconception["misconception_type"] == "heavier_falls_faster"
