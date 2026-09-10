"""
Chemistry Expert Service - Domain Intelligence for Chemistry Tutoring

Provides subject-specific expertise for:
- Problem type detection (Lewis structures, bonding, reactions, etc.)
- Step generation following Socratic method
- Visualization generation for chemistry concepts
- Student response evaluation
- Common misconception detection

Uses:
- Knowledge Graph for concept retrieval
- Model Gateway for LLM-based evaluation
- Renderers for visualization creation
"""

import logging
import uuid
from typing import Any, Dict, List, Optional

from api.models.teaching_step import (
    DifficultyLevel,
    InteractionConfig,
    StepType,
    Subject,
    TeachingStep,
    VisualizationConfig,
    VisualizationType,
    EvaluationResult,
)
from api.models.subject_expert_models import (
    ChemistryProblemAnalysis,
    ChemistryProblemType,
    ChemistryMisconception,
)

logger = logging.getLogger(__name__)


class ChemistryExpertService:
    """Expert service for chemistry problem solving and tutoring.

    Detects chemistry problem types, generates step-by-step solutions,
    creates visualizations, and evaluates student responses following
    pedagogical best practices.
    """

    def __init__(
        self,
        kg_service: Optional[Any] = None,
        model_gateway: Optional[Any] = None,
    ):
        """Initialize the Chemistry Expert Service.

        Args:
            kg_service: Knowledge Graph service for concept retrieval
            model_gateway: Model Gateway for LLM-based evaluation
        """
        self.kg_service = kg_service
        self.model_gateway = model_gateway
        self.service_name = "chemistry_expert"
        logger.info("ChemistryExpertService initialized")

    async def analyze_problem(self, problem: str) -> ChemistryProblemAnalysis:
        """Detect the type of chemistry problem and analyze it.

        Args:
            problem: Problem text to analyze

        Returns:
            ChemistryProblemAnalysis with problem type, difficulty, concepts

        Raises:
            ValueError: If problem cannot be analyzed
        """
        if not problem or not isinstance(problem, str):
            raise ValueError("Problem must be a non-empty string")

        logger.debug(f"Analyzing chemistry problem: {problem[:100]}...")

        # Detect problem type
        problem_type = await self._detect_problem_type(problem)
        logger.debug(f"Detected problem type: {problem_type}")

        # Extract difficulty and concepts
        difficulty = self._estimate_difficulty(problem, problem_type)
        concepts = await self._extract_concepts(problem, problem_type)

        # Extract molecule or reaction
        molecule_or_reaction = self._extract_molecule_or_reaction(problem)

        # Extract key information
        key_info = await self._extract_key_information(problem, problem_type)

        # Determine solution method
        solution_method = self._determine_solution_method(problem, problem_type)

        # Find common errors for this type
        common_errors = self._get_common_errors(problem_type)

        analysis = ChemistryProblemAnalysis(
            problem_type=problem_type,
            difficulty=difficulty,
            concepts=concepts,
            molecule_or_reaction=molecule_or_reaction,
            key_information=key_info,
            solution_method=solution_method,
            common_errors=common_errors,
        )

        logger.info(f"Problem analysis complete: {analysis.problem_type}")
        return analysis

    async def generate_steps(
        self,
        analysis: ChemistryProblemAnalysis,
        student_level: int = 10,
    ) -> List[TeachingStep]:
        """Generate problem-specific teaching steps.

        Args:
            analysis: Problem analysis from analyze_problem()
            student_level: Grade level (default 10)

        Returns:
            List of TeachingStep objects ordered sequentially

        Raises:
            ValueError: If analysis is invalid
        """
        if not analysis:
            raise ValueError("Analysis cannot be None")

        logger.info(f"Generating steps for {analysis.problem_type.value}")

        # Route to problem-specific step generator
        if analysis.problem_type == ChemistryProblemType.LEWIS_STRUCTURE:
            steps = await self._solve_lewis_structure(analysis)
        elif analysis.problem_type == ChemistryProblemType.BONDING:
            steps = await self._solve_bonding(analysis)
        elif analysis.problem_type == ChemistryProblemType.MOLECULAR_GEOMETRY:
            steps = await self._solve_molecular_geometry(analysis)
        elif analysis.problem_type == ChemistryProblemType.REACTIONS:
            steps = await self._solve_reactions(analysis)
        elif analysis.problem_type == ChemistryProblemType.STOICHIOMETRY:
            steps = await self._solve_stoichiometry(analysis)
        elif analysis.problem_type == ChemistryProblemType.ELECTRON_CONFIGURATION:
            steps = await self._solve_electron_configuration(analysis)
        else:
            raise ValueError(f"Unknown problem type: {analysis.problem_type}")

        logger.info(f"Generated {len(steps)} teaching steps")
        return steps

    async def create_visualization(
        self,
        step: TeachingStep,
    ) -> List[VisualizationConfig]:
        """Create chemistry-specific visualizations for a step.

        Args:
            step: TeachingStep that needs visualization

        Returns:
            List of VisualizationConfig objects

        Raises:
            ValueError: If step cannot be visualized
        """
        if not step:
            raise ValueError("Step cannot be None")

        logger.debug(f"Creating visualization for step {step.id}")
        visualizations = []

        # Molecular structure
        if "molecule" in step.metadata or "lewis" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.MOLECULE,
                data={
                    "atoms": step.metadata.get("atoms", []),
                    "bonds": step.metadata.get("bonds", []),
                    "lone_pairs": step.metadata.get("lone_pairs", []),
                },
                title=f"Lewis Structure: {step.metadata.get('formula', 'molecule')}",
            )
            visualizations.append(viz)

        # Electron configuration
        if "electron_config" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.TABLE,
                data={
                    "orbitals": step.metadata.get("orbitals", []),
                    "electrons": step.metadata.get("electrons", []),
                },
                title="Electron Configuration",
            )
            visualizations.append(viz)

        # Geometry
        if "geometry" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.GEOMETRY,
                data={
                    "shape": step.metadata.get("shape"),
                    "atoms": step.metadata.get("atoms", []),
                },
                title=f"Molecular Geometry: {step.metadata.get('shape', 'unknown')}",
            )
            visualizations.append(viz)

        return visualizations

    async def evaluate_response(
        self,
        question: str,
        student_response: str,
        context: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate student's chemistry response.

        Args:
            question: The question asked
            student_response: Student's answer/work
            context: Additional context (expected answer, step_id, etc.)

        Returns:
            EvaluationResult with feedback and routing

        Raises:
            ValueError: If response evaluation fails
        """
        if not student_response or not isinstance(student_response, str):
            raise ValueError("Student response must be a non-empty string")

        logger.debug(f"Evaluating response: {student_response[:50]}...")

        # Check correctness
        expected_answer = context.get("expected_answer", "")
        is_correct = await self._check_answer_correctness(
            student_response, expected_answer
        )

        # Detect misconceptions if incorrect
        misconception = None
        if not is_correct:
            misconception = await self.detect_misconception(
                student_response, context.get("problem_type", "unknown")
            )

        # Generate feedback
        if is_correct:
            feedback = "Excellent work! Your answer is correct."
            condition = "correct"
            confidence = 0.95
        elif misconception:
            feedback = f"Not quite right. {misconception.explanation}"
            condition = "incorrect"
            confidence = 0.85
        else:
            feedback = "Let me provide a hint: Review the rules for this concept and try again."
            condition = "incorrect"
            confidence = 0.7

        result = EvaluationResult(
            is_correct=is_correct,
            condition=condition,
            confidence=confidence,
            feedback_message=feedback,
            explanation=misconception.correct_understanding if misconception else None,
            evaluation_time_ms=100,
            model_used="chemistry_expert",
        )

        logger.info(f"Evaluation result: {result.condition}")
        return result

    async def detect_misconception(
        self,
        error: str,
        problem_type: str,
    ) -> Optional[ChemistryMisconception]:
        """Detect common chemistry misconceptions.

        Args:
            error: Student's erroneous response
            problem_type: Type of problem being solved

        Returns:
            ChemistryMisconception if detected, None otherwise
        """
        if not error:
            return None

        logger.debug(f"Detecting misconception in: {error[:50]}...")

        error_lower = error.lower()

        # Octet rule misapplication
        if "octet" in error_lower:
            return ChemistryMisconception(
                error_type="octet_rule_misapplication",
                description="Misunderstanding how the octet rule applies",
                explanation="The octet rule applies to most main group elements, but not all. Hydrogen follows the duet rule. Some elements can exceed the octet.",
                correct_understanding="Check valence electrons and electron configuration to know when octet rule applies.",
                visual_aid="Show electron configuration for different elements",
            )

        # Electronegativity confusion
        if "electronegativity" in error_lower or "electronegative" in error_lower:
            return ChemistryMisconception(
                error_type="electronegativity_confusion",
                description="Misunderstanding how electronegativity determines bonding",
                explanation="Electronegativity difference determines bond type. ΔEN < 0.5 (covalent), 0.5-1.7 (polar covalent), > 1.7 (ionic).",
                correct_understanding="Use electronegativity values to predict bond character.",
            )

        # Bonding misconception
        if "bond" in error_lower and "electron" in error_lower:
            return ChemistryMisconception(
                error_type="bonding_misconception",
                description="Misunderstanding how electrons are shared in bonds",
                explanation="In covalent bonds, electrons are SHARED between atoms. In ionic bonds, electrons are TRANSFERRED.",
                correct_understanding="Know the difference between electron sharing (covalent) and electron transfer (ionic).",
            )

        # Equation balancing
        if "balance" in error_lower or "equation" in error_lower:
            return ChemistryMisconception(
                error_type="unbalanced_equation",
                description="Chemical equation is not balanced",
                explanation="In a balanced equation, the number of each type of atom must be the same on both sides.",
                correct_understanding="Count atoms of each element on reactant and product sides. Coefficients balance atoms.",
            )

        # Stoichiometry
        if "mole" in error_lower or "stoich" in error_lower:
            return ChemistryMisconception(
                error_type="stoichiometry_error",
                description="Error in stoichiometric calculations",
                explanation="Stoichiometry uses mole ratios from balanced equations. Convert mass→mole→mole→mass using molar masses.",
                correct_understanding="Follow the conversion sequence: grams → moles → moles of product → grams",
            )

        return None

    # ============================================================
    # PROBLEM-SPECIFIC SOLVERS
    # ============================================================

    async def _solve_lewis_structure(self, analysis: ChemistryProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for Lewis structure problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Count Valence Electrons",
            description="Count total valence electrons from all atoms.",
            learning_objective="Determine electron count",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Identify Central Atom",
            description="Usually the least electronegative element (except hydrogen) is central.",
            learning_objective="Choose central atom",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Connect with Single Bonds",
            description="Draw single bonds from central atom to other atoms.",
            learning_objective="Create basic structure",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step3)

        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.EXPLANATION,
            title="Distribute Remaining Electrons",
            description="Place remaining electrons as lone pairs around atoms.",
            learning_objective="Complete electron distribution",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step4)

        step5 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=5,
            type=StepType.EXPLANATION,
            title="Add Multiple Bonds if Needed",
            description="If atoms don't have octets, form double or triple bonds.",
            learning_objective="Apply octet rule",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step5)

        step6 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=6,
            type=StepType.CHECK,
            title="Verify Octets",
            description="Check that all atoms have appropriate number of electrons (octet for main group).",
            learning_objective="Validate structure",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step6)

        return steps

    async def _solve_bonding(self, analysis: ChemistryProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for bonding type problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Look Up Electronegativity",
            description="Find electronegativity values for each atom involved.",
            learning_objective="Use periodic table",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Calculate Electronegativity Difference",
            description="Subtract to find ΔEN (always positive, larger minus smaller).",
            learning_objective="Calculate ΔEN",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Determine Bond Type",
            description="Use ΔEN to classify:\n• ΔEN < 0.5: Nonpolar covalent\n• 0.5 ≤ ΔEN < 1.7: Polar covalent\n• ΔEN ≥ 1.7: Ionic",
            learning_objective="Classify bonds",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step3)

        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.EXPLANATION,
            title="Explain Electron Distribution",
            description="Describe how electrons are shared or transferred based on bond type.",
            learning_objective="Explain bonding",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step4)

        return steps

    async def _solve_molecular_geometry(self, analysis: ChemistryProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for molecular geometry (VSEPR) problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Draw Lewis Structure",
            description="First draw the Lewis structure with all bonds and lone pairs.",
            learning_objective="Create Lewis structure",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Count Electron Domains",
            description="Count bonding pairs + lone pairs around central atom.",
            learning_objective="Count domains",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Determine Electron Geometry",
            description="Based on number of domains: 2→linear, 3→trigonal planar, 4→tetrahedral, etc.",
            learning_objective="Identify electron geometry",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step3)

        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.EXPLANATION,
            title="Determine Molecular Geometry",
            description="Account for lone pairs. Molecular geometry considers only atom positions, not lone pairs.",
            learning_objective="Find molecular geometry",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
            visualizations=[
                VisualizationConfig(
                    type=VisualizationType.GEOMETRY,
                    data={"shape": "tetrahedral"},
                    title="Molecular Geometry",
                )
            ],
        )
        steps.append(step4)

        return steps

    async def _solve_reactions(self, analysis: ChemistryProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for chemical reaction problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Write the Unbalanced Equation",
            description="Write the formulas for all reactants and products.",
            learning_objective="Set up equation",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Balance the Equation",
            description="Add coefficients to balance atoms of each element.",
            learning_objective="Balance atoms",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.CHECK,
            title="Verify Balance",
            description="Check that all atoms are balanced on both sides.",
            learning_objective="Validate equation",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step3)

        return steps

    async def _solve_stoichiometry(self, analysis: ChemistryProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for stoichiometry problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Write Balanced Equation",
            description="Start with a balanced chemical equation.",
            learning_objective="Ensure balanced equation",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Convert Given Amount to Moles",
            description="Use molar mass to convert grams to moles.",
            learning_objective="Calculate moles",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Use Mole Ratio",
            description="Use coefficients from balanced equation to find moles of desired substance.",
            learning_objective="Apply stoichiometry",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step3)

        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.EXPLANATION,
            title="Convert to Desired Units",
            description="Convert moles back to grams (or other units) if needed.",
            learning_objective="Complete calculation",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step4)

        return steps

    async def _solve_electron_configuration(self, analysis: ChemistryProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for electron configuration problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Find Atomic Number",
            description="The atomic number tells you how many electrons the atom has.",
            learning_objective="Determine electron count",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Apply Aufbau Principle",
            description="Fill orbitals in order: 1s, 2s, 2p, 3s, 3p, 4s, 3d, ...",
            learning_objective="Order electron filling",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Fill Each Orbital",
            description="Each orbital can hold up to 2 electrons (opposite spin).",
            learning_objective="Distribute electrons",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.CHEMISTRY,
        )
        steps.append(step3)

        return steps

    # ============================================================
    # HELPER METHODS
    # ============================================================

    async def _detect_problem_type(self, problem: str) -> ChemistryProblemType:
        """Detect the type of chemistry problem from text."""
        problem_lower = problem.lower()

        if any(kw in problem_lower for kw in ["lewis", "structure", "electron"]):
            return ChemistryProblemType.LEWIS_STRUCTURE

        if any(kw in problem_lower for kw in ["bond", "ionic", "covalent"]):
            return ChemistryProblemType.BONDING

        if any(kw in problem_lower for kw in ["geometry", "shape", "vsepr"]):
            return ChemistryProblemType.MOLECULAR_GEOMETRY

        if any(kw in problem_lower for kw in ["reaction", "product", "reactant", "balance"]):
            return ChemistryProblemType.REACTIONS

        if any(kw in problem_lower for kw in ["stoich", "mole", "gram"]):
            return ChemistryProblemType.STOICHIOMETRY

        if any(kw in problem_lower for kw in ["configuration", "orbital", "electron"]):
            return ChemistryProblemType.ELECTRON_CONFIGURATION

        return ChemistryProblemType.REACTIONS  # Default

    def _estimate_difficulty(
        self, problem: str, problem_type: ChemistryProblemType
    ) -> int:
        """Estimate problem difficulty (1-5)."""
        base_difficulty = {
            ChemistryProblemType.LEWIS_STRUCTURE: 2,
            ChemistryProblemType.BONDING: 2,
            ChemistryProblemType.MOLECULAR_GEOMETRY: 3,
            ChemistryProblemType.REACTIONS: 1,
            ChemistryProblemType.STOICHIOMETRY: 3,
            ChemistryProblemType.ELECTRON_CONFIGURATION: 2,
        }.get(problem_type, 2)

        if "polyatomic" in problem.lower():
            base_difficulty += 1
        if any(kw in problem.lower() for kw in ["coordinate", "resonance"]):
            base_difficulty += 1

        return min(5, max(1, base_difficulty))

    async def _extract_concepts(
        self, problem: str, problem_type: ChemistryProblemType
    ) -> List[str]:
        """Extract concepts involved in the problem."""
        type_concepts = {
            ChemistryProblemType.LEWIS_STRUCTURE: ["valence electrons", "bonding", "lone pairs"],
            ChemistryProblemType.BONDING: ["electronegativity", "bond types", "electron transfer"],
            ChemistryProblemType.MOLECULAR_GEOMETRY: ["VSEPR theory", "electron domains"],
            ChemistryProblemType.REACTIONS: ["balancing", "stoichiometry", "reaction types"],
            ChemistryProblemType.STOICHIOMETRY: ["mole ratios", "molar mass", "conversions"],
            ChemistryProblemType.ELECTRON_CONFIGURATION: ["Aufbau principle", "orbitals", "Pauli exclusion"],
        }
        return type_concepts.get(problem_type, [])

    def _extract_molecule_or_reaction(self, problem: str) -> str:
        """Extract the molecule formula or reaction from the problem."""
        # Look for chemical formulas (simple pattern)
        import re
        # Match patterns like H2O, CO2, etc
        matches = re.findall(r"[A-Z][a-z]?\d*(?:[A-Z][a-z]?\d*)*", problem)
        if matches:
            return " + ".join(matches[:3])  # Return first few as a sample
        return "unknown"

    async def _extract_key_information(
        self, problem: str, problem_type: ChemistryProblemType
    ) -> Dict[str, Any]:
        """Extract key information from the problem."""
        info = {}

        if "molar mass" in problem.lower():
            info["has_molar_mass"] = True

        if any(kw in problem.lower() for kw in ["gram", "g", "kg"]):
            info["mass_given"] = True

        if "mole" in problem.lower():
            info["moles_given"] = True

        return info

    def _determine_solution_method(
        self, problem: str, problem_type: ChemistryProblemType
    ) -> str:
        """Determine the primary solution method."""
        methods = {
            ChemistryProblemType.LEWIS_STRUCTURE: "Count valence electrons, place bonds and lone pairs",
            ChemistryProblemType.BONDING: "Calculate electronegativity difference to classify bond",
            ChemistryProblemType.MOLECULAR_GEOMETRY: "Use VSEPR theory to predict shape",
            ChemistryProblemType.REACTIONS: "Balance chemical equation",
            ChemistryProblemType.STOICHIOMETRY: "Use mole ratios from balanced equation",
            ChemistryProblemType.ELECTRON_CONFIGURATION: "Fill orbitals using Aufbau principle",
        }
        return methods.get(problem_type, "Problem-specific approach")

    def _get_common_errors(self, problem_type: ChemistryProblemType) -> List[str]:
        """Get common student errors for a problem type."""
        errors = {
            ChemistryProblemType.LEWIS_STRUCTURE: [
                "Wrong valence electron count",
                "Forgetting lone pairs",
                "Not applying octet rule",
            ],
            ChemistryProblemType.BONDING: [
                "Wrong electronegativity values",
                "Incorrect bond classification",
            ],
            ChemistryProblemType.MOLECULAR_GEOMETRY: [
                "Confusing electron geometry and molecular geometry",
                "Forgetting lone pairs affect geometry",
            ],
            ChemistryProblemType.REACTIONS: [
                "Unbalanced equation",
                "Wrong formulas",
            ],
            ChemistryProblemType.STOICHIOMETRY: [
                "Unit conversion errors",
                "Wrong mole ratio",
            ],
        }
        return errors.get(problem_type, [])

    async def _check_answer_correctness(
        self, student_answer: str, expected_answer: str
    ) -> bool:
        """Check if student's answer matches expected answer."""
        if not expected_answer:
            return len(student_answer) > 0

        student_clean = student_answer.strip().lower()
        expected_clean = expected_answer.strip().lower()

        # Exact match
        if student_clean == expected_clean:
            return True

        # For formulas, try flexible matching
        student_parts = student_clean.split("+")
        expected_parts = expected_clean.split("+")

        if len(student_parts) == len(expected_parts):
            # Check if all parts match (order might vary)
            return set(p.strip() for p in student_parts) == set(
                p.strip() for p in expected_parts
            )

        return False
