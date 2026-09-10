"""Contract coverage for renderer-safe Grade 10--12 STEM primitives."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from api.services.visual_tutor.teaching_plan_contract import validate_teaching_plan


def _plan_for(action: dict) -> dict:
    return {
        "schema_version": 1,
        "representation": "conceptual_explanation",
        "learning_objective": "Interpret one bounded STEM visual.",
        "teaching_message": "Study this visual, then explain one observation.",
        "board_actions": [
            action,
            {
                "id": "task",
                "type": "student_task",
                "sequence_index": 1,
                "text": "What does this visual show?",
                "requires_student_response": True,
            },
        ],
        "allowed_student_actions": ["submit_answer", "request_hint"],
        "hidden_answer_policy": {
            "mode": "hidden",
            "deterministic_policy_permits_final_reveal": False,
        },
        "next_state_policy": {
            "correct": "continue",
            "invalid": "reteach",
            "incomplete": "ask_for_work",
            "stuck": "reteach",
            "hint": "ask_for_work",
            "explain_differently": "reteach",
        },
    }


@pytest.mark.parametrize(
    ("action", "expected_type"),
    [
        (
            {
                "id": "fbd",
                "type": "draw_free_body_diagram",
                "sequence_index": 0,
                "layout_zone": "visual",
                "layout_flow": "diagram",
                "forces": [
                    {"direction": "up", "label": "N"},
                    {"direction": "down", "label": "W"},
                ],
            },
            "draw_free_body_diagram",
        ),
        (
            {
                "id": "molecule",
                "type": "draw_molecule",
                "sequence_index": 0,
                "layout_zone": "visual",
                "layout_flow": "diagram",
                "points": [
                    {"x": 0.5, "y": 0.35, "label": "O"},
                    {"x": 0.25, "y": 0.75, "label": "H"},
                    {"x": 0.75, "y": 0.75, "label": "H"},
                ],
                "molecule_bonds": [
                    {"from_index": 0, "to_index": 1, "order": 1},
                    {"from_index": 0, "to_index": 2, "order": 1},
                ],
            },
            "draw_molecule",
        ),
        (
            {
                "id": "wave",
                "type": "draw_wave",
                "sequence_index": 0,
                "layout_zone": "visual",
                "layout_flow": "diagram",
                "width": 280,
                "height": 160,
            },
            "draw_wave",
        ),
        (
            {
                "id": "atom",
                "type": "draw_atom_model",
                "sequence_index": 0,
                "layout_zone": "visual",
                "layout_flow": "diagram",
                "atom_model": {
                    "symbol": "Na",
                    "protons": 11,
                    "neutrons": 12,
                    "electrons_per_shell": [2, 8, 1],
                },
            },
            "draw_atom_model",
        ),
        (
            {
                "id": "particles",
                "type": "draw_particle_diagram",
                "sequence_index": 0,
                "layout_zone": "visual",
                "layout_flow": "diagram",
                "particle_diagram": {
                    "state": "gas",
                    "particle_count": 12,
                    "particle_label": "oxygen particle",
                },
            },
            "draw_particle_diagram",
        ),
        (
            {
                "id": "circuit",
                "type": "draw_circuit_diagram",
                "sequence_index": 0,
                "layout_zone": "visual",
                "layout_flow": "diagram",
                "circuit_diagram": {
                    "components": [
                        {"kind": "cell", "label": "6 V"},
                        {"kind": "lamp", "label": "Lamp"},
                        {"kind": "switch", "label": "S"},
                    ],
                },
            },
            "draw_circuit_diagram",
        ),
        (
            {
                "id": "reaction",
                "type": "show_reaction_layout",
                "sequence_index": 0,
                "layout_zone": "visual",
                "layout_flow": "horizontal",
                "reaction_layout": {
                    "reactants": ["H2", "O2"],
                    "products": ["H2O"],
                    "coefficients": [2, 1, 2],
                },
            },
            "show_reaction_layout",
        ),
    ],
)
def test_accepts_only_bounded_typed_stem_visual_data(
    action: dict, expected_type: str
) -> None:
    plan = validate_teaching_plan(_plan_for(action))

    assert plan.board_actions[0].type.value == expected_type
    assert plan.board_actions[0].layout_zone.value == "visual"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda action: action.update(forces=[]),
        lambda action: action["forces"].append(
            {"direction": "diagonal", "label": "bad"}
        ),
    ],
)
def test_free_body_diagrams_reject_missing_or_unbounded_force_data(mutate) -> None:
    action = {
        "id": "fbd", "type": "draw_free_body_diagram", "sequence_index": 0,
        "forces": [{"direction": "up", "label": "N"}],
    }
    mutate(action)
    with pytest.raises(ValidationError):
        validate_teaching_plan(_plan_for(action))


@pytest.mark.parametrize(
    "action",
    [
        {"id": "m", "type": "draw_molecule", "sequence_index": 0},
        {"id": "w", "type": "draw_wave", "sequence_index": 0, "width": 240},
        {
            "id": "a", "type": "draw_atom_model", "sequence_index": 0,
            "atom_model": {"symbol": "Na", "protons": 11, "neutrons": 12, "electrons_per_shell": [119]},
        },
        {
            "id": "p", "type": "draw_particle_diagram", "sequence_index": 0,
            "particle_diagram": {"state": "plasma", "particle_count": 12},
        },
        {
            "id": "c", "type": "draw_circuit_diagram", "sequence_index": 0,
            "circuit_diagram": {"components": [{"kind": "lamp"}, {"kind": "switch"}]},
        },
        {
            "id": "r", "type": "show_reaction_layout", "sequence_index": 0,
            "reaction_layout": {"reactants": ["H2"], "products": ["H2O"], "coefficients": [0, 1]},
        },
    ],
)
def test_stem_visuals_reject_missing_or_invalid_typed_payloads(action: dict) -> None:
    with pytest.raises(ValidationError):
        validate_teaching_plan(_plan_for(deepcopy(action)))


def test_stem_visual_contract_rejects_untyped_renderer_code() -> None:
    action = {
        "id": "circuit", "type": "draw_circuit_diagram", "sequence_index": 0,
        "circuit_diagram": {"components": [{"kind": "cell"}, {"kind": "lamp"}]},
        "svg": "<svg onload=alert(1)>",
    }
    with pytest.raises(ValidationError):
        validate_teaching_plan(_plan_for(action))


def test_molecule_bonds_must_reference_declared_atoms() -> None:
    action = {
        "id": "molecule", "type": "draw_molecule", "sequence_index": 0,
        "points": [{"x": 0.5, "y": 0.5, "label": "O"}],
        "molecule_bonds": [{"from_index": 0, "to_index": 2, "order": 1}],
    }
    with pytest.raises(ValidationError):
        validate_teaching_plan(_plan_for(action))
