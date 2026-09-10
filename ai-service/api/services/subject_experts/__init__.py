"""Subject-expert factory."""
from api.services.subject_experts.base_expert import SubjectExpert
from api.services.subject_experts.chemistry_expert import ChemistryExpert
from api.services.subject_experts.math_expert import MathExpert
from api.services.subject_experts.physics_expert import PhysicsExpert

async def get_expert(subject: str) -> SubjectExpert:
    experts = {"math": MathExpert, "physics": PhysicsExpert, "chemistry": ChemistryExpert}
    try: return experts[subject.casefold()]()
    except KeyError as exc: raise ValueError(f"Unknown subject: {subject}") from exc

__all__ = ["ChemistryExpert", "MathExpert", "PhysicsExpert", "SubjectExpert", "get_expert"]
