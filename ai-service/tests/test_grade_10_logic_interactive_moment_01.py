"""Contract for the first unpublished Grade 10 Logic teaching moment.

This protects the source-linked authoring boundary.  It deliberately tests the
draft JSON directly, so the tutor cannot make the moment student-facing before
the content has been reviewed by the curriculum pipeline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_MOMENT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "curriculum_drafts"
    / "grade_10_math_part1_logic_moment_01.json"
)
_KHMER_TEXT = re.compile(r"[\u1780-\u17ff]")
_SEMANTIC_ZONES = {
    "problem",
    "working",
    "visual",
    "student_task",
    "reference",
    "feedback",
}
_SEMANTIC_FLOWS = {"vertical", "horizontal", "overlay", "diagram"}
_ABSOLUTE_GEOMETRY = {"x", "y", "width", "height"}
_ANSWER_FIELDS = {
    "answer",
    "answers",
    "answer_key",
    "final_answer",
    "final_answer_text",
    "solution",
    "solution_steps",
}


def _moment() -> dict[str, Any]:
    with _MOMENT_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _contains_khmer(value: Any) -> bool:
    if isinstance(value, str):
        return bool(_KHMER_TEXT.search(value))
    if isinstance(value, dict):
        return any(_contains_khmer(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_khmer(child) for child in value)
    return False


def test_logic_moment_01_is_a_source_linked_draft_for_exactly_pdf_page_9() -> None:
    moment = _moment()

    assert moment["record_type"] == "interactive_teaching_moment_draft"
    assert moment["student_delivery"] == "disabled"
    assert moment["grade"] == 10
    assert moment["subject"] == "Mathematics"
    assert moment["chapter"] == 1
    assert moment["lesson"]["english_label"] == "Statements"
    assert moment["lesson"]["source_page"] == 9

    source = moment["source"]
    assert source["source_id"] == "moeys-math-g10-part1-2020-ch1-logic"
    assert source["file_name"] == "Math-Part1-1.pdf"
    assert source["pdf_page"] == 9


def test_logic_moment_01_is_one_bounded_interactive_teaching_moment() -> None:
    moment = _moment()

    objectives = moment["learning_objectives"]
    assert len(objectives) == 1
    assert objectives[0]["text"].strip()
    assert objectives[0]["source_page"] == 9

    plan = moment["teaching_plan"]
    explanation = plan["spoken_explanation"]
    assert isinstance(explanation["text"], str)
    assert explanation["text"].strip()
    assert len(explanation["text"].split()) <= 45
    assert isinstance(plan["student_task"], dict)
    assert plan["student_task"]
    assert plan["waiting_for_student_input"] is True
    assert plan["answer_revealed"] is False

    board_actions = plan["board_actions"]
    assert 1 <= len(board_actions) <= 3
    assert "board_actions" not in plan["student_task"]


def test_logic_moment_01_uses_semantic_layout_not_ai_authored_coordinates() -> None:
    for action in _moment()["teaching_plan"]["board_actions"]:
        assert action["layout_zone"] in _SEMANTIC_ZONES
        assert action["layout_flow"] in _SEMANTIC_FLOWS
        assert not (_ABSOLUTE_GEOMETRY & set(action))


def test_logic_moment_01_keeps_khmer_and_glossary_terms_traceable() -> None:
    moment = _moment()
    glossary_terms = moment["glossary_terms"]
    declared_ids = {term["term_id"] for term in glossary_terms}
    assert len(declared_ids) == len(glossary_terms)
    assert all(term["term_khmer"].strip() for term in glossary_terms)
    assert all(term["source_page"] == 9 for term in glossary_terms)

    plan = moment["teaching_plan"]
    for item in [*plan["board_actions"], plan["spoken_explanation"], plan["student_task"]]:
        assert set(item.get("glossary_term_ids", [])) <= declared_ids
        if _contains_khmer(item):
            assert item["glossary_term_ids"], "Khmer STEM terms must be documented"

    for node in _walk(moment):
        direct_text = [value for value in node.values() if isinstance(value, str)]
        if any(_contains_khmer(value) for value in direct_text):
            assert node.get("source_page") == 9


def test_logic_moment_01_does_not_embed_a_solution_or_final_answer() -> None:
    for node in _walk(_moment()):
        assert not (_ANSWER_FIELDS & set(node))
