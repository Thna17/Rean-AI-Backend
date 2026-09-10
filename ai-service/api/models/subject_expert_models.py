"""
Subject Expert Models - Pydantic Models for Domain-Specific Intelligence

Defines data models for subject experts:
- Math Problem Analysis and Misconceptions
- Physics Problem Analysis and Misconceptions
- Chemistry Problem Analysis and Misconceptions
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============================================================
# MATH EXPERT MODELS
# ============================================================

class MathProblemType(str, Enum):
    """Types of math problems that can be analyzed"""
    LINEAR_EQUATION = "linear_equation"
    QUADRATIC_EQUATION = "quadratic_equation"
    SYSTEM_OF_EQUATIONS = "system_of_equations"
    GEOMETRY = "geometry"
    FACTORING = "factoring"
    EXPANDING = "expanding"
    SIMPLIFYING = "simplifying"
    FUNCTIONS = "functions"
    INEQUALITIES = "inequalities"
    TRIGONOMETRY = "trigonometry"


class MathProblemAnalysis(BaseModel):
    """Analysis result for a math problem"""
    problem_type: MathProblemType = Field(..., description="Type of math problem")
    difficulty: int = Field(..., ge=1, le=5, description="Difficulty level (1-5)")
    concepts: List[str] = Field(default_factory=list, description="Concepts involved")
    solution_method: str = Field(..., description="Primary solution method")
    expected_answer: str = Field(default="", description="Expected final answer (if available)")
    has_multiple_solutions: bool = Field(
        False, description="Whether problem has multiple valid answers"
    )
    common_errors: List[str] = Field(default_factory=list, description="Common student mistakes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class MathMisconception(BaseModel):
    """Description of a common math misconception"""
    error_type: str = Field(..., description="Type of error (e.g., 'sign_error', 'distribution')")
    description: str = Field(..., description="What the misconception is")
    explanation: str = Field(..., description="Why this misconception occurs")
    correction: str = Field(..., description="How to correct the misconception")
    similar_errors: List[str] = Field(default_factory=list, description="Related errors")


# ============================================================
# PHYSICS EXPERT MODELS
# ============================================================

class PhysicsProblemType(str, Enum):
    """Types of physics problems that can be analyzed"""
    KINEMATICS = "kinematics"
    DYNAMICS = "dynamics"
    CIRCULAR_MOTION = "circular_motion"
    ENERGY = "energy"
    WAVES = "waves"
    ELECTRICITY = "electricity"
    MAGNETISM = "magnetism"


class PhysicsProblemAnalysis(BaseModel):
    """Analysis result for a physics problem"""
    problem_type: PhysicsProblemType = Field(..., description="Type of physics problem")
    difficulty: int = Field(..., ge=1, le=5, description="Difficulty level (1-5)")
    concepts: List[str] = Field(default_factory=list, description="Physics concepts involved")
    given_values: Dict[str, str] = Field(
        default_factory=dict, description="Known values and their units"
    )
    find_value: str = Field(..., description="What we need to find")
    equations_needed: List[str] = Field(
        default_factory=list, description="Physics equations needed"
    )
    solution_method: str = Field(..., description="Primary solution approach")
    common_errors: List[str] = Field(default_factory=list, description="Common mistakes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class PhysicsMisconception(BaseModel):
    """Description of a common physics misconception"""
    error_type: str = Field(..., description="Type of misconception")
    description: str = Field(..., description="What the misconception is")
    explanation: str = Field(..., description="Why this misconception is common")
    correct_concept: str = Field(..., description="Correct understanding")
    examples: List[str] = Field(default_factory=list, description="Examples showing difference")


# ============================================================
# CHEMISTRY EXPERT MODELS
# ============================================================

class ChemistryProblemType(str, Enum):
    """Types of chemistry problems that can be analyzed"""
    LEWIS_STRUCTURE = "lewis_structure"
    BONDING = "bonding"
    MOLECULAR_GEOMETRY = "molecular_geometry"
    REACTIONS = "reactions"
    STOICHIOMETRY = "stoichiometry"
    ELECTRON_CONFIGURATION = "electron_configuration"


class ChemistryProblemAnalysis(BaseModel):
    """Analysis result for a chemistry problem"""
    problem_type: ChemistryProblemType = Field(..., description="Type of chemistry problem")
    difficulty: int = Field(..., ge=1, le=5, description="Difficulty level (1-5)")
    concepts: List[str] = Field(default_factory=list, description="Chemistry concepts involved")
    molecule_or_reaction: str = Field(..., description="Molecule formula or reaction equation")
    key_information: Dict[str, Any] = Field(
        default_factory=dict, description="Key data about the problem"
    )
    solution_method: str = Field(..., description="Primary solution approach")
    common_errors: List[str] = Field(default_factory=list, description="Common mistakes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class ChemistryMisconception(BaseModel):
    """Description of a common chemistry misconception"""
    error_type: str = Field(..., description="Type of misconception")
    description: str = Field(..., description="What the misconception is")
    explanation: str = Field(..., description="Why this misconception occurs")
    correct_understanding: str = Field(..., description="Correct understanding")
    visual_aid: Optional[str] = Field(None, description="Suggested visual aid")
