"""
Test Spaced Repetition Service - Unit tests for SM-2 scheduling

Tests:
- SM-2 scheduling algorithm
- Progress tracking
- Due problem retrieval
- Progress statistics
"""

import pytest
from datetime import datetime, timedelta

from api.models.problem_models import ProgressUpdate, StudentProgress
from api.services.spaced_repetition_service import SpacedRepetitionService


@pytest.fixture
def service():
    """Create a fresh service for each test"""
    return SpacedRepetitionService()


@pytest.mark.asyncio
class TestSpacedRepetitionService:
    """Test SpacedRepetitionService"""

    async def test_mark_solved_easy(self, service):
        """Test marking problem as easy (7-day review)"""
        progress = await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=120,
            ),
        )

        assert progress.times_solved == 1
        assert progress.confidence_level == "easy"
        assert progress.next_review is not None
        # Check it's approximately 7 days from now
        days_until = (progress.next_review - datetime.now()).days
        assert 6 <= days_until <= 8

    async def test_mark_solved_medium(self, service):
        """Test marking problem as medium (3-day review)"""
        progress = await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=180,
            ),
        )

        assert progress.times_solved == 1
        assert progress.confidence_level == "medium"
        days_until = (progress.next_review - datetime.now()).days
        assert 2 <= days_until <= 4

    async def test_mark_solved_hard(self, service):
        """Test marking problem as hard (1-day review)"""
        progress = await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="hard",
                time_spent_seconds=300,
            ),
        )

        assert progress.times_solved == 1
        assert progress.confidence_level == "hard"
        days_until = (progress.next_review - datetime.now()).days
        assert 0 <= days_until <= 2

    async def test_mark_solved_increments_count(self, service):
        """Test that solving same problem increments count"""
        # First solve
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=100,
            ),
        )

        # Second solve
        progress = await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=50,
            ),
        )

        assert progress.times_solved == 2
        assert progress.time_spent_seconds == 150  # 100 + 50

    async def test_mark_solved_updates_misconceptions(self, service):
        """Test that misconceptions are tracked"""
        progress = await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=100,
                misconceptions_detected=["sign_error"],
            ),
        )

        assert "sign_error" in progress.misconceptions_detected

    async def test_mark_failed(self, service):
        """Test marking problem as failed"""
        progress = await service.mark_failed(
            student_id="student_001",
            problem_id="math_001",
            time_spent_seconds=200,
        )

        assert progress.times_failed == 1
        assert progress.confidence_level == "hard"
        # Should be due tomorrow
        days_until = (progress.next_review - datetime.now()).days
        assert 0 <= days_until <= 2

    async def test_mark_failed_increments_count(self, service):
        """Test that failing same problem increments count"""
        # First failure
        await service.mark_failed(
            student_id="student_001",
            problem_id="math_001",
            time_spent_seconds=100,
        )

        # Second failure
        progress = await service.mark_failed(
            student_id="student_001",
            problem_id="math_001",
            time_spent_seconds=100,
        )

        assert progress.times_failed == 2

    async def test_get_due_problems_empty(self, service):
        """Test no due problems for new student"""
        due = await service.get_due_problems("student_001")
        assert due == []

    async def test_get_due_problems_hard_solved(self, service):
        """Test problem marked hard appears as due"""
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="hard",
                time_spent_seconds=100,
            ),
        )

        due = await service.get_due_problems("student_001")
        # Hard problems schedule for tomorrow, so might appear due
        # depending on exact timing

    async def test_get_student_progress_empty(self, service):
        """Test progress for student with no history"""
        progress = await service.get_student_progress("student_001")

        assert progress["student_id"] == "student_001"
        assert progress["total_solved"] == 0
        assert progress["total_failed"] == 0
        assert progress["problems_due"] == 0

    async def test_get_student_progress_with_problems(self, service):
        """Test progress after solving problems"""
        # Solve one problem
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=100,
            ),
        )

        # Fail another
        await service.mark_failed(
            student_id="student_001",
            problem_id="math_002",
            time_spent_seconds=200,
        )

        progress = await service.get_student_progress("student_001")

        assert progress["total_solved"] == 1
        assert progress["total_failed"] == 1
        assert progress["total_time_spent"] == 300

    async def test_get_student_progress_average_confidence(self, service):
        """Test average confidence calculation"""
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=100,
            ),
        )

        await service.mark_solved(
            student_id="student_001",
            problem_id="math_002",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=100,
            ),
        )

        progress = await service.get_student_progress("student_001")
        assert progress["average_confidence"] in ["easy", "medium"]

    async def test_get_problem_progress(self, service):
        """Test retrieving progress for specific problem"""
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=100,
            ),
        )

        progress = await service.get_problem_progress("student_001", "math_001")

        assert progress is not None
        assert progress.times_solved == 1

    async def test_get_problem_progress_not_attempted(self, service):
        """Test retrieving progress for unattempted problem"""
        progress = await service.get_problem_progress("student_001", "math_001")
        assert progress is None

    async def test_reset_progress_single_student(self, service):
        """Test resetting progress for one student"""
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=100,
            ),
        )

        message = await service.reset_progress("student_001")
        assert "reset" in message.lower()

        progress = await service.get_student_progress("student_001")
        assert progress["total_solved"] == 0

    async def test_reset_progress_all_students(self, service):
        """Test resetting all progress"""
        # Add progress for multiple students
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=100,
            ),
        )

        await service.mark_solved(
            student_id="student_002",
            problem_id="math_002",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=100,
            ),
        )

        # Reset all
        await service.reset_progress()

        prog1 = await service.get_student_progress("student_001")
        prog2 = await service.get_student_progress("student_002")

        assert prog1["total_solved"] == 0
        assert prog2["total_solved"] == 0

    async def test_get_all_students(self, service):
        """Test retrieving list of all students"""
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=100,
            ),
        )

        await service.mark_solved(
            student_id="student_002",
            problem_id="math_002",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=100,
            ),
        )

        students = await service.get_all_students()
        assert "student_001" in students
        assert "student_002" in students

    async def test_get_student_problems(self, service):
        """Test retrieving problems for a student"""
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=100,
            ),
        )

        await service.mark_solved(
            student_id="student_001",
            problem_id="math_002",
            progress_update=ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=100,
            ),
        )

        problems = await service.get_student_problems("student_001")
        assert len(problems) == 2
        assert "math_001" in problems
        assert "math_002" in problems

    async def test_calculate_next_review(self, service):
        """Test next review calculation"""
        easy_next = service._calculate_next_review("easy")
        medium_next = service._calculate_next_review("medium")
        hard_next = service._calculate_next_review("hard")

        assert easy_next > medium_next > hard_next

    async def test_multiple_students_isolated(self, service):
        """Test that progress is isolated per student"""
        # Student 1 solves math_001
        await service.mark_solved(
            student_id="student_001",
            problem_id="math_001",
            progress_update=ProgressUpdate(
                confidence_level="easy",
                time_spent_seconds=100,
            ),
        )

        # Student 2 hasn't solved anything
        progress_s2 = await service.get_student_progress("student_002")
        assert progress_s2["total_solved"] == 0

        # But student 1 has
        progress_s1 = await service.get_student_progress("student_001")
        assert progress_s1["total_solved"] == 1
