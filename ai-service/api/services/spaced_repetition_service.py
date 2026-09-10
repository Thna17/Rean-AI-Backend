"""
Spaced Repetition Service - SM-2 Algorithm Implementation

Manages student progress and schedules problem reviews using a simplified
SM-2 (Spaced Repetition) algorithm. Tracks:
- Times solved/failed per problem
- Confidence level
- Next review date
- Misconceptions detected

Scheduling rules (simplified SM-2 for MVP):
- Easy (confidence 4-5): 7 days
- Medium (confidence 3): 3 days
- Hard (confidence 1-2): 1 day
- New: Available immediately
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from api.models.problem_models import ProgressUpdate, StudentProgress

logger = logging.getLogger(__name__)


class SpacedRepetitionService:
    """
    Service for managing spaced repetition scheduling and progress tracking.
    
    Implements simplified SM-2 algorithm for scheduling problem reviews.
    Stores progress in-memory (Phase 1 MVP; database in Phase 2).
    """

    def __init__(self) -> None:
        """Initialize the service with empty progress dictionary."""
        self.student_progress: Dict[str, Dict[str, StudentProgress]] = {}
        logger.info("SpacedRepetitionService initialized")

    def _get_key(self, student_id: str, problem_id: str) -> str:
        """Create composite key for progress lookup."""
        return f"{student_id}:{problem_id}"

    def _calculate_next_review(self, confidence_level: str) -> datetime:
        """
        Calculate next review date based on confidence level (SM-2 simplified).
        
        Args:
            confidence_level: "easy", "medium", "hard"
            
        Returns:
            datetime: Next review date
        """
        now = datetime.now()
        if confidence_level == "easy":
            return now + timedelta(days=7)
        elif confidence_level == "medium":
            return now + timedelta(days=3)
        elif confidence_level == "hard":
            return now + timedelta(days=1)
        else:  # "new"
            return now

    async def mark_solved(
        self,
        student_id: str,
        problem_id: str,
        progress_update: ProgressUpdate,
    ) -> StudentProgress:
        """
        Mark a problem as solved and update progress.
        
        Args:
            student_id: Student identifier
            problem_id: Problem identifier
            progress_update: Confidence level and time spent
            
        Returns:
            Updated StudentProgress object
        """
        key = self._get_key(student_id, problem_id)

        # Get or create progress record
        if student_id not in self.student_progress:
            self.student_progress[student_id] = {}

        if problem_id not in self.student_progress[student_id]:
            # First time solving
            progress = StudentProgress(
                student_id=student_id,
                problem_id=problem_id,
                times_solved=1,
                confidence_level=progress_update.confidence_level,
                last_seen=datetime.now(),
                next_review=self._calculate_next_review(
                    progress_update.confidence_level
                ),
                time_spent_seconds=progress_update.time_spent_seconds,
                misconceptions_detected=progress_update.misconceptions_detected or [],
            )
        else:
            # Update existing progress
            progress = self.student_progress[student_id][problem_id]
            progress.times_solved += 1
            progress.confidence_level = progress_update.confidence_level
            progress.last_seen = datetime.now()
            progress.next_review = self._calculate_next_review(
                progress_update.confidence_level
            )
            progress.time_spent_seconds += progress_update.time_spent_seconds
            if progress_update.misconceptions_detected:
                progress.misconceptions_detected = (
                    progress_update.misconceptions_detected
                )
            progress.updated_at = datetime.now()

        # Store progress
        self.student_progress[student_id][problem_id] = progress

        logger.info(
            f"Student {student_id} solved {problem_id} "
            f"(confidence: {progress_update.confidence_level}, "
            f"next_review: {progress.next_review})"
        )

        return progress

    async def mark_failed(
        self,
        student_id: str,
        problem_id: str,
        time_spent_seconds: int,
    ) -> StudentProgress:
        """
        Mark a problem as failed (student couldn't solve it).
        
        Sets confidence to "hard" and schedules review for next day.
        
        Args:
            student_id: Student identifier
            problem_id: Problem identifier
            time_spent_seconds: Time spent on attempt
            
        Returns:
            Updated StudentProgress object
        """
        key = self._get_key(student_id, problem_id)

        if student_id not in self.student_progress:
            self.student_progress[student_id] = {}

        if problem_id not in self.student_progress[student_id]:
            # First attempt, but failed
            progress = StudentProgress(
                student_id=student_id,
                problem_id=problem_id,
                times_failed=1,
                confidence_level="hard",
                last_seen=datetime.now(),
                next_review=self._calculate_next_review("hard"),
                time_spent_seconds=time_spent_seconds,
            )
        else:
            # Update existing progress
            progress = self.student_progress[student_id][problem_id]
            progress.times_failed += 1
            progress.confidence_level = "hard"
            progress.last_seen = datetime.now()
            progress.next_review = self._calculate_next_review("hard")
            progress.time_spent_seconds += time_spent_seconds
            progress.updated_at = datetime.now()

        self.student_progress[student_id][problem_id] = progress

        logger.info(
            f"Student {student_id} failed {problem_id} "
            f"(next_review: {progress.next_review})"
        )

        return progress

    async def get_due_problems(self, student_id: str) -> List[str]:
        """
        Get all problems due for review for a student.
        
        Returns problems where next_review <= now, sorted by priority
        (hard > medium > easy).
        
        Args:
            student_id: Student identifier
            
        Returns:
            List of problem IDs due for review
        """
        if student_id not in self.student_progress:
            return []

        now = datetime.now()
        due_problems = []

        for problem_id, progress in self.student_progress[student_id].items():
            # Include if next_review is None (new) or past
            if progress.next_review is None or progress.next_review <= now:
                due_problems.append((problem_id, progress.confidence_level))

        # Sort by priority: hard > medium > easy
        priority_map = {"hard": 0, "medium": 1, "easy": 2, "new": 3}
        due_problems.sort(
            key=lambda x: priority_map.get(x[1], 99)
        )

        result = [p[0] for p in due_problems]
        logger.info(f"Retrieved {len(result)} due problems for student {student_id}")
        return result

    async def get_student_progress(self, student_id: str) -> Dict[str, Any]:
        """
        Get progress summary statistics for a student.
        
        Args:
            student_id: Student identifier
            
        Returns:
            Dictionary with progress stats
        """
        if student_id not in self.student_progress:
            return {
                "student_id": student_id,
                "total_solved": 0,
                "total_failed": 0,
                "problems_due": 0,
                "total_time_spent": 0,
                "average_confidence": "new",
                "recent_problems": [],
            }

        problems = self.student_progress[student_id]
        now = datetime.now()

        total_solved = sum(p.times_solved for p in problems.values())
        total_failed = sum(p.times_failed for p in problems.values())
        problems_due = sum(
            1
            for p in problems.values()
            if p.next_review is None or p.next_review <= now
        )
        total_time = sum(p.time_spent_seconds for p in problems.values())

        # Calculate average confidence
        confidences = [p.confidence_level for p in problems.values()]
        if confidences:
            confidence_scores = {
                "easy": 4,
                "medium": 3,
                "hard": 1,
                "new": 0,
            }
            avg_score = sum(
                confidence_scores.get(c, 0) for c in confidences
            ) / len(confidences)
            if avg_score >= 3.5:
                avg_confidence = "easy"
            elif avg_score >= 2:
                avg_confidence = "medium"
            elif avg_score >= 1:
                avg_confidence = "hard"
            else:
                avg_confidence = "new"
        else:
            avg_confidence = "new"

        # Get recent problems (last 5)
        recent = sorted(
            problems.items(),
            key=lambda x: x[1].last_seen or datetime.min,
            reverse=True,
        )[:5]

        recent_problems = [
            {
                "problem_id": pid,
                "confidence_level": p.confidence_level,
                "last_seen": p.last_seen.isoformat() if p.last_seen else None,
                "next_review": p.next_review.isoformat() if p.next_review else None,
            }
            for pid, p in recent
        ]

        result = {
            "student_id": student_id,
            "total_solved": total_solved,
            "total_failed": total_failed,
            "problems_due": problems_due,
            "total_time_spent": total_time,
            "average_confidence": avg_confidence,
            "recent_problems": recent_problems,
        }

        logger.info(f"Retrieved progress for student {student_id}")
        return result

    async def get_problem_progress(
        self, student_id: str, problem_id: str
    ) -> Optional[StudentProgress]:
        """
        Get progress for a specific problem.
        
        Args:
            student_id: Student identifier
            problem_id: Problem identifier
            
        Returns:
            StudentProgress or None if not attempted
        """
        if student_id in self.student_progress:
            return self.student_progress[student_id].get(problem_id)
        return None

    async def reset_progress(self, student_id: Optional[str] = None) -> str:
        """
        Reset progress for a student or all students.
        
        Args:
            student_id: If provided, reset only this student. If None, reset all.
            
        Returns:
            Confirmation message
        """
        if student_id:
            if student_id in self.student_progress:
                del self.student_progress[student_id]
            logger.info(f"Reset progress for student {student_id}")
            return f"Progress reset for student {student_id}"
        else:
            self.student_progress.clear()
            logger.info("Reset all progress")
            return "All progress reset"

    async def get_all_students(self) -> List[str]:
        """
        Get list of all students with progress records.
        
        Returns:
            List of student IDs
        """
        return list(self.student_progress.keys())

    async def get_student_problems(self, student_id: str) -> List[str]:
        """
        Get all problems attempted by a student.
        
        Args:
            student_id: Student identifier
            
        Returns:
            List of problem IDs
        """
        if student_id not in self.student_progress:
            return []
        return list(self.student_progress[student_id].keys())
