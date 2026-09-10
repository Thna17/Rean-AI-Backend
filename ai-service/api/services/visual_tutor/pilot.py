"""Closed-by-default pilot allowlist; curriculum grounding remains authoritative."""
from __future__ import annotations
from fastapi import HTTPException
from api.core.config import settings
from typing import Any

def enforce_pilot_scope(request: Any) -> None:
    if not settings.VISUAL_TUTOR_PILOT_ENABLED:
        return
    grades = {int(value) for value in settings.VISUAL_TUTOR_PILOT_GRADES.split(',') if value.strip().isdigit()}
    subjects = {value.strip().lower() for value in settings.VISUAL_TUTOR_PILOT_SUBJECTS.split(',') if value.strip()}
    lessons = {value.strip().lower() for value in settings.VISUAL_TUTOR_PILOT_LESSONS.split(',') if value.strip()}
    languages = {value.strip().lower() for value in settings.VISUAL_TUTOR_PILOT_LANGUAGE_MODES.split(',') if value.strip()}
    metadata = getattr(request, 'metadata', {}) or {}
    grade = metadata.get('grade_level_hint')
    if not isinstance(grade, int):
        raw_grade = getattr(request, 'grade_level', None)
        grade = int(raw_grade) if str(raw_grade or '').isdigit() else None
    mode = getattr(request, 'language_mode', None)
    language = mode.value if mode else metadata.get('language_mode', 'english')
    if (grade not in grades or str(getattr(request, 'subject', '')).lower() not in subjects
        or not getattr(request, 'topic', None) or request.topic.lower() not in lessons or str(language).lower() not in languages):
        raise HTTPException(403, 'This lesson is not available in the supervised pilot.')
