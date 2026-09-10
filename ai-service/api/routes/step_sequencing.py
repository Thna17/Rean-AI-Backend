"""
Step Sequencing Routes - Teaching Workflow API

Endpoints for the interactive step-by-step teaching experience:
- POST /step-sequencing/start: Start teaching a problem
- POST /step-sequencing/{session_id}/respond: Student responds to a step
- GET /step-sequencing/{session_id}: Get current session state

This module orchestrates the teaching workflow by:
1. Accepting a problem from the student
2. Generating a multi-step teaching plan
3. Managing student responses
4. Routing to next steps adaptively
5. Tracking progress and performance
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from api.models.problem_models import Problem
from api.models.teaching_step import (
    TeachingPlan,
    TeachingStep,
    Subject,
)
from api.services.step_sequencing_service import StepSequencingService
from api.repositories.problem_repository import ProblemRepository
from api.services.spaced_repetition_service import SpacedRepetitionService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/step-sequencing", tags=["Step Sequencing"])

# Initialize services (will be injected later)
_step_sequencing_service: Optional[StepSequencingService] = None
_problem_repository: Optional[ProblemRepository] = None
_spaced_repetition_service: Optional[SpacedRepetitionService] = None

# Session storage (in-memory for MVP, move to Redis in Phase 2.3)
_sessions: Dict[str, Dict[str, Any]] = {}


def initialize_services(
    step_sequencing_service: StepSequencingService,
    problem_repository: ProblemRepository,
    spaced_repetition_service: SpacedRepetitionService,
) -> None:
    """Initialize the services used by this router.
    
    Args:
        step_sequencing_service: Service for generating teaching plans
        problem_repository: Service for loading problems
        spaced_repetition_service: Service for tracking progress
    """
    global _step_sequencing_service, _problem_repository, _spaced_repetition_service
    _step_sequencing_service = step_sequencing_service
    _problem_repository = problem_repository
    _spaced_repetition_service = spaced_repetition_service
    logger.info("Step Sequencing services initialized")


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class StartTeachingRequest(BaseModel):
    """Request to start teaching a problem"""
    problem_id: str = Field(..., description="ID of the problem to teach")
    student_id: str = Field(..., description="ID of the student")
    learning_style: Optional[str] = Field(
        None,
        description="Student learning style: visual, analytical, kinesthetic"
    )
    include_hints: bool = Field(
        True,
        description="Whether to include hints in teaching plan"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "problem_id": "math_linear_001",
                "student_id": "student_001",
                "learning_style": "visual",
                "include_hints": True,
            }
        }


class StudentResponseRequest(BaseModel):
    """Student response to a teaching step"""
    student_response: str = Field(..., description="Student's response to the step")
    response_type: str = Field(
        "text",
        description="Type of response: text, multiple_choice, numeric, draw"
    )
    confidence_level: Optional[str] = Field(
        None,
        description="Student's confidence: easy, medium, hard"
    )
    time_spent_seconds: int = Field(
        0,
        description="Time spent on this step"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "student_response": "x = 4",
                "response_type": "text",
                "confidence_level": "medium",
                "time_spent_seconds": 45,
            }
        }


class StartTeachingResponse(BaseModel):
    """Response to start teaching request"""
    session_id: str = Field(..., description="Unique session ID")
    problem: Dict[str, Any] = Field(..., description="Problem data")
    current_step: Dict[str, Any] = Field(..., description="First teaching step")
    total_steps: int = Field(..., description="Total steps in teaching plan")
    teaching_plan_id: str = Field(..., description="ID of the teaching plan")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "problem": {
                    "id": "math_linear_001",
                    "problem": "Solve 2x + 5 = 13",
                    "answer": "4",
                    "difficulty": 1,
                },
                "current_step": {
                    "id": "step_1",
                    "step_number": 1,
                    "type": "question",
                    "title": "Identify the operation",
                    "description": "What operation do we see with the 5?",
                },
                "total_steps": 5,
                "teaching_plan_id": "plan_xyz789",
            }
        }


class StudentResponseResponse(BaseModel):
    """Response to student answer evaluation"""
    is_correct: bool = Field(..., description="Whether response is correct")
    feedback: str = Field(..., description="Feedback for the response")
    confidence: float = Field(..., description="Confidence in evaluation (0-1)")
    next_step: Optional[Dict[str, Any]] = Field(
        None,
        description="Next teaching step, or None if complete"
    )
    misconceptions_detected: list[str] = Field(
        default_factory=list,
        description="Any misconceptions identified"
    )
    hint_text: Optional[str] = Field(None, description="Hint if answer wrong")
    session_complete: bool = Field(
        False,
        description="True if teaching session complete"
    )
    final_feedback: Optional[str] = Field(
        None,
        description="Final feedback if session complete"
    )
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        json_schema_extra = {
            "example": {
                "is_correct": False,
                "feedback": "Not quite. Look at the +5. What's the opposite operation?",
                "confidence": 0.85,
                "misconceptions_detected": ["operation_confusion"],
                "hint_text": "If we have +5 on one side, what do we do to both sides?",
                "session_complete": False,
                "next_step": {
                    "id": "step_1_retry",
                    "step_number": 1,
                    "type": "hint",
                    "title": "Hint",
                    "description": "Try again with this hint...",
                },
            }
        }


class SessionStatusResponse(BaseModel):
    """Current session state"""
    session_id: str = Field(..., description="Session ID")
    problem_id: str = Field(..., description="Problem ID")
    student_id: str = Field(..., description="Student ID")
    current_step_number: int = Field(..., description="Current step number")
    total_steps: int = Field(..., description="Total steps")
    progress_percent: float = Field(..., description="Progress percentage (0-100)")
    correct_responses: int = Field(..., description="Number of correct responses")
    incorrect_responses: int = Field(..., description="Number of incorrect responses")
    session_started: datetime = Field(..., description="When session started")
    last_update: datetime = Field(..., description="Last update time")
    is_complete: bool = Field(..., description="Whether session is complete")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "problem_id": "math_linear_001",
                "student_id": "student_001",
                "current_step_number": 2,
                "total_steps": 5,
                "progress_percent": 40.0,
                "correct_responses": 1,
                "incorrect_responses": 0,
            }
        }


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/start",
    response_model=StartTeachingResponse,
    summary="Start teaching a problem",
    description="Initialize a teaching session for a problem. Returns the first step.",
)
async def start_teaching(request: StartTeachingRequest) -> StartTeachingResponse:
    """
    Start a teaching session for a problem.
    
    This endpoint:
    1. Loads the problem from the repository
    2. Generates a multi-step teaching plan
    3. Creates a session to track progress
    4. Returns the first teaching step
    
    Args:
        request: StartTeachingRequest with problem_id and student_id
        
    Returns:
        StartTeachingResponse with session_id, problem, first step, and plan
        
    Raises:
        HTTPException: If problem not found or plan generation fails
    """
    logger.info(
        f"Starting teaching session for problem {request.problem_id}, "
        f"student {request.student_id}"
    )
    
    try:
        # Validate services are initialized
        if not _step_sequencing_service or not _problem_repository:
            logger.error("Services not initialized")
            raise HTTPException(
                status_code=500,
                detail="Step Sequencing service not initialized"
            )
        
        # Load the problem (synchronous call, but we await for compatibility)
        problem: Problem = _problem_repository.get_by_id(request.problem_id)
        if not problem:
            logger.warning(f"Problem not found: {request.problem_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Problem {request.problem_id} not found"
            )
        
        # Generate teaching plan
        teaching_plan: TeachingPlan = await _step_sequencing_service.generate_teaching_plan(
            problem=problem.problem,
            subject=Subject(problem.subject),
            grade_level=problem.grade_level,
            learning_style=request.learning_style,
            include_hints=request.include_hints,
            max_steps=8,
            metadata={
                "problem_id": problem.id,
                "problem_difficulty": problem.difficulty,
                "expected_steps": problem.expected_steps,
            },
        )
        
        if not teaching_plan.steps:
            logger.error(f"No steps generated for problem {request.problem_id}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate teaching steps"
            )
        
        # Create session
        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        first_step = teaching_plan.steps[0]
        
        session_data = {
            "session_id": session_id,
            "problem_id": request.problem_id,
            "student_id": request.student_id,
            "teaching_plan_id": teaching_plan.id,
            "teaching_plan": teaching_plan,
            "current_step_number": 1,
            "current_step_id": first_step.id,
            "total_steps": len(teaching_plan.steps),
            "correct_responses": 0,
            "incorrect_responses": 0,
            "responses": [],  # Track all responses
            "session_started": datetime.now(timezone.utc),
            "last_update": datetime.now(timezone.utc),
            "is_complete": False,
        }
        
        _sessions[session_id] = session_data
        logger.info(f"Session created: {session_id} with {len(teaching_plan.steps)} steps")
        
        # Return response
        return StartTeachingResponse(
            session_id=session_id,
            problem=problem.model_dump(),
            current_step=first_step.model_dump(),
            total_steps=len(teaching_plan.steps),
            teaching_plan_id=teaching_plan.id,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting teaching: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error starting teaching session: {str(e)}"
        )


@router.post(
    "/{session_id}/respond",
    response_model=StudentResponseResponse,
    summary="Student responds to a step",
    description="Process student response to a teaching step and return feedback and next step.",
)
async def respond_to_step(
    session_id: str,
    request: StudentResponseRequest = Body(...),
) -> StudentResponseResponse:
    """
    Process student's response to a teaching step.
    
    This endpoint:
    1. Validates the session exists
    2. Evaluates the student's response
    3. Generates feedback
    4. Routes to next step (adaptive)
    5. Tracks progress
    
    Args:
        session_id: The session ID
        request: StudentResponseRequest with student_response
        
    Returns:
        StudentResponseResponse with feedback, is_correct, and next_step
        
    Raises:
        HTTPException: If session not found or evaluation fails
    """
    logger.info(f"Processing response for session {session_id}")
    
    try:
        # Validate services
        if not _step_sequencing_service:
            raise HTTPException(
                status_code=500,
                detail="Step Sequencing service not initialized"
            )
        
        # Get session
        session = _sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        # Session already complete
        if session.get("is_complete"):
            logger.info(f"Session {session_id} already complete")
            return StudentResponseResponse(
                is_correct=True,
                feedback="This teaching session is complete. Great work!",
                confidence=1.0,
                session_complete=True,
                final_feedback="You have completed all steps. Excellent!",
            )
        
        # Get current step
        current_step_id = session["current_step_id"]
        teaching_plan: TeachingPlan = session["teaching_plan"]
        current_step: TeachingStep = teaching_plan.get_step_by_id(current_step_id)
        
        if not current_step:
            logger.error(f"Current step not found: {current_step_id}")
            raise HTTPException(
                status_code=500,
                detail="Current step not found"
            )
        
        # Evaluate response
        evaluation_result = await _step_sequencing_service.evaluate_step_response(
            step=current_step,
            student_response=request.student_response,
            response_type=request.response_type,
            context={
                "student_id": session["student_id"],
                "step_number": session["current_step_number"],
            },
        )
        
        # Update session
        if evaluation_result.is_correct:
            session["correct_responses"] += 1
        else:
            session["incorrect_responses"] += 1
        
        session["responses"].append({
            "step_id": current_step_id,
            "student_response": request.student_response,
            "is_correct": evaluation_result.is_correct,
            "confidence": evaluation_result.confidence,
            "timestamp": datetime.now(timezone.utc),
        })
        
        # Get next step
        next_step = None
        session_complete = False
        final_feedback = None
        
        if evaluation_result.is_correct or session["incorrect_responses"] >= 3:
            # Move to next step
            next_step_obj = _step_sequencing_service.get_next_step(
                plan=teaching_plan,
                current_step_id=current_step_id,
                evaluation_result=evaluation_result,
            )
            
            if next_step_obj:
                session["current_step_number"] += 1
                session["current_step_id"] = next_step_obj.id
                next_step = next_step_obj.model_dump()
            else:
                # No more steps - session complete
                session_complete = True
                session["is_complete"] = True
                final_feedback = (
                    f"Excellent! You've completed all {session['total_steps']} steps. "
                    f"Correct: {session['correct_responses']}, "
                    f"Incorrect: {session['incorrect_responses']}"
                )
        
        session["last_update"] = datetime.now(timezone.utc)
        
        logger.info(
            f"Response evaluated: correct={evaluation_result.is_correct}, "
            f"session_complete={session_complete}"
        )
        
        # Return response
        return StudentResponseResponse(
            is_correct=evaluation_result.is_correct,
            feedback=evaluation_result.feedback_message,
            confidence=evaluation_result.confidence,
            next_step=next_step,
            misconceptions_detected=session.get("misconceptions", []),
            hint_text=evaluation_result.hint_text,
            session_complete=session_complete,
            final_feedback=final_feedback,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing response: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error processing response: {str(e)}"
        )


@router.get(
    "/{session_id}",
    response_model=SessionStatusResponse,
    summary="Get session status",
    description="Get current status of a teaching session.",
)
async def get_session_status(session_id: str) -> SessionStatusResponse:
    """
    Get the current status of a teaching session.
    
    Args:
        session_id: The session ID
        
    Returns:
        SessionStatusResponse with current progress and status
        
    Raises:
        HTTPException: If session not found
    """
    logger.info(f"Getting status for session {session_id}")
    
    try:
        session = _sessions.get(session_id)
        if not session:
            logger.warning(f"Session not found: {session_id}")
            raise HTTPException(
                status_code=404,
                detail=f"Session {session_id} not found"
            )
        
        total = session["total_steps"]
        current = session["current_step_number"]
        progress = (current / total * 100) if total > 0 else 0
        
        return SessionStatusResponse(
            session_id=session_id,
            problem_id=session["problem_id"],
            student_id=session["student_id"],
            current_step_number=current,
            total_steps=total,
            progress_percent=progress,
            correct_responses=session["correct_responses"],
            incorrect_responses=session["incorrect_responses"],
            session_started=session["session_started"],
            last_update=session["last_update"],
            is_complete=session["is_complete"],
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error getting session status: {str(e)}"
        )


@router.delete(
    "/{session_id}",
    summary="Delete session",
    description="Clean up a teaching session (optional).",
)
async def delete_session(session_id: str) -> dict:
    """
    Delete a session from storage.
    
    Args:
        session_id: The session ID
        
    Returns:
        Confirmation message
    """
    logger.info(f"Deleting session {session_id}")
    
    if session_id in _sessions:
        del _sessions[session_id]
        return {"message": f"Session {session_id} deleted"}
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Session {session_id} not found"
        )
