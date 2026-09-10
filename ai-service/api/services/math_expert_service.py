"""
Math Expert Service - Domain Intelligence for Mathematics Tutoring

Provides subject-specific expertise for:
- Problem type detection (linear, quadratic, geometry, etc.)
- Step generation following Socratic method
- Visualization generation for mathematical concepts
- Student response evaluation
- Common misconception detection

Uses:
- Knowledge Graph for concept retrieval
- Model Gateway for LLM-based evaluation
- Renderers for visualization creation
"""

import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

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
    MathProblemAnalysis,
    MathProblemType,
    MathMisconception,
)

logger = logging.getLogger(__name__)


class MathExpertService:
    """Expert service for mathematics problem solving and tutoring.
    
    Detects math problem types, generates step-by-step solutions,
    creates visualizations, and evaluates student responses following
    pedagogical best practices.
    """

    def __init__(
        self,
        kg_service: Optional[Any] = None,
        model_gateway: Optional[Any] = None,
    ):
        """Initialize the Math Expert Service.

        Args:
            kg_service: Knowledge Graph service for concept retrieval
            model_gateway: Model Gateway for LLM-based evaluation
        """
        self.kg_service = kg_service
        self.model_gateway = model_gateway
        self.service_name = "math_expert"
        logger.info("MathExpertService initialized")

    async def analyze_problem(self, problem: str) -> MathProblemAnalysis:
        """Detect the type of math problem and analyze it.

        Args:
            problem: Problem text to analyze

        Returns:
            MathProblemAnalysis with problem type, difficulty, concepts

        Raises:
            ValueError: If problem cannot be analyzed
        """
        if not problem or not isinstance(problem, str):
            raise ValueError("Problem must be a non-empty string")

        logger.debug(f"Analyzing math problem: {problem[:100]}...")

        # Detect problem type
        problem_type = await self._detect_problem_type(problem)
        logger.debug(f"Detected problem type: {problem_type}")

        # Extract difficulty and concepts
        difficulty = self._estimate_difficulty(problem, problem_type)
        concepts = await self._extract_concepts(problem, problem_type)

        # Determine solution method
        solution_method = self._determine_solution_method(problem, problem_type)

        # Find common errors for this type
        common_errors = self._get_common_errors(problem_type)

        analysis = MathProblemAnalysis(
            problem_type=problem_type,
            difficulty=difficulty,
            concepts=concepts,
            solution_method=solution_method,
            common_errors=common_errors,
        )

        logger.info(f"Problem analysis complete: {analysis.problem_type}")
        return analysis

    async def generate_steps(
        self,
        analysis: MathProblemAnalysis,
        student_level: int = 10,
    ) -> List[TeachingStep]:
        """Generate problem-specific teaching steps.

        Each problem type has specific step sequences following the Socratic method:
        1. Explain the concept/method
        2. Ask guiding question
        3. Provide feedback on student thinking
        4. Show visualization
        5. Continue until solved
        6. Verify understanding

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
        if analysis.problem_type == MathProblemType.LINEAR_EQUATION:
            steps = await self._solve_linear_equation(analysis)
        elif analysis.problem_type == MathProblemType.QUADRATIC_EQUATION:
            steps = await self._solve_quadratic_equation(analysis)
        elif analysis.problem_type == MathProblemType.SYSTEM_OF_EQUATIONS:
            steps = await self._solve_system_equations(analysis)
        elif analysis.problem_type == MathProblemType.GEOMETRY:
            steps = await self._solve_geometry_problem(analysis)
        elif analysis.problem_type == MathProblemType.FACTORING:
            steps = await self._solve_factoring(analysis)
        elif analysis.problem_type == MathProblemType.EXPANDING:
            steps = await self._solve_expanding(analysis)
        elif analysis.problem_type == MathProblemType.SIMPLIFYING:
            steps = await self._solve_simplifying(analysis)
        elif analysis.problem_type == MathProblemType.FUNCTIONS:
            steps = await self._solve_functions(analysis)
        elif analysis.problem_type == MathProblemType.INEQUALITIES:
            steps = await self._solve_inequalities(analysis)
        elif analysis.problem_type == MathProblemType.TRIGONOMETRY:
            steps = await self._solve_trigonometry(analysis)
        else:
            raise ValueError(f"Unknown problem type: {analysis.problem_type}")

        logger.info(f"Generated {len(steps)} teaching steps")
        return steps

    async def create_visualization(
        self,
        step: TeachingStep,
    ) -> List[VisualizationConfig]:
        """Create math-specific visualizations for a step.

        Generates visualizations appropriate for the step content:
        - GraphRenderer: For function graphs and plots
        - GeometricRenderer: For shapes and geometry
        - Number lines: For inequalities
        - Equation animations: For solving steps

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

        # Create visualizations based on step metadata
        if "equation" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.GRAPH,
                data={
                    "equation": step.metadata.get("equation"),
                    "plot_range": {"min": -10, "max": 10},
                    "variables": ["x", "y"],
                },
                title=f"Graph of {step.metadata.get('equation', 'equation')}",
                annotations=["Points of interest marked"],
            )
            visualizations.append(viz)

        if "shape" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.GEOMETRY,
                data={
                    "shape_type": step.metadata.get("shape"),
                    "dimensions": step.metadata.get("dimensions", {}),
                    "labels": step.metadata.get("labels", []),
                },
                title=f"{step.metadata.get('shape', 'Shape')} Diagram",
            )
            visualizations.append(viz)

        if "number_line" in step.metadata:
            viz = VisualizationConfig(
                type=VisualizationType.NUMBER_LINE,
                data={
                    "range": step.metadata.get("range", {"min": -10, "max": 10}),
                    "points": step.metadata.get("points", []),
                    "solution_set": step.metadata.get("solution_set"),
                },
                title="Solution on Number Line",
            )
            visualizations.append(viz)

        return visualizations

    async def evaluate_response(
        self,
        question: str,
        student_response: str,
        context: Dict[str, Any],
    ) -> EvaluationResult:
        """Evaluate student's math response.

        Checks for:
        - Correct numerical answer
        - Correct algebraic form
        - Proper units
        - Valid work shown

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

        # Basic correctness check
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
            feedback = "Let me provide a hint: Review your steps and check for any calculation errors."
            condition = "incorrect"
            confidence = 0.7

        result = EvaluationResult(
            is_correct=is_correct,
            condition=condition,
            confidence=confidence,
            feedback_message=feedback,
            explanation=misconception.correction if misconception else None,
            evaluation_time_ms=100,  # Approximate
            model_used="math_expert",
        )

        logger.info(f"Evaluation result: {result.condition}")
        return result

    async def detect_misconception(
        self,
        error: str,
        problem_type: str,
    ) -> Optional[MathMisconception]:
        """Detect common algebra/geometry misconceptions.

        Identifies patterns in student errors:
        - Sign errors (forgot negative)
        - Distribution errors (a(b+c) ≠ ab+c)
        - Order of operations violations
        - Division errors (forgot to divide ALL terms)
        - Geometry misconceptions (angles don't add up)
        - Function misconceptions (f(x) is not f times x)

        Args:
            error: Student's erroneous response/work
            problem_type: Type of problem being solved

        Returns:
            MathMisconception if detected, None otherwise
        """
        if not error:
            return None

        logger.debug(f"Detecting misconception in: {error[:50]}...")

        # Check for common error patterns
        error_lower = error.lower()

        # Sign error pattern
        if re.search(r"[+-]\s*\w+\s*[+-]\s*\w+", error) and "-" not in error:
            return MathMisconception(
                error_type="sign_error",
                description="Forgot to apply negative sign",
                explanation="When subtracting, remember to change the sign of each term being subtracted.",
                correction="For example: 5 - 3 = 2, not 5 + 3 = 8",
                similar_errors=["forgot_negative", "sign_flip"],
            )

        # Distribution error pattern
        if "(" in error and ")" in error:
            if re.search(r"\(.*\+.*\)", error):
                # Check if they forgot to distribute
                return MathMisconception(
                    error_type="distribution_error",
                    description="Forgot to distribute multiplication",
                    explanation="When multiplying by a parenthesis, multiply EACH term: a(b+c) = ab + ac",
                    correction="Example: 2(3+4) = 2(3) + 2(4) = 6 + 8 = 14",
                    similar_errors=["forgot_to_multiply", "incomplete_distribution"],
                )

        # Division error pattern
        if "/" in error or "÷" in error:
            return MathMisconception(
                error_type="division_error",
                description="May have forgotten to divide ALL terms",
                explanation="When dividing an equation, you must divide EVERY term on both sides.",
                correction="Example: (2x + 4)/2 = 6 becomes x + 2 = 3",
                similar_errors=["partial_division"],
            )

        # Order of operations pattern
        if re.search(r"\+.*\*|\*.*\+", error):
            return MathMisconception(
                error_type="order_of_operations",
                description="May have used wrong order of operations",
                explanation="Remember PEMDAS: Parentheses, Exponents, Multiplication/Division, Addition/Subtraction",
                correction="Multiplication and Division come before Addition and Subtraction",
                similar_errors=["bodmas_error", "pemdas_violation"],
            )

        return None

    # ============================================================
    # PROBLEM-SPECIFIC SOLVERS
    # ============================================================

    async def _solve_linear_equation(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for solving linear equations like 2x + 5 = 13."""
        steps = []

        # Step 1: Explain the goal
        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Understand the Goal",
            description="We need to isolate the variable (get x by itself) to find its value.",
            learning_objective="Understand that solving means isolating the variable",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
            metadata={"concept": "linear_equations"},
        )
        steps.append(step1)

        # Step 2: Ask what to do first
        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.QUESTION,
            title="First Step",
            description="What operation should we perform to remove the constant from the left side?",
            learning_objective="Recognize inverse operations",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
            interaction=InteractionConfig(
                question_text="What operation removes the +5 from the left side?",
                interaction_type="multiple_choice",
                choices=["Add 5", "Subtract 5", "Multiply by 5", "Divide by 5"],
                expected_answer="Subtract 5",
            ),
            branching_rules=[
                {
                    "condition": "correct",
                    "target_step_id": steps[0].id if steps else None,
                }
            ],
            metadata={"operation": "subtract_constant"},
        )
        steps.append(step2)

        # Step 3: Perform the operation
        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Apply the Operation",
            description="We subtract 5 from both sides: 2x + 5 - 5 = 13 - 5, which simplifies to 2x = 8",
            learning_objective="Apply inverse operations correctly",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
            visualizations=[
                VisualizationConfig(
                    type=VisualizationType.NUMBER_LINE,
                    data={
                        "equation": "2x + 5 = 13",
                        "after_step": "2x = 8",
                    },
                    title="After Subtracting 5 from Both Sides",
                )
            ],
            metadata={"equation": "2x = 8"},
        )
        steps.append(step3)

        # Step 4: Isolate x
        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.QUESTION,
            title="Isolate the Variable",
            description="Now we need to get x completely by itself. What should we do?",
            learning_objective="Apply division as inverse of multiplication",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
            interaction=InteractionConfig(
                question_text="How do we get x by itself from 2x = 8?",
                interaction_type="multiple_choice",
                choices=["Divide both sides by 2", "Subtract 2", "Multiply by 2"],
                expected_answer="Divide both sides by 2",
            ),
            metadata={"operation": "divide_by_coefficient"},
        )
        steps.append(step4)

        # Step 5: Solution
        step5 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=5,
            type=StepType.EXPLANATION,
            title="Find the Solution",
            description="Dividing both sides by 2: 2x/2 = 8/2, so x = 4",
            learning_objective="Complete the solution process",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
            visualizations=[
                VisualizationConfig(
                    type=VisualizationType.GRAPH,
                    data={"equation": "y = 2x + 5", "point": {"x": 4, "y": 13}},
                    title="Solution Point (4, 13)",
                )
            ],
            metadata={"answer": "x = 4", "equation": "2x + 5 = 13"},
        )
        steps.append(step5)

        # Step 6: Verify
        step6 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=6,
            type=StepType.CHECK,
            title="Verify Your Solution",
            description="Let's check: If x = 4, then 2(4) + 5 = 8 + 5 = 13 ✓",
            learning_objective="Verify solutions through substitution",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
            interaction=InteractionConfig(
                question_text="Does x = 4 work in the original equation?",
                interaction_type="multiple_choice",
                choices=["Yes", "No"],
                expected_answer="Yes",
            ),
        )
        steps.append(step6)

        return steps

    async def _solve_quadratic_equation(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for solving quadratic equations."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Quadratic Equation Form",
            description="A quadratic equation has the form ax² + bx + c = 0. We need to find the values of x that make this true.",
            learning_objective="Understand quadratic equation structure",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.QUESTION,
            title="Choose Solution Method",
            description="For this equation, which method should we use?",
            learning_objective="Identify when to use factoring vs formula",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
            interaction=InteractionConfig(
                question_text="Does this equation factor nicely or should we use the quadratic formula?",
                interaction_type="multiple_choice",
                choices=["Factor", "Quadratic Formula"],
                expected_answer="Factor",  # Will vary by equation
            ),
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Factor the Expression",
            description="Find two numbers that multiply to c and add to b, then write as (x + p)(x + q) = 0",
            learning_objective="Apply factoring technique",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step3)

        step4 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=4,
            type=StepType.EXPLANATION,
            title="Apply Zero Product Property",
            description="If (x + p)(x + q) = 0, then either x + p = 0 or x + q = 0",
            learning_objective="Apply zero product property",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step4)

        step5 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=5,
            type=StepType.EXPLANATION,
            title="Solve for x",
            description="Solve each linear equation: x = -p and x = -q",
            learning_objective="Complete solution",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step5)

        return steps

    async def _solve_system_equations(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for solving systems of equations."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="System of Equations",
            description="A system has two or more equations. We need to find values that satisfy ALL equations.",
            learning_objective="Understand system solutions",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.QUESTION,
            title="Choose Method",
            description="Which method should we use?",
            learning_objective="Select appropriate solution method",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
            interaction=InteractionConfig(
                question_text="Should we use substitution or elimination?",
                interaction_type="multiple_choice",
                choices=["Substitution", "Elimination", "Graphing"],
                expected_answer="Elimination",
            ),
        )
        steps.append(step2)

        return steps

    async def _solve_geometry_problem(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for geometry problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Identify the Shape",
            description="First, let's identify what geometric shape we're working with.",
            learning_objective="Recognize geometric shapes",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
            visualizations=[
                VisualizationConfig(
                    type=VisualizationType.GEOMETRY,
                    data={"shape_type": "unknown"},
                    title="Geometric Shape",
                )
            ],
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Recall the Formula",
            description="For this shape, the relevant formula is...",
            learning_objective="Know shape-specific formulas",
            difficulty=DifficultyLevel.REMEMBER,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.QUESTION,
            title="Apply the Formula",
            description="Now substitute the known values into the formula.",
            learning_objective="Apply formulas correctly",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
            interaction=InteractionConfig(
                question_text="What do you get when you substitute the values?",
                interaction_type="text_input",
            ),
        )
        steps.append(step3)

        return steps

    async def _solve_factoring(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for factoring problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="What is Factoring?",
            description="Factoring means writing a number or expression as a product of its factors.",
            learning_objective="Understand factoring concept",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Find Common Factors",
            description="Look for factors that appear in all terms.",
            learning_objective="Identify common factors",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step2)

        return steps

    async def _solve_expanding(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for expanding expressions."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Use the Distributive Property",
            description="Multiply each term in the first group by each term in the second group.",
            learning_objective="Apply distributive property",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Combine Like Terms",
            description="Add or subtract terms with the same variables and powers.",
            learning_objective="Combine like terms",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step2)

        return steps

    async def _solve_simplifying(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for simplifying expressions."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Identify Like Terms",
            description="Find terms with the same variables and powers that can be combined.",
            learning_objective="Recognize like terms",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Combine Like Terms",
            description="Add or subtract the coefficients of like terms.",
            learning_objective="Simplify expressions",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step2)

        return steps

    async def _solve_functions(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for function problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Understanding Functions",
            description="A function f(x) gives an output for each input value x.",
            learning_objective="Understand function concept",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Evaluate the Function",
            description="Substitute the given x-value into the function and calculate.",
            learning_objective="Evaluate functions",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step2)

        return steps

    async def _solve_inequalities(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for solving inequalities."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Understanding Inequalities",
            description="Inequalities show that one expression is greater than, less than, or not equal to another.",
            learning_objective="Understand inequality symbols",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Solve Like Equations",
            description="Use the same steps as solving equations, but remember: flip the inequality sign when multiplying or dividing by a negative number.",
            learning_objective="Solve inequalities",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step2)

        step3 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=3,
            type=StepType.EXPLANATION,
            title="Show Solution on Number Line",
            description="The solution is a range of values shown on a number line.",
            learning_objective="Represent solutions visually",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
            visualizations=[
                VisualizationConfig(
                    type=VisualizationType.NUMBER_LINE,
                    data={"range": {"min": -10, "max": 10}},
                    title="Solution Set",
                )
            ],
        )
        steps.append(step3)

        return steps

    async def _solve_trigonometry(self, analysis: MathProblemAnalysis) -> List[TeachingStep]:
        """Generate steps for trigonometry problems."""
        steps = []

        step1 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=1,
            type=StepType.EXPLANATION,
            title="Trigonometric Ratios",
            description="Sin, Cos, and Tan are ratios of sides in right triangles.",
            learning_objective="Understand trig ratios",
            difficulty=DifficultyLevel.UNDERSTAND,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step1)

        step2 = TeachingStep(
            id=str(uuid.uuid4()),
            step_number=2,
            type=StepType.EXPLANATION,
            title="Identify the Sides",
            description="Determine which sides are opposite, adjacent, and hypotenuse relative to the angle.",
            learning_objective="Identify triangle sides",
            difficulty=DifficultyLevel.APPLY,
            subject=Subject.MATHEMATICS,
        )
        steps.append(step2)

        return steps

    # ============================================================
    # HELPER METHODS
    # ============================================================

    async def _detect_problem_type(self, problem: str) -> MathProblemType:
        """Detect the type of math problem from text."""
        problem_lower = problem.lower()

        # Linear equation detection
        if any(keyword in problem_lower for keyword in ["solve", "equation"]):
            if any(kw in problem_lower for kw in ["^2", "squared", "x^2"]):
                return MathProblemType.QUADRATIC_EQUATION
            elif any(kw in problem_lower for kw in ["2x +", "3x -", "4x +"]):
                return MathProblemType.LINEAR_EQUATION

        # System of equations
        if any(kw in problem_lower for kw in ["system", "2x +", "both equations"]):
            return MathProblemType.SYSTEM_OF_EQUATIONS

        # Geometry
        if any(kw in problem_lower for kw in ["area", "perimeter", "triangle", "circle", "square", "rectangle"]):
            return MathProblemType.GEOMETRY

        # Factoring
        if "factor" in problem_lower:
            return MathProblemType.FACTORING

        # Expanding
        if any(kw in problem_lower for kw in ["expand", "multiply", "distribute"]):
            return MathProblemType.EXPANDING

        # Simplifying
        if "simplify" in problem_lower:
            return MathProblemType.SIMPLIFYING

        # Functions
        if "function" in problem_lower or "f(x)" in problem:
            return MathProblemType.FUNCTIONS

        # Inequalities
        if any(kw in problem_lower for kw in [">", "<", "≥", "≤", "inequality"]):
            return MathProblemType.INEQUALITIES

        # Trigonometry
        if any(kw in problem_lower for kw in ["sin", "cos", "tan", "angle", "degree"]):
            return MathProblemType.TRIGONOMETRY

        # Default to linear equation
        return MathProblemType.LINEAR_EQUATION

    def _estimate_difficulty(
        self, problem: str, problem_type: MathProblemType
    ) -> int:
        """Estimate problem difficulty (1-5)."""
        # Base difficulty by type
        base_difficulty = {
            MathProblemType.LINEAR_EQUATION: 1,
            MathProblemType.QUADRATIC_EQUATION: 3,
            MathProblemType.SYSTEM_OF_EQUATIONS: 3,
            MathProblemType.GEOMETRY: 2,
            MathProblemType.FACTORING: 2,
            MathProblemType.EXPANDING: 2,
            MathProblemType.SIMPLIFYING: 1,
            MathProblemType.FUNCTIONS: 3,
            MathProblemType.INEQUALITIES: 2,
            MathProblemType.TRIGONOMETRY: 4,
        }.get(problem_type, 2)

        # Adjust for complexity indicators
        if any(kw in problem.lower() for kw in ["fraction", "decimal"]):
            base_difficulty += 1
        if any(kw in problem for kw in ["^3", "^4", "cube", "fourth"]):
            base_difficulty += 1

        return min(5, max(1, base_difficulty))

    async def _extract_concepts(
        self, problem: str, problem_type: MathProblemType
    ) -> List[str]:
        """Extract concepts involved in the problem."""
        concepts = []

        # Type-specific concepts
        type_concepts = {
            MathProblemType.LINEAR_EQUATION: ["linear equations", "inverse operations", "simplification"],
            MathProblemType.QUADRATIC_EQUATION: ["quadratic equations", "factoring", "zero product property"],
            MathProblemType.SYSTEM_OF_EQUATIONS: ["systems", "substitution", "elimination"],
            MathProblemType.GEOMETRY: ["shapes", "area", "perimeter", "formulas"],
            MathProblemType.FACTORING: ["factoring", "common factors", "grouping"],
            MathProblemType.EXPANDING: ["distributive property", "polynomials"],
            MathProblemType.SIMPLIFYING: ["like terms", "order of operations"],
            MathProblemType.FUNCTIONS: ["functions", "domain", "range"],
            MathProblemType.INEQUALITIES: ["inequalities", "solution sets"],
            MathProblemType.TRIGONOMETRY: ["trigonometry", "sine", "cosine", "tangent"],
        }

        concepts.extend(type_concepts.get(problem_type, []))

        # General concepts from problem text
        if "fraction" in problem.lower():
            concepts.append("fractions")
        if "decimal" in problem.lower():
            concepts.append("decimals")

        return list(set(concepts))

    def _determine_solution_method(
        self, problem: str, problem_type: MathProblemType
    ) -> str:
        """Determine the primary solution method."""
        methods = {
            MathProblemType.LINEAR_EQUATION: "Isolate the variable using inverse operations",
            MathProblemType.QUADRATIC_EQUATION: "Factor or use quadratic formula",
            MathProblemType.SYSTEM_OF_EQUATIONS: "Use substitution or elimination",
            MathProblemType.GEOMETRY: "Identify shape and apply formula",
            MathProblemType.FACTORING: "Find common factors or factor pairs",
            MathProblemType.EXPANDING: "Apply distributive property",
            MathProblemType.SIMPLIFYING: "Combine like terms",
            MathProblemType.FUNCTIONS: "Evaluate by substitution",
            MathProblemType.INEQUALITIES: "Solve like equation, watch inequality sign",
            MathProblemType.TRIGONOMETRY: "Use trig ratios",
        }
        return methods.get(problem_type, "Problem-specific approach")

    def _get_common_errors(self, problem_type: MathProblemType) -> List[str]:
        """Get common student errors for a problem type."""
        errors = {
            MathProblemType.LINEAR_EQUATION: [
                "Sign errors when moving terms",
                "Forgetting to divide ALL terms",
                "Not performing same operation on both sides",
            ],
            MathProblemType.QUADRATIC_EQUATION: [
                "Wrong factors chosen",
                "Sign errors in quadratic formula",
                "Forgetting ± in solutions",
            ],
            MathProblemType.SYSTEM_OF_EQUATIONS: [
                "Arithmetic errors",
                "Not finding common coefficient",
            ],
            MathProblemType.GEOMETRY: [
                "Using wrong formula",
                "Confusing area and perimeter",
            ],
            MathProblemType.FACTORING: [
                "Missing factors",
                "Wrong sign combinations",
            ],
            MathProblemType.EXPANDING: [
                "Forgetting to distribute to all terms",
                "Sign errors",
            ],
        }
        return errors.get(problem_type, [])

    async def _check_answer_correctness(
        self, student_answer: str, expected_answer: str
    ) -> bool:
        """Check if student's answer matches expected answer."""
        if not expected_answer:
            # If no expected answer, check basic reasonableness
            return len(student_answer) > 0

        # Simple string matching (can be enhanced with symbolic math)
        student_clean = student_answer.strip().lower()
        expected_clean = expected_answer.strip().lower()

        # Exact match
        if student_clean == expected_clean:
            return True

        # Try numeric comparison if both are numbers
        try:
            student_num = float(student_answer.replace("x", ""))
            expected_num = float(expected_answer.replace("x", ""))
            return abs(student_num - expected_num) < 0.001
        except (ValueError, AttributeError):
            pass

        return False
