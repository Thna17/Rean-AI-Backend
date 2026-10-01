"""The boundaries that must never open.

These are the highest-value tests here: a regression in any of them exposes one
student's work to another, or turns the internal AI service into a public API.
"""

from __future__ import annotations

import pytest

from conftest import AI_BASE, GATEWAY_BASE, STUDENT_ORIGIN, assert_no_secret_leak

import httpx


class TestGatewayRequiresAStudent:
    def test_no_token_is_rejected(self, gateway):
        response = gateway.get("/progress/dashboard", token=None)
        assert response.status_code in (401, 403), (
            f"the gateway served student data with no token: {response.status_code}"
        )

    def test_a_garbage_token_is_rejected(self, gateway):
        response = gateway.get("/progress/dashboard", token="not-a-real-token")
        assert response.status_code in (401, 403)

    def test_a_turn_cannot_be_taken_anonymously(self, gateway):
        response = gateway.post(
            "/tutor/turn",
            {"subject": "Mathematics", "message": "Solve 3x + 7 = 22"},
            token=None,
            timeout=60.0,
        )
        assert response.status_code in (401, 403)


class TestAiServiceIsInternalOnly:
    """It must never behave like a second public API."""

    def test_no_internal_token_is_forbidden(self, ai_service):
        response = ai_service.post(
            "/api/v1/visual_tutor/turn",
            {"user_id": "e2e", "subject": "Mathematics", "message": "Solve x + 1 = 2"},
            token="",
            timeout=60.0,
        )
        assert response.status_code in (401, 403, 503), response.text[:200]

    def test_a_wrong_internal_token_is_forbidden(self, ai_service):
        response = ai_service.post(
            "/api/v1/visual_tutor/turn",
            {"user_id": "e2e", "subject": "Mathematics", "message": "Solve x + 1 = 2"},
            token="wrong-token-entirely",
            timeout=60.0,
        )
        assert response.status_code == 403, response.text[:200]

    def test_a_valid_token_without_a_user_is_unauthenticated(self, ai_service):
        response = ai_service.post(
            "/api/v1/visual_tutor/turn",
            {"user_id": "e2e", "subject": "Mathematics", "message": "Solve x + 1 = 2"},
            user_id=None,
            timeout=60.0,
        )
        assert response.status_code == 401, response.text[:200]

    def test_a_body_cannot_claim_a_different_user_than_the_header(self, ai_service):
        """The gateway supplies the verified uid; the body must not override it."""
        response = ai_service.post(
            "/api/v1/visual_tutor/turn",
            {
                "user_id": "someone-else",
                "subject": "Mathematics",
                "message": "Solve 3x + 7 = 22",
            },
            user_id="e2e-real-owner",
            timeout=120.0,
        )
        assert response.status_code == 403, (
            "a body-supplied user_id was accepted over the authenticated header: "
            f"{response.status_code} {response.text[:200]}"
        )


class TestOneStudentCannotReadAnother:
    def test_a_session_is_readable_only_by_its_owner(self, gateway, internal_token):
        """Create a session as the demo student, then try to read it as someone else.

        The demo token is the only student identity the gateway will mint here, so
        the second read goes to the AI service with a different authenticated uid —
        the same check `tutor-session.routes.ts` delegates to.
        """
        turn = gateway.solve("Solve 3x + 7 = 22")
        session_id = turn["session_id"]

        with httpx.Client() as client:
            intruder = client.get(
                f"{AI_BASE}/api/v1/visual_tutor/sessions/{session_id}",
                headers={
                    "X-Visual-Tutor-Internal-Token": internal_token,
                    "X-Visual-Tutor-User-Id": "e2e-intruder",
                },
                timeout=30.0,
            )

        assert intruder.status_code in (403, 404), (
            "another student read this session: "
            f"{intruder.status_code} {intruder.text[:300]}"
        )
        assert session_id not in intruder.text or intruder.status_code != 200


class TestErrorsDoNotLeak:
    def test_a_rejected_request_reveals_no_secret(self, gateway, internal_token):
        response = gateway.post(
            "/tutor/turn", {"subject": "Mathematics"}, timeout=60.0
        )
        assert_no_secret_leak(response.text, internal_token)

    def test_an_unauthenticated_error_reveals_no_secret(self, gateway, internal_token):
        response = gateway.get("/progress/dashboard", token=None)
        assert_no_secret_leak(response.text, internal_token)

    def test_a_validation_error_carries_no_stack_trace(self, gateway):
        """A request the gateway itself rejects must stay clean."""
        response = gateway.post(
            "/tutor/turn", {"subject": "Mathematics"}, timeout=60.0
        )
        assert "stack" not in response.text.lower(), response.text[:200]

    @pytest.mark.xfail(
        strict=True,
        reason="An upstream failure is reported with a `stack` field. Development "
        "mode makes that acceptable locally, but the same handler serves "
        "production, so this needs an explicit environment guard before launch.",
    )
    def test_an_upstream_failure_carries_no_stack_trace(self, gateway):
        first = gateway.solve("Solve 3x + 7 = 22")
        response = gateway.turn(
            "Why do we subtract 7 first?",
            session_id=first["session_id"],
            action="request_hint",
        )
        assert response.status_code != 200, "expected the known follow-up failure"
        assert "stack" not in response.text.lower(), response.text[:300]


def test_cors_rejects_an_origin_the_student_app_never_uses():
    """Only ports 53123 and 53124 are trusted, per CLAUDE.md §2.2."""
    with httpx.Client() as client:
        response = client.options(
            f"{GATEWAY_BASE}/tutor/turn",
            headers={
                "Origin": "http://evil.example",
                "Access-Control-Request-Method": "POST",
            },
            timeout=30.0,
        )
    allowed = response.headers.get("access-control-allow-origin")
    assert allowed != "http://evil.example", (
        "an untrusted origin was granted CORS access"
    )
    assert allowed != "*", "the gateway must not answer with a wildcard origin"


def test_cors_accepts_the_student_app_origin():
    with httpx.Client() as client:
        response = client.options(
            f"{GATEWAY_BASE}/tutor/turn",
            headers={
                "Origin": STUDENT_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
            timeout=30.0,
        )
    assert response.headers.get("access-control-allow-origin") == STUDENT_ORIGIN, (
        "the student app's own origin was refused, which would break the web app"
    )
