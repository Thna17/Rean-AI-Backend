import sympy
from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter

router = APIRouter()

class MathQuery(BaseModel):
    expression: str

class MathResponse(BaseModel):
    is_valid: bool
    simplified: Optional[str] = None
    solution: Optional[str] = None
    error: Optional[str] = None

@router.post("/verify")
def verify_math(query: MathQuery) -> MathResponse:
    """
    Evaluates a mathematical expression or equation using SymPy.
    This provides a deterministic sandbox to verify math problems.
    """
    try:
        if "=" in query.expression:
            lhs_str, rhs_str = query.expression.split("=", 1)
            lhs = sympy.sympify(lhs_str.strip())
            rhs = sympy.sympify(rhs_str.strip())
            eq = sympy.Eq(lhs, rhs)
            solution = sympy.solve(eq)
            return MathResponse(
                is_valid=True,
                solution=str(solution)
            )
        else:
            expr = sympy.sympify(query.expression.strip())
            simplified = sympy.simplify(expr)
            return MathResponse(
                is_valid=True,
                simplified=str(simplified)
            )
    except Exception as e:
        return MathResponse(
            is_valid=False,
            error=str(e)
        )
