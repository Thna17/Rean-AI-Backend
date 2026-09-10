from __future__ import annotations

import pytest

from api.models.visual_tutor import VisualTutorAction, VisualTutorTurnRequest
from api.services.visual_tutor.policy import decide_visual_tutor_policy


def _reviewed_glossary(*, terms: list[dict[str, str]] | None = None) -> dict:
    """One reviewed Grade 10 Mathematics glossary, as retrieval serializes it."""
    return {
        "id": "kh-g10-linear-v1",
        "grade": 10,
        "subject": "Mathematics",
        "lesson": "Linear Equations",
        "glossary_version": "2026.1",
        "curriculum_version": "khmoeys-high-school-2026",
        "source_id": "moeys-math-g10-p12",
        "reviewer_status": "approved",
        "terms": terms
        or [
            {
                "english": "equation",
                "khmer": "សមីការ",
                "glossary_version": "2026.1",
                "curriculum_version": "khmoeys-high-school-2026",
                "source_id": "moeys-math-g10-p12",
                "reviewer_status": "approved",
            },
            {
                "english": "variable",
                "khmer": "អថេរ",
                "glossary_version": "2026.1",
                "curriculum_version": "khmoeys-high-school-2026",
                "source_id": "moeys-math-g10-p12",
                "reviewer_status": "approved",
            },
        ],
    }


@pytest.mark.parametrize(
    ("language_mode", "locale", "message", "expected"),
    [
        ("khmer", "en-US", "Please explain 2x + 5 = 15", "khmer"),
        ("english", "km-KH", "សូមពន្យល់ 2x + 5 = 15", "english"),
        ("bilingual", "km-KH", "សូមពន្យល់ 2x + 5 = 15", "bilingual"),
    ],
)
def test_explicit_language_mode_routes_tutor_output(
    language_mode: str, locale: str, message: str, expected: str
) -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="language-mode-student",
            locale=locale,
            message=message,
            action=VisualTutorAction.SUBMIT_PROBLEM,
            language_mode=language_mode,
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert policy.metadata["language_mode"] == expected
    assert policy.use_khmer_explanation is (expected in {"khmer", "bilingual"})


def test_language_mode_defaults_from_locale_when_not_explicit() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="language-mode-default",
            locale="km-KH",
            message="សូមជួយពន្យល់",
            action=VisualTutorAction.SUBMIT_PROBLEM,
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert policy.metadata["language_mode"] == "khmer"


def test_only_reviewed_provenanced_curriculum_glossary_terms_are_exposed() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="glossary-student",
            locale="km-KH",
            message="សូមពន្យល់សមីការ",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={
                "curriculum_context": {
                    "reviewed_khmer_glossary": _reviewed_glossary(),
                    # Historical authoring metadata must never be treated as
                    # terminology, even if it conflicts with the reviewed set.
                    "khmer_terms": {"equation": "មិនត្រូវបង្ហាញ"},
                },
            },
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert policy.metadata["approved_glossary_terms"] == {
        "equation": "សមីការ",
        "variable": "អថេរ",
    }
    assert policy.metadata["glossary_term_provenance"]["equation"] == {
        "glossary_version": "2026.1",
        "curriculum_version": "khmoeys-high-school-2026",
        "source_id": "moeys-math-g10-p12",
        "reviewer_status": "approved",
    }
    assert "khmer_terms" not in policy.metadata
    assert policy.metadata["glossary_gaps"] == []


def test_missing_glossary_term_is_marked_for_curriculum_review_not_invented() -> None:
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="glossary-gap-student",
            locale="km-KH",
            message="សូមពន្យល់អំពី slope",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={
                "language_mode": "khmer",
                "curriculum_context": {
                    "reviewed_khmer_glossary": _reviewed_glossary(),
                    "khmer_terms": {"slope": "មិនត្រូវបង្ហាញ"},
                },
                "required_glossary_terms": ["slope"],
            },
        ),
        has_problem=True,
        problem_type="slope_from_two_points",
    )

    assert policy.metadata["approved_glossary_terms"] == {
        "equation": "សមីការ",
        "variable": "អថេរ",
    }
    assert policy.metadata["glossary_gaps"] == ["slope"]
    assert policy.metadata["curriculum_review_queue_items"] == [
        {
            "kind": "glossary_gap",
            "term": "slope",
            "grade": 10,
            "subject": "Mathematics",
            "lesson": "Linear Equations",
            "reason": "no_approved_khmer_term",
        },
    ]
    assert "student" not in str(policy.metadata["curriculum_review_queue_items"])
    assert "មិនត្រូវបង្ហាញ" not in str(policy.metadata)


def test_incomplete_or_unreviewed_glossary_evidence_fails_closed() -> None:
    invalid = _reviewed_glossary(
        terms=[
            {
                "english": "equation",
                "khmer": "សមីការ",
                "glossary_version": "2026.1",
                "curriculum_version": "khmoeys-high-school-2026",
                # A reviewed term without its source/reviewer evidence must
                # not become a learner-facing translation.
                "reviewer_status": "approved",
            },
        ],
    )
    policy = decide_visual_tutor_policy(
        VisualTutorTurnRequest(
            user_id="unreviewed-glossary-student",
            locale="km-KH",
            message="សូមពន្យល់សមីការ",
            action=VisualTutorAction.SUBMIT_PROBLEM,
            metadata={
                "curriculum_context": {"reviewed_khmer_glossary": invalid},
                "required_glossary_terms": ["equation"],
            },
        ),
        has_problem=True,
        problem_type="linear_equation_one_variable",
    )

    assert policy.metadata["approved_glossary_terms"] == {}
    assert policy.metadata["glossary_gaps"] == ["equation"]
    assert policy.metadata["curriculum_review_queue_items"][0]["term"] == "equation"
