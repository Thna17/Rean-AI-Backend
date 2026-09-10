"""
Problem Models - Pydantic Models for Problem Bank Management

Defines data models for:
- Problem: Complete problem definition
- StudentProgress: Track individual problem progress
- ProgressUpdate: Request model for marking problems solved
- Supporting enums for subject and difficulty
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProblemSubject(str, Enum):
    """Subject categories for problems"""

    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"


class ProblemDifficulty(int, Enum):
    """Difficulty levels on 1-5 scale"""

    EASY = 1
    MEDIUM = 2
    INTERMEDIATE = 3
    ADVANCED = 4
    EXPERT = 5


class Problem(BaseModel):
    """
    Complete problem definition with all metadata.
    
    Used to store curriculum-aligned problems for the AI Visual Tutor.
    Each problem is self-contained with solution method, expected steps,
    common misconceptions, and curriculum concepts.
    """

    id: str = Field(
        ...,
        description="Unique identifier (e.g., 'math_linear_001')",
        min_length=1,
    )
    subject: ProblemSubject = Field(
        ..., description="Subject category (mathematics, physics, chemistry)"
    )
    grade_level: int = Field(
        ..., description="Grade level (10, 11, or 12)", ge=10, le=12
    )
    topic: str = Field(
        ..., description="Main topic (e.g., 'linear_equations', 'kinematics')"
    )
    subtopic: Optional[str] = Field(
        default=None,
        description="Sub-topic for finer categorization (e.g., 'two_step_equations')",
    )
    difficulty: int = Field(
        ...,
        description="Difficulty level (1=easy to 5=expert)",
        ge=1,
        le=5,
    )
    problem: str = Field(
        ..., description="The actual problem statement that student reads"
    )
    answer: str = Field(..., description="Expected final answer (string format)")
    solution_method: str = Field(
        ..., description="Primary solution approach (e.g., 'inverse_operations')"
    )
    expected_steps: int = Field(
        ..., description="Typical number of steps to solve", ge=1
    )
    misconceptions: List[str] = Field(
        default_factory=list,
        description="Common student errors (e.g., ['sign_error', 'forgot_division'])",
    )
    concepts: List[str] = Field(
        default_factory=list,
        description="Learning concepts involved (e.g., ['equality', 'variables'])",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Metadata tags for filtering (e.g., ['cambodia_grade_10'])",
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="ISO timestamp of creation"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Extra metadata (source, notes, etc.)"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "math_linear_001",
                "subject": "mathematics",
                "grade_level": 10,
                "topic": "linear_equations",
                "subtopic": "two_step_equations",
                "difficulty": 1,
                "problem": "Solve 2x + 5 = 13 for x",
                "answer": "4",
                "solution_method": "inverse_operations",
                "expected_steps": 4,
                "misconceptions": ["sign_error", "forgot_division"],
                "concepts": ["inverse_operations", "equality"],
                "tags": ["cambodia_grade_10"],
                "created_at": "2024-08-26T10:00:00",
                "metadata": {"source": "cambodia_curriculum"},
            }
        }
    }


class StudentProgress(BaseModel):
    """
    Tracks individual student progress on a specific problem.
    
    Used by SpacedRepetitionService to schedule reviews and track
    learning outcomes. Each student-problem pair has its own progress record.
    """

    student_id: str = Field(
        ..., description="Unique student identifier", min_length=1
    )
    problem_id: str = Field(
        ..., description="Problem identifier (must match Problem.id)", min_length=1
    )
    times_solved: int = Field(
        default=0,
        description="Number of times student successfully solved this problem",
        ge=0,
    )
    times_failed: int = Field(
        default=0,
        description="Number of times student failed to solve this problem",
        ge=0,
    )
    last_seen: Optional[datetime] = Field(
        default=None, description="Timestamp of last attempt"
    )
    confidence_level: str = Field(
        default="new",
        description="Student confidence: 'new', 'easy', 'medium', 'hard'",
    )
    next_review: Optional[datetime] = Field(
        default=None,
        description="When problem is due for review (SM-2 scheduling)",
    )
    time_spent_seconds: int = Field(
        default=0, description="Total time spent on this problem", ge=0
    )
    misconceptions_detected: List[str] = Field(
        default_factory=list,
        description="Misconceptions identified in student responses",
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="When progress record was created"
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="When progress was last updated",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "student_id": "student_001",
                "problem_id": "math_linear_001",
                "times_solved": 1,
                "times_failed": 0,
                "last_seen": "2024-08-26T10:30:00",
                "confidence_level": "medium",
                "next_review": "2024-08-29T10:30:00",
                "time_spent_seconds": 180,
                "misconceptions_detected": ["sign_error"],
                "created_at": "2024-08-26T10:30:00",
                "updated_at": "2024-08-26T10:30:00",
            }
        }
    }


class ProgressUpdate(BaseModel):
    """
    Request model for marking a problem as solved.
    
    Student sends this when completing a problem. Backend uses it to
    update StudentProgress and schedule next review via SpacedRepetitionService.
    """

    confidence_level: str = Field(
        ...,
        description="How confident student is: 'easy', 'medium', 'hard'",
    )
    time_spent_seconds: int = Field(
        ..., description="Seconds spent solving this problem", ge=0
    )
    misconceptions_detected: Optional[List[str]] = Field(
        default=None,
        description="Misconceptions identified by AI grading",
    )
    student_response: Optional[str] = Field(
        default=None,
        description="Student's actual response (for analysis)",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "confidence_level": "medium",
                "time_spent_seconds": 180,
                "misconceptions_detected": ["sign_error"],
                "student_response": "x = 4",
            }
        }
    }
