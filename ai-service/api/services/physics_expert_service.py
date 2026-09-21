"""
Physics Expert Service - Domain Intelligence for Physics Tutoring

Provides subject-specific expertise for:
- Problem type detection (kinematics, dynamics, energy, etc.)
- Step generation following Socratic method
- Visualization generation for physics concepts
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
    PhysicsProblemAnalysis,
    PhysicsProblemType,
    PhysicsMisconception,
)

logger = logging.getLogger(__name__)


class PhysicsExpertService:
    """Expert service for physics problem solving and tutoring.

    Detects physics problem types, generates step-by-step solutions,
    creates visualizations, and evaluates student responses following
    pedagogical best practices.
    """

    def __init__(
        self,
        kg_service: Optional[Any] = None,
        model_gateway: Optional[Any] = None,
    ):
        """Initialize the Physics Expert Service.

        Args:
            kg_service: Knowledge Graph service for concept retrieval
            model_gateway: Model Gateway for LLM-based evaluation
        """
        self.kg_service = kg_service
        self.model_gateway = model_gateway
        self.service_name = "physics_expert"
        logger.info("PhysicsExpertService initialized")

    async def analyze_problem(self, problem: str) -> PhysicsProblemAnalysis:
        """Detect the type of physics problem and analyze it.

        Args:
            problem: Problem text to analyze

        Returns:
            PhysicsProblemAnalysis with problem type, difficulty, concepts

        Raises:
            ValueError: If problem cannot be analyzed
        """
        if not problem or not isinstance(problem, str):
            raise ValueError("Problem must be a non-empty string")

        logger.debug(f"Analyzing physics problem: {problem[:100]}...")

        # Detect problem type
        problem_type = await self._detect_problem_type(problem)
        logger.debug(f"Detected problem type: {problem_type}")

        # Extract difficulty and concepts
        difficulty = self._estimate_difficulty(problem, problem_type)
        concepts = await self._extract_concepts(problem, problem_type)

        # Extract given values
        given_values = await self._extract_given_values(problem)

        # Determine what to find
        find_value = self._determine_find_value(problem, problem_type)

        # Determine equations needed
        equations = self._get_equations_needed(problem_type)

        # Determine solution method
        solution_method = self._determine_solution_method(problem, problem_type)

        # Find common errors for this type
        common_errors = self._get_common_errors(problem_type)

        analysis = PhysicsProblemAnalysis(
            problem_type=problem_type,
            difficulty=difficulty,
            concepts=concepts,
            given_values=given_values,
            find_value=find_value,
            equations_needed=equations,
            solution_method=solution_method,
            common_errors=common_errors,
        )

        logger.info(f"Problem analysis complete: {analysis.problem_type}")
        return analysis

    async def generate_steps(
        self,
        analysis: PhysicsProblemAnalysis,
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
        if analysis.problem_type == PhysicsProblemType.KINEMATICS:
            steps = await self._solve_kinematics(analysis)
        elif analysis.problem_type == PhysicsProblemType.DYNAMICS:
            steps = await self._solve_dynamics(analysis)
        elif analysis.problem_type == PhysicsProblemType.CIRCULAR_MOTION:
            steps = await self._solve_circular_motion(analysis)
        elif analysis.problem_type == PhysicsProblemType.ENERGY:
            steps = await self._solve_energy(analysis)
        elif analysis.problem_type == PhysicsProblemType.WAVES:
            steps = await self._solve_waves(analysis)
        elif analysis.problem_type == PhysicsProblemType.ELECTRICITY:
            steps = await self._solve_electricity(analysis)
        elif analysis.problem_type == PhysicsProblemType.MAGNETISM:
            steps = await self._solve_magnetism(analysis)
        else:
            raise ValueError(f"Unknown problem type: {analysis.problem_type}")

        logger.info(f"Generated {len(steps)} teaching steps")
        return steps

    async def create_visualization(
        self,
        step: TeachingStep,
    ) -> List[VisualizationConfig]:
        """Create physics-specific visualizations for a step.

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

        # Free body diagram
        if "forces" in step.metadata or "free_body" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.VECTOR,
                data={
                    "vectors": step.metadata.get("forces", []),
                    "object": step.metadata.get("object", "block"),
                    "scale": step.metadata.get("scale", 1.0),
                },
                title="Free Body Diagram",
            )
            visualizations.append(viz)

        # Motion graph
        if "motion_graph" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.GRAPH,
                data={
                    "graph_type": step.metadata.get("graph_type", "position_vs_time"),
                    "x_axis": "time (s)",
                    "y_axis": step.metadata.get("y_axis", "position (m)"),
                },
                title="Motion Graph",
            )
            visualizations.append(viz)

        # Energy diagram
        if "energy_types" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.TABLE,
                data={
                    "energy_types": step.metadata.get("energy_types", []),
                    "values": step.metadata.get("values", []),
                },
                title="Energy Diagram",
            )
            visualizations.append(viz)

        return visualizations

    async def evaluate_response(
        self,
        question: str,
        student_response: str,
        context: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate student's physics response.

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

        # Check units
        has_units = self._check_units(student_response)
        
        # Detect misconceptions if incorrect
        misconception = None
        if not is_correct:
            misconception = await self.detect_misconception(
                student_response, context.get("problem_type", "unknown")
            )

        # Generate feedback
        if is_correct:
            feedback = "Excellent work! Your answer and reasoning are correct."
            condition = "correct"
            confidence = 0.95
        elif not has_units and expected_answer:
            feedback = "Your numerical answer looks good, but don't forget to include units!"
            condition = "incorrect"
            confidence = 0.8
        elif misconception:
            feedback = f"Not quite. {misconception.explanation}"
            condition = "incorrect"
            confidence = 0.85
        else:
            feedback = "Let me provide a hint: Check your calculation and make sure you used the correct equation."
            condition = "incorrect"
            confidence = 0.7

        result = EvaluationResult(
            is_correct=is_correct,
            condition=condition,
            confidence=confidence,
            feedback_message=feedback,
            explanation=misconception.correction if misconception else None,
            evaluation_time_ms=100,
            model_used="physics_expert",
        )

        logger.info(f"Evaluation result: {result.condition}")
        return result

    async def detect_misconception(
        self,
        error: str,
        problem_type: str,
    ) -> Optional[PhysicsMisconception]:
        """Detect common physics misconceptions.

        Args:
            error: Student's erroneous response
            problem_type: Type of problem being solved

        Returns:
            PhysicsMisconception if detected, None otherwise
        """
        if not error:
            return None

        logger.debug(f"Detecting misconception in: {error[:50]}...")

        error_lower = error.lower()

        # Velocity vs acceleration confusion
        if "velocity" in error_lower and "acceleration" in error_lower:
            return PhysicsMisconception(
                error_type="velocity_acceleration_confusion",
                description="Confusing velocity and acceleration",
                explanation="Velocity is speed with direction. Acceleration is the change in velocity. They are different!",
                correct_concept="Velocity = change in position / time. Acceleration = change in velocity / time.",
                examples=[
                    "A car traveling at constant 60 mph has velocity but ZERO acceleration",
                    "A car speeding up has both velocity AND acceleration",
                ],
            )

        # Force misconception
        if "force" in error_lower and "motion" in error_lower:
            return PhysicsMisconception(
                error_type="force_needed_for_motion",
                description="Thinking force is needed to keep something moving",
                explanation="Objects in motion stay in motion without force (Newton's 1st law). Force causes CHANGES in motion.",
                correct_concept="Net force = mass × acceleration. No net force = no change in velocity.",
                examples=[
                    "A ball rolling on frictionless ice keeps rolling without force",
                    "You need force to START motion, not to CONTINUE it",
                ],
            )

        # Free fall misconception
        if "free fall" in error_lower or "gravity" in error_lower:
            return PhysicsMisconception(
                error_type="free_fall_misconception",
                description="Thinking heavier objects fall faster",
                explanation="All objects fall with same acceleration (g = 9.8 m/s²) in vacuum, regardless of mass.",
                correct_concept="In free fall, a = g for all objects. Air resistance affects real-world falling.",
                examples=[
                    "A feather and bowling ball fall at same rate in a vacuum",
                    "On the moon, they also fall at same rate (different g value though)",
                ],
            )

        # Energy conservation
        if "energy" in error_lower and "lost" in error_lower:
            return PhysicsMisconception(
                error_type="energy_loss",
                description="Thinking energy is lost in collisions",
                explanation="Energy is never lost, only transformed. Some becomes heat, sound, deformation.",
                correct_concept="Total energy is conserved. Energy transforms between forms but total stays constant.",
                examples=[
                    "In inelastic collision, some kinetic energy becomes heat and sound",
                    "Mechanical energy converts to thermal energy due to friction",
                ],
            )

        return None

    # ============================================================
    # PROBLEM-SPECIFIC SOLVERS
    # ============================================================

    async def _solve_kinematics(self, analysis: PhysicsProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for kinematics problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Identify Known and Unknown",
            description="List all given values (initial velocity, acceleration, time, etc.) and what we need to find.",
            learning_objective="Extract problem information",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.PHYSICS,
            metadata={"given_values": analysis.given_values},
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="List Kinematic Equations",
            description="The main kinematic equations are:\nv = u + at\ns = ut + ½at²\nv² = u² + 2as",
            learning_objective="Know kinematic equations",
            difficulty=DifficultyLevel.REMEMBER,
            subject=Subject.PHYSICS,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.QUESTION,
            title="Choose the Right Equation",
            description="Which equation should we use?",
            learning_objective="Select appropriate equation",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
            interaction=InteractionConfig(
                question_text="Which equation relates the variables we know and the one we need to find?",
                interaction_type="text_input",
            ),
        )
        steps.append(step3)

        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.EXPLANATION,
            title="Substitute Values",
            description="Plug in the known values into the equation.",
            learning_objective="Apply equation correctly",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
        )
        steps.append(step4)

        step5 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=5,
            type=StepType.EXPLANATION,
            title="Solve for Unknown",
            description="Use algebra to solve for the unknown quantity.",
            learning_objective="Complete solution",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
        )
        steps.append(step5)

        step6 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=6,
            type=StepType.CHECK,
            title="Check Your Answer",
            description="Does the answer make physical sense? Do the units match?",
            learning_objective="Verify solution reasonableness",
            difficulty=DifficultyLevel.EVALUATE,
            subject=Subject.PHYSICS,
        )
        steps.append(step6)

        return steps

    async def _solve_dynamics(self, analysis: PhysicsProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for dynamics (forces) problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Draw Free Body Diagram",
            description="Draw the object and all forces acting on it.",
            learning_objective="Visualize force interactions",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.PHYSICS,
            visualizations=[
                VisualizationConfig(
                    type=VisualizationType.VECTOR,
                    data={"forces": []},
                    title="Free Body Diagram",
                )
            ],
            metadata={"free_body": True},
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Identify All Forces",
            description="List all forces: weight (mg), normal force (N), friction (f), applied force (F), etc.",
            learning_objective="Recognize all forces present",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.PHYSICS,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Find Net Force",
            description="Add all forces as vectors. Remember: forces in same direction add, opposite directions subtract.",
            learning_objective="Calculate net force",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
        )
        steps.append(step3)

        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.EXPLANATION,
            title="Apply Newton's Second Law",
            description="F_net = ma. Use this to find acceleration or the unknown force.",
            learning_objective="Apply F = ma",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
        )
        steps.append(step4)

        return steps

    async def _solve_circular_motion(self, analysis: PhysicsProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for circular motion problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Circular Motion Basics",
            description="In circular motion, an object moves in a circle at constant speed. The velocity direction changes, so there IS acceleration!",
            learning_objective="Understand centripetal acceleration",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.PHYSICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Centripetal Force",
            description="Centripetal force points toward the center: F_c = mv²/r. This force is needed to keep the object in circular path.",
            learning_objective="Know centripetal force equation",
            difficulty=DifficultyLevel.REMEMBER,
            subject=Subject.PHYSICS,
        )
        steps.append(step2)

        return steps

    async def _solve_energy(self, analysis: PhysicsProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for energy problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Identify Energy Types",
            description="What types of energy are present? Kinetic (KE = ½mv²), Potential (PE = mgh), etc.",
            learning_objective="Recognize energy forms",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.PHYSICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Energy Conservation",
            description="Total mechanical energy is conserved (if no friction). E_initial = E_final",
            learning_objective="Apply energy conservation",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Solve for Unknown",
            description="Use energy conservation equation to find the missing quantity.",
            learning_objective="Complete solution",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
        )
        steps.append(step3)

        return steps

    async def _solve_waves(self, analysis: PhysicsProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for wave problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Wave Properties",
            description="Key properties: wavelength (λ), frequency (f), wave speed (v), amplitude (A), period (T)",
            learning_objective="Know wave terminology",
            difficulty=DifficultyLevel.REMEMBER,
            subject=Subject.PHYSICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Wave Equation",
            description="The fundamental wave equation: v = fλ (speed = frequency × wavelength)",
            learning_objective="Know wave equation",
            difficulty=DifficultyLevel.REMEMBER,
            subject=Subject.PHYSICS,
        )
        steps.append(step2)

        return steps

    async def _solve_electricity(self, analysis: PhysicsProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for electricity problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Circuit Analysis",
            description="Identify the circuit configuration. Is it series, parallel, or mixed?",
            learning_objective="Analyze circuits",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.PHYSICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Apply Ohm's Law",
            description="V = IR (Voltage = Current × Resistance). Use this with Kirchhoff's laws.",
            learning_objective="Apply Ohm's law",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.PHYSICS,
        )
        steps.append(step2)

        return steps

    async def _solve_magnetism(self, analysis: PhysicsProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for magnetism problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Magnetic Force",
            description="A moving charge in a magnetic field experiences a force: F = qvB sin(θ)",
            learning_objective="Know magnetic force equation",
            difficulty=DifficultyLevel.REMEMBER,
            subject=Subject.PHYSICS,
        )
        steps.append(step1)

        return steps

    # ============================================================
    # HELPER METHODS
    # ============================================================

    async def _detect_problem_type(self, problem: str) -> PhysicsProblemType:
        """Detect the type of physics problem from text."""
        problem_lower = problem.lower()

        # Most specific first: a force, energy or circuit problem often also
        # mentions velocity, acceleration or time, so kinematics is checked
        # last (and is the default).
        if any(kw in problem_lower for kw in ["circular", "orbit", "centripetal"]):
            return PhysicsProblemType.CIRCULAR_MOTION

        if any(kw in problem_lower for kw in ["electric", "charge", "current", "voltage", "circuit"]):
            return PhysicsProblemType.ELECTRICITY

        if any(kw in problem_lower for kw in ["magnetic", "magnet", "field"]):
            return PhysicsProblemType.MAGNETISM

        if any(kw in problem_lower for kw in ["wave", "frequency", "wavelength", "sound"]):
            return PhysicsProblemType.WAVES

        if any(kw in problem_lower for kw in ["energy", "kinetic", "potential", "conserve"]):
            return PhysicsProblemType.ENERGY

        if any(kw in problem_lower for kw in ["force", "newton", "f=ma", "weight"]):
            return PhysicsProblemType.DYNAMICS

        if any(kw in problem_lower for kw in ["velocity", "acceleration", "time", "motion"]):
            return PhysicsProblemType.KINEMATICS

        return PhysicsProblemType.KINEMATICS  # Default

    def _estimate_difficulty(
        self, problem: str, problem_type: PhysicsProblemType
    ) -> int:
        """Estimate problem difficulty (1-5)."""
        base_difficulty = {
            PhysicsProblemType.KINEMATICS: 2,
            PhysicsProblemType.DYNAMICS: 3,
            PhysicsProblemType.CIRCULAR_MOTION: 4,
            PhysicsProblemType.ENERGY: 3,
            PhysicsProblemType.WAVES: 3,
            PhysicsProblemType.ELECTRICITY: 3,
            PhysicsProblemType.MAGNETISM: 4,
        }.get(problem_type, 3)

        if "vector" in problem.lower():
            base_difficulty += 1

        return min(5, max(1, base_difficulty))

    async def _extract_concepts(
        self, problem: str, problem_type: PhysicsProblemType
    ) -> List[str]:
        """Extract concepts involved in the problem."""
        type_concepts = {
            PhysicsProblemType.KINEMATICS: ["motion", "velocity", "acceleration", "equations of motion"],
            PhysicsProblemType.DYNAMICS: ["forces", "Newton's laws", "acceleration"],
            PhysicsProblemType.CIRCULAR_MOTION: ["circular motion", "centripetal force", "angular velocity"],
            PhysicsProblemType.ENERGY: ["kinetic energy", "potential energy", "conservation"],
            PhysicsProblemType.WAVES: ["waves", "frequency", "wavelength", "wave speed"],
            PhysicsProblemType.ELECTRICITY: ["electric fields", "circuits", "current", "voltage"],
            PhysicsProblemType.MAGNETISM: ["magnetic fields", "moving charges", "force"],
        }
        return type_concepts.get(problem_type, [])

    async def _extract_given_values(self, problem: str) -> Dict[str, str]:
        """Extract given values and units from problem."""
        # This is a simplified version; would need more sophisticated parsing
        values = {}
        if "m/s" in problem or "v =" in problem.lower():
            values["velocity"] = "m/s"
        if "a =" in problem.lower() or "m/s²" in problem:
            values["acceleration"] = "m/s²"
        if "kg" in problem:
            values["mass"] = "kg"
        if "m" in problem:
            values["distance"] = "m"
        return values

    def _determine_find_value(self, problem: str, problem_type: PhysicsProblemType) -> str:
        """Determine what the problem is asking to find."""
        problem_lower = problem.lower()
        
        if "velocity" in problem_lower or "speed" in problem_lower:
            return "velocity (m/s)"
        if "acceleration" in problem_lower:
            return "acceleration (m/s²)"
        if "time" in problem_lower:
            return "time (s)"
        if "distance" in problem_lower or "displacement" in problem_lower:
            return "distance (m)"
        if "force" in problem_lower:
            return "force (N)"
        if "energy" in problem_lower:
            return "energy (J)"
        
        return "Unknown"

    def _get_equations_needed(self, problem_type: PhysicsProblemType) -> List[str]:
        """Get physics equations needed for the problem type."""
        equations = {
            PhysicsProblemType.KINEMATICS: ["v = u + at", "s = ut + ½at²", "v² = u² + 2as"],
            PhysicsProblemType.DYNAMICS: ["F = ma", "F_friction = μN"],
            PhysicsProblemType.CIRCULAR_MOTION: ["F_c = mv²/r", "ω = v/r"],
            PhysicsProblemType.ENERGY: ["KE = ½mv²", "PE = mgh", "E_total = KE + PE"],
            PhysicsProblemType.WAVES: ["v = fλ", "f = 1/T"],
            PhysicsProblemType.ELECTRICITY: ["V = IR", "P = VI"],
            PhysicsProblemType.MAGNETISM: ["F = qvB sin(θ)"],
        }
        return equations.get(problem_type, [])

    def _determine_solution_method(
        self, problem: str, problem_type: PhysicsProblemType
    ) -> str:
        """Determine the primary solution method."""
        methods = {
            PhysicsProblemType.KINEMATICS: "Use kinematic equations",
            PhysicsProblemType.DYNAMICS: "Draw FBD, find net force, apply F=ma",
            PhysicsProblemType.CIRCULAR_MOTION: "Apply centripetal force equation",
            PhysicsProblemType.ENERGY: "Apply energy conservation",
            PhysicsProblemType.WAVES: "Use wave equation v=fλ",
            PhysicsProblemType.ELECTRICITY: "Apply Ohm's law and Kirchhoff's laws",
            PhysicsProblemType.MAGNETISM: "Apply magnetic force equation",
        }
        return methods.get(problem_type, "Problem-specific approach")

    def _get_common_errors(self, problem_type: PhysicsProblemType) -> List[str]:
        """Get common student errors for a problem type."""
        errors = {
            PhysicsProblemType.KINEMATICS: [
                "Confusing velocity and acceleration",
                "Wrong equation choice",
                "Sign errors with direction",
            ],
            PhysicsProblemType.DYNAMICS: [
                "Missing forces in FBD",
                "Wrong direction for friction",
                "Forgetting to use vector addition",
            ],
            PhysicsProblemType.ENERGY: [
                "Forgetting energy is conserved",
                "Unit conversion errors",
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

        if student_clean == expected_clean:
            return True

        # Try numeric comparison
        try:
            # Extract numbers from both strings
            import re
            student_num = float(re.search(r"[\d.]+", student_answer).group())
            expected_num = float(re.search(r"[\d.]+", expected_answer).group())
            # Allow 5% tolerance for physics calculations
            tolerance = abs(expected_num) * 0.05 + 0.001
            return abs(student_num - expected_num) < tolerance
        except (ValueError, AttributeError):
            pass

        return False

    def _check_units(self, response: str) -> bool:
        """Check if response includes units."""
        units = ["m", "kg", "s", "n", "j", "w", "hz", "m/s", "m/s²", "c", "f", "v", "a"]
        response_lower = response.lower()
        return any(unit in response_lower for unit in units)
