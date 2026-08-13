from __future__ import annotations

import random
from typing import Any, Dict, Optional


def generate_practice_problem(
    topic: str,
    metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Generates a new practice problem for the Visual Tutor based on the topic.
    Returns a dict with 'problem_text' and 'problem_type'.
    """
    topic_normalized = topic.lower().strip()
    
    if "linear equation" in topic_normalized:
        return _generate_linear_equation(metadata)
        
    # Never substitute a different topic. The caller can return a transparent
    # unavailable state and keep the learner's progress accurate.
    return None


def _generate_linear_equation(metadata: Dict[str, Any]) -> Dict[str, Any]:
    # Randomly select a format: ax + b = c, or ax - b = c
    a = random.randint(2, 9)
    b = random.randint(1, 20)
    
    # Ensure a clean integer answer by picking x first
    x = random.randint(1, 12)
    is_addition = random.choice([True, False])
    
    if is_addition:
        c = (a * x) + b
        problem_text = f"{a}x + {b} = {c}"
    else:
        c = (a * x) - b
        problem_text = f"{a}x - {b} = {c}"
        
    return {
        "problem_text": problem_text,
        "problem_type": "linear_equation_one_variable",
    }
