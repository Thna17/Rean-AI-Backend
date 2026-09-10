"""Content-free client telemetry ingestion with local safety limits."""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque

from api.models.visual_tutor import VisualTutorClientTelemetryBatch
from api.services.visual_tutor.observability import get_visual_tutor_telemetry


class VisualTutorClientTelemetryIngestor:
    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._dedupe: dict[str, float] = {}

    def ingest(self, *, authenticated_user: str, batch: VisualTutorClientTelemetryBatch) -> str:
        now = time.monotonic()
        window = self._windows[authenticated_user]
        while window and window[0] < now - 60:
            window.popleft()
        if len(window) >= 30:
            return "rate_limited"
        digest = hashlib.sha256(batch.model_dump_json().encode()).hexdigest()
        if self._dedupe.get(digest, 0) > now - 60:
            return "duplicate"
        window.append(now)
        self._dedupe[digest] = now
        telemetry = get_visual_tutor_telemetry()
        for event in batch.events:
            tags = {"device_class": batch.device_class, "screen_class": batch.viewport_bucket,
                    "reduced_motion": str(batch.reduced_motion).lower()}
            if event.lifecycle:
                telemetry.record_event("visual_tutor.client.action", value=event.count,
                                       lifecycle=event.lifecycle, **tags)
            elif event.metric and event.duration_ms is not None:
                telemetry.record_event(f"visual_tutor.client.{event.metric}_ms",
                                       value=event.duration_ms, unit="ms", **tags)
            else:
                telemetry.record_event(f"visual_tutor.client.{event.kind}", value=event.count,
                                       outcome=event.outcome, **tags)
        return "accepted"


_ingestor = VisualTutorClientTelemetryIngestor()

def get_client_telemetry_ingestor() -> VisualTutorClientTelemetryIngestor:
    return _ingestor


CLIENT_TELEMETRY_ALERTS = {
    "stream_to_visible_p95_ms": {"warn_above": 3000},
    "board_conflict_rate": {"warn_above": 0.01},
    "recovery_failure_rate": {"warn_above": 0.01},
    "off_screen_action_count": {"warn_above": 0},
}
