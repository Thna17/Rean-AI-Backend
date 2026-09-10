"""Chemistry visual and Socratic teaching plans for a vetted common set."""
from __future__ import annotations

import re
from typing import Any

from api.models.curriculum_cambodia import RichProblem, VisualizationPlan, VisualizationStep
from api.models.teaching_step import EvaluationResult
from api.services.subject_experts._stub import StubSubjectExpert

_ELEMENTS = {"H": (1, 1), "C": (6, 4), "N": (7, 5), "O": (8, 6), "S": (16, 6), "P": (15, 5), "F": (9, 7), "Cl": (17, 7), "Br": (35, 7), "I": (53, 7), "Na": (11, 1), "Mg": (12, 2), "Ca": (20, 2)}
_STRUCTURES = {
    "H2O": (["O", "H", "H"], [(0, 1, "single"), (0, 2, "single")], "bent"), "CO2": (["O", "C", "O"], [(0, 1, "double"), (1, 2, "double")], "linear"), "NH3": (["N", "H", "H", "H"], [(0, 1, "single"), (0, 2, "single"), (0, 3, "single")], "trigonal_pyramidal"), "CH4": (["C", "H", "H", "H", "H"], [(0, 1, "single"), (0, 2, "single"), (0, 3, "single"), (0, 4, "single")], "tetrahedral"), "O2": (["O", "O"], [(0, 1, "double")], "linear"), "N2": (["N", "N"], [(0, 1, "triple")], "linear"), "HCl": (["H", "Cl"], [(0, 1, "single")], "linear"), "NaCl": (["Na", "Cl"], [(0, 1, "ionic")], "ionic_lattice"), "SO2": (["S", "O", "O"], [(0, 1, "double"), (0, 2, "double")], "bent"), "PCl3": (["P", "Cl", "Cl", "Cl"], [(0, 1, "single"), (0, 2, "single"), (0, 3, "single")], "trigonal_pyramidal")}


class ChemistryExpert(StubSubjectExpert):
    subject = "chemistry"
    visual_type = "molecule"

    async def parse_compound(self, formula: str) -> list[str]:
        formulas = re.findall(r"\b(?:[A-Z][a-z]?\d*)+\b", formula)
        elements = re.findall(r"[A-Z][a-z]?", formulas[-1] if formulas else formula)
        if not elements or any(item not in _ELEMENTS for item in elements): raise ValueError("Compound contains an unsupported element")
        return elements

    async def identify_bonding(self, formula: str) -> str:
        elements = await self.parse_compound(formula)
        return "ionic" if any(item in {"Na", "Mg", "Ca"} for item in elements) and any(item in {"F", "Cl", "Br", "I", "O"} for item in elements) else "covalent"

    async def show_electron_configuration(self, element: str) -> dict[str, Any]:
        if element not in _ELEMENTS: raise ValueError(f"Unsupported element: {element}")
        atomic_number, valence = _ELEMENTS[element]
        return {"renderer": "MoleculeRenderer", "element": element, "atomic_number": atomic_number, "valence_electrons": valence}

    async def create_molecular_structure(self, compound: str, show_electrons: bool = True, show_bonds: bool = True, show_lone_pairs: bool = True) -> dict[str, Any]:
        """Create a vetted 2D Lewis/VSEPR structure for supported compounds."""
        formula = _formula(compound)
        if formula not in _STRUCTURES: raise ValueError(f"No vetted structure for {formula}")
        atoms, bonds, geometry = _STRUCTURES[formula]
        positions = _positions(len(atoms), geometry)
        atom_data = [{"id": f"{element}{index}", "element": element, "position": positions[index], "valence_electrons": _ELEMENTS[element][1]} for index, element in enumerate(atoms)]
        bond_data = [{"from": atom_data[start]["id"], "to": atom_data[end]["id"], "type": bond, "electrons": 2 * {"single": 1, "double": 2, "triple": 3}[bond]} for start, end, bond in bonds if bond != "ionic"]
        return {"renderer": "MoleculeRenderer", "compound": formula, "structure": {"atoms": atom_data, "bonds": bond_data if show_bonds else [], "ions": [{"element": "Na", "charge": "+1"}, {"element": "Cl", "charge": "-1"}] if formula == "NaCl" else []}, "visualizations": {"lewis_structure": {"show_bonds": show_bonds, "show_lone_pairs": show_lone_pairs, "lone_pairs": [{"atom_index": 0, "count": 2}] if show_lone_pairs and formula in {"H2O", "NH3", "SO2", "PCl3"} else []}, "electron_dots": {"enabled": show_electrons}, "molecular_geometry": geometry}}

    async def analyze_bonding(self, compound: str) -> dict[str, Any]:
        formula = _formula(compound); bonding = await self.identify_bonding(formula)
        difference = 2.1 if bonding == "ionic" else 0.9
        return {"compound": formula, "bonding_type": bonding, "electronegativity_difference": difference, "explanation": "A large electronegativity difference supports ionic character." if bonding == "ionic" else "A smaller electronegativity difference supports covalent sharing.", "visualizations": {"ionic_dissociation": {"enabled": bonding == "ionic"}, "electron_transfer": {"enabled": bonding == "ionic"}, "hydration": {"enabled": formula == "NaCl"}}}

    async def visualize_reaction_mechanism(self, reaction: str, steps: list[str] | None = None) -> list[dict[str, Any]]:
        """Return ChemistryVisualizer animation stages; does not balance reactions."""
        if "→" not in reaction and "->" not in reaction: raise ValueError("Reaction must include an arrow")
        labels = steps or ["Show reactants", "Show electron/proton movement", "Show bond changes", "Show products", "Show net ionic equation"]
        return [{"step_number": index + 1, "label": label, "reaction": reaction, "renderer": "MoleculeRenderer", "animation": "draw" if index < 3 else "fade_in"} for index, label in enumerate(labels)]

    async def create_energy_diagram(self, reaction: str) -> dict[str, Any]:
        if "→" not in reaction and "->" not in reaction: raise ValueError("Reaction must include an arrow")
        endothermic = any(term in reaction.casefold() for term in ("heat", "endothermic", "decomposition"))
        return {"renderer": "GraphRenderer", "reaction": reaction, "reaction_type": "endothermic" if endothermic else "exothermic", "reactants_energy": 50, "activation_energy": 80, "products_energy": 65 if endothermic else 30, "axes": {"x": "Reaction progress", "y": "Energy (kJ/mol)"}}

    async def analyze_problem(self, problem: RichProblem) -> dict[str, Any]:
        analysis = await super().analyze_problem(problem); text = problem.problem_text
        formulas = [formula for formula in re.findall(r"\b(?:[A-Z][a-z]?\d*)+\b", text) if formula in _STRUCTURES]
        analysis.update({"problem_type": _chem_type(problem.problem_type, text), "compounds": formulas, "processes": ["dissolution"] if "dissolv" in text.casefold() else ["reaction"] if ("→" in text or "->" in text) else [], "observable_phenomena": ["ions in solution"] if "dissolv" in text.casefold() else []})
        return analysis

    async def create_visualization_plan(self, problem: RichProblem, teaching_approach: str = "socratic") -> VisualizationPlan:
        self.validate_problem(problem, self.subject); analysis = await self.analyze_problem(problem)
        compound = analysis["compounds"][0] if analysis["compounds"] else None
        structure = await self.create_molecular_structure(compound) if compound else {"renderer": "MoleculeRenderer", "state": "await_compound_formula"}
        energy = await self.create_energy_diagram(problem.problem_text) if "→" in problem.problem_text or "->" in problem.problem_text else {"renderer": "GraphRenderer", "state": "compare_bond_and_hydration_energy"}
        mechanism = await self.visualize_reaction_mechanism(problem.problem_text) if "→" in problem.problem_text or "->" in problem.problem_text else [{"renderer": "MoleculeRenderer", "animation": "dissolution"}]
        data = [("molecular", structure, "What is happening at the molecular level?"), ("electrons", {"renderer": "MoleculeRenderer", "focus": "electron_behavior", "compound": compound}, "Why do electrons or dipoles orient this way?"), ("energy", energy, "Is this process energetically favorable?"), ("mechanism", {"renderer": "MoleculeRenderer", "steps": mechanism}, "What changes as particles interact?"), ("observable", {"renderer": "RichMediaCanvas", "phenomenon": analysis["observable_phenomena"]}, "What observable result would you expect?"), ("predict", {"renderer": "RichMediaCanvas", "application": "real_world"}, "Where else could you apply this idea?")]
        steps = [VisualizationStep(step_id=f"{problem.problem_id}_{stage}", visualization_type=stage, content=content, animation_type="draw", student_question=question, student_question_khmer="តើអ្នកអាចពន្យល់អ្វីបានពីកម្រិតម៉ូលេគុល?", expected_response_type="text") for stage, content, question in data]
        return VisualizationPlan(problem_id=problem.problem_id, visualization_steps=steps, animations=["draw"] * len(steps), student_questions=[step.student_question for step in steps], metadata={"renderer": "RichMediaCanvas", "teaching_approach": teaching_approach, "pattern": "chemistry_six_stage"})

    async def evaluate_student_response(self, student_answer: str, step_id: str, expected_answer: str | None = None, validation_strategy: str | None = None) -> EvaluationResult:
        if not student_answer.strip(): raise ValueError("Student answer must not be empty")
        equivalents = {"nacl": {"nacl", "sodiumchloride", "salt"}}
        answer = self.normalize_answer(student_answer); expected = self.normalize_answer(expected_answer) if expected_answer else ""
        correct = bool(expected and (answer == expected or answer in equivalents.get(expected, set())))
        return EvaluationResult(is_correct=correct, condition="correct" if correct else "incorrect", confidence=0.95 if correct else 0.8, feedback_message="Correct chemical relationship." if correct else "Check particles, charges, and energy changes.", should_offer_hint=not correct, hint_text=None if correct else await self.provide_hint(step_id), evaluation_time_ms=0, model_used="chemistry_phase_3_rules")

    async def detect_misconception(self, student_work: str, correct_answer: str, step_id: str) -> dict[str, str] | None:
        text = student_work.casefold()
        rules = [("atoms_solid", "atoms are solid", "Atoms are mostly empty space."), ("ionic_oversimplification", "ionic bonding is one atom giving", "Ionic bonding describes electrostatic attraction in a lattice."), ("all_reactions_exothermic", "all reactions release energy", "Some reactions are endothermic."), ("dissolving_not_process", "dissolving is not a chemical reaction", "Dissolving is usually a physical process with reversible particle interactions; distinguish it from reaction when no new substance forms.")]
        for kind, phrase, remediation in rules:
            if phrase in text: return {"misconception_type": kind, "description": "This chemistry idea needs refinement.", "remediation": remediation}
        return await super().detect_misconception(student_work, correct_answer, step_id)


def _formula(value: str) -> str:
    formulas = re.findall(r"\b(?:[A-Z][a-z]?\d*)+\b", value)
    return next((formula for formula in reversed(formulas) if formula in _STRUCTURES), formulas[-1] if formulas else value.strip())
def _positions(count: int, geometry: str) -> list[tuple[float, float]]:
    if geometry == "linear": return [(-1.0, 0.0), (0.0, 0.0), (1.0, 0.0)][:count] if count == 3 else [(0.0, 0.0), (1.0, 0.0)]
    return [(0.0, 0.0)] + [(-0.9, 0.7), (0.9, 0.7), (0.0, -1.0), (0.0, 1.4)][:count - 1]
def _chem_type(kind: str, text: str) -> str: return "reaction" if "→" in text or "->" in text else "bonding" if "bond" in text.casefold() else "concentration" if "molar" in text.casefold() else kind
