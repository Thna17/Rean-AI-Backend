"""
Test Problem Models - Unit tests for Pydantic models

Tests:
- Problem model creation and validation
- StudentProgress model
- ProgressUpdate model
- JSON serialization/deserialization
"""

import pytest
from datetime import datetime

from api.models.problem_models import (
    Problem,
    ProblemSubject,
    ProblemDifficulty,
    StudentProgress,
    ProgressUpdate,
)


class TestProblemSubject:
    """Test ProblemSubject enum"""

    def test_mathematics(self):
        assert ProblemSubject.MATHEMATICS == "mathematics"

    def test_physics(self):
        assert ProblemSubject.PHYSICS == "physics"

    def test_chemistry(self):
        assert ProblemSubject.CHEMISTRY == "chemistry"


class TestProblemDifficulty:
    """Test ProblemDifficulty enum"""

    def test_easy(self):
        assert ProblemDifficulty.EASY == 1

    def test_medium(self):
        assert ProblemDifficulty.MEDIUM == 2

    def test_intermediate(self):
        assert ProblemDifficulty.INTERMEDIATE == 3

    def test_advanced(self):
        assert ProblemDifficulty.ADVANCED == 4

    def test_expert(self):
        assert ProblemDifficulty.EXPERT == 5


class TestProblem:
    """Test Problem model"""

    def test_problem_creation(self):
        """Test creating a problem"""
        problem = Problem(
            id="math_linear_001",
            subject=ProblemSubject.MATHEMATICS,
            grade_level=10,
            topic="linear_equations",
            subtopic="two_step",
            difficulty=1,
            problem="Solve 2x + 5 = 13",
            answer="4",
            solution_method="inverse_operations",
            expected_steps=4,
            misconceptions=["sign_error"],
            concepts=["equality"],
            tags=["cambodia"],
            created_at=datetime.now(),
            metadata={},
        )

        assert problem.id == "math_linear_001"
        assert problem.subject == ProblemSubject.MATHEMATICS
        assert problem.difficulty == 1
        assert len(problem.misconceptions) == 1

    def test_problem_validation_grade_level(self):
        """Test grade level validation (10-12)"""
        with pytest.raises(ValueError):
            Problem(
                id="test",
                subject=ProblemSubject.MATHEMATICS,
                grade_level=9,  # Invalid
                topic="test",
                difficulty=1,
                problem="test",
                answer="test",
                solution_method="test",
                expected_steps=1,
                created_at=datetime.now(),
            )

    def test_problem_validation_difficulty(self):
        """Test difficulty validation (1-5)"""
        with pytest.raises(ValueError):
            Problem(
                id="test",
                subject=ProblemSubject.MATHEMATICS,
                grade_level=10,
                topic="test",
                difficulty=6,  # Invalid
                problem="test",
                answer="test",
                solution_method="test",
                expected_steps=1,
                created_at=datetime.now(),
            )

    def test_problem_json_serialization(self):
        """Test converting problem to JSON"""
        now = datetime.now()
        problem = Problem(
            id="math_linear_001",
            subject=ProblemSubject.MATHEMATICS,
            grade_level=10,
            topic="linear_equations",
            difficulty=1,
            problem="Solve 2x + 5 = 13",
            answer="4",
            solution_method="inverse_operations",
            expected_steps=4,
            misconceptions=["sign_error"],
            concepts=["equality"],
            tags=["cambodia"],
            created_at=now,
            metadata={"source": "test"},
        )

        json_data = problem.model_dump(mode="json")
        assert json_data["id"] == "math_linear_001"
        assert json_data["subject"] == "mathematics"
        assert json_data["difficulty"] == 1

    def test_problem_json_deserialization(self):
        """Test creating problem from JSON"""
        json_data = {
            "id": "math_linear_001",
            "subject": "mathematics",
            "grade_level": 10,
            "topic": "linear_equations",
            "subtopic": "two_step",
            "difficulty": 1,
            "problem": "Solve 2x + 5 = 13",
            "answer": "4",
            "solution_method": "inverse_operations",
            "expected_steps": 4,
            "misconceptions": ["sign_error"],
            "concepts": ["equality"],
            "tags": ["cambodia"],
            "created_at": "2024-08-26T10:00:00",
            "metadata": {},
        }

        problem = Problem(**json_data)
        assert problem.id == "math_linear_001"
        assert problem.subject == ProblemSubject.MATHEMATICS

    def test_problem_default_values(self):
        """Test default values for optional fields"""
        problem = Problem(
            id="test",
            subject=ProblemSubject.MATHEMATICS,
            grade_level=10,
            topic="test",
            difficulty=1,
            problem="test",
            answer="test",
            solution_method="test",
            expected_steps=1,
            created_at=datetime.now(),
        )

        assert problem.subtopic is None
        assert problem.misconceptions == []
        assert problem.concepts == []
        assert problem.tags == []
        assert problem.metadata == {}


class TestStudentProgress:
    """Test StudentProgress model"""

    def test_progress_creation(self):
        """Test creating progress record"""
        progress = StudentProgress(
            student_id="student_001",
            problem_id="math_linear_001",
            times_solved=1,
            confidence_level="medium",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert progress.student_id == "student_001"
        assert progress.times_solved == 1
        assert progress.confidence_level == "medium"

    def test_progress_validation_times_solved(self):
        """Test times_solved validation (>= 0)"""
        with pytest.raises(ValueError):
            StudentProgress(
                student_id="test",
                problem_id="test",
                times_solved=-1,  # Invalid
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )

    def test_progress_default_values(self):
        """Test default values"""
        progress = StudentProgress(
            student_id="student_001",
            problem_id="math_001",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert progress.times_solved == 0
        assert progress.times_failed == 0
        assert progress.last_seen is None
        assert progress.confidence_level == "new"
        assert progress.next_review is None
        assert progress.time_spent_seconds == 0
        assert progress.misconceptions_detected == []

    def test_progress_json_serialization(self):
        """Test progress to JSON"""
        now = datetime.now()
        progress = StudentProgress(
            student_id="student_001",
            problem_id="math_001",
            times_solved=1,
            confidence_level="medium",
            created_at=now,
            updated_at=now,
        )

        json_data = progress.model_dump(mode="json")
        assert json_data["student_id"] == "student_001"
        assert json_data["times_solved"] == 1

    def test_progress_json_deserialization(self):
        """Test creating progress from JSON"""
        json_data = {
            "student_id": "student_001",
            "problem_id": "math_001",
            "times_solved": 2,
            "times_failed": 0,
            "last_seen": "2024-08-26T10:00:00",
            "confidence_level": "easy",
            "next_review": "2024-09-02T10:00:00",
            "time_spent_seconds": 300,
            "misconceptions_detected": [],
            "created_at": "2024-08-26T10:00:00",
            "updated_at": "2024-08-26T10:00:00",
        }

        progress = StudentProgress(**json_data)
        assert progress.student_id == "student_001"
        assert progress.times_solved == 2


class TestProgressUpdate:
    """Test ProgressUpdate model"""

    def test_progress_update_creation(self):
        """Test creating progress update"""
        update = ProgressUpdate(
            confidence_level="medium",
            time_spent_seconds=180,
        )

        assert update.confidence_level == "medium"
        assert update.time_spent_seconds == 180

    def test_progress_update_with_misconceptions(self):
        """Test progress update with misconceptions"""
        update = ProgressUpdate(
            confidence_level="hard",
            time_spent_seconds=300,
            misconceptions_detected=["sign_error", "arithmetic_error"],
        )

        assert len(update.misconceptions_detected) == 2

    def test_progress_update_validation_time(self):
        """Test time_spent validation (>= 0)"""
        with pytest.raises(ValueError):
            ProgressUpdate(
                confidence_level="medium",
                time_spent_seconds=-10,  # Invalid
            )

    def test_progress_update_default_values(self):
        """Test default values"""
        update = ProgressUpdate(
            confidence_level="easy",
            time_spent_seconds=100,
        )

        assert update.misconceptions_detected is None
        assert update.student_response is None

    def test_progress_update_json_serialization(self):
        """Test update to JSON"""
        update = ProgressUpdate(
            confidence_level="medium",
            time_spent_seconds=180,
            misconceptions_detected=["error1"],
        )

        json_data = update.model_dump(mode="json")
        assert json_data["confidence_level"] == "medium"
        assert json_data["time_spent_seconds"] == 180


class TestModelIntegration:
    """Integration tests for models"""

    def test_problem_and_progress_together(self):
        """Test problem and progress working together"""
        problem = Problem(
            id="math_001",
            subject=ProblemSubject.MATHEMATICS,
            grade_level=10,
            topic="linear_equations",
            difficulty=1,
            problem="Solve x + 5 = 10",
            answer="5",
            solution_method="inverse_operations",
            expected_steps=2,
            created_at=datetime.now(),
        )

        progress = StudentProgress(
            student_id="student_001",
            problem_id=problem.id,
            times_solved=1,
            confidence_level="easy",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert progress.problem_id == problem.id

    def test_progress_update_matches_progress(self):
        """Test ProgressUpdate fields match StudentProgress"""
        update = ProgressUpdate(
            confidence_level="medium",
            time_spent_seconds=180,
            misconceptions_detected=["error1"],
        )

        progress = StudentProgress(
            student_id="student_001",
            problem_id="math_001",
            confidence_level=update.confidence_level,
            time_spent_seconds=update.time_spent_seconds,
            misconceptions_detected=update.misconceptions_detected or [],
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        assert progress.confidence_level == update.confidence_level
        assert progress.time_spent_seconds == update.time_spent_seconds
