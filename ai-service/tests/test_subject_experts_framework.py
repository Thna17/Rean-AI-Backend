import pytest
from api.models.curriculum_cambodia import RichProblem
from api.services.subject_experts import ChemistryExpert, MathExpert, PhysicsExpert, SubjectExpert, get_expert

def problem(subject: str) -> RichProblem:
    return RichProblem(problem_id=f"{subject}_g10_test", subject=subject, grade=10, unit="Test", topic_id=f"{subject}_g10_topic", problem_text="Solve 2x + 5 = 13" if subject == "math" else "A block has weight and normal force" if subject == "physics" else "NaCl", problem_text_khmer="លំហាត់សាកល្បង", problem_type="test", visualizations_needed=["diagram"], concepts=["test"])

@pytest.mark.asyncio
@pytest.mark.parametrize(("subject", "expert_type"), [("math", MathExpert), ("physics", PhysicsExpert), ("chemistry", ChemistryExpert)])
async def test_factory_and_shared_socratic_contract(subject, expert_type) -> None:
    expert = await get_expert(subject); assert isinstance(expert, SubjectExpert); assert isinstance(expert, expert_type)
    analysis = await expert.analyze_problem(problem(subject)); assert analysis["problem_type"] == "test"
    plan = await expert.create_visualization_plan(problem(subject)); assert plan.visualization_steps[0].student_question
    assert not (await expert.evaluate_student_response("try", "step", "answer")).is_correct
    assert await expert.detect_misconception("wrong", "right", "step")
    assert (await expert.generate_reteach_step("step")).interaction is not None

@pytest.mark.asyncio
async def test_subject_specific_phase_zero_helpers() -> None:
    assert (await MathExpert().equation_parser("2x + 5"))["variables"] == ["x"]
    assert "weight" in await PhysicsExpert().identify_forces("weight and normal")
    assert await ChemistryExpert().identify_bonding("NaCl") == "ionic"
