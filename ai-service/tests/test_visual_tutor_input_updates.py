import pytest
from api.models.visual_tutor import VisualTutorProblemUnderstandingRequest
from api.services.visual_tutor.problem_understanding import (
    understand_visual_tutor_problem,
    _normalize_math_text,
    _strip_khmer,
)

def test_normalize_math_text_implicit_multiplication():
    # 2(x+3) -> 2*(x+3)
    assert _normalize_math_text("2(x+3)=10") == "2*(x+3)=10"
    # x(y+1) -> x*(y+1)
    assert _normalize_math_text("x(y+1)=0") == "x*(y+1)=0"
    # 3x -> 3*x
    assert _normalize_math_text("3x = 15") == "3*x = 15"
    # (x+1)2 -> (x+1)*2
    assert _normalize_math_text("(x+1)2") == "(x+1)*2"
    # (x+1)y -> (x+1)*y
    assert _normalize_math_text("(x+1)y") == "(x+1)*y"

def test_normalize_math_text_ambiguous_fractions():
    # 1/2x -> (1/2)*x
    assert _normalize_math_text("1/2x + 4 = 10") == "(1/2)*x + 4 = 10"
    assert _normalize_math_text("3/4y=5") == "(3/4)*y=5"

def test_normalize_math_text_khmer_stripping():
    # សូមដោះស្រាយ 2x=10 -> 2x=10
    khmer_str = "សូមដោះស្រាយ 2x=10"
    assert _normalize_math_text(khmer_str) == "2*x=10"

def test_understand_visual_tutor_problem_physics_chemistry():
    # Test Physics
    req_phys = VisualTutorProblemUnderstandingRequest(
        subject="physics",
        message="v = u + at",
        locale="en",
    )
    res_phys = understand_visual_tutor_problem(req_phys)
    assert res_phys.subject == "physics"
    assert res_phys.problem_type == "physics_kinematics"
    assert res_phys.known_solver_available is True

    # Test Chemistry
    req_chem = VisualTutorProblemUnderstandingRequest(
        subject="chemistry",
        message="balance H2 + O2 -> H2O",
        locale="en",
    )
    res_chem = understand_visual_tutor_problem(req_chem)
    assert res_chem.subject == "chemistry"
    assert res_chem.problem_type == "chemistry_balancing_equations"
    assert res_chem.known_solver_available is True
