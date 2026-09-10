"""Privacy-safe Visual Tutor metrics for the existing in-process telemetry stack.

Events intentionally contain only bounded enums/counts.  Do not add prompts,
answers, session/user IDs, tokens, or learner-memory values here.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from api.services.telemetry import get_telemetry

logger = logging.getLogger(__name__)

_SAFE_TAGS = {
    "action_type", "lifecycle", "reason", "subject", "grade", "language",
    "tutor_move", "representation", "outcome", "misconception_category",
    "recovery", "device_class", "screen_class",
    "reduced_motion",
}


def _tags(values: dict[str, Any]) -> dict[str, str]:
    safe: dict[str, str] = {}
    for key, value in values.items():
        text = str(value).lower()
        # Tags are dimensions, never text. Restrict to bounded machine enums.
        if key in _SAFE_TAGS and re.fullmatch(r"[a-z0-9_-]{1,64}", text):
            safe[key] = text
    return safe


@dataclass
class VisualTutorTelemetry:
    """Structured, bounded Visual Tutor instrumentation and release gates."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def record_event(self, name: str, *, value: float = 1, unit: str = "count", **tags: Any) -> None:
        safe_tags = _tags(tags)
        event = {"event": name, "value": value, "unit": unit, "tags": safe_tags}
        self.events.append(event)
        get_telemetry().record_metric(name, value, unit=unit, tags=safe_tags)
        logger.info("visual_tutor_event=%s tags=%s", name, safe_tags)

    def dashboard_snapshot(self) -> dict[str, Any]:
        dashboard = get_telemetry().get_dashboard_data()
        return {"visual_tutor": dashboard, "recent_event_count": len(self.events)}

    def record_board_action(self, lifecycle: str, *, action_type: str, off_screen: bool = False) -> None:
        """Track client lifecycle summaries without action IDs or board contents."""
        if lifecycle not in {"received", "validated", "rendered", "skipped"}:
            return
        self.record_event("visual_tutor.board.action", lifecycle=lifecycle, action_type=action_type)
        if off_screen:
            self.record_event("visual_tutor.board.action_off_screen", lifecycle=lifecycle, action_type=action_type)

    def evaluate_release_gates(self, evidence: dict[str, Any]) -> dict[str, bool]:
        """Evaluate deterministic acceptance evidence; missing evidence fails closed."""
        return {
            "no_active_action_off_screen": evidence.get("active_action_off_screen", 1) == 0,
            "no_malformed_action_crashes": evidence.get("malformed_action_crashes", 1) == 0,
            "stable_board_restoration": evidence.get("board_restore_success_rate", 0) >= 1,
            "correct_answer_lock": evidence.get("answer_lock_pass_rate", 0) >= 1,
            "grounded_curriculum_retrieval": evidence.get("grounded_retrieval_rate", 0) >= 1,
            "one_teaching_moment": evidence.get("one_teaching_moment_rate", 0) >= 1,
            "active_action_visible": evidence.get("active_action_visible_rate", 0) >= 1,
            "phone_no_horizontal_overflow": evidence.get("phone_horizontal_overflow_count", 1) == 0,
            "khmer_text_wraps": evidence.get("khmer_text_wrap_success_rate", 0) >= 1,
            "stale_events_rejected": evidence.get("stale_stream_events_rendered", 1) == 0,
            "timeline_controls": evidence.get("timeline_controls_pass_rate", 0) >= 1,
            "student_task_interactive": evidence.get("student_task_interactive_rate", 0) >= 1,
        }


_instance: VisualTutorTelemetry | None = None


def get_visual_tutor_telemetry() -> VisualTutorTelemetry:
    global _instance
    if _instance is None:
        _instance = VisualTutorTelemetry()
    return _instance


def record_turn_response(response: Any, *, curriculum_confidence: float | None = None) -> None:
    """Emit a safe response summary after policy enforcement."""
    telemetry = get_visual_tutor_telemetry()
    metadata = getattr(response, "metadata", {}) or {}
    actions = getattr(response, "board_actions", []) or []
    behavior = getattr(response, "tutor_behavior", None)
    decision = getattr(behavior, "metadata", {}).get("adaptive_tutor_decision", {}) if behavior else {}
    telemetry.record_event("visual_tutor.turn.completed", outcome="answer_reveal" if not response.final_answer_locked else "waiting",
                           tutor_move=decision.get("tutor_move"), representation=metadata.get("representation"),
                           misconception_category=metadata.get("misconception_type"))
    telemetry.record_event("visual_tutor.board.actions", value=len(actions), unit="actions")
    if curriculum_confidence is not None:
        telemetry.record_event("visual_tutor.retrieval.confidence", value=max(0, min(1, curriculum_confidence)), unit="ratio")
