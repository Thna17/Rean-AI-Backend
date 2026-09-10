"""Safety contract for the unpublished Grade 10 Mathematics Logic draft.

The project owner has confirmed the source's curriculum authority. The draft
still must not become learner-facing until its source-linked chunks, glossary,
and distribution checks are complete.
"""
from __future__ import annotations

import json
from pathlib import Path


_DRAFT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curriculum_drafts"
    / "grade_10_math_part1_logic.json"
)


def _draft() -> dict[str, object]:
    with _DRAFT_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def test_logic_draft_is_traceable_unpublished_authoring_material() -> None:
    draft = _draft()

    assert draft["record_type"] == "curriculum_source_draft"
    assert draft["status"] == "authoritative_source_confirmed"
    assert draft["student_delivery"] == "disabled"
    assert draft["grade"] == 10
    assert draft["subject"] == "Mathematics"
    assert draft["chapter"] == {
        "number": 1,
        "english_label": "Logic",
        "khmer_source_label": "តក្កវិជ្ជា",
        "source_table_of_contents_pdf_page": 5,
    }

    source = draft["source"]
    assert isinstance(source, dict)
    assert source["source_id"] == "moeys-math-g10-part1-2020-ch1-logic"
    assert source["authority_status"] == "official_curriculum_source_confirmed_by_project_owner"
    assert source["file_name"] == "Math-Part1-1.pdf"
    assert source["title"] == "Math G10 Part I"
    assert source["publisher"] == "Ministry of Education, Youth and Sport / Publishing and Distribution House"
    assert source["isbn"] == "978-995-000-714"
    assert source["edition_year"] == 2020
    assert source["provided_local_path"] == "/Users/macbookpro/Downloads/Math-Part1-1.pdf"
    assert source["evidence"]["lesson_pdf_pages"] == {
        "start": 9,
        "end": 24,
        "basis": "printed lesson pages 2–17; the next table-of-contents section begins at printed page 18",
    }


def test_logic_draft_requires_reviews_and_contains_no_unreviewed_student_content() -> None:
    draft = _draft()

    assert draft["review_requirements"] == {
        "source_transcription_qa": "required",
        "approved_lesson_chunk": "required",
        "reviewed_glossary_set": "required",
        "distribution_rights_confirmation": "required",
    }
    assert "khmer_terms" not in draft
    assert "approved_glossary" not in draft
    assert draft["publication_state"] == {
        "curriculum_version": "moeys-upper-secondary-2020.draft",
        "review_status": "authoritative_source_confirmed",
        "production_retrieval_enabled": False,
        "pilot_enabled": False,
    }

    # A source draft may describe its scope, but learner-facing explanations,
    # exercises, answer keys, and worked solutions must wait until structured
    # source-linked chunks and a reviewed glossary set are prepared.
    forbidden_keys = {
        "learner_content",
        "student_content",
        "board_actions",
        "explanation",
        "examples",
        "exercises",
        "answer",
        "answers",
        "answer_key",
        "solution",
        "solution_steps",
    }
    assert not (forbidden_keys & set(draft))
