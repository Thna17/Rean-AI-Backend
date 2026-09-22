"""
Problem Repository - Data Access Layer for Problem Bank

Loads problems from JSON file and provides query methods.
Handles all problem persistence and retrieval for Phase 1 MVP.

In Phase 2, this will be replaced with database queries.
"""

import json
import logging
from pathlib import Path
from typing import List, Optional

from api.models.problem_models import Problem

logger = logging.getLogger(__name__)


DEFAULT_PROBLEMS_PATH = Path(__file__).resolve().parents[2] / "data" / "problems.json"


class ProblemRepository:
    """
    Repository for loading and querying problems from JSON.
    
    Loads all problems into memory on initialization.
    Provides query methods for filtering by subject, difficulty, topic, etc.
    """

    def __init__(self, data_path: str | None = None) -> None:
        """
        Initialize repository and load problems from JSON.
        
        Args:
            data_path: Path to problems.json file. Defaults to this service's
                data/problems.json, independent of the working directory.
        """
        self.data_path = data_path or str(DEFAULT_PROBLEMS_PATH)
        self.problems: List[Problem] = []
        self._load_problems()

    def _load_problems(self) -> None:
        """
        Load problems from JSON file.
        
        Parses JSON and creates Problem objects. Handles missing files gracefully.
        """
        try:
            path = Path(self.data_path)
            if not path.exists():
                logger.warning(f"Problems file not found: {self.data_path}")
                return

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Parse each item as a Problem object
            for item in data:
                try:
                    problem = Problem(**item)
                    self.problems.append(problem)
                except Exception as e:
                    logger.error(f"Failed to parse problem {item.get('id')}: {str(e)}")

            logger.info(f"Loaded {len(self.problems)} problems from {self.data_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {self.data_path}: {str(e)}")
        except Exception as e:
            logger.error(f"Error loading problems: {str(e)}")

    def get_all(self) -> List[Problem]:
        """
        Get all problems.
        
        Returns:
            List of all Problem objects
        """
        return self.problems

    def get_by_id(self, problem_id: str) -> Optional[Problem]:
        """
        Find problem by exact ID match.
        
        Args:
            problem_id: Problem identifier
            
        Returns:
            Problem object or None if not found
        """
        for problem in self.problems:
            if problem.id == problem_id:
                return problem
        return None

    def get_by_subject(self, subject: str) -> List[Problem]:
        """
        Get all problems for a subject.
        
        Args:
            subject: Subject name (case-insensitive)
            
        Returns:
            List of Problem objects, sorted by difficulty
        """
        subject_lower = subject.lower()
        matching = [
            p for p in self.problems if p.subject.value.lower() == subject_lower
        ]
        # Sort by difficulty
        return sorted(matching, key=lambda p: p.difficulty)

    def get_by_difficulty(self, difficulty: int) -> List[Problem]:
        """
        Get all problems at a specific difficulty level.
        
        Args:
            difficulty: Difficulty level (1-5)
            
        Returns:
            List of Problem objects
        """
        return [p for p in self.problems if p.difficulty == difficulty]

    def get_by_topic(self, topic: str) -> List[Problem]:
        """
        Get all problems for a topic (substring match, case-insensitive).
        
        Args:
            topic: Topic name
            
        Returns:
            List of Problem objects
        """
        topic_lower = topic.lower()
        matching = [
            p for p in self.problems if topic_lower in p.topic.lower()
        ]
        return sorted(matching, key=lambda p: p.difficulty)

    def get_by_grade_level(self, grade_level: int) -> List[Problem]:
        """
        Get all problems for a grade level.
        
        Args:
            grade_level: Grade (10, 11, or 12)
            
        Returns:
            List of Problem objects
        """
        return [p for p in self.problems if p.grade_level == grade_level]

    def get_random(self, count: int = 1, subject: Optional[str] = None) -> List[Problem]:
        """
        Get random problems.
        
        Args:
            count: Number of random problems to return
            subject: Optional subject filter
            
        Returns:
            List of random Problem objects
        """
        import random

        # Filter by subject if provided
        pool = self.get_by_subject(subject) if subject else self.problems

        # Return random sample
        if count >= len(pool):
            return pool
        return random.sample(pool, count)

    def search(
        self,
        subject: Optional[str] = None,
        difficulty: Optional[int] = None,
        topic: Optional[str] = None,
        grade_level: Optional[int] = None,
    ) -> List[Problem]:
        """
        Search problems with multiple filters.
        
        All filters are optional (if None, don't filter on that dimension).
        
        Args:
            subject: Subject filter
            difficulty: Difficulty level filter
            topic: Topic filter
            grade_level: Grade level filter
            
        Returns:
            List of Problem objects matching ALL filters
        """
        results = self.problems

        if subject:
            results = [p for p in results if p.subject.value.lower() == subject.lower()]

        if difficulty:
            results = [p for p in results if p.difficulty == difficulty]

        if topic:
            topic_lower = topic.lower()
            results = [p for p in results if topic_lower in p.topic.lower()]

        if grade_level:
            results = [p for p in results if p.grade_level == grade_level]

        # Sort by difficulty
        return sorted(results, key=lambda p: p.difficulty)

    def count(self) -> int:
        """
        Get total number of problems.
        
        Returns:
            Integer count
        """
        return len(self.problems)

    def count_by_subject(self, subject: str) -> int:
        """
        Get count of problems for a subject.
        
        Args:
            subject: Subject name
            
        Returns:
            Integer count
        """
        return len(self.get_by_subject(subject))

    def get_statistics(self) -> dict:
        """
        Get statistics about the problem bank.
        
        Returns:
            Dictionary with counts by subject, grade, difficulty
        """
        stats = {
            "total": len(self.problems),
            "by_subject": {},
            "by_grade": {},
            "by_difficulty": {},
        }

        for problem in self.problems:
            # Count by subject
            subject = problem.subject.value
            stats["by_subject"][subject] = stats["by_subject"].get(subject, 0) + 1

            # Count by grade
            grade = problem.grade_level
            stats["by_grade"][grade] = stats["by_grade"].get(grade, 0) + 1

            # Count by difficulty
            diff = problem.difficulty
            stats["by_difficulty"][diff] = stats["by_difficulty"].get(diff, 0) + 1

        return stats
