import pytest
from pydantic import ValidationError

from api.models.visual_tutor import VisualTutorClientTelemetryBatch
from api.services.visual_tutor.client_telemetry import VisualTutorClientTelemetryIngestor


def _batch() -> VisualTutorClientTelemetryBatch:
    return VisualTutorClientTelemetryBatch.model_validate({
        "events": [{"kind": "latency", "metric": "stream_to_visible", "duration_ms": 42}],
        "device_class": "mobile", "viewport_bucket": "sm", "reduced_motion": False,
    })


def test_client_telemetry_schema_rejects_text_and_identifiers() -> None:
    payload = _batch().model_dump()
    payload["student_text"] = "Solve x = 5"
    with pytest.raises(ValidationError):
        VisualTutorClientTelemetryBatch.model_validate(payload)
    payload = _batch().model_dump()
    payload["events"][0]["action_id"] = "secret-action"
    with pytest.raises(ValidationError):
        VisualTutorClientTelemetryBatch.model_validate(payload)


def test_ingestion_deduplicates_without_logging_payload() -> None:
    ingestor = VisualTutorClientTelemetryIngestor()
    assert ingestor.ingest(authenticated_user="verified-user", batch=_batch()) == "accepted"
    assert ingestor.ingest(authenticated_user="verified-user", batch=_batch()) == "duplicate"
