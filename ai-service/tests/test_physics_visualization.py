import math

import pytest

from api.services.subject_experts.physics_expert import PhysicsExpert


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", [
    "A 5kg box on an incline at 30°, pushed with 20N force",
    "A 2kg block on a rough surface",
    "A 10kg mass hangs from a rope",
    "A 1kg box is pulled across a surface with friction",
    "វត្ថុមានទម្ងន់លើផ្ទៃទំនោរ",
])
async def test_fbd_uses_vector_renderer_and_coordinate_metadata(scenario: str) -> None:
    diagram = await PhysicsExpert().create_free_body_diagram(scenario)
    assert diagram["renderer"] == "VectorRenderer"
    assert diagram["coordinate_system"]["x_axis"]
    assert diagram["forces"]
    assert all("visualization" in force for force in diagram["forces"])


@pytest.mark.asyncio
async def test_motion_graphs_describe_constant_acceleration_relationships() -> None:
    graphs = await PhysicsExpert().create_motion_graphs("Car accelerating from 0 to 20 m/s in 5 seconds")
    assert [graph["id"] for graph in graphs] == ["x_t", "v_t", "a_t"]
    assert graphs[0]["curve"] == "parabolic"
    assert graphs[1]["points"][-1]["y"] == 20
    assert graphs[2]["points"][0]["y"] == 4
    assert all(graph["renderer"] == "GraphRenderer" for graph in graphs)


@pytest.mark.asyncio
async def test_vector_addition_calculates_resultant_components() -> None:
    result = await PhysicsExpert().visualize_vector_addition([
        {"magnitude": 10, "direction": 0},
        {"magnitude": 10, "direction": 90},
    ])
    assert result["arrangement"] == "head_to_tail"
    assert result["resultant"]["magnitude"] == pytest.approx(math.sqrt(200))
    assert result["resultant"]["direction_degrees"] == pytest.approx(45)


@pytest.mark.asyncio
async def test_invalid_physics_visualization_input_is_rejected() -> None:
    expert = PhysicsExpert()
    with pytest.raises(ValueError):
        await expert.create_free_body_diagram("")
    with pytest.raises(ValueError):
        await expert.visualize_vector_addition([])


@pytest.mark.asyncio
async def test_fbd_marks_unknown_applied_force_and_includes_tension() -> None:
    expert = PhysicsExpert()
    pushed = await expert.create_free_body_diagram("A box is pushed")
    assert next(force for force in pushed["forces"] if force["name"] == "Applied force")["unknown"]
    hanging = await expert.create_free_body_diagram("A 10kg mass hangs from a rope")
    assert {force["name"] for force in hanging["forces"]} == {"Weight", "Tension"}
    assert next(force for force in hanging["forces"] if force["name"] == "Weight")["render_direction_degrees"] == 90


@pytest.mark.asyncio
async def test_physics_plan_contains_renderer_ready_fbd() -> None:
    from api.models.curriculum_cambodia import RichProblem
    problem = RichProblem(problem_id="physics_g10_force", subject="physics", grade=10, unit="Dynamics", topic_id="physics_g10_dynamics_01", problem_text="A 5kg box is pushed with 20N force", problem_text_khmer="ប្រអប់ត្រូវបានរុញ", problem_type="force", visualizations_needed=["free_body_diagram"], concepts=["force"])
    plan = await PhysicsExpert().create_visualization_plan(problem)
    assert plan.visualization_steps[1].content["renderer"] == "VectorRenderer"
