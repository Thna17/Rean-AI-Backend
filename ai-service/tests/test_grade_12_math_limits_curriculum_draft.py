"""Validation contract for the narrow Grade 12 Mathematics Limits local MVP."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from api.services.curriculum.local_draft_validation import validate_grade_12_limits_drafts


_DRAFT_PATH = Path(__file__).resolve().parents[1] / "data" / "curriculum_drafts" / "grade_12_math_limits.json"
_MOMENT_PATH = Path(__file__).resolve().parents[1] / "data" / "curriculum_drafts" / "grade_12_math_limits_moment_01.json"
_SOURCE_ID = "provided-pdf-2025-10-01-00007213"


def _documents() -> tuple[dict, dict]:
    with _DRAFT_PATH.open(encoding="utf-8") as file:
        draft = json.load(file)
    with _MOMENT_PATH.open(encoding="utf-8") as file:
        moment = json.load(file)
    return draft, moment


def test_grade_12_limits_draft_is_source_linked_and_local_only() -> None:
    draft, moment = _documents()

    validate_grade_12_limits_drafts(draft, moment)

    assert draft["student_delivery"] == "disabled"
    assert draft["source"]["source_id"] == _SOURCE_ID
    assert draft["source"]["file_name"] == "Pages from 2025-10-01-00007213.pdf"
    assert draft["lesson"]["khmer_source_label"] == "លីមីតនៃអនុគមន៍"
    assert draft["mvp_scope"]["unsupported_by_default"] is True
    assert all(item["authoring_status"] in {"interactive_draft_created", "source_outline_only"} for item in draft["teachable_moment_index"])
    assert moment["teaching_moment_id"].endswith("finite-at-point.01")
    assert all(
        step["source_id"] == _SOURCE_ID and step["source_page"] == 1
        for step in moment["interactive_progression"]["steps"]
    )


def test_every_formula_and_glossary_term_is_source_cited_and_reviewed() -> None:
    draft, moment = _documents()

    formulae = [*draft["source_formula_catalog"], *moment["source_formulas"]]
    assert formulae
    assert all(item["source_id"] == _SOURCE_ID and isinstance(item["source_page"], int) for item in formulae)
    glossary = [*draft["glossary_terms"], *moment["glossary_terms"]]
    assert glossary
    assert all(item["term_khmer"] and item["reviewer_status"] == "source_transcription_verified" for item in glossary)
    assert all(item["curriculum_version"] == "local-g12-math-limits-2025-10-01-v1" for item in glossary)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda draft, moment: draft["source"].pop("source_id"),
        lambda draft, moment: draft.update({"student_delivery": "enabled"}),
        lambda draft, moment: moment.update({"student_delivery": "enabled"}),
        lambda draft, moment: draft["publication_state"].update({"pilot_enabled": True}),
        lambda draft, moment: draft["mvp_scope"].update({"unsupported_by_default": False}),
        lambda draft, moment: draft["mvp_scope"]["supported_contexts"][0].update({"grade": 11}),
        lambda draft, moment: draft["mvp_scope"]["supported_contexts"][0].update({"subject": "Physics"}),
        lambda draft, moment: moment["lesson"].update({"id": "math.g12.lesson2.other"}),
        lambda draft, moment: moment["glossary_terms"][0].update({"reviewer_status": "unreviewed"}),
        lambda draft, moment: draft["teachable_moment_index"][0].pop("source_id"),
        lambda draft, moment: moment["source_formulas"][0].pop("source_page"),
        lambda draft, moment: moment["interactive_progression"]["steps"][0].pop("source_id"),
        lambda draft, moment: moment["prerequisite_concepts"][0].pop("source_page"),
        lambda draft, moment: moment["common_misconceptions"][0].update({"review_status": "source_supported"}),
        lambda draft, moment: moment["teaching_plan"].update({"waiting_for_student_input": False}),
        lambda draft, moment: moment["teaching_plan"]["hidden_answer_policy"].update({"deterministic_policy_permits_final_reveal": True}),
        lambda draft, moment: moment["teaching_plan"]["board_actions"][2].update({"answer_key": {"final": "5"}}),
    ],
)
def test_validator_rejects_unsafe_or_unsupported_local_draft(mutate) -> None:
    draft, moment = (copy.deepcopy(value) for value in _documents())
    mutate(draft, moment)

    with pytest.raises(ValueError):
        validate_grade_12_limits_drafts(draft, moment)


def test_first_moment_is_small_source_cited_and_answer_locked() -> None:
    _, moment = _documents()
    plan = moment["teaching_plan"]

    assert len(moment["learning_objectives"]) == 1
    assert len(plan["board_actions"]) == 3
    assert [action["type"] for action in plan["board_actions"]] == ["write_text", "show_table", "student_task"]
    assert all("source_id" in action and "source_page" in action for action in plan["board_actions"])
    assert plan["student_task"]["requires_student_response"] is True
    assert plan["waiting_for_student_input"] is True
    assert plan["answer_revealed"] is False
    assert plan["hidden_answer_policy"] == {
        "mode": "hidden",
        "deterministic_policy_permits_final_reveal": False,
    }
    serialized = json.dumps(moment, ensure_ascii=False)
    for private_key in ("answer_key", "final_answer", "solution_steps", "accepted_answer_forms"):
        assert private_key not in serialized
