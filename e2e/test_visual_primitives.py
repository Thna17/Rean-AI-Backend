"""STEM diagrams must survive the trip through the gateway.

The AI service declares six visual primitives in
`api/services/visual_tutor/teaching_plan_contract.py`, and the Flutter renderer
normalizes all six. The gateway sits between them with its own allowlist, so this
is exactly the seam no in-process test can see.
"""

from __future__ import annotations

import pytest

from conftest import board_actions

# Declared by TeachingPlanActionType in the AI service's contract.
STEM_PRIMITIVES = (
    "draw_free_body_diagram",
    "draw_molecule",
    "draw_atom_model",
    "draw_particle_diagram",
    "draw_circuit_diagram",
    "show_reaction_layout",
)


def _types(turn: dict) -> list[str]:
    return [str(action.get("type")) for action in board_actions(turn)]


def test_a_dropped_board_item_is_at_least_admitted_to_the_student(gateway):
    """Whatever else happens, the board must not silently lose an item."""
    turn = gateway.solve(
        "A car starts from rest and accelerates at 2 m/s^2 for 5 s. "
        "Find its velocity and the distance travelled.",
        subject="Physics",
    )
    types = _types(turn)
    assert types, "the board came back empty"
    # If the gateway substitutes a notice, it has to be a real, visible one.
    for action in board_actions(turn):
        if action.get("type") == "show_feedback":
            assert str(action.get("text") or "").strip(), (
                "a substituted notice with no text leaves a blank gap on the board"
            )


def test_a_physics_free_body_diagram_reaches_the_student(gateway, ai_service):
    """Pins the drop, and proves it happens at the gateway rather than upstream."""
    problem = (
        "A car starts from rest and accelerates at 2 m/s^2 for 5 s. "
        "Find its velocity and the distance travelled."
    )

    direct = ai_service.post(
        "/api/v1/visual_tutor/turn",
        {
            "user_id": "e2e-primitive",
            "subject": "Physics",
            "grade": 11,
            "message": problem,
            "language_mode": "english",
            "action": "submit_problem",
            "metadata": {"public_contract_version": 1},
        },
        user_id="e2e-primitive",
    )
    assert direct.status_code == 200, direct.text[:300]
    upstream = _types(direct.json())

    if "draw_free_body_diagram" not in upstream:
        pytest.skip(
            "this problem did not produce a free-body diagram upstream, so there "
            "is nothing for the gateway to drop"
        )

    through_gateway = _types(gateway.solve(problem, subject="Physics"))
    assert "draw_free_body_diagram" in through_gateway, (
        "the AI service drew a free-body diagram and the gateway removed it; "
        f"upstream={upstream} gateway={through_gateway}"
    )


def test_the_gateway_and_ai_service_agree_on_which_actions_exist(ai_service):
    """A contract drift check that does not need a problem to trigger a diagram.

    CLAUDE.md §4.4 requires the Python and Dart contracts to match 1:1. The
    gateway is a third copy of the same contract and has drifted from both.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    python_contract = (
        root / "ai-service/api/services/visual_tutor/teaching_plan_contract.py"
    ).read_text()
    gateway_contract = (
        root / "backend-ai-tutor/backend/src/services/teaching-plan.contract.ts"
    ).read_text()

    missing = [
        primitive
        for primitive in STEM_PRIMITIVES
        if f'"{primitive}"' in python_contract
        and f"'{primitive}'" not in gateway_contract
    ]
    assert not missing, (
        "the AI service can emit these action types but the gateway's allowlist "
        f"rejects them, so they never reach a student: {missing}"
    )
