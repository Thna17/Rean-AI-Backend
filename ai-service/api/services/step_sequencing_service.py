"""
Step Sequencing Service - Multi-step Interactive Teaching Engine

Orchestrates the step-by-step teaching experience:
- Analyzes student problems
- Generates multi-step teaching plans
- Evaluates student responses
- Routes to next steps adaptively
- Follows Socratic method (guide, don't answer)

Integration points:
- Knowledge Graph (concept retrieval)
- Model Gateway (LLM evaluation)
- Graph-CAG pipeline (problem analysis)
"""

import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from api.models.teaching_step import (
    DifficultyLevel,
    EvaluationResult,
    InteractionConfig,
    StepType,
    Subject,
    TeachingPlan,
    TeachingStep,
    VisualizationConfig,
    VisualizationType,
)

logger = logging.getLogger(__name__)

# Import expert services
from api.services.math_expert_service import MathExpertService
from api.services.physics_expert_service import PhysicsExpertService
from api.services.chemistry_expert_service import ChemistryExpertService


class MathStepSequence(Enum):
    """Predefined step sequences for math problems"""
    BASIC_EQUATION = "basic_equation"           # Linear equations
    QUADRATIC = "quadratic"                     # Quadratic equations
    GEOMETRY_TRIANGLE = "geometry_triangle"     # Triangle problems
    GEOMETRY_CIRCLE = "geometry_circle"         # Circle problems
    POLYNOMIAL = "polynomial"                   # Polynomial operations
    FUNCTION = "function"                       # Function concepts


class PhysicsStepSequence(Enum):
    """Predefined step sequences for physics problems"""
    KINEMATICS = "kinematics"                   # Motion problems
    DYNAMICS = "dynamics"                       # Force and motion
    ENERGY = "energy"                           # Energy conservation
    CIRCULAR_MOTION = "circular_motion"         # Circular motion
    WAVES = "waves"                             # Wave phenomena
    ELECTROSTATICS = "electrostatics"           # Electric charges


class ChemistryStepSequence(Enum):
    """Predefined step sequences for chemistry problems"""
    BONDING = "bonding"                         # Chemical bonding
    REACTIONS = "reactions"                     # Chemical reactions
    STOICHIOMETRY = "stoichiometry"             # Stoichiometry
    EQUILIBRIUM = "equilibrium"                 # Chemical equilibrium
    REDOX = "redox"                             # Redox reactions
    SOLUTIONS = "solutions"                     # Solution chemistry


class StepSequencingService:
    """Service for generating and managing step-by-step teaching plans.
    
    Generates adaptive multi-step lessons that follow the Socratic method,
    evaluates student responses, and routes to appropriate next steps.
    """
    
    def __init__(self, kg_service=None, model_gateway=None):
        """Initialize the step sequencing service.
        
        Args:
            kg_service: Knowledge Graph service for concept retrieval
            model_gateway: Model Gateway for LLM evaluation
        """
        self.kg_service = kg_service
        self.model_gateway = model_gateway
        self.service_name = "step_sequencing"
        
        # Initialize subject expert services
        self.math_expert = MathExpertService(kg_service, model_gateway)
        self.physics_expert = PhysicsExpertService(kg_service, model_gateway)
        self.chemistry_expert = ChemistryExpertService(kg_service, model_gateway)
    
    async def generate_teaching_plan(
        self,
        problem: str,
        subject: Subject,
        grade_level: int,
        learning_style: Optional[str] = None,
        include_hints: bool = True,
        difficulty_preference: Optional[DifficultyLevel] = None,
        max_steps: int = 8,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TeachingPlan:
        """Generate a complete multi-step teaching plan for a problem.
        
        Args:
            problem: Student's problem/question text
            subject: Subject domain (mathematics, physics, chemistry)
            grade_level: Grade level (10-12)
            learning_style: Student learning style (visual, analytical, kinesthetic)
            include_hints: Whether to include hints in the plan
            difficulty_preference: Preferred difficulty level
            max_steps: Maximum number of steps to generate (1-20)
            metadata: Additional context
            
        Returns:
            TeachingPlan with complete multi-step lesson
            
        Raises:
            ValueError: If problem or parameters are invalid
        """
        metadata = metadata or {}
        logger.info(
            "Generating teaching plan",
            extra={
                "subject": subject.value,
                "grade_level": grade_level,
                "learning_style": learning_style,
                "max_steps": max_steps,
            }
        )
        
        try:
            # Step 1: Analyze the problem
            analysis = await self._analyze_problem(problem, subject, grade_level, metadata)
            logger.debug(f"Problem analysis: {analysis}")
            
            # Step 2: Generate steps based on analysis
            steps = await self._generate_steps(
                problem=problem,
                analysis=analysis,
                subject=subject,
                grade_level=grade_level,
                learning_style=learning_style,
                difficulty_preference=difficulty_preference,
                include_hints=include_hints,
                max_steps=max_steps,
            )
            
            if not steps:
                raise ValueError("Failed to generate any teaching steps")
            
            logger.info(f"Generated {len(steps)} teaching steps")
            
            # Step 2.5: Enrich steps with concept graph from KG
            target_concepts = analysis.get("target_concepts", [])
            if self.kg_service and target_concepts:
                steps = await self._enrich_steps_with_kg(
                    steps, target_concepts, analysis
                )
            
            # Step 3: Create adaptive rules
            adaptive_rules = self._create_adaptive_rules(steps, subject, learning_style)
            
            # Step 4: Get prerequisite concepts from KG
            prerequisite_concepts = analysis.get("prerequisites", [])
            if self.kg_service and target_concepts:
                # Fetch prerequisites for target concepts from KG
                for concept in target_concepts:
                    try:
                        prereqs = await self.kg_service.get_prerequisites(concept)
                        prerequisite_concepts.extend(prereqs)
                    except Exception as e:
                        logger.debug(f"Failed to fetch prerequisites for {concept}: {e}")
                # Remove duplicates
                prerequisite_concepts = list(set(prerequisite_concepts))
            
            # Step 5: Assemble the plan
            plan = TeachingPlan(
                id=str(uuid.uuid4()),
                problem=problem,
                subject=subject,
                grade_level=grade_level,
                steps=steps,
                adaptive_rules=adaptive_rules,
                learning_style=learning_style,
                prerequisite_concepts=prerequisite_concepts,
                target_concepts=analysis.get("target_concepts", []),
                version=1,
                metadata=metadata,
            )
            
            logger.info(f"Teaching plan created: {plan.id}")
            return plan
            
        except Exception as e:
            logger.error(f"Error generating teaching plan: {str(e)}", exc_info=True)
            raise
    
    async def evaluate_step_response(
        self,
        step: TeachingStep,
        student_response: str,
        response_type: str = "text",
        context: Optional[Dict[str, Any]] = None,
    ) -> EvaluationResult:
        """Evaluate a student's response to a teaching step.
        
        Args:
            step: The teaching step being answered
            student_response: Student's response text
            response_type: Type of response (text, multiple_choice, numeric, draw)
            context: Additional context (hints used, previous answers, etc.)
            
        Returns:
            EvaluationResult with feedback and next step routing
        """
        context = context or {}
        logger.info(
            "Evaluating step response",
            extra={"step_id": step.id, "response_type": response_type}
        )
        
        try:
            start_time = datetime.utcnow()
            
            # If step has no interaction, evaluation is trivial
            if step.interaction is None:
                logger.warning(f"Step {step.id} has no interaction defined")
                return EvaluationResult(
                    is_correct=True,
                    condition="correct",
                    confidence=1.0,
                    feedback_message="Step completed.",
                    evaluation_time_ms=int((datetime.utcnow() - start_time).total_seconds() * 1000),
                    model_used="none",
                )
            
            # Determine if response is correct
            is_correct = await self._evaluate_response(
                step.interaction,
                student_response,
                response_type,
                context,
            )
            
            # Generate appropriate feedback
            feedback_result = await self._generate_feedback(
                step=step,
                is_correct=is_correct,
                student_response=student_response,
                context=context,
            )
            
            evaluation_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Determine routing
            condition = "correct" if is_correct else "incorrect"
            next_step_id = step.get_next_step_id()
            
            # Apply branching rules
            for rule in step.branching_rules:
                if rule.condition == condition:
                    next_step_id = rule.target_step_id
                    break
            
            result = EvaluationResult(
                is_correct=is_correct,
                condition=condition,
                confidence=feedback_result.get("confidence", 0.85),
                feedback_message=feedback_result.get("feedback", ""),
                explanation=feedback_result.get("explanation"),
                next_step_id=next_step_id,
                should_offer_hint=not is_correct and step.interaction.hint_text is not None,
                hint_text=step.interaction.hint_text if not is_correct else None,
                evaluation_time_ms=evaluation_time_ms,
                model_used=feedback_result.get("model_used", "rule_based"),
            )
            
            logger.info(f"Evaluation result: is_correct={is_correct}, confidence={result.confidence}")
            return result
            
        except Exception as e:
            logger.error(f"Error evaluating step response: {str(e)}", exc_info=True)
            raise
    
    def get_next_step(
        self,
        plan: TeachingPlan,
        current_step_id: str,
        evaluation_result: EvaluationResult,
    ) -> Optional[TeachingStep]:
        """Get the next step based on evaluation result.
        
        Args:
            plan: The teaching plan
            current_step_id: Current step ID
            evaluation_result: Result of evaluating current step
            
        Returns:
            Next TeachingStep, or None if plan complete
        """
        if evaluation_result.next_step_id:
            return plan.get_step_by_id(evaluation_result.next_step_id)
        
        # Fallback: try to get next sequential step
        current_step = plan.get_step_by_id(current_step_id)
        if current_step is None:
            return None
        
        # Find next step by step number
        for step in plan.steps:
            if step.step_number == current_step.step_number + 1:
                return step
        
        return None  # No more steps
    
    def _create_adaptive_rules(
        self,
        steps: List[TeachingStep],
        subject: Subject,
        learning_style: Optional[str],
    ) -> Dict[str, Any]:
        """Create adaptive routing rules for the teaching plan.
        
        Args:
            steps: List of teaching steps
            subject: Subject domain
            learning_style: Student learning style
            
        Returns:
            Dictionary of adaptive routing rules
        """
        rules = {
            "version": 1,
            "subject": subject.value,
            "learning_style": learning_style or "mixed",
            "branching_strategy": "evaluation_based",
            "hint_strategy": "offer_on_wrong",
            "retry_limit": 3,
            "step_timeout_seconds": 300,
        }
        
        # Subject-specific rules
        if subject == Subject.MATHEMATICS:
            rules["verification_strategy"] = "symbolic_and_numerical"
            rules["simplification_required"] = True
        elif subject == Subject.PHYSICS:
            rules["verification_strategy"] = "formula_and_calculation"
            rules["units_required"] = True
        elif subject == Subject.CHEMISTRY:
            rules["verification_strategy"] = "stoichiometry"
            rules["balanced_equation_required"] = True
        
        return rules
    
    async def _enrich_steps_with_kg(
        self,
        steps: List[TeachingStep],
        target_concepts: List[str],
        analysis: Dict[str, Any],
    ) -> List[TeachingStep]:
        """Enrich teaching steps with knowledge graph data (concept maps, prerequisites).
        
        Args:
            steps: List of teaching steps to enrich
            target_concepts: Target concepts for the problem
            analysis: Problem analysis dictionary
            
        Returns:
            Enriched list of teaching steps with concept_graph populated
        """
        if not self.kg_service or not target_concepts:
            return steps
        
        try:
            # Fetch prerequisites and misconceptions for each target concept
            for concept in target_concepts:
                try:
                    # Get prerequisites for this concept
                    prerequisites = await self.kg_service.get_prerequisites(concept)
                    
                    # Get misconceptions for this concept
                    misconceptions = await self.kg_service.get_misconceptions(concept)
                    
                    # Get next concepts (what builds on this)
                    next_concepts = await self.kg_service.get_next_concepts(concept)
                    
                    # Build concept graph
                    concept_graph = {
                        "concept": concept,
                        "prerequisites": prerequisites,
                        "misconceptions": misconceptions,
                        "next_concepts": next_concepts,
                    }
                    
                    # Add to first step's concept graph
                    if steps:
                        if steps[0].concept_graph is None:
                            steps[0].concept_graph = {}
                        
                        if "concepts" not in steps[0].concept_graph:
                            steps[0].concept_graph["concepts"] = []
                        
                        steps[0].concept_graph["concepts"].append(concept_graph)
                    
                    logger.debug(f"Enriched concept {concept} with KG data")
                    
                except Exception as e:
                    logger.debug(f"Failed to enrich concept {concept}: {e}")
            
            # Add overall concept graph to first step
            if steps and steps[0].concept_graph:
                steps[0].concept_graph["target_concepts"] = target_concepts
                steps[0].concept_graph["learning_path"] = analysis.get("suggested_sequence", "unknown")
            
            logger.info(f"Enriched {len(steps)} steps with knowledge graph data")
            
        except Exception as e:
            logger.warning(f"Error enriching steps with KG data: {e}")
        
        return steps
    
    # Private helper methods
    
    async def _analyze_problem(
        self,
        problem: str,
        subject: Subject,
        grade_level: int,
        metadata: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Analyze student problem to extract key concepts and structure.
        
        Args:
            problem: Problem text
            subject: Subject domain
            grade_level: Grade level
            metadata: Additional context
            
        Returns:
            Analysis dictionary with problem structure
        """
        logger.debug(f"Analyzing problem: {problem[:100]}...")
        
        # Basic analysis
        analysis = {
            "problem_type": metadata.get("problem_type", "general"),
            "prerequisites": [],
            "target_concepts": [],
            "suggested_sequence": None,
        }
        
        # Subject-specific analysis
        if subject == Subject.MATHEMATICS:
            analysis = self._analyze_math_problem(problem, analysis)
        elif subject == Subject.PHYSICS:
            analysis = self._analyze_physics_problem(problem, analysis)
        elif subject == Subject.CHEMISTRY:
            analysis = self._analyze_chemistry_problem(problem, analysis)
        
        return analysis
    
    def _analyze_math_problem(self, problem: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze mathematics problem."""
        lower = problem.lower()
        
        if "x" in lower or "equation" in lower:
            analysis["suggested_sequence"] = MathStepSequence.BASIC_EQUATION
            analysis["target_concepts"] = ["variable", "equation_solving", "inverse_operations"]
        elif "triangle" in lower or "angle" in lower:
            analysis["suggested_sequence"] = MathStepSequence.GEOMETRY_TRIANGLE
            analysis["target_concepts"] = ["triangle_properties", "angle_sum", "trigonometry"]
        elif "circle" in lower:
            analysis["suggested_sequence"] = MathStepSequence.GEOMETRY_CIRCLE
            analysis["target_concepts"] = ["circle_properties", "radius", "circumference"]
        else:
            analysis["target_concepts"] = ["problem_solving"]
        
        return analysis
    
    def _analyze_physics_problem(self, problem: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze physics problem."""
        lower = problem.lower()
        
        if "force" in lower or "newton" in lower:
            analysis["suggested_sequence"] = PhysicsStepSequence.DYNAMICS
            analysis["target_concepts"] = ["force", "newton_laws", "acceleration"]
        elif "speed" in lower or "velocity" in lower or "motion" in lower:
            analysis["suggested_sequence"] = PhysicsStepSequence.KINEMATICS
            analysis["target_concepts"] = ["velocity", "acceleration", "displacement"]
        elif "energy" in lower:
            analysis["suggested_sequence"] = PhysicsStepSequence.ENERGY
            analysis["target_concepts"] = ["kinetic_energy", "potential_energy", "conservation"]
        else:
            analysis["target_concepts"] = ["physics_problem_solving"]
        
        return analysis
    
    def _analyze_chemistry_problem(self, problem: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze chemistry problem."""
        lower = problem.lower()
        
        if "bond" in lower or "bonding" in lower:
            analysis["suggested_sequence"] = ChemistryStepSequence.BONDING
            analysis["target_concepts"] = ["chemical_bonding", "electron_configuration"]
        elif "reaction" in lower or "equation" in lower:
            analysis["suggested_sequence"] = ChemistryStepSequence.REACTIONS
            analysis["target_concepts"] = ["chemical_reactions", "stoichiometry", "balancing"]
        elif "equilibrium" in lower:
            analysis["suggested_sequence"] = ChemistryStepSequence.EQUILIBRIUM
            analysis["target_concepts"] = ["equilibrium", "le_chatelier"]
        else:
            analysis["target_concepts"] = ["chemistry_problem_solving"]
        
        return analysis
    
    async def _generate_steps(
        self,
        problem: str,
        analysis: Dict[str, Any],
        subject: Subject,
        grade_level: int,
        learning_style: Optional[str],
        difficulty_preference: Optional[DifficultyLevel],
        include_hints: bool,
        max_steps: int,
    ) -> List[TeachingStep]:
        """Generate teaching steps based on problem analysis.
        
        Routes to subject-specific experts for intelligent step generation.
        
        Args:
            problem: Problem text
            analysis: Problem analysis
            subject: Subject domain
            grade_level: Grade level
            learning_style: Student learning style
            difficulty_preference: Preferred difficulty
            include_hints: Include hints
            max_steps: Maximum steps
            
        Returns:
            List of TeachingStep objects
        """
        steps = []
        
        # Subject-specific step generation using expert services
        if subject == Subject.MATHEMATICS:
            steps = await self._generate_math_steps(
                problem, analysis, grade_level, learning_style, include_hints, max_steps
            )
        elif subject == Subject.PHYSICS:
            steps = await self._generate_physics_steps(
                problem, analysis, grade_level, learning_style, include_hints, max_steps
            )
        elif subject == Subject.CHEMISTRY:
            steps = await self._generate_chemistry_steps(
                problem, analysis, grade_level, learning_style, include_hints, max_steps
            )
        
        # Limit to max_steps
        if len(steps) > max_steps:
            steps = steps[:max_steps]
        
        return steps
    
    async def _generate_math_steps(
        self,
        problem: str,
        analysis: Dict[str, Any],
        grade_level: int,
        learning_style: Optional[str],
        include_hints: bool,
        max_steps: int,
    ) -> List[TeachingStep]:
        """Generate math-specific teaching steps using MathExpertService."""
        try:
            # Use expert service to analyze problem
            problem_analysis = await self.math_expert.analyze_problem(problem)
            
            # Generate expert-driven steps
            steps = await self.math_expert.generate_steps(problem_analysis, grade_level)
            
            logger.info(f"Generated {len(steps)} math steps using expert service")
            return steps
        except Exception as e:
            logger.error(f"Error generating math steps with expert: {e}")
            # Fall back to generic implementation
            return await self._generate_math_steps_fallback(
                problem, analysis, grade_level, learning_style, include_hints, max_steps
            )
    
    async def _generate_math_steps_fallback(
        self,
        problem: str,
        analysis: Dict[str, Any],
        grade_level: int,
        learning_style: Optional[str],
        include_hints: bool,
        max_steps: int,
    ) -> List[TeachingStep]:
        """Fallback generic math steps if expert fails."""
        # This is the original fallback implementation
        steps = []
        
        # Step 1: Understand the problem
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.QUESTION,
            title="Understand the Problem",
            description="Let's start by understanding what the problem is asking.",
            learning_objective="Identify the given information and what we need to find",
            subject=Subject.MATHEMATICS,
            difficulty=DifficultyLevel.UNDERSTAND,
            estimated_time_seconds=30,
            interaction=InteractionConfig(
                question_text=f"What is given in this problem and what do we need to find?\n\nProblem: {problem}",
                interaction_type="text_input",
                expected_answer=None,  # Open-ended
                hint_text="Look for 'given' and 'find' parts of the problem",
            ),
        ))
        
        # Step 2: Identify the method
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.EXPLANATION,
            title="Choose a Method",
            description="Now let's think about which method to use.",
            learning_objective="Select appropriate solving strategy",
            subject=Subject.MATHEMATICS,
            difficulty=DifficultyLevel.UNDERSTAND,
            estimated_time_seconds=30,
            board_actions=[],
        ))
        
        # Step 3: Work through the solution (visualization)
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.VISUALIZATION,
            title="Work Through the Solution",
            description="Let's solve this step by step.",
            learning_objective="Perform calculations correctly",
            subject=Subject.MATHEMATICS,
            difficulty=DifficultyLevel.APPLY,
            estimated_time_seconds=45,
            board_actions=[],
        ))
        
        # Step 4: Verify the solution
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.CHECK,
            title="Check Your Answer",
            description="Let's verify that our solution is correct.",
            learning_objective="Validate solution and understand why it works",
            subject=Subject.MATHEMATICS,
            difficulty=DifficultyLevel.UNDERSTAND,
            estimated_time_seconds=30,
            interaction=InteractionConfig(
                question_text="Does our solution make sense? Why or why not?",
                interaction_type="text_input",
                hint_text="Check if the solution satisfies the original equation",
            ),
        ))
        
        return steps[:max_steps]
    
    async def _generate_physics_steps(
        self,
        problem: str,
        analysis: Dict[str, Any],
        grade_level: int,
        learning_style: Optional[str],
        include_hints: bool,
        max_steps: int,
    ) -> List[TeachingStep]:
        """Generate physics-specific teaching steps using PhysicsExpertService."""
        try:
            # Use expert service to analyze problem
            problem_analysis = await self.physics_expert.analyze_problem(problem)
            
            # Generate expert-driven steps
            steps = await self.physics_expert.generate_steps(problem_analysis, grade_level)
            
            logger.info(f"Generated {len(steps)} physics steps using expert service")
            return steps
        except Exception as e:
            logger.error(f"Error generating physics steps with expert: {e}")
            # Fall back to generic implementation
            return await self._generate_physics_steps_fallback(
                problem, analysis, grade_level, learning_style, include_hints, max_steps
            )
    
    async def _generate_physics_steps_fallback(
        self,
        problem: str,
        analysis: Dict[str, Any],
        grade_level: int,
        learning_style: Optional[str],
        include_hints: bool,
        max_steps: int,
    ) -> List[TeachingStep]:
        """Fallback generic physics steps if expert fails."""
        # This is the original fallback implementation
        steps = []
        
        # Step 1: Visualize the situation
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.VISUALIZATION,
            title="Visualize the Physical Situation",
            description="Let's draw what's happening in this problem.",
            learning_objective="Develop mental model of the physical situation",
            subject=Subject.PHYSICS,
            difficulty=DifficultyLevel.UNDERSTAND,
            estimated_time_seconds=30,
            board_actions=[],
        ))
        
        # Step 2: Identify forces/quantities
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.QUESTION,
            title="Identify Key Quantities",
            description="What forces or quantities are involved?",
            learning_objective="Extract relevant physics quantities from problem",
            subject=Subject.PHYSICS,
            difficulty=DifficultyLevel.UNDERSTAND,
            estimated_time_seconds=30,
            interaction=InteractionConfig(
                question_text=f"What forces or quantities are mentioned in this problem?\n\nProblem: {problem}",
                interaction_type="text_input",
                hint_text="Look for masses, velocities, forces, distances, etc.",
            ),
        ))
        
        # Step 3: Apply physics principles
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.EXPLANATION,
            title="Apply Physics Principles",
            description="Which physics principles apply here?",
            learning_objective="Select and apply relevant physics laws",
            subject=Subject.PHYSICS,
            difficulty=DifficultyLevel.APPLY,
            estimated_time_seconds=45,
            board_actions=[],
        ))
        
        # Step 4: Calculate
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.VISUALIZATION,
            title="Perform Calculations",
            description="Let's work through the math.",
            learning_objective="Execute calculations correctly",
            subject=Subject.PHYSICS,
            difficulty=DifficultyLevel.APPLY,
            estimated_time_seconds=45,
            board_actions=[],
        ))
        
        # Step 5: Interpret results
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.CHECK,
            title="Interpret the Result",
            description="What does this answer tell us?",
            learning_objective="Connect mathematical result to physical meaning",
            subject=Subject.PHYSICS,
            difficulty=DifficultyLevel.UNDERSTAND,
            estimated_time_seconds=30,
            interaction=InteractionConfig(
                question_text="What does this result mean physically? Is it reasonable?",
                interaction_type="text_input",
                hint_text="Check units and reasonableness of magnitude",
            ),
        ))
        
        return steps[:max_steps]
    
    async def _generate_chemistry_steps(
        self,
        problem: str,
        analysis: Dict[str, Any],
        grade_level: int,
        learning_style: Optional[str],
        include_hints: bool,
        max_steps: int,
    ) -> List[TeachingStep]:
        """Generate chemistry-specific teaching steps using ChemistryExpertService."""
        try:
            # Use expert service to analyze problem
            problem_analysis = await self.chemistry_expert.analyze_problem(problem)
            
            # Generate expert-driven steps
            steps = await self.chemistry_expert.generate_steps(problem_analysis, grade_level)
            
            logger.info(f"Generated {len(steps)} chemistry steps using expert service")
            return steps
        except Exception as e:
            logger.error(f"Error generating chemistry steps with expert: {e}")
            # Fall back to generic implementation
            return await self._generate_chemistry_steps_fallback(
                problem, analysis, grade_level, learning_style, include_hints, max_steps
            )
    
    async def _generate_chemistry_steps_fallback(
        self,
        problem: str,
        analysis: Dict[str, Any],
        grade_level: int,
        learning_style: Optional[str],
        include_hints: bool,
        max_steps: int,
    ) -> List[TeachingStep]:
        """Fallback generic chemistry steps if expert fails."""
        # This is the original fallback implementation
        steps = []
        
        # Step 1: Identify reactants and products
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.QUESTION,
            title="Identify Reactants and Products",
            description="What substances are involved in this reaction?",
            learning_objective="Recognize and name chemical substances",
            subject=Subject.CHEMISTRY,
            difficulty=DifficultyLevel.REMEMBER,
            estimated_time_seconds=30,
            interaction=InteractionConfig(
                question_text=f"What are the reactants and products in this reaction?\n\nProblem: {problem}",
                interaction_type="text_input",
                hint_text="Identify what you start with (reactants) and what you end with (products)",
            ),
        ))
        
        # Step 2: Visualize molecular structures
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.VISUALIZATION,
            title="Visualize Molecular Structures",
            description="Let's draw the molecules involved.",
            learning_objective="Understand molecular composition",
            subject=Subject.CHEMISTRY,
            difficulty=DifficultyLevel.UNDERSTAND,
            estimated_time_seconds=30,
            visualizations=[
                VisualizationConfig(
                    type=VisualizationType.MOLECULE,
                    data={"molecules": []},
                    title="Molecular Structures",
                )
            ],
        ))
        
        # Step 3: Balance the equation
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.QUESTION,
            title="Balance the Equation",
            description="Make sure atoms are balanced on both sides.",
            learning_objective="Balance chemical equations",
            subject=Subject.CHEMISTRY,
            difficulty=DifficultyLevel.APPLY,
            estimated_time_seconds=45,
            interaction=InteractionConfig(
                question_text="Write the balanced chemical equation.",
                interaction_type="text_input",
                hint_text="Count atoms of each element on both sides. Adjust coefficients to balance.",
            ),
        ))
        
        # Step 4: Check stoichiometry
        steps.append(TeachingStep(
            id=str(uuid.uuid4()),
            step_number=len(steps) + 1,
            type=StepType.CHECK,
            title="Verify Stoichiometry",
            description="Is the equation properly balanced?",
            learning_objective="Verify equation balance using stoichiometry",
            subject=Subject.CHEMISTRY,
            difficulty=DifficultyLevel.ANALYZE,
            estimated_time_seconds=30,
            interaction=InteractionConfig(
                question_text="Count atoms on each side. Is the equation balanced?",
                interaction_type="text_input",
                hint_text="Create a table: element | left side | right side",
            ),
        ))
        
        return steps[:max_steps]
    
    async def _evaluate_response(
        self,
        interaction: InteractionConfig,
        student_response: str,
        response_type: str,
        context: Dict[str, Any],
    ) -> bool:
        """Evaluate if a student response is correct.
        
        Args:
            interaction: Interaction configuration
            student_response: Student's response
            response_type: Type of response
            context: Additional context
            
        Returns:
            True if response is correct
        """
        # Simple pattern matching for now
        if interaction.expected_answer is None:
            # Open-ended response - always accept
            return True
        
        # Case-insensitive comparison
        return student_response.lower().strip() == interaction.expected_answer.lower().strip()
    
    async def _generate_feedback(
        self,
        step: TeachingStep,
        is_correct: bool,
        student_response: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate feedback for a student response.
        
        Args:
            step: The teaching step
            is_correct: Whether response is correct
            student_response: Student's response
            context: Additional context
            
        Returns:
            Dictionary with feedback, explanation, and confidence
        """
        if is_correct:
            feedback = "Excellent! Your answer is correct. Well done!"
            explanation = "You've understood this step correctly."
            confidence = 0.95
        else:
            feedback = "Not quite right. Let me show you another way to think about this."
            explanation = f"Your response: '{student_response}' doesn't match what we're looking for."
            confidence = 0.7
        
        return {
            "feedback": feedback,
            "explanation": explanation,
            "confidence": confidence,
            "model_used": "rule_based",
        }
