"""Validation contract for teachable moments 02-10 of the Grade 12 Limits
local MVP (moment 01 has its own dedicated coverage in
test_grade_12_math_limits_curriculum_draft.py). Each moment is transcribed
directly from the cited pages of provided-pdf-2025-10-01-00007213 and must
pass the same source-citation and student-safety contract as moment 01.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from api.services.curriculum.local_draft_validation import validate_grade_12_limits_drafts

_DRAFT_PATH = Path(__file__).resolve().parents[1] / "data" / "curriculum_drafts" / "grade_12_math_limits.json"
_MOMENTS_DIR = Path(__file__).resolve().parents[1] / "data" / "curriculum_drafts"
_SOURCE_ID = "provided-pdf-2025-10-01-00007213"

_MOMENT_SUFFIXES = [
    "02_one-sided-infinite",
    "03_at-infinity",
    "04_algebraic-laws",
    "05_composition",
    "06_comparison",
    "07_indeterminate-forms",
    "08_trigonometric",
    "09_exponential",
    "10_logarithmic",
]


def _draft() -> dict:
    with _DRAFT_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _moment(number: str) -> dict:
    path = _MOMENTS_DIR / f"grade_12_math_limits_moment_{number}.json"
    with path.open(encoding="utf-8") as file:
        return json.load(file)


@pytest.mark.parametrize("number", [f"{n:02d}" for n in range(2, 11)])
def test_moment_passes_the_shared_local_draft_validator(number: str) -> None:
    validate_grade_12_limits_drafts(_draft(), _moment(number))


@pytest.mark.parametrize("number", [f"{n:02d}" for n in range(2, 11)])
def test_moment_is_disabled_and_source_linked(number: str) -> None:
    moment = _moment(number)

    assert moment["student_delivery"] == "disabled"
    assert moment["source"]["source_id"] == _SOURCE_ID
    assert moment["lesson"]["id"] == "math.g12.lesson1.limits-of-functions"
    assert moment["grade"] == 12
    assert moment["subject"] == "Mathematics"


@pytest.mark.parametrize("number", [f"{n:02d}" for n in range(2, 11)])
def test_moment_matches_its_own_teachable_moment_index_entry(number: str) -> None:
    moment = _moment(number)
    index_entries = {item["id"]: item for item in _draft()["teachable_moment_index"]}

    entry = index_entries[moment["teaching_moment_id"]]
    assert entry["authoring_status"] == "interactive_draft_created"
    assert entry["visual_representation"] == moment["teaching_plan"]["representation"]
    assert entry["source_pages"] == moment["source"]["pdf_pages"]


def test_all_ten_moments_are_now_drafted() -> None:
    index_entries = _draft()["teachable_moment_index"]
    assert len(index_entries) == 10
    assert all(
        item["authoring_status"] == "interactive_draft_created" for item in index_entries
    )


def test_no_moment_leaks_a_private_answer_field_at_the_json_level() -> None:
    private_keys = {
        "answer", "answers", "answer_key", "final_answer", "final_answer_text",
        "solution", "solution_steps", "accepted_answer_forms",
    }
    for number in [f"{n:02d}" for n in range(1, 11)]:
        moment = _moment(number)
        serialized = json.dumps(moment, ensure_ascii=False)
        for key in private_keys:
            assert f'"{key}"' not in serialized, f"moment {number} leaks {key!r}"
