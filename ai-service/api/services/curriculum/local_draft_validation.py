"""Validation for source-linked, non-published local curriculum drafts."""
from __future__ import annotations

from typing import Any


_ALLOWED_GLOSSARY_STATUSES = {"source_transcription_verified", "approved"}
_PRIVATE_ANSWER_FIELDS = {
    "answer", "answers", "answer_key", "final_answer", "final_answer_text",
    "solution", "solution_steps", "accepted_answer_forms", "expected_operation", "expected_step",
}


def validate_grade_12_limits_drafts(draft: dict[str, Any], moment: dict[str, Any]) -> None:
    """Fail closed until the exact local Grade 12 Limits source is well formed."""
    source_id = "provided-pdf-2025-10-01-00007213"
    lesson_id = "math.g12.lesson1.limits-of-functions"
    if draft.get("grade") != 12 or draft.get("subject") != "Mathematics":
        raise ValueError("unsupported local MVP curriculum scope")
    if draft.get("student_delivery") != "disabled":
        raise ValueError("local curriculum draft must not enable student delivery")
    publication = draft.get("publication_state", {})
    if publication.get("production_retrieval_enabled") is not False or publication.get("pilot_enabled") is not False:
        raise ValueError("local curriculum draft must not enable publication")
    contexts = draft.get("mvp_scope", {}).get("supported_contexts", [])
    if contexts != [{"grade": 12, "subject": "Mathematics", "topic_id": "math-g12-limits-of-functions", "lesson_id": lesson_id}]:
        raise ValueError("local MVP must advertise exactly one supported context")
    if draft.get("mvp_scope", {}).get("unsupported_by_default") is not True:
        raise ValueError("local MVP scope must be default deny")
    if draft.get("source", {}).get("source_id") != source_id:
        raise ValueError("draft source_id is required")
    if moment.get("grade") != 12 or moment.get("subject") != "Mathematics" or moment.get("lesson", {}).get("id") != lesson_id:
        raise ValueError("interactive moment is outside the local MVP scope")
    if moment.get("student_delivery") != "disabled":
        raise ValueError("local interactive moment must not enable student delivery")
    if moment.get("source", {}).get("source_id") != source_id:
        raise ValueError("moment source_id is required")
    _require_citations(draft.get("source_formula_catalog", []), "formula")
    _require_citations(moment.get("source_formulas", []), "formula")
    progression = moment.get("interactive_progression", {})
    if progression.get("source_id") != source_id:
        raise ValueError("interactive progression source_id is required")
    _require_citations(progression.get("steps", []), "interactive progression step")
    _require_moment_outline_citations(draft.get("teachable_moment_index", []), source_id)
    for item in [*draft.get("glossary_terms", []), *moment.get("glossary_terms", [])]:
        if not item.get("term_khmer") or item.get("reviewer_status") not in _ALLOWED_GLOSSARY_STATUSES:
            raise ValueError("unreviewed Khmer glossary term")
        _require_citations([item], "glossary term")
    objectives = moment.get("learning_objectives", [])
    if len(objectives) != 1:
        raise ValueError("a local teaching moment needs exactly one objective")
    _require_citations(objectives, "learning objective")
    _require_citations(moment.get("prerequisite_concepts", []), "prerequisite concept")
    for misconception in moment.get("common_misconceptions", []):
        if misconception.get("review_status") != "pedagogical_review_required":
            _require_citations([misconception], "common misconception")
    plan = moment.get("teaching_plan", {})
    actions = plan.get("board_actions", [])
    if not 1 <= len(actions) <= 3 or sum(action.get("type") == "student_task" for action in actions) != 1:
        raise ValueError("a local teaching moment needs one bounded student task")
    _require_citations([plan.get("spoken_explanation", {}), *actions, plan.get("student_task", {})], "teaching content")
    task_actions = [action for action in actions if action.get("type") == "student_task"]
    if not task_actions[0].get("text") or task_actions[0].get("requires_student_response") is not True:
        raise ValueError("student task must contain a question and wait for a response")
    if plan.get("student_task", {}).get("requires_student_response") is not True or plan.get("waiting_for_student_input") is not True:
        raise ValueError("teaching moment must wait for the student")
    policy = plan.get("hidden_answer_policy", {})
    if policy.get("mode") != "hidden" or policy.get("deterministic_policy_permits_final_reveal") is not False or plan.get("answer_revealed") is not False:
        raise ValueError("first teaching moment must keep the answer locked")
    _reject_private_answer_fields(moment)


def _require_citations(items: list[dict[str, Any]], label: str) -> None:
    if not items or any(not item.get("source_id") or not isinstance(item.get("source_page"), int) for item in items):
        raise ValueError(f"uncited {label}")


def _require_moment_outline_citations(items: list[dict[str, Any]], source_id: str) -> None:
    if not items:
        raise ValueError("missing teachable moment index")
    for item in items:
        pages = item.get("source_pages")
        if item.get("source_id") != source_id or not isinstance(pages, list) or not pages or any(not isinstance(page, int) or page < 1 or page > 26 for page in pages):
            raise ValueError("uncited teachable moment outline")


def _reject_private_answer_fields(value: Any) -> None:
    if isinstance(value, dict):
        if _PRIVATE_ANSWER_FIELDS & set(value):
            raise ValueError("private answer data is not allowed in a local teaching draft")
        for child in value.values():
            _reject_private_answer_fields(child)
    elif isinstance(value, list):
        for child in value:
            _reject_private_answer_fields(child)
