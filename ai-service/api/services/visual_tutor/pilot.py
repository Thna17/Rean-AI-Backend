"""Supervised pilot allowlist gate grounded in curriculum scope."""
from __future__ import annotations

from typing import Any
from fastapi import HTTPException

from api.core.config import settings
from api.services.visual_tutor.scope import build_out_of_scope_message, check_scope


def enforce_pilot_scope(request: Any) -> None:
    """Enforces that the request falls within the supervised Grade 12 STEM pilot."""
    if not settings.VISUAL_TUTOR_PILOT_ENABLED:
        return

    metadata = getattr(request, "metadata", {}) or {}
    grade = (
        metadata.get("grade")
        or metadata.get("grade_level")
        or metadata.get("grade_level_hint")
    )
    if grade is None:
        raw_grade = getattr(request, "grade_level", None)
        grade = int(raw_grade) if str(raw_grade or "").isdigit() else None

    mode = getattr(request, "language_mode", None)
    language = (
        mode.value
        if hasattr(mode, "value")
        else (mode or metadata.get("language_mode", "english"))
    )

    subject = getattr(request, "subject", "")
    topic = getattr(request, "topic", None)
    message = getattr(request, "message", "")
    problem_text = getattr(
        getattr(request, "current_state", None), "problem_text", ""
    ) or getattr(request, "problem_text", "")

    decision = check_scope(
        grade=grade,
        subject=subject,
        topic=topic,
        topic_id=metadata.get("topic_id"),
        message=message,
        problem_text=problem_text,
        language_mode=str(language) if language else None,
    )

    if not decision.is_in_scope:
        refusal = build_out_of_scope_message(str(language))
        raise HTTPException(403, refusal["display_text"])

    # If explicit lessons filter is active in pilot config, enforce it
    pilot_lessons = {
        value.strip().lower()
        for value in settings.VISUAL_TUTOR_PILOT_LESSONS.split(",")
        if value.strip()
    }
    if pilot_lessons:
        norm_topic = (topic or "").strip().lower()
        norm_topic_id = str(metadata.get("topic_id") or "").strip().lower()
        if norm_topic not in pilot_lessons and norm_topic_id not in pilot_lessons:
            refusal = build_out_of_scope_message(str(language))
            raise HTTPException(403, refusal["display_text"])
