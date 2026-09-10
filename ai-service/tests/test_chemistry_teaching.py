import pytest
from api.models.curriculum_cambodia import RichProblem
from api.services.subject_experts.chemistry_expert import ChemistryExpert

@pytest.mark.asyncio
@pytest.mark.parametrize("compound,geometry", [("H2O", "bent"), ("CO2", "linear"), ("NH3", "trigonal_pyramidal"), ("CH4", "tetrahedral"), ("O2", "linear"), ("N2", "linear"), ("HCl", "linear"), ("NaCl", "ionic_lattice"), ("SO2", "bent"), ("PCl3", "trigonal_pyramidal")])
async def test_vetted_molecular_structures(compound, geometry) -> None:
    structure = await ChemistryExpert().create_molecular_structure(compound)
    assert structure["renderer"] == "MoleculeRenderer"
    assert structure["visualizations"]["molecular_geometry"] == geometry
    assert structure["structure"]["atoms"]

@pytest.mark.asyncio
async def test_bonding_mechanism_and_energy_visuals() -> None:
    expert = ChemistryExpert()
    assert (await expert.analyze_bonding("NaCl"))["bonding_type"] == "ionic"
    assert len(await expert.visualize_reaction_mechanism("HCl + NaOH → NaCl + H2O", [])) == 5
    assert (await expert.create_energy_diagram("HCl + NaOH → NaCl + H2O"))["reaction_type"] == "exothermic"

@pytest.mark.asyncio
async def test_chemistry_six_stage_plan_evaluation_and_misconception() -> None:
    problem = RichProblem(problem_id="chem_g10_dissolve", subject="chemistry", grade=10, unit="Bonding", topic_id="chemistry_g10_bonding_01", problem_text="Why does NaCl dissolve in water?", problem_text_khmer="ហេតុអ្វី NaCl រលាយក្នុងទឹក?", problem_type="bonding", visualizations_needed=["molecule"], concepts=["ionic_bonding"])
    expert = ChemistryExpert(); plan = await expert.create_visualization_plan(problem)
    assert [step.step_id.rsplit("_", 1)[-1] for step in plan.visualization_steps] == ["molecular", "electrons", "energy", "mechanism", "observable", "predict"]
    assert (await expert.evaluate_student_response("salt", "step", "NaCl")).is_correct
    misconception = await expert.detect_misconception("All reactions release energy", "", "step")
    assert misconception and misconception["misconception_type"] == "all_reactions_exothermic"
