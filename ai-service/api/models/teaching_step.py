"""
Teaching Step Models - Pydantic Models for Step Sequencing

Defines the complete data model for multi-step interactive teaching:
- StepType: Enum of step types (explanation, visualization, question, feedback, hint, check)
- TeachingStep: Single step in a lesson with visualizations, questions, and branching
- TeachingPlan: Complete lesson plan with all steps and adaptive routing rules
- EvaluationResult: Result of student response evaluation
- AdaptiveRule: Branching rules for adaptive pathways
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class StepType(str, Enum):
    """Teaching step types following Socratic method"""
    EXPLANATION = "explanation"      # AI explains a concept or principle
    VISUALIZATION = "visualization"  # Show diagram, graph, or visual representation
    QUESTION = "question"            # Ask student to do something or answer
    FEEDBACK = "feedback"            # Respond to student's answer
    HINT = "hint"                    # Provide a clue for problem-solving
    CHECK = "check"                  # Verify student understands concept


class DifficultyLevel(int, Enum):
    """Bloom's taxonomy difficulty levels"""
    REMEMBER = 1          # Knowledge/recall
    UNDERSTAND = 2        # Comprehension/understanding
    APPLY = 3            # Application
    ANALYZE = 4          # Analysis
    EVALUATE = 5         # Synthesis/evaluation


class VisualizationType(str, Enum):
    """Types of visualizations that can be rendered"""
    NONE = "none"
    GRAPH = "graph"                  # Mathematical graph/plot
    GEOMETRY = "geometry"            # Geometric shapes (triangle, circle, polygon)
    VECTOR = "vector"                # Physics vectors with components
    MOLECULE = "molecule"            # Chemistry molecular structure
    NUMBER_LINE = "number_line"      # Number line for algebra
    TABLE = "table"                  # Data table
    TIMELINE = "timeline"            # Timeline/sequence
    ANIMATION = "animation"          # Animated sequence


class Subject(str, Enum):
    """Subject domains supported"""
    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"


class VisualizationConfig(BaseModel):
    """Configuration for a visualization to render"""
    model_config = ConfigDict(use_enum_values=True)
    
    type: VisualizationType = Field(..., description="Type of visualization")
    data: dict[str, Any] = Field(..., description="Visualization-specific data")
    title: Optional[str] = Field(None, description="Visualization title")
    annotations: Optional[list[str]] = Field(None, description="Annotations for visualization")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class InteractionConfig(BaseModel):
    """Configuration for student interaction/question"""
    model_config = ConfigDict(use_enum_values=True)
    
    question_text: str = Field(..., description="Question to ask student")
    interaction_type: Literal["text_input", "multiple_choice", "numeric", "draw"] = Field(
        "text_input",
        description="Type of student interaction"
    )
    choices: Optional[list[str]] = Field(None, description="For multiple choice")
    expected_answer: Optional[str] = Field(None, description="Expected student response")
    tolerance: Optional[float] = Field(None, description="Tolerance for numeric answers")
    hint_text: Optional[str] = Field(None, description="Hint if student struggles")
    max_attempts: int = Field(3, description="Maximum attempts allowed")


class BranchingRule(BaseModel):
    """Conditional branching rule for adaptive pathways"""
    model_config = ConfigDict(use_enum_values=True)
    
    condition: str = Field(
        ...,
        description="Condition name: 'correct', 'incorrect', 'hint_used', 'timeout'"
    )
    target_step_id: str = Field(..., description="Next step ID if condition matches")
    confidence_threshold: Optional[float] = Field(
        None,
        description="Confidence threshold for evaluation (0.0-1.0)"
    )


class TeachingStep(BaseModel):
    """Single step in a multi-step teaching sequence
    
    Represents one atomic unit of instruction following the Socratic method:
    - Explains/visualizes a concept
    - Asks student to respond or think
    - Branches based on student response
    """
    model_config = ConfigDict(use_enum_values=True)
    
    # Identity
    id: str = Field(..., description="Unique step ID (UUID or similar)")
    step_number: int = Field(..., description="Sequential step number (1-indexed)")
    
    # Content
    type: StepType = Field(..., description="Type of step (explanation, question, etc.)")
    title: str = Field(..., description="Short step title")
    description: str = Field(..., description="Detailed description of what happens in this step")
    
    # Visual content (renders on RichMediaCanvas)
    visualizations: list[VisualizationConfig] = Field(
        default_factory=list,
        description="List of visualizations to display"
    )
    board_actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of board actions for RichMediaCanvas rendering"
    )
    
    # Interaction (if this step asks something)
    interaction: Optional[InteractionConfig] = Field(
        None,
        description="Student interaction configuration (for question steps)"
    )
    
    # Branching
    next_step_id: Optional[str] = Field(
        None,
        description="Default next step ID (if no branching needed)"
    )
    branching_rules: list[BranchingRule] = Field(
        default_factory=list,
        description="Conditional routing rules for adaptive paths"
    )
    
    # Learning objective
    learning_objective: str = Field(
        ...,
        description="What student should understand by end of step"
    )
    difficulty: DifficultyLevel = Field(
        DifficultyLevel.UNDERSTAND,
        description="Difficulty level (1=remember, 5=evaluate)"
    )
    subject: Subject = Field(..., description="Subject domain")
    
    # Concept graph (prerequisites, relationships)
    concept_graph: Optional[dict[str, Any]] = Field(
        None,
        description="Knowledge graph data: prerequisites, concepts, misconceptions"
    )
    
    # Timing & metadata
    estimated_time_seconds: int = Field(
        30,
        description="Expected time to complete step in seconds"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional step metadata"
    )
    
    def get_next_step_id(self, evaluation_result: Optional['EvaluationResult'] = None) -> Optional[str]:
        """Determine next step ID based on evaluation result.
        
        Args:
            evaluation_result: Result of student response evaluation
            
        Returns:
            Next step ID, or None if this is final step
        """
        if evaluation_result is None:
            return self.next_step_id
        
        # Match branching rules
        for rule in self.branching_rules:
            if rule.condition == evaluation_result.condition:
                if rule.confidence_threshold is None or \
                   evaluation_result.confidence >= rule.confidence_threshold:
                    return rule.target_step_id
        
        # Fallback to default
        return self.next_step_id


class TeachingPlan(BaseModel):
    """Complete multi-step teaching plan for a problem
    
    Represents a full lesson with multiple sequenced steps, adaptive branching,
    and comprehensive metadata for tracking student progress.
    """
    model_config = ConfigDict(use_enum_values=True)
    
    # Identity
    id: str = Field(..., description="Unique plan ID (UUID or similar)")
    session_id: Optional[str] = Field(None, description="Associated session ID")
    
    # Content
    problem: str = Field(..., description="Original student problem/question")
    subject: Subject = Field(..., description="Subject domain")
    grade_level: int = Field(..., ge=10, le=12, description="Cambodia grade level (10-12)")
    
    # Steps
    steps: list[TeachingStep] = Field(
        ...,
        min_length=1,
        description="Ordered list of teaching steps"
    )
    
    # Adaptive rules
    adaptive_rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Global adaptive routing rules and learning style preferences"
    )
    
    # Learning context
    learning_style: Optional[str] = Field(
        None,
        description="Student learning style: visual, analytical, kinesthetic"
    )
    prerequisite_concepts: list[str] = Field(
        default_factory=list,
        description="Prerequisites student should understand"
    )
    target_concepts: list[str] = Field(
        default_factory=list,
        description="Concepts this lesson targets"
    )
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(default="ai_service", description="Creator of this plan")
    version: int = Field(1, description="Plan version")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )
    
    def get_step_by_id(self, step_id: str) -> Optional[TeachingStep]:
        """Get a step by its ID.
        
        Args:
            step_id: Step ID to find
            
        Returns:
            TeachingStep if found, None otherwise
        """
        for step in self.steps:
            if step.id == step_id:
                return step
        return None
    
    @property
    def first_step(self) -> TeachingStep:
        """Get the first step in the plan.
        
        Returns:
            First TeachingStep
            
        Raises:
            IndexError: If plan has no steps
        """
        if not self.steps:
            raise IndexError("Teaching plan has no steps")
        return self.steps[0]
    
    def get_progress_percent(self, current_step_id: str) -> float:
        """Calculate progress percentage based on current step.
        
        Args:
            current_step_id: Currently active step ID
            
        Returns:
            Progress percentage (0.0-100.0)
        """
        if not self.steps:
            return 0.0
        
        for i, step in enumerate(self.steps):
            if step.id == current_step_id:
                return (i + 1) / len(self.steps) * 100.0
        
        return 0.0
    
    def is_last_step(self, step_id: str) -> bool:
        """Check if step is the last in the plan.
        
        Args:
            step_id: Step ID to check
            
        Returns:
            True if this is the last step
        """
        if not self.steps:
            return False
        return self.steps[-1].id == step_id


class EvaluationResult(BaseModel):
    """Result of evaluating student response to a step
    
    Contains evaluation details, feedback, and routing information
    for determining next step.
    """
    model_config = ConfigDict(use_enum_values=True)
    
    # Evaluation
    is_correct: bool = Field(..., description="Whether response is correct")
    condition: str = Field(
        ...,
        description="Condition type: 'correct', 'incorrect', 'partial', 'hint_used'"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence in evaluation (0.0-1.0)"
    )
    
    # Feedback
    feedback_message: str = Field(..., description="Feedback to show student")
    explanation: Optional[str] = Field(
        None,
        description="Detailed explanation of why response is correct/incorrect"
    )
    
    # Routing
    next_step_id: Optional[str] = Field(
        None,
        description="Next step ID to show student"
    )
    should_offer_hint: bool = Field(
        False,
        description="Whether to offer a hint"
    )
    hint_text: Optional[str] = Field(None, description="Hint text if offered")
    
    # Metadata
    evaluation_time_ms: int = Field(..., description="Time spent evaluating in milliseconds")
    model_used: str = Field(default="unknown", description="Model used for evaluation")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )


class StepSequencingRequest(BaseModel):
    """Request to generate a teaching plan"""
    model_config = ConfigDict(use_enum_values=True)
    
    problem: str = Field(..., description="Student's problem/question")
    subject: Subject = Field(..., description="Subject domain")
    grade_level: int = Field(..., ge=10, le=12, description="Grade level (10-12)")
    learning_style: Optional[str] = Field(
        None,
        description="Student learning style (visual, analytical, kinesthetic)"
    )
    include_hints: bool = Field(True, description="Whether to include hints in plan")
    difficulty_preference: Optional[DifficultyLevel] = Field(
        None,
        description="Preferred difficulty level"
    )
    max_steps: int = Field(8, ge=1, le=20, description="Maximum steps to generate")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context"
    )


class StepEvaluationRequest(BaseModel):
    """Request to evaluate student response to a step"""
    model_config = ConfigDict(use_enum_values=True)
    
    step_id: str = Field(..., description="Step being evaluated")
    student_response: str = Field(..., description="Student's response text")
    response_type: str = Field(
        default="text",
        description="Type of response (text, multiple_choice, numeric, draw)"
    )
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context (previous answers, hints used, etc.)"
    )
