"""Acceptance checks for privacy-safe Visual Tutor operational telemetry."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from api.services.visual_tutor.observability import VisualTutorTelemetry, record_turn_response


_MATRIX_PATH = Path(__file__).parent / "fixtures" / "visual_tutor_release_acceptance_matrix.json"


def test_structured_events_drop_raw_or_sensitive_values_even_in_allowed_tag_names(monkeypatch) -> None:
    """Logs must contain bounded labels, never student or protected data."""
    telemetry = VisualTutorTelemetry()
    monkeypatch.setattr(
        "api.services.visual_tutor.observability.get_telemetry",
        lambda: SimpleNamespace(record_metric=lambda *args, **kwargs: None),
    )

    telemetry.record_event(
        "visual_tutor.board.action",
        action_type="write_equation",
        lifecycle="rendered",
        subject="Mathematics",
        grade=10,
        language="khmer",
        # These must never become log tags, regardless of their key.
        student_text="Solve 2x + 5 = 15",
        hidden_answer="x = 5",
        user_id="student-123",
        access_token="secret-token",
        learner_evidence="often confuses subtraction",
        # A free-form reason is equally unsafe; only a bounded reason label is allowed.
        reason="Student wrote: 2x + 5 = 15",
    )

    event = telemetry.events[-1]
    assert event["tags"] == {
        "action_type": "write_equation",
        "lifecycle": "rendered",
        "subject": "mathematics",
        "grade": "10",
        "language": "khmer",
    }
    serialized = json.dumps(event, ensure_ascii=False)
    for forbidden in (
        "2x + 5 = 15",
        "x = 5",
        "student-123",
        "secret-token",
        "often confuses",
    ):
        assert forbidden not in serialized


def test_turn_summary_records_only_safe_outcomes_and_bounded_operational_labels(monkeypatch) -> None:
    telemetry = VisualTutorTelemetry()
    monkeypatch.setattr(
        "api.services.visual_tutor.observability.get_visual_tutor_telemetry",
        lambda: telemetry,
    )
    monkeypatch.setattr(
        "api.services.visual_tutor.observability.get_telemetry",
        lambda: SimpleNamespace(record_metric=lambda *args, **kwargs: None),
    )
    response = SimpleNamespace(
        final_answer_locked=True,
        board_actions=[SimpleNamespace(), SimpleNamespace()],
        tutor_behavior=SimpleNamespace(metadata={
            "adaptive_tutor_decision": {"tutor_move": "reteach"},
        }),
        metadata={
            "representation": "free_body_diagram",
            "misconception_type": "sign_direction",
            "student_text": "My private attempt is 40 N",
            "hidden_answer": "50 N",
            "learner_model_summary": {"private": "do not log"},
        },
    )

    record_turn_response(response, curriculum_confidence=1.4)

    assert telemetry.events[0] == {
        "event": "visual_tutor.turn.completed",
        "value": 1,
        "unit": "count",
        "tags": {
            "outcome": "waiting",
            "tutor_move": "reteach",
            "representation": "free_body_diagram",
            "misconception_category": "sign_direction",
        },
    }
    assert telemetry.events[1] == {
        "event": "visual_tutor.board.actions",
        "value": 2,
        "unit": "actions",
        "tags": {},
    }
    assert telemetry.events[2]["event"] == "visual_tutor.retrieval.confidence"
    assert telemetry.events[2]["value"] == 1
    assert "private attempt" not in json.dumps(telemetry.events, ensure_ascii=False)


def test_board_action_lifecycle_tracks_only_supported_states_and_off_screen_signal(monkeypatch) -> None:
    telemetry = VisualTutorTelemetry()
    monkeypatch.setattr(
        "api.services.visual_tutor.observability.get_telemetry",
        lambda: SimpleNamespace(record_metric=lambda *args, **kwargs: None),
    )

    for lifecycle in ("received", "validated", "rendered", "skipped"):
        telemetry.record_board_action(lifecycle, action_type="draw_free_body_diagram")
    telemetry.record_board_action(
        "rendered", action_type="draw_free_body_diagram", off_screen=True,
    )
    telemetry.record_board_action("not-a-real-state", action_type="write_text")

    assert [event["tags"]["lifecycle"] for event in telemetry.events[:4]] == [
        "received", "validated", "rendered", "skipped",
    ]
    assert telemetry.events[-1] == {
        "event": "visual_tutor.board.action_off_screen",
        "value": 1,
        "unit": "count",
        "tags": {
            "lifecycle": "rendered",
            "action_type": "draw_free_body_diagram",
        },
    }
    assert len(telemetry.events) == 6


def test_release_acceptance_matrix_covers_the_supported_school_and_device_surface() -> None:
    matrix = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))

    assert matrix["schema_version"] == 2
    assert set(matrix["subjects"]) == {"Mathematics", "Physics", "Chemistry"}
    assert set(matrix["grades"]) == {10, 11, 12}
    assert set(matrix["languages"]) == {"khmer", "english", "bilingual"}
    profiles = matrix["device_profiles"]
    assert {(profile["id"], profile["width"], profile["height"], profile["class"])
            for profile in profiles} == {
        ("mobile-360-portrait", 360, 760, "mobile"),
        ("mobile-390-portrait", 390, 844, "mobile"),
        ("mobile-412-portrait", 412, 915, "mobile"),
        ("tablet-portrait", 900, 1200, "tablet"),
        ("desktop", 1440, 900, "desktop"),
        ("tablet-landscape", 1180, 760, "landscape"),
    }
    assert len({
        (subject, grade, language, profile["id"])
        for subject in matrix["subjects"]
        for grade in matrix["grades"]
        for language in matrix["languages"]
        for profile in profiles
    }) == 162


def test_release_gates_fail_closed_and_pass_only_with_complete_evidence() -> None:
    telemetry = VisualTutorTelemetry()
    matrix = json.loads(_MATRIX_PATH.read_text(encoding="utf-8"))

    failed = telemetry.evaluate_release_gates({})
    assert set(failed) == set(matrix["required_gates"])
    assert not any(failed.values())

    passed = telemetry.evaluate_release_gates({
        "active_action_off_screen": 0,
        "malformed_action_crashes": 0,
        "board_restore_success_rate": 1.0,
        "answer_lock_pass_rate": 1.0,
        "grounded_retrieval_rate": 1.0,
        "one_teaching_moment_rate": 1.0,
        "active_action_visible_rate": 1.0,
        "phone_horizontal_overflow_count": 0,
        "khmer_text_wrap_success_rate": 1.0,
        "stale_stream_events_rendered": 0,
        "timeline_controls_pass_rate": 1.0,
        "student_task_interactive_rate": 1.0,
    })
    assert passed == {gate: True for gate in matrix["required_gates"]}
