"""Shared fixtures for the end-to-end suite.

These tests talk to running services over HTTP. Nothing here imports application
code, so a test can only pass if the real request/response path works — which is
the whole point: the unit suites already cover everything inside each process.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

import httpx
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

GATEWAY_BASE = os.getenv("E2E_GATEWAY_BASE", "http://localhost:4000/api/v1")
AI_BASE = os.getenv("E2E_AI_BASE", "http://localhost:8001")

# The gateway only trusts these browser origins (CORS_ALLOWED_ORIGINS), so every
# student-shaped request sends one.
STUDENT_ORIGIN = "http://localhost:53123"

# Development-only student identity. Enabled by ALLOW_DEVELOPMENT_FALLBACKS and
# refused outright in staging or production by config/env.ts.
DEMO_TOKEN = os.getenv("E2E_DEMO_TOKEN", "demo-token")

# The statuses the public tutor-turn contract carries. The gateway rejects a turn
# reporting anything else, and the AI service declares the same set in
# api/routes/math_verifier.py.
PUBLIC_VERIFICATION_STATUSES = frozenset(
    {
        "correct",
        "mathematically_valid_but_inefficient",
        "invalid",
        "incomplete",
        "cannot_verify",
    }
)

KHMER = re.compile(r"[ក-៿]")
# Terms the Khmer curriculum copy keeps in Latin script.
_LATIN_EXCEPTIONS = ("STEM", "AI", "ReanAI")

SLOW_TURN_TIMEOUT = 240.0


def latin_prose(text: str) -> list[str]:
    """Runs of Latin letters that are not an allowed technical term."""
    stripped = text
    for term in _LATIN_EXCEPTIONS:
        stripped = stripped.replace(term, " ")
    return re.findall(r"[A-Za-z]{4,}", stripped)


def _internal_token() -> str:
    """Read the gateway↔AI-service secret from the env file, never hardcode it."""
    env_file = REPO_ROOT / "ai-service" / ".env"
    override = os.getenv("VISUAL_TUTOR_INTERNAL_TOKEN")
    if override:
        return override.strip()
    if not env_file.exists():
        pytest.skip(f"{env_file} is missing; cannot authenticate to the AI service")
    for line in env_file.read_text().splitlines():
        if line.startswith("VISUAL_TUTOR_INTERNAL_TOKEN="):
            return line.split("=", 1)[1].strip()
    pytest.skip("VISUAL_TUTOR_INTERNAL_TOKEN is not set in ai-service/.env")


def _wait_for(url: str, name: str, timeout: float = 90.0) -> None:
    """The AI service loads STT/TTS models first and needs ~25s to answer."""
    deadline = time.monotonic() + timeout
    last: str = "no attempt made"
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code < 500:
                return
            last = f"HTTP {response.status_code}"
        except Exception as exc:  # noqa: BLE001 - reported verbatim below
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(2.0)
    pytest.skip(
        f"{name} did not become ready at {url} within {timeout:.0f}s ({last}). "
        "Start the stack first — see e2e/README.md."
    )


@pytest.fixture(scope="session", autouse=True)
def _stack_is_up() -> None:
    _wait_for(f"{AI_BASE}/health", "ai-service")
    _wait_for(f"{GATEWAY_BASE}/health", "gateway")


@pytest.fixture(scope="session")
def internal_token() -> str:
    return _internal_token()


@pytest.fixture
def student_id() -> str:
    """A fresh identity per test.

    The AI service caches solutions in-process and the rate limiter shares keys,
    so tests that reuse an id can pass only because of the order they ran in.
    """
    return f"e2e-{uuid.uuid4().hex[:12]}"


class GatewayClient:
    """The public API, exactly as the student app reaches it."""

    def __init__(self, client: httpx.Client) -> None:
        self._client = client

    def _headers(self, token: str | None = DEMO_TOKEN) -> dict[str, str]:
        headers = {"Origin": STUDENT_ORIGIN, "Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        token: str | None = DEMO_TOKEN,
        timeout: float = SLOW_TURN_TIMEOUT,
    ) -> httpx.Response:
        return self._client.post(
            f"{GATEWAY_BASE}{path}",
            json=body,
            headers=self._headers(token),
            timeout=timeout,
        )

    def get(
        self,
        path: str,
        *,
        token: str | None = DEMO_TOKEN,
        timeout: float = 60.0,
    ) -> httpx.Response:
        return self._client.get(
            f"{GATEWAY_BASE}{path}",
            headers=self._headers(token),
            timeout=timeout,
        )

    def turn(
        self,
        message: str,
        *,
        subject: str = "Mathematics",
        language_mode: str = "english",
        action: str = "submit_problem",
        topic: str | None = None,
        metadata: dict[str, Any] | None = None,
        session_id: str | None = None,
        **extra: Any,
    ) -> httpx.Response:
        body: dict[str, Any] = {
            "subject": subject,
            "message": message,
            "action": action,
            "language_mode": language_mode,
        }
        if topic is not None:
            body["topic"] = topic
        if metadata is not None:
            body["metadata"] = metadata
        if session_id is not None:
            body["session_id"] = session_id
        body.update(extra)
        return self.post("/tutor/turn", body)

    def solve(self, message: str, **kwargs: Any) -> dict[str, Any]:
        """A turn that must succeed, returned as its decoded body."""
        response = self.turn(message, **kwargs)
        assert response.status_code == 200, (
            f"the gateway refused a turn it should accept: "
            f"HTTP {response.status_code} {response.text[:400]}"
        )
        return response.json()


@pytest.fixture
def gateway() -> Iterator[GatewayClient]:
    with httpx.Client(follow_redirects=False) as client:
        yield GatewayClient(client)


class AiServiceClient:
    """The internal service, reached the way only the gateway is meant to."""

    def __init__(self, client: httpx.Client, token: str) -> None:
        self._client = client
        self._token = token

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        user_id: str | None = "e2e-internal",
        token: str | None = None,
        timeout: float = SLOW_TURN_TIMEOUT,
    ) -> httpx.Response:
        headers = {"Content-Type": "application/json"}
        resolved = self._token if token is None else token
        if resolved:
            headers["X-Visual-Tutor-Internal-Token"] = resolved
        if user_id is not None:
            headers["X-Visual-Tutor-User-Id"] = user_id
        return self._client.post(
            f"{AI_BASE}{path}", json=body, headers=headers, timeout=timeout
        )

    def get(self, path: str, *, timeout: float = 30.0) -> httpx.Response:
        return self._client.get(f"{AI_BASE}{path}", timeout=timeout)


@pytest.fixture
def ai_service(internal_token: str) -> Iterator[AiServiceClient]:
    with httpx.Client() as client:
        yield AiServiceClient(client, internal_token)


def board_actions(turn: dict[str, Any]) -> list[dict[str, Any]]:
    return (turn.get("teaching_plan") or {}).get("visible_board_actions") or []


def board_text(turn: dict[str, Any]) -> str:
    """Everything written on the board, for assertions about what a student reads."""
    parts: list[str] = []
    for action in board_actions(turn):
        for key in ("text", "latex"):
            value = action.get(key)
            if isinstance(value, str) and value.strip():
                parts.append(value)
    return "\n".join(parts)


def teaching_message(turn: dict[str, Any]) -> str:
    return str((turn.get("teaching_plan") or {}).get("teaching_message") or "")


def assert_contract_shape(turn: dict[str, Any]) -> None:
    """Fields the Flutter client needs, and the ones it silently drops without."""
    for key in (
        "schema_version",
        "session_id",
        "turn_id",
        "board_version",
        "base_board_version",
        "board_update_mode",
        "lesson_state",
        "tutor_status",
        "teaching_plan",
        "verification",
    ):
        assert key in turn, f"the public turn is missing {key!r}: {sorted(turn)}"

    verification = turn["verification"]
    assert set(verification) == {
        "status",
        "verified",
        "concise_evidence",
        "student_facing_feedback",
    }, f"verification carries keys the gateway forbids: {sorted(verification)}"
    assert verification["status"] in PUBLIC_VERIFICATION_STATUSES, (
        f"status {verification['status']!r} is outside the public contract, which "
        "makes the gateway reject the whole turn"
    )
    assert isinstance(verification["verified"], bool)

    for action in board_actions(turn):
        for key in (
            "action_id",
            "problem_instance_id",
            "active_step_id",
            "board_version",
            "base_board_version",
        ):
            assert key in action, (
                f"board action {action.get('id')!r} is missing {key!r}; the Flutter "
                "client drops such an action silently"
            )


def assert_no_secret_leak(text: str, internal_token: str) -> None:
    lowered = text.lower()
    assert internal_token not in text, "a response echoed the internal service token"
    for marker in ("private_key", "firebase_private", "begin private key"):
        assert marker not in lowered, f"a response leaked {marker!r}"


def parse_sse(raw: str) -> list[dict[str, Any]]:
    """Decode an SSE body into its data payloads, in arrival order."""
    events: list[dict[str, Any]] = []
    for block in re.split(r"\r?\n\r?\n", raw):
        data = [
            line.split(":", 1)[1].strip()
            for line in block.splitlines()
            if line.startswith("data:")
        ]
        if not data:
            continue
        try:
            payload = json.loads("\n".join(data))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events
