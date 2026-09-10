"""
Problem Routes - REST API Endpoints for Problem Bank

Provides endpoints for:
- Listing and searching problems
- Getting single problems
- Marking problems as solved/failed
- Tracking student progress
- Getting due problems for spaced repetition

All endpoints are async and include proper error handling and logging.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from api.models.problem_models import Problem, ProgressUpdate, StudentProgress
from api.repositories.problem_repository import ProblemRepository
from api.services.spaced_repetition_service import SpacedRepetitionService

router = APIRouter(prefix="/problems", tags=["problems"])
logger = logging.getLogger(__name__)

# Initialize services (in production, use dependency injection)
problem_repo = ProblemRepository()
spaced_rep_service = SpacedRepetitionService()


@router.get("", response_model=dict)
async def list_problems(
    subject: Optional[str] = Query(None, description="Filter by subject"),
    difficulty: Optional[int] = Query(None, description="Filter by difficulty (1-5)"),
    topic: Optional[str] = Query(None, description="Filter by topic"),
    grade_level: Optional[int] = Query(None, description="Filter by grade (10-12)"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
) -> dict:
    """
    List all problems with optional filters.
    
    Args:
        subject: Filter by 'mathematics', 'physics', or 'chemistry'
        difficulty: Filter by difficulty level (1-5)
        topic: Filter by topic name (substring match)
        grade_level: Filter by grade (10, 11, 12)
        limit: Maximum number of results
        
    Returns:
        Dictionary with total count and problem list
    """
    try:
        # Search with filters
        problems = problem_repo.search(
            subject=subject,
            difficulty=difficulty,
            topic=topic,
            grade_level=grade_level,
        )

        # Apply limit
        problems = problems[:limit]

        logger.info(
            f"Listed {len(problems)} problems "
            f"(subject={subject}, difficulty={difficulty}, topic={topic})"
        )

        return {
            "total": len(problems),
            "problems": [p.model_dump(mode="json") for p in problems],
        }

    except Exception as e:
        logger.error(f"Error listing problems: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{problem_id}", response_model=dict)
async def get_problem(problem_id: str) -> dict:
    """
    Get a single problem by ID.
    
    Args:
        problem_id: Problem identifier
        
    Returns:
        Problem object
    """
    try:
        problem = problem_repo.get_by_id(problem_id)
        if not problem:
            logger.warning(f"Problem not found: {problem_id}")
            raise HTTPException(status_code=404, detail="Problem not found")

        logger.info(f"Retrieved problem {problem_id}")
        return problem.model_dump(mode="json")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving problem {problem_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{problem_id}/solve", response_model=dict)
async def solve_problem(
    problem_id: str,
    request: dict,  # Contains student_id and ProgressUpdate
) -> dict:
    """
    Mark a problem as solved and update progress.
    
    Calls SpacedRepetitionService to schedule next review.
    
    Args:
        problem_id: Problem identifier
        request: Contains student_id, confidence_level, time_spent_seconds
        
    Returns:
        Updated progress with next review date
    """
    try:
        # Validate problem exists
        problem = problem_repo.get_by_id(problem_id)
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")

        # Parse request
        student_id = request.get("student_id")
        if not student_id:
            raise HTTPException(
                status_code=400, detail="student_id is required"
            )

        # Create ProgressUpdate
        progress_update = ProgressUpdate(
            confidence_level=request.get("confidence_level", "medium"),
            time_spent_seconds=request.get("time_spent_seconds", 0),
            misconceptions_detected=request.get("misconceptions_detected"),
            student_response=request.get("student_response"),
        )

        # Update progress
        progress = await spaced_rep_service.mark_solved(
            student_id=student_id,
            problem_id=problem_id,
            progress_update=progress_update,
        )

        logger.info(f"Student {student_id} solved problem {problem_id}")

        return {
            "status": "success",
            "message": "Problem marked as solved",
            "progress": progress.model_dump(mode="json"),
            "next_review_date": progress.next_review.date().isoformat()
            if progress.next_review
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking problem solved: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{problem_id}/fail", response_model=dict)
async def fail_problem(problem_id: str, request: dict) -> dict:
    """
    Mark a problem as failed (student couldn't solve it).
    
    Args:
        problem_id: Problem identifier
        request: Contains student_id, time_spent_seconds
        
    Returns:
        Updated progress
    """
    try:
        # Validate problem exists
        problem = problem_repo.get_by_id(problem_id)
        if not problem:
            raise HTTPException(status_code=404, detail="Problem not found")

        student_id = request.get("student_id")
        if not student_id:
            raise HTTPException(
                status_code=400, detail="student_id is required"
            )

        time_spent = request.get("time_spent_seconds", 0)

        # Mark as failed
        progress = await spaced_rep_service.mark_failed(
            student_id=student_id,
            problem_id=problem_id,
            time_spent_seconds=time_spent,
        )

        logger.info(f"Student {student_id} failed problem {problem_id}")

        return {
            "status": "failed",
            "message": "Problem marked as failed",
            "progress": progress.model_dump(mode="json"),
            "next_review_date": progress.next_review.date().isoformat()
            if progress.next_review
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking problem failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/student/{student_id}/progress", response_model=dict)
async def get_student_progress(student_id: str) -> dict:
    """
    Get progress dashboard for a student.
    
    Shows solved, failed, due problems and other statistics.
    
    Args:
        student_id: Student identifier
        
    Returns:
        Progress statistics
    """
    try:
        progress = await spaced_rep_service.get_student_progress(student_id)
        logger.info(f"Retrieved progress for student {student_id}")
        return progress

    except Exception as e:
        logger.error(f"Error retrieving progress: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/student/{student_id}/due-problems", response_model=dict)
async def get_due_problems(
    student_id: str,
    limit: int = Query(10, ge=1, le=50),
) -> dict:
    """
    Get problems due for review (spaced repetition schedule).
    
    Args:
        student_id: Student identifier
        limit: Max problems to return
        
    Returns:
        List of due problems with metadata
    """
    try:
        # Get problem IDs due for review
        due_ids = await spaced_rep_service.get_due_problems(student_id)
        due_ids = due_ids[:limit]

        # Get full problem objects
        due_problems = []
        for problem_id in due_ids:
            problem = problem_repo.get_by_id(problem_id)
            if problem:
                progress = await spaced_rep_service.get_problem_progress(
                    student_id, problem_id
                )
                due_problems.append({
                    **problem.model_dump(mode="json"),
                    "confidence_level": progress.confidence_level
                    if progress
                    else "new",
                    "last_seen": progress.last_seen.isoformat()
                    if progress and progress.last_seen
                    else None,
                    "next_review": progress.next_review.isoformat()
                    if progress and progress.next_review
                    else None,
                })

        logger.info(f"Retrieved {len(due_problems)} due problems for {student_id}")

        return {
            "student_id": student_id,
            "due_count": len(due_problems),
            "problems": due_problems,
        }

    except Exception as e:
        logger.error(f"Error retrieving due problems: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/bank/statistics", response_model=dict)
async def get_bank_statistics() -> dict:
    """
    Get statistics about the problem bank.
    
    Shows counts by subject, grade, difficulty.
    
    Returns:
        Statistics dictionary
    """
    try:
        stats = problem_repo.get_statistics()
        logger.info("Retrieved problem bank statistics")
        return stats

    except Exception as e:
        logger.error(f"Error retrieving statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset", response_model=dict)
async def reset_progress(request: dict) -> dict:
    """
    Reset progress for a student (testing endpoint).
    
    Args:
        request: Contains optional student_id
        
    Returns:
        Confirmation message
    """
    try:
        student_id = request.get("student_id")
        message = await spaced_rep_service.reset_progress(student_id)
        logger.info(f"Reset progress: {message}")
        return {"status": "success", "message": message}

    except Exception as e:
        logger.error(f"Error resetting progress: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
